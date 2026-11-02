package com.xebolax.nomesubaslosprecios.ui

import android.content.Intent
import android.os.Bundle
import android.view.Menu
import android.view.MenuItem
import android.view.View
import android.view.accessibility.AccessibilityNodeInfo
import androidx.activity.OnBackPressedCallback
import androidx.activity.enableEdgeToEdge
import androidx.appcompat.app.AppCompatActivity
import androidx.appcompat.widget.SearchView
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import androidx.core.view.isVisible
import androidx.core.view.updatePadding
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.lifecycleScope
import androidx.lifecycle.repeatOnLifecycle
import androidx.recyclerview.widget.LinearLayoutManager
import com.google.android.material.dialog.MaterialAlertDialogBuilder
import com.xebolax.nomesubaslosprecios.BuildConfig
import com.xebolax.nomesubaslosprecios.R
import com.xebolax.nomesubaslosprecios.accesibilidad.Accion
import com.xebolax.nomesubaslosprecios.accesibilidad.ZonaAcciones
import com.xebolax.nomesubaslosprecios.accesibilidad.avisar
import com.xebolax.nomesubaslosprecios.accesibilidad.configurarBarra
import com.xebolax.nomesubaslosprecios.accesibilidad.confirmar
import com.xebolax.nomesubaslosprecios.accesibilidad.elegirUno
import com.xebolax.nomesubaslosprecios.accesibilidad.ponerMenuLateral
import com.xebolax.nomesubaslosprecios.accesibilidad.sinFocoPropio
import com.xebolax.nomesubaslosprecios.actualizaciones.GestorActualizaciones
import com.xebolax.nomesubaslosprecios.databinding.ActivityPrincipalBinding
import com.xebolax.nomesubaslosprecios.datos.AvisoConProducto
import com.xebolax.nomesubaslosprecios.datos.BaseDatos
import com.xebolax.nomesubaslosprecios.datos.Preferencias
import com.xebolax.nomesubaslosprecios.nucleo.Categoria
import com.xebolax.nomesubaslosprecios.nucleo.Fechas
import com.xebolax.nomesubaslosprecios.nucleo.Ofertas
import com.xebolax.nomesubaslosprecios.nucleo.ProductoConNombres
import com.xebolax.nomesubaslosprecios.nucleo.Tienda
import com.xebolax.nomesubaslosprecios.nucleo.formatearImporte
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.text.Collator
import java.util.Locale

/**
 * Pantalla principal: las 7 secciones de la especificación en el menú lateral
 * (destinos) y, tras el divisor, las acciones generales. La barra dice la
 * sección; la lista es de una sola parada por fila; «Añadir producto» abajo.
 */
class PrincipalActivity : AppCompatActivity() {

	companion object {
		private const val ESTADO_SECCION = "seccion"
		private const val ESTADO_GRUPO_TIPO = "grupo_tipo"
		private const val ESTADO_GRUPO_CLAVE = "grupo_clave"
		private const val ESTADO_GRUPO_TITULO = "grupo_titulo"
		private const val ESTADO_BUSQUEDA = "busqueda"
		private const val ESTADO_TEXTO = "texto_estado"

		/** Clave del grupo «Sin categoría» (no es una fila de la tabla). */
		private const val SIN_CATEGORIA = -1L
	}

	/** Un grupo abierto dentro de Categorías, Tiendas o Comparar. */
	private data class Grupo(val tipo: Int, val clave: String, val titulo: String)

	private lateinit var b: ActivityPrincipalBinding
	val actualizaciones = GestorActualizaciones(this)
	private val adaptador = AdaptadorFilas()
	private lateinit var acciones: AccionesProducto
	private var seccion = R.id.destino_todos
	private var grupo: Grupo? = null
	private var busqueda = ""
	private val prefs by lazy { Preferencias(this) }
	private val coteja: Collator = Collator.getInstance(Locale("es", "ES")).apply { strength = Collator.PRIMARY }
	private var menu: Menu? = null

	/** Atrás con un grupo abierto vuelve a la lista de grupos. */
	private val atras = object : OnBackPressedCallback(false) {
		override fun handleOnBackPressed() {
			val cerrado = grupo ?: return
			grupo = null
			actualizarAtras()
			cargar(foco = grupoId(cerrado))
		}
	}

