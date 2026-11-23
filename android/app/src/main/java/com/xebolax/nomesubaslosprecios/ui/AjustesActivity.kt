package com.xebolax.nomesubaslosprecios.ui

import android.Manifest
import android.content.ActivityNotFoundException
import android.content.Intent
import android.content.SharedPreferences
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.provider.Settings
import android.text.InputType
import android.util.Log
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import androidx.core.view.updatePadding
import androidx.preference.EditTextPreference
import androidx.preference.Preference
import androidx.preference.PreferenceFragmentCompat
import com.google.android.material.dialog.MaterialAlertDialogBuilder
import com.xebolax.nomesubaslosprecios.R
import com.xebolax.nomesubaslosprecios.accesibilidad.configurarBarra
import com.xebolax.nomesubaslosprecios.accesibilidad.mensaje
import com.xebolax.nomesubaslosprecios.databinding.ActivityAjustesBinding
import com.xebolax.nomesubaslosprecios.datos.Preferencias
import com.xebolax.nomesubaslosprecios.motor.Notificaciones
import com.xebolax.nomesubaslosprecios.motor.TrabajoComprobacion
import com.xebolax.nomesubaslosprecios.nucleo.OrigenActualizaciones
import com.xebolax.nomesubaslosprecios.nucleo.TipoColor
import com.xebolax.nomesubaslosprecios.nucleo.formatearPorcentaje

/** Ajustes. Se abre solo desde el menú lateral (una sola puerta). */
class AjustesActivity : AppCompatActivity() {

	private lateinit var b: ActivityAjustesBinding

	override fun onCreate(estado: Bundle?) {
		enableEdgeToEdge()
		super.onCreate(estado)
		b = ActivityAjustesBinding.inflate(layoutInflater)
		setContentView(b.root)
		ViewCompat.setOnApplyWindowInsetsListener(b.root) { v, insets ->
			val barras = insets.getInsets(WindowInsetsCompat.Type.systemBars() or WindowInsetsCompat.Type.displayCutout() or WindowInsetsCompat.Type.ime())
			v.updatePadding(left = barras.left, top = barras.top, right = barras.right, bottom = barras.bottom)
			WindowInsetsCompat.CONSUMED
		}
		configurarBarra(b.barra, getString(R.string.ajustes))
		if (estado == null) supportFragmentManager.beginTransaction().replace(R.id.contenedor, AjustesFragment()).commit()
	}
}

class AjustesFragment : PreferenceFragmentCompat(), SharedPreferences.OnSharedPreferenceChangeListener {

	private companion object {
		const val ETIQUETA = "Ajustes"
	}

	private val permiso = registerForActivityResult(ActivityResultContracts.RequestPermission()) { actualizarPermiso() }

	override fun onCreatePreferences(estado: Bundle?, raiz: String?) {
		setPreferencesFromResource(R.xml.preferencias, raiz)
		findPreference<EditTextPreference>(Preferencias.CAMBIO_MINIMO_PORCENTAJE)?.apply {
			setOnBindEditTextListener { it.inputType = InputType.TYPE_CLASS_NUMBER or InputType.TYPE_NUMBER_FLAG_DECIMAL }
			summaryProvider = Preference.SummaryProvider<EditTextPreference> { p ->
				val v = p.text?.replace(',', '.')?.toDoubleOrNull() ?: 0.0
				if (v <= 0.0) getString(R.string.ajuste_cambio_minimo_todos) else getString(R.string.ajuste_cambio_minimo_valor, formatearPorcentaje(v))
			}
			setOnPreferenceChangeListener { _, nuevo ->
				val v = nuevo.toString().replace(',', '.').toDoubleOrNull()
				val valido = v != null && v >= 0 && v < 100
				if (!valido) requireContext().mensaje(getString(R.string.ajuste_cambio_minimo), getString(R.string.error_porcentaje))
				valido
			}
		}
		configurarDireccionActualizaciones()
		findPreference<Preference>("permiso_notificaciones")?.setOnPreferenceClickListener {
			pedirPermiso()
			true
		}
		findPreference<Preference>("notificacion_prueba")?.setOnPreferenceClickListener {
			val c = requireContext()
			if (!Notificaciones.prueba(c)) c.mensaje(getString(R.string.ajuste_notificacion_prueba), getString(R.string.notificaciones_desactivadas))
			true
		}
		findPreference<Preference>("acciones_talkback")?.setOnPreferenceClickListener {
			startActivity(Intent(requireContext(), AccionesAjustesActivity::class.java))
			true
		}
		findPreference<Preference>("bateria")?.setOnPreferenceClickListener {
			abrirBateria()
			true
		}
		actualizarPermiso()
	}

	override fun onResume() {
		super.onResume()
		preferenceManager.sharedPreferences?.registerOnSharedPreferenceChangeListener(this)
		actualizarPermiso()
	}

	override fun onPause() {
		preferenceManager.sharedPreferences?.unregisterOnSharedPreferenceChangeListener(this)
		super.onPause()
	}

