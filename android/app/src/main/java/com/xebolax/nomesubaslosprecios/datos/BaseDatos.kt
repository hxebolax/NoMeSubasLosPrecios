package com.xebolax.nomesubaslosprecios.datos

import android.content.ContentValues
import android.content.Context
import android.database.Cursor
import android.database.sqlite.SQLiteDatabase
import android.database.sqlite.SQLiteOpenHelper
import com.xebolax.nomesubaslosprecios.nucleo.Aviso
import com.xebolax.nomesubaslosprecios.nucleo.AvisoExportado
import com.xebolax.nomesubaslosprecios.nucleo.AvisoNuevo
import com.xebolax.nomesubaslosprecios.nucleo.Categoria
import com.xebolax.nomesubaslosprecios.nucleo.DatosIntercambio
import com.xebolax.nomesubaslosprecios.nucleo.Fechas
import com.xebolax.nomesubaslosprecios.nucleo.ModoDescarga
import com.xebolax.nomesubaslosprecios.nucleo.Producto
import com.xebolax.nomesubaslosprecios.nucleo.ProductoConNombres
import com.xebolax.nomesubaslosprecios.nucleo.ProductoExportado
import com.xebolax.nomesubaslosprecios.nucleo.PuntoHistorial
import com.xebolax.nomesubaslosprecios.nucleo.Tienda
import com.xebolax.nomesubaslosprecios.nucleo.dominioDe
import com.xebolax.nomesubaslosprecios.nucleo.limpiarUrl
import com.xebolax.nomesubaslosprecios.nucleo.nombreTiendaPorDominio
import com.xebolax.nomesubaslosprecios.nucleo.redondear
import java.util.UUID

/** Aviso con el nombre de su producto (null si se borró el producto). */
data class AvisoConProducto(val aviso: Aviso, val nombreProducto: String?)

/** Lo que hace falta para deshacer el borrado de un producto. */
data class CopiaProducto(val producto: Producto, val historial: List<PuntoHistorial>, val avisos: List<Long>)

/** Cuántos elementos tiene un archivo y qué se hará con ellos al importar. */
data class ResumenImportacion(
	val productos: Int,
	val categorias: Int,
	val tiendas: Int,
	val anadir: Int,
	val actualizar: Int,
	val noValidos: Int,
)

enum class ModoImportacion { COMBINAR, REEMPLAZAR }

/**
 * Base de datos SQLite con exactamente las tablas y columnas de
 * ESPECIFICACION.md (las mismas que la app de Windows), con las claves
 * foráneas activadas. Todo se llama desde Dispatchers.IO.
 */
class BaseDatos private constructor(contexto: Context) : SQLiteOpenHelper(contexto, NOMBRE, null, VERSION) {

	companion object {
		const val NOMBRE = "nomesubaslosprecios.db"
		const val VERSION = 2

		@Volatile
		private var unica: BaseDatos? = null

		fun obtener(contexto: Context): BaseDatos =
			unica ?: synchronized(this) { unica ?: BaseDatos(contexto.applicationContext).also { unica = it } }

		fun nuevoUuid(): String = UUID.randomUUID().toString()

		private const val COLUMNAS_PRODUCTO = "p.id, p.uuid, p.nombre, p.url, p.tienda_id, p.categoria_id, p.grupo, p.moneda, p.precio_actual, " +
			"p.disponible, p.precio_inicial, p.precio_minimo, p.fecha_minimo, p.precio_maximo, p.fecha_maximo, p.precio_anterior, " +
			"p.fecha_cambio, p.precio_objetivo, p.alerta_porcentaje, p.avisar_disponible, p.selector_precio, p.imagen_url, p.notas, " +
			"p.favorito, p.activo, p.fecha_alta, p.ultima_comprobacion, p.ultimo_error, p.errores_seguidos, " +
			"p.variante, p.origen_precio, p.confianza, p.huella_selector, p.desde"

		/** Columnas que añade la migración 2 (extracción ampliada). */
		private val MIGRACION_2 = listOf(
			"ALTER TABLE productos ADD COLUMN variante TEXT",
			"ALTER TABLE productos ADD COLUMN origen_precio TEXT",
			"ALTER TABLE productos ADD COLUMN confianza TEXT",
			"ALTER TABLE productos ADD COLUMN huella_selector TEXT",
			"ALTER TABLE productos ADD COLUMN desde INTEGER DEFAULT 0",
			"ALTER TABLE tiendas ADD COLUMN modo_descarga TEXT DEFAULT 'auto'",
		)
	}

