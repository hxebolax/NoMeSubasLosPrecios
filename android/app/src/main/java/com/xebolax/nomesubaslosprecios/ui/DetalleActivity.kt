package com.xebolax.nomesubaslosprecios.ui

import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.widget.LinearLayout
import android.widget.TextView
import androidx.activity.enableEdgeToEdge
import androidx.appcompat.app.AppCompatActivity
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import androidx.core.view.isVisible
import androidx.core.view.updatePadding
import androidx.lifecycle.lifecycleScope
import com.google.android.material.button.MaterialButton
import com.xebolax.nomesubaslosprecios.R
import com.xebolax.nomesubaslosprecios.accesibilidad.configurarBarra
import com.xebolax.nomesubaslosprecios.accesibilidad.dp
import com.xebolax.nomesubaslosprecios.databinding.ActivityDetalleBinding
import com.xebolax.nomesubaslosprecios.datos.BaseDatos
import com.xebolax.nomesubaslosprecios.nucleo.Fechas
import com.xebolax.nomesubaslosprecios.nucleo.ProductoConNombres
import com.xebolax.nomesubaslosprecios.nucleo.PuntoHistorial
import com.xebolax.nomesubaslosprecios.nucleo.cambioPorcentaje
import com.xebolax.nomesubaslosprecios.nucleo.formatearImporte
import com.xebolax.nomesubaslosprecios.nucleo.formatearPorcentaje
import com.xebolax.nomesubaslosprecios.nucleo.redondear
import android.util.Log
import com.xebolax.nomesubaslosprecios.accesibilidad.conEspera
import com.xebolax.nomesubaslosprecios.accesibilidad.elegirUno
import com.xebolax.nomesubaslosprecios.accesibilidad.mensaje
import com.xebolax.nomesubaslosprecios.motor.Comprobador
import com.xebolax.nomesubaslosprecios.motor.ErrorDescarga
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import kotlin.math.abs

/**
 * Detalles de un producto (ESPECIFICACION.md, «Detalles del producto»): el
 * resumen hablado arriba, las acciones según el estado, los datos, la gráfica
 * (decorativa) y el historial como lista que se lee fila a fila.
 */
class DetalleActivity : AppCompatActivity() {

	companion object {
		const val EXTRA_ID = "producto_id"

		fun abrir(c: Context, id: Long) {
			c.startActivity(Intent(c, DetalleActivity::class.java).putExtra(EXTRA_ID, id))
		}
	}

	private lateinit var b: ActivityDetalleBinding
	private lateinit var acciones: AccionesProducto
	private var id = 0L

	override fun onCreate(estado: Bundle?) {
		enableEdgeToEdge()
		super.onCreate(estado)
		b = ActivityDetalleBinding.inflate(layoutInflater)
		setContentView(b.root)
		ViewCompat.setOnApplyWindowInsetsListener(b.root) { v, insets ->
			val barras = insets.getInsets(WindowInsetsCompat.Type.systemBars() or WindowInsetsCompat.Type.displayCutout() or WindowInsetsCompat.Type.ime())
			v.updatePadding(left = barras.left, top = barras.top, right = barras.right, bottom = barras.bottom)
			WindowInsetsCompat.CONSUMED
		}
		configurarBarra(b.barra, getString(R.string.detalles))
		id = intent.getLongExtra(EXTRA_ID, 0L)
		acciones = AccionesProducto(this, alCambiar = { cargar() }, alResultado = { texto ->
			b.estado.text = texto
			b.estado.isVisible = true
		})
	}

	override fun onResume() {
		super.onResume()
		cargar()
	}

	private fun cargar() {
		lifecycleScope.launch {
			val (pc, historial) = withContext(Dispatchers.IO) {
				val db = BaseDatos.obtener(this@DetalleActivity)
				db.productoConNombres(id) to db.historial(id)
			}
			if (pc == null) {
				// Se borró (o no existe): no hay nada que enseñar
				finish()
				return@launch
			}
			pintar(pc, historial)
		}
	}

