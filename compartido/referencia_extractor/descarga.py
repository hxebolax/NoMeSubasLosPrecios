"""Descarga con cabeceras de Chrome, como pide la especificación.

Solo biblioteca estándar. Sigue redirecciones, guarda cookies en memoria y
descomprime gzip/deflate. No intenta saltarse bloqueos: si la tienda responde
403, 429, 202 o una página de verificación, lo devuelve tal cual.
"""
import gzip
import http.cookiejar
import urllib.error
import urllib.request
import zlib

CABECERAS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.5",
    "Accept-Encoding": "gzip, deflate",
}

TEXTOS_BLOQUEO = ("captcha", "cf-chl", "challenge-platform", "just a moment",
                  "attention required", "awswafcookiedomainlist", "access denied",
                  "verify you are human", "comprueba que eres humano")


def crear_abridor():
    tarro = http.cookiejar.CookieJar()
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(tarro))


def _descomprimir(datos, codificacion):
    codificacion = (codificacion or "").lower()
    if codificacion == "gzip":
        return gzip.decompress(datos)
    if codificacion == "deflate":
        try:
            return zlib.decompress(datos)
        except zlib.error:
            return zlib.decompress(datos, -zlib.MAX_WBITS)
    return datos


def descargar(url, abridor=None, espera=20):
    """Devuelve (estado, url_final, html). estado es el código HTTP o 0 si falla la red."""
    abridor = abridor or crear_abridor()
    peticion = urllib.request.Request(url, headers=CABECERAS)
    try:
        with abridor.open(peticion, timeout=espera) as r:
            datos = _descomprimir(r.read(), r.headers.get("Content-Encoding"))
            juego = r.headers.get_content_charset() or "utf-8"
            return r.status, r.geturl(), datos.decode(juego, errors="replace")
    except urllib.error.HTTPError as e:
        try:
            datos = _descomprimir(e.read(), e.headers.get("Content-Encoding"))
            texto = datos.decode("utf-8", errors="replace")
        except Exception:
            texto = ""
        return e.code, url, texto
    except Exception as e:  # red, DNS, tiempo agotado
        return 0, url, f"ERROR: {e}"


def parece_bloqueo(estado, html):
    if estado in (403, 429, 202):
        return True
    bajo = html[:20000].lower()
    return any(t in bajo for t in TEXTOS_BLOQUEO) and len(html) < 60000
