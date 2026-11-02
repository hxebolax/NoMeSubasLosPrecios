"""Lectura y escritura de importes y porcentajes en formato español.

Es el contrato común con la app de Android (``analizarImporte`` e
``importeDeMaquina``): los vectores de ``compartido/pruebas/importes.json``
deben dar exactamente el mismo resultado en las dos. Por eso la regla de
separadores está escrita paso a paso tal como la describe la especificación,
sin «mejoras» propias que harían divergir a las dos apps.

Sin wx: se prueba con pytest sin interfaz.
"""

from __future__ import annotations

import math
import re
from decimal import ROUND_HALF_UP, Decimal

# Dígitos separados por punto, coma o apóstrofo, o por un espacio (normal,
# duro U+00A0 o fino U+202F) seguido de exactamente tres dígitos. Así un punto
# final de frase no cuenta («129,99.» → 129,99).
_PATRON_IMPORTE = re.compile("\\d+(?:[.,'\u2019]\\d+|[ \u00a0\u202f]\\d{3}(?!\\d))*")
# Formato de máquina (JSON-LD como texto, atributos content): punto decimal.
_PATRON_MAQUINA = re.compile(r"^\d+(\.\d{1,2})?$")
_SEPARADORES_MILES = str.maketrans("", "", " \u00a0\u202f'\u2019")

# Símbolo con el que se escribe cada moneda (detrás del número, como en España).
SIMBOLOS_MONEDA = {"EUR": "€", "USD": "$", "GBP": "£"}
# Signo menos tipográfico (U+2212) de los textos de los avisos: «−19,10 €».
MENOS = "\u2212"


def redondeo_comercial(valor: float, decimales: int = 2) -> float:
	"""Redondea «a la mitad hacia arriba» sobre la representación decimal del número.

	``round()`` de Python redondea al par y trabaja sobre el binario
	(``round(2.675, 2)`` da 2.67); Android usa redondeo comercial. Con
	``Decimal(repr(x))`` las dos apps dan el mismo céntimo.
	"""
	cuanto = Decimal(1).scaleb(-decimales)
	return float(Decimal(repr(float(valor))).quantize(cuanto, rounding=ROUND_HALF_UP))


def analizar_importe(texto: str | None) -> float | None:
	"""Devuelve el primer importe de ``texto`` o ``None`` si no hay ninguno mayor que 0.

	Reglas (las mismas que Android):

	1. Primera coincidencia de la expresión regular de importes.
	2. Se quitan espacios y apóstrofos (separadores de miles).
	3. Con punto y coma a la vez, el que aparece el último es el decimal.
	4. Con un solo tipo: si aparece más de una vez, o una vez seguido de
	   exactamente tres dígitos, es de miles; si no, es decimal.
	5. Sin dígitos o resultado ≤ 0 → ``None``. 6. Redondeo a dos decimales.
	"""
	if not texto:
		return None
	coincidencia = _PATRON_IMPORTE.search(str(texto))
	if coincidencia is None:
		return None
	cadena = coincidencia.group(0).translate(_SEPARADORES_MILES)
	if "." in cadena and "," in cadena:
		decimal = "." if cadena.rfind(".") > cadena.rfind(",") else ","
		miles = "," if decimal == "." else "."
		cadena = cadena.replace(miles, "").replace(decimal, ".")
	else:
		separador = "." if "." in cadena else ("," if "," in cadena else "")
		if separador:
			partes = cadena.split(separador)
			if len(partes) > 2 or len(partes[1]) == 3:
				cadena = "".join(partes)
			else:
				cadena = partes[0] + "." + partes[1]
	try:
		valor = float(cadena)
	except ValueError:
		return None
	if not math.isfinite(valor) or valor <= 0:
		return None
	return redondeo_comercial(valor)


def importe_de_maquina(valor: object) -> float | None:
	"""Lee un importe de JSON-LD o de un atributo ``content``.

	Un número JSON se usa tal cual. Un texto en formato de máquina
	(``"1299.99"``, ``"12.5"``, ``"1299"``) se lee con punto decimal; cualquier
	otro texto pasa por :func:`analizar_importe` (``"1.299"`` → 1299).
	"""
	if valor is None or isinstance(valor, bool):
		return None
	if isinstance(valor, (int, float)):
		numero = float(valor)
		return redondeo_comercial(numero) if math.isfinite(numero) and numero > 0 else None
	texto = str(valor).strip()
	if not texto:
		return None
	if _PATRON_MAQUINA.match(texto):
		numero = float(texto)
		return redondeo_comercial(numero) if numero > 0 else None
	return analizar_importe(texto)


def redondear(valor: float | None) -> float | None:
	"""Redondea a céntimos (como se guarda en la base de datos)."""
	return None if valor is None else redondeo_comercial(valor)


def formato_numero(valor: float, decimales: int = 2) -> str:
	"""``1299.99`` → ``"1.299,99"`` (miles con punto y decimales con coma)."""
	texto = f"{abs(valor):,.{decimales}f}".replace(",", "\u0001").replace(".", ",").replace("\u0001", ".")
	return ("-" if valor < 0 else "") + texto


def formato_importe(valor: float | None, moneda: str | None = "EUR") -> str:
	"""Importe para leer: ``"1.299,99 €"``, nunca ``"€1299.99"``.

	El símbolo va detrás con un espacio normal (así lo escriben las dos apps y
	el lector de pantalla lo lee como «euros»). Sin precio: «sin precio».
	"""
	if valor is None:
		return "sin precio"
	codigo = (moneda or "EUR").upper()
	simbolo = SIMBOLOS_MONEDA.get(codigo, codigo)
	return f"{formato_numero(valor)} {simbolo}"


def formato_porcentaje(valor: float) -> str:
	"""Porcentaje con una decimal y coma (``7,5``); sin decimal si es entero (``10``).

	Devuelve solo el número: el que llama añade « %» (los avisos ponen el
	signo delante y el espacio antes de «%»).
	"""
	redondeado = redondeo_comercial(abs(valor), 1)
	if redondeado == int(redondeado):
		return str(int(redondeado))
	return f"{redondeado:.1f}".replace(".", ",")


def porcentaje_cambio(anterior: float, nuevo: float) -> float:
	"""Cambio en % de ``anterior`` a ``nuevo``: ``(nuevo - anterior) / anterior × 100``."""
	if not anterior:
		return 0.0
	return (nuevo - anterior) / anterior * 100.0
