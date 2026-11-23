"""Prototipo de extractor genérico de precios (sin JavaScript).

Orden (ver investigacion-extractor-generico.md):
  0. (ya existentes) JSON-LD Product, metadatos y microdatos -> funcion extraer_basico()
  1. Datos embebidos de plataforma: Shopify, WooCommerce, PrestaShop, Magento 2,
     Salesforce Commerce Cloud, VTEX, BigCommerce.
  2. Estado de aplicación: __NEXT_DATA__, __NUXT_DATA__, __INITIAL_STATE__,
     __PRELOADED_STATE__, __APOLLO_STATE__, <script type="application/json">.
  3. Señales de analítica: dataLayer GA4/UA, gtag, píxel de Facebook, Klaviyo,
     ecomm_totalvalue, twitter:label1/data1.
  4. Heurística de candidatos visibles con puntuación y umbral.
  5. Decisión: aceptar, o devolver candidatos para que elija el usuario.

Solo biblioteca estándar + BeautifulSoup 4 (html.parser).
"""
import html as html_mod
import json
import re
from urllib.parse import urlparse, parse_qs, unquote

from bs4 import BeautifulSoup, Comment, NavigableString, Tag

from importes import analizar_importe, importe_de_maquina

# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------

def numero_de_maquina(v):
    """Valor de un campo de máquina (JSON, data-price-amount, content).
    Más estricto que importe_de_maquina: "12.990" se lee 12.99, no 12990."""
    if isinstance(v, bool) or v is None:
        return None
    if isinstance(v, (int, float)):
        return round(float(v), 2) if v > 0 else None
    t = str(v).strip()
    if re.fullmatch(r"\d+(?:\.\d+)?", t):
        f = round(float(t), 2)
        return f if f > 0 else None
    return importe_de_maquina(t)


def objeto_equilibrado(texto, inicio):
    """Devuelve el texto de {...} o [...] que empieza en texto[inicio],
    respetando cadenas entre comillas. None si no se cierra."""
    if inicio >= len(texto) or texto[inicio] not in "{[":
        return None
    pila = []
    en_cadena = None
    escape = False
    for i in range(inicio, min(len(texto), inicio + 3_000_000)):
        c = texto[i]
        if en_cadena:
            if escape:
                escape = False
            elif c == "\\":
                escape = True
            elif c == en_cadena:
                en_cadena = None
            continue
        if c in "\"'`":
            en_cadena = c
        elif c in "{[":
            pila.append(c)
        elif c in "}]":
            if not pila:
                return None
            pila.pop()
            if not pila:
                return texto[inicio:i + 1]
    return None


def json_tras(texto, patron, flags=re.S):
    """Busca patron (que termina justo antes de { o [) y devuelve los objetos JSON que lo siguen."""
    salida = []
    for m in re.finditer(patron, texto, flags):
        j = m.end()
        while j < len(texto) and texto[j] in " \t\r\n":
            j += 1
        bloque = objeto_equilibrado(texto, j)
        if not bloque:
            continue
        obj = cargar_json_flexible(bloque)
        if obj is not None:
            salida.append(obj)
    return salida


def cargar_json_flexible(bloque):
    try:
        return json.loads(bloque)
    except Exception:
        pass
    # Objeto literal de JavaScript sencillo: comillas simples y claves sin comillas.
    t = re.sub(r"(?<=[{,])\s*([A-Za-z_$][\w$]*)\s*:", r'"\1":', bloque)
    t = re.sub(r"'([^'\\]*(?:\\.[^'\\]*)*)'", lambda m: json.dumps(m.group(1)), t)
    t = re.sub(r",\s*([}\]])", r"\1", t)
    try:
        return json.loads(t)
    except Exception:
        return None


def recorrer(obj, ruta=()):
    """Genera (ruta, dict) para cada diccionario del árbol."""
    if isinstance(obj, dict):
        yield ruta, obj
        for k, v in obj.items():
            yield from recorrer(v, ruta + (str(k),))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from recorrer(v, ruta + (str(i),))


def norm(texto):
    return re.sub(r"\s+", " ", texto or "").strip()


class Candidato:
    def __init__(self, valor, origen, puntos=0.0, texto="", elemento=None, motivos=None, moneda=None):
        self.valor = valor
        self.origen = origen
        self.puntos = puntos
        self.texto = texto
        self.elemento = elemento
        self.motivos = motivos or []
        self.moneda = moneda

    def como_dict(self):
        return {"valor": self.valor, "origen": self.origen, "puntos": round(self.puntos, 1),
                "texto": self.texto[:80], "motivos": self.motivos, "moneda": self.moneda}


# ---------------------------------------------------------------------------
# Paso 0: lo que la especificación ya hace (versión compacta para comparar)
# ---------------------------------------------------------------------------

def _ofertas(o):
    if isinstance(o, list):
        for x in o:
            yield from _ofertas(x)
    elif isinstance(o, dict):
        if "offers" in o and o.get("@type") == "AggregateOffer":
            yield o
            yield from _ofertas(o["offers"])
        else:
            yield o


def extraer_basico(sopa):
    for s in sopa.find_all("script", type=re.compile("ld\\+json", re.I)):
        try:
            datos = json.loads(s.string or s.get_text() or "")
        except Exception:
            continue
        for _, d in recorrer(datos):
            t = d.get("@type")
            tipos = t if isinstance(t, list) else [t]
            if "Product" not in tipos or "offers" not in d:
                continue
            precios = []
            for of in _ofertas(d["offers"]):
                v = of.get("price")
                if v in (None, ""):
                    v = of.get("lowPrice")
                if v in (None, "") and of.get("priceSpecification"):
                    ps = of["priceSpecification"]
                    ps = ps[0] if isinstance(ps, list) and ps else ps
                    v = ps.get("price") if isinstance(ps, dict) else None
                p = importe_de_maquina(v)
                if p:
                    precios.append((p, of.get("priceCurrency")))
            if precios:
                p, mon = min(precios)
                return p, mon, "json-ld"
    for prop in ("product:price:amount", "og:price:amount"):
        m = sopa.find("meta", attrs={"property": prop})
        if m and importe_de_maquina(m.get("content")):
            return importe_de_maquina(m.get("content")), None, "meta " + prop
    m = sopa.find("meta", attrs={"itemprop": "price"})
    if m and importe_de_maquina(m.get("content")):
        return importe_de_maquina(m.get("content")), None, "meta itemprop"
    e = sopa.find(attrs={"itemprop": "price"})
    if e:
        v = importe_de_maquina(e.get("content")) if e.get("content") else analizar_importe(e.get_text(" "))
        if v:
            return v, None, "microdatos"
    return None, None, None


