package com.xebolax.nomesubaslosprecios.ui

import android.app.Dialog
import android.content.Context
import android.content.res.Configuration
import android.graphics.drawable.Drawable
import android.graphics.drawable.GradientDrawable
import android.util.AttributeSet
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.ArrayAdapter
import android.widget.CheckedTextView
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.TextView
import androidx.preference.ListPreference
import androidx.preference.Preference
import androidx.preference.PreferenceViewHolder
import com.google.android.material.color.MaterialColors
import com.google.android.material.dialog.MaterialAlertDialogBuilder
import com.xebolax.nomesubaslosprecios.R
import com.xebolax.nomesubaslosprecios.datos.Preferencias
import com.xebolax.nomesubaslosprecios.nucleo.AjustesColores
import com.xebolax.nomesubaslosprecios.nucleo.ColorPaleta
import com.xebolax.nomesubaslosprecios.nucleo.Colores
import com.xebolax.nomesubaslosprecios.nucleo.ModoColores
import com.xebolax.nomesubaslosprecios.nucleo.TipoColor

/*
 * Colores de la lista (1.1.0, ESPECIFICACION.md, «Colores de la lista»): cómo se
 * pinta una fila, la muestra de color, la lista de colores de Ajustes y la
 * vista previa. El color es solo para quien ve la pantalla: las filas siguen
 * diciendo su estado y lo que oye TalkBack no cambia.
 */

/** Con el tema oscuro se usan «Fondo oscuro» y «Texto claro». */
fun Context.temaOscuro(): Boolean =
	(resources.configuration.uiMode and Configuration.UI_MODE_NIGHT_MASK) == Configuration.UI_MODE_NIGHT_YES

fun Context.nombreTipoColor(t: TipoColor): String = getString(
	when (t) {
		TipoColor.BAJADA -> R.string.color_tipo_bajada
		TipoColor.SUBIDA -> R.string.color_tipo_subida
		TipoColor.OBJETIVO -> R.string.color_tipo_objetivo
		TipoColor.PROBLEMA -> R.string.color_tipo_problema
	},
)

/**
 * Pinta una fila (item_fila) según su tipo de color: el fondo (modo fondo) o las
 * letras (modo texto). Sin color, vuelve a los colores del tema. El estado
 * pulsado y enfocado se ve igual porque va en el primer plano (foreground).
 */
class PintorFila(private val fila: View, private val titulo: TextView, private val detalle: TextView) {

	private val colorTitulo = titulo.textColors
	private val colorDetalle = detalle.textColors

	fun pintar(tipo: TipoColor?, ajustes: AjustesColores?) {
		val color = ajustes?.pintura(tipo, fila.context.temaOscuro())
		val modo = ajustes?.modo
		if (color != null && modo == ModoColores.FONDO) fila.setBackgroundColor(color) else fila.background = null
		if (color != null && modo == ModoColores.TEXTO) {
			titulo.setTextColor(color)
			detalle.setTextColor(color)
		} else {
			titulo.setTextColor(colorTitulo)
			detalle.setTextColor(colorDetalle)
		}
	}
}

/**
 * Muestra de un color (círculo de 24 dp con borde, para que se vea sobre
 * cualquier fondo): el tono que de verdad llevará la lista con el modo y el
 * tema actuales. «Sin color» es un círculo vacío. Siempre decorativa.
 */
fun Context.muestraColor(color: ColorPaleta, modo: ModoColores): Drawable {
	val lado = (24 * resources.displayMetrics.density).toInt()
	val borde = MaterialColors.getColor(this, com.google.android.material.R.attr.colorOutline, 0xFF5F6A5E.toInt())
	return GradientDrawable().apply {
		shape = GradientDrawable.OVAL
		setSize(lado, lado)
		setColor(color.pintura(modo, temaOscuro()) ?: 0)
		setStroke((1.5f * resources.displayMetrics.density).toInt().coerceAtLeast(1), borde)
	}
}

/**
 * Lista de colores de Ajustes (color_bajada, color_subida...). La fila dice su
 * título y el color elegido («Subida, Rojo») y lleva la muestra al final,
 * decorativa. Al pulsarla se abre la lista de la paleta: cada opción con su
 * muestra y su nombre (TalkBack lee el nombre y «marcado» en la elegida).
 */
