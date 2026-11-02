package com.xebolax.nomesubaslosprecios.ui

import android.content.ActivityNotFoundException
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.util.Log
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import com.xebolax.nomesubaslosprecios.R
import com.xebolax.nomesubaslosprecios.accesibilidad.Accion
import com.xebolax.nomesubaslosprecios.accesibilidad.avisar
import com.xebolax.nomesubaslosprecios.accesibilidad.conDeshacer
import com.xebolax.nomesubaslosprecios.accesibilidad.conEspera
import com.xebolax.nomesubaslosprecios.accesibilidad.copiar
import com.xebolax.nomesubaslosprecios.accesibilidad.elegirUno
import com.xebolax.nomesubaslosprecios.accesibilidad.mensaje
import com.xebolax.nomesubaslosprecios.accesibilidad.pedirTexto
import com.xebolax.nomesubaslosprecios.datos.BaseDatos
import com.xebolax.nomesubaslosprecios.datos.CopiaProducto
import com.xebolax.nomesubaslosprecios.motor.Comprobador
import com.xebolax.nomesubaslosprecios.motor.Notificaciones
import com.xebolax.nomesubaslosprecios.nucleo.Producto
import com.xebolax.nomesubaslosprecios.nucleo.ProductoConNombres
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/** Último producto borrado desde los detalles: la lista ofrece «Deshacer» al volver. */
object Papelera {
	@Volatile
	var ultima: CopiaProducto? = null
}

/**
 * Las acciones sobre un producto (ESPECIFICACION.md, «Acciones sobre un
 * producto»), las mismas en la lista y en los detalles, y según el estado:
 * «Quitar de favoritos» si ya lo está, «Reanudar» si está en pausa.
 */
