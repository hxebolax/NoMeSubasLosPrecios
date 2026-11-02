package com.xebolax.nomesubaslosprecios.ui

import android.os.Bundle
import android.widget.LinearLayout
import androidx.activity.enableEdgeToEdge
import androidx.appcompat.app.AppCompatActivity
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import androidx.core.view.isVisible
import androidx.core.view.updatePadding
import androidx.lifecycle.lifecycleScope
import androidx.recyclerview.widget.LinearLayoutManager
import com.google.android.material.dialog.MaterialAlertDialogBuilder
import com.google.android.material.textfield.TextInputEditText
import com.xebolax.nomesubaslosprecios.R
import com.xebolax.nomesubaslosprecios.accesibilidad.Accion
import com.xebolax.nomesubaslosprecios.accesibilidad.ZonaAcciones
import com.xebolax.nomesubaslosprecios.accesibilidad.campoTexto
import com.xebolax.nomesubaslosprecios.accesibilidad.configurarBarra
import com.xebolax.nomesubaslosprecios.accesibilidad.confirmar
import com.xebolax.nomesubaslosprecios.accesibilidad.dp
import com.xebolax.nomesubaslosprecios.accesibilidad.elegir
import com.xebolax.nomesubaslosprecios.accesibilidad.sinFocoPropio
import com.xebolax.nomesubaslosprecios.databinding.ActivityListaBinding
import com.xebolax.nomesubaslosprecios.datos.BaseDatos
import com.xebolax.nomesubaslosprecios.nucleo.Categoria
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/**
 * Gestionar categorías: añadir, renombrar, borrar (los productos pasan a «Sin
 * categoría», tras confirmar) y ordenar con «Subir» y «Bajar» (acciones de
 * TalkBack y menú de la fila, sin arrastrar).
 */
class CategoriasActivity : AppCompatActivity() {

	private lateinit var b: ActivityListaBinding
	private val adaptador = AdaptadorFilas()
	private val db by lazy { BaseDatos.obtener(this) }

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
		configurarBarra(b.barra, getString(R.string.gestionar_categorias))
		b.lista.layoutManager = LinearLayoutManager(this)
		b.lista.adapter = adaptador
		b.lista.sinFocoPropio()
		b.anadir.setText(R.string.anadir_categoria)
		b.anadir.isVisible = true
		b.anadir.setOnClickListener { editar(null) }
		cargar()
	}

	private fun estado(texto: String) {
		b.estado.text = texto
		b.estado.isVisible = true
	}

	private fun cargar() {
		lifecycleScope.launch {
			val (lista, cuenta) = withContext(Dispatchers.IO) { db.categorias() to db.productosPorCategoria() }
			adaptador.submitList(lista.mapIndexed { i, c -> fila(c, cuenta[c.id] ?: 0, i, lista.size) })
			b.vacio.setText(R.string.vacio_categorias)
			b.vacio.isVisible = lista.isEmpty()
		}
	}

	private fun fila(c: Categoria, productos: Int, posicion: Int, total: Int): Fila {
		val n = resources.getQuantityString(R.plurals.n_productos, productos, productos)
		val detalle = listOfNotNull(n, c.descripcion?.takeIf { it.isNotBlank() }).joinToString(", ")
		val acciones = mutableListOf<Accion>()
		acciones += getString(R.string.accion_renombrar) to { editar(c) }
		if (posicion > 0) acciones += getString(R.string.accion_subir) to { mover(c, -1) }
		if (posicion < total - 1) acciones += getString(R.string.accion_bajar) to { mover(c, 1) }
		acciones += getString(R.string.accion_borrar_x, c.nombre) to { borrar(c, productos) }
		return Fila(
			id = c.id, titulo = c.nombre, detalle = detalle,
			descripcion = "${c.nombre}, $detalle, " + getString(R.string.posicion_de, posicion + 1, total),
			etiquetaPulsar = getString(R.string.mas_opciones), zona = ZonaAcciones.CATEGORIA,
			alPulsar = { elegir(c.nombre, acciones) }, acciones = acciones,
		)
	}

	private fun mover(c: Categoria, paso: Int) {
		lifecycleScope.launch {
			withContext(Dispatchers.IO) { db.moverCategoria(c.id, paso) }
			estado(getString(if (paso < 0) R.string.categoria_subida else R.string.categoria_bajada, c.nombre))
			cargar()
		}
	}

	private fun borrar(c: Categoria, productos: Int) {
		val texto = if (productos > 0) resources.getQuantityString(R.plurals.confirmar_borrar_categoria, productos, c.nombre, productos)
		else getString(R.string.confirmar_borrar_categoria_vacia, c.nombre)
		confirmar(texto, getString(R.string.borrar)) {
			lifecycleScope.launch {
				withContext(Dispatchers.IO) { db.borrarCategoria(c.id) }
				estado(getString(R.string.categoria_borrada, c.nombre))
				cargar()
			}
		}
	}

	/** Nombre y descripción en un mismo diálogo (null: categoría nueva). */
	private fun editar(c: Categoria?) {
		val (contNombre, campoNombre) = campoTexto(getString(R.string.nombre_categoria), c?.nombre.orEmpty())
		val (contDescripcion, campoDescripcion) = campoTexto(getString(R.string.descripcion_opcional), c?.descripcion.orEmpty())
		val vista = LinearLayout(this).apply {
			orientation = LinearLayout.VERTICAL
			val m = dp(this@CategoriasActivity, 20)
			setPadding(m, m / 2, m, 0)
			addView(contNombre)
			addView(contDescripcion)
		}
		val dialogo = MaterialAlertDialogBuilder(this)
			.setTitle(if (c == null) R.string.anadir_categoria else R.string.renombrar_categoria)
			.setView(vista)
			.setPositiveButton(R.string.guardar, null)
			.setNegativeButton(R.string.cancelar, null)
			.create()
		dialogo.setOnShowListener {
			campoNombre.requestFocus()
			dialogo.getButton(android.app.AlertDialog.BUTTON_POSITIVE).setOnClickListener {
				val nombre = (campoNombre as TextInputEditText).text?.toString()?.trim().orEmpty()
				val descripcion = campoDescripcion.text?.toString()?.trim()
				lifecycleScope.launch {
					val error = when {
						nombre.isEmpty() -> getString(R.string.error_nombre_vacio)
						withContext(Dispatchers.IO) { db.existeCategoria(nombre, c?.id ?: 0) } -> getString(R.string.error_categoria_existe)
						else -> null
					}
					if (error != null) {
						contNombre.error = error
						return@launch
					}
					withContext(Dispatchers.IO) {
						if (c == null) db.crearCategoria(nombre, descripcion) else db.renombrarCategoria(c.id, nombre, descripcion)
					}
					dialogo.dismiss()
					estado(getString(if (c == null) R.string.categoria_creada else R.string.categoria_guardada, nombre))
					cargar()
				}
			}
		}
		dialogo.show()
	}
}
