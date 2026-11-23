package com.xebolax.nomesubaslosprecios.nucleo

import org.json.JSONArray
import org.json.JSONException
import org.json.JSONObject

/** Producto tal como va en el archivo: relaciones por uuid y su historial. */
data class ProductoExportado(
	val producto: Producto,
	val tiendaUuid: String?,
	val categoriaUuid: String?,
	val historial: List<PuntoHistorial>,
)

/** Aviso tal como va en el archivo: el producto por uuid. */
data class AvisoExportado(val productoUuid: String?, val aviso: Aviso)

/** El contenido completo de un archivo de intercambio (FORMATO_INTERCAMBIO.md). */
data class DatosIntercambio(
	val app: String = "android",
	val versionApp: String = "1.0.0",
	val exportado: String = Fechas.ahora(),
	val categorias: List<Categoria> = emptyList(),
	val tiendas: List<Tienda> = emptyList(),
	val productos: List<ProductoExportado> = emptyList(),
	val avisos: List<AvisoExportado> = emptyList(),
	/** Ajustes con las claves de la especificación (null si no se exportaron). */
	val ajustes: Map<String, Any?>? = null,
	/** Productos que se saltaron al leer (sin url o sin uuid). */
	val noValidos: Int = 0,
)

/** El archivo no se puede importar: el mensaje se muestra tal cual al usuario. */
class ArchivoNoValido(mensaje: String, causa: Throwable? = null) : Exception(mensaje, causa)

/**
 * Lectura y escritura del formato de intercambio entre Windows y Android.
 * Lógica pura (org.json para leer y EscritorJson para escribir con las
 * claves en orden), probada en la JVM con compartido/pruebas/exportacion-ejemplo.json.
 */
object Intercambio {

	const val FORMATO = "NoMeSubasLosPrecios"
	const val VERSION_FORMATO = 1

	const val ERROR_FORMATO = "Este archivo no es una exportación de No Me Subas Los Precios."
	const val ERROR_VERSION = "El archivo es de una versión más nueva de la app. Actualízala para importarlo."

	/** Claves de ajustes de la especificación que se exportan (más solo_wifi, propio de Android). */
	val CLAVES_AJUSTES = listOf(
		"intervalo_horas", "comprobar_al_iniciar", "avisar_bajadas", "avisar_subidas", "avisar_objetivo", "avisar_minimo",
		"avisar_disponible", "avisar_agotado", "avisar_errores", "cambio_minimo_porcentaje", "pausa_entre_peticiones",
		"tiempo_espera", "conservar_avisos_dias", "buscar_actualizaciones", "solo_wifi",
		// 1.1.0: colores de la lista
		"colores_lista", "colores_modo", "color_bajada", "color_subida", "color_objetivo", "color_problema",
		// 1.2.0: origen de las actualizaciones
		"origen_actualizaciones", "url_actualizaciones",
	)

	// --- Lectura ----------------------------------------------------------------------------

	private fun JSONObject.texto(clave: String): String? = if (isNull(clave)) null else opt(clave)?.toString()

	private fun JSONObject.numero(clave: String): Double? = when (val v = opt(clave)) {
		is Number -> redondear(v.toDouble())
		// Nunca deberían venir como texto, pero si vienen, se leen en formato de máquina
		is String -> importeDeMaquina(v)
		else -> null
	}

	private fun JSONObject.booleano(clave: String, porDefecto: Boolean): Boolean = when (val v = opt(clave)) {
		is Boolean -> v
		is Number -> v.toInt() != 0
		is String -> v.equals("true", ignoreCase = true) || v == "1"
		else -> porDefecto
	}

	private fun JSONObject.entero(clave: String, porDefecto: Int): Int = (opt(clave) as? Number)?.toInt() ?: porDefecto

	private fun objetos(a: JSONArray?): List<JSONObject> = if (a == null) emptyList() else (0 until a.length()).mapNotNull { a.optJSONObject(it) }