	override fun onCreate(estado: Bundle?) {
		enableEdgeToEdge()
		super.onCreate(estado)
		b = ActivityPrincipalBinding.inflate(layoutInflater)
		onBackPressedDispatcher.addCallback(this, atras)
		configurarBarra(b.barra, getString(R.string.seccion_todos), conArriba = false)
		setContentView(ponerMenuLateral(b.root, b.barra, R.menu.menu_lateral, { seccion }, R.drawable.ic_menu_lateral) { id -> alElegirMenu(id) })
		ViewCompat.setOnApplyWindowInsetsListener(b.root) { v, insets ->
			val barras = insets.getInsets(WindowInsetsCompat.Type.systemBars() or WindowInsetsCompat.Type.displayCutout() or WindowInsetsCompat.Type.ime())
			v.updatePadding(left = barras.left, top = barras.top, right = barras.right, bottom = barras.bottom)
			WindowInsetsCompat.CONSUMED
		}
		acciones = AccionesProducto(this, alCambiar = { cargar() }, alResultado = { mostrarEstado(it) })
		b.lista.layoutManager = LinearLayoutManager(this)
		b.lista.adapter = adaptador
		b.lista.sinFocoPropio()
		b.anadir.setOnClickListener { EditarProductoActivity.anadir(this) }

		if (estado != null) {
			seccion = estado.getInt(ESTADO_SECCION, R.id.destino_todos)
			val tipo = estado.getInt(ESTADO_GRUPO_TIPO, 0)
			if (tipo != 0) grupo = Grupo(tipo, estado.getString(ESTADO_GRUPO_CLAVE).orEmpty(), estado.getString(ESTADO_GRUPO_TITULO).orEmpty())
			busqueda = estado.getString(ESTADO_BUSQUEDA).orEmpty()
			estado.getString(ESTADO_TEXTO)?.let { mostrarEstado(it) }
		}
		actualizarAtras()

		lifecycleScope.launch {
			repeatOnLifecycle(Lifecycle.State.STARTED) {
				launch {
					com.xebolax.nomesubaslosprecios.motor.Comprobador.progreso.collect { p ->
						b.progreso.isVisible = p != null
						if (p != null) b.progreso.text = getString(R.string.progreso_comprobacion_pantalla, p.hechos, p.total)
						actualizarMenuComprobacion()
						if (p == null) cargar()
					}
				}
				launch {
					ComprobacionManual.resultado.collect { texto ->
						if (texto != null) {
							mostrarEstado(texto)
							ComprobacionManual.resultado.value = null
						}
					}
				}
			}
		}

		if (estado == null) {
			actualizaciones.alIniciar()
			comprobarAlIniciar()
		}
	}

	override fun onSaveInstanceState(estado: Bundle) {
		super.onSaveInstanceState(estado)
		estado.putInt(ESTADO_SECCION, seccion)
		grupo?.let {
			estado.putInt(ESTADO_GRUPO_TIPO, it.tipo)
			estado.putString(ESTADO_GRUPO_CLAVE, it.clave)
			estado.putString(ESTADO_GRUPO_TITULO, it.titulo)
		}
		estado.putString(ESTADO_BUSQUEDA, busqueda)
		if (b.estado.isVisible) estado.putString(ESTADO_TEXTO, b.estado.text.toString())
	}

	override fun onResume() {
		super.onResume()
		cargar()
		Papelera.ultima?.let { copia ->
			Papelera.ultima = null
			acciones.ofrecerDeshacer(copia)
		}
	}

	/** Al abrir la app, si toca por el intervalo, se comprueba en segundo plano (sin molestar). */
	private fun comprobarAlIniciar() {
		if (!prefs.comprobarAlIniciar) return
		val intervalo = prefs.intervaloHoras * 60L * 60 * 1000
		if (System.currentTimeMillis() - prefs.ultimaComprobacionGeneral < intervalo) return
		ComprobacionManual.lanzar(this, manual = false)
	}

