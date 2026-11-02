package com.xebolax.nomesubaslosprecios

import android.app.Application
import android.util.Log
import com.xebolax.nomesubaslosprecios.accesibilidad.DeslizadorAjuste
import com.xebolax.nomesubaslosprecios.accesibilidad.MemoriaFoco
import com.xebolax.nomesubaslosprecios.datos.Preferencias
import com.xebolax.nomesubaslosprecios.motor.Notificaciones
import com.xebolax.nomesubaslosprecios.motor.TrabajoComprobacion
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob

class NoMeSubasApp : Application() {

	companion object {
		private const val ETIQUETA = "NoMeSubas"

		/** Ámbito para tareas que no dependen de una pantalla (la comprobación manual sigue aunque se cierre). */
		val ambito = CoroutineScope(SupervisorJob() + Dispatchers.Default)
	}

	override fun onCreate() {
		super.onCreate()
		// TalkBack vuelve al elemento de partida al cerrar diálogos y pantallas encima
		registerActivityLifecycleCallbacks(MemoriaFoco)
		DeslizadorAjuste.formatos[Preferencias.PAUSA_ENTRE_PETICIONES] = DeslizadorAjuste.segundos
		DeslizadorAjuste.formatos[Preferencias.TIEMPO_ESPERA] = DeslizadorAjuste.segundos
		Notificaciones.crearCanales(this)
		try {
			// Al arrancar se vuelve a programar (por si cambió el intervalo o se borraron los datos de WorkManager)
			TrabajoComprobacion.programar(this)
		} catch (e: IllegalStateException) {
			Log.e(ETIQUETA, "No se pudo programar la comprobación periódica", e)
		}
	}
}