# ---------------------------------------------------------------------------
# Detección de plataforma
# ---------------------------------------------------------------------------

FIRMAS = [
    ("shopify", r"cdn\.shopify\.com|ShopifyAnalytics|Shopify\.shop\s*="),
    ("woocommerce", r"woocommerce-Price-amount|wp-content/plugins/woocommerce|class=\"[^\"]*woocommerce"),
    ("prestashop", r"var prestashop\s*=|prestashop\s*=\s*\{|/modules/ps_|PrestaShop"),
    ("magento", r"x-magento-init|data-mage-init|Magento_[A-Z]|mage/cookies"),
    ("sfcc", r"/on/demandware\.|demandware\.static|dwvar_"),
    ("vtex", r"vteximg\.com|vtexassets\.com|data-varname=\"__STATE__\"|skuJson_\d|vtex\.events"),
    ("bigcommerce", r"BCData\s*=|cdn\d*\.bigcommerce\.com"),
    ("shopware", r"Shopware|sw-plugin|data-shopware"),
    ("wix", r"static\.wixstatic\.com|wix-warmup-data"),
    ("next", r"id=\"__NEXT_DATA__\""),
    ("nuxt", r"__NUXT__|id=\"__NUXT_DATA__\""),
]


def detectar_plataformas(html):
    return [n for n, p in FIRMAS if re.search(p, html)]


# ---------------------------------------------------------------------------
# Paso 1: datos embebidos de plataforma
# ---------------------------------------------------------------------------

def variante_de_url(url):
    if not url:
        return None
    q = parse_qs(urlparse(url).query)
    return (q.get("variant") or [None])[0]


def plataforma_shopify(html, sopa, url):
    res = []
    var_id = variante_de_url(url)
    # a) var meta = {"product":{...,"variants":[{"id":..,"price":12999}]}}  (céntimos)
    for meta in json_tras(html, r"var\s+meta\s*=\s*(?=\{)") + json_tras(html, r"ShopifyAnalytics\.meta\s*=\s*(?=\{)"):
        prod = meta.get("product") if isinstance(meta, dict) else None
        if not isinstance(prod, dict) or not prod.get("variants"):
            continue
        vs = prod["variants"]
        elegidas = [v for v in vs if var_id and str(v.get("id")) == var_id] or vs
        precios = sorted({v["price"] / 100 for v in elegidas if isinstance(v.get("price"), (int, float)) and v["price"] > 0})
        if precios:
            res.append(Candidato(round(precios[0], 2), "shopify meta (céntimos)",
                                 motivos=["desde" if len(precios) > 1 else "variante única o elegida"]))
    # b) <script type="application/json" data-selected-variant> / data-product-json / id="ProductJson-..."
    for s in sopa.find_all("script"):
        a = s.attrs
        if not ("data-selected-variant" in a or "data-product-json" in a or str(a.get("id", "")).startswith("ProductJson")):
            continue
        try:
            d = json.loads(s.string or "")
        except Exception:
            continue
        if isinstance(d, dict) and "variants" in d:
            vs = [v for v in d["variants"] if not var_id or str(v.get("id")) == var_id] or d["variants"]
            p = min((v["price"] for v in vs if isinstance(v.get("price"), int)), default=None)
        else:
            p = d.get("price") if isinstance(d, dict) else None
        if isinstance(p, int) and p > 0:
            res.append(Candidato(round(p / 100, 2), "shopify product-json (céntimos)"))
    return res


def bloque_principal_woo(sopa):
    for sel in ("div.product .summary", "div[id^=product-] .summary", ".single-product-wrapper .summary",
                ".product-summary", ".wd-single-price", ".elementor-widget-woocommerce-product-price",
                ".elementor-widget-wd_single_product_price"):
        b = sopa.select_one(sel)
        if b:
            return b
    return None


def precio_woo_en(bloque):
    """Dentro de p.price: <ins> gana a <del>; un rango «a – b» da el mínimo (desde)."""
    caja = bloque if "price" in (bloque.get("class") or []) else (bloque.select_one("p.price, span.price") or bloque)
    ins = caja.select("ins .woocommerce-Price-amount")
    cantidades = ins or [a for a in caja.select(".woocommerce-Price-amount") if not a.find_parent("del")]
    vals = [analizar_importe(a.get_text(" ")) for a in cantidades]
    vals = [v for v in vals if v]
    if not vals:
        return None, None
    return min(vals), ("rango desde" if len(set(vals)) > 1 else "")


def plataforma_woocommerce(html, sopa, url):
    res = []
    form = sopa.select_one("form.variations_form[data-product_variations]")
    if form:
        try:
            variaciones = json.loads(form["data-product_variations"])
        except Exception:
            variaciones = False  # "false" cuando hay demasiadas variaciones (se cargan por AJAX)
        if isinstance(variaciones, list) and variaciones:
            q = parse_qs(urlparse(url or "").query)
            elegidas = [v for v in variaciones
                        if q and all(q.get(k, [None])[0] in (None, val, "") or val == "" for k, val in v.get("attributes", {}).items())
                        and any(k in q for k in v.get("attributes", {}))]
            pool = elegidas or variaciones
            disponibles = [v for v in pool if v.get("is_in_stock", True)] or pool
            precios = sorted({numero_de_maquina(v.get("display_price")) for v in disponibles} - {None})
            if precios:
                res.append(Candidato(precios[0], "woocommerce variaciones",
                                     motivos=["variante de la URL" if elegidas else ("desde" if len(precios) > 1 else "todas iguales")]))
    # Precio simple: el primer «.price» que sigue al título del producto (no el del menú
    # o los relacionados, que en muchas plantillas van ANTES en el HTML).
    titulo = sopa.select_one("h1.product_title, .product_title, h1.entry-title") or sopa.find("h1")
    b = None
    if titulo is not None:
        anc_t = set(id(x) for x in [titulo] + ancestros(titulo))
        for n, e in enumerate(titulo.find_all_next(class_="price")):
            if n > 30:
                break
            if e.name in ("p", "span", "div") and e.select_one(".woocommerce-Price-amount") and \
                    not any(es_zona_ajena(a, anc_t) for a in ancestros(e)):
                b = e
                break
    if b is None:
        b = bloque_principal_woo(sopa)
    if b:
        v, nota = precio_woo_en(b)
        if v:
            res.append(Candidato(v, "woocommerce .summary .price", motivos=[nota] if nota else []))
    return res