	private fun mostrarEstado(texto: String) {
		b.estado.text = texto
		b.estado.isVisible = texto.isNotEmpty()
	}

	private fun actualizarAtras() {
		atras.isEnabled = grupo != null
	}

	// --- Menú lateral -------------------------------------------------------------------------

	private fun tituloSeccion(id: Int = seccion): String = getString(
		when (id) {
			R.id.destino_categorias -> R.string.seccion_categorias
			R.id.destino_tiendas -> R.string.seccion_tiendas
			R.id.destino_ofertas -> R.string.seccion_ofertas
			R.id.destino_favoritos -> R.string.seccion_favoritos
			R.id.destino_comparar -> R.string.seccion_comparar
			R.id.destino_avisos -> R.string.seccion_avisos
			else -> R.string.seccion_todos
		},
	)

	private fun alElegirMenu(id: Int) {
		when (id) {
			R.id.destino_todos, R.id.destino_categorias, R.id.destino_tiendas, R.id.destino_ofertas,
			R.id.destino_favoritos, R.id.destino_comparar, R.id.destino_avisos -> {
				seccion = id
				grupo = null
				busqueda = ""
				menu?.findItem(R.id.menu_buscar)?.collapseActionView()
				actualizarAtras()
				b.estado.isVisible = false
				cargar()
				// Cambia la sección sin cambiar de ventana: TalkBack anuncia el título del panel
				ViewCompat.setAccessibilityPaneTitle(b.lista, getString(R.string.seccion_de, tituloSeccion()))
				invalidateOptionsMenu()
			}
			R.id.accion_importar -> startActivity(Intent(this, ImportarExportarActivity::class.java))
			R.id.accion_categorias -> startActivity(Intent(this, CategoriasActivity::class.java))
			R.id.accion_tiendas -> startActivity(Intent(this, TiendasActivity::class.java))
			R.id.accion_ajustes -> startActivity(Intent(this, AjustesActivity::class.java))
			R.id.accion_manual -> startActivity(Intent(this, ManualActivity::class.java))
			R.id.accion_actualizaciones -> actualizaciones.comprobarAMano()
			R.id.accion_acerca -> acercaDe()
		}
	}

	private fun acercaDe() {
		MaterialAlertDialogBuilder(this)
			.setTitle(R.string.acerca_de)
			.setMessage(getString(R.string.acerca_de_texto, BuildConfig.VERSION_NAME))
			.setPositiveButton(R.string.aceptar, null)
			.setNeutralButton(R.string.novedades_version) { _, _ ->
				startActivity(Intent(this, ManualActivity::class.java).putExtra(ManualActivity.EXTRA_NOVEDADES, true))
			}
			.show()
	}

	// --- Menú de la barra ----------------------------------------------------------------------

	private val enProductos: Boolean
		get() = when (seccion) {
			R.id.destino_avisos -> false
			R.id.destino_categorias, R.id.destino_tiendas, R.id.destino_comparar -> grupo != null
			else -> true
		}

	override fun onCreateOptionsMenu(m: Menu): Boolean {
		menuInflater.inflate(R.menu.principal, m)
		menu = m
		val buscar = m.findItem(R.id.menu_buscar)
		val vista = buscar.actionView as SearchView
		vista.queryHint = getString(R.string.buscar_productos)
		if (busqueda.isNotEmpty()) {
			buscar.expandActionView()
			vista.setQuery(busqueda, false)
		}
		vista.setOnQueryTextListener(object : SearchView.OnQueryTextListener {
			override fun onQueryTextSubmit(texto: String): Boolean {
				vista.clearFocus()
				return true
			}

			override fun onQueryTextChange(texto: String): Boolean {
				if (texto == busqueda) return true
				busqueda = texto
				cargar(anunciarResultados = true)
				return true
			}
		})
		return true
	}

	override fun onPrepareOptionsMenu(m: Menu): Boolean {
		val avisos = seccion == R.id.destino_avisos
		m.findItem(R.id.menu_buscar).isVisible = enProductos
		m.findItem(R.id.menu_ordenar).isVisible = enProductos && seccion != R.id.destino_ofertas && seccion != R.id.destino_comparar
		m.findItem(R.id.menu_filtrar).isVisible = enProductos
		m.findItem(R.id.menu_leidos).isVisible = avisos
		m.findItem(R.id.menu_borrar_avisos).isVisible = avisos
		menu = m
		actualizarMenuComprobacion()
		return super.onPrepareOptionsMenu(m)
	}

