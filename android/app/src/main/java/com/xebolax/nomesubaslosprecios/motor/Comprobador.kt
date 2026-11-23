package com.xebolax.nomesubaslosprecios.motor

import android.content.Context
import android.util.Log
import com.xebolax.nomesubaslosprecios.datos.BaseDatos
import com.xebolax.nomesubaslosprecios.datos.Preferencias
import com.xebolax.nomesubaslosprecios.nucleo.Aviso
import com.xebolax.nomesubaslosprecios.nucleo.Confianza
import com.xebolax.nomesubaslosprecios.nucleo.Extractor
import com.xebolax.nomesubaslosprecios.nucleo.Fechas
import com.xebolax.nomesubaslosprecios.nucleo.Lectura
import com.xebolax.nomesubaslosprecios.nucleo.LogicaAvisos
import com.xebolax.nomesubaslosprecios.nucleo.ModoDescarga
import com.xebolax.nomesubaslosprecios.nucleo.Producto
import com.xebolax.nomesubaslosprecios.nucleo.ReglasTiendas
import com.xebolax.nomesubaslosprecios.nucleo.ResultadoExtraccion
import com.xebolax.nomesubaslosprecios.nucleo.SelectoresUsuario
import com.xebolax.nomesubaslosprecios.nucleo.Tienda
import com.xebolax.nomesubaslosprecios.nucleo.dominioDe
import com.xebolax.nomesubaslosprecios.nucleo.leerJson
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.Semaphore
import kotlinx.coroutines.sync.withPermit
import kotlinx.coroutines.withContext
import java.util.concurrent.atomic.AtomicInteger
import kotlin.math.abs
import kotlin.random.Random

/** Progreso de una comprobación de todos los productos (para la pantalla y la notificación). */
data class Progreso(val hechos: Int, val total: Int, val manual: Boolean)

/** Cómo terminó una comprobación de varios productos. */
data class ResumenComprobacion(val total: Int, val comprobados: Int, val cambios: Int, val errores: Int, val avisos: Int, val pendientes: Int)

/** Resultado de comprobar un solo producto. */
data class ResultadoUno(val producto: Producto, val avisos: List<Aviso>, val error: String?, val cambio: Boolean)

/**
 * El motor de comprobación: API de la tienda, descarga directa o navegador
 * integrado, extracción, lógica de avisos, guardado y notificación. Tiendas
 * distintas en paralelo (como mucho 3 a la vez) y, dentro de una tienda, con
 * una pausa entre página y página.
 */
object Comprobador {

	private const val ETIQUETA = "Comprobador"
	const val MAX_TIENDAS_A_LA_VEZ = 3

	/** Solo una comprobación general a la vez (la periódica o la manual). */
	private val cerrojo = Mutex()

	private val _progreso = MutableStateFlow<Progreso?>(null)
	/** null si no hay ninguna comprobación general en curso. */
	val progreso: StateFlow<Progreso?> = _progreso

	@Volatile
	private var reglas: ReglasTiendas? = null

	/** tiendas.json de los assets, cargado una sola vez. */
	fun reglas(contexto: Context): ReglasTiendas {
		reglas?.let { return it }
		synchronized(this) {
			reglas?.let { return it }
			val cargadas = try {
				ReglasTiendas.leer(contexto.assets.open("tiendas.json").bufferedReader(Charsets.UTF_8).use { it.readText() })
			} catch (e: Exception) {
				Log.e(ETIQUETA, "No se pudo leer tiendas.json: se usará solo la extracción genérica", e)
				ReglasTiendas.VACIAS
			}
			reglas = cargadas
			return cargadas
		}
	}

	private fun registro(texto: String, e: Throwable?) {
		Log.d(ETIQUETA, texto, e)
	}

	/** Importe de la huella del selector elegido ({"importe": 39.99, "contexto": "...", "atributo": "content"}). */
	fun importeHuella(huella: String?): Double? = ((leerJson(huella) as? Map<*, *>)?.get("importe") as? Number)?.toDouble()

