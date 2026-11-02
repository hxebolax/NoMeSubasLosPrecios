package com.xebolax.nomesubaslosprecios.ui

import android.content.Intent
import android.os.Bundle
import androidx.activity.enableEdgeToEdge
import androidx.appcompat.app.AppCompatActivity
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import androidx.core.view.isVisible
import androidx.core.view.updatePadding
import androidx.lifecycle.lifecycleScope
import androidx.recyclerview.widget.LinearLayoutManager
import com.xebolax.nomesubaslosprecios.R
import com.xebolax.nomesubaslosprecios.accesibilidad.Accion
import com.xebolax.nomesubaslosprecios.accesibilidad.ZonaAcciones
import com.xebolax.nomesubaslosprecios.accesibilidad.configurarBarra
import com.xebolax.nomesubaslosprecios.accesibilidad.confirmar
import com.xebolax.nomesubaslosprecios.accesibilidad.sinFocoPropio
import com.xebolax.nomesubaslosprecios.databinding.ActivityListaBinding
import com.xebolax.nomesubaslosprecios.datos.BaseDatos
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/**
 * Gestionar tiendas: ver, abrir para renombrar, editar selectores y notas y
 * probar; borrar solo si no tiene productos (si tiene, no se ofrece).
 */
class TiendasActivity : AppCompatActivity() {

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
		configurarBarra(b.barra, getString(R.string.gestionar_tiendas))
		b.lista.layoutManager = LinearLayoutManager(this)
		b.lista.adapter = adaptador
		b.lista.sinFocoPropio()
	}

	override fun onResume() {
		super.onResume()
		cargar()
	}

	private fun cargar() {
		lifecycleScope.launch {
			val (tiendas, cuenta) = withContext(Dispatchers.IO) { db.tiendas() to db.productosPorTienda() }
			adaptador.submitList(tiendas.map { t ->
				val n = cuenta[t.id] ?: 0
				val propios = !t.selectorPrecio.isNullOrBlank() || !t.selectorTitulo.isNullOrBlank() || !t.selectorDisponible.isNullOrBlank()
				val detalle = listOfNotNull(
					t.dominio,
					resources.getQuantityString(R.plurals.n_productos, n, n),
					if (propios) getString(R.string.con_selectores_propios) else null,
				).joinToString(", ")
				val acciones = mutableListOf<Accion>()
				acciones += getString(R.string.editar) to { abrir(t.id) }
				if (n == 0) acciones += getString(R.string.accion_borrar_x, t.nombre) to {
					confirmar(getString(R.string.confirmar_borrar_tienda, t.nombre), getString(R.string.borrar)) {
						lifecycleScope.launch {
							withContext(Dispatchers.IO) { db.borrarTienda(t.id) }
							b.estado.text = getString(R.string.tienda_borrada, t.nombre)
							b.estado.isVisible = true
							cargar()
						}
					}
				}
				Fila(
					id = t.id, titulo = t.nombre, detalle = detalle, descripcion = "${t.nombre}, $detalle",
					etiquetaPulsar = getString(R.string.editar), zona = ZonaAcciones.TIENDA, alPulsar = { abrir(t.id) }, acciones = acciones,
				)
			})
			b.vacio.setText(R.string.vacio_tiendas)
			b.vacio.isVisible = tiendas.isEmpty()
		}
	}

	private fun abrir(id: Long) {
		startActivity(Intent(this, EditarTiendaActivity::class.java).putExtra(EditarTiendaActivity.EXTRA_ID, id))
	}
}