	override fun onConfigure(db: SQLiteDatabase) {
		super.onConfigure(db)
		db.setForeignKeyConstraintsEnabled(true)
	}

	override fun onCreate(db: SQLiteDatabase) {
		db.execSQL(
			"""CREATE TABLE categorias (
				id INTEGER PRIMARY KEY,
				uuid TEXT UNIQUE NOT NULL,
				nombre TEXT NOT NULL,
				descripcion TEXT,
				orden INTEGER
			)""",
		)
		db.execSQL("CREATE UNIQUE INDEX categorias_nombre ON categorias(nombre COLLATE NOCASE)")
		db.execSQL(
			"""CREATE TABLE tiendas (
				id INTEGER PRIMARY KEY,
				uuid TEXT UNIQUE NOT NULL,
				nombre TEXT NOT NULL,
				dominio TEXT UNIQUE NOT NULL,
				selector_precio TEXT,
				selector_titulo TEXT,
				selector_disponible TEXT,
				notas TEXT
			)""",
		)
		db.execSQL(
			"""CREATE TABLE productos (
				id INTEGER PRIMARY KEY,
				uuid TEXT UNIQUE NOT NULL,
				nombre TEXT NOT NULL,
				url TEXT NOT NULL,
				tienda_id INTEGER REFERENCES tiendas(id),
				categoria_id INTEGER NULL REFERENCES categorias(id) ON DELETE SET NULL,
				grupo TEXT,
				moneda TEXT DEFAULT 'EUR',
				precio_actual REAL NULL,
				disponible INTEGER DEFAULT 1,
				precio_inicial REAL NULL,
				precio_minimo REAL NULL,
				fecha_minimo TEXT,
				precio_maximo REAL NULL,
				fecha_maximo TEXT,
				precio_anterior REAL NULL,
				fecha_cambio TEXT,
				precio_objetivo REAL NULL,
				alerta_porcentaje REAL DEFAULT 0,
				avisar_disponible INTEGER DEFAULT 1,
				selector_precio TEXT,
				imagen_url TEXT,
				notas TEXT,
				favorito INTEGER DEFAULT 0,
				activo INTEGER DEFAULT 1,
				fecha_alta TEXT,
				ultima_comprobacion TEXT,
				ultimo_error TEXT,
				errores_seguidos INTEGER DEFAULT 0
			)""",
		)
		db.execSQL("CREATE INDEX productos_url ON productos(url)")
		db.execSQL(
			"""CREATE TABLE historial (
				id INTEGER PRIMARY KEY,
				producto_id INTEGER NOT NULL REFERENCES productos(id) ON DELETE CASCADE,
				fecha TEXT NOT NULL,
				precio REAL NULL,
				disponible INTEGER
			)""",
		)
		db.execSQL("CREATE UNIQUE INDEX historial_producto_fecha ON historial(producto_id, fecha)")
		db.execSQL(
			"""CREATE TABLE avisos (
				id INTEGER PRIMARY KEY,
				producto_id INTEGER NULL REFERENCES productos(id) ON DELETE SET NULL,
				fecha TEXT,
				tipo TEXT,
				titulo TEXT,
				mensaje TEXT,
				leido INTEGER DEFAULT 0
			)""",
		)
		db.execSQL("CREATE INDEX avisos_fecha ON avisos(fecha)")
		// La versión 2 se crea igual que se migra: así las dos rutas dan el mismo esquema
		MIGRACION_2.forEach { db.execSQL(it) }
	}

	/** Migraciones por versión: cada paso lleva de la versión v a la v + 1. */
	override fun onUpgrade(db: SQLiteDatabase, anterior: Int, nueva: Int) {
		for (v in anterior until nueva) {
			when (v) {
				1 -> MIGRACION_2.forEach { db.execSQL(it) }
				else -> Unit
			}
		}
	}

	// --- Ayudantes de cursores --------------------------------------------------------------

	private fun Cursor.texto(i: Int): String? = if (isNull(i)) null else getString(i)
	private fun Cursor.real(i: Int): Double? = if (isNull(i)) null else getDouble(i)
	private fun Cursor.largo(i: Int): Long? = if (isNull(i)) null else getLong(i)
	private fun Cursor.bool(i: Int, porDefecto: Boolean): Boolean = if (isNull(i)) porDefecto else getInt(i) != 0

	private inline fun <T> consulta(sql: String, vararg args: String, fila: (Cursor) -> T): List<T> =
		readableDatabase.rawQuery(sql, args).use { c ->
			val lista = ArrayList<T>(c.count)
			while (c.moveToNext()) lista += fila(c)
			lista
		}