	/** «Elegir variante»: las variantes de la página con su precio; la elegida se guarda y se usa en las comprobaciones. */
	private fun elegirVariante(pc: ProductoConNombres) {
		val p = pc.producto
		lifecycleScope.launch {
			try {
				val db = BaseDatos.obtener(this@DetalleActivity)
				val tienda = withContext(Dispatchers.IO) { p.tiendaId?.let { db.tienda(it) } }
				val r = conEspera(getString(R.string.buscando_variantes)) {
					Comprobador.extraer(this@DetalleActivity, p.url, Comprobador.selectores(p, tienda).copy(variante = null), tienda?.nombre, tienda)
				}
				if (r.variantes.isEmpty()) {
					mensaje(getString(R.string.elegir_variante), getString(R.string.sin_variantes))
					return@launch
				}
				val nombres = r.variantes.map { v ->
					listOfNotNull(v.nombre, v.precio?.let { formatearImporte(it, p.moneda) }, if (v.disponible == false) getString(R.string.estado_agotado) else null)
						.joinToString(", ")
				}
				val actual = r.variantes.indexOfFirst { it.clave == p.variante || it.nombre == p.variante }
				elegirUno(getString(R.string.elegir_variante), nombres, actual) { i ->
					val v = r.variantes[i]
					lifecycleScope.launch {
						withContext(Dispatchers.IO) {
							db.actualizarProducto((db.producto(p.id) ?: p).copy(variante = v.clave, desde = false))
							Comprobador.comprobarUno(this@DetalleActivity, p.id)
						}
						b.estado.text = getString(R.string.variante_elegida, v.nombre)
						b.estado.isVisible = true
						cargar()
					}
				}
			} catch (e: CancellationException) {
				throw e
			} catch (e: ErrorDescarga) {
				Log.w("Detalle", "No se pudo descargar ${p.url}", e)
				mensaje(getString(R.string.elegir_variante), e.message.orEmpty())
			} catch (e: Exception) {
				Log.e("Detalle", "No se pudieron leer las variantes", e)
				mensaje(getString(R.string.elegir_variante), getString(R.string.error_inesperado))
			}
		}
	}

	private fun linea(contenedor: LinearLayout, texto: String) {
		contenedor.addView(TextView(this).apply {
			this.text = texto
			setTextAppearance(com.google.android.material.R.style.TextAppearance_Material3_BodyLarge)
			setPadding(0, dp(this@DetalleActivity, 4), 0, dp(this@DetalleActivity, 4))
			// Seleccionable para poder copiar la dirección o el error
			setTextIsSelectable(true)
		})
	}