	override fun onSharedPreferenceChanged(p: SharedPreferences?, clave: String?) {
		// Al cambiar el intervalo o la red se reprograma (ExistingPeriodicWorkPolicy.UPDATE)
		if (clave == Preferencias.INTERVALO_HORAS || clave == Preferencias.SOLO_WIFI) TrabajoComprobacion.programar(requireContext())
		if (clave == Preferencias.ORIGEN_ACTUALIZACIONES) activarDireccionActualizaciones()
		// Colores de la lista: las muestras dependen de «Qué se colorea» y la vista previa, de todo.
		// La lista principal se repinta sola al volver (PrincipalActivity.onResume).
		if (clave in Preferencias.CLAVES_COLORES) {
			if (clave == Preferencias.COLORES_MODO) {
				for (t in TipoColor.entries) findPreference<PreferenciaColor>(t.clave)?.refrescar()
			}
			findPreference<VistaPreviaColores>("colores_vista_previa")?.refrescar()
		}
	}

	/**
	 * «Dirección personalizada» (1.2.0): teclado de direcciones, resumen con la
	 * dirección o «Ninguna», activa solo con el origen «personalizada». Una
	 * dirección no válida no se guarda y se explica por qué; una válida se guarda
	 * ya normalizada (la carpeta, con «/» al final). Vacía se puede guardar.
	 */
	private fun configurarDireccionActualizaciones() {
		findPreference<EditTextPreference>(Preferencias.URL_ACTUALIZACIONES)?.apply {
			setOnBindEditTextListener {
				it.inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_URI
				it.hint = getString(R.string.ajuste_url_actualizaciones)
				it.setSelection(it.text.length)
			}
			summaryProvider = Preference.SummaryProvider<EditTextPreference> { p ->
				p.text?.trim()?.takeIf { it.isNotEmpty() } ?: getString(R.string.ajuste_url_ninguna)
			}
			setOnPreferenceChangeListener { pref, nuevo ->
				val texto = nuevo?.toString()?.trim().orEmpty()
				if (texto.isEmpty()) return@setOnPreferenceChangeListener true
				val base = OrigenActualizaciones.basePersonalizada(texto)
				if (base.isEmpty()) {
					requireContext().mensaje(getString(R.string.ajuste_url_actualizaciones), getString(R.string.ajuste_url_no_valida))
					false
				} else if (base != nuevo) {
					// Se guarda la carpeta normalizada en lugar de lo escrito
					(pref as EditTextPreference).text = base
					false
				} else true
			}
		}
		activarDireccionActualizaciones()
	}

	private fun activarDireccionActualizaciones() {
		findPreference<Preference>(Preferencias.URL_ACTUALIZACIONES)?.isEnabled =
			Preferencias(requireContext()).origenActualizaciones == OrigenActualizaciones.PERSONALIZADA
	}

	private fun permisoConcedido() = Build.VERSION.SDK_INT < 33 ||
		ContextCompat.checkSelfPermission(requireContext(), Manifest.permission.POST_NOTIFICATIONS) == PackageManager.PERMISSION_GRANTED

	private fun actualizarPermiso() {
		findPreference<Preference>("permiso_notificaciones")?.summary =
			getString(if (permisoConcedido() && Notificaciones.permitidas(requireContext())) R.string.ajuste_permiso_si else R.string.ajuste_permiso_no)
	}

	/** El permiso se explica antes de pedirlo; si ya se denegó, se abre la pantalla de notificaciones de la app. */
	private fun pedirPermiso() {
		val c = requireContext()
		if (permisoConcedido() && Notificaciones.permitidas(c)) {
			c.mensaje(getString(R.string.ajuste_permiso), getString(R.string.ajuste_permiso_si))
			return
		}
		MaterialAlertDialogBuilder(c)
			.setTitle(R.string.permiso_titulo)
			.setMessage(R.string.permiso_explicacion)
			.setPositiveButton(R.string.permitir_avisos) { _, _ ->
				val prefs = Preferencias(c)
				// Android solo muestra su diálogo si no se denegó antes; si no, se abren los ajustes de la app
				val puedePedir = Build.VERSION.SDK_INT >= 33 && !permisoConcedido() &&
					(!prefs.permisoExplicado || shouldShowRequestPermissionRationale(Manifest.permission.POST_NOTIFICATIONS))
				prefs.permisoExplicado = true
				if (puedePedir) permiso.launch(Manifest.permission.POST_NOTIFICATIONS) else abrirAjustesNotificaciones()
			}
			.setNegativeButton(R.string.ahora_no, null)
			.show()
	}

	private fun abrirAjustesNotificaciones() {
		val c = requireContext()
		val intent = if (Build.VERSION.SDK_INT >= 26) Intent(Settings.ACTION_APP_NOTIFICATION_SETTINGS).putExtra(Settings.EXTRA_APP_PACKAGE, c.packageName)
		else Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS, Uri.parse("package:${c.packageName}"))
		try {
			startActivity(intent)
		} catch (e: ActivityNotFoundException) {
			Log.e(ETIQUETA, "No se pudo abrir los ajustes de notificaciones", e)
		}
	}

	/** Abre la pantalla de optimización de batería del sistema (no se pide quitarla por defecto). */
	private fun abrirBateria() {
		try {
			startActivity(Intent(Settings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS))
		} catch (e: ActivityNotFoundException) {
			Log.e(ETIQUETA, "No se pudo abrir la optimización de batería", e)
			try {
				startActivity(Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS, Uri.parse("package:${requireContext().packageName}")))
			} catch (e2: ActivityNotFoundException) {
				Log.e(ETIQUETA, "No se pudo abrir la información de la app", e2)
				requireContext().mensaje(getString(R.string.ajuste_bateria), getString(R.string.ajuste_bateria_resumen))
			}
		}
	}
}