	private fun producto(c: Cursor, o: Int = 0) = Producto(
		id = c.getLong(o), uuid = c.getString(o + 1), nombre = c.texto(o + 2).orEmpty(), url = c.texto(o + 3).orEmpty(),
		tiendaId = c.largo(o + 4), categoriaId = c.largo(o + 5), grupo = c.texto(o + 6), moneda = c.texto(o + 7) ?: "EUR",
		precioActual = c.real(o + 8), disponible = c.bool(o + 9, true), precioInicial = c.real(o + 10), precioMinimo = c.real(o + 11),
		fechaMinimo = c.texto(o + 12), precioMaximo = c.real(o + 13), fechaMaximo = c.texto(o + 14), precioAnterior = c.real(o + 15),
		fechaCambio = c.texto(o + 16), precioObjetivo = c.real(o + 17), alertaPorcentaje = c.real(o + 18) ?: 0.0,
		avisarDisponible = c.bool(o + 19, true), selectorPrecio = c.texto(o + 20), imagenUrl = c.texto(o + 21), notas = c.texto(o + 22),
		favorito = c.bool(o + 23, false), activo = c.bool(o + 24, true), fechaAlta = c.texto(o + 25), ultimaComprobacion = c.texto(o + 26),
		ultimoError = c.texto(o + 27), erroresSeguidos = c.largo(o + 28)?.toInt() ?: 0,
		variante = c.texto(o + 29), origenPrecio = c.texto(o + 30), confianza = c.texto(o + 31), huellaSelector = c.texto(o + 32),
		desde = c.bool(o + 33, false),
	)

	private fun valores(p: Producto, conId: Boolean = false) = ContentValues().apply {
		if (conId && p.id > 0) put("id", p.id)
		put("uuid", p.uuid)
		put("nombre", p.nombre)
		put("url", p.url)
		put("tienda_id", p.tiendaId)
		put("categoria_id", p.categoriaId)
		put("grupo", p.grupo?.trim()?.ifEmpty { null })
		put("moneda", p.moneda)
		put("precio_actual", p.precioActual?.let { redondear(it) })
		put("disponible", if (p.disponible) 1 else 0)
		put("precio_inicial", p.precioInicial?.let { redondear(it) })
		put("precio_minimo", p.precioMinimo?.let { redondear(it) })
		put("fecha_minimo", p.fechaMinimo)
		put("precio_maximo", p.precioMaximo?.let { redondear(it) })
		put("fecha_maximo", p.fechaMaximo)
		put("precio_anterior", p.precioAnterior?.let { redondear(it) })
		put("fecha_cambio", p.fechaCambio)
		put("precio_objetivo", p.precioObjetivo?.let { redondear(it) })
		put("alerta_porcentaje", p.alertaPorcentaje)
		put("avisar_disponible", if (p.avisarDisponible) 1 else 0)
		put("selector_precio", p.selectorPrecio?.trim()?.ifEmpty { null })
		put("imagen_url", p.imagenUrl)
		put("notas", p.notas?.trim()?.ifEmpty { null })
		put("favorito", if (p.favorito) 1 else 0)
		put("activo", if (p.activo) 1 else 0)
		put("fecha_alta", p.fechaAlta)
		put("ultima_comprobacion", p.ultimaComprobacion)
		put("ultimo_error", p.ultimoError)
		put("errores_seguidos", p.erroresSeguidos)
		put("variante", p.variante?.ifEmpty { null })
		put("origen_precio", p.origenPrecio)
		put("confianza", p.confianza)
		put("huella_selector", p.huellaSelector)
		put("desde", if (p.desde) 1 else 0)
	}

	private fun categoria(c: Cursor) = Categoria(c.getLong(0), c.getString(1), c.texto(2).orEmpty(), c.texto(3), c.largo(4)?.toInt() ?: 0)

	private fun tienda(c: Cursor) = Tienda(
		c.getLong(0), c.getString(1), c.texto(2).orEmpty(), c.texto(3).orEmpty(), c.texto(4), c.texto(5), c.texto(6), c.texto(7),
		c.texto(8)?.takeIf { it in ModoDescarga.TODOS } ?: ModoDescarga.AUTO,
	)

	private fun valores(t: Tienda) = ContentValues().apply {
		put("uuid", t.uuid)
		put("nombre", t.nombre)
		put("dominio", t.dominio)
		put("selector_precio", t.selectorPrecio?.trim()?.ifEmpty { null })
		put("selector_titulo", t.selectorTitulo?.trim()?.ifEmpty { null })
		put("selector_disponible", t.selectorDisponible?.trim()?.ifEmpty { null })
		put("notas", t.notas?.trim()?.ifEmpty { null })
		put("modo_descarga", t.modoDescarga)
	}

