package com.xebolax.nomesubaslosprecios.nucleo

import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/** analizarImporte con los vectores comunes de compartido/pruebas/importes.json. */
class ImportesTest {

	@Test
	fun vectoresComunes() {
		val lista = JSONObject(Comun.leer("importes.json")).getJSONArray("importes")
		assertTrue("No hay vectores de importes", lista.length() > 0)
		val fallos = mutableListOf<String>()
		for (i in 0 until lista.length()) {
			val caso = lista.getJSONObject(i)
			val texto = caso.getString("texto")
			val esperado = if (caso.isNull("valor")) null else caso.getDouble("valor")
			val obtenido = analizarImporte(texto)
			if (esperado != obtenido) fallos += "«$texto»: se esperaba $esperado y salió $obtenido"
		}
		assertTrue("Importes que no coinciden:\n" + fallos.joinToString("\n"), fallos.isEmpty())
	}

	@Test
	fun importeDeMaquina() {
		assertEquals(1299.99, importeDeMaquina("1299.99")!!, 0.0)
		assertEquals(12.5, importeDeMaquina("12.5")!!, 0.0)
		assertEquals(1299.0, importeDeMaquina("1299")!!, 0.0)
		assertEquals(1299.0, importeDeMaquina("1.299")!!, 0.0)
		assertEquals(1299.0, importeDeMaquina("1.299,00")!!, 0.0)
		assertEquals(24.95, importeDeMaquina("24,95")!!, 0.0)
		assertNull(importeDeMaquina("0"))
		assertNull(importeDeMaquina("0.00"))
		assertNull(importeDeMaquina(""))
		assertNull(importeDeMaquina(null))
	}
}
