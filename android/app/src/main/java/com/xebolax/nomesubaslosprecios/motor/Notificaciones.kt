package com.xebolax.nomesubaslosprecios.motor

import android.Manifest
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.util.Log
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.core.app.TaskStackBuilder
import androidx.core.content.ContextCompat
import com.xebolax.nomesubaslosprecios.R
import com.xebolax.nomesubaslosprecios.datos.BaseDatos
import com.xebolax.nomesubaslosprecios.nucleo.Aviso
import com.xebolax.nomesubaslosprecios.nucleo.LogicaAvisos
import com.xebolax.nomesubaslosprecios.nucleo.TipoAviso
import com.xebolax.nomesubaslosprecios.ui.DetalleActivity
import com.xebolax.nomesubaslosprecios.ui.PrincipalActivity

/**
 * Canales y notificaciones (ESPECIFICACION.md, «Notificaciones y segundo
 * plano», Android). Si el usuario no da permiso, no se muestra nada, pero
 * la sección Avisos lo sigue registrando todo.
 */
object Notificaciones {

	private const val ETIQUETA = "Notificaciones"

	const val CANAL_BAJADAS = "bajadas"
	const val CANAL_SUBIDAS = "subidas"
	const val CANAL_DISPONIBILIDAD = "disponibilidad"
	const val CANAL_PROBLEMAS = "problemas"
	const val CANAL_PROGRESO = "progreso"

	private const val ID_PROGRESO = 1
	private const val ID_RESUMEN = 2
	private const val ID_PRUEBA = 3
	/** Los avisos usan su id más esta base, para no chocar con los fijos. */
	private const val BASE_AVISOS = 1000

	fun crearCanales(c: Context) {
		if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
		val canales = listOf(
			NotificationChannel(CANAL_BAJADAS, c.getString(R.string.canal_bajadas), NotificationManager.IMPORTANCE_HIGH)
				.apply { description = c.getString(R.string.canal_bajadas_descripcion) },
			NotificationChannel(CANAL_SUBIDAS, c.getString(R.string.canal_subidas), NotificationManager.IMPORTANCE_DEFAULT)
				.apply { description = c.getString(R.string.canal_subidas_descripcion) },
			NotificationChannel(CANAL_DISPONIBILIDAD, c.getString(R.string.canal_disponibilidad), NotificationManager.IMPORTANCE_DEFAULT)
				.apply { description = c.getString(R.string.canal_disponibilidad_descripcion) },
			NotificationChannel(CANAL_PROBLEMAS, c.getString(R.string.canal_problemas), NotificationManager.IMPORTANCE_LOW)
				.apply { description = c.getString(R.string.canal_problemas_descripcion) },
			NotificationChannel(CANAL_PROGRESO, c.getString(R.string.canal_progreso), NotificationManager.IMPORTANCE_LOW)
				.apply { description = c.getString(R.string.canal_progreso_descripcion) },
		)
		c.getSystemService(NotificationManager::class.java).createNotificationChannels(canales)
	}