	private fun pintar(pc: ProductoConNombres, historial: List<PuntoHistorial>) {
		val p = pc.producto
		val nombre = p.nombre.ifBlank { p.url }
		val titulo = getString(R.string.detalles_de, nombre)
		title = titulo
		supportActionBar?.title = nombre
		b.resumen.text = resumenHablado(p)

		// Acciones (botones con el texto de lo que hacen ahora)
		b.botones.removeAllViews()
		for ((texto, accion) in acciones.acciones(pc, conDetalles = false) { copia ->
			Papelera.ultima = copia
			finish()
		}) {
			val boton = layoutInflater.inflate(R.layout.item_boton, b.botones, false) as MaterialButton
			boton.text = texto
			boton.setOnClickListener { accion() }
			b.botones.addView(boton)
		}
		val extra = mutableListOf<Pair<String, () -> Unit>>()
		if (p.desde || !p.variante.isNullOrBlank()) extra += getString(R.string.elegir_variante) to { elegirVariante(pc) }
		extra += getString(R.string.elegir_precio) to { ElegirPrecioActivity.abrir(this, p.id) }
		extra += getString(R.string.abrir_tienda_en_la_app) to { NavegadorActivity.abrir(this, p.url) }
		for ((texto, accion) in extra) {
			val boton = layoutInflater.inflate(R.layout.item_boton, b.botones, false) as MaterialButton
			boton.text = texto
			boton.setOnClickListener { accion() }
			b.botones.addView(boton)
		}

		// Datos
		val m = p.moneda
		b.datos.removeAllViews()
		val datos = mutableListOf<String>()
		datos += getString(R.string.dato_estado, estadosFila(p).ifEmpty { listOf(getString(R.string.estado_disponible)) }.joinToString(", "))
		datos += getString(R.string.dato_precio_actual, precioTexto(p))
		datos += getString(R.string.dato_disponible, getString(if (p.disponible) R.string.si else R.string.no))
		datos += getString(R.string.dato_tienda, pc.tienda)
		datos += getString(R.string.dato_categoria, pc.categoria ?: getString(R.string.sin_categoria))
		p.grupo?.takeIf { it.isNotBlank() }?.let { datos += getString(R.string.dato_grupo, it) }
		datos += getString(R.string.dato_objetivo, p.precioObjetivo?.let { formatearImporte(it, m) } ?: getString(R.string.ninguno))
		datos += getString(R.string.dato_alerta, if (p.alertaPorcentaje > 0) formatearPorcentaje(p.alertaPorcentaje) + " %" else getString(R.string.cualquier_bajada))
		p.precioInicial?.let { datos += getString(R.string.dato_inicial, formatearImporte(it, m)) }
		p.precioMinimo?.let { datos += getString(R.string.dato_minimo, formatearImporte(it, m), Fechas.diaHablado(p.fechaMinimo)) }
		p.precioMaximo?.let { datos += getString(R.string.dato_maximo, formatearImporte(it, m), Fechas.diaHablado(p.fechaMaximo)) }
		val conPrecio = historial.mapNotNull { it.precio }
		if (conPrecio.isNotEmpty()) datos += getString(R.string.dato_media, formatearImporte(redondear(conPrecio.average()), m))
		val actual = p.precioActual
		val minimo = p.precioMinimo
		if (actual != null && minimo != null) {
			datos += if (actual <= minimo) getString(R.string.dato_en_minimo)
			else getString(R.string.dato_sobre_minimo, formatearImporte(actual - minimo, m), formatearPorcentaje(cambioPorcentaje(minimo, actual)))
		}
		datos += getString(R.string.dato_ultima, p.ultimaComprobacion?.let { Fechas.fechaHora(it) } ?: getString(R.string.nunca))
		datos += getString(R.string.dato_resultado, textoComprobacion(p))
		if (!p.ultimoError.isNullOrBlank()) datos += getString(R.string.dato_error, p.ultimoError)
		p.origenPrecio?.let { datos += getString(R.string.dato_origen, it) }
		p.confianza?.let { datos += getString(R.string.dato_confianza, it) }
		if (!p.variante.isNullOrBlank()) datos += getString(R.string.dato_variante, p.variante)
		p.fechaAlta?.let { datos += getString(R.string.dato_alta, Fechas.diaHablado(it)) }
		if (!p.notas.isNullOrBlank()) datos += getString(R.string.dato_notas, p.notas)
		datos += getString(R.string.dato_direccion, p.url)
		datos.forEach { linea(b.datos, it) }

		// Gráfica (decorativa) e historial (lo que se lee)
		b.grafica.mostrar(historial, m)
		b.grafica.isVisible = historial.count { it.precio != null } >= 1
		b.historial.removeAllViews()
		if (historial.isEmpty()) linea(b.historial, getString(R.string.historial_vacio))
		historial.asReversed().forEachIndexed { i, h ->
			val anterior = historial.asReversed().getOrNull(i + 1)
			val partes = mutableListOf(Fechas.fechaHora(h.fecha), h.precio?.let { formatearImporte(it, m) } ?: getString(R.string.sin_precio_leido))
			if (!h.disponible) partes += getString(R.string.estado_agotado)
			val antes = anterior?.precio
			if (h.precio != null && antes != null && antes != h.precio) {
				val dif = formatearImporte(abs(h.precio - antes), m)
				val pct = formatearPorcentaje(cambioPorcentaje(antes, h.precio))
				partes += if (h.precio < antes) getString(R.string.cambio_bajo, dif, pct) else getString(R.string.cambio_subio, dif, pct)
			} else if (anterior == null) partes += getString(R.string.primera_lectura)
			else if (anterior.disponible != h.disponible) partes += getString(if (h.disponible) R.string.volvio_disponible else R.string.se_agoto)
			linea(b.historial, partes.joinToString(", "))
		}
	}
}
