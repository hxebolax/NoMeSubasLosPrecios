package com.xebolax.nomesubaslosprecios.ui

import android.net.Uri
import android.os.Bundle
import android.util.Log
import android.widget.LinearLayout
import android.widget.TextView
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import androidx.core.view.isVisible
import androidx.core.view.updatePadding
import androidx.lifecycle.lifecycleScope
import com.google.android.material.checkbox.MaterialCheckBox
import com.google.android.material.dialog.MaterialAlertDialogBuilder
import com.xebolax.nomesubaslosprecios.BuildConfig
import com.xebolax.nomesubaslosprecios.R
import com.xebolax.nomesubaslosprecios.accesibilidad.conEspera
import com.xebolax.nomesubaslosprecios.accesibilidad.configurarBarra
import com.xebolax.nomesubaslosprecios.accesibilidad.confirmar
import com.xebolax.nomesubaslosprecios.accesibilidad.dp
import com.xebolax.nomesubaslosprecios.accesibilidad.mensaje
import com.xebolax.nomesubaslosprecios.databinding.ActivityImportarBinding
import com.xebolax.nomesubaslosprecios.datos.BaseDatos
import com.xebolax.nomesubaslosprecios.datos.ModoImportacion
import com.xebolax.nomesubaslosprecios.datos.Preferencias
import com.xebolax.nomesubaslosprecios.datos.ResumenImportacion
import com.xebolax.nomesubaslosprecios.motor.TrabajoComprobacion
import com.xebolax.nomesubaslosprecios.nucleo.ArchivoNoValido
import com.xebolax.nomesubaslosprecios.nucleo.Csv
import com.xebolax.nomesubaslosprecios.nucleo.DatosIntercambio
import com.xebolax.nomesubaslosprecios.nucleo.Fechas
import com.xebolax.nomesubaslosprecios.nucleo.Intercambio
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File

/**
 * Importar y exportar (ESPECIFICACION.md, «Importar y exportar»): el archivo
 * de intercambio JSON común con Windows y el CSV para hojas de cálculo, con el
 * selector de archivos del sistema (Drive, Descargas, USB...).
 */
class ImportarExportarActivity : AppCompatActivity() {

	private companion object {
		const val ETIQUETA = "ImportarExportar"
	}

	private lateinit var b: ActivityImportarBinding
	private val db by lazy { BaseDatos.obtener(this) }

	private val crearJson = registerForActivityResult(ActivityResultContracts.CreateDocument("application/json")) { uri -> uri?.let { exportarJson(it) } }
	private val crearCsv = registerForActivityResult(ActivityResultContracts.CreateDocument("text/csv")) { uri -> uri?.let { exportarCsv(it) } }
	private val abrir = registerForActivityResult(ActivityResultContracts.OpenDocument()) { uri -> uri?.let { leerArchivo(it) } }

	override fun onCreate(estado: Bundle?) {
		enableEdgeToEdge()
		super.onCreate(estado)
		b = ActivityImportarBinding.inflate(layoutInflater)
		setContentView(b.root)
		ViewCompat.setOnApplyWindowInsetsListener(b.root) { v, insets ->
			val barras = insets.getInsets(WindowInsetsCompat.Type.systemBars() or WindowInsetsCompat.Type.displayCutout() or WindowInsetsCompat.Type.ime())
			v.updatePadding(left = barras.left, top = barras.top, right = barras.right, bottom = barras.bottom)
			WindowInsetsCompat.CONSUMED
		}
		configurarBarra(b.barra, getString(R.string.importar_exportar))
		b.exportar.setOnClickListener { crearJson.launch(Intercambio.nombreArchivo()) }
		b.exportarCsv.setOnClickListener { crearCsv.launch("NoMeSubasLosPrecios-${Fechas.hoyParaArchivo()}.csv") }
		b.importar.setOnClickListener { abrir.launch(arrayOf("application/json", "text/plain", "application/octet-stream")) }
	}

	private fun estado(texto: String) {
		b.estado.text = texto
		b.estado.isVisible = true
	}

	private fun error(titulo: Int, e: Exception) {
		Log.e(ETIQUETA, "Fallo al importar o exportar", e)
		val texto = if (e is ArchivoNoValido) e.message.orEmpty() else getString(R.string.error_archivo, e.localizedMessage ?: e.javaClass.simpleName)
		mensaje(getString(titulo), texto)
	}

	private fun datosParaExportar(conAjustes: Boolean): DatosIntercambio {
		val d = db.exportar()
		return d.copy(versionApp = BuildConfig.VERSION_NAME, ajustes = if (conAjustes) Preferencias(this).exportar() else null)
	}

	private fun exportarJson(uri: Uri) {
		val conAjustes = b.conAjustes.isChecked
		lifecycleScope.launch {
			try {
				val d = conEspera(getString(R.string.exportando)) {
					withContext(Dispatchers.IO) {
						val d = datosParaExportar(conAjustes)
						// Se escribe en el Uri elegido de una vez
						val texto = Intercambio.escribir(d)
						contentResolver.openOutputStream(uri, "wt")?.use { it.write(texto.toByteArray(Charsets.UTF_8)) }
							?: throw IllegalStateException("No se pudo abrir el archivo")
						d
					}
				}
				estado(resources.getQuantityString(R.plurals.exportados, d.productos.size, d.productos.size))
			} catch (e: CancellationException) {
				throw e
			} catch (e: Exception) {
				error(R.string.exportar, e)
			}
		}
	}

