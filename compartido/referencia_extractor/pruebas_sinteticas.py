"""Vectores de prueba mínimos para plataformas y trampas que no se pudieron descargar
(Shopify respondió 429 a todas las peticiones; VTEX, SFCC, Next, Nuxt...).
Están escritos a partir de la estructura documentada de cada plataforma.
Uso: python -I pruebas_sinteticas.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bs4 import BeautifulSoup  # noqa: E402

import extractor_generico as eg  # noqa: E402
from selector_css import generar_selector, validar_selector, palabra_estable  # noqa: E402

BOTON = '<form><button type="submit" name="add">Añadir al carrito</button></form>'

CASOS = [
    ("Shopify var meta en céntimos, variante de la URL",
     "https://t.es/products/camiseta?variant=222",
     '<script src="//cdn.shopify.com/x.js"></script><script>var meta = {"product":{"id":1,"variants":[{"id":111,"price":2999},{"id":222,"price":3499}]},"page":{"pageType":"product"}};\nfor (var attr in meta) {}</script><h1>Camiseta</h1>',
     34.99),
    ("Shopify data-selected-variant (Dawn)",
     "https://t.es/products/taza",
     '<link href="//cdn.shopify.com/s.css"><h1>Taza</h1><script type="application/json" data-selected-variant>{"id":5,"price":1250,"compare_at_price":1500}</script>' + BOTON,
     12.5),
    ("Magento 2 Luma: finalPrice del bloque principal, no oldPrice ni relacionados",
     None,
     '<script type="text/x-magento-init">{}</script><div class="product-info-main"><h1>Bolso</h1><div class="price-box" data-role="priceBox">'
     '<span class="special-price"><span data-price-amount="59.9" data-price-type="finalPrice" class="price-wrapper"><span class="price">59,90 €</span></span></span>'
     '<span class="old-price"><span data-price-amount="79.9" data-price-type="oldPrice" class="price-wrapper"><span class="price">79,90 €</span></span></span></div>' + BOTON + '</div>'
     '<div class="block related"><span data-price-amount="9.9" data-price-type="finalPrice"></span></div>',
     59.9),
    ("WooCommerce variaciones con atributo en la URL",
     "https://t.es/producto/cafe/?attribute_pa_peso=1kg",
     '<div class="woocommerce"><h1 class="product_title">Café</h1><p class="price"><span class="woocommerce-Price-amount">12,00 €</span> – <span class="woocommerce-Price-amount">40,00 €</span></p>'
     '<form class="variations_form" data-product_variations=\'[{"attributes":{"attribute_pa_peso":"250g"},"display_price":12,"is_in_stock":true},{"attributes":{"attribute_pa_peso":"1kg"},"display_price":40,"is_in_stock":true}]\'>' + BOTON + '</form></div>',
     40.0),
    ("PrestaShop 1.6 #our_price_display",
     None,
     '<script>var prestashop = {}; var productPrice = 19.95;</script><h1>Pienso</h1><span id="our_price_display" class="price" itemprop="price" content="19.95">19,95 €</span>' + BOTON,
     19.95),
    ("Salesforce Commerce Cloud .sales .value[content]",
     None,
     '<link href="/on/demandware.static/x.css"><div class="product-detail" data-pid="ABC"><h1>Gafas</h1><div class="prices"><div class="price"><span class="strike-through list"><span class="value" content="69.99">69,99 €</span></span>'
     '<span class="sales"><span class="value" content="48.99">48,99 €</span></span></div></div>' + BOTON + '</div>',
     48.99),
    ("VTEX antiguo: skuJson en céntimos (solo SKU disponibles)",
     None,
     '<script src="https://x.vteximg.com.br/a.js"></script><script>var skuJson_0 = {"productId":1,"name":"Zapatilla","skus":[{"sku":1,"available":false,"bestPrice":4990},{"sku":2,"available":true,"bestPrice":5990}]};</script><h1>Zapatilla</h1>',
     59.9),
    ("VTEX IO: __STATE__ commertialOffer.Price",
     None,
     '<template data-type="json" data-varname="__STATE__"><script>{"Product:sku-1":{"productName":"Sofá"},"$Product:sku-1.items.0.sellers.0.commertialOffer":{"Price":299.0,"ListPrice":349.0,"AvailableQuantity":5}}</script></template><h1>Sofá</h1>',
     299.0),
    ("BigCommerce BCData con IVA",
     None,
     '<script>var BCData = {"product_attributes":{"sku":"X","price":{"with_tax":{"formatted":"121,00 €","value":121,"currency":"EUR"},"without_tax":{"value":100}}}};</script><h1>Lámpara</h1>',
     121.0),
    ("Next.js __NEXT_DATA__ con el producto (nombre = h1)",
     None,
     '<script id="__NEXT_DATA__" type="application/json">{"props":{"pageProps":{"product":{"name":"Silla nórdica roble","price":{"current":89.95,"old":119.95},"related":[{"name":"Mesa","price":{"current":199}}]}}}}</script><h1>Silla nórdica roble</h1>',
     89.95),
    ("Nuxt 3 __NUXT_DATA__ (devalue)",
     None,
     '<script type="application/json" id="__NUXT_DATA__">[{"data":1},{"producto":2},{"name":3,"price":4},"Mochila urbana gris",45.5]</script><h1>Mochila urbana gris</h1>',
     45.5),
    ("Solo analítica: GA4 view_item + píxel de Facebook coinciden",
     None,
     '<h1>Altavoz</h1><script>dataLayer.push({"event":"view_item","ecommerce":{"currency":"EUR","value":79.0,"items":[{"item_id":"A1","price":79.0}]}});'
     'fbq("track","ViewContent",{"value":79.0,"currency":"EUR"});</script>',
     79.0),
    ("Trampa: cuota mensual al lado del precio",
     None,
     '<main><h1>Portátil</h1><div class="product-price">599,00 €</div><div class="financing">o 24,96 €/mes en 24 cuotas</div>' + BOTON + '</main>',
     599.0),
    ("Trampa: precio por kilo",
     None,
     '<main><h1>Queso curado 300 g</h1><span class="price">3,75 €</span> <small class="unit">12,50 €/kg</small>' + BOTON + '</main>',
     3.75),
    ("Trampa: precio sin IVA y con IVA (B2B)",
     None,
     '<main><h1>Taladro</h1><div class="price-excl">99,00 € + IVA</div><div class="price-incl">119,79 € IVA incluido</div>' + BOTON + '</main>',
     119.79),
    ("Trampa: tachado con clase .old y oferta",
     None,
     '<main><h1>Robot</h1><span class="price old">249,00 €</span><span class="price">199,00 €</span><span class="badge">Ahorra 50,00 €</span>' + BOTON + '</main>',
     199.0),
    ("Trampa: página de categoría (muchos productos) -> no debe dar precio",
     None,
     '<h1>Zapatillas</h1>' + ''.join('<div class="product-card"><a href="/p%d">Modelo %d</a><span class="price">%d,99 €</span><button>Añadir al carrito</button></div>' % (i, i, 40 + i) for i in range(8)),
     None),
    ("Trampa: envío gratis como único importe visible",
     None,
     '<main><h1>Planta</h1><p class="shipping">Envío gratis a partir de 49 €</p>' + BOTON + '</main>',
     None),
    ("twitter:label1 = Precio (Yoast WooCommerce SEO) coincide con el visible",
     None,
     '<meta name="twitter:label1" content="Precio"><meta name="twitter:data1" content="24,90 €"><main><h1>Libro</h1><p><span class="amount">24,90 €</span></p>' + BOTON + '</main>',
     24.9),
]


def main():
    bien = 0
    for nombre, url, html, esperado in CASOS:
        r = eg.extraer(html, url, usar_basico=False)
        ok = r["precio"] == esperado
        bien += ok
        print("%s  %s -> %s (%s)" % ("OK   " if ok else "FALLA", nombre, r["precio"], r["fuente"]))
    print("\nExtractor: %d de %d" % (bien, len(CASOS)))

    # Selectores
    html = ('<div class="css-1x2y3z product-main"><h1 class="sc-abc123">X</h1>'
            '<div class="Price_wrapper__3x9Yz"><span class="Price_price__a1B2c current-price" data-test="product-price">19,99 €</span></div>'
            '<div class="price"><span>29,99 €</span></div></div>'
            '<ul class="related"><li><span class="Price_price__a1B2c">5,00 €</span></li></ul>')
    sopa = BeautifulSoup(html, "html.parser")
    el = sopa.find(attrs={"data-test": "product-price"})
    sel, atr = generar_selector(el, sopa)
    print("Selector para 19,99:", sel, "válido:", validar_selector(sopa, sel, atr, 19.99))
    el2 = sopa.select_one(".price span")
    sel2, atr2 = generar_selector(el2, sopa)
    print("Selector para 29,99:", sel2, "válido:", validar_selector(sopa, sel2, atr2, 29.99))
    for n in ("css-1x2y3z", "sc-abc123", "Price_price__a1B2c", "jsx-2847563", "md:text-lg", "is-active",
              "product-price", "current-price", "price__current", "js-product-price", "woocommerce-Price-amount"):
        print("  %-26s estable: %s" % (n, palabra_estable(n)))


if __name__ == "__main__":
    main()