	private fun actualizarMenuComprobacion() {
		val m = menu ?: return
		val enCurso = ComprobacionManual.enCurso
		m.findItem(R.id.menu_comprobar)?.isVisible = !enCurso
		m.findItem(R.id.menu_detener)?.isVisible = enCurso
	}

	override fun onOptionsItemSelected(item: MenuItem): Boolean {
		when (item.itemId) {
			R.id.menu_comprobar -> {
				if (!ComprobacionManual.lanzar(this)) mostrarEstado(getString(R.string.comprobacion_en_curso))
				else avisar(getString(R.string.comprobando_precios), mostrar = false)
				actualizarMenuComprobacion()
			}
			R.id.menu_detener -> ComprobacionManual.detener()
			R.id.menu_ordenar -> elegirOrden()
			R.id.menu_filtrar -> elegirFiltros()
			R.id.menu_leidos -> lifecycleScope.launch {
				withContext(Dispatchers.IO) { BaseDatos.obtener(this@PrincipalActivity).marcarTodosLeidos() }
				mostrarEstado(getString(R.string.avisos_marcados_leidos))
				cargar()
			}
			R.id.menu_borrar_avisos -> confirmar(getString(R.string.confirmar_borrar_avisos), getString(R.string.borrar_todos_avisos)) {
				lifecycleScope.launch {
					withContext(Dispatchers.IO) { BaseDatos.obtener(this@PrincipalActivity).borrarAvisos() }
					mostrarEstado(getString(R.string.avisos_borrados))
					cargar()
				}
			}
			else -> return super.onOptionsItemSelected(item)
		}
		return true
	}

	private val ordenes = listOf("nombre", "precio", "bajada", "cambio", "alta", "tienda")

	private fun elegirOrden() {
		val nombres = listOf(R.string.orden_nombre, R.string.orden_precio, R.string.orden_bajada, R.string.orden_cambio, R.string.orden_alta, R.string.orden_tienda)
			.map { getString(it) }
		elegirUno(getString(R.string.ordenar), nombres, ordenes.indexOf(prefs.orden).coerceAtLeast(0)) { i ->
			prefs.orden = ordenes[i]
			mostrarEstado(getString(R.string.ordenado_por, nombres[i]))
			cargar()
		}
	}

	private fun elegirFiltros() {
		val claves = listOf("activos", "error", "agotados")
		val nombres = arrayOf(getString(R.string.filtro_activos), getString(R.string.filtro_error), getString(R.string.filtro_agotados))
		val actuales = prefs.filtros
		val marcados = BooleanArray(claves.size) { claves[it] in actuales }
		MaterialAlertDialogBuilder(this)
			.setTitle(R.string.filtrar)
			.setMultiChoiceItems(nombres, marcados) { _, i, marcado -> marcados[i] = marcado }
			.setPositiveButton(R.string.aplicar) { _, _ ->
				prefs.filtros = claves.filterIndexed { i, _ -> marcados[i] }.toSet()
				cargar(anunciarResultados = true)
			}
			.setNegativeButton(R.string.cancelar, null)
			.show()
	}

	// --- Contenido de cada sección -------------------------------------------------------------

	private fun grupoId(g: Grupo): Long = when (g.tipo) {
		R.id.destino_comparar -> g.clave.lowercase().hashCode().toLong()
		else -> g.clave.toLongOrNull() ?: 0L
	}

	/** Datos leídos de la base de datos para una sección. */
	private class Datos(
		val productos: List<ProductoConNombres>,
		val categorias: List<Categoria>,
		val tiendas: List<Tienda>,
		val avisos: List<AvisoConProducto>,
	)