	private fun exportarCsv(uri: Uri) {
		lifecycleScope.launch {
			try {
				val n = conEspera(getString(R.string.exportando)) {
					withContext(Dispatchers.IO) {
						val productos = db.productos()
						contentResolver.openOutputStream(uri, "wt")?.use { it.write(Csv.escribir(productos).toByteArray(Charsets.UTF_8)) }
							?: throw IllegalStateException("No se pudo abrir el archivo")
						productos.size
					}
				}
				estado(resources.getQuantityString(R.plurals.exportados_csv, n, n))
			} catch (e: CancellationException) {
				throw e
			} catch (e: Exception) {
				error(R.string.exportar_csv, e)
			}
		}
	}

	private fun leerArchivo(uri: Uri) {
		lifecycleScope.launch {
			try {
				val (d, resumen) = conEspera(getString(R.string.leyendo_archivo)) {
					withContext(Dispatchers.IO) {
						val texto = contentResolver.openInputStream(uri)?.use { it.readBytes().toString(Charsets.UTF_8) }
							?: throw IllegalStateException("No se pudo abrir el archivo")
						val d = Intercambio.leer(texto)
						d to db.simularImportacion(d, ModoImportacion.COMBINAR)
					}
				}
				preguntarModo(d, resumen)
			} catch (e: CancellationException) {
				throw e
			} catch (e: Exception) {
				error(R.string.importar, e)
			}
		}
	}

	private fun textoResumen(r: ResumenImportacion): String {
		val partes = mutableListOf(
			getString(
				R.string.resumen_importacion,
				resources.getQuantityString(R.plurals.n_productos, r.productos, r.productos),
				resources.getQuantityString(R.plurals.n_categorias, r.categorias, r.categorias),
				resources.getQuantityString(R.plurals.n_tiendas, r.tiendas, r.tiendas),
				resources.getQuantityString(R.plurals.se_anadiran, r.anadir, r.anadir),
				resources.getQuantityString(R.plurals.se_actualizaran, r.actualizar, r.actualizar),
			),
		)
		if (r.noValidos > 0) partes += resources.getQuantityString(R.plurals.no_validos, r.noValidos, r.noValidos)
		return partes.joinToString(" ")
	}

	/** Resumen previo y elección: Combinar (por defecto) o Reemplazar todo (con confirmación y copia de seguridad). */
	private fun preguntarModo(d: DatosIntercambio, resumen: ResumenImportacion) {
		val m = dp(this, 20)
		val texto = TextView(this).apply {
			text = textoResumen(resumen)
			setTextAppearance(com.google.android.material.R.style.TextAppearance_Material3_BodyLarge)
		}
		val ajustes = MaterialCheckBox(this).apply {
			setText(R.string.aplicar_ajustes_archivo)
			minHeight = dp(this@ImportarExportarActivity, 48)
		}
		val vista = LinearLayout(this).apply {
			orientation = LinearLayout.VERTICAL
			setPadding(m, m / 2, m, 0)
			addView(texto)
			if (d.ajustes != null) addView(ajustes)
		}
		MaterialAlertDialogBuilder(this)
			.setTitle(R.string.importar)
			.setView(vista)
			.setPositiveButton(R.string.combinar) { _, _ -> importar(d, ModoImportacion.COMBINAR, ajustes.isChecked) }
			.setNeutralButton(R.string.reemplazar_todo) { _, _ ->
				confirmar(getString(R.string.confirmar_reemplazar), getString(R.string.reemplazar_todo)) {
					importar(d, ModoImportacion.REEMPLAZAR, ajustes.isChecked)
				}
			}
			.setNegativeButton(R.string.cancelar, null)
			.show()
	}

	private fun importar(d: DatosIntercambio, modo: ModoImportacion, conAjustes: Boolean) {
		lifecycleScope.launch {
			try {
				val r = conEspera(getString(R.string.importando)) {
					withContext(Dispatchers.IO) {
						if (modo == ModoImportacion.REEMPLAZAR) copiaDeSeguridad()
						// En una transacción: si algo falla, no cambia nada
						db.importar(d, modo)
					}
				}
				if (conAjustes) d.ajustes?.let {
					Preferencias(this@ImportarExportarActivity).importar(it)
					TrabajoComprobacion.programar(this@ImportarExportarActivity)
				}
				estado(getString(R.string.importacion_hecha, textoResumen(r)))
			} catch (e: CancellationException) {
				throw e
			} catch (e: Exception) {
				error(R.string.importar, e)
			}
		}
	}

	/** Antes de reemplazar, copia de lo que había en el almacenamiento de la app (se guardan las 5 últimas). */
	private fun copiaDeSeguridad() {
		val carpeta = File(filesDir, "copias").apply { mkdirs() }
		File(carpeta, "antes-de-reemplazar-${System.currentTimeMillis()}.json").writeText(Intercambio.escribir(datosParaExportar(true)), Charsets.UTF_8)
		carpeta.listFiles()?.sortedByDescending { it.lastModified() }?.drop(5)?.forEach { it.delete() }
	}
}