	/** Lee un archivo de intercambio. Lanza ArchivoNoValido con el mensaje para el usuario. */
	fun leer(json: String): DatosIntercambio {
		val raiz = try {
			JSONObject(json.removePrefix("﻿"))
		} catch (e: JSONException) {
			throw ArchivoNoValido(ERROR_FORMATO, e)
		}
		if (raiz.optString("formato") != FORMATO) throw ArchivoNoValido(ERROR_FORMATO)
		if (raiz.optInt("version_formato", 1) > VERSION_FORMATO) throw ArchivoNoValido(ERROR_VERSION)

		val categorias = objetos(raiz.optJSONArray("categorias")).mapIndexedNotNull { i, o ->
			val uuid = o.texto("uuid")?.trim().orEmpty()
			val nombre = o.texto("nombre")?.trim().orEmpty()
			if (uuid.isEmpty() || nombre.isEmpty()) null
			else Categoria(uuid = uuid, nombre = nombre, descripcion = o.texto("descripcion"), orden = o.entero("orden", i))
		}
		val tiendas = objetos(raiz.optJSONArray("tiendas")).mapNotNull { o ->
			val uuid = o.texto("uuid")?.trim().orEmpty()
			val dominio = o.texto("dominio")?.trim()?.lowercase().orEmpty()
			if (uuid.isEmpty() || dominio.isEmpty()) null
			else Tienda(
				uuid = uuid,
				nombre = o.texto("nombre")?.trim()?.ifEmpty { null } ?: nombreTiendaPorDominio(dominio),
				dominio = dominio,
				selectorPrecio = o.texto("selector_precio"),
				selectorTitulo = o.texto("selector_titulo"),
				selectorDisponible = o.texto("selector_disponible"),
				notas = o.texto("notas"),
				modoDescarga = o.texto("modo_descarga")?.takeIf { it in ModoDescarga.TODOS } ?: ModoDescarga.AUTO,
			)
		}
		var noValidos = 0
		val productos = objetos(raiz.optJSONArray("productos")).mapNotNull { o ->
			val uuid = o.texto("uuid")?.trim().orEmpty()
			val url = o.texto("url")?.trim().orEmpty()
			if (uuid.isEmpty() || url.isEmpty()) {
				noValidos++
				return@mapNotNull null
			}
			val historial = objetos(o.optJSONArray("historial")).mapNotNull { h ->
				val fecha = h.texto("fecha")?.trim().orEmpty()
				if (fecha.isEmpty()) null else PuntoHistorial(fecha, h.numero("precio"), h.booleano("disponible", true))
			}.sortedBy { it.fecha }
			ProductoExportado(
				producto = Producto(
					uuid = uuid,
					nombre = o.texto("nombre").orEmpty(),
					url = url,
					grupo = o.texto("grupo"),
					moneda = o.texto("moneda")?.ifBlank { null } ?: "EUR",
					precioActual = o.numero("precio_actual"),
					precioInicial = o.numero("precio_inicial"),
					precioMinimo = o.numero("precio_minimo"),
					precioMaximo = o.numero("precio_maximo"),
					precioAnterior = o.numero("precio_anterior"),
					precioObjetivo = o.numero("precio_objetivo"),
					fechaMinimo = o.texto("fecha_minimo"),
					fechaMaximo = o.texto("fecha_maximo"),
					fechaCambio = o.texto("fecha_cambio"),
					fechaAlta = o.texto("fecha_alta"),
					ultimaComprobacion = o.texto("ultima_comprobacion"),
					disponible = o.booleano("disponible", true),
					avisarDisponible = o.booleano("avisar_disponible", true),
					favorito = o.booleano("favorito", false),
					activo = o.booleano("activo", true),
					alertaPorcentaje = (o.opt("alerta_porcentaje") as? Number)?.toDouble() ?: 0.0,
					selectorPrecio = o.texto("selector_precio"),
					imagenUrl = o.texto("imagen_url"),
					notas = o.texto("notas"),
					ultimoError = o.texto("ultimo_error"),
					erroresSeguidos = o.entero("errores_seguidos", 0),
					variante = o.texto("variante"),
					origenPrecio = o.texto("origen_precio"),
					confianza = o.texto("confianza"),
					huellaSelector = o.texto("huella_selector"),
					desde = o.booleano("desde", false),
				),
				tiendaUuid = o.texto("tienda"),
				categoriaUuid = o.texto("categoria"),
				historial = historial,
			)
		}
		val avisos = objetos(raiz.optJSONArray("avisos")).mapNotNull { o ->
			val tipo = o.texto("tipo")?.trim().orEmpty()
			val fecha = o.texto("fecha")?.trim().orEmpty()
			if (tipo.isEmpty() || fecha.isEmpty()) null
			else AvisoExportado(
				o.texto("producto"),
				Aviso(fecha = fecha, tipo = tipo, titulo = o.texto("titulo").orEmpty(), mensaje = o.texto("mensaje").orEmpty(), leido = o.booleano("leido", false)),
			)
		}
		val ajustes = raiz.optJSONObject("ajustes")?.let { a ->
			LinkedHashMap<String, Any?>().apply {
				for (clave in a.keys()) if (clave in CLAVES_AJUSTES) put(clave, if (a.isNull(clave)) null else a.opt(clave))
			}
		}
		return DatosIntercambio(
			app = raiz.optString("app", "desconocida"),
			versionApp = raiz.optString("version_app"),
			exportado = raiz.optString("exportado"),
			categorias = categorias,
			tiendas = tiendas,
			productos = productos,
			avisos = avisos,
			ajustes = ajustes,
			noValidos = noValidos,
		)
	}

