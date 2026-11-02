package com.xebolax.nomesubaslosprecios.ui

import android.annotation.SuppressLint
import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.webkit.CookieManager
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.activity.enableEdgeToEdge
import androidx.appcompat.app.AppCompatActivity
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import androidx.core.view.updatePadding
import com.xebolax.nomesubaslosprecios.R
import com.xebolax.nomesubaslosprecios.accesibilidad.configurarBarra
import com.xebolax.nomesubaslosprecios.databinding.ActivityNavegadorBinding
import com.xebolax.nomesubaslosprecios.nucleo.dominioDe

/**
 * «Abrir la tienda en la app»: la página en el navegador integrado, visible,
 * para que el usuario resuelva una verificación o acepte las cookies. Las
 * cookies se quedan para las comprobaciones siguientes. Atrás la cierra.
 */
class NavegadorActivity : AppCompatActivity() {

	companion object {
		private const val EXTRA_URL = "url"

		fun abrir(c: Context, url: String) {
			c.startActivity(Intent(c, NavegadorActivity::class.java).putExtra(EXTRA_URL, url))
		}
	}

	private lateinit var b: ActivityNavegadorBinding

	@SuppressLint("SetJavaScriptEnabled")
	override fun onCreate(estado: Bundle?) {
		enableEdgeToEdge()
		super.onCreate(estado)
		b = ActivityNavegadorBinding.inflate(layoutInflater)
		setContentView(b.root)
		ViewCompat.setOnApplyWindowInsetsListener(b.root) { v, insets ->
			val barras = insets.getInsets(WindowInsetsCompat.Type.systemBars() or WindowInsetsCompat.Type.displayCutout() or WindowInsetsCompat.Type.ime())
			v.updatePadding(left = barras.left, top = barras.top, right = barras.right, bottom = barras.bottom)
			WindowInsetsCompat.CONSUMED
		}
		val url = intent.getStringExtra(EXTRA_URL).orEmpty()
		configurarBarra(b.barra, getString(R.string.tienda_en_la_app, dominioDe(url)))
		b.web.settings.javaScriptEnabled = true
		b.web.settings.domStorageEnabled = true
		CookieManager.getInstance().setAcceptCookie(true)
		CookieManager.getInstance().setAcceptThirdPartyCookies(b.web, true)
		// Los enlaces se quedan dentro (es la misma tienda)
		b.web.webViewClient = object : WebViewClient() {
			override fun onPageFinished(v: WebView?, u: String?) {
				v?.title?.takeIf { it.isNotBlank() }?.let { b.estado.text = getString(R.string.navegador_cargada, it) }
			}
		}
		if (estado == null) b.web.loadUrl(url) else b.web.restoreState(estado)
	}

	override fun onSaveInstanceState(estado: Bundle) {
		super.onSaveInstanceState(estado)
		b.web.saveState(estado)
	}

	override fun onPause() {
		CookieManager.getInstance().flush()
		super.onPause()
	}

	override fun onDestroy() {
		b.web.destroy()
		super.onDestroy()
	}
}
