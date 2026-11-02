package com.xebolax.nomesubaslosprecios.ui

import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.util.Log
import android.widget.LinearLayout
import android.widget.TextView
import androidx.activity.enableEdgeToEdge
import androidx.appcompat.app.AppCompatActivity
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import androidx.core.view.isVisible
import androidx.core.view.updatePadding
import androidx.lifecycle.lifecycleScope
import androidx.recyclerview.widget.LinearLayoutManager
import com.google.android.material.checkbox.MaterialCheckBox
import com.google.android.material.dialog.MaterialAlertDialogBuilder
import com.xebolax.nomesubaslosprecios.R
import com.xebolax.nomesubaslosprecios.accesibilidad.conEspera
import com.xebolax.nomesubaslosprecios.accesibilidad.configurarBarra
import com.xebolax.nomesubaslosprecios.accesibilidad.dp
import com.xebolax.nomesubaslosprecios.accesibilidad.mensaje
import com.xebolax.nomesubaslosprecios.accesibilidad.pedirTexto
import com.xebolax.nomesubaslosprecios.accesibilidad.sinFocoPropio
import com.xebolax.nomesubaslosprecios.databinding.ActivityListaBinding
import com.xebolax.nomesubaslosprecios.datos.BaseDatos
import com.xebolax.nomesubaslosprecios.motor.Comprobador
import com.xebolax.nomesubaslosprecios.motor.ErrorDescarga
import com.xebolax.nomesubaslosprecios.motor.Notificaciones
import com.xebolax.nomesubaslosprecios.nucleo.Candidato
import com.xebolax.nomesubaslosprecios.nucleo.Confianza
import com.xebolax.nomesubaslosprecios.nucleo.EscritorJson
import com.xebolax.nomesubaslosprecios.nucleo.ExtractorGenerico
import com.xebolax.nomesubaslosprecios.nucleo.OrigenPrecio
import com.xebolax.nomesubaslosprecios.nucleo.Producto
import com.xebolax.nomesubaslosprecios.nucleo.SelectorCss
import com.xebolax.nomesubaslosprecios.nucleo.Tienda
import com.xebolax.nomesubaslosprecios.nucleo.formatearImporte
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.jsoup.nodes.Document

/**
 * «Elegir el precio en la página» (ESPECIFICACION.md, «Elegir el precio» y
 * EXTRACTOR_GENERICO.md, 7): descarga la página y muestra los importes
 * candidatos, uno por fila con su contexto en palabras. Al elegir uno se
 * genera un selector CSS estable, se valida y se guarda en el producto (y,
 * si se pide, en la tienda) con su huella.
 */
class ElegirPrecioActivity : AppCompatActivity() {

	companion object {
		private const val ETIQUETA = "ElegirPrecio"
		private const val EXTRA_ID = "producto_id"
		private const val ID_NINGUNO = -1L
		private const val ID_ESCRIBIR = -2L

		fun abrir(c: Context, id: Long) {
			c.startActivity(Intent(c, ElegirPrecioActivity::class.java).putExtra(EXTRA_ID, id))
		}
	}

	private lateinit var b: ActivityListaBinding
	private val adaptador = AdaptadorFilas()
	private val db by lazy { BaseDatos.obtener(this) }
	private var producto: Producto? = null
	private var tienda: Tienda? = null
	private var documento: Document? = null

	override fun onCreate(estado: Bundle?) {
		enableEdgeToEdge()
		super.onCreate(estado)
		b = ActivityListaBinding.inflate(layoutInflater)
		setContentView(b.root)
		ViewCompat.setOnApplyWindowInsetsListener(b.root) { v, insets ->
			val barras = insets.getInsets(WindowInsetsCompat.Type.systemBars() or WindowInsetsCompat.Type.displayCutout() or WindowInsetsCompat.Type.ime())
			v.updatePadding(left = barras.left, top = barras.top, right = barras.right, bottom = barras.bottom)
			WindowInsetsCompat.CONSUMED
		}
		configurarBarra(b.barra, getString(R.string.elegir_precio))
		b.lista.layoutManager = LinearLayoutManager(this)
		b.lista.adapter = adaptador
		b.lista.sinFocoPropio()
		cargar(intent.getLongExtra(EXTRA_ID, 0L))
	}

	private fun estado(texto: String) {
		b.estado.text = texto
		b.estado.isVisible = true
	}

	private fun cargar(id: Long) {
		lifecycleScope.launch {
			try {
				val (p, t) = withContext(Dispatchers.IO) { db.producto(id).let { it to it?.tiendaId?.let { tid -> db.tienda(tid) } } }
				if (p == null) {
					finish()
					return@launch
				}
				producto = p
				tienda = t
				// Sin el selector propio del producto: se quieren todos los importes de la página
				val r = conEspera(getString(R.string.descargando_pagina)) {
					Comprobador.extraer(this@ElegirPrecioActivity, p.url, Comprobador.selectores(p, t).copy(precioProducto = null, huellaImporte = null), t?.nombre, t)
				}
				val doc = r.documento
				if (doc == null) {
					estado(getString(R.string.elegir_precio_api))
					return@launch
				}
				documento = doc
				val candidatos = withContext(Dispatchers.Default) { ExtractorGenerico.candidatosVisibles(doc).first }
				mostrar(ExtractorGenerico.opcionesParaElegir(candidatos, p.moneda), r.precio)
			} catch (e: CancellationException) {
				throw e
			} catch (e: ErrorDescarga) {
				Log.w(ETIQUETA, "No se pudo descargar la página", e)
				mensaje(getString(R.string.elegir_precio), e.message.orEmpty()) { finish() }
			} catch (e: Exception) {
				Log.e(ETIQUETA, "No se pudo preparar la lista de precios", e)
				mensaje(getString(R.string.elegir_precio), getString(R.string.error_inesperado)) { finish() }
			}
		}
	}

