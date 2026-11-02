"""Textos y cálculos de lo que se enseña: filas de la lista, ofertas, orden, resumen...

Todo puro (sin wx ni base de datos) para poder probarlo: la ventana solo
pinta lo que estas funciones devuelven. Los textos están pensados para el
lector de pantalla: importes «129,99 €», fechas con el mes en letra,
estado primero.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Iterable, Mapping
from datetime import datetime, timedelta, timezone
from typing import Any

from app.services import errores
from app.services.importes import formato_importe, formato_porcentaje
from app.services.repositorio import leer_fecha

# Secciones (mismo orden que el menú lateral de Android).
TODOS, CATEGORIAS, TIENDAS, OFERTAS, FAVORITOS, COMPARAR, AVISOS = range(7)
SECCIONES = (
	"Todos los productos",
	"Categorías",
	"Tiendas",
	"Ofertas",
	"Favoritos",
	"Comparar",
	"Avisos",
)
SECCIONES_CON_GRUPOS = (CATEGORIAS, TIENDAS, COMPARAR)

ORDENES = (
	("nombre", "Nombre"),
	("precio", "Precio"),
	("bajada", "Mayor bajada"),
	("cambio", "Último cambio"),
	("alta", "Fecha de alta"),
	("tienda", "Tienda"),
)

DIAS_OFERTA = 7
_MESES = (
	"enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
	"noviembre", "diciembre",
)


def normalizar(texto: str | None) -> str:
	"""Minúsculas y sin acentos (para buscar y ordenar en español)."""
	descompuesto = unicodedata.normalize("NFKD", texto or "")
	return "".join(c for c in descompuesto if not unicodedata.combining(c)).casefold()


# ── Fechas ───────────────────────────────────────────────────────────────────


def fecha_legible(iso: str | None, ahora: datetime | None = None, con_hora: bool = True) -> str:
	"""«2 de noviembre, 21:15» en hora local (con el año si no es el actual)."""
	fecha = leer_fecha(iso)
	if fecha is None:
		return "nunca"
	local = fecha.astimezone()
	actual = (ahora or datetime.now(timezone.utc)).astimezone()
	texto = f"{local.day} de {_MESES[local.month - 1]}"
	if local.year != actual.year:
		texto += f" de {local.year}"
	if con_hora:
		texto += f", {local.hour:02d}:{local.minute:02d}"
	return texto


def fecha_corta(iso: str | None) -> str:
	"""«3 de octubre» (para el resumen hablado)."""
	return fecha_legible(iso, con_hora=False)


# ── Estado y cambio de un producto ───────────────────────────────────────────


def porcentaje_bajada(p: Mapping[str, Any]) -> float:
	"""Bajada respecto al precio anterior en % (0 si no bajó)."""
	actual, anterior = p.get("precio_actual"), p.get("precio_anterior")
	if actual is None or not anterior or actual >= anterior:
		return 0.0
	return (anterior - actual) / anterior * 100.0


def objetivo_alcanzado(p: Mapping[str, Any]) -> bool:
	actual, objetivo = p.get("precio_actual"), p.get("precio_objetivo")
	return actual is not None and objetivo is not None and actual <= objetivo


def en_oferta(p: Mapping[str, Any], ahora: datetime | None = None) -> bool:
	"""Bajó en los últimos 7 días, está en su mínimo histórico o en el precio deseado."""
	actual = p.get("precio_actual")
	if actual is None:
		return False
	if objetivo_alcanzado(p):
		return True
	ahora = ahora or datetime.now(timezone.utc)
	cambio = leer_fecha(p.get("fecha_cambio"))
	if porcentaje_bajada(p) > 0 and cambio is not None and ahora - cambio <= timedelta(days=DIAS_OFERTA):
		return True
	minimo, maximo = p.get("precio_minimo"), p.get("precio_maximo")
	# En el mínimo, pero solo si el precio ha variado alguna vez (si no, todo
	# producto recién añadido estaría «en oferta»).
	return minimo is not None and maximo is not None and minimo < maximo and actual <= minimo


def estado_comprobacion(p: Mapping[str, Any]) -> str:
	"""Estado de la última comprobación (constante de :mod:`errores`)."""
	if not p.get("ultima_comprobacion"):
		return errores.PENDIENTE
	if not p.get("ultimo_error"):
		return errores.CORRECTA
	estado = p.get("estado")
	if estado and estado not in (errores.CORRECTA, errores.PENDIENTE):
		return estado
	return errores.estado_de_error(p.get("ultimo_error"))


def texto_estado(p: Mapping[str, Any], ahora: datetime | None = None) -> str:
	"""Primera columna: «En pausa», «Bloqueada por la tienda», «Agotado», «En oferta»...

	Un bloqueo de la tienda nunca se confunde con «agotado».
	"""
	if not p.get("activo", 1):
		return "En pausa"
	estado = estado_comprobacion(p)
	if estado == errores.BLOQUEADA:
		return "Bloqueada por la tienda"
	if estado == errores.SIN_PRECIO:
		return "Sin precio"
	if estado == errores.SIN_CONEXION:
		return "Sin conexión"
	if estado == errores.ERROR:
		return "Error"
	if not p.get("disponible", 1):
		return "Agotado"
	if estado == errores.PENDIENTE:
		return "Pendiente"
	if en_oferta(p, ahora):
		return "En oferta"
	return "Correcto"


def texto_cambio(p: Mapping[str, Any]) -> str:
	"""«bajó 10,00 € (7 %)», «subió 5,00 € (3 %)» o «sin cambios»; y si toca, «precio deseado alcanzado»."""
	actual, anterior, moneda = p.get("precio_actual"), p.get("precio_anterior"), p.get("moneda")
	if actual is not None and anterior and actual != anterior:
		diferencia = abs(actual - anterior)
		porcentaje = formato_porcentaje(abs(actual - anterior) / anterior * 100)
		verbo = "bajó" if actual < anterior else "subió"
		texto = f"{verbo} {formato_importe(diferencia, moneda)} ({porcentaje} %)"
	else:
		texto = "sin cambios"
	if objetivo_alcanzado(p):
		texto += ", precio deseado alcanzado"
	return texto


def texto_precio(p: Mapping[str, Any]) -> str:
	"""«129,99 €», o «desde 51,95 €» si hay variantes con precios distintos y no se eligió ninguna."""
	texto = formato_importe(p.get("precio_actual"), p.get("moneda"))
	if p.get("desde") and p.get("precio_actual") is not None:
		texto = f"desde {texto}"
	return texto


def columnas_producto(p: Mapping[str, Any], ahora: datetime | None = None) -> list[str]:
	"""Estado, Nombre, Precio, Cambio, Tienda, Categoría, Precio deseado, Última comprobación."""
	objetivo = p.get("precio_objetivo")
	return [
		texto_estado(p, ahora),
		p.get("nombre") or p.get("url") or "",
		texto_precio(p),
		texto_cambio(p),
		p.get("tienda") or "",
		p.get("categoria") or "",
		formato_importe(objetivo, p.get("moneda")) if objetivo is not None else "ninguno",
		fecha_legible(p.get("ultima_comprobacion"), ahora),
	]


# ── Búsqueda, filtros y orden ────────────────────────────────────────────────


def coincide(p: Mapping[str, Any], texto: str) -> bool:
	"""Búsqueda por nombre, tienda, categoría, notas y grupo (sin acentos ni mayúsculas)."""
	palabras = normalizar(texto).split()
	if not palabras:
		return True
	donde = normalizar(" ".join(str(p.get(c) or "") for c in ("nombre", "tienda", "categoria", "notas", "grupo")))
	return all(palabra in donde for palabra in palabras)


def filtrar(
	productos: Iterable[Mapping[str, Any]],
	texto: str = "",
	solo_activos: bool = False,
	solo_error: bool = False,
	solo_agotados: bool = False,
) -> list[Mapping[str, Any]]:
	resultado = []
	for p in productos:
		if solo_activos and not p.get("activo"):
			continue
		if solo_error and not p.get("ultimo_error"):
			continue
		if solo_agotados and p.get("disponible", 1):
			continue
		if coincide(p, texto):
			resultado.append(p)
	return resultado


def _clave_nombre(p: Mapping[str, Any]) -> str:
	return normalizar(p.get("nombre") or p.get("url"))


def ordenar(productos: Iterable[Mapping[str, Any]], orden: str = "nombre") -> list[Mapping[str, Any]]:
	lista = sorted(productos, key=_clave_nombre)
	if orden == "precio":
		lista.sort(key=lambda p: (p.get("precio_actual") is None, p.get("precio_actual") or 0))
	elif orden == "bajada":
		lista.sort(key=lambda p: -porcentaje_bajada(p))
	elif orden == "cambio":
		lista.sort(key=lambda p: p.get("fecha_cambio") or "", reverse=True)
	elif orden == "alta":
		lista.sort(key=lambda p: p.get("fecha_alta") or "", reverse=True)
	elif orden == "tienda":
		lista.sort(key=lambda p: normalizar(p.get("tienda")))
	return lista


def ofertas(productos: Iterable[Mapping[str, Any]], ahora: datetime | None = None) -> list[Mapping[str, Any]]:
	"""Productos en oferta, ordenados por porcentaje de bajada."""
	return sorted((p for p in productos if en_oferta(p, ahora)), key=lambda p: (-porcentaje_bajada(p), _clave_nombre(p)))


def comparar(productos: Iterable[Mapping[str, Any]]) -> list[tuple[Mapping[str, Any], str]]:
	"""Productos de un grupo de más barato a más caro, con la diferencia con el más barato."""
	lista = sorted(productos, key=lambda p: (p.get("precio_actual") is None, p.get("precio_actual") or 0, _clave_nombre(p)))
	if not lista or lista[0].get("precio_actual") is None:
		return [(p, "sin precio") for p in lista]
	barato = lista[0]["precio_actual"]
	resultado = []
	for indice, p in enumerate(lista):
		precio = p.get("precio_actual")
		if precio is None:
			texto = "sin precio"
		elif indice == 0 or precio == barato:
			texto = "el más barato"
		else:
			texto = f"{formato_importe(precio - barato, p.get('moneda'))} más ({formato_porcentaje((precio - barato) / barato * 100)} %)"
		resultado.append((p, texto))
	return resultado


# ── Detalles ─────────────────────────────────────────────────────────────────


def media_historial(historial: Iterable[Mapping[str, Any]]) -> float | None:
	precios = [h["precio"] for h in historial if h.get("precio") is not None]
	return sum(precios) / len(precios) if precios else None


def resumen_hablado(p: Mapping[str, Any]) -> str:
	"""«Ahora 129,99 €. Mínimo 119,00 € el 3 de octubre. Máximo 149,00 €. Está un 9,2 % por encima del mínimo.»"""
	moneda = p.get("moneda")
	actual, minimo, maximo = p.get("precio_actual"), p.get("precio_minimo"), p.get("precio_maximo")
	if actual is None:
		texto = "Todavía no se ha podido leer el precio."
		if not p.get("disponible", 1):
			texto = "Agotado y sin precio conocido."
		return texto
	partes = [f"Ahora {texto_precio(p)}."]
	if not p.get("disponible", 1):
		partes[0] = f"Agotado; último precio {formato_importe(actual, moneda)}."
	if minimo is not None:
		fecha = f" el {fecha_corta(p.get('fecha_minimo'))}" if p.get("fecha_minimo") else ""
		partes.append(f"Mínimo {formato_importe(minimo, moneda)}{fecha}.")
	if maximo is not None:
		partes.append(f"Máximo {formato_importe(maximo, moneda)}.")
	if minimo is not None and minimo > 0:
		if actual <= minimo:
			partes.append("Está en su mínimo histórico.")
		else:
			partes.append(f"Está un {formato_porcentaje((actual - minimo) / minimo * 100)} % por encima del mínimo.")
	return " ".join(partes)


def filas_historial(historial: list[Mapping[str, Any]], moneda: str | None) -> list[list[str]]:
	"""Fecha, precio, cambio con el anterior y disponibilidad (de la más nueva a la más vieja)."""
	filas = []
	anterior: float | None = None
	for h in historial:
		precio = h.get("precio")
		if precio is None or anterior is None:
			cambio = "primera lectura" if anterior is None else "sin precio"
		elif precio == anterior:
			cambio = "sin cambios"
		else:
			verbo = "bajó" if precio < anterior else "subió"
			cambio = f"{verbo} {formato_importe(abs(precio - anterior), moneda)} ({formato_porcentaje(abs(precio - anterior) / anterior * 100)} %)"
		filas.append([
			fecha_legible(h.get("fecha")), formato_importe(precio, moneda), cambio,
			"disponible" if h.get("disponible", 1) else "agotado",
		])
		if precio is not None:
			anterior = precio
	return list(reversed(filas))


def lineas_detalles(p: Mapping[str, Any], historial: list[Mapping[str, Any]]) -> list[tuple[str, str]]:
	"""Pares (etiqueta, valor) de los datos del producto, en orden de lectura."""
	moneda = p.get("moneda")
	media = media_historial(historial)
	minimo = p.get("precio_minimo")
	actual = p.get("precio_actual")
	diferencia = "—"
	if actual is not None and minimo is not None:
		diferencia = "en el mínimo" if actual <= minimo else f"{formato_importe(actual - minimo, moneda)} por encima"
	estado = estado_comprobacion(p)
	lineas = [
		("Nombre", p.get("nombre") or ""),
		("Precio actual", texto_precio(p)),
		("Disponibilidad", "disponible" if p.get("disponible", 1) else "agotado"),
		("Estado", texto_estado(p)),
		("Última comprobación", f"{fecha_legible(p.get('ultima_comprobacion'))} ({errores.TEXTOS_ESTADO.get(estado, estado)})"),
		("Último error", p.get("ultimo_error") or "ninguno"),
		("Tienda", p.get("tienda") or ""),
		("Categoría", p.get("categoria") or ""),
		("Grupo para comparar", p.get("grupo") or "ninguno"),
		("Precio deseado", formato_importe(p.get("precio_objetivo"), moneda) if p.get("precio_objetivo") is not None else "ninguno"),
		("Alerta de bajada", f"{formato_porcentaje(p.get('alerta_porcentaje') or 0)} %" if p.get("alerta_porcentaje") else "cualquier bajada"),
		("Cambio", texto_cambio(p)),
		("Precio inicial", formato_importe(p.get("precio_inicial"), moneda)),
		("Precio mínimo", f"{formato_importe(minimo, moneda)} ({fecha_legible(p.get('fecha_minimo'))})" if minimo is not None else "—"),
		("Precio máximo", f"{formato_importe(p.get('precio_maximo'), moneda)} ({fecha_legible(p.get('fecha_maximo'))})" if p.get("precio_maximo") is not None else "—"),
		("Media del historial", formato_importe(media, moneda) if media is not None else "—"),
		("Diferencia con el mínimo", diferencia),
		("Origen del precio", p.get("origen_precio") or "—"),
		("Confianza", {"alta": "alta", "media": "media (detectado automáticamente)", "baja": "baja (detectado automáticamente)"}.get(
			p.get("confianza") or "", "—")),
		("Variante", p.get("variante") or ("sin elegir (precio «desde»)" if p.get("desde") else "—")),
		("Posición del precio", "elegida por ti en la página" if p.get("huella_selector") else (
			"selector propio" if p.get("selector_precio") else "automática")),
		("Fecha de alta", fecha_legible(p.get("fecha_alta"))),
		("Dirección", p.get("url") or ""),
		("Notas", p.get("notas") or ""),
	]
	if not p.get("activo", 1):
		lineas.insert(3, ("Comprobación", "en pausa"))
	return lineas
