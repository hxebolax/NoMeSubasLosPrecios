package com.xebolax.nomesubaslosprecios.nucleo

import org.json.JSONObject

/**
 * API pública de una tienda (campo «api» de tiendas.json): dirección con el
 * identificador sacado de la URL del producto y rutas a los datos.
 * Rutas: claves separadas por puntos; un número es una posición de lista;
 * «clave[campo=valor]» elige el primer elemento de la lista con ese valor.
 */
data class ApiTienda(
	val idDesdeUrl: Regex,
	val url: String,
	val precio: List<String>,
	val nombre: List<String>,
	val imagen: List<String>,
	val disponibleRuta: String?,
	val disponibleIgual: Any?,
) {
	/** Dirección de la API para un producto, o null si el identificador no sale de su URL. */
	fun urlPara(urlProducto: String): String? {
		val id = idDesdeUrl.find(urlProducto)?.groupValues?.getOrNull(1)?.takeIf { it.isNotEmpty() } ?: return null
		return url.replace("{id}", id)
	}

	/** Lo que dice la respuesta de la API. null si no es JSON. */
	fun extraer(json: String): ResultadoExtraccion? {
		val datos = leerJson(json) ?: return null
		val precio = precio.firstNotNullOfOrNull { ruta -> valorEn(datos, ruta)?.let { if (it is String) importeDeMaquina(it) else numeroDeMaquina(it) } }
		val nombre = nombre.firstNotNullOfOrNull { ruta -> (valorEn(datos, ruta) as? String)?.trim()?.ifEmpty { null } }
		val imagen = imagen.firstNotNullOfOrNull { ruta -> (valorEn(datos, ruta) as? String)?.trim()?.ifEmpty { null } }
		val disponible = disponibleRuta?.let { ruta ->
			val v = valorEn(datos, ruta)
			if (v == null) null else v.toString() == disponibleIgual.toString()
		} ?: if (precio != null) true else null
		val error = if (precio == null && disponible != false) MensajesError.SIN_PRECIO else null
		return ResultadoExtraccion(
			precio = precio, moneda = "EUR", nombre = nombre, imagen = imagen, disponible = disponible, bloqueo = false, error = error,
			origen = if (precio != null) OrigenPrecio.API else null, parciales = emptyList(),
			confianza = if (precio != null) Confianza.ALTA else null,
		)
	}

	companion object {
		fun leer(o: JSONObject): ApiTienda? {
			val patron = o.optString("id_desde_url").ifEmpty { return null }
			val url = o.optString("url").ifEmpty { return null }
			fun lista(clave: String) = o.optJSONArray(clave)?.let { a -> (0 until a.length()).map { a.optString(it) }.filter { it.isNotEmpty() } }
				?: o.optString(clave).takeIf { it.isNotEmpty() }?.let { listOf(it) } ?: emptyList()
			val disp = o.optJSONObject("disponible")
			return try {
				ApiTienda(
					Regex(patron), url, lista("precio"), lista("nombre"), lista("imagen"),
					disp?.optString("ruta")?.ifEmpty { null }, disp?.opt("igual")?.let { aKotlin(it) },
				)
			} catch (e: IllegalArgumentException) {
				null
			}
		}

		private val FILTRO = Regex("^(.*)\\[([^=\\]]+)=([^\\]]*)]$")

		/** Valor en una ruta «a.b.0.c» o «lista[clave=valor].campo». */
		fun valorEn(datos: Any?, ruta: String): Any? {
			var actual: Any? = datos
			for (trozo in ruta.split('.')) {
				if (actual == null) return null
				val filtro = FILTRO.find(trozo)
				if (filtro != null) {
					val (clave, campo, valor) = filtro.destructured
					val lista = if (clave.isEmpty()) actual else (actual as? Map<*, *>)?.get(clave)
					actual = (lista as? List<*>)?.firstOrNull { (it as? Map<*, *>)?.get(campo)?.toString() == valor }
					continue
				}
				actual = when (actual) {
					is Map<*, *> -> actual[trozo]
					is List<*> -> trozo.toIntOrNull()?.let { actual.getOrNull(it) }
					else -> null
				}
			}
			return actual
		}
	}
}
