package com.xebolax.nomesubaslosprecios.ui

import android.os.Bundle
import androidx.activity.OnBackPressedCallback
import androidx.activity.enableEdgeToEdge
import androidx.appcompat.app.AppCompatActivity
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import androidx.core.view.isVisible
import androidx.core.view.updatePadding
import androidx.recyclerview.widget.LinearLayoutManager
import com.xebolax.nomesubaslosprecios.R
import com.xebolax.nomesubaslosprecios.accesibilidad.Accion
import com.xebolax.nomesubaslosprecios.accesibilidad.AccionesTalkBack
import com.xebolax.nomesubaslosprecios.accesibilidad.ZonaAcciones
import com.xebolax.nomesubaslosprecios.accesibilidad.configurarBarra
import com.xebolax.nomesubaslosprecios.accesibilidad.confirmar
import com.xebolax.nomesubaslosprecios.accesibilidad.sinFocoPropio
import com.xebolax.nomesubaslosprecios.databinding.ActivityListaBinding

/**
 * Ajustes, Acciones de TalkBack: en cada zona (productos, avisos...) el
 * usuario elige qué acciones salen en las acciones rápidas de TalkBack y en
 * qué orden. Cada acción es una fila de una parada: el doble toque la activa o
 * la desactiva, y «Subir» y «Bajar» la ordenan sin arrastrar. La pulsación
 * larga de las listas sigue mostrando siempre todas.
 */
class AccionesAjustesActivity : AppCompatActivity() {

	private companion object {
		const val ESTADO_ZONA = "zona"
	}

	private lateinit var b: ActivityListaBinding
	private val adaptador = AdaptadorFilas()
	private var zona: ZonaAcciones? = null

	/** Atrás con una zona abierta vuelve a la lista de zonas. */
	private val atras = object : OnBackPressedCallback(false) {
		override fun handleOnBackPressed() {
			val z = zona ?: return
			zona = null
			pintar(foco = z.ordinal.toLong())
		}
	}

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
		configurarBarra(b.barra, getString(R.string.acciones_talkback))
		onBackPressedDispatcher.addCallback(this, atras)
		b.lista.layoutManager = LinearLayoutManager(this)
		b.lista.adapter = adaptador
		b.lista.sinFocoPropio()
		b.anadir.setText(R.string.restablecer)
		b.anadir.icon = null
		b.anadir.setOnClickListener {
			val z = zona ?: return@setOnClickListener
			confirmar(getString(R.string.confirmar_restablecer, getString(z.titulo)), getString(R.string.restablecer)) {
				AccionesTalkBack.restablecer(this, z)
				estado(getString(R.string.acciones_restablecidas))
				pintar()
			}
		}
		zona = estado?.getString(ESTADO_ZONA)?.let { n -> ZonaAcciones.entries.firstOrNull { it.name == n } }
		pintar()
	}

	override fun onSaveInstanceState(estado: Bundle) {
		super.onSaveInstanceState(estado)
		zona?.let { estado.putString(ESTADO_ZONA, it.name) }
	}

	private fun estado(texto: String) {
		b.estado.text = texto
		b.estado.isVisible = true
	}

	/** Las claves de la zona en el orden en que se muestran: las elegidas en su orden y después las demás. */
	private fun orden(z: ZonaAcciones): List<String> {
		val elegidas = AccionesTalkBack.elegidas(this, z)
		val todas = AccionesTalkBack.entradas(this, z).map { it.clave }
		return elegidas.filter { it in todas } + todas.filter { it !in elegidas }
	}

	private fun pintar(foco: Long? = null) {
		val z = zona
		atras.isEnabled = z != null
		b.anadir.isVisible = z != null
		val titulo = if (z == null) getString(R.string.acciones_talkback) else getString(R.string.acciones_de_zona, getString(z.titulo))
		title = titulo
		supportActionBar?.title = titulo
		ViewCompat.setAccessibilityPaneTitle(b.lista, titulo)
		val filas = if (z == null) {
			ZonaAcciones.entries.map { zn ->
				val nombre = getString(zn.titulo)
				val n = AccionesTalkBack.elegidas(this, zn).size
				val detalle = resources.getQuantityString(R.plurals.n_acciones_rapidas, n, n)
				Fila(zn.ordinal.toLong(), nombre, detalle, "$nombre, $detalle", getString(R.string.abrir), alPulsar = {
					zona = zn
					pintar()
				})
			}
		} else {
			val entradas = AccionesTalkBack.entradas(this, z).associateBy { it.clave }
			val elegidas = AccionesTalkBack.elegidas(this, z)
			val claves = orden(z)
			claves.mapIndexed { i, clave ->
				val e = entradas.getValue(clave)
				val nombre = AccionesTalkBack.nombre(this, e)
				val activa = clave in elegidas
				val estadoTexto = getString(if (activa) R.string.en_acciones_rapidas else R.string.fuera_de_acciones_rapidas)
				val acciones = mutableListOf<Accion>()
				acciones += getString(if (activa) R.string.quitar_de_rapidas else R.string.poner_en_rapidas) to { cambiar(z, clave, !activa) }
				// Solo se ordenan las que están en las acciones rápidas (van primero, en su orden)
				if (activa && i > 0) acciones += getString(R.string.accion_subir) to { mover(z, clave, -1) }
				if (activa && i < elegidas.size - 1) acciones += getString(R.string.accion_bajar) to { mover(z, clave, 1) }
				Fila(
					id = clave.hashCode().toLong(), titulo = nombre, detalle = estadoTexto,
					descripcion = "$nombre, $estadoTexto, " + getString(R.string.posicion_de, i + 1, claves.size),
					etiquetaPulsar = getString(if (activa) R.string.quitar_de_rapidas else R.string.poner_en_rapidas),
					destacada = activa, alPulsar = { cambiar(z, clave, !activa) }, acciones = acciones,
				)
			}
		}
		adaptador.submitList(filas) {
			if (foco != null) b.lista.post {
				val pos = filas.indexOfFirst { it.id == foco }
				if (pos >= 0) b.lista.findViewHolderForAdapterPosition(pos)?.itemView
					?.performAccessibilityAction(android.view.accessibility.AccessibilityNodeInfo.ACTION_ACCESSIBILITY_FOCUS, null)
			}
		}
		b.vacio.isVisible = false
	}

	private fun cambiar(z: ZonaAcciones, clave: String, activa: Boolean) {
		val elegidas = AccionesTalkBack.elegidas(this, z).toMutableList()
		if (activa) {
			// Se coloca en su sitio según el orden mostrado
			val ordenActual = orden(z)
			elegidas += clave
			AccionesTalkBack.guardar(this, z, ordenActual.filter { it in elegidas })
		} else {
			elegidas.remove(clave)
			AccionesTalkBack.guardar(this, z, elegidas)
		}
		pintar()
	}

	/** Sube o baja una acción; el foco sigue en la misma acción (su id es el de la clave). */
	private fun mover(z: ZonaAcciones, clave: String, paso: Int) {
		val lista = AccionesTalkBack.elegidas(this, z).toMutableList()
		val i = lista.indexOf(clave)
		val j = i + paso
		if (i < 0 || j !in lista.indices) return
		lista.removeAt(i)
		lista.add(j, clave)
		AccionesTalkBack.guardar(this, z, lista)
		estado(getString(if (paso < 0) R.string.accion_subida else R.string.accion_bajada, AccionesTalkBack.nombre(this, AccionesTalkBack.entradas(this, z).first { it.clave == clave })))
		pintar(foco = clave.hashCode().toLong())
	}
}