	private fun mostrar(opciones: List<Pair<String, Candidato>>, automatico: Double?) {
		val p = producto ?: return
		estado(
			if (opciones.isEmpty()) getString(R.string.elegir_precio_sin_candidatos)
			else if (automatico != null) getString(R.string.elegir_precio_con_automatico, formatearImporte(automatico, p.moneda))
			else getString(R.string.elegir_precio_explicacion),
		)
		val filas = opciones.mapIndexed { i, (texto, c) ->
			Fila(
				id = i.toLong(), titulo = texto, detalle = "", descripcion = texto, etiquetaPulsar = getString(R.string.usar_este_precio),
				alPulsar = { confirmar(texto, c) },
			)
		} + Fila(ID_NINGUNO, getString(R.string.ninguno_es_el_precio), "", getString(R.string.ninguno_es_el_precio), null, alPulsar = { finish() }) +
			Fila(ID_ESCRIBIR, getString(R.string.escribir_selector), "", getString(R.string.escribir_selector), null, alPulsar = { escribirSelector() })
		adaptador.submitList(filas)
	}

	private fun confirmar(texto: String, c: Candidato) {
		val m = dp(this, 20)
		val casilla = MaterialCheckBox(this).apply {
			setText(R.string.usar_para_la_tienda)
			minHeight = dp(this@ElegirPrecioActivity, 48)
		}
		val vista = LinearLayout(this).apply {
			orientation = LinearLayout.VERTICAL
			setPadding(m, m / 2, m, 0)
			addView(TextView(this@ElegirPrecioActivity).apply {
				this.text = texto
				setTextAppearance(com.google.android.material.R.style.TextAppearance_Material3_BodyLarge)
			})
			addView(casilla)
		}
		MaterialAlertDialogBuilder(this)
			.setTitle(R.string.usar_este_precio)
			.setView(vista)
			.setPositiveButton(R.string.usar_este_precio) { _, _ -> guardar(c, casilla.isChecked) }
			.setNegativeButton(R.string.cancelar, null)
			.show()
	}

	/** Genera el selector, lo valida y lo guarda con su huella. Si no vale, lo dice y la lista sigue abierta. */
	private fun guardar(c: Candidato, enTienda: Boolean) {
		val doc = documento ?: return
		val el = c.elemento ?: return
		val p = producto ?: return
		val (selector, atributo) = SelectorCss.generar(el, doc)
		// Válido: un único elemento con el mismo importe o, si no hay nada único, que el primero sea el elegido
		val valido = SelectorCss.validar(doc, selector, atributo, c.valor) ||
			(doc.select(selector).firstOrNull() === el && SelectorCss.importeDe(el, atributo) == c.valor)
		if (!valido) {
			estado(getString(R.string.selector_no_valido))
			return
		}
		// Huella común con Windows: importe, contexto en palabras y atributo («» si se lee el texto)
		val contexto = ExtractorGenerico.describir(c, p.moneda).substringAfter(" — ", "").substringBefore(" — «").ifEmpty { c.texto }
		val huella = EscritorJson.escribir(linkedMapOf("importe" to c.valor, "contexto" to contexto, "atributo" to (atributo ?: ""))).trim()
		lifecycleScope.launch {
			val r = withContext(Dispatchers.IO) {
				db.actualizarProducto(p.copy(selectorPrecio = selector, huellaSelector = huella, origenPrecio = OrigenPrecio.ELEGIDO.texto, confianza = Confianza.ALTA))
				if (enTienda) tienda?.let { db.actualizarTienda(it.copy(selectorPrecio = selector)) }
				Comprobador.comprobarUno(this@ElegirPrecioActivity, p.id)
			}
			r?.let { Notificaciones.avisar(applicationContext, it.avisos) }
			mensaje(getString(R.string.elegir_precio), getString(R.string.precio_guardado_posicion, formatearImporte(c.valor, p.moneda))) { finish() }
		}
	}

	private fun escribirSelector() {
		val p = producto ?: return
		pedirTexto(getString(R.string.escribir_selector), getString(R.string.campo_selector), p.selectorPrecio.orEmpty()) { css ->
			if (css.isBlank()) return@pedirTexto
			lifecycleScope.launch {
				val r = withContext(Dispatchers.IO) {
					db.actualizarProducto(p.copy(selectorPrecio = css, huellaSelector = null))
					Comprobador.comprobarUno(this@ElegirPrecioActivity, p.id)
				}
				val texto = when {
					r == null -> getString(R.string.error_inesperado)
					r.error != null -> getString(R.string.comprobado_con_error, r.error)
					else -> getString(R.string.comprobado_con_cambio, precioTexto(r.producto))
				}
				mensaje(getString(R.string.escribir_selector), texto) { finish() }
			}
		}
	}
}