	// --- Categorías -----------------------------------------------------------------------------

	fun categorias(): List<Categoria> =
		consulta("SELECT id, uuid, nombre, descripcion, orden FROM categorias ORDER BY orden, nombre COLLATE NOCASE") { categoria(it) }

	fun categoria(id: Long): Categoria? =
		consulta("SELECT id, uuid, nombre, descripcion, orden FROM categorias WHERE id = ?", id.toString()) { categoria(it) }.firstOrNull()

	private fun categoriaPorNombre(db: SQLiteDatabase, nombre: String): Categoria? =
		db.rawQuery("SELECT id, uuid, nombre, descripcion, orden FROM categorias", null).use { c ->
			while (c.moveToNext()) if (c.getString(2).equals(nombre, ignoreCase = true)) return categoria(c)
			null
		}

	fun existeCategoria(nombre: String, salvo: Long = 0): Boolean = categoriaPorNombre(readableDatabase, nombre.trim())?.let { it.id != salvo } ?: false

	/** Crea una categoría al final del orden. Devuelve su id (o el de la que ya tenía ese nombre). */
	fun crearCategoria(nombre: String, descripcion: String? = null): Long {
		val db = writableDatabase
		categoriaPorNombre(db, nombre.trim())?.let { return it.id }
		val orden = db.rawQuery("SELECT COALESCE(MAX(orden), -1) + 1 FROM categorias", null).use { if (it.moveToFirst()) it.getInt(0) else 0 }
		return db.insertOrThrow("categorias", null, ContentValues().apply {
			put("uuid", nuevoUuid())
			put("nombre", nombre.trim())
			put("descripcion", descripcion?.trim()?.ifEmpty { null })
			put("orden", orden)
		})
	}

	fun renombrarCategoria(id: Long, nombre: String, descripcion: String?) {
		writableDatabase.update("categorias", ContentValues().apply {
			put("nombre", nombre.trim())
			put("descripcion", descripcion?.trim()?.ifEmpty { null })
		}, "id = ?", arrayOf(id.toString()))
	}

	/** Borra la categoría: sus productos pasan a «Sin categoría» (ON DELETE SET NULL). */
	fun borrarCategoria(id: Long) {
		writableDatabase.delete("categorias", "id = ?", arrayOf(id.toString()))
	}

	/** Sube (-1) o baja (+1) una categoría en el orden; deja el orden numerado de 0 en adelante. */
	fun moverCategoria(id: Long, paso: Int) {
		val db = writableDatabase
		db.beginTransaction()
		try {
			val lista = categorias().toMutableList()
			val i = lista.indexOfFirst { it.id == id }
			val j = i + paso
			if (i >= 0 && j in lista.indices) {
				val c = lista.removeAt(i)
				lista.add(j, c)
			}
			lista.forEachIndexed { orden, c -> db.update("categorias", ContentValues().apply { put("orden", orden) }, "id = ?", arrayOf(c.id.toString())) }
			db.setTransactionSuccessful()
		} finally {
			db.endTransaction()
		}
	}

	/** Número de productos por categoría (la clave null es «Sin categoría»). */
	fun productosPorCategoria(): Map<Long?, Int> =
		consulta("SELECT categoria_id, COUNT(*) FROM productos GROUP BY categoria_id") { c -> c.largo(0) to c.getInt(1) }.toMap()

	// --- Tiendas -----------------------------------------------------------------------------------

	fun tiendas(): List<Tienda> =
		consulta("SELECT id, uuid, nombre, dominio, selector_precio, selector_titulo, selector_disponible, notas, modo_descarga FROM tiendas ORDER BY nombre COLLATE NOCASE") { tienda(it) }

	fun tienda(id: Long): Tienda? =
		consulta("SELECT id, uuid, nombre, dominio, selector_precio, selector_titulo, selector_disponible, notas, modo_descarga FROM tiendas WHERE id = ?", id.toString()) { tienda(it) }.firstOrNull()

	fun tiendaPorDominio(dominio: String): Tienda? =
		consulta("SELECT id, uuid, nombre, dominio, selector_precio, selector_titulo, selector_disponible, notas, modo_descarga FROM tiendas WHERE dominio = ?", dominio) { tienda(it) }.firstOrNull()

