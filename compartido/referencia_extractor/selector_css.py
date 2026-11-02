"""Genera un selector CSS estable para el elemento que elige el usuario, y lo valida.

Orden de preferencia (inspirado en @medv/finder y en el generador de Playwright):
  1. itemprop="price" / data-price-type="finalPrice" / data-* semánticos (data-test, data-testid, data-qa...)
  2. #id estable
  3. etiqueta + 1 o 2 clases estables
  4. lo anterior precedido de un ancestro estable (id o clase): «ancestro descendiente»
  5. último recurso: ruta con :nth-of-type desde el ancestro estable más cercano
Siempre se comprueba que el selector devuelve UN solo elemento, que es el elegido,
y que su importe es el mismo.
"""
import re

from importes import analizar_importe, importe_de_maquina

# Nombres generados por herramientas (no sobreviven a una nueva versión de la web)
RE_GENERADO = re.compile(
    r"^(?:css|sc|jsx|emotion|e|tw|svelte|astro|chakra|mui|Mui[A-Za-z]*|makeStyles|styled|ng-tns|ember|v|data-v)-[A-Za-z0-9_-]*\d[A-Za-z0-9_-]*$"  # css-1x2y3z, sc-abc123, jsx-123, svelte-x1y2
    r"|^[A-Za-z][\w-]*_{1,2}(?=[A-Za-z0-9-]*\d)[A-Za-z0-9-]{5,}$"  # CSS Modules: Price_price__3x9Yz, styles_box_a1B2c
    r"|^_?(?=[a-zA-Z]*\d)(?=\d*[a-zA-Z])[a-zA-Z0-9]{5,8}$"         # hash corto mezclado: a1b2c3, _3xYz9
    r"|[:\[\]/!@]"                                                  # Tailwind: md:text-lg, w-[12px], w-1/2
    r"|\d{3,}"                                                      # tres o más cifras seguidas
)
# Clases de estado o de maquetación que cambian con la interacción o el diseño
RE_ESTADO = re.compile(r"^(?:is-|has-|js-is-|active|selected|current-?item|open|closed|hover|focus|visible|hidden|loaded|lazy|show|fade|in|d-|col-|row|flex|grid|mt-|mb-|ml-|mr-|pt-|pb-|p-|m-|text-|font-|bg-|w-|h-|swiper-slide|slick-)", re.I)
ATRIBUTOS_ESTABLES = ("itemprop", "data-price-type", "data-test", "data-testid", "data-test-id", "data-qa", "data-cy",
                      "data-role", "data-element", "data-hook", "data-automation", "data-ui", "name")


def palabra_estable(nombre):
    if not nombre or len(nombre) < 3 or len(nombre) > 60:
        return False
    if RE_GENERADO.search(nombre) or RE_ESTADO.search(nombre):
        return False
    # cada trozo debe parecer una palabra: sin 4 consonantes seguidas (idea de finder)
    for trozo in re.split(r"[-_]+|(?<=[a-z])(?=[A-Z])", nombre):
        if trozo and re.search(r"[^aeiouy0-9]{5,}", trozo.lower()):
            return False
    return True


def escapar(v):
    return v.replace("\\", "\\\\").replace('"', '\\"')


def clases_estables(el):
    return [c for c in (el.get("class") or []) if palabra_estable(c)]


def id_estable(el):
    i = el.get("id")
    return i if i and palabra_estable(i) and re.fullmatch(r"[A-Za-z][\w-]*", i) else None


def partes_de(el):
    """Selectores candidatos para UN elemento, de más a menos preferido."""
    out = []
    for a in ATRIBUTOS_ESTABLES:
        v = el.get(a)
        if isinstance(v, str) and v and len(v) < 60 and palabra_estable(v.replace(" ", "-")):
            out.append('%s[%s="%s"]' % (el.name, a, escapar(v)))
    i = id_estable(el)
    if i:
        out.append("#" + i)
    cs = clases_estables(el)
    for c in cs:
        out.append("%s.%s" % (el.name, c))
    for k in range(len(cs)):
        for j in range(k + 1, len(cs)):
            out.append("%s.%s.%s" % (el.name, cs[k], cs[j]))
    return out


def unico(sopa, sel, el):
    try:
        r = sopa.select(sel, limit=2)
    except Exception:
        return False
    return len(r) == 1 and r[0] is el


def nth_of_type(el):
    hermanos = [h for h in el.parent.find_all(el.name, recursive=False)] if el.parent else [el]
    if len(hermanos) == 1:
        return el.name
    return "%s:nth-of-type(%d)" % (el.name, hermanos.index(el) + 1)


def atributo_de_valor(el):
    if el.get("content") and importe_de_maquina(el.get("content")):
        return "content"
    for a in ("data-price-amount", "data-price", "data-product-price", "data-price-value"):
        if el.get(a):
            return a
    return None


def generar_selector(el, sopa):
    """Devuelve (selector, atributo o None)."""
    atributo = atributo_de_valor(el)
    propias = partes_de(el)
    for s in propias:
        if unico(sopa, s, el):
            return s, atributo
    # ancestros estables (hasta 8 niveles)
    p = el.parent
    nivel = 0
    while p is not None and getattr(p, "name", None) not in (None, "[document]", "html") and nivel < 8:
        for pa in partes_de(p)[:6]:
            for s in propias + [el.name]:
                sel = "%s %s" % (pa, s)
                if unico(sopa, sel, el):
                    return sel, atributo
        p = p.parent
        nivel += 1
    # ancestro estable cercano (hasta 5 niveles) + ruta corta con > y :nth-of-type
    p = el.parent
    tramo = [nth_of_type(el)]
    nivel = 0
    while p is not None and getattr(p, "name", None) not in (None, "[document]", "html", "body") and nivel < 5:
        for pa in partes_de(p)[:6]:
            sel = pa + " > " + " > ".join(tramo)
            if unico(sopa, sel, el):
                return sel, atributo
        tramo.insert(0, nth_of_type(p))
        p = p.parent
        nivel += 1
    # Si no hay nada único, vale un selector cuyo PRIMER resultado sea el elegido
    # (la app usa el primer elemento que dé un importe válido).
    for s in propias:
        try:
            r = sopa.select(s, limit=1)
        except Exception:
            continue
        if r and r[0] is el:
            return s, atributo
    # último recurso: ruta nth-of-type desde el ancestro con id o desde body
    ruta = []
    p = el
    while p is not None and p.name not in ("body", "html", "[document]"):
        i = id_estable(p)
        if i and p is not el:
            ruta.append("#" + i)
            break
        ruta.append(nth_of_type(p))
        p = p.parent
    sel = " > ".join(reversed(ruta))
    if not sel.startswith("#"):
        sel = "body > " + sel
    return sel, atributo


def validar_selector(sopa, selector, atributo, esperado):
    """Válido si devuelve un único elemento y su importe es el esperado."""
    try:
        r = sopa.select(selector)
    except Exception:
        return False
    if len(r) != 1:
        return False
    v = importe_de_maquina(r[0].get(atributo)) if atributo else analizar_importe(r[0].get_text(" "))
    return v == esperado
