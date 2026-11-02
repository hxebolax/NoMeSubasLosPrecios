"""Lectura de importes, idéntica a la sección «Importes de texto» de ESPECIFICACION.md."""
import re

PATRON_IMPORTE = re.compile(r"\d+(?:[.,'’]\d+|[   ]\d{3}(?!\d))*")
PATRON_MAQUINA = re.compile(r"^\d+(\.\d{1,2})?$")


def analizar_importe(texto):
    if texto is None:
        return None
    m = PATRON_IMPORTE.search(str(texto))
    if not m:
        return None
    s = re.sub(r"[   '’]", "", m.group(0))
    if "." in s and "," in s:
        dec = "." if s.rfind(".") > s.rfind(",") else ","
        mil = "," if dec == "." else "."
        s = s.replace(mil, "").replace(dec, ".")
    elif "." in s or "," in s:
        sep = "." if "." in s else ","
        if s.count(sep) > 1:
            s = s.replace(sep, "")
        else:
            entero, resto = s.split(sep)
            s = entero + resto if len(resto) == 3 else entero + "." + resto
    try:
        v = round(float(s), 2)
    except ValueError:
        return None
    return v if v > 0 else None


def importe_de_maquina(valor):
    """Número JSON tal cual; texto "1299.99" en formato de máquina; si no, analizar_importe."""
    if isinstance(valor, bool) or valor is None:
        return None
    if isinstance(valor, (int, float)):
        return round(float(valor), 2) if valor > 0 else None
    t = str(valor).strip()
    if PATRON_MAQUINA.match(t):
        v = round(float(t), 2)
        return v if v > 0 else None
    return analizar_importe(t)