class PreferenciaColor @JvmOverloads constructor(
	contexto: Context,
	atributos: AttributeSet? = null,
) : ListPreference(contexto, atributos) {

	init {
		entries = Colores.PALETA.map { it.nombre }.toTypedArray()
		entryValues = Colores.IDS.toTypedArray()
		widgetLayoutResource = R.layout.preferencia_muestra
		summaryProvider = SimpleSummaryProvider.getInstance()
	}

	private val tipo: TipoColor? get() = TipoColor.entries.firstOrNull { it.clave == key }

	private fun colorActual(): ColorPaleta = Colores.color(value, tipo)

	private fun modo(): ModoColores = Preferencias(context).coloresModo

	/** Un valor desconocido se muestra como el de por defecto (como lo lee la lista). */
	override fun onSetInitialValue(valorPorDefecto: Any?) {
		super.onSetInitialValue(valorPorDefecto)
		val v = value
		if (v == null || v !in Colores.IDS) value = colorActual().id
	}

	override fun onBindViewHolder(holder: PreferenceViewHolder) {
		super.onBindViewHolder(holder)
		(holder.findViewById(R.id.muestra) as? ImageView)?.apply {
			setImageDrawable(context.muestraColor(colorActual(), modo()))
			importantForAccessibility = View.IMPORTANT_FOR_ACCESSIBILITY_NO
			// Apagada como el texto de la fila cuando los colores están desactivados
			alpha = if (isEnabled) 1f else 0.38f
		}
	}

	/** Para repintar la muestra cuando cambia «Qué se colorea». */
	fun refrescar() = notifyChanged()

	override fun onClick() {
		val c = context
		val modo = modo()
		val actual = Colores.IDS.indexOf(colorActual().id)
		val adaptador = object : ArrayAdapter<ColorPaleta>(c, R.layout.item_color, Colores.PALETA) {
			override fun getView(posicion: Int, reciclada: View?, padre: ViewGroup): View {
				val v = (reciclada ?: LayoutInflater.from(c).inflate(R.layout.item_color, padre, false)) as CheckedTextView
				val color = Colores.PALETA[posicion]
				v.text = color.nombre
				v.setCompoundDrawablesRelativeWithIntrinsicBounds(c.muestraColor(color, modo), null, null, null)
				return v
			}
		}
		var dialogo: Dialog? = null
		dialogo = MaterialAlertDialogBuilder(c)
			.setTitle(title)
			.setSingleChoiceItems(adaptador, actual) { _, i ->
				val nuevo = Colores.IDS[i]
				if (callChangeListener(nuevo)) value = nuevo
				dialogo?.dismiss()
			}
			.setNegativeButton(R.string.cancelar, null)
			.show()
	}
}

/**
 * Vista previa de Ajustes: una fila de ejemplo por estado, pintada como quedará
 * la lista. Decorativa para TalkBack (no se lee ni se enfoca): lo que importa ya
 * lo dicen las listas de colores.
 */
class VistaPreviaColores @JvmOverloads constructor(
	contexto: Context,
	atributos: AttributeSet? = null,
) : Preference(contexto, atributos) {

	private val ejemplos = listOf(
		TipoColor.BAJADA to (R.string.colores_ejemplo_bajada to R.string.colores_ejemplo_bajada_detalle),
		TipoColor.SUBIDA to (R.string.colores_ejemplo_subida to R.string.colores_ejemplo_subida_detalle),
		TipoColor.OBJETIVO to (R.string.colores_ejemplo_objetivo to R.string.colores_ejemplo_objetivo_detalle),
		TipoColor.PROBLEMA to (R.string.colores_ejemplo_problema to R.string.colores_ejemplo_problema_detalle),
	)

	init {
		layoutResource = R.layout.preferencia_vista_previa
		isSelectable = false
		isPersistent = false
	}

	override fun onBindViewHolder(holder: PreferenceViewHolder) {
		super.onBindViewHolder(holder)
		holder.itemView.isFocusable = false
		holder.itemView.isClickable = false
		val filas = holder.findViewById(R.id.vista_previa_filas) as LinearLayout
		val ajustes = Preferencias(context).ajustesColores
		filas.removeAllViews()
		val inflador = LayoutInflater.from(context)
		for ((tipo, textos) in ejemplos) {
			val fila = inflador.inflate(R.layout.item_fila, filas, false)
			fila.isClickable = false
			fila.isFocusable = false
			fila.foreground = null
			val titulo = fila.findViewById<TextView>(R.id.fila_titulo)
			val detalle = fila.findViewById<TextView>(R.id.fila_detalle)
			titulo.setText(textos.first)
			detalle.setText(textos.second)
			PintorFila(fila, titulo, detalle).pintar(tipo, ajustes)
			filas.addView(fila)
		}
	}

	/** Para repintar al cambiar cualquier ajuste de colores. */
	fun refrescar() = notifyChanged()
}