	/** Vuelve a leer y a pintar la sección. foco: id de la fila que debe recibir el foco de TalkBack. */
	private fun cargar(anunciarResultados: Boolean = false, foco: Long? = null) {
		val seccionPedida = seccion
		lifecycleScope.launch {
			val datos = withContext(Dispatchers.IO) {
				val db = BaseDatos.obtener(this@PrincipalActivity)
				Datos(
					db.productos(),
					if (seccionPedida == R.id.destino_categorias) db.categorias() else emptyList(),
					if (seccionPedida == R.id.destino_tiendas) db.tiendas() else emptyList(),
					if (seccionPedida == R.id.destino_avisos) db.avisos() else emptyList(),
				)
			}
			if (seccionPedida != seccion) return@launch
			pintar(datos, anunciarResultados, foco)
		}
	}

	private fun pintar(d: Datos, anunciarResultados: Boolean, foco: Long?) {
		val g = grupo
		val titulo = when {
			g == null -> tituloSeccion()
			g.tipo == R.id.destino_categorias -> getString(R.string.titulo_categoria, g.titulo)
			g.tipo == R.id.destino_tiendas -> getString(R.string.titulo_tienda, g.titulo)
			else -> getString(R.string.titulo_grupo, g.titulo)
		}
		b.barra.title = titulo
		title = titulo
		val filas: List<Fila>
		val vacio: String
		when {
			seccion == R.id.destino_avisos -> {
				filas = d.avisos.map { filaAviso(it) }
				vacio = getString(R.string.vacio_avisos)
			}
			seccion == R.id.destino_categorias && g == null -> {
				filas = filasCategorias(d)
				vacio = getString(R.string.vacio_productos)
			}
			seccion == R.id.destino_tiendas && g == null -> {
				filas = filasTiendas(d)
				vacio = getString(R.string.vacio_tiendas)
			}
			seccion == R.id.destino_comparar && g == null -> {
				filas = filasGrupos(d)
				vacio = getString(R.string.vacio_comparar)
			}
			else -> {
				val lista = productosDeLaVista(d.productos)
				filas = if (seccion == R.id.destino_comparar) filasComparar(lista) else lista.map { filaProducto(it) }
				vacio = when {
					busqueda.isNotBlank() || prefs.filtros.isNotEmpty() -> getString(R.string.vacio_busqueda)
					seccion == R.id.destino_ofertas -> getString(R.string.vacio_ofertas)
					seccion == R.id.destino_favoritos -> getString(R.string.vacio_favoritos)
					else -> getString(R.string.vacio_productos)
				}
				if (anunciarResultados) mostrarEstado(resources.getQuantityString(R.plurals.productos_encontrados, lista.size, lista.size))
			}
		}
		adaptador.submitList(filas) {
			if (foco != null) {
				val pos = filas.indexOfFirst { it.id == foco }
				if (pos >= 0) {
					b.lista.scrollToPosition(pos)
					b.lista.post {
						b.lista.findViewHolderForAdapterPosition(pos)?.itemView?.performAccessibilityAction(AccessibilityNodeInfo.ACTION_ACCESSIBILITY_FOCUS, null)
					}
				}
			}
		}
		b.vacio.text = vacio
		b.vacio.isVisible = filas.isEmpty()
		b.anadir.visibility = if (seccion == R.id.destino_avisos) View.GONE else View.VISIBLE
		invalidateOptionsMenu()
	}

	/** Productos de la sección (o del grupo abierto) con búsqueda, filtros y orden. */
	private fun productosDeLaVista(todos: List<ProductoConNombres>): List<ProductoConNombres> {
		val g = grupo
		var lista = when (seccion) {
			R.id.destino_favoritos -> todos.filter { it.producto.favorito }
			R.id.destino_ofertas -> todos.filter { it.producto.activo && Ofertas.esOferta(it.producto) }
			R.id.destino_categorias -> {
				val id = g?.clave?.toLongOrNull()
				todos.filter { if (id == SIN_CATEGORIA) it.producto.categoriaId == null else it.producto.categoriaId == id }
			}
			R.id.destino_tiendas -> todos.filter { it.producto.tiendaId == g?.clave?.toLongOrNull() }
			R.id.destino_comparar -> todos.filter { it.producto.grupo?.trim().equals(g?.clave, ignoreCase = true) }
			else -> todos
		}
		val filtros = prefs.filtros
		if ("activos" in filtros) lista = lista.filter { it.producto.activo }
		if ("error" in filtros) lista = lista.filter { !it.producto.ultimoError.isNullOrBlank() }
		if ("agotados" in filtros) lista = lista.filter { !it.producto.disponible }
		val q = busqueda.trim()
		if (q.isNotEmpty()) lista = lista.filter { pc ->
			listOfNotNull(pc.producto.nombre, pc.tienda, pc.categoria, pc.producto.notas, pc.producto.grupo).any { it.contains(q, ignoreCase = true) }
		}
		return when {
			seccion == R.id.destino_ofertas -> lista.sortedByDescending { Ofertas.porcentajeBajada(it.producto) }
			seccion == R.id.destino_comparar -> lista.sortedWith(compareBy(nullsLast()) { it.producto.precioActual })
			else -> ordenar(lista)
		}
	}

