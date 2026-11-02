package com.xebolax.nomesubaslosprecios.ui

import android.os.Bundle
import android.util.Log
import androidx.activity.enableEdgeToEdge
import androidx.appcompat.app.AppCompatActivity
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import androidx.core.view.isVisible
import androidx.core.view.updatePadding
import androidx.lifecycle.lifecycleScope
import com.google.android.material.textfield.TextInputEditText
import com.xebolax.nomesubaslosprecios.R
import com.xebolax.nomesubaslosprecios.accesibilidad.avisar
import com.xebolax.nomesubaslosprecios.accesibilidad.conEspera
import com.xebolax.nomesubaslosprecios.accesibilidad.configurarBarra
import com.xebolax.nomesubaslosprecios.accesibilidad.confirmar
import com.xebolax.nomesubaslosprecios.accesibilidad.elegir
import com.xebolax.nomesubaslosprecios.accesibilidad.elegirUno
import com.xebolax.nomesubaslosprecios.accesibilidad.mensaje
import com.xebolax.nomesubaslosprecios.databinding.ActivityEditarTiendaBinding
import com.xebolax.nomesubaslosprecios.datos.BaseDatos
import com.xebolax.nomesubaslosprecios.motor.Comprobador
import com.xebolax.nomesubaslosprecios.motor.ErrorDescarga
import com.xebolax.nomesubaslosprecios.nucleo.ModoDescarga
import com.xebolax.nomesubaslosprecios.nucleo.Producto
import com.xebolax.nomesubaslosprecios.nucleo.SelectoresUsuario
import com.xebolax.nomesubaslosprecios.nucleo.Tienda
import com.xebolax.nomesubaslosprecios.nucleo.formatearImporte
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/**
 * Editar una tienda: renombrarla, sus selectores CSS propios y sus notas.
 * «Probar los selectores» descarga un producto de la tienda con lo escrito en
 * los campos (sin guardar) y dice lo que saca y de dónde.
 */
class EditarTiendaActivity : AppCompatActivity() {

	companion object {
		const val EXTRA_ID = "tienda_id"
		private const val ETIQUETA = "EditarTienda"
		private const val ESTADO_MODO = "modo"
	}

	private lateinit var b: ActivityEditarTiendaBinding
	private val db by lazy { BaseDatos.obtener(this) }
	private var tienda: Tienda? = null
	private var productos: List<Producto> = emptyList()
	private var modo = ModoDescarga.AUTO

	private fun nombreModo(m: String) = getString(
		when (m) {
			ModoDescarga.DIRECTO -> R.string.modo_directo
			ModoDescarga.NAVEGADOR -> R.string.modo_navegador
			else -> R.string.modo_auto
		},
	)

	private fun mostrarModo() {
		b.modo.text = getString(R.string.modo_descarga_x, nombreModo(modo))
	}

	override fun onCreate(estado: Bundle?) {
		enableEdgeToEdge()
		super.onCreate(estado)
		b = ActivityEditarTiendaBinding.inflate(layoutInflater)
		setContentView(b.root)
		ViewCompat.setOnApplyWindowInsetsListener(b.root) { v, insets ->
			val barras = insets.getInsets(WindowInsetsCompat.Type.systemBars() or WindowInsetsCompat.Type.displayCutout() or WindowInsetsCompat.Type.ime())
			v.updatePadding(left = barras.left, top = barras.top, right = barras.right, bottom = barras.bottom)
			WindowInsetsCompat.CONSUMED
		}
		configurarBarra(b.barra, getString(R.string.editar_tienda))
		val id = intent.getLongExtra(EXTRA_ID, 0L)
		b.guardar.setOnClickListener { guardar() }
		b.probar.setOnClickListener { probar() }
		b.borrar.setOnClickListener { borrar() }
		b.modo.setOnClickListener {
			elegirUno(getString(R.string.modo_descarga), ModoDescarga.TODOS.map { nombreModo(it) }, ModoDescarga.TODOS.indexOf(modo)) { i ->
				modo = ModoDescarga.TODOS[i]
				mostrarModo()
			}
		}
		b.abrirEnApp.setOnClickListener {
			val t = tienda ?: return@setOnClickListener
			NavegadorActivity.abrir(this, productos.firstOrNull()?.url ?: "https://www.${t.dominio}/")
		}
		if (estado != null) modo = estado.getString(ESTADO_MODO) ?: ModoDescarga.AUTO
		lifecycleScope.launch {
			val (t, lista) = withContext(Dispatchers.IO) {
				db.tienda(id) to db.productos().map { it.producto }.filter { it.tiendaId == id }
			}
			if (t == null) {
				finish()
				return@launch
			}
			tienda = t
			productos = lista
			val titulo = getString(R.string.editar_tienda_x, t.nombre)
			title = titulo
			supportActionBar?.title = titulo
			b.dominio.text = getString(R.string.dominio_y_productos, t.dominio, resources.getQuantityString(R.plurals.n_productos, lista.size, lista.size))
			Comprobador.reglas(this@EditarTiendaActivity).para(t.dominio)?.notas?.takeIf { it.isNotBlank() }?.let {
				b.notasReglas.text = getString(R.string.notas_de_la_tienda, it)
				b.notasReglas.isVisible = true
			}
			if (estado == null) {
				modo = t.modoDescarga
				b.nombre.setText(t.nombre)
				b.selectorPrecio.setText(t.selectorPrecio.orEmpty())
				b.selectorTitulo.setText(t.selectorTitulo.orEmpty())
				b.selectorDisponible.setText(t.selectorDisponible.orEmpty())
				b.notas.setText(t.notas.orEmpty())
			}
			mostrarModo()
			b.borrar.isVisible = lista.isEmpty()
			b.probar.isEnabled = lista.isNotEmpty()
		}
	}