def plataforma_prestashop(html, sopa, url):
    res = []
    d = sopa.select_one("#product-details[data-product]")
    if d:
        try:
            datos = json.loads(d["data-product"])
            v = numero_de_maquina(datos.get("price_amount")) or analizar_importe(datos.get("price"))
            if v:
                res.append(Candidato(v, "prestashop data-product price_amount"))
        except Exception:
            pass
    e = sopa.select_one(".product-prices .current-price [content], .current-price-value[content], .current-price [itemprop=price][content]")
    if e:
        v = numero_de_maquina(e.get("content"))
        if v:
            res.append(Candidato(v, "prestashop .current-price content"))
    e = sopa.select_one("#our_price_display")  # PrestaShop 1.6
    if e:
        v = numero_de_maquina(e.get("content")) if e.get("content") else analizar_importe(e.get_text())
        if v:
            res.append(Candidato(v, "prestashop 1.6 #our_price_display"))
    m = re.search(r"var\s+productPrice\s*=\s*['\"]?([\d.]+)", html)  # PrestaShop 1.6
    if m and numero_de_maquina(m.group(1)):
        res.append(Candidato(numero_de_maquina(m.group(1)), "prestashop 1.6 productPrice"))
    return res


def plataforma_magento(html, sopa, url):
    res = []
    principal = sopa.select_one(".product-info-main, .product-info-price, #maincontent .product-info-main")
    if principal:
        for e in principal.select('[data-price-type="finalPrice"][data-price-amount]'):
            if e.find_parent(class_=re.compile(r"old-price|tier")):
                continue
            v = numero_de_maquina(e.get("data-price-amount"))
            if v:
                res.append(Candidato(v, "magento finalPrice (bloque principal)"))
                break
    # jsonConfig de productos configurables: optionPrices.*.finalPrice.amount
    for cfg in json_tras(html, r'"jsonConfig"\s*:\s*(?=\{)'):
        op = cfg.get("optionPrices") if isinstance(cfg, dict) else None
        if isinstance(op, dict):
            precios = sorted({numero_de_maquina(x.get("finalPrice", {}).get("amount")) for x in op.values()} - {None})
            if precios:
                res.append(Candidato(precios[0], "magento jsonConfig optionPrices",
                                     motivos=["desde" if len(precios) > 1 else ""]))
        break
    return res


def plataforma_sfcc(html, sopa, url):
    res = []
    bloque = sopa.select_one(".product-detail[data-pid], .pdp-main, .product-detail, #product-content")
    if bloque:
        e = bloque.select_one(".prices .price .sales .value[content], .prices .sales .value[content], .price-sales")
        if e:
            v = numero_de_maquina(e.get("content")) if e.get("content") else analizar_importe(e.get_text())
            if v:
                res.append(Candidato(v, "sfcc .prices .sales .value"))
    return res


def plataforma_vtex(html, sopa, url):
    res = []
    for sku in json_tras(html, r"var\s+skuJson_\d+\s*=\s*(?=\{)"):
        precios = sorted({s["bestPrice"] / 100 for s in sku.get("skus", [])
                          if s.get("available") and isinstance(s.get("bestPrice"), (int, float)) and s["bestPrice"] > 0})
        if precios:
            res.append(Candidato(round(precios[0], 2), "vtex skuJson bestPrice (céntimos)"))
    for d in json_tras(html, r"vtex\.events\.addData\(\s*(?=\{)"):
        v = numero_de_maquina(d.get("productPriceTo")) if isinstance(d, dict) else None
        if v:
            res.append(Candidato(v, "vtex addData productPriceTo"))
    t = sopa.find("template", attrs={"data-varname": "__STATE__"})
    if t:
        sc = t.find("script")
        cuerpo = (sc.string if sc is not None else None) or t.decode_contents()
        try:
            estado = json.loads(cuerpo[cuerpo.find("{"):cuerpo.rfind("}") + 1])
        except Exception:
            estado = {}
        precios = []
        for clave, o in estado.items():
            if isinstance(o, dict) and "commertialOffer" in clave and o.get("AvailableQuantity", 1) > 0:
                v = numero_de_maquina(o.get("Price"))
                if v:
                    precios.append(v)
        if precios:
            res.append(Candidato(min(precios), "vtex __STATE__ commertialOffer.Price"))
    return res


def plataforma_bigcommerce(html, sopa, url):
    res = []
    for d in json_tras(html, r"var\s+BCData\s*=\s*(?=\{)"):
        try:
            p = d["product_attributes"]["price"]
            v = numero_de_maquina((p.get("with_tax") or p.get("without_tax"))["value"])
            if v:
                res.append(Candidato(v, "bigcommerce BCData price.with_tax" if p.get("with_tax") else "bigcommerce BCData sin IVA"))
        except Exception:
            pass
    return res


PLATAFORMAS = {
    "shopify": plataforma_shopify,
    "woocommerce": plataforma_woocommerce,
    "prestashop": plataforma_prestashop,
    "magento": plataforma_magento,
    "sfcc": plataforma_sfcc,
    "vtex": plataforma_vtex,
    "bigcommerce": plataforma_bigcommerce,
}

# ---------------------------------------------------------------------------
# Paso 2: estado de aplicación (Next, Nuxt 3, Redux, Apollo, application/json)
# ---------------------------------------------------------------------------

CLAVES_PRECIO = ("price", "Price", "salePrice", "sellingPrice", "finalPrice", "currentPrice", "priceValue",
                 "special_price", "final_price", "precio", "pvp", "amount")
CLAVES_NOMBRE = ("name", "Name", "title", "productName", "nombre")
CLAVES_EXCLUIR = re.compile(r"old|was|list|regular|original|compare|before|strike|base|shipping|tax|unit|perUnit|min|max|anterior", re.I)