	private fun ordenar(lista: List<ProductoConNombres>): List<ProductoConNombres> {
		val porNombre = Comparator<ProductoConNombres> { a, b -> coteja.compare(a.producto.nombre, b.producto.nombre) }
		return when (prefs.orden) {
			"precio" -> lista.sortedWith(compareBy<ProductoConNombres, Double?>(nullsLast()) { it.producto.precioActual }.then(porNombre))
			"bajada" -> lista.sortedWith(compareByDescending<ProductoConNombres> { Ofertas.porcentajeBajada(it.producto) }.then(porNombre))
			"cambio" -> lista.sortedWith(compareByDescending<ProductoConNombres> { Fechas.ms(it.producto.fechaCambio) ?: 0L }.then(porNombre))
			"alta" -> lista.sortedWith(compareByDescending<ProductoConNombres> { Fechas.ms(it.producto.fechaAlta) ?: 0L }.then(porNombre))
			"tienda" -> lista.sortedWith(Comparator<ProductoConNombres> { a, b -> coteja.compare(a.tienda, b.tienda) }.then(porNombre))
			else -> lista.sortedWith(porNombre)
		}
	}

	private fun filaProducto(pc: ProductoConNombres, extra: String? = null): Fila {
		val p = pc.producto
		val acc: List<Accion> = acciones.acciones(pc, conDetalles = false) { copia -> acciones.ofrecerDeshacer(copia) }
		return Fila(
			id = p.id,
			titulo = tituloFila(pc),
			detalle = detalleFila(pc, extra),
			descripcion = textoFila(pc, extra),
			etiquetaPulsar = getString(R.string.ver_detalles),
			destacada = Ofertas.esOferta(p) && p.activo,
			zona = ZonaAcciones.PRODUCTO,
			alPulsar = { DetalleActivity.abrir(this, p.id) },
			acciones = acc,
		)
	}

	/** Comparar: de más barato a más caro, con la diferencia con el más barato. */
	private fun filasComparar(lista: List<ProductoConNombres>): List<Fila> {
		val minimo = lista.firstOrNull { it.producto.precioActual != null }?.producto?.precioActual
		return lista.map { pc ->
			val precio = pc.producto.precioActual
			val extra = when {
				precio == null || minimo == null -> null
				precio <= minimo -> getString(R.string.el_mas_barato)
				else -> getString(R.string.mas_que_el_mas_barato, formatearImporte(precio - minimo, pc.producto.moneda))
			}
			filaProducto(pc, extra)
		}
	}

	private fun filaGrupo(id: Long, nombre: String, cuantos: Int, extra: String?, abrir: () -> Unit): Fila {
		val n = resources.getQuantityString(R.plurals.n_productos, cuantos, cuantos)
		val detalle = listOfNotNull(n, extra).joinToString(", ")
		return Fila(
			id = id, titulo = nombre, detalle = detalle, descripcion = "$nombre, $detalle",
			etiquetaPulsar = getString(R.string.ver_productos), zona = ZonaAcciones.GRUPO, alPulsar = abrir,
		)
	}

	private fun abrirGrupo(g: Grupo) {
		grupo = g
		actualizarAtras()
		cargar()
		ViewCompat.setAccessibilityPaneTitle(b.lista, g.titulo)
	}

