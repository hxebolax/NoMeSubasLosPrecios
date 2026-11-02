package com.xebolax.nomesubaslosprecios.ui

import android.Manifest
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.util.Log
import android.view.accessibility.AccessibilityNodeInfo
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import androidx.core.view.isVisible
import androidx.core.view.updatePadding
import androidx.lifecycle.lifecycleScope
import com.google.android.material.dialog.MaterialAlertDialogBuilder
import com.xebolax.nomesubaslosprecios.R
import com.xebolax.nomesubaslosprecios.accesibilidad.avisar
import com.xebolax.nomesubaslosprecios.accesibilidad.conEspera
import com.xebolax.nomesubaslosprecios.accesibilidad.configurarBarra
import com.xebolax.nomesubaslosprecios.accesibilidad.elegirUno
import com.xebolax.nomesubaslosprecios.accesibilidad.pedirTexto
import com.xebolax.nomesubaslosprecios.databinding.ActivityEditarProductoBinding
import com.xebolax.nomesubaslosprecios.datos.BaseDatos
import com.xebolax.nomesubaslosprecios.datos.Preferencias
import com.xebolax.nomesubaslosprecios.motor.Comprobador
import com.xebolax.nomesubaslosprecios.motor.ErrorDescarga
import com.xebolax.nomesubaslosprecios.motor.Notificaciones
import com.xebolax.nomesubaslosprecios.nucleo.Categoria
import com.xebolax.nomesubaslosprecios.nucleo.Fechas
import com.xebolax.nomesubaslosprecios.nucleo.Lectura
import com.xebolax.nomesubaslosprecios.nucleo.MensajesError
import com.xebolax.nomesubaslosprecios.nucleo.LogicaAvisos
import com.xebolax.nomesubaslosprecios.nucleo.Producto
import com.xebolax.nomesubaslosprecios.nucleo.ResultadoExtraccion
import com.xebolax.nomesubaslosprecios.nucleo.analizarImporte
import com.xebolax.nomesubaslosprecios.nucleo.dominioDe
import com.xebolax.nomesubaslosprecios.nucleo.formatearImporte
import com.xebolax.nomesubaslosprecios.nucleo.formatearPorcentaje
import com.xebolax.nomesubaslosprecios.nucleo.limpiarUrl
import com.xebolax.nomesubaslosprecios.nucleo.pareceUrl
import com.xebolax.nomesubaslosprecios.nucleo.primeraUrl
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/**
 * Añadir o editar un producto. Al añadir se comprueba en el momento (con
 * espera cancelable) y se confirma lo encontrado antes de guardar. También
 * recibe direcciones compartidas desde el navegador (ACTION_SEND text/plain).
 */
class EditarProductoActivity : AppCompatActivity() {

	companion object {
		private const val ETIQUETA = "EditarProducto"
		const val EXTRA_ID = "producto_id"
		const val EXTRA_URL = "url"
		private const val ESTADO_CATEGORIA = "categoria"

		fun anadir(c: Context, url: String? = null) {
			c.startActivity(Intent(c, EditarProductoActivity::class.java).apply { if (url != null) putExtra(EXTRA_URL, url) })
		}

		fun editar(c: Context, id: Long) {
			c.startActivity(Intent(c, EditarProductoActivity::class.java).putExtra(EXTRA_ID, id))
		}
	}

	private lateinit var b: ActivityEditarProductoBinding
	private val db by lazy { BaseDatos.obtener(this) }
	/** El producto que se edita (null al añadir). */
	private var original: Producto? = null
	private var categoriaId: Long? = null
	private var categorias: List<Categoria> = emptyList()

	private val permisoNotificaciones = registerForActivityResult(ActivityResultContracts.RequestPermission()) { concedido ->
		if (!concedido) avisar(getString(R.string.permiso_denegado))
		finish()
	}