def _precio_de_objeto(d):
    for k in CLAVES_PRECIO:
        if k not in d:
            continue
        v = d[k]
        if isinstance(v, dict):  # {"amount": 129.99} / {"value": ...} / {"centAmount": 12999}
            if "centAmount" in v:
                return numero_de_maquina(v["centAmount"] / 100 if isinstance(v["centAmount"], (int, float)) else None)
            for kk in ("amount", "value", "current", "final", "sale", "price"):
                if kk in v and not isinstance(v[kk], (dict, list)):
                    return numero_de_maquina(v[kk])
            continue
        if isinstance(v, (int, float, str)) and not isinstance(v, bool):
            return numero_de_maquina(v)
    for k, v in d.items():
        if re.search(r"(?i)(price|precio).*(cents|centimos)$", k) and isinstance(v, int) and v > 0:
            return round(v / 100, 2)
    return None


def productos_en_json(datos, nombre_ref):
    """Objetos con nombre + precio. Si coinciden con el título de la página, puntúan más."""
    vistos = []
    clave_ref = set(re.findall(r"\w{4,}", (nombre_ref or "").lower()))
    for ruta, d in recorrer(datos):
        nombre = next((d[k] for k in CLAVES_NOMBRE if isinstance(d.get(k), str)), None)
        if not nombre:
            continue
        v = _precio_de_objeto(d)
        if not v:
            continue
        palabras = set(re.findall(r"\w{4,}", nombre.lower()))
        parecido = len(palabras & clave_ref) / max(1, len(palabras)) if clave_ref else 0
        vistos.append((v, nombre, parecido, "/".join(ruta[-3:])))
    return vistos


def bloques_de_estado(html, sopa):
    bloques = []
    for s in sopa.find_all("script"):
        tipo = (s.get("type") or "").lower()
        sid = s.get("id") or ""
        txt = s.string or ""
        if sid == "__NEXT_DATA__" or (tipo == "application/json" and len(txt) > 50):
            try:
                d = json.loads(txt)
                if sid == "__NUXT_DATA__" and isinstance(d, list):
                    d = devalue_nuxt(d)
                bloques.append((sid or "application/json", d))
            except Exception:
                pass
    for nombre in ("__INITIAL_STATE__", "__PRELOADED_STATE__", "__APOLLO_STATE__", "__APP_STATE__", "__STORE__"):
        for d in json_tras(html, r"window\.%s\s*=\s*(?=[{\[])" % nombre) + json_tras(html, r"window\[['\"]%s['\"]\]\s*=\s*(?=[{\[])" % nombre):
            bloques.append((nombre, d))
    # Variables de plantilla con el producto: var scopeProduct = {...}; window.productData = {...}
    patron = r"(?:\b(?:var|let|const)\s+|window\.)([A-Za-z_$]*(?:[Pp]roduct|[Pp]roducto|[Ii]tem|[Pp]dp|[Ss]ku|[Oo]ffer)[A-Za-z0-9_$]*)\s*=\s*(?=\{)"
    for m in re.finditer(patron, html):
        bloque = objeto_equilibrado(html, m.end())
        if bloque and len(bloque) < 2_000_000:
            d = cargar_json_flexible(bloque)
            if d is not None:
                bloques.append(("var " + m.group(1), d))
    return bloques


def devalue_nuxt(arr):
    """Nuxt 3 serializa con «devalue»: una lista plana donde los enteros son referencias."""
    cache = {}

    def res(i, prof=0):
        if prof > 60 or not isinstance(i, int) or i < 0 or i >= len(arr):
            return None
        if i in cache:
            return cache[i]
        v = arr[i]
        if isinstance(v, dict):
            out = {}
            cache[i] = out
            for k, ref in v.items():
                out[k] = res(ref, prof + 1)
            return out
        if isinstance(v, list):
            if v and isinstance(v[0], str) and v[0] in ("Reactive", "ShallowReactive", "Ref", "ShallowRef", "EmptyRef"):
                return res(v[1], prof + 1) if len(v) > 1 else None
            out = []
            cache[i] = out
            out.extend(res(r, prof + 1) for r in v)
            return out
        return v
    return res(0)


# ---------------------------------------------------------------------------
# Paso 3: analítica y píxeles (corroboran; pueden ir sin IVA)
# ---------------------------------------------------------------------------