	/** Atributo de la huella del que se lee el importe (vacío: el texto). */
	fun atributoHuella(huella: String?): String? = ((leerJson(huella) as? Map<*, *>)?.get("atributo") as? String)?.ifEmpty { null }

	fun selectores(p: Producto?, t: Tienda?) = SelectoresUsuario(
		precioProducto = p?.selectorPrecio,
		precioTienda = t?.selectorPrecio,
		tituloTienda = t?.selectorTitulo,
		disponibleTienda = t?.selectorDisponible,
		huellaImporte = importeHuella(p?.huellaSelector),
		huellaAtributo = atributoHuella(p?.huellaSelector),
		variante = p?.variante,
	)

	/** ¿La página parece montada con JavaScript (muy poco texto visible o un contenedor de aplicación vacío)? */
	private fun pareceJavaScript(r: ResultadoExtraccion, html: String): Boolean {
		val doc = r.documento ?: return false
		val texto = doc.body()?.text()?.length ?: 0
		return texto < 300 || html.contains("__NEXT_DATA__") || doc.selectFirst("app-root:empty, #root:empty, #app:empty") != null
	}

	private suspend fun conNavegador(contexto: Context, url: String, s: SelectoresUsuario, nombreTienda: String?): ResultadoExtraccion? {
		val reglas = reglas(contexto)
		Log.i(ETIQUETA, "Se prueba con el navegador integrado: $url")
		val html = Navegador.cargar(contexto, url) { h ->
			Extractor.extraer(h, url, reglas, s, nombreTienda).precio != null
		} ?: return null
		Log.i(ETIQUETA, "Navegador integrado: ${html.length} caracteres")
		return withContext(Dispatchers.Default) { Extractor.extraer(html, url, reglas, s, nombreTienda, 200, ::registro) }
	}

	/** Página descargada (directa o con el navegador) para elegir el precio: el resultado con su documento. Lanza ErrorDescarga. */
	suspend fun extraer(contexto: Context, url: String, selectores: SelectoresUsuario, nombreTienda: String?, tienda: Tienda? = null): ResultadoExtraccion {
		val reglas = reglas(contexto)
		val regla = reglas.para(dominioDe(url))
		// 2 bis. API de la tienda, antes que el HTML (si el usuario no ha puesto selectores propios)
		val api = regla?.api
		if (api != null && selectores.precioProducto.isNullOrBlank() && selectores.precioTienda.isNullOrBlank()) {
			api.urlPara(url)?.let { urlApi ->
				try {
					val pagina = Descargador.descargar(urlApi, Preferencias(contexto).tiempoEspera, aceptar = "application/json")
					val r = api.extraer(pagina.html)
					Log.i(ETIQUETA, "API de ${regla.nombre}: código ${pagina.codigo}, precio ${r?.precio}")
					if (r != null && (r.precio != null || r.disponible == false)) return r
				} catch (e: CancellationException) {
					throw e
				} catch (e: ErrorDescarga) {
					Log.w(ETIQUETA, "La API de ${regla.nombre} no respondió; se sigue con la página", e)
				}
			}
		}
		val modo = tienda?.modoDescarga ?: ModoDescarga.AUTO
		val navegadorPrimero = modo == ModoDescarga.NAVEGADOR || (modo == ModoDescarga.AUTO && regla?.navegador == true)
		if (navegadorPrimero) {
			conNavegador(contexto, url, selectores, nombreTienda)?.let { return it }
			if (modo == ModoDescarga.NAVEGADOR) throw ErrorDescarga(MensajesNavegador.SIN_NAVEGADOR)
		}
		val r = try {
			val pagina = Descargador.descargar(url, Preferencias(contexto).tiempoEspera)
			Log.i(ETIQUETA, "Descargada $url: código ${pagina.codigo}, ${pagina.html.length} caracteres, final ${pagina.urlFinal}")
			withContext(Dispatchers.Default) {
				Extractor.extraer(pagina.html, url, reglas, selectores, nombreTienda, pagina.codigo, ::registro) to pagina.html
			}
		} catch (e: ErrorDescarga) {
			// Bloqueada a la descarga normal: en automático se prueba con el navegador integrado
			if (modo == ModoDescarga.AUTO && e.bloqueo && !navegadorPrimero) {
				conNavegador(contexto, url, selectores, nombreTienda)?.let { return it }
			}
			// 1.1.0: algunas protecciones (Akamai en G2A) dejan la descarga colgada en vez de rechazarla.
			// Un fallo de DNS o de red no llega aquí (es «sin conexión»). Si el navegador tampoco puede,
			// se da el error de la descarga normal (una cancelación sí se propaga).
			if (modo == ModoDescarga.AUTO && e.tiempoAgotado && !navegadorPrimero) {
				Log.i(ETIQUETA, "La descarga normal de $url no respondió; se prueba con el navegador integrado")
				val n = try {
					conNavegador(contexto, url, selectores, nombreTienda)
				} catch (c: CancellationException) {
					throw c
				} catch (otro: Exception) {
					Log.w(ETIQUETA, "El navegador integrado tampoco pudo con $url", otro)
					null
				}
				if (n != null) return n
				Log.i(ETIQUETA, "El navegador integrado tampoco pudo con $url")
			}
			throw e
		}
		val (resultado, html) = r
		Log.i(ETIQUETA, "Extracción de $url: precio ${resultado.precio} (${resultado.origenTexto}), error ${resultado.error}, título «${resultado.documento?.title()}»")
		if (modo == ModoDescarga.AUTO && !navegadorPrimero && (resultado.bloqueo || (resultado.precio == null && pareceJavaScript(resultado, html)))) {
			conNavegador(contexto, url, selectores, nombreTienda)?.let { n -> if (n.precio != null || n.disponible == false) return n }
		}
		return resultado
	}

