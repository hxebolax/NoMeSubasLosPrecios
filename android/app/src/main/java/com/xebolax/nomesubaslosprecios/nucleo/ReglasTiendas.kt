package com.xebolax.nomesubaslosprecios.nucleo

import org.json.JSONArray
import org.json.JSONObject

/** Una regla CSS de tiendas.json: el selector y, si se pide, el atributo que se lee en vez del texto. */
data class ReglaCss(val css: String, val atributo: String? = null)

/** Regla de disponibilidad: si el elemento existe y su texto contiene alguno de «agotado» («» = siempre), está agotado. */
data class ReglaDisponible(val css: String, val agotado: List<String>)

/** Reglas de una tienda de tiendas.json. */
data class ReglasTienda(
	val id: String,
	val nombre: String,
	val dominios: List<String>,
	val precio: List<ReglaCss>,
	val titulo: List<ReglaCss>,
	val imagen: List<ReglaCss>,
	val disponible: List<ReglaDisponible>,
	val bloqueo: List<String>,
	val notas: String,
	/** La tienda no da la página a una descarga normal o monta el precio con JavaScript: va con el navegador integrado. */
	val navegador: Boolean = false,
	/** API pública de la tienda (Mercadona, Consum, BM), que se usa antes que el HTML. */
	val api: ApiTienda? = null,
)

/**
 * tiendas.json cargado una sola vez, con un mapa de dominio a tienda para
 * buscar deprisa aunque el archivo crezca mucho.
 */
class ReglasTiendas(val bloqueoGeneral: List<String>, val tiendas: List<ReglasTienda>) {

	private val porDominio: Map<String, ReglasTienda> = HashMap<String, ReglasTienda>().apply {
		for (t in tiendas) for (d in t.dominios) putIfAbsent(d.lowercase(), t)
	}

	/** La tienda cuyo dominio coincide (igual o termina en «.» + dominio), o null si no está. */
	fun para(dominio: String): ReglasTienda? {
		var d = dominio.lowercase()
		while (true) {
			porDominio[d]?.let { return it }
			val punto = d.indexOf('.')
			if (punto < 0) return null
			d = d.substring(punto + 1)
			if (!d.contains('.')) return null
		}
	}

	/** Nombre de la tienda para un dominio: el de tiendas.json o el del dominio con la primera letra en mayúscula. */
	fun nombrePara(dominio: String): String = para(dominio)?.nombre ?: nombreTiendaPorDominio(dominio)

	companion object {
		val VACIAS = ReglasTiendas(emptyList(), emptyList())

		private fun textos(a: JSONArray?): List<String> =
			if (a == null) emptyList() else (0 until a.length()).mapNotNull { i -> if (a.isNull(i)) null else a.optString(i) }

		private fun reglas(a: JSONArray?): List<ReglaCss> {
			if (a == null) return emptyList()
			return (0 until a.length()).mapNotNull { i ->
				val o = a.optJSONObject(i) ?: return@mapNotNull null
				val css = o.optString("css").trim()
				if (css.isEmpty()) null else ReglaCss(css, o.optString("atributo").trim().ifEmpty { null })
			}
		}

		private fun reglasDisponible(a: JSONArray?): List<ReglaDisponible> {
			if (a == null) return emptyList()
			return (0 until a.length()).mapNotNull { i ->
				val o = a.optJSONObject(i) ?: return@mapNotNull null
				val css = o.optString("css").trim()
				if (css.isEmpty()) null else ReglaDisponible(css, textos(o.optJSONArray("agotado")).map { it.lowercase() })
			}
		}

		/** Lee el texto de tiendas.json. Lanza una excepción si no es JSON válido. */
		fun leer(json: String): ReglasTiendas {
			val raiz = JSONObject(json)
			val lista = raiz.optJSONArray("tiendas") ?: JSONArray()
			val tiendas = (0 until lista.length()).mapNotNull { i ->
				val o = lista.optJSONObject(i) ?: return@mapNotNull null
				ReglasTienda(
					id = o.optString("id"),
					nombre = o.optString("nombre"),
					dominios = textos(o.optJSONArray("dominios")).map { it.lowercase().trim() },
					precio = reglas(o.optJSONArray("precio")),
					titulo = reglas(o.optJSONArray("titulo")),
					imagen = reglas(o.optJSONArray("imagen")),
					disponible = reglasDisponible(o.optJSONArray("disponible")),
					bloqueo = textos(o.optJSONArray("bloqueo")),
					notas = o.optString("notas"),
					navegador = o.optBoolean("navegador", false),
					api = o.optJSONObject("api")?.let { ApiTienda.leer(it) },
				)
			}
			return ReglasTiendas(textos(raiz.optJSONArray("bloqueo_general")), tiendas)
		}
	}
}