	// --- Escritura ----------------------------------------------------------------------------

	/** Escribe el archivo con las claves en el orden de FORMATO_INTERCAMBIO.md y sin ids internos. */
	fun escribir(d: DatosIntercambio): String {
		val raiz = LinkedHashMap<String, Any?>()
		raiz["formato"] = FORMATO
		raiz["version_formato"] = VERSION_FORMATO
		raiz["app"] = d.app
		raiz["version_app"] = d.versionApp
		raiz["exportado"] = d.exportado
		raiz["categorias"] = d.categorias.map { c ->
			linkedMapOf<String, Any?>("uuid" to c.uuid, "nombre" to c.nombre, "descripcion" to c.descripcion, "orden" to c.orden)
		}
		raiz["tiendas"] = d.tiendas.map { t ->
			linkedMapOf<String, Any?>(
				"uuid" to t.uuid, "nombre" to t.nombre, "dominio" to t.dominio, "selector_precio" to t.selectorPrecio,
				"selector_titulo" to t.selectorTitulo, "selector_disponible" to t.selectorDisponible, "notas" to t.notas,
				"modo_descarga" to t.modoDescarga,
			)
		}
		raiz["productos"] = d.productos.map { e ->
			val p = e.producto
			linkedMapOf<String, Any?>(
				"uuid" to p.uuid,
				"nombre" to p.nombre,
				"url" to p.url,
				"tienda" to e.tiendaUuid,
				"categoria" to e.categoriaUuid,
				"grupo" to p.grupo,
				"moneda" to p.moneda,
				"precio_actual" to p.precioActual,
				"precio_inicial" to p.precioInicial,
				"precio_minimo" to p.precioMinimo,
				"precio_maximo" to p.precioMaximo,
				"precio_anterior" to p.precioAnterior,
				"precio_objetivo" to p.precioObjetivo,
				"fecha_minimo" to p.fechaMinimo,
				"fecha_maximo" to p.fechaMaximo,
				"fecha_cambio" to p.fechaCambio,
				"fecha_alta" to p.fechaAlta,
				"ultima_comprobacion" to p.ultimaComprobacion,
				"disponible" to p.disponible,
				"avisar_disponible" to p.avisarDisponible,
				"favorito" to p.favorito,
				"activo" to p.activo,
				"alerta_porcentaje" to p.alertaPorcentaje,
				"selector_precio" to p.selectorPrecio,
				"imagen_url" to p.imagenUrl,
				"notas" to p.notas,
				"ultimo_error" to p.ultimoError?.ifEmpty { null },
				"errores_seguidos" to p.erroresSeguidos,
				"variante" to p.variante,
				"origen_precio" to p.origenPrecio,
				"confianza" to p.confianza,
				"huella_selector" to p.huellaSelector,
				"desde" to p.desde,
				"historial" to e.historial.sortedBy { it.fecha }.map { h ->
					linkedMapOf<String, Any?>("fecha" to h.fecha, "precio" to h.precio, "disponible" to h.disponible)
				},
			)
		}
		raiz["avisos"] = d.avisos.map { a ->
			linkedMapOf<String, Any?>(
				"producto" to a.productoUuid, "fecha" to a.aviso.fecha, "tipo" to a.aviso.tipo,
				"titulo" to a.aviso.titulo, "mensaje" to a.aviso.mensaje, "leido" to a.aviso.leido,
			)
		}
		d.ajustes?.let { raiz["ajustes"] = LinkedHashMap(it) }
		return EscritorJson.escribir(raiz)
	}

	/** Nombre propuesto al exportar: NoMeSubasLosPrecios-AAAA-MM-DD.json. */
	fun nombreArchivo(): String = "NoMeSubasLosPrecios-${Fechas.hoyParaArchivo()}.json"
}