	/** La tienda del dominio; si no existe, se crea con el nombre de tiendas.json o del dominio. */
	fun tiendaParaDominio(dominio: String, nombre: String = nombreTiendaPorDominio(dominio)): Tienda {
		tiendaPorDominio(dominio)?.let { return it }
		val t = Tienda(uuid = nuevoUuid(), nombre = nombre, dominio = dominio)
		val id = writableDatabase.insertWithOnConflict("tiendas", null, valores(t), SQLiteDatabase.CONFLICT_IGNORE)
		return if (id > 0) t.copy(id = id) else tiendaPorDominio(dominio) ?: t
	}

	fun actualizarTienda(t: Tienda) {
		writableDatabase.update("tiendas", valores(t), "id = ?", arrayOf(t.id.toString()))
	}

	/** Borra la tienda solo si no tiene productos. Devuelve si se borró. */
	fun borrarTienda(id: Long): Boolean {
		if ((productosPorTienda()[id] ?: 0) > 0) return false
		return writableDatabase.delete("tiendas", "id = ?", arrayOf(id.toString())) > 0
	}

	fun productosPorTienda(): Map<Long, Int> =
		consulta("SELECT tienda_id, COUNT(*) FROM productos WHERE tienda_id IS NOT NULL GROUP BY tienda_id") { c -> c.getLong(0) to c.getInt(1) }.toMap()

	// --- Productos ---------------------------------------------------------------------------------

	/** Todos los productos con el nombre de su tienda y su categoría. */
	fun productos(): List<ProductoConNombres> = consulta(
		"SELECT $COLUMNAS_PRODUCTO, t.nombre, t.dominio, c.nombre FROM productos p " +
			"LEFT JOIN tiendas t ON t.id = p.tienda_id LEFT JOIN categorias c ON c.id = p.categoria_id",
	) { c -> ProductoConNombres(producto(c), c.texto(34) ?: c.texto(35) ?: dominioDe(c.getString(3)), c.texto(36)) }

	fun producto(id: Long): Producto? =
		consulta("SELECT $COLUMNAS_PRODUCTO FROM productos p WHERE p.id = ?", id.toString()) { producto(it) }.firstOrNull()

	fun productoConNombres(id: Long): ProductoConNombres? = consulta(
		"SELECT $COLUMNAS_PRODUCTO, t.nombre, t.dominio, c.nombre FROM productos p " +
			"LEFT JOIN tiendas t ON t.id = p.tienda_id LEFT JOIN categorias c ON c.id = p.categoria_id WHERE p.id = ?",
		id.toString(),
	) { c -> ProductoConNombres(producto(c), c.texto(34) ?: c.texto(35) ?: dominioDe(c.getString(3)), c.texto(36)) }.firstOrNull()

	fun productoPorUrl(url: String): Producto? =
		consulta("SELECT $COLUMNAS_PRODUCTO FROM productos p WHERE p.url = ?", url) { producto(it) }.firstOrNull()

	fun cuantosProductos(): Int = readableDatabase.rawQuery("SELECT COUNT(*) FROM productos", null).use { if (it.moveToFirst()) it.getInt(0) else 0 }

	/** Inserta un producto nuevo y devuelve su id. */
	fun crearProducto(p: Producto): Long = writableDatabase.insertOrThrow("productos", null, valores(p))

	fun actualizarProducto(p: Producto) {
		writableDatabase.update("productos", valores(p), "id = ?", arrayOf(p.id.toString()))
	}

	fun historial(productoId: Long): List<PuntoHistorial> =
		consulta("SELECT fecha, precio, disponible FROM historial WHERE producto_id = ? ORDER BY fecha", productoId.toString()) { c ->
			PuntoHistorial(c.getString(0), c.real(1), c.bool(2, true))
		}

	/**
	 * Guarda el resultado de una comprobación en una transacción: el producto,
	 * la fila de historial y los avisos. Devuelve los avisos guardados con su id.
	 */
	fun guardarComprobacion(p: Producto, fila: PuntoHistorial?, avisos: List<AvisoNuevo>): List<Aviso> {
		val db = writableDatabase
		db.beginTransaction()
		try {
			db.update("productos", valores(p), "id = ?", arrayOf(p.id.toString()))
			fila?.let { anadirHistorial(db, p.id, it, SQLiteDatabase.CONFLICT_REPLACE) }
			val guardados = avisos.map { a ->
				val aviso = Aviso(productoId = p.id, fecha = p.ultimaComprobacion ?: Fechas.ahora(), tipo = a.tipo, titulo = a.titulo, mensaje = a.mensaje)
				aviso.copy(id = anadirAviso(db, aviso))
			}
			db.setTransactionSuccessful()
			return guardados
		} finally {
			db.endTransaction()
		}
	}

