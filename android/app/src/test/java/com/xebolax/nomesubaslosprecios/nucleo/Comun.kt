package com.xebolax.nomesubaslosprecios.nucleo

import java.io.File

/** Carpetas comunes con la app de Windows: compartido/pruebas y compartido/recursos. */
object Comun {

	private fun carpeta(propiedad: String, relativa: String): File {
		System.getProperty(propiedad)?.let { File(it) }?.takeIf { it.isDirectory }?.let { return it }
		// Sin la propiedad de Gradle: relativa al módulo (android/app)
		return File(System.getProperty("user.dir"), relativa).canonicalFile
	}

	val pruebas: File by lazy { carpeta("pruebas.dir", "../../compartido/pruebas") }
	val recursos: File by lazy { carpeta("recursos.dir", "../../compartido/recursos") }

	fun leer(nombre: String): String = File(pruebas, nombre).readText(Charsets.UTF_8)

	val reglas: ReglasTiendas by lazy { ReglasTiendas.leer(File(recursos, "tiendas.json").readText(Charsets.UTF_8)) }
}