	override fun onCreate(estado: Bundle?) {
		enableEdgeToEdge()
		super.onCreate(estado)
		b = ActivityEditarProductoBinding.inflate(layoutInflater)
		setContentView(b.root)
		ViewCompat.setOnApplyWindowInsetsListener(b.root) { v, insets ->
			val barras = insets.getInsets(WindowInsetsCompat.Type.systemBars() or WindowInsetsCompat.Type.displayCutout() or WindowInsetsCompat.Type.ime())
			v.updatePadding(left = barras.left, top = barras.top, right = barras.right, bottom = barras.bottom)
			WindowInsetsCompat.CONSUMED
		}
		val id = intent.getLongExtra(EXTRA_ID, 0L)
		configurarBarra(b.barra, getString(if (id > 0) R.string.editar_producto else R.string.anadir_producto))
		b.guardar.setText(if (id > 0) R.string.guardar_cambios else R.string.comprobar_y_guardar)
		b.guardar.setOnClickListener { guardar() }
		b.categoria.setOnClickListener { elegirCategoria() }
		b.elegirPrecio.isVisible = id > 0
		b.elegirPrecio.setOnClickListener { ElegirPrecioActivity.abrir(this, id) }
		if (estado != null && estado.containsKey(ESTADO_CATEGORIA)) categoriaId = estado.getLong(ESTADO_CATEGORIA).takeIf { it > 0 }

		lifecycleScope.launch {
			val (p, cats) = withContext(Dispatchers.IO) { (if (id > 0) db.producto(id) else null) to db.categorias() }
			categorias = cats
			if (id > 0 && p == null) {
				finish()
				return@launch
			}
			original = p
			if (estado == null) {
				if (p != null) rellenar(p)
				else {
					// Dirección compartida desde el navegador o pasada por quien abre la pantalla
					val compartida = if (intent.action == Intent.ACTION_SEND) intent.getStringExtra(Intent.EXTRA_TEXT) else intent.getStringExtra(EXTRA_URL)
					val url = primeraUrl(compartida) ?: compartida?.trim()
					if (!url.isNullOrBlank()) b.url.setText(url)
				}
			}
			mostrarCategoria()
		}
	}

	override fun onSaveInstanceState(estado: Bundle) {
		super.onSaveInstanceState(estado)
		estado.putLong(ESTADO_CATEGORIA, categoriaId ?: 0L)
	}

	private fun rellenar(p: Producto) {
		b.url.setText(p.url)
		b.nombre.setText(p.nombre)
		categoriaId = p.categoriaId
		b.grupo.setText(p.grupo.orEmpty())
		b.objetivo.setText(p.precioObjetivo?.let { formatearImporte(it).substringBeforeLast(' ') }.orEmpty())
		b.alerta.setText(if (p.alertaPorcentaje > 0) formatearPorcentaje(p.alertaPorcentaje) else "")
		b.avisarDisponible.isChecked = p.avisarDisponible
		b.selector.setText(p.selectorPrecio.orEmpty())
		b.notas.setText(p.notas.orEmpty())
	}

	private fun mostrarCategoria() {
		val nombre = categorias.firstOrNull { it.id == categoriaId }?.nombre ?: getString(R.string.sin_categoria)
		b.categoria.text = getString(R.string.campo_categoria, nombre)
	}

	private fun elegirCategoria() {
		val nombres = listOf(getString(R.string.sin_categoria)) + categorias.map { it.nombre } + getString(R.string.nueva_categoria)
		val actual = if (categoriaId == null) 0 else categorias.indexOfFirst { it.id == categoriaId } + 1
		elegirUno(getString(R.string.elegir_categoria), nombres, actual) { i ->
			when (i) {
				0 -> categoriaId = null
				nombres.lastIndex -> {
					pedirTexto(getString(R.string.nueva_categoria), getString(R.string.nombre_categoria)) { nombre ->
						if (nombre.isBlank()) return@pedirTexto
						lifecycleScope.launch {
							val nueva = withContext(Dispatchers.IO) {
								val id = db.crearCategoria(nombre)
								categorias = db.categorias()
								id
							}
							categoriaId = nueva
							mostrarCategoria()
						}
					}
					return@elegirUno
				}
				else -> categoriaId = categorias[i - 1].id
			}
			mostrarCategoria()
		}
	}

	private fun texto(campo: com.google.android.material.textfield.TextInputEditText) = campo.text?.toString()?.trim().orEmpty()