	private fun anadirHistorial(db: SQLiteDatabase, productoId: Long, h: PuntoHistorial, conflicto: Int) {
		db.insertWithOnConflict("historial", null, ContentValues().apply {
			put("producto_id", productoId)
			put("fecha", h.fecha)
			put("precio", h.precio?.let { redondear(it) })
			put("disponible", if (h.disponible) 1 else 0)
		}, conflicto)
	}

	/** Borra un producto y devuelve lo necesario para deshacerlo. */
	fun eliminarProducto(id: Long): CopiaProducto? {
		val db = writableDatabase
		db.beginTransaction()
		try {
			val p = producto(id) ?: return null
			val copia = CopiaProducto(
				p, historial(id),
				consulta("SELECT id FROM avisos WHERE producto_id = ?", id.toString()) { it.getLong(0) },
			)
			db.delete("productos", "id = ?", arrayOf(id.toString()))
			db.setTransactionSuccessful()
			return copia
		} finally {
			db.endTransaction()
		}
	}

	/** Deshace el borrado: el producto con su mismo id, su historial y sus avisos. */
	fun restaurar(copia: CopiaProducto) {
		val db = writableDatabase
		db.beginTransaction()
		try {
			db.insertWithOnConflict("productos", null, valores(copia.producto, conId = true), SQLiteDatabase.CONFLICT_REPLACE)
			copia.historial.forEach { anadirHistorial(db, copia.producto.id, it, SQLiteDatabase.CONFLICT_IGNORE) }
			copia.avisos.forEach { db.update("avisos", ContentValues().apply { put("producto_id", copia.producto.id) }, "id = ?", arrayOf(it.toString())) }
			db.setTransactionSuccessful()
		} finally {
			db.endTransaction()
		}
	}

	// --- Avisos ----------------------------------------------------------------------------------------

	private fun anadirAviso(db: SQLiteDatabase, a: Aviso): Long = db.insertOrThrow("avisos", null, ContentValues().apply {
		put("producto_id", a.productoId)
		put("fecha", a.fecha)
		put("tipo", a.tipo)
		put("titulo", a.titulo)
		put("mensaje", a.mensaje)
		put("leido", if (a.leido) 1 else 0)
	})

	/** Los avisos: los no leídos primero y, dentro, del más nuevo al más viejo. */
	fun avisos(): List<AvisoConProducto> = consulta(
		"SELECT a.id, a.producto_id, a.fecha, a.tipo, a.titulo, a.mensaje, a.leido, p.nombre FROM avisos a " +
			"LEFT JOIN productos p ON p.id = a.producto_id ORDER BY a.leido, a.fecha DESC, a.id DESC",
	) { c ->
		AvisoConProducto(
			Aviso(c.getLong(0), c.largo(1), c.texto(2).orEmpty(), c.texto(3).orEmpty(), c.texto(4).orEmpty(), c.texto(5).orEmpty(), c.bool(6, false)),
			c.texto(7),
		)
	}

	fun avisosSinLeer(): Int = readableDatabase.rawQuery("SELECT COUNT(*) FROM avisos WHERE leido = 0", null).use { if (it.moveToFirst()) it.getInt(0) else 0 }

	fun marcarAviso(id: Long, leido: Boolean) {
		writableDatabase.update("avisos", ContentValues().apply { put("leido", if (leido) 1 else 0) }, "id = ?", arrayOf(id.toString()))
	}

	fun marcarTodosLeidos() {
		writableDatabase.execSQL("UPDATE avisos SET leido = 1 WHERE leido = 0")
	}

	fun borrarAviso(id: Long) {
		writableDatabase.delete("avisos", "id = ?", arrayOf(id.toString()))
	}

	fun borrarAvisos() {
		writableDatabase.delete("avisos", null, null)
	}

	/** Borra los avisos de más de «dias» días (0 = se guardan siempre). */
	fun purgarAvisos(dias: Int) {
		if (dias <= 0) return
		val limite = Fechas.iso(System.currentTimeMillis() - dias * 24L * 60 * 60 * 1000)
		writableDatabase.delete("avisos", "fecha < ?", arrayOf(limite))
	}

	// --- Exportar e importar --------------------------------------------------------------------------