	/** Comprueba un producto y guarda el resultado. No notifica (lo hace quien llama). */
	suspend fun comprobarUno(contexto: Context, id: Long): ResultadoUno? = withContext(Dispatchers.IO) {
		val db = BaseDatos.obtener(contexto)
		val p = db.producto(id) ?: return@withContext null
		val tienda = p.tiendaId?.let { db.tienda(it) }
		val nombreTienda = tienda?.nombre ?: reglas(contexto).nombrePara(dominioDe(p.url))
		val ajustes = Preferencias(contexto).ajustesAvisos
		val ahora = Fechas.ahora()
		val resultado = try {
			var r = extraer(contexto, p.url, selectores(p, tienda), nombreTienda, tienda)
			// Con confianza media o baja, un cambio de más del 50 % se vuelve a comprobar una vez
			val p0 = p.precioActual
			val p1 = r.precio
			if (p0 != null && p1 != null && r.confianza != Confianza.ALTA && abs(p1 - p0) / p0 > 0.5) {
				Log.i(ETIQUETA, "Cambio de más del 50 % con confianza ${r.confianza} en ${p.url}: se comprueba otra vez")
				delay(3000)
				r = extraer(contexto, p.url, selectores(p, tienda), nombreTienda, tienda)
			}
			val error = r.error
			if (error != null) LogicaAvisos.aplicarError(p, error, ajustes, ahora, nombreTienda)
			else LogicaAvisos.aplicarLectura(
				p,
				Lectura(r.precio, r.disponible ?: true, r.nombre, r.imagen, if (r.precio != null) r.moneda else null, r.origenTexto, r.confianza, r.desde),
				ajustes, ahora, nombreTienda,
			)
		} catch (e: CancellationException) {
			throw e
		} catch (e: ErrorDescarga) {
			Log.w(ETIQUETA, "No se pudo descargar ${p.url}: ${e.message}", e)
			LogicaAvisos.aplicarError(p, e.message.orEmpty(), ajustes, ahora, nombreTienda)
		} catch (e: Exception) {
			Log.e(ETIQUETA, "Error inesperado al comprobar ${p.url}", e)
			LogicaAvisos.aplicarError(p, "No se pudo comprobar el producto por un error inesperado.", ajustes, ahora, nombreTienda)
		}
		val avisos = db.guardarComprobacion(resultado.producto, resultado.historial, resultado.avisos)
		ResultadoUno(resultado.producto, avisos, resultado.producto.ultimoError?.ifEmpty { null }, resultado.cambio)
	}