	/** Lee y valida los campos. Devuelve null (y marca el error en su campo) si algo no vale. */
	private fun leerCampos(): Producto? {
		b.campoUrl.error = null
		b.campoObjetivo.error = null
		b.campoAlerta.error = null
		val url = texto(b.url)
		if (!pareceUrl(url)) {
			b.campoUrl.error = getString(R.string.error_direccion)
			b.url.requestFocus()
			return null
		}
		val objetivoTexto = texto(b.objetivo)
		val objetivo = if (objetivoTexto.isEmpty()) null else analizarImporte(objetivoTexto)
		if (objetivoTexto.isNotEmpty() && objetivo == null) {
			b.campoObjetivo.error = getString(R.string.error_objetivo)
			b.objetivo.requestFocus()
			return null
		}
		val alertaTexto = texto(b.alerta)
		val alerta = if (alertaTexto.isEmpty()) 0.0 else alertaTexto.replace(',', '.').toDoubleOrNull()
		if (alerta == null || alerta < 0 || alerta >= 100) {
			b.campoAlerta.error = getString(R.string.error_alerta)
			b.alerta.requestFocus()
			return null
		}
		val base = original ?: Producto(uuid = BaseDatos.nuevoUuid(), nombre = "", url = "", fechaAlta = Fechas.ahora())
		return base.copy(
			url = limpiarUrl(url),
			nombre = texto(b.nombre),
			categoriaId = categoriaId,
			grupo = texto(b.grupo).ifEmpty { null },
			precioObjetivo = objetivo,
			alertaPorcentaje = alerta,
			avisarDisponible = b.avisarDisponible.isChecked,
			selectorPrecio = texto(b.selector).ifEmpty { null },
			notas = texto(b.notas).ifEmpty { null },
		)
	}

	private fun guardar() {
		val p = leerCampos() ?: return
		lifecycleScope.launch {
			// ¿Ya se sigue esa dirección?
			val repetido = withContext(Dispatchers.IO) { db.productoPorUrl(p.url) }?.takeIf { it.id != p.id }
			if (repetido != null) {
				MaterialAlertDialogBuilder(this@EditarProductoActivity)
					.setTitle(R.string.ya_existe_titulo)
					.setMessage(getString(R.string.ya_existe_texto, repetido.nombre.ifBlank { repetido.url }))
					.setPositiveButton(R.string.abrir_producto) { _, _ ->
						DetalleActivity.abrir(this@EditarProductoActivity, repetido.id)
						finish()
					}
					.setNegativeButton(R.string.cancelar, null)
					.show()
				return@launch
			}
			if (original != null) guardarCambios(p) else comprobarYConfirmar(p)
		}
	}

	private suspend fun tiendaDe(url: String) = withContext(Dispatchers.IO) {
		val dominio = dominioDe(url)
		db.tiendaParaDominio(dominio, Comprobador.reglas(this@EditarProductoActivity).nombrePara(dominio))
	}

	private fun guardarCambios(p: Producto) {
		lifecycleScope.launch {
			withContext(Dispatchers.IO) {
				val tienda = if (p.url != original?.url) tiendaDe(p.url).id else p.tiendaId
				db.actualizarProducto(p.copy(tiendaId = tienda, nombre = p.nombre.ifBlank { original?.nombre.orEmpty() }))
			}
			avisar(getString(R.string.cambios_guardados))
			finish()
		}
	}

	/** Al añadir: se comprueba la página en el momento y se pregunta si guardar lo encontrado. */
	private fun comprobarYConfirmar(p: Producto) {
		lifecycleScope.launch {
			var resultado: ResultadoExtraccion? = null
			var error: String? = null
			try {
				val tienda = tiendaDe(p.url)
				resultado = conEspera(getString(R.string.comprobando_producto), getString(R.string.comprobando_producto_texto)) {
					Comprobador.extraer(this@EditarProductoActivity, p.url, Comprobador.selectores(p, tienda), tienda.nombre)
				}
				error = resultado.error
			} catch (e: CancellationException) {
				throw e
			} catch (e: ErrorDescarga) {
				Log.w(ETIQUETA, "No se pudo descargar ${p.url}", e)
				error = e.message
			} catch (e: Exception) {
				Log.e(ETIQUETA, "Error al comprobar ${p.url}", e)
				error = getString(R.string.error_inesperado)
			}
			val r = resultado
			if (error == null && r != null) {
				val nombre = p.nombre.ifBlank { r.nombre ?: p.url }
				val precio = r.precio?.let { formatearImporte(it, r.moneda) } ?: getString(R.string.sin_precio_leido)
				val disponible = getString(if (r.disponible != false) R.string.disponible else R.string.estado_agotado).lowercase()
				val precioTexto = if (r.desde) getString(R.string.desde, precio) else precio
				val variantes = if (r.desde) "\n\n" + getString(R.string.tiene_variantes) else ""
				val dialogo = MaterialAlertDialogBuilder(this@EditarProductoActivity)
					.setTitle(R.string.producto_encontrado)
					.setMessage(getString(R.string.encontrado_guardar, nombre, precioTexto, disponible) + variantes)
					.setPositiveButton(R.string.guardar) { _, _ -> guardarNuevo(p, r, null) }
					.setNegativeButton(R.string.cancelar, null)
				// Con variantes sin elegir se ofrece elegir una (se abre el producto, donde está «Elegir variante»)
				if (r.desde && r.variantes.isNotEmpty()) {
					dialogo.setNeutralButton(R.string.guardar_y_elegir_variante) { _, _ -> guardarNuevo(p, r, null, Despues.ELEGIR_VARIANTE) }
				}
				dialogo.show()
			} else {
				// Sin precio seguro pero con importes en la página: «Elige el correcto»
				val hayCandidatos = r != null && r.candidatos.isNotEmpty() && r.documento != null
				MaterialAlertDialogBuilder(this@EditarProductoActivity)
					.setTitle(if (hayCandidatos || error == MensajesError.SIN_PRECIO) R.string.no_se_encontro_precio else R.string.no_se_pudo_comprobar)
					.setMessage(if (hayCandidatos) getString(R.string.no_seguro_elige) else getString(R.string.guardar_igualmente_texto, error ?: ""))
					.setPositiveButton(if (hayCandidatos) R.string.elegir_precio else R.string.guardar_igualmente) { _, _ ->
						guardarNuevo(p, null, error, if (hayCandidatos) Despues.ELEGIR_PRECIO else Despues.NADA)
					}
					.setNeutralButton(R.string.editar_selector) { _, _ ->
						b.selector.requestFocus()
						b.campoSelector.post { b.campoSelector.performAccessibilityAction(AccessibilityNodeInfo.ACTION_ACCESSIBILITY_FOCUS, null) }
					}
					.setNegativeButton(R.string.cancelar, null)
					.show()
			}
		}
	}

