package com.xebolax.nomesubaslosprecios.motor

import android.util.Log
import com.xebolax.nomesubaslosprecios.nucleo.MensajesError
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.withContext
import okhttp3.Call
import okhttp3.Callback
import okhttp3.Cookie
import okhttp3.CookieJar
import okhttp3.HttpUrl
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import org.jsoup.Jsoup
import java.io.ByteArrayInputStream
import java.io.IOException
import java.net.ConnectException
import java.net.SocketTimeoutException
import java.net.UnknownHostException
import java.nio.charset.Charset
import java.util.concurrent.TimeUnit
import javax.net.ssl.SSLException
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException

/** Una página descargada: el HTML ya decodificado, la dirección final y el código HTTP. */
data class Pagina(val html: String, val urlFinal: String, val codigo: Int)

/** Fallo de descarga con el mensaje en español para el usuario. bloqueo: la tienda pidió verificación. */
class ErrorDescarga(mensaje: String, val bloqueo: Boolean = false, causa: Throwable? = null) : Exception(mensaje, causa)

/**
 * Descarga de páginas como un navegador de escritorio (ESPECIFICACION.md,
 * «Descarga de páginas»): cabeceras de Chrome, gzip (OkHttp lo hace solo),
 * redirecciones, cookies de sesión en memoria y un reintento tras 5 segundos
 * si falla la red o la tienda responde 5xx.
 */
object Descargador {

	private const val ETIQUETA = "Descargador"
	const val AGENTE = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"

	/** Cookies en memoria por dominio (algunas tiendas, como Coolmod, las piden entre la redirección y la página). */
	private object Galletas : CookieJar {
		private val guardadas = HashMap<String, MutableList<Cookie>>()

		@Synchronized
		override fun saveFromResponse(url: HttpUrl, cookies: List<Cookie>) {
			val lista = guardadas.getOrPut(url.host) { mutableListOf() }
			for (c in cookies) {
				lista.removeAll { it.name == c.name && it.domain == c.domain && it.path == c.path }
				lista += c
			}
		}

		@Synchronized
		override fun loadForRequest(url: HttpUrl): List<Cookie> {
			val ahora = System.currentTimeMillis()
			return guardadas.values.flatten().filter { it.expiresAt > ahora && it.matches(url) }
		}
	}

	private val base: OkHttpClient by lazy {
		OkHttpClient.Builder()
			.cookieJar(Galletas)
			.followRedirects(true)
			.followSslRedirects(true)
			.retryOnConnectionFailure(true)
			.build()
	}

	private fun cliente(segundos: Int): OkHttpClient = base.newBuilder()
		.connectTimeout(segundos.toLong().coerceAtMost(20), TimeUnit.SECONDS)
		.readTimeout(segundos.toLong(), TimeUnit.SECONDS)
		.callTimeout(segundos.toLong() + 5, TimeUnit.SECONDS)
		.build()

	private fun peticion(url: String, aceptar: String) = Request.Builder()
		.url(url)
		.header("User-Agent", AGENTE)
		.header("Accept", aceptar)
		.header("Accept-Language", "es-ES,es;q=0.9,en;q=0.5")
		.header("Upgrade-Insecure-Requests", "1")
		.build()

	/** Ejecuta la llamada sin bloquear y la cancela si se cancela la corrutina. */
	private suspend fun Call.esperar(): Response = suspendCancellableCoroutine { cont ->
		cont.invokeOnCancellation { cancel() }
		enqueue(object : Callback {
			override fun onResponse(call: Call, response: Response) = cont.resume(response)
			override fun onFailure(call: Call, e: IOException) {
				if (!cont.isCancelled) cont.resumeWithException(e)
			}
		})
	}

	/** Texto de la página: el juego de caracteres de la cabecera o, si no lo dice, el que detecta Jsoup en el HTML. */
	private fun decodificar(bytes: ByteArray, tipo: String?, url: String): String {
		val juego = tipo?.let { Regex("charset=([\\w.:-]+)", RegexOption.IGNORE_CASE).find(it)?.groupValues?.get(1) }
		if (juego != null) {
			try {
				return String(bytes, Charset.forName(juego.trim('"')))
			} catch (e: IllegalArgumentException) {
				Log.w(ETIQUETA, "Juego de caracteres desconocido: $juego", e)
			}
		}
		// JSON (API de la tienda) y texto que no es HTML: UTF-8 tal cual (Jsoup lo envolvería en <html>)
		if (tipo != null && !tipo.contains("html", ignoreCase = true) && !tipo.contains("xml", ignoreCase = true)) return String(bytes, Charsets.UTF_8)
		return Jsoup.parse(ByteArrayInputStream(bytes), null, url).outerHtml()
	}

	/**
	 * Descarga la página. Lanza ErrorDescarga con un mensaje entendible; las
	 * respuestas 403 y 429 son un bloqueo de la tienda. Nunca más de 2 intentos.
	 */
	suspend fun descargar(
		url: String,
		tiempoEspera: Int,
		aceptar: String = "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
	): Pagina = withContext(Dispatchers.IO) {
		val cliente = cliente(tiempoEspera)
		var ultimo: Exception? = null
		for (intento in 1..2) {
			ensureActive()
			try {
				cliente.newCall(peticion(url, aceptar)).esperar().use { r ->
					val codigo = r.code
					when {
						codigo == 403 || codigo == 429 -> throw ErrorDescarga(MensajesError.BLOQUEO, bloqueo = true)
						codigo == 404 || codigo == 410 -> throw ErrorDescarga(MensajesError.NO_ENCONTRADA)
						codigo >= 500 -> throw IOException("La tienda respondió $codigo")
						// 400: algunas tiendas (Douglas, «Request Too Long») bloquean así; lo decide la extracción con sus textos
						codigo >= 400 && codigo != 400 -> throw ErrorDescarga(MensajesError.codigo(codigo))
					}
					val bytes = r.body?.bytes() ?: ByteArray(0)
					return@withContext Pagina(decodificar(bytes, r.header("Content-Type"), r.request.url.toString()), r.request.url.toString(), codigo)
				}
			} catch (e: ErrorDescarga) {
				throw e
			} catch (e: IOException) {
				ensureActive()
				ultimo = e
				Log.w(ETIQUETA, "Intento $intento fallido al descargar $url", e)
				if (intento == 1) delay(5000)
			}
		}
		val e = ultimo
		throw when (e) {
			is UnknownHostException, is ConnectException -> ErrorDescarga(MensajesError.SIN_CONEXION, causa = e)
			is SocketTimeoutException -> ErrorDescarga(MensajesError.TIEMPO_AGOTADO, causa = e)
			is SSLException -> ErrorDescarga("No se pudo establecer una conexión segura con la tienda.", causa = e)
			else -> {
				val codigo = e?.message?.let { Regex("respondió (\\d{3})").find(it)?.groupValues?.get(1)?.toIntOrNull() }
				if (codigo != null) ErrorDescarga(MensajesError.codigo(codigo), causa = e)
				else if (e is java.io.InterruptedIOException) ErrorDescarga(MensajesError.TIEMPO_AGOTADO, causa = e)
				else ErrorDescarga(MensajesError.SIN_CONEXION, causa = e)
			}
		}
	}
}
