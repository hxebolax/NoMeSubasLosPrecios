package com.xebolax.nomesubaslosprecios.motor

import android.annotation.SuppressLint
import android.content.Context
import android.util.Log
import android.webkit.CookieManager
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import com.xebolax.nomesubaslosprecios.nucleo.leerJson
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeoutOrNull
import kotlin.coroutines.resume

/**
 * Navegador integrado sin mostrar (ESPECIFICACION.md, «Navegador
 * integrado»): carga la página con el WebView del sistema, como lo haría el
 * usuario, y devuelve el HTML ya montado. Sin cambiar el User-Agent ni nada
 * para engañar a la tienda; las cookies se conservan (CookieManager). Uno a
 * la vez y 30 segundos como mucho. El WebView se crea en el hilo principal,
 * también cuando lo llama el trabajo en segundo plano.
 */
object Navegador {

	private const val ETIQUETA = "Navegador"
	private const val MAXIMO_MS = 30_000L
	private const val ESPERA_EXTRA_MS = 8_000L

	private val uno = Mutex()

	/** HTML de la página tras cargarla, o null si no se pudo (sin motor web, tiempo agotado...). tienePrecio dice si ya se puede dejar de esperar. */
	suspend fun cargar(contexto: Context, url: String, tienePrecio: (String) -> Boolean): String? = uno.withLock {
		withContext(Dispatchers.Main) {
			val vista = try {
				crear(contexto.applicationContext)
			} catch (e: Exception) {
				// Sin WebView en el sistema (o actualizándose): se dice en el registro y se sigue sin navegador
				Log.e(ETIQUETA, "No se pudo crear el navegador integrado", e)
				return@withContext null
			}
			try {
				withTimeoutOrNull(MAXIMO_MS) {
					val cargada = CompletableDeferred<Unit>()
					vista.webViewClient = object : WebViewClient() {
						override fun onPageFinished(v: WebView?, u: String?) {
							cargada.complete(Unit)
						}

						override fun onReceivedError(v: WebView?, peticion: WebResourceRequest?, error: WebResourceError?) {
							if (peticion?.isForMainFrame == true) Log.w(ETIQUETA, "Error al cargar $url: ${error?.description}")
						}
					}
					vista.loadUrl(url)
					cargada.await()
					var html = leerHtml(vista)
					var esperado = 0L
					// Hasta 8 segundos más mientras no haya precio (las páginas montadas con JavaScript tardan)
					while ((html == null || !tienePrecio(html)) && esperado < ESPERA_EXTRA_MS) {
						delay(1000)
						esperado += 1000
						html = leerHtml(vista) ?: html
					}
					html
				}
			} finally {
				CookieManager.getInstance().flush()
				vista.stopLoading()
				vista.destroy()
			}
		}
	}

	@SuppressLint("SetJavaScriptEnabled")
	private fun crear(c: Context): WebView {
		val v = WebView(c)
		v.settings.javaScriptEnabled = true
		v.settings.domStorageEnabled = true
		v.settings.loadsImagesAutomatically = false
		CookieManager.getInstance().setAcceptCookie(true)
		CookieManager.getInstance().setAcceptThirdPartyCookies(v, true)
		return v
	}

	private suspend fun leerHtml(v: WebView): String? = suspendCancellableCoroutine { cont ->
		v.evaluateJavascript("document.documentElement.outerHTML") { valor ->
			// Llega como cadena JSON («"<html>..."»)
			cont.resume(leerJson(valor) as? String)
		}
	}
}