	/** Todo para el archivo de intercambio (sin ajustes: los añade quien exporta si se piden). */
	fun exportar(): DatosIntercambio {
		val categorias = categorias()
		val tiendas = tiendas()
		val uuidCategoria = categorias.associate { it.id to it.uuid }
		val uuidTienda = tiendas.associate { it.id to it.uuid }
		val productos = consulta("SELECT $COLUMNAS_PRODUCTO FROM productos p ORDER BY p.id") { producto(it) }
		val uuidProducto = productos.associate { it.id to it.uuid }
		return DatosIntercambio(
			categorias = categorias.map { it.copy(id = 0) },
			tiendas = tiendas.map { it.copy(id = 0) },
			productos = productos.map { p ->
				ProductoExportado(p.copy(id = 0, tiendaId = null, categoriaId = null), p.tiendaId?.let { uuidTienda[it] }, p.categoriaId?.let { uuidCategoria[it] }, historial(p.id))
			},
			avisos = avisos().map { a -> AvisoExportado(a.aviso.productoId?.let { uuidProducto[it] }, a.aviso.copy(id = 0, productoId = null)) },
		)
	}

	private fun productoExistente(db: SQLiteDatabase, uuid: String, url: String): Producto? =
		db.rawQuery("SELECT $COLUMNAS_PRODUCTO FROM productos p WHERE p.uuid = ?", arrayOf(uuid)).use { if (it.moveToFirst()) producto(it) else null }
			?: db.rawQuery("SELECT $COLUMNAS_PRODUCTO FROM productos p WHERE p.url = ?", arrayOf(limpiarUrl(url))).use { if (it.moveToFirst()) producto(it) else null }

	/** Lo que se haría al importar (para el resumen previo). */
	fun simularImportacion(d: DatosIntercambio, modo: ModoImportacion): ResumenImportacion {
		val db = readableDatabase
		val existentes = if (modo == ModoImportacion.REEMPLAZAR) 0 else d.productos.count { productoExistente(db, it.producto.uuid, it.producto.url) != null }
		return ResumenImportacion(d.productos.size, d.categorias.size, d.tiendas.size, d.productos.size - existentes, existentes, d.noValidos)
	}