	fun permitidas(c: Context): Boolean {
		if (Build.VERSION.SDK_INT >= 33 &&
			ContextCompat.checkSelfPermission(c, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED
		) return false
		return NotificationManagerCompat.from(c).areNotificationsEnabled()
	}

	private fun canal(tipo: String) = when (tipo) {
		TipoAviso.OBJETIVO, TipoAviso.MINIMO, TipoAviso.BAJADA -> CANAL_BAJADAS
		TipoAviso.SUBIDA -> CANAL_SUBIDAS
		TipoAviso.DISPONIBLE, TipoAviso.AGOTADO -> CANAL_DISPONIBILIDAD
		else -> CANAL_PROBLEMAS
	}

	private fun publicar(c: Context, id: Int, n: android.app.Notification) {
		if (!permitidas(c)) return
		try {
			NotificationManagerCompat.from(c).notify(id, n)
		} catch (e: SecurityException) {
			Log.e(ETIQUETA, "Sin permiso para notificar", e)
		}
	}

	private fun abrirApp(c: Context): PendingIntent =
		PendingIntent.getActivity(
			c, 0, Intent(c, PrincipalActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP),
			PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
		)

	/** Notifica los avisos de una comprobación, en un grupo y con un resumen si hay más de 3. */
	fun avisar(c: Context, avisos: List<Aviso>) {
		if (avisos.isEmpty()) return
		val db = BaseDatos.obtener(c)
		val grupo = "comprobacion_${System.currentTimeMillis()}"
		for (a in avisos) {
			val producto = a.productoId?.let { db.producto(it) }
			val b = NotificationCompat.Builder(c, canal(a.tipo))
				.setSmallIcon(R.drawable.ic_notif)
				.setContentTitle(a.titulo)
				.setContentText(a.mensaje)
				.setStyle(NotificationCompat.BigTextStyle().bigText(a.mensaje))
				.setAutoCancel(true)
				.setGroup(grupo)
				.setCategory(NotificationCompat.CATEGORY_RECOMMENDATION)
			if (producto != null) {
				// Pulsar la notificación abre los detalles, con la lista debajo para volver
				val detalle = Intent(c, DetalleActivity::class.java).putExtra(DetalleActivity.EXTRA_ID, producto.id)
				val pila = TaskStackBuilder.create(c).addNextIntentWithParentStack(detalle)
					.getPendingIntent(a.id.toInt(), PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
				b.setContentIntent(pila)
				val tienda = PendingIntent.getActivity(
					c, a.id.toInt(), Intent(Intent.ACTION_VIEW, Uri.parse(producto.url)).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK),
					PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
				)
				b.addAction(R.drawable.ic_notif, c.getString(R.string.abrir_en_la_tienda), tienda)
			} else b.setContentIntent(abrirApp(c))
			publicar(c, BASE_AVISOS + a.id.toInt(), b.build())
		}
		if (avisos.size > 3) {
			val texto = LogicaAvisos.textoResumen(avisos.size)
			val resumen = NotificationCompat.Builder(c, CANAL_BAJADAS)
				.setSmallIcon(R.drawable.ic_notif)
				.setContentTitle(texto)
				.setContentText(c.getString(R.string.resumen_notificacion_texto))
				.setGroup(grupo)
				.setGroupSummary(true)
				.setAutoCancel(true)
				.setContentIntent(abrirApp(c))
				.build()
			publicar(c, ID_RESUMEN, resumen)
		}
	}

	/** Notificación de progreso de la comprobación manual (canal de baja importancia, sin sonido). */
	fun progreso(c: Context, hechos: Int, total: Int) {
		val n = NotificationCompat.Builder(c, CANAL_PROGRESO)
			.setSmallIcon(R.drawable.ic_notif)
			.setContentTitle(c.getString(R.string.comprobando_precios))
			.setContentText(c.getString(R.string.progreso_comprobacion, hechos, total))
			.setProgress(total, hechos, total == 0)
			.setOngoing(true)
			.setOnlyAlertOnce(true)
			.setSilent(true)
			.setContentIntent(abrirApp(c))
			.build()
		publicar(c, ID_PROGRESO, n)
	}

	fun quitarProgreso(c: Context) {
		NotificationManagerCompat.from(c).cancel(ID_PROGRESO)
	}

	/** «Enviar una notificación de prueba» de Ajustes. Devuelve si se pudo enviar. */
	fun prueba(c: Context): Boolean {
		if (!permitidas(c)) return false
		val n = NotificationCompat.Builder(c, CANAL_BAJADAS)
			.setSmallIcon(R.drawable.ic_notif)
			.setContentTitle(c.getString(R.string.notificacion_prueba_titulo))
			.setContentText(c.getString(R.string.notificacion_prueba_texto))
			.setAutoCancel(true)
			.setContentIntent(abrirApp(c))
			.build()
		publicar(c, ID_PRUEBA, n)
		return true
	}
}