class AccionesProducto(
	private val actividad: AppCompatActivity,
	/** Se llama tras cualquier cambio, para refrescar la pantalla. */
	private val alCambiar: () -> Unit,
	/** Dónde se muestra el resultado de «Comprobar ahora» (región viva de la pantalla). */
	private val alResultado: (String) -> Unit,
) {

	private companion object {
		const val ETIQUETA = "AccionesProducto"
	}

	private val db get() = BaseDatos.obtener(actividad)

	/** Todas las acciones, en el orden del menú. conDetalles: añade «Ver detalles» (en la lista). */
	fun acciones(pc: ProductoConNombres, conDetalles: Boolean, alEliminar: (CopiaProducto) -> Unit): List<Accion> {
		val p = pc.producto
		val nombre = p.nombre.ifBlank { p.url }
		val c = actividad
		val lista = mutableListOf<Accion>()
		if (conDetalles) lista += c.getString(R.string.ver_detalles) to { DetalleActivity.abrir(c, p.id) }
		lista += c.getString(R.string.abrir_en_la_tienda) to { abrirEnTienda(c, p.url) }
		lista += c.getString(R.string.comprobar_ahora) to { comprobarAhora(p.id) }
		lista += c.getString(R.string.editar) to { EditarProductoActivity.editar(c, p.id) }
		lista += c.getString(R.string.mover_a_categoria) to { moverACategoria(p) }
		lista += c.getString(if (p.favorito) R.string.quitar_de_favoritos else R.string.anadir_a_favoritos) to {
			cambiar(p.copy(favorito = !p.favorito), if (p.favorito) R.string.quitado_de_favoritos else R.string.anadido_a_favoritos)
		}
		lista += c.getString(if (p.activo) R.string.pausar else R.string.reanudar) to {
			cambiar(p.copy(activo = !p.activo), if (p.activo) R.string.pausado else R.string.reanudado)
		}
		lista += c.getString(R.string.compartir_enlace) to { compartir(p) }
		lista += c.getString(R.string.copiar_enlace) to { c.copiar(p.url, nombre) }
		lista += c.getString(R.string.eliminar_x, nombre) to { eliminar(p, alEliminar) }
		return lista
	}

	private fun cambiar(p: Producto, aviso: Int) {
		actividad.lifecycleScope.launch {
			withContext(Dispatchers.IO) { db.actualizarProducto(p) }
			actividad.avisar(actividad.getString(aviso), mostrar = false)
			alCambiar()
		}
	}

	private fun compartir(p: Producto) {
		val texto = Intent(Intent.ACTION_SEND).setType("text/plain")
			.putExtra(Intent.EXTRA_SUBJECT, p.nombre)
			.putExtra(Intent.EXTRA_TEXT, p.url)
		actividad.startActivity(Intent.createChooser(texto, actividad.getString(R.string.compartir_enlace)))
	}

	fun comprobarAhora(id: Long) {
		actividad.lifecycleScope.launch {
			try {
				val r = actividad.conEspera(actividad.getString(R.string.comprobando_precio)) { Comprobador.comprobarUno(actividad, id) } ?: return@launch
				Notificaciones.avisar(actividad.applicationContext, r.avisos)
				val p = r.producto
				val texto = when {
					r.error != null -> actividad.getString(R.string.comprobado_con_error, r.error)
					r.avisos.isNotEmpty() -> r.avisos.joinToString(" ") { it.mensaje }
					r.cambio -> actividad.getString(R.string.comprobado_con_cambio, actividad.precioTexto(p))
					else -> actividad.getString(R.string.comprobado_sin_cambios, actividad.precioTexto(p))
				}
				alCambiar()
				alResultado(texto)
			} catch (e: CancellationException) {
				throw e
			} catch (e: Exception) {
				Log.e(ETIQUETA, "No se pudo comprobar el producto $id", e)
				actividad.mensaje(actividad.getString(R.string.comprobar_ahora), actividad.getString(R.string.error_inesperado))
			}
		}
	}

	/** Elegir categoría: «Sin categoría», las que hay y «Nueva categoría…». */
	fun moverACategoria(p: Producto) {
		actividad.lifecycleScope.launch {
			val categorias = withContext(Dispatchers.IO) { db.categorias() }
			val nombres = listOf(actividad.getString(R.string.sin_categoria)) + categorias.map { it.nombre } + actividad.getString(R.string.nueva_categoria)
			val actual = if (p.categoriaId == null) 0 else categorias.indexOfFirst { it.id == p.categoriaId } + 1
			actividad.elegirUno(actividad.getString(R.string.mover_a_categoria), nombres, actual) { i ->
				when (i) {
					0 -> mover(p, null)
					nombres.lastIndex -> actividad.pedirTexto(actividad.getString(R.string.nueva_categoria), actividad.getString(R.string.nombre_categoria)) { nombre ->
						if (nombre.isNotBlank()) actividad.lifecycleScope.launch {
							val id = withContext(Dispatchers.IO) { db.crearCategoria(nombre) }
							mover(p, id)
						}
					}
					else -> mover(p, categorias[i - 1].id)
				}
			}
		}
	}

	private fun mover(p: Producto, categoria: Long?) {
		actividad.lifecycleScope.launch {
			val nombre = withContext(Dispatchers.IO) {
				db.actualizarProducto((db.producto(p.id) ?: p).copy(categoriaId = categoria))
				categoria?.let { db.categoria(it)?.nombre }
			}
			actividad.avisar(actividad.getString(R.string.movido_a, nombre ?: actividad.getString(R.string.sin_categoria)), mostrar = false)
			alCambiar()
		}
	}

	private fun eliminar(p: Producto, alEliminar: (CopiaProducto) -> Unit) {
		actividad.lifecycleScope.launch {
			val copia = withContext(Dispatchers.IO) { db.eliminarProducto(p.id) } ?: return@launch
			alEliminar(copia)
		}
	}

	/** «Producto eliminado» con Deshacer (en la lista). */
	fun ofrecerDeshacer(copia: CopiaProducto) {
		actividad.conDeshacer(actividad.getString(R.string.eliminado_x, copia.producto.nombre.ifBlank { copia.producto.url })) {
			actividad.lifecycleScope.launch {
				withContext(Dispatchers.IO) { db.restaurar(copia) }
				alCambiar()
			}
		}
		alCambiar()
	}
}

/** Abre la página del producto en el navegador. */
fun abrirEnTienda(c: Context, url: String) {
	try {
		c.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url)))
	} catch (e: ActivityNotFoundException) {
		Log.e("AccionesProducto", "No hay navegador para abrir $url", e)
		c.mensaje(c.getString(R.string.abrir_en_la_tienda), c.getString(R.string.sin_navegador))
	}
}
