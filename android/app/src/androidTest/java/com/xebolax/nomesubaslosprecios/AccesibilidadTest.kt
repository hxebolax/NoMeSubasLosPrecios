package com.xebolax.nomesubaslosprecios

import android.accessibilityservice.AccessibilityService
import android.app.UiAutomation
import android.content.Context
import android.content.Intent
import android.os.Build
import android.util.Log
import android.view.accessibility.AccessibilityEvent
import android.view.accessibility.AccessibilityNodeInfo
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.google.android.apps.common.testing.accessibility.framework.AccessibilityCheckPreset
import com.google.android.apps.common.testing.accessibility.framework.AccessibilityCheckResult.AccessibilityCheckResultType
import com.google.android.apps.common.testing.accessibility.framework.Parameters
import com.google.android.apps.common.testing.accessibility.framework.uielement.AccessibilityHierarchyAndroid
import com.google.android.apps.common.testing.accessibility.framework.utils.contrast.BitmapImage
import com.xebolax.nomesubaslosprecios.datos.BaseDatos
import com.xebolax.nomesubaslosprecios.nucleo.AjustesAvisos
import com.xebolax.nomesubaslosprecios.nucleo.Colores
import com.xebolax.nomesubaslosprecios.nucleo.Lectura
import com.xebolax.nomesubaslosprecios.nucleo.LogicaAvisos
import com.xebolax.nomesubaslosprecios.nucleo.Producto
import com.xebolax.nomesubaslosprecios.ui.AjustesActivity
import com.xebolax.nomesubaslosprecios.ui.CategoriasActivity
import com.xebolax.nomesubaslosprecios.ui.DetalleActivity
import com.xebolax.nomesubaslosprecios.ui.EditarProductoActivity
import com.xebolax.nomesubaslosprecios.ui.ImportarExportarActivity
import com.xebolax.nomesubaslosprecios.ui.ManualActivity
import com.xebolax.nomesubaslosprecios.ui.TiendasActivity
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import java.util.Locale

/**
 * Recorre las pantallas de la app con TalkBack activo, como quien desliza el
 * dedo de elemento en elemento: pone el foco de accesibilidad en cada uno
 * (TalkBack lo lee de verdad; con su registro detallado se ve qué dice), prueba
 * los deslizadores y pasa las comprobaciones del Accessibility Test Framework
 * de Google (las de Accessibility Scanner: etiquetas, tamaño de los objetivos,
 * contraste, duplicados...). Todo queda en el registro con las etiquetas
 * «Recorrido», «ATF», «Foco», «Eventos» y «Menu».
 *
 * Por defecto no falla: es un informe para revisar. Con el argumento
 * estricto=true falla si hay elementos sin nombre o errores del ATF.
 *
 * Se pasa con TalkBack encendido en el emulador (ver referencias/pruebas.md):
 *
 *     (solo con el emulador conectado; con un móvil físico enchufado, fija ANDROID_SERIAL=emulator-5554)
 *     gradle connectedDebugAndroidTest -Pandroid.testInstrumentationRunnerArguments.class=com.xebolax.nomesubaslosprecios.AccesibilidadTest
 *     adb -s emulator-5554 logcat -d -s Recorrido ATF Foco Eventos Menu
 *
 * Dependencias (androidTestImplementation): androidx.test:runner, androidx.test:core,
 * androidx.test.ext:junit y com.google.android.apps.common.testing.accessibility.framework:accessibility-test-framework.
 *
 * QUÉ ADAPTAR: el paquete; pantallas (cada pantalla con el Intent que la abre);
 * preparar() para crear datos de muestra (sin listas vacías, que no prueban nada);
 * y los textos de focoVuelveTrasVentanas().
 */
@RunWith(AndroidJUnit4::class)
class AccesibilidadTest {

	private val instrumentacion = InstrumentationRegistry.getInstrumentation()
	private lateinit var app: Context
	private lateinit var ui: UiAutomation
	private val estricto = InstrumentationRegistry.getArguments().getString("estricto") == "true"
	private val problemas = mutableListOf<String>()