	private fun filasCategorias(d: Datos): List<Fila> {
		val cuenta = d.productos.groupingBy { it.producto.categoriaId }.eachCount()
		val sin = getString(R.string.sin_categoria)
		return d.categorias.map { c ->
			filaGrupo(c.id, c.nombre, cuenta[c.id] ?: 0, c.descripcion) { abrirGrupo(Grupo(R.id.destino_categorias, c.id.toString(), c.nombre)) }
		} + filaGrupo(SIN_CATEGORIA, sin, cuenta[null] ?: 0, null) { abrirGrupo(Grupo(R.id.destino_categorias, SIN_CATEGORIA.toString(), sin)) }
	}

	private fun filasTiendas(d: Datos): List<Fila> {
		val cuenta = d.productos.groupingBy { it.producto.tiendaId }.eachCount()
		return d.tiendas.map { t ->
			filaGrupo(t.id, t.nombre, cuenta[t.id] ?: 0, t.dominio) { abrirGrupo(Grupo(R.id.destino_tiendas, t.id.toString(), t.nombre)) }
		}
	}

	private fun filasGrupos(d: Datos): List<Fila> {
		val grupos = d.productos.filter { !it.producto.grupo.isNullOrBlank() }.groupBy { it.producto.grupo!!.trim().lowercase() }
		return grupos.values.sortedWith { a, b -> coteja.compare(a.first().producto.grupo, b.first().producto.grupo) }.map { lista ->
			val nombre = lista.first().producto.grupo!!.trim()
			val masBarato = lista.mapNotNull { pc -> pc.producto.precioActual?.let { it to pc.producto.moneda } }.minByOrNull { it.first }
			val extra = masBarato?.let { getString(R.string.desde, formatearImporte(it.first, it.second)) }
			filaGrupo(nombre.lowercase().hashCode().toLong(), nombre, lista.size, extra) { abrirGrupo(Grupo(R.id.destino_comparar, nombre, nombre)) }
		}
	}

	private fun filaAviso(ap: AvisoConProducto): Fila {
		val a = ap.aviso
		val db = BaseDatos.obtener(this)
		val estado = if (a.leido) null else getString(R.string.no_leido)
		val fecha = Fechas.fechaHora(a.fecha)
		val titulo = listOfNotNull(estado, a.titulo).joinToString(", ")
		val acc = mutableListOf<Accion>()
		acc += getString(if (a.leido) R.string.marcar_no_leido else R.string.marcar_leido) to {
			lifecycleScope.launch {
				withContext(Dispatchers.IO) { db.marcarAviso(a.id, !a.leido) }
				cargar()
			}
		}
		if (a.productoId != null) acc += getString(R.string.ver_producto) to { abrirAviso(a.id, a.productoId) }
		acc += getString(R.string.borrar_aviso) to {
			lifecycleScope.launch {
				withContext(Dispatchers.IO) { db.borrarAviso(a.id) }
				mostrarEstado(getString(R.string.aviso_borrado))
				cargar()
			}
		}
		return Fila(
			id = a.id,
			titulo = titulo,
			detalle = "${a.mensaje} $fecha",
			descripcion = listOfNotNull(estado, a.titulo, a.mensaje, fecha).joinToString(", "),
			etiquetaPulsar = getString(if (a.productoId != null) R.string.ver_producto else R.string.marcar_leido),
			destacada = !a.leido,
			zona = ZonaAcciones.AVISO,
			alPulsar = {
				if (a.productoId != null) abrirAviso(a.id, a.productoId)
				else lifecycleScope.launch {
					withContext(Dispatchers.IO) { db.marcarAviso(a.id, true) }
					cargar()
				}
			},
			acciones = acc,
		)
	}

	/** Abrir un aviso lo marca como leído y lleva a su producto. */
	private fun abrirAviso(id: Long, productoId: Long) {
		lifecycleScope.launch {
			withContext(Dispatchers.IO) { BaseDatos.obtener(this@PrincipalActivity).marcarAviso(id, true) }
			DetalleActivity.abrir(this@PrincipalActivity, productoId)
		}
	}
}