def senales_analitica(html, sopa):
    res = []
    # GA4: {event:"view_item", ecommerce:{value, items:[{price}]}} y gtag('event','view_item',{...})
    for m in re.finditer(r"""['"]?event['"]?\s*:\s*['"]view_item['"]""", html):
        ini = html.rfind("{", 0, m.start())
        # retrocede hasta un { cuyo objeto contenga a la coincidencia
        for _ in range(6):
            bloque = objeto_equilibrado(html, ini) if ini >= 0 else None
            if bloque and ini + len(bloque) > m.end():
                break
            ini = html.rfind("{", 0, ini)
        obj = cargar_json_flexible(bloque) if bloque else None
        if isinstance(obj, dict):
            eco = obj.get("ecommerce") or {}
            items = eco.get("items") or []
            if items and isinstance(items[0], dict):
                it = items[0]
                if "price_tax_inc" in it:
                    v = numero_de_maquina(it["price_tax_inc"])
                    if v:
                        res.append(Candidato(v, "dataLayer view_item price_tax_inc"))
                v = numero_de_maquina(it.get("price"))
                if v:
                    res.append(Candidato(v, "dataLayer view_item items[0].price", motivos=["puede ir sin IVA"]))
    for d in json_tras(html, r"""gtag\(\s*['"]event['"]\s*,\s*['"]view_item['"]\s*,\s*(?=\{)"""):
        it = (d.get("items") or [{}])[0] if isinstance(d, dict) else {}
        v = numero_de_maquina(it.get("price")) or numero_de_maquina(d.get("value"))
        if v:
            res.append(Candidato(v, "gtag view_item"))
    # Universal Analytics: ecommerce.detail.products[0].price
    for d in json_tras(html, r"""['"]?detail['"]?\s*:\s*(?=\{\s*['"]?(?:actionField|products))"""):
        prods = d.get("products") if isinstance(d, dict) else None
        if prods and isinstance(prods[0], dict):
            v = numero_de_maquina(prods[0].get("price"))
            if v:
                res.append(Candidato(v, "dataLayer UA detail.products[0].price", motivos=["puede ir sin IVA"]))
    # Píxel de Facebook: fbq('track','ViewContent',{value:..})
    for d in json_tras(html, r"""fbq\(\s*['"]track['"]\s*,\s*['"]ViewContent['"]\s*,\s*(?=\{)"""):
        v = numero_de_maquina(d.get("value")) if isinstance(d, dict) else None
        if v:
            res.append(Candidato(v, "fbq ViewContent value"))
    for m in re.finditer(r"facebook\.com/tr\?[^\"'<>\s]*ev=ViewContent[^\"'<>\s]*", html):
        q = parse_qs(urlparse(html_mod.unescape(m.group(0))).query)
        v = numero_de_maquina((q.get("cd[value]") or q.get("cd[product_price]") or [None])[0])
        if v:
            res.append(Candidato(v, "fbq noscript cd[value]"))
            break
    # PixelYourSite (WordPress): "name":"ViewContent" ... "value":"39.99"
    m = re.search(r'"name"\s*:\s*"ViewContent".{0,600}?"value"\s*:\s*"?([\d.]+)', html, re.S)
    if m and numero_de_maquina(m.group(1)):
        res.append(Candidato(numero_de_maquina(m.group(1)), "PixelYourSite ViewContent value"))
    # Klaviyo: _learnq.push(['track','Viewed Product',{Price:..}])  /  klaviyo.track('Viewed Product',{...})
    for d in json_tras(html, r"""['"]Viewed Product['"]\s*,\s*(?=\{)"""):
        v = numero_de_maquina(d.get("Price") or d.get("Value")) if isinstance(d, dict) else None
        if v:
            res.append(Candidato(v, "Klaviyo Viewed Product"))
    # Remarketing de Google: ecomm_totalvalue (suele ir con IVA si existe la variante _tax_exc)
    m = re.search(r"""['"]?ecomm_totalvalue['"]?\s*:\s*['"]?(\d+(?:\.\d+)?)""", html)
    if m and numero_de_maquina(m.group(1)):
        res.append(Candidato(numero_de_maquina(m.group(1)), "google_tag_params ecomm_totalvalue"))
    # twitter:label1 = Precio / Price  ->  twitter:data1 (Yoast WooCommerce SEO)
    for i in (1, 2):
        lab = sopa.find("meta", attrs={"name": "twitter:label%d" % i})
        dat = sopa.find("meta", attrs={"name": "twitter:data%d" % i})
        if lab and dat and re.fullmatch(r"(?i)\s*(precio|price|prix|preço|prezzo)\s*", lab.get("content", "")):
            v = analizar_importe(dat.get("content"))
            if v:
                res.append(Candidato(v, "twitter:data%d (label Precio)" % i))
    return res


# ---------------------------------------------------------------------------
# Paso 4: heurística de candidatos visibles
# ---------------------------------------------------------------------------

MONEDA = r"(?:€|EUR|eur|euros?|\$|USD|£|GBP)"
NUM = r"\d{1,3}(?:[.\s  ]\d{3})*(?:[.,]\d{1,2})?|\d+(?:[.,]\d{1,2})?"
RE_PRECIO_TEXTO = re.compile(r"(?:%s\s*(?:%s)|(?:%s)\s*,?-?\s*%s)" % (MONEDA, NUM, NUM, MONEDA))
RE_CLASE_PRECIO = re.compile(r"price|precio|prezzo|preco|preis|prix|amount|importe|pvp|cost|tarifa|money", re.I)
RE_CLASE_ACTUAL = re.compile(r"current|final|sale|special|actual|now|offer|oferta|promo|selling|our[-_]?price|regular-price__current|price--main|main-price|product-price", re.I)
RE_CLASE_TACHADO = re.compile(r"(?<![bfghst])old|was|before|(?<!font-)regular(?!-price__current)|compare|tachad|anterior|strike|line-through|crossed|rrp|pvpr|list-?price|original|antes|precio-?base|price-?before|discount-from", re.I)
RE_ZONA_AJENA = re.compile(r"related|relacionad|recommend|recomend|upsell|up-sell|cross-?sell|carousel|carrusel|slider|swiper|similar|recent|viewed|vistos|also|tambien|bundle|accesor|complement|footer|header|navbar|menu|minicart|mini-cart|cart-drawer|widget_shopping_cart|sidebar|newsletter|popup|modal|banner|product-tile|product-item(?!-info)|product-card|miniature|grid-product|product-list|productos-|products-grid|tile|frequently|compra-junto|pack", re.I)
RE_DESDE = re.compile(r"\b(desde|a partir de|from|ab|starting at)\b", re.I)
RE_CUOTA = re.compile(r"/\s*mes|al mes|mensual|cuotas?|financ|plazos|meses|month|/mo\b|aplazame|sequra|klarna|pagantis|paypal en 3|en \d+ pagos", re.I)
RE_AHORRO = re.compile(r"ahorr|descuento|dto\.?|save|you save|-\s*\d+\s*%|\d+\s*%\s*(dto|off)|rebaja de", re.I)
RE_ENVIO = re.compile(r"env[ií]o|gastos|shipping|entrega|portes|gratis a partir|pedidos? superiores?|free delivery", re.I)
RE_UNIDAD = re.compile(r"/\s*(kg|g|l|ml|m2|m²|m|100\s*g|100\s*ml|lavado|dosis|litro|kilo|cápsula|capsula)\b|por (kilo|litro|lavado|dosis|cápsula)|precio (por kilo|por litro|unitario)|\bunit price|€\s*/\s*(kg|l|m)", re.I)
RE_UNIDAD_DEBIL = re.compile(r"/\s*(ud|u|unidad|uds)\b|por unidad", re.I)  # suele ser el precio de venta
RE_ANTES = re.compile(r"precio original|precio anterior|precio de venta recomendado|pvp ?rec|pvpr|antes:?\s|\bwas\b|\brrp\b|original price|regular price|precio habitual|precio sin descuento", re.I)
RE_ETIQUETA_PRECIO = re.compile(r"\b(precio|p\.?v\.?p\.?|price|importe)\s*:", re.I)
RE_ACTUAL_TXT = re.compile(r"precio actual|current price|ahora:?\s|now:?\s|precio final|tu precio", re.I)
RE_SIN_IVA = re.compile(r"sin iva|iva no incl|\+\s*iva|excl\.?\s*(iva|vat|tax)|tax excl|base imponible|antes de impuestos|vat excl|pretax|sin impuestos", re.I)
RE_CON_IVA = re.compile(r"iva incl|con iva|impuestos incl|vat incl|tax incl|igic incl", re.I)
RE_BOTON_CARRITO = re.compile(r"a[ñn]adir al carrito|a[ñn]adir a la cesta|a[ñn]adir a la bolsa|comprar ahora|comprar\b|add to (cart|bag|basket)|buy now|añadir$|reservar", re.I)