	override fun onSaveInstanceState(estado: Bundle) {
		super.onSaveInstanceState(estado)
		estado.putString(ESTADO_MODO, modo)
	}

	private fun texto(campo: TextInputEditText) = campo.text?.toString()?.trim().orEmpty()

	private fun guardar() {
		val t = tienda ?: return
		val nombre = texto(b.nombre)
		if (nombre.isEmpty()) {
			b.campoNombre.error = getString(R.string.error_nombre_vacio)
			b.nombre.requestFocus()
			return
		}
		b.campoNombre.error = null
		lifecycleScope.launch {
			withContext(Dispatchers.IO) {
				db.actualizarTienda(
					t.copy(
						nombre = nombre,
						selectorPrecio = texto(b.selectorPrecio).ifEmpty { null },
						selectorTitulo = texto(b.selectorTitulo).ifEmpty { null },
						selectorDisponible = texto(b.selectorDisponible).ifEmpty { null },
						notas = texto(b.notas).ifEmpty { null },
						modoDescarga = modo,
					),
				)
			}
			avisar(getString(R.string.cambios_guardados))
			finish()
		}
	}

	private fun probar() {
		if (productos.isEmpty()) return
		if (productos.size == 1) return probarCon(productos[0])
		elegir(getString(R.string.elegir_producto_prueba), productos.map { p -> p.nombre.ifBlank { p.url } to { probarCon(p) } })
	}

	/** Prueba los selectores escritos en los campos (sin guardarlos) con un producto de la tienda. */
	private fun probarCon(p: Producto) {
		val selectores = SelectoresUsuario(
			precioProducto = p.selectorPrecio,
			precioTienda = texto(b.selectorPrecio),
			tituloTienda = texto(b.selectorTitulo),
			disponibleTienda = texto(b.selectorDisponible),
		)
		lifecycleScope.launch {
			val texto = try {
				val r = conEspera(getString(R.string.probando_selectores)) {
					Comprobador.extraer(this@EditarTiendaActivity, p.url, selectores, texto(b.nombre).ifEmpty { null }, tienda?.copy(modoDescarga = modo))
				}
				buildString {
					append(getString(R.string.prueba_precio, r.precio?.let { formatearImporte(it, r.moneda) } ?: getString(R.string.sin_precio_leido)))
					r.origenTexto?.let { append(" ").append(getString(R.string.prueba_origen, it)) }
					append("\n").append(getString(R.string.prueba_nombre, r.nombre ?: getString(R.string.no_encontrado)))
					append("\n").append(
						getString(
							R.string.prueba_disponible,
							when (r.disponible) {
								true -> getString(R.string.disponible)
								false -> getString(R.string.estado_agotado)
								null -> getString(R.string.no_se_sabe)
							},
						),
					)
					r.error?.let { append("\n\n").append(it) }
				}
			} catch (e: CancellationException) {
				throw e
			} catch (e: ErrorDescarga) {
				Log.w(ETIQUETA, "No se pudo descargar ${p.url}", e)
				e.message.orEmpty()
			} catch (e: Exception) {
				Log.e(ETIQUETA, "Error al probar los selectores con ${p.url}", e)
				getString(R.string.error_inesperado)
			}
			// El resultado en esta misma pantalla, en un mensaje que se puede recorrer
			mensaje(getString(R.string.resultado_prueba), texto)
		}
	}

	private fun borrar() {
		val t = tienda ?: return
		confirmar(getString(R.string.confirmar_borrar_tienda, t.nombre), getString(R.string.borrar)) {
			lifecycleScope.launch {
				val borrada = withContext(Dispatchers.IO) { db.borrarTienda(t.id) }
				if (borrada) {
					avisar(getString(R.string.tienda_borrada, t.nombre))
					finish()
				} else {
					b.estado.text = getString(R.string.tienda_con_productos)
					b.estado.isVisible = true
				}
			}
		}
	}
}