	/** Qué hacer después de guardar: elegir el precio en la página o la variante. */
	private enum class Despues { NADA, ELEGIR_PRECIO, ELEGIR_VARIANTE }

	private fun guardarNuevo(p: Producto, r: ResultadoExtraccion?, error: String?, despues: Despues = Despues.NADA) {
		lifecycleScope.launch {
			val (avisos, primero) = withContext(Dispatchers.IO) {
				val tienda = tiendaDe(p.url)
				val nuevo = p.copy(tiendaId = tienda.id, nombre = p.nombre.ifBlank { r?.nombre ?: "" })
				val id = db.crearProducto(nuevo)
				val guardado = nuevo.copy(id = id)
				val ajustes = Preferencias(this@EditarProductoActivity).ajustesAvisos
				val ahora = Fechas.ahora()
				val resultado = if (r != null) {
					LogicaAvisos.aplicarLectura(
						guardado,
						Lectura(r.precio, r.disponible ?: true, r.nombre, r.imagen, if (r.precio != null) r.moneda else null, r.origenTexto, r.confianza, r.desde),
						ajustes, ahora, tienda.nombre,
					)
				} else LogicaAvisos.aplicarError(guardado, error ?: getString(R.string.error_inesperado), ajustes, ahora, tienda.nombre)
				db.guardarComprobacion(resultado.producto, resultado.historial, resultado.avisos) to (db.cuantosProductos() == 1)
			}
			Notificaciones.avisar(applicationContext, avisos)
			avisar(getString(R.string.producto_guardado))
			val nuevoId = withContext(Dispatchers.IO) { db.productoPorUrl(p.url)?.id }
			if (nuevoId != null && despues == Despues.ELEGIR_PRECIO) ElegirPrecioActivity.abrir(this@EditarProductoActivity, nuevoId)
			if (nuevoId != null && despues == Despues.ELEGIR_VARIANTE) DetalleActivity.abrir(this@EditarProductoActivity, nuevoId)
			// El permiso de notificaciones se pide en contexto, al crear el primer producto
			if (primero && despues == Despues.NADA) pedirPermiso() else finish()
		}
	}

	private fun pedirPermiso() {
		val prefs = Preferencias(this)
		if (Build.VERSION.SDK_INT < 33 || prefs.permisoExplicado ||
			ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS) == PackageManager.PERMISSION_GRANTED
		) {
			finish()
			return
		}
		prefs.permisoExplicado = true
		MaterialAlertDialogBuilder(this)
			.setTitle(R.string.permiso_titulo)
			.setMessage(R.string.permiso_explicacion)
			.setPositiveButton(R.string.permitir_avisos) { _, _ -> permisoNotificaciones.launch(Manifest.permission.POST_NOTIFICATIONS) }
			.setNegativeButton(R.string.ahora_no) { _, _ -> finish() }
			.setOnCancelListener { finish() }
			.show()
	}
}
