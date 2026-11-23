package com.xebolax.nomesubaslosprecios.ui

import android.graphics.Typeface
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.TextView
import androidx.core.view.isVisible
import androidx.recyclerview.widget.DiffUtil
import androidx.recyclerview.widget.ListAdapter
import androidx.recyclerview.widget.RecyclerView
import com.xebolax.nomesubaslosprecios.R
import com.xebolax.nomesubaslosprecios.accesibilidad.Accion
import com.xebolax.nomesubaslosprecios.accesibilidad.ZonaAcciones
import com.xebolax.nomesubaslosprecios.accesibilidad.accionAlMantener
import com.xebolax.nomesubaslosprecios.accesibilidad.accionesAccesibles
import com.xebolax.nomesubaslosprecios.accesibilidad.elegir
import com.xebolax.nomesubaslosprecios.accesibilidad.etiquetaPulsar
import com.xebolax.nomesubaslosprecios.nucleo.AjustesColores
import com.xebolax.nomesubaslosprecios.nucleo.TipoColor

/**
 * Una fila de lista: una sola parada para TalkBack que lo dice todo en una
 * línea (descripcion, con el estado primero), lo que hace el doble toque, las
 * acciones de TalkBack según el estado y el menú de la pulsación larga con todas.
 */
data class Fila(
	/** Id estable (el del dato): así el foco no se pierde al refrescar. */
	val id: Long,
	val titulo: String,
	val detalle: String,
	val descripcion: String,
	val etiquetaPulsar: String?,
	val destacada: Boolean = false,
	val zona: ZonaAcciones? = null,
	val alPulsar: () -> Unit,
	val acciones: List<Accion> = emptyList(),
	/** Color de la fila según su estado (1.1.0); solo visual: lo que se oye no cambia. */
	val tipoColor: TipoColor? = null,
) {
	/** Para comparar el contenido sin las lambdas. */
	val contenido get() = listOf(titulo, detalle, descripcion, etiquetaPulsar, destacada, acciones.map { it.first }, tipoColor)
}

class AdaptadorFilas : ListAdapter<Fila, AdaptadorFilas.Vista>(Diferencias) {

	init {
		setHasStableIds(true)
	}

	/** Ajustes de colores de la lista (null: sin colores). Al cambiar, se repintan las filas a la vista. */
	var colores: AjustesColores? = null
		set(v) {
			if (field == v) return
			field = v
			if (itemCount > 0) notifyItemRangeChanged(0, itemCount)
		}

	private object Diferencias : DiffUtil.ItemCallback<Fila>() {
		override fun areItemsTheSame(a: Fila, b: Fila) = a.id == b.id
		override fun areContentsTheSame(a: Fila, b: Fila) = a.contenido == b.contenido
	}

	class Vista(v: View) : RecyclerView.ViewHolder(v) {
		val titulo: TextView = v.findViewById(R.id.fila_titulo)
		val detalle: TextView = v.findViewById(R.id.fila_detalle)
		val pintor = PintorFila(v, titulo, detalle)
	}

	override fun getItemId(posicion: Int): Long = getItem(posicion).id

	override fun onCreateViewHolder(padre: ViewGroup, tipo: Int) =
		Vista(LayoutInflater.from(padre.context).inflate(R.layout.item_fila, padre, false))

	override fun onBindViewHolder(v: Vista, posicion: Int) {
		val f = getItem(posicion)
		v.titulo.text = f.titulo
		v.titulo.setTypeface(null, if (f.destacada) Typeface.BOLD else Typeface.NORMAL)
		v.detalle.text = f.detalle
		v.detalle.isVisible = f.detalle.isNotEmpty()
		v.pintor.pintar(f.tipoColor, colores)
		val fila = v.itemView
		// Lo que se oye: la línea entera en el orden de la especificación
		fila.contentDescription = f.descripcion
		fila.setOnClickListener { f.alPulsar() }
		f.etiquetaPulsar?.let { fila.etiquetaPulsar(it) }
		fila.accionesAccesibles(f.acciones, f.zona)
		if (f.acciones.isNotEmpty()) {
			fila.accionAlMantener(fila.context.getString(R.string.mas_opciones)) { fila.context.elegir(f.titulo, f.acciones) }
		} else {
			fila.setOnLongClickListener(null)
			fila.isLongClickable = false
		}
	}
}