	/** ¿Hay una comprobación general en marcha? */
	val enCurso: Boolean get() = cerrojo.isLocked

	/**
	 * Comprueba los productos activos. manual: todos y con notificación de
	 * progreso; si no, solo los que toca por el intervalo. limiteMs: tiempo
	 * máximo (el trabajo en segundo plano no debe pasar de unos 8 minutos);
	 * lo que no dé tiempo queda en «pendientes» para encadenar otro trabajo.
	 * Devuelve null si ya había otra comprobación en curso.
	 */
	suspend fun comprobarTodos(contexto: Context, manual: Boolean, limiteMs: Long? = null): ResumenComprobacion? {
		if (!cerrojo.tryLock()) return null
		try {
			return withContext(Dispatchers.IO) { comprobarTodosConCerrojo(contexto.applicationContext, manual, limiteMs) }
		} finally {
			_progreso.value = null
			if (manual) Notificaciones.quitarProgreso(contexto)
			cerrojo.unlock()
		}
	}

	private suspend fun comprobarTodosConCerrojo(contexto: Context, manual: Boolean, limiteMs: Long?): ResumenComprobacion {
		val db = BaseDatos.obtener(contexto)
		val prefs = Preferencias(contexto)
		val inicio = System.currentTimeMillis()
		val margen = prefs.intervaloHoras * 60L * 60 * 1000 * 3 / 4
		val todos = db.productos().map { it.producto }.filter { it.activo }
		val lista = (if (manual) todos else todos.filter { p ->
			val ultima = Fechas.ms(p.ultimaComprobacion) ?: 0L
			inicio - ultima >= margen
		}).sortedBy { Fechas.ms(it.ultimaComprobacion) ?: 0L }
		val total = lista.size
		val hechos = AtomicInteger(0)
		val cambios = AtomicInteger(0)
		val errores = AtomicInteger(0)
		val avisos = java.util.Collections.synchronizedList(mutableListOf<Aviso>())
		_progreso.value = Progreso(0, total, manual)
		if (manual && total > 0) Notificaciones.progreso(contexto, 0, total)
		val pausa = prefs.pausaEntrePeticiones * 1000L
		val porTienda = lista.groupBy { it.tiendaId ?: -dominioDe(it.url).hashCode().toLong() }
		val semaforo = Semaphore(MAX_TIENDAS_A_LA_VEZ)
		fun sinTiempo() = limiteMs != null && System.currentTimeMillis() - inicio > limiteMs
		coroutineScope {
			porTienda.values.map { productos ->
				async {
					semaforo.withPermit {
						productos.forEachIndexed { i, p ->
							if (sinTiempo()) return@withPermit
							if (i > 0) delay(pausa + Random.nextLong(0, 2001))
							val r = comprobarUno(contexto, p.id)
							if (r != null) {
								if (r.error != null) errores.incrementAndGet()
								if (r.cambio) cambios.incrementAndGet()
								avisos += r.avisos
							}
							val n = hechos.incrementAndGet()
							_progreso.value = Progreso(n, total, manual)
							if (manual) Notificaciones.progreso(contexto, n, total)
						}
					}
				}
			}.awaitAll()
		}
		db.purgarAvisos(prefs.conservarAvisosDias)
		val pendientes = total - hechos.get()
		if (pendientes == 0) prefs.ultimaComprobacionGeneral = System.currentTimeMillis()
		Notificaciones.avisar(contexto, avisos.toList())
		Log.i(ETIQUETA, "Comprobados ${hechos.get()} de $total productos: ${cambios.get()} cambios, ${errores.get()} errores, ${avisos.size} avisos")
		return ResumenComprobacion(total, hechos.get(), cambios.get(), errores.get(), avisos.size, pendientes)
	}
}

/** Mensajes del navegador integrado. */
object MensajesNavegador {
	const val SIN_NAVEGADOR = "No se pudo cargar la página con el navegador integrado de Android. Comprueba que «Android System WebView» está instalado y actualizado."
}