ETIQUETAS_FUERA = ("script", "style", "noscript", "template", "svg", "head", "iframe", "select", "option", "button", "label", "title")


def texto_propio_corto(el, limite=48):
    t = norm(el.get_text(" "))
    return t if 0 < len(t) <= limite else None


def ancestros(el, n=50):
    out = []
    p = el.parent
    while p is not None and isinstance(p, Tag) and len(out) < n:
        out.append(p)
        p = p.parent
    return out


def atributos_texto(el):
    partes = [el.get("id") or "", " ".join(el.get("class") or []), el.get("itemprop") or ""]
    partes += [f"{k}={v}" for k, v in el.attrs.items() if k.startswith("data-") and isinstance(v, str) and len(v) < 60]
    partes += [k for k in el.attrs if k.startswith("data-")]
    return " ".join(partes)


def clases_sin_variantes(el):
    """Clases del elemento sin las variantes de Tailwind (con «:» o «[»), que describen a otros elementos."""
    return " ".join(c for c in (el.get("class") or []) if ":" not in c and "[" not in c)


def tachado(el):
    for a in [el] + ancestros(el, 4):
        if a.name in ("del", "s", "strike"):
            return True
        if RE_CLASE_TACHADO.search(clases_sin_variantes(a) + " " + (a.get("id") or "")):
            return True
        if "line-through" in (a.get("style") or ""):
            return True
        if a.get("data-price-type") in ("oldPrice", "basePrice"):
            return True
    return False


def es_cabecera_del_sitio(h):
    """<header> de la web (con menú o logo), no el <header> de un <article> o <section>."""
    cls = " ".join(h.get("class") or []) + " " + (h.get("id") or "")
    return bool(h.find("nav") or re.search(r"site|masthead|main-header|page-header|top-?bar|cabecera", cls, re.I)
                or (h.parent is not None and h.parent.name == "body"))


def es_zona_ajena(a, ancestros_h1):
    """Contenedor de relacionados, carrusel, menú, pie... que NO contiene el h1 del producto."""
    if a.name in ("body", "html", "main", "[document]") or id(a) in ancestros_h1:
        return False
    if a.name in ("footer", "nav", "aside"):
        return True
    if a.name == "header" and es_cabecera_del_sitio(a):
        return True
    fichas = (a.get("class") or []) + ([a.get("id")] if a.get("id") else [])
    return any(RE_ZONA_AJENA.search(f) for f in fichas)


def localizar_ancla(sopa):
    """h1 del producto y botón/formulario de compra; su ancestro común es el bloque principal."""
    h1 = None
    for h in sopa.find_all("h1"):
        if h.find_parent(["nav", "footer"]) or not norm(h.get_text()):
            continue
        cab = h.find_parent("header")
        if cab is not None and es_cabecera_del_sitio(cab):
            continue
        h1 = h
        break
    if h1 is None:
        h1 = sopa.select_one(".product_title, .product-title, .product-name, [itemprop=name]")
    anc_h1 = set(id(x) for x in ([h1] + ancestros(h1))) if h1 is not None else set()
    orden = orden_documento(sopa)
    pos_h1 = orden.get(id(h1), 0) if h1 is not None else 0
    botones = []
    for b in sopa.find_all(["button", "input", "a"]):
        t = norm(b.get_text(" ") if b.name != "input" else (b.get("value") or ""))
        cls = " ".join(b.get("class") or []) + " " + (b.get("name") or "") + " " + (b.get("id") or "") + " " + str(b.get("data-button-action") or "")
        if (RE_BOTON_CARRITO.search(t) and len(t) < 40) or re.search(r"add-to-cart|addtocart|add_to_cart|btn-cart|tocart|buy-button", cls, re.I):
            if any(es_zona_ajena(a, anc_h1) for a in ancestros(b)):
                continue
            botones.append(b)
    # el primero DESPUÉS del h1; si no hay, el primero de la página
    boton = next((b for b in botones if orden.get(id(b), 0) > pos_h1), botones[0] if botones else None)
    principal = None
    if h1 is not None and boton is not None:
        anc_h1 = [h1] + ancestros(h1)
        anc_b = set(id(x) for x in [boton] + ancestros(boton))
        for a in anc_h1:
            if id(a) in anc_b:
                principal = a
                break
        if principal is not None and principal.name in ("html", "body", "[document]"):
            principal = None
    return h1, boton, principal


def _texto_nodo(n):
    if isinstance(n, NavigableString):
        return "" if isinstance(n, Comment) else str(n)
    if isinstance(n, Tag) and n.name not in ETIQUETAS_FUERA[:6]:
        return n.get_text(" ")
    return ""


def contexto_adyacente(el, limite=40, niveles=3):
    """Texto inmediatamente antes y después del elemento, sin cruzar otro importe.
    Si el elemento no tiene hermanos con texto, sube hasta `niveles` padres."""
    nodo = el
    antes = despues = ""
    for _ in range(niveles):
        partes = []
        for h in nodo.previous_siblings:
            tx = norm(_texto_nodo(h))
            if not tx:
                continue
            if RE_PRECIO_TEXTO.search(tx):
                break
            partes.insert(0, tx)
            if sum(len(x) for x in partes) >= limite:
                break
        antes = norm(" ".join(partes))[-limite:]
        partes = []
        for h in nodo.next_siblings:
            tx = norm(_texto_nodo(h))
            if not tx:
                continue
            if RE_PRECIO_TEXTO.search(tx):
                break
            partes.append(tx)
            if sum(len(x) for x in partes) >= limite:
                break
        despues = norm(" ".join(partes))[:limite]
        if antes or despues or nodo.parent is None:
            break
        nodo = nodo.parent
    return antes, despues


