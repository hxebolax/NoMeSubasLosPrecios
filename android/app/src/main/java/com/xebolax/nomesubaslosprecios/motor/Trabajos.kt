package com.xebolax.nomesubaslosprecios.motor

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.util.Log
import androidx.work.BackoffPolicy
import androidx.work.Constraints
import androidx.work.CoroutineWorker
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.ExistingWorkPolicy
import androidx.work.NetworkType
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import com.xebolax.nomesubaslosprecios.datos.Preferencias
import kotlinx.coroutines.CancellationException
import java.util.concurrent.TimeUnit

/**
 * Comprobación periódica con WorkManager: cada intervalo_horas, con red
 * (sin medir si solo_wifi) y la batería no baja. Un trabajo no pasa de unos
 * 8 minutos: si quedan productos, encadena otro que sigue donde lo dejó.
 */
class TrabajoComprobacion(contexto: Context, parametros: WorkerParameters) : CoroutineWorker(contexto, parametros) {

	companion object {
		private const val ETIQUETA = "TrabajoComprobacion"
		const val PERIODICO = "comprobacion_periodica"
		const val CONTINUACION = "comprobacion_continuacion"
		/** Tiempo máximo de un trabajo (WorkManager corta a los 10 minutos). */
		const val LIMITE_MS = 8 * 60 * 1000L

		private fun restricciones(c: Context) = Constraints.Builder()
			.setRequiredNetworkType(if (Preferencias(c).soloWifi) NetworkType.UNMETERED else NetworkType.CONNECTED)
			.setRequiresBatteryNotLow(true)
			.build()

		/** Programa (o reprograma, al cambiar el intervalo) la comprobación periódica. */
		fun programar(c: Context) {
			val horas = Preferencias(c).intervaloHoras.toLong()
			val peticion = PeriodicWorkRequestBuilder<TrabajoComprobacion>(horas, TimeUnit.HOURS)
				.setConstraints(restricciones(c))
				.setBackoffCriteria(BackoffPolicy.EXPONENTIAL, 15, TimeUnit.MINUTES)
				.build()
			WorkManager.getInstance(c).enqueueUniquePeriodicWork(PERIODICO, ExistingPeriodicWorkPolicy.UPDATE, peticion)
			Log.i(ETIQUETA, "Comprobación programada cada $horas horas")
		}

		/** Encadena otro trabajo para los productos que no dio tiempo a comprobar. */
		fun encadenar(c: Context) {
			val peticion = OneTimeWorkRequestBuilder<TrabajoComprobacion>()
				.setConstraints(restricciones(c))
				.setInitialDelay(1, TimeUnit.MINUTES)
				.setBackoffCriteria(BackoffPolicy.EXPONENTIAL, 15, TimeUnit.MINUTES)
				.build()
			WorkManager.getInstance(c).enqueueUniqueWork(CONTINUACION, ExistingWorkPolicy.APPEND_OR_REPLACE, peticion)
		}
	}

	override suspend fun doWork(): Result {
		return try {
			val resumen = Comprobador.comprobarTodos(applicationContext, manual = false, limiteMs = LIMITE_MS)
			if (resumen == null) {
				Log.i(ETIQUETA, "Ya había una comprobación en curso")
			} else if (resumen.pendientes > 0) {
				Log.i(ETIQUETA, "Quedan ${resumen.pendientes} productos: se encadena otro trabajo")
				encadenar(applicationContext)
			}
			Result.success()
		} catch (e: CancellationException) {
			throw e
		} catch (e: Exception) {
			Log.e(ETIQUETA, "La comprobación en segundo plano falló", e)
			if (runAttemptCount < 3) Result.retry() else Result.failure()
		}
	}
}

/** Al arrancar el teléfono o actualizar la app, se vuelve a programar la comprobación. */
class ArranqueReceptor : BroadcastReceiver() {
	override fun onReceive(contexto: Context, intent: Intent) {
		if (intent.action == Intent.ACTION_BOOT_COMPLETED || intent.action == Intent.ACTION_MY_PACKAGE_REPLACED) {
			TrabajoComprobacion.programar(contexto)
		}
	}
}