	/** Pantallas que se recorren además de la de inicio: nombre para el registro y cómo abrirla. */
	private val pantallas: List<Pair<String, (Context) -> Intent>> by lazy {
		listOf(
			"Detalles del producto" to { c -> Intent(c, DetalleActivity::class.java).putExtra(DetalleActivity.EXTRA_ID, idMuestra) },
			"Añadir producto" to { c -> Intent(c, EditarProductoActivity::class.java) },
			"Editar producto" to { c -> Intent(c, EditarProductoActivity::class.java).putExtra(EditarProductoActivity.EXTRA_ID, idMuestra) },
			"Gestionar categorías" to { c -> Intent(c, CategoriasActivity::class.java) },
			"Gestionar tiendas" to { c -> Intent(c, TiendasActivity::class.java) },
			"Importar y exportar" to { c -> Intent(c, ImportarExportarActivity::class.java) },
			"Ajustes" to { c -> Intent(c, AjustesActivity::class.java) },
			"Manual" to { c -> Intent(c, ManualActivity::class.java) },
		)
	}

	/** Producto de muestra (para no recorrer listas vacías). */
	private var idMuestra = 0L

	/** Datos de muestra: una tienda, una categoría y un producto con historial y un aviso. */
	private fun crearMuestra() {
		val db = BaseDatos.obtener(app)
		if (db.cuantosProductos() > 0) {
			idMuestra = db.productos().first().producto.id
			return
		}
		val tienda = db.tiendaParaDominio("tiendaejemplo.es", "Tiendaejemplo")
		val categoria = db.crearCategoria("Electrónica", "Aparatos")
		val p = Producto(
			uuid = BaseDatos.nuevoUuid(), nombre = "Auriculares de prueba", url = "https://www.tiendaejemplo.es/p/x200",
			tiendaId = tienda.id, categoriaId = categoria, fechaAlta = "2026-10-01T10:00:00Z",
		)
		idMuestra = db.crearProducto(p)
		val guardado = p.copy(id = idMuestra)
		val primera = LogicaAvisos.aplicarLectura(guardado, Lectura(149.0, true), AjustesAvisos(), "2026-10-01T10:00:00Z", "Tiendaejemplo")
		db.guardarComprobacion(primera.producto, primera.historial, primera.avisos)
		val bajada = LogicaAvisos.aplicarLectura(primera.producto, Lectura(129.99, true), AjustesAvisos(), "2026-11-01T10:00:00Z", "Tiendaejemplo")
		db.guardarComprobacion(bajada.producto, bajada.historial, bajada.avisos)
	}

	@Before
	fun preparar() {
		app = instrumentacion.targetContext
		// Sin suprimir TalkBack: tiene que seguir hablando mientras se recorre
		ui = instrumentacion.getUiAutomation(UiAutomation.FLAG_DONT_SUPPRESS_ACCESSIBILITY_SERVICES)
		// La app en español, como la usará el usuario (quita esta línea si la app no tiene idioma por app)
		if (Build.VERSION.SDK_INT >= 33) ui.executeShellCommand("cmd locale set-app-locales ${app.packageName} --locales es-ES").close()
		// Sin el aviso del permiso de notificaciones tapando la pantalla
		if (Build.VERSION.SDK_INT >= 33) ui.grantRuntimePermission(app.packageName, android.Manifest.permission.POST_NOTIFICATIONS)
		esperar(1500)
		crearMuestra()
	}

	// --- Utilidades ----------------------------------------------------------------------------

	private fun esperar(ms: Long) = Thread.sleep(ms)

	private fun inicio(): Intent = requireNotNull(app.packageManager.getLaunchIntentForPackage(app.packageName)) { "La app no tiene pantalla de inicio" }