	/**
	 * Importa un archivo en una sola transacción: si algo falla no cambia nada.
	 * Combinar: se busca por uuid (o URL, dominio y nombre) y gana el dato más
	 * reciente en los precios; lo del usuario se toma del archivo. Reemplazar:
	 * se borra todo y se carga el archivo.
	 */
	fun importar(d: DatosIntercambio, modo: ModoImportacion): ResumenImportacion {
		val db = writableDatabase
		val resumen = simularImportacion(d, modo)
		db.beginTransaction()
		try {
			if (modo == ModoImportacion.REEMPLAZAR) {
				db.delete("avisos", null, null)
				db.delete("historial", null, null)
				db.delete("productos", null, null)
				db.delete("categorias", null, null)
				db.delete("tiendas", null, null)
			}
			// Categorías: por uuid y, si no, por nombre
			val idCategoria = HashMap<String, Long>()
			for (c in d.categorias) {
				val existente = db.rawQuery("SELECT id FROM categorias WHERE uuid = ?", arrayOf(c.uuid)).use { if (it.moveToFirst()) it.getLong(0) else null }
					?: categoriaPorNombre(db, c.nombre)?.id
				val v = ContentValues().apply {
					put("nombre", c.nombre)
					put("descripcion", c.descripcion)
					put("orden", c.orden)
				}
				if (existente != null) {
					// Si otro ya tiene ese nombre, se conserva el nombre de aquí para no romper la unicidad
					if (categoriaPorNombre(db, c.nombre)?.let { it.id != existente } == true) v.remove("nombre")
					db.update("categorias", v, "id = ?", arrayOf(existente.toString()))
					idCategoria[c.uuid] = existente
				} else {
					v.put("uuid", c.uuid)
					idCategoria[c.uuid] = db.insertOrThrow("categorias", null, v)
				}
			}
			// Tiendas: por uuid y, si no, por dominio
			val idTienda = HashMap<String, Long>()
			for (t in d.tiendas) {
				val existente = db.rawQuery("SELECT id FROM tiendas WHERE uuid = ?", arrayOf(t.uuid)).use { if (it.moveToFirst()) it.getLong(0) else null }
					?: db.rawQuery("SELECT id FROM tiendas WHERE dominio = ?", arrayOf(t.dominio)).use { if (it.moveToFirst()) it.getLong(0) else null }
				if (existente != null) {
					val v = valores(t).apply {
						remove("uuid")
						if (db.rawQuery("SELECT id FROM tiendas WHERE dominio = ? AND id <> ?", arrayOf(t.dominio, existente.toString())).use { it.count > 0 }) remove("dominio")
					}
					db.update("tiendas", v, "id = ?", arrayOf(existente.toString()))
					idTienda[t.uuid] = existente
				} else {
					idTienda[t.uuid] = db.insertOrThrow("tiendas", null, valores(t))
				}
			}
			// Productos
			val idProducto = HashMap<String, Long>()
			for (e in d.productos) {
				val archivo = e.producto.copy(url = limpiarUrl(e.producto.url))
				val tiendaId = e.tiendaUuid?.let { idTienda[it] } ?: run {
					// Tienda que no está en la lista: la de su dominio, creándola si hace falta
					val dominio = dominioDe(archivo.url)
					db.rawQuery("SELECT id FROM tiendas WHERE dominio = ?", arrayOf(dominio)).use { if (it.moveToFirst()) it.getLong(0) else null }
						?: db.insertOrThrow("tiendas", null, valores(Tienda(uuid = nuevoUuid(), nombre = nombreTiendaPorDominio(dominio), dominio = dominio)))
				}
				val categoriaId = e.categoriaUuid?.let { idCategoria[it] }
				val local = if (modo == ModoImportacion.COMBINAR) productoExistente(db, archivo.uuid, archivo.url) else null
				val id: Long
				if (local == null) {
					id = db.insertOrThrow("productos", null, valores(archivo.copy(id = 0, tiendaId = tiendaId, categoriaId = categoriaId)))
				} else {
					// Lo del usuario, del archivo; los precios, del que se comprobó más tarde
					val archivoMasNuevo = (Fechas.ms(archivo.ultimaComprobacion) ?: 0L) > (Fechas.ms(local.ultimaComprobacion) ?: 0L)
					val precios = if (archivoMasNuevo) archivo else local
					val combinado = local.copy(
						nombre = archivo.nombre.ifBlank { local.nombre },
						categoriaId = categoriaId,
						grupo = archivo.grupo,
						precioObjetivo = archivo.precioObjetivo,
						alertaPorcentaje = archivo.alertaPorcentaje,
						avisarDisponible = archivo.avisarDisponible,
						selectorPrecio = archivo.selectorPrecio,
						variante = archivo.variante,
						huellaSelector = archivo.huellaSelector,
						origenPrecio = precios.origenPrecio,
						confianza = precios.confianza,
						desde = precios.desde,
						notas = archivo.notas,
						favorito = archivo.favorito,
						activo = archivo.activo,
						tiendaId = tiendaId,
						moneda = precios.moneda,
						precioActual = precios.precioActual,
						disponible = precios.disponible,
						precioInicial = precios.precioInicial ?: local.precioInicial,
						precioMinimo = precios.precioMinimo,
						fechaMinimo = precios.fechaMinimo,
						precioMaximo = precios.precioMaximo,
						fechaMaximo = precios.fechaMaximo,
						precioAnterior = precios.precioAnterior,
						fechaCambio = precios.fechaCambio,
						imagenUrl = precios.imagenUrl ?: local.imagenUrl,
						ultimaComprobacion = precios.ultimaComprobacion,
						ultimoError = precios.ultimoError,
						erroresSeguidos = precios.erroresSeguidos,
						fechaAlta = listOfNotNull(local.fechaAlta, archivo.fechaAlta).minOrNull(),
					)
					db.update("productos", valores(combinado), "id = ?", arrayOf(local.id.toString()))
					id = local.id
				}
				idProducto[e.producto.uuid] = id
				// El historial se une sin duplicar (por fecha)
				e.historial.forEach { anadirHistorial(db, id, it, SQLiteDatabase.CONFLICT_IGNORE) }
			}
			// Avisos: sin duplicar (mismo producto, fecha y tipo)
			for (a in d.avisos) {
				val productoId = a.productoUuid?.let { idProducto[it] }
					?: a.productoUuid?.let { u -> db.rawQuery("SELECT id FROM productos WHERE uuid = ?", arrayOf(u)).use { if (it.moveToFirst()) it.getLong(0) else null } }
				val repetido = db.rawQuery(
					"SELECT id FROM avisos WHERE fecha = ? AND tipo = ? AND mensaje = ?",
					arrayOf(a.aviso.fecha, a.aviso.tipo, a.aviso.mensaje),
				).use { it.count > 0 }
				if (!repetido) anadirAviso(db, a.aviso.copy(productoId = productoId))
			}
			db.setTransactionSuccessful()
			return resumen
		} finally {
			db.endTransaction()
		}
	}
}