def orden_documento(sopa):
    return {id(e): i for i, e in enumerate(sopa.find_all(True))}


def candidatos_visibles(sopa):
    h1, boton, principal = localizar_ancla(sopa)
    orden = orden_documento(sopa)
    total = max(1, len(orden))
    pos_h1 = orden.get(id(h1)) if h1 is not None else None
    pos_boton = orden.get(id(boton)) if boton is not None else None
    tam_principal = len(principal.find_all(True)) if principal is not None else 0
    principal_util = principal is not None and (tam_principal < 0.5 * total or total < 300)
    anc_h1 = set(id(x) for x in ([h1] + ancestros(h1))) if h1 is not None else set()

    brutos = []
    for el in sopa.find_all(True):
        if el.name in ETIQUETAS_FUERA or el.find_parent(ETIQUETAS_FUERA):
            continue
        t = texto_propio_corto(el)
        valor_attr = None
        for a in ("data-price-amount", "data-price", "data-product-price", "data-price-value"):
            if el.get(a) and re.fullmatch(r"\s*\d+(?:[.,]\d+)?\s*", str(el.get(a))):
                valor_attr = numero_de_maquina(str(el.get(a)).replace(",", "."))
                break
        if el.get("itemprop") == "price" and el.get("content"):
            valor_attr = numero_de_maquina(el.get("content"))
        if t is None and valor_attr is None:
            continue
        if t and re.match(r"^[.,]\s?\d", t):
            continue  # trozo decimal de un precio partido («,29 €»): lo recoge su contenedor
        m = RE_PRECIO_TEXTO.search(t) if t else None
        clase_precio = bool(RE_CLASE_PRECIO.search(atributos_texto(el)))
        if not m and valor_attr is None and not (clase_precio and t and re.search(r"\d[.,]\d{2}\b", t)):
            continue
        valor = valor_attr or analizar_importe(m.group(0) if m else t)
        if not valor or valor > 1_000_000:
            continue
        # quedarnos con el elemento más profundo: si un hijo da el mismo valor, el padre sobra
        if any(isinstance(h, Tag) and h.name not in ETIQUETAS_FUERA and texto_propio_corto(h) and
               (RE_PRECIO_TEXTO.search(texto_propio_corto(h)) and analizar_importe(RE_PRECIO_TEXTO.search(texto_propio_corto(h)).group(0)) == valor)
               for h in el.find_all(True)) and valor_attr is None:
            continue
        brutos.append((el, valor, t or "", bool(m)))

    cands = []
    for el, valor, t, con_moneda in brutos:
        p, motivos = 0.0, []
        anc = ancestros(el, 60)
        cerca = [el] + anc[:3]
        attrs_cerca = " ".join(atributos_texto(a) for a in cerca)
        # contexto textual ADYACENTE: lo que hay justo antes y justo después (sin otros importes)
        antes, despues = contexto_adyacente(el)
        propio_y_antes = antes[-40:] + " | " + t
        propio_y_despues = t + " | " + despues[:40]
        alrededor = antes[-40:] + " | " + t + " | " + despues[:40]
        if con_moneda:
            p += 2; motivos.append("moneda +2")
        if RE_CLASE_PRECIO.search(attrs_cerca):
            p += 2; motivos.append("clase precio +2")
            if RE_CLASE_ACTUAL.search(attrs_cerca) and not RE_CLASE_TACHADO.search(attrs_cerca):
                p += 1; motivos.append("clase actual/final +1")
        if el.get("itemprop") == "price" or el.get("data-price-amount") or el.find_parent(attrs={"data-price-type": "finalPrice"}):
            p += 2; motivos.append("itemprop/data-price +2")
        dentro_principal = principal_util and any(a is principal for a in anc)
        if dentro_principal:
            p += 4; motivos.append("bloque principal +4")
        pos = orden.get(id(el), 0)
        if pos_h1 is not None:
            d = abs(pos - pos_h1)
            extra = max(0.0, 2.0 * (1 - d / 300))
            if extra:
                p += extra; motivos.append("cerca del h1 +%.1f" % extra)
            if pos < pos_h1 - 400:
                p -= 2; motivos.append("muy por encima del h1 -2")
        if pos_boton is not None:
            d = abs(pos - pos_boton)
            extra = max(0.0, 2.0 * (1 - d / 150))
            if extra:
                p += extra; motivos.append("cerca de comprar +%.1f" % extra)
        if tachado(el):
            p -= 6; motivos.append("tachado -6")
        if RE_ANTES.search(propio_y_antes) and not tachado(el):
            p -= 6; motivos.append("tachado (texto «antes/original») -6")
        if RE_ACTUAL_TXT.search(propio_y_antes):
            p += 1; motivos.append("«precio actual» +1")
        elif RE_ETIQUETA_PRECIO.search(propio_y_antes):
            p += 1; motivos.append("etiqueta «Precio/PVP» +1")
        if not dentro_principal and any(es_zona_ajena(a, anc_h1) for a in anc):
            p -= 5; motivos.append("zona ajena (relacionados, carrusel, cabecera...) -5")
        if RE_CUOTA.search(alrededor):
            p -= 6; motivos.append("cuota/financiación -6")
        if RE_AHORRO.search(propio_y_antes):
            p -= 5; motivos.append("ahorro/descuento -5")
        if RE_ENVIO.search(propio_y_antes):
            p -= 5; motivos.append("envío -5")
        if RE_UNIDAD.search(t) or RE_UNIDAD.search(despues[:15]):
            p -= 5; motivos.append("precio por kilo/litro -5")
        elif RE_UNIDAD_DEBIL.search(t):
            p -= 1; motivos.append("«por unidad» -1")
        if RE_SIN_IVA.search(alrededor):
            p -= 4; motivos.append("sin IVA -4")
        elif RE_CON_IVA.search(propio_y_despues):
            p += 1; motivos.append("IVA incluido +1")
        if RE_DESDE.search(antes[-25:] + " " + t[:12]):
            p -= 2; motivos.append("desde -2")
        cands.append(Candidato(valor, "visible", p, t, el, motivos))
    return cands, (h1, boton, principal if principal_util else None)


