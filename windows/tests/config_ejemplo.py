"""Configuración de EJEMPLO de las plantillas del agente «configuracion».

Las pruebas copiadas de la plantilla (``test_configuracion.py`` y
``test_dialogo_preferencias.py``) comprueban el mecanismo (carga, fusión,
migraciones, validación, diálogo) con estas claves de ejemplo; la fixture
``configuracion_de_ejemplo`` las pone en lugar de las reales de la app. Las
claves reales se prueban en ``test_ajustes.py``.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.core.configuracion import Regla, eliminar_clave, renombrar_clave
from app.ui.dialogo_preferencias import BOOL, CARPETA, DECIMAL, ENTERO, OPCION, SECRETO, TEXTO, N_, Opcion, Pagina

VALORES_POR_DEFECTO: dict[str, dict[str, Any]] = {
	"general": {
		"idioma": "es",
		"confirmar_salida": True,
		"minimizar_a_bandeja": False,
		"carpeta_descargas": "",
	},
	"apariencia": {
		"tamano_fuente": 11,
		"tema": "sistema",
	},
	"accesibilidad": {
		"anunciar_cambios": True,
		"retardo_voz_ms": 120,
		"volumen": 0.8,
	},
	"red": {
		"intervalo_actualizacion_s": 60,
		"usar_proxy": False,
		"servidor_proxy": "",
		"puerto_proxy": 8080,
	},
}


REGLAS: dict[str, Regla] = {
	"general.idioma": Regla(opciones=("es", "en", "fr", "pt")),
	"apariencia.tamano_fuente": Regla(minimo=8, maximo=40),
	"apariencia.tema": Regla(opciones=("sistema", "claro", "oscuro")),
	"accesibilidad.retardo_voz_ms": Regla(minimo=0, maximo=2000),
	"accesibilidad.volumen": Regla(minimo=0.0, maximo=1.0),
	"red.intervalo_actualizacion_s": Regla(minimo=10, maximo=86400),
	"red.servidor_proxy": Regla(longitud_maxima=255),
	"red.puerto_proxy": Regla(minimo=1, maximo=65535),
}



def _migrar_a_2(datos: dict) -> None:
	"""v1 → v2: la fuente pasó de «general» a «apariencia» y se retiró «usar_sonidos_viejos».

	EJEMPLO: sustitúyelo por las migraciones reales del proyecto.
	"""
	renombrar_clave(datos, "general.tamano_letra", "apariencia.tamano_fuente")
	eliminar_clave(datos, "general.usar_sonidos_viejos")


MIGRACIONES: dict[int, Callable[[dict], None]] = {
	1: _migrar_a_2,
}



PAGINAS: tuple[Pagina, ...] = (
	Pagina(N_("General"), (
		Opcion("general.idioma", N_("&Idioma de la interfaz:"), OPCION,
			N_("Idioma de menús y mensajes. Se aplica al reiniciar la aplicación."),
			opciones=(("es", N_("Español")), ("en", N_("Inglés")), ("fr", N_("Francés")), ("pt", N_("Portugués")))),
		Opcion("general.confirmar_salida", N_("&Confirmar antes de salir"), BOOL,
			N_("Pregunta antes de cerrar la aplicación.")),
		Opcion("general.minimizar_a_bandeja", N_("&Minimizar a la bandeja del sistema"), BOOL,
			N_("Al minimizar, la ventana se oculta y queda un icono junto al reloj.")),
		Opcion("general.carpeta_descargas", N_("Carpeta de &descargas:"), CARPETA,
			N_("Dónde se guardan los archivos descargados. Vacío: preguntar cada vez.")),
	)),
	Pagina(N_("Apariencia"), (
		Opcion("apariencia.tamano_fuente", N_("&Tamaño de la letra:"), ENTERO,
			N_("Tamaño en puntos del texto de las listas y del lector. Se aplica al momento.")),
		Opcion("apariencia.tema", N_("T&ema:"), OPCION,
			N_("Colores de la interfaz."),
			opciones=(("sistema", N_("Según el sistema")), ("claro", N_("Claro")), ("oscuro", N_("Oscuro")))),
	)),
	Pagina(N_("Accesibilidad"), (
		Opcion("accesibilidad.anunciar_cambios", N_("&Anunciar los cambios con el lector de pantalla"), BOOL,
			N_("Lee en voz alta los avisos breves (guardado, elementos nuevos...).")),
		Opcion("accesibilidad.retardo_voz_ms", N_("&Retardo de los avisos (milisegundos):"), ENTERO,
			N_("Espera antes de hablar para no pisar lo que el lector anuncia al mover el foco.")),
		Opcion("accesibilidad.volumen", N_("&Volumen de los sonidos (0 a 1):"), DECIMAL,
			N_("Volumen de los sonidos de la aplicación."), incremento=0.05),
	)),
	Pagina(N_("Red"), (
		Opcion("red.intervalo_actualizacion_s", N_("&Intervalo de actualización (segundos):"), ENTERO,
			N_("Cada cuánto se buscan novedades.")),
		Opcion("red.usar_proxy", N_("&Usar un servidor proxy"), BOOL,
			N_("Envía las conexiones a través del proxy indicado debajo.")),
		Opcion("red.servidor_proxy", N_("&Servidor proxy:"), TEXTO,
			N_("Nombre o dirección del proxy, sin «http://».")),
		Opcion("red.puerto_proxy", N_("&Puerto del proxy:"), ENTERO,
			N_("Puerto del servidor proxy.")),
		Opcion("red.contrasena_proxy", N_("C&ontraseña del proxy:"), SECRETO,
			N_("Se guarda cifrada, nunca en el archivo de configuración.")),
	)),
)


