package com.xebolax.nomesubaslosprecios.ui

import android.content.Context
import android.util.Log
import com.xebolax.nomesubaslosprecios.NoMeSubasApp
import com.xebolax.nomesubaslosprecios.R
import com.xebolax.nomesubaslosprecios.motor.Comprobador
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.launch

/**
 * «Comprobar todos ahora»: corre en el ámbito de la app (sigue aunque se
 * cierre la pantalla), con notificación de progreso, y deja el resultado para
 * mostrarlo en la pantalla principal.
 */
object ComprobacionManual {

	private const val ETIQUETA = "ComprobacionManual"

	private var trabajo: Job? = null

	/** Texto del resultado de la última comprobación manual, hasta que la pantalla lo muestra. */
	val resultado = MutableStateFlow<String?>(null)

	/** Lanza la comprobación. Devuelve false si ya había una en curso. */
	fun lanzar(contexto: Context, manual: Boolean = true): Boolean {
		if (Comprobador.enCurso || trabajo?.isActive == true) return false
		val app = contexto.applicationContext
		trabajo = NoMeSubasApp.ambito.launch {
			try {
				val r = Comprobador.comprobarTodos(app, manual = manual) ?: return@launch
				if (!manual) return@launch
				resultado.value = when {
					r.total == 0 -> app.getString(R.string.nada_que_comprobar)
					else -> app.resources.getQuantityString(R.plurals.comprobacion_terminada, r.comprobados, r.comprobados) + " " +
						app.resources.getQuantityString(R.plurals.cambios_de_precio, r.cambios, r.cambios) + " " +
						app.resources.getQuantityString(R.plurals.con_problemas, r.errores, r.errores)
				}
			} catch (e: CancellationException) {
				if (manual) resultado.value = app.getString(R.string.comprobacion_detenida)
				throw e
			} catch (e: Exception) {
				Log.e(ETIQUETA, "La comprobación de todos los productos falló", e)
				if (manual) resultado.value = app.getString(R.string.error_inesperado)
			}
		}
		return true
	}

	fun detener() {
		trabajo?.cancel()
	}

	val enCurso: Boolean get() = trabajo?.isActive == true || Comprobador.enCurso
}