# ---------------------------------------------------------------------------
# Paso 5: decisión
# ---------------------------------------------------------------------------

UMBRAL = 8.0          # puntos mínimos del mejor candidato visible
MARGEN = 3.0          # ventaja mínima sobre el mejor candidato con OTRO importe
BONO_COINCIDE = 3.0   # coincide con datos ocultos (estado, analítica)
UMBRAL_UNICO = 5.0    # si es el ÚNICO importe con puntos positivos de la página


def agrupar(cands):
    por_valor = {}
    for c in cands:
        por_valor.setdefault(c.valor, []).append(c)
    return por_valor


def extraer(html, url=None, usar_basico=True):
    sopa = BeautifulSoup(html, "html.parser")
    for c in sopa.find_all(string=lambda s: isinstance(s, Comment)):
        c.extract()
    out = {"precio": None, "fuente": None, "confianza": None, "plataformas": detectar_plataformas(html),
           "candidatos": [], "ocultos": []}
    if usar_basico:
        p, mon, fuente = extraer_basico(sopa)
        if p:
            out.update(precio=p, fuente=fuente, confianza="alta")
            return out

    # 1. plataforma
    for plat in out["plataformas"]:
        f = PLATAFORMAS.get(plat)
        if not f:
            continue
        cs = f(html, sopa, url)
        out["ocultos"] += [c.como_dict() for c in cs]
        if cs:
            c = cs[0]
            out.update(precio=c.valor, fuente=c.origen + (" (" + ", ".join(m for m in c.motivos if m) + ")" if any(c.motivos) else ""),
                       confianza="alta")
            # Se siguen calculando los visibles solo para informar; la plataforma gana.
            return out

    # 2 y 3. ocultos que corroboran
    titulo = ""
    og = sopa.find("meta", attrs={"property": "og:title"})
    if og:
        titulo = og.get("content", "")
    h1 = sopa.find("h1")
    if h1:
        titulo += " " + norm(h1.get_text())
    ocultos = []
    for nombre, datos in bloques_de_estado(html, sopa):
        prods = productos_en_json(datos, titulo)
        buenos = [x for x in prods if x[2] >= 0.5]
        for v, nom, par, ruta in buenos[:5]:
            ocultos.append(Candidato(v, "estado %s (%s)" % (nombre, ruta), motivos=["nombre coincide %.0f%%" % (par * 100)]))
    ocultos += senales_analitica(html, sopa)
    out["ocultos"] = [c.como_dict() for c in ocultos]
    valores_ocultos = {}
    for c in ocultos:
        valores_ocultos.setdefault(c.valor, set()).add(c.origen.split(" ")[0])

    # 4. visibles
    vis, (h1, boton, principal) = candidatos_visibles(sopa)
    for c in vis:
        if c.valor in valores_ocultos:
            n = len(valores_ocultos[c.valor])
            c.puntos += BONO_COINCIDE + (1 if n > 1 else 0)
            c.motivos.append("coincide con datos ocultos +%d" % (BONO_COINCIDE + (1 if n > 1 else 0)))
    vis.sort(key=lambda c: -c.puntos)
    out["candidatos"] = [c.como_dict() for c in vis[:12]]
    out["anclas"] = {"h1": norm(h1.get_text())[:60] if h1 else None,
                     "boton": norm(boton.get_text(" ") or boton.get("value") or "")[:40] if boton else None,
                     "bloque_principal": bool(principal)}

    # 5. decisión
    if vis:
        mejor = vis[0]
        otro = next((c for c in vis[1:] if c.valor != mejor.valor), None)
        margen = mejor.puntos - (otro.puntos if otro else 0)
        if mejor.puntos >= UMBRAL and (otro is None or margen >= MARGEN):
            out.update(precio=mejor.valor, fuente="heurística visible", confianza="media", elemento=mejor.elemento)
            return out
        # Candidato único: un solo importe en toda la página, junto al botón de compra y sin
        # ninguna penalización (tiendas antiguas sin h1 ni datos estructurados).
        positivos = {c.valor for c in vis if c.puntos > 0}
        if (len(positivos) == 1 and mejor.puntos >= UMBRAL_UNICO and boton is not None
                and not any("-" in m for m in mejor.motivos)):
            out.update(precio=mejor.valor, fuente="heurística visible (candidato único)", confianza="baja",
                       elemento=mejor.elemento)
            return out
    # Sin visible seguro: dos fuentes ocultas independientes que coinciden y ninguna otra cifra oculta
    distintas = {v for v in valores_ocultos}
    if len(distintas) == 1:
        v = next(iter(distintas))
        if len(valores_ocultos[v]) >= 2:
            out.update(precio=v, fuente="datos ocultos coincidentes", confianza="media")
            return out
    # Un objeto de estado cuyo nombre coincide con el título (>= 80 %) y un único importe
    seguros = {c.valor for c in ocultos if c.origen.startswith("estado") and
               any(m.startswith("nombre coincide") and int(m.split()[-1].rstrip("%")) >= 80 for m in c.motivos)}
    mejor_vis = vis[0].puntos if vis else 0
    if len(seguros) == 1 and mejor_vis < UMBRAL:
        out.update(precio=seguros.pop(), fuente="estado embebido con el nombre del producto", confianza="media")
        return out
    out.update(fuente="preguntar al usuario", confianza="ninguna")
    return out


def describir_candidato(c):
    """Texto para lector de pantalla: «39,99 € — junto a "Añadir al carrito"»."""
    imp = ("%.2f" % c["valor"]).replace(".", ",") + " €"
    m = " ".join(c["motivos"])
    partes = []
    if "tachado" in m:
        partes.append("tachado")
    if "bloque principal" in m or "cerca de comprar" in m:
        partes.append("junto al botón de compra")
    if "zona ajena" in m:
        partes.append("en otra zona (relacionados, carrusel o pie)")
    if "cuota" in m:
        partes.append("cuota o financiación")
    if "por unidad" in m:
        partes.append("precio por unidad")
    if "envío" in m:
        partes.append("envío")
    if "sin IVA" in m:
        partes.append("sin IVA")
    if "coincide con datos ocultos" in m:
        partes.append("coincide con los datos internos de la página")
    return imp + (" — " + ", ".join(partes) if partes else "") + (" — «%s»" % c["texto"] if c["texto"] else "")
