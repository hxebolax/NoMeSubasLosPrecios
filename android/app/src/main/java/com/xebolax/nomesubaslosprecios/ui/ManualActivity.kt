package com.xebolax.nomesubaslosprecios.ui

import android.os.Bundle
import android.text.SpannableString
import android.text.Spanned
import android.text.style.BulletSpan
import android.util.Log
import android.widget.LinearLayout
import android.widget.TextView
import androidx.activity.enableEdgeToEdge
import androidx.appcompat.app.AppCompatActivity
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import androidx.core.view.updatePadding
import androidx.lifecycle.lifecycleScope
import com.xebolax.nomesubaslosprecios.R
import com.xebolax.nomesubaslosprecios.accesibilidad.configurarBarra
import com.xebolax.nomesubaslosprecios.accesibilidad.dp
import com.xebolax.nomesubaslosprecios.accesibilidad.encabezado
import com.xebolax.nomesubaslosprecios.databinding.ActivityManualBinding
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/**
 * Manual (manual.md) o novedades (novedades.md) de los assets, los mismos que
 * usa la app de Windows. «#», «##» y «###» son encabezados de verdad (con
 * TalkBack se navega por ellos); «- » es un punto de lista, cuyo símbolo es
 * solo visual para que TalkBack no diga «viñeta» en cada línea.
 */
class ManualActivity : AppCompatActivity() {

	companion object {
		const val EXTRA_NOVEDADES = "novedades"
		private const val ETIQUETA = "Manual"
	}

	private lateinit var b: ActivityManualBinding

	override fun onCreate(estado: Bundle?) {
		enableEdgeToEdge()
		super.onCreate(estado)
		b = ActivityManualBinding.inflate(layoutInflater)
		setContentView(b.root)
		ViewCompat.setOnApplyWindowInsetsListener(b.root) { v, insets ->
			val barras = insets.getInsets(WindowInsetsCompat.Type.systemBars() or WindowInsetsCompat.Type.displayCutout() or WindowInsetsCompat.Type.ime())
			v.updatePadding(left = barras.left, top = barras.top, right = barras.right, bottom = barras.bottom)
			WindowInsetsCompat.CONSUMED
		}
		val novedades = intent.getBooleanExtra(EXTRA_NOVEDADES, false)
		configurarBarra(b.barra, getString(if (novedades) R.string.novedades_version else R.string.manual))
		cargar(if (novedades) "novedades.md" else "manual.md")
	}

	private fun cargar(archivo: String) {
		lifecycleScope.launch {
			try {
				val texto = withContext(Dispatchers.IO) { assets.open(archivo).bufferedReader(Charsets.UTF_8).use { it.readText() } }
				pintar(texto)
			} catch (e: CancellationException) {
				throw e
			} catch (e: Exception) {
				Log.e(ETIQUETA, "No se pudo leer $archivo", e)
				anadir(getString(R.string.error_manual), com.google.android.material.R.style.TextAppearance_Material3_BodyLarge, encabezado = false)
			}
		}
	}

	/** Quita lo que solo es formato en Markdown: negritas, código y enlaces (se queda el texto). */
	private fun limpiar(linea: String): String = linea
		.replace(Regex("\\[([^\\]]+)]\\(([^)]+)\\)"), "$1 ($2)")
		.replace("**", "")
		.replace("__", "")
		.replace("`", "")
		.trim()

	private fun pintar(texto: String) {
		val cuerpo = com.google.android.material.R.style.TextAppearance_Material3_BodyLarge
		val parrafo = StringBuilder()
		fun cerrarParrafo() {
			if (parrafo.isNotBlank()) anadir(limpiar(parrafo.toString()), cuerpo, encabezado = false)
			parrafo.clear()
		}
		for (linea in texto.lines()) {
			val l = linea.trimEnd()
			when {
				l.startsWith("### ") -> {
					cerrarParrafo()
					anadir(limpiar(l.removePrefix("### ")), com.google.android.material.R.style.TextAppearance_Material3_TitleSmall, encabezado = true)
				}
				l.startsWith("## ") -> {
					cerrarParrafo()
					anadir(limpiar(l.removePrefix("## ")), com.google.android.material.R.style.TextAppearance_Material3_TitleMedium, encabezado = true)
				}
				l.startsWith("# ") -> {
					cerrarParrafo()
					anadir(limpiar(l.removePrefix("# ")), com.google.android.material.R.style.TextAppearance_Material3_HeadlineSmall, encabezado = true)
				}
				l.trimStart().startsWith("- ") || l.trimStart().startsWith("* ") -> {
					cerrarParrafo()
					anadirPunto(limpiar(l.trimStart().substring(2)), cuerpo)
				}
				l.isBlank() -> cerrarParrafo()
				else -> parrafo.append(l.trim()).append(' ')
			}
		}
		cerrarParrafo()
	}

	private fun anadirPunto(texto: String, estilo: Int) {
		val conPunto = SpannableString(texto)
		conPunto.setSpan(BulletSpan(dp(this, 12)), 0, texto.length, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE)
		anadir(conPunto, estilo, encabezado = false)
	}

	private fun anadir(texto: CharSequence, estilo: Int, encabezado: Boolean): TextView {
		val vista = TextView(this).apply {
			text = texto
			setTextAppearance(estilo)
			setPadding(0, dp(this@ManualActivity, if (encabezado) 16 else 4), 0, dp(this@ManualActivity, 4))
			setTextIsSelectable(!encabezado)
		}
		if (encabezado) vista.encabezado()
		b.contenedor.addView(vista, LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT))
		return vista
	}
}