	private fun abrir(intent: Intent, espera: Long = 4000) {
		app.startActivity(intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK))
		esperar(espera)
	}

	private fun raiz(): AccessibilityNodeInfo? {
		repeat(10) {
			ui.rootInActiveWindow?.let { return it }
			esperar(300)
		}
		return null
	}

	/** Lo que diría TalkBack de un nodo: su nombre y su estado. */
	private fun texto(n: AccessibilityNodeInfo): String {
		val partes = listOfNotNull(
			n.contentDescription?.toString()?.takeIf { it.isNotBlank() } ?: n.text?.toString()?.takeIf { it.isNotBlank() },
			if (Build.VERSION.SDK_INT >= 30) n.stateDescription?.toString()?.takeIf { it.isNotBlank() } else null,
		)
		return partes.joinToString(", ")
	}

	/** Su texto o, en una fila, el de lo que tiene dentro. */
	private fun nombre(n: AccessibilityNodeInfo): String = texto(n).ifBlank {
		(0 until n.childCount).mapNotNull { n.getChild(it)?.let { h -> nombre(h) } }.filter { it.isNotBlank() }.joinToString(", ")
	}

	/** Toca el primer elemento con ese texto o descripción (como un doble toque de TalkBack). */
	private fun tocar(texto: String): Boolean {
		val nodo = elemento(texto) ?: return false
		val ok = nodo.performAction(AccessibilityNodeInfo.ACTION_CLICK)
		esperar(2500)
		return ok
	}

	/** El elemento pulsable visible que se llama exactamente así (o, si no hay, el que lo contiene). */
	private fun elemento(texto: String): AccessibilityNodeInfo? {
		val todos = raiz()?.findAccessibilityNodeInfosByText(texto)?.filter { it.isVisibleToUser }.orEmpty()
		val n = todos.firstOrNull { (it.contentDescription ?: it.text)?.toString()?.trim() == texto } ?: todos.firstOrNull() ?: return null
		var p: AccessibilityNodeInfo? = n
		while (p != null && !p.isClickable && !p.isLongClickable) p = p.parent
		return p ?: n
	}

	/** ¿TalkBack se pararía en este elemento al deslizar? (tiene acción, o texto sin un padre con acción) */
	private fun enfocable(n: AccessibilityNodeInfo): Boolean {
		if (!n.isVisibleToUser) return false
		// TalkBack no se para en los contenedores con desplazamiento que tienen elementos dentro
		val clase = n.className?.toString().orEmpty()
		if ((n.isScrollable || clase.endsWith("ScrollView") || clase.endsWith("RecyclerView")) && n.childCount > 0) return false
		if (n.isClickable || n.isLongClickable || n.isFocusable || (Build.VERSION.SDK_INT >= 28 && n.isScreenReaderFocusable)) return true
		if (n.text.isNullOrBlank() && n.contentDescription.isNullOrBlank()) return false
		var p = n.parent
		while (p != null) {
			if (p.isClickable || p.isFocusable || (Build.VERSION.SDK_INT >= 28 && p.isScreenReaderFocusable)) return false
			p = p.parent
		}
		return true
	}

	private fun recoger(n: AccessibilityNodeInfo, lista: MutableList<AccessibilityNodeInfo>) {
		// Lo que TalkBack no visita (una vista marcada como no importante dentro de un control propio) no cuenta
		if (enfocable(n) && n.isImportantForAccessibility) lista += n
		for (i in 0 until n.childCount) n.getChild(i)?.let { recoger(it, lista) }
	}

	/** Recorre la pantalla con el foco de TalkBack y pasa las comprobaciones de accesibilidad. */
	private fun revisar(pantalla: String, maximo: Int = 45) {
		val r = raiz() ?: run { Log.w("Recorrido", "$pantalla | SIN VENTANA"); return }
		Log.i("Recorrido", "=== $pantalla ===")
		val nodos = mutableListOf<AccessibilityNodeInfo>()
		recoger(r, nodos)
		nodos.take(maximo).forEachIndexed { i, n ->
			val clase = n.className?.toString()?.substringAfterLast('.').orEmpty()
			val sinNombre = nombre(n).isBlank()
			if (sinNombre) problemas += "$pantalla: elemento ${i + 1} ($clase) sin nombre"
			Log.i("Recorrido", "$pantalla | ${i + 1} | $clase | ${if (sinNombre) "¡SIN NOMBRE!" else nombre(n)}" +
				(if (n.isClickable) " | pulsable" else "") + (if (n.actionList.size > 6) " | ${n.actionList.size} acciones" else ""))
			n.performAction(AccessibilityNodeInfo.ACTION_ACCESSIBILITY_FOCUS)
			esperar(700)
			// Deslizadores: deslizar arriba como con TalkBack, ver qué valor dice y volver
			if (clase == "SeekBar" && n.actionList.any { it.id == AccessibilityNodeInfo.ACTION_SCROLL_FORWARD }) {
				val antes = texto(n)
				n.performAction(AccessibilityNodeInfo.ACTION_SCROLL_FORWARD)
				esperar(900)
				n.refresh()
				Log.i("Recorrido", "$pantalla | DESLIZADOR | $antes  →  ${texto(n)}")
				n.performAction(AccessibilityNodeInfo.ACTION_SCROLL_BACKWARD)
				esperar(600)
			}
		}
		if (nodos.size > maximo) Log.i("Recorrido", "$pantalla | ... ${nodos.size - maximo} más")
		comprobar(pantalla, r)
	}

	/**
	 * Accessibility Test Framework sobre la jerarquía y una captura (para el
	 * contraste). Falsos avisos de contraste conocidos: el recuadro de foco de
	 * TalkBack y el oscurecido de detrás de un cajón abierto.
	 */
	private fun comprobar(pantalla: String, r: AccessibilityNodeInfo) {
		runCatching {
			val jerarquia = AccessibilityHierarchyAndroid.newBuilder(r, app).build()
			val parametros = Parameters()
			ui.takeScreenshot()?.let { parametros.putScreenCapture(BitmapImage(it)) }
			val comprobaciones = AccessibilityCheckPreset.getAccessibilityHierarchyChecksForPreset(AccessibilityCheckPreset.LATEST)
			for (c in comprobaciones) {
				for (res in c.runCheckOnHierarchy(jerarquia, null, parametros)) {
					if (res.type != AccessibilityCheckResultType.ERROR && res.type != AccessibilityCheckResultType.WARNING) continue
					val e = res.element
					val quien = listOfNotNull(e?.contentDescription?.toString(), e?.text?.toString(), e?.className?.toString()?.substringAfterLast('.'))
						.firstOrNull { it.isNotBlank() }.orEmpty()
					val linea = "$pantalla | ${res.type} | ${c.javaClass.simpleName} | $quien | ${res.getMessage(Locale.getDefault())}"
					Log.w("ATF", linea)
					if (res.type == AccessibilityCheckResultType.ERROR) problemas += linea
				}
			}
		}.onFailure { Log.e("ATF", "$pantalla | no se pudo comprobar", it) }
	}

	private fun comprobarEstricto() {
		problemas.forEach { Log.w("Recorrido", "PROBLEMA | $it") }
		if (estricto) assertTrue("Problemas de accesibilidad:\n" + problemas.joinToString("\n"), problemas.isEmpty())
	}

	// --- El recorrido ----------------------------------------------------------------------------

	@Test
	fun recorrerTodo() {
		abrir(inicio())
		revisar("Inicio")
		if (tocar(app.getString(R.string.abrir_menu))) {
			revisar("Menú lateral")
			atras()
		}
		for ((titulo, abrirla) in pantallas) {
			abrir(abrirla(app))
			revisar(titulo)
		}
		comprobarEstricto()
	}

	/**
	 * Ajustes, «Colores de la lista» (1.1.0): las filas de colores dicen su título y
	 * el color elegido, la vista previa no la visita TalkBack y la lista de colores
	 * lee el nombre de cada color con «marcado» en el elegido.
	 */
	@Test
	fun coloresDeLaLista() {
		abrir(Intent(app, AjustesActivity::class.java))
		val titulo = app.getString(R.string.ajustes_colores)
		val ultimo = app.getString(R.string.color_tipo_problema)
		repeat(8) {
			if (elemento(ultimo) != null) return@repeat
			val lista = mutableListOf<AccessibilityNodeInfo>()
			fun buscar(n: AccessibilityNodeInfo) {
				if (n.isScrollable) lista += n
				for (i in 0 until n.childCount) n.getChild(i)?.let { buscar(it) }
			}
			raiz()?.let { buscar(it) }
			lista.firstOrNull()?.performAction(AccessibilityNodeInfo.ACTION_SCROLL_FORWARD)
			esperar(800)
		}
		assertTrue("No se llega a «$titulo»", elemento(titulo) != null || elemento(ultimo) != null)
		revisar("Ajustes: colores de la lista")
		val nodos = mutableListOf<AccessibilityNodeInfo>()
		raiz()?.let { recoger(it, nodos) }
		val nombres = nodos.map { nombre(it) }
		val ejemplo = app.getString(R.string.colores_ejemplo_subida)
		assertTrue("La vista previa no debe leerse: $nombres", nombres.none { ejemplo in it })
		val bajada = app.getString(R.string.color_tipo_bajada)
		val filaBajada = nombres.firstOrNull { it.startsWith(bajada) }
		assertTrue("La fila «$bajada» debe decir también el color: $filaBajada", filaBajada != null && filaBajada.length > bajada.length + 2)
		if (tocar(bajada)) {
			revisar("Lista de colores")
			// Las opciones que se ven (la lista se desplaza hasta la elegida): cada una con el nombre del color
			val opciones = Colores.PALETA.mapNotNull { c ->
				raiz()?.findAccessibilityNodeInfosByText(c.nombre)?.firstOrNull { it.text?.toString() == c.nombre && it.isCheckable }
			}
			val marcadas = opciones.filter { it.isChecked }.map { it.text.toString() }
			Log.i("Recorrido", "Lista de colores | ${opciones.size} opciones a la vista | marcadas: $marcadas")
			assertTrue("La lista de colores no muestra opciones marcables", opciones.isNotEmpty())
			assertTrue("Debe haber un color marcado: $marcadas", marcadas.size == 1)
			atras()
		}
		comprobarEstricto()
	}

	/** Qué expone a TalkBack cada elemento del menú lateral: solo el destino actual «seleccionado», nada «marcable». */
	@Test
	fun menuLateral() {
		abrir(inicio())
		if (!tocar(app.getString(R.string.abrir_menu))) {
			Log.i("Menu", "Esta pantalla no tiene menú lateral")
			return
		}
		esperar(1000)
		Log.i("Menu", "Foco al abrir: ${conFoco()?.let { "${nombre(it)} seleccionado=${it.isSelected}" }}")
		val r = raiz() ?: return
		val nodos = mutableListOf<AccessibilityNodeInfo>()
		recoger(r, nodos)
		val seleccionados = nodos.count { it.isSelected }
		for (n in nodos) {
			Log.i("Menu", "${n.className?.toString()?.substringAfterLast('.')} | ${nombre(n)} | pulsable=${n.isClickable} marcable=${n.isCheckable} " +
				"marcado=${n.isChecked} seleccionado=${n.isSelected} enfocable=${n.isFocusable} hijos=${n.childCount}")
			if (n.isCheckable) problemas += "Menú lateral: «${nombre(n)}» es marcable (TalkBack dirá marcado o no marcado)"
		}
		if (seleccionados != 1) problemas += "Menú lateral: $seleccionados elementos seleccionados (debe ser 1, el destino actual)"
		atras()
		comprobarEstricto()
	}

	// --- El foco vuelve a su sitio al cerrar ventanas ------------------------------------------

	private fun conFoco(): AccessibilityNodeInfo? = raiz()?.findFocus(AccessibilityNodeInfo.FOCUS_ACCESSIBILITY)

	private fun atras() {
		ui.performGlobalAction(AccessibilityService.GLOBAL_ACTION_BACK)
		esperar(1500)
	}

	/** Pone el foco en el elemento, abre algo encima, lo cierra y mira si el foco ha vuelto al mismo sitio. */
	private fun vuelta(prueba: String, n: AccessibilityNodeInfo?, abrirlo: (AccessibilityNodeInfo) -> Unit, cerrarlo: () -> Unit) {
		if (n == null) { Log.w("Foco", "$prueba | NO ENCONTRADO"); return }
		n.performAction(AccessibilityNodeInfo.ACTION_ACCESSIBILITY_FOCUS)
		esperar(1000)
		val antes = nombre(n)
		abrirlo(n)
		esperar(2500)
		val encima = raiz()?.let { r -> mutableListOf<AccessibilityNodeInfo>().also { recoger(r, it) }.take(4).joinToString(" / ") { nombre(it) } }
		// Qué eventos llegan a TalkBack al cerrar (un TYPE_WINDOW_STATE_CHANGED de la pantalla de debajo repetiría su título)
		ui.setOnAccessibilityEventListener { e ->
			if (e.eventType != AccessibilityEvent.TYPE_WINDOW_CONTENT_CHANGED)
				Log.i("Eventos", "$prueba | ${AccessibilityEvent.eventTypeToString(e.eventType)} | ${e.className} | ${e.text}")
		}
		cerrarlo()
		esperar(2500)
		ui.setOnAccessibilityEventListener(null)
		val despues = conFoco()
		val bien = despues != null && (despues == n || nombre(despues) == antes)
		if (!bien) problemas += "$prueba: el foco no volvió (antes: $antes, después: ${despues?.let { nombre(it) } ?: "nada"})"
		Log.i("Foco", "$prueba | ${if (bien) "BIEN" else "MAL"} | antes: $antes | encima: $encima | después: ${despues?.let { nombre(it) } ?: "nada"}")
	}

	@Test
	fun focoVuelveTrasVentanas() {
		abrir(inicio())
		// El menú lateral y volver: el foco tiene que quedar en «Abrir menú»
		vuelta("Menú lateral", elemento(app.getString(R.string.abrir_menu)), { it.performAction(AccessibilityNodeInfo.ACTION_CLICK) }, ::atras)
		// Las acciones de una fila (pulsación larga) y volver
		vuelta("Fila: acciones", elemento("Auriculares de prueba"), { it.performAction(AccessibilityNodeInfo.ACTION_LONG_CLICK) }, ::atras)
		comprobarEstricto()
	}
}
