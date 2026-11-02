# Investigación: extractor genérico de precios

Fecha: 2 de noviembre de 2026.

Objetivo: ampliar lo que viene después del paso 6 (microdatos) de la sección «Extracción del precio» de `compartido/ESPECIFICACION.md`, para que la app acierte en el máximo de tiendas sin reglas propias y sin dar precios falsos. Todo funciona con una petición HTTP normal, sin ejecutar JavaScript, y es igual en Windows (Python con BeautifulSoup) y en Android (Kotlin con Jsoup).

El prototipo está en `adjuntos/prototipo_extractor/`. Los resultados de la prueba con páginas reales están en `resultados.txt` y `resultados.json` de esa carpeta.

## 1. Resumen

- El orden propuesto, después de los pasos actuales, es: datos de la plataforma de tienda, estado de la aplicación incrustado, señales de analítica, heurística sobre el HTML visible con puntuación y umbral, y, si nada es seguro, una lista de candidatos para que elija el usuario.
- Regla de oro: **un dato de plataforma o un candidato visible con mucha ventaja se acepta; todo lo demás se pregunta**. La analítica (dataLayer, píxel de Facebook) nunca decide sola si hay un candidato visible distinto, porque a menudo va sin IVA.
- Prueba real: 12 fichas descargadas una sola vez de 11 tiendas españolas pequeñas y medianas (WooCommerce, PrestaShop, Magento 2 con Hyvä, Salesforce Commerce Cloud, Obramat, una plataforma propia y una tienda PHP antigua).
  - La especificación actual (JSON-LD, metas y microdatos) acierta 10 de 12.
  - Con la ampliación acierta 12 de 12, sin ningún precio falso.
  - Quitando el JSON-LD y las metas (para simular tiendas que no los tienen), la ampliación sigue acertando 12 de 12. La heurística visible sola acierta 11 de 12 y en la que falta (un producto con variantes) no inventa: pregunta al usuario.
- Las ocho tiendas Shopify probadas respondieron 429 a la descarga con la biblioteca estándar de Python, ya fuera la colección o la ficha. No se intentó saltar el bloqueo. Shopify se cubre con vectores de prueba sintéticos (19 de 19 correctos).
- Los selectores CSS generados para el candidato elegido fueron válidos en las 10 páginas probadas: devuelven un único elemento con el mismo importe.

## 2. Dónde encaja en la especificación

Orden completo, con los pasos nuevos a partir del 7. Se usa el primer resultado válido, salvo donde se dice otra cosa:

1. `selector_precio` del producto.
2. `selector_precio` de la tienda.
3. Reglas de `tiendas.json`.
4. JSON-LD Product.
5. Metadatos (`product:price:amount`, `og:price:amount`, `meta[itemprop=price]`).
6. Microdatos (`itemprop="price"`).
7. **Plataforma**: se detecta la plataforma de tienda por su firma en el HTML y se leen sus datos propios (Shopify, WooCommerce, PrestaShop, Magento 2, Salesforce Commerce Cloud, VTEX, BigCommerce). Si da un importe, se usa con confianza alta.
8. **Estado de la aplicación**: `__NEXT_DATA__`, `__NUXT_DATA__`, `__INITIAL_STATE__`, `__PRELOADED_STATE__`, `__APOLLO_STATE__`, `<script type="application/json">` y variables de plantilla con «product» en el nombre. No decide solo: da candidatos ocultos.
9. **Analítica**: dataLayer de GA4 y Universal Analytics, `gtag`, píxel de Facebook, PixelYourSite, Klaviyo, `ecomm_totalvalue` y `twitter:label1`/`twitter:data1`. Tampoco decide solo: da candidatos ocultos.
10. **Heurística visible**: candidatos del HTML con puntuación. Los que coinciden con un importe de los pasos 8 y 9 reciben un bono.
11. **Decisión**: se acepta el mejor candidato visible si pasa el umbral y saca margen al siguiente importe distinto. Si no, se aceptan datos ocultos solo en dos casos muy concretos (ver el apartado 6.6).
12. **Pregunta al usuario**: lista accesible de candidatos. El elegido se guarda como `selector_precio` del producto (o de la tienda, si el usuario lo pide).

Un detalle sobre el paso 5 que conviene corregir en la especificación: en las tiendas PrestaShop, `product:price:amount` va con IVA y existe además `product:pretax_price:amount` sin IVA. Nunca hay que leer el `pretax`.

## 3. Algoritmo propuesto, en pseudocódigo

Independiente del lenguaje. `analizarImporte` e `importeDeMaquina` son las funciones que ya define la especificación. `numeroDeMaquina` es nueva (apartado 8.1).

```
funcion extraerGenerico(html, url):
    doc = parsear(html)                      # sin comentarios HTML
    plataformas = detectarPlataformas(html)  # apartado 4, en el orden de la lista

    # Paso 7: plataforma
    para cada p en plataformas:
        c = extractorDePlataforma(p, html, doc, url)
        si c no es nulo: devolver (c.importe, fuente = p, confianza = ALTA)

    # Pasos 8 y 9: candidatos ocultos (no deciden solos)
    titulo = og:title + " " + texto(h1)
    ocultos = []
    para cada (nombre, datos) en bloquesDeEstado(html, doc):
        para cada objeto con nombre y precio dentro de datos:
            si parecido(objeto.nombre, titulo) >= 0.5: ocultos.añadir(objeto.precio, familia = "estado")
    ocultos += senalesDeAnalitica(html, doc)     # familia = "dataLayer", "fbq", "gtag", ...

    # Paso 10: candidatos visibles
    (h1, boton, bloque) = localizarAnclas(doc)
    visibles = candidatosVisibles(doc, h1, boton, bloque)   # apartado 6
    para cada c en visibles:
        familias = familias de ocultos con el mismo importe que c
        si familias no vacio: c.puntos += 3 + (1 si familias >= 2)
    ordenar visibles por puntos de mayor a menor

    # Paso 11: decision
    si visibles no vacio:
        mejor = visibles[0]
        otro = primer c de visibles con c.importe != mejor.importe
        margen = mejor.puntos - (otro.puntos si existe, si no 0)
        si mejor.puntos >= 8 y (no existe otro o margen >= 3):
            devolver (mejor.importe, fuente = "visible", confianza = MEDIA)
        importesPositivos = importes distintos de los c con puntos > 0
        si tamaño(importesPositivos) == 1 y mejor.puntos >= 5 y boton existe
           y mejor no tiene ninguna penalizacion:
            devolver (mejor.importe, fuente = "candidato unico", confianza = BAJA)
    distintos = importes distintos de ocultos
    si tamaño(distintos) == 1 y ese importe viene de 2 familias o mas:
        devolver (importe, fuente = "datos ocultos coincidentes", confianza = MEDIA)
    seguros = importes de ocultos de familia "estado" con parecido >= 0.8
    si tamaño(seguros) == 1 y (visibles vacio o visibles[0].puntos < 8):
        devolver (importe, fuente = "estado con el nombre del producto", confianza = MEDIA)

    # Paso 12
    devolver SIN_PRECIO con la lista de candidatos para el usuario
```

La «confianza» no se enseña como número. Sirve para dos cosas:

- Con confianza baja o media, un cambio de precio de más del 50 % se vuelve a comprobar antes de avisar.
- La pantalla del producto puede decir «Precio detectado automáticamente» y ofrecer «Elegir otro precio».

## 4. Datos embebidos por plataforma

### 4.0 Extracción por llaves equilibradas

Casi todos los datos están en JavaScript del tipo `var x = {...};`. Una expresión regular codiciosa (`\{.*\}`) falla con objetos anidados. Lo fiable es:

1. Buscar el inicio con una expresión regular que termina justo antes de la llave, con una anticipación `(?=\{)`.
2. Recorrer carácter a carácter contando `{`, `[`, `}` y `]`, ignorando lo que está dentro de comillas (`"`, `'` o acento grave) y los caracteres escapados con `\`.
3. Cortar cuando el contador vuelve a cero y pasarlo a `JSON.parse` / `json.loads`.
4. Si falla, un segundo intento «flexible» para objetos literales sencillos de JavaScript:
   - poner comillas a las claves: `(?<=[{,])\s*([A-Za-z_$][\w$]*)\s*:` se cambia por `"$1":`;
   - convertir las cadenas entre comillas simples a dobles;
   - quitar las comas finales: `,\s*([}\]])` se cambia por `$1`.
5. Si también falla, se ignora. Se registra en depuración y la extracción no se rompe.

```
funcion objetoEquilibrado(texto, inicio):
    si texto[inicio] no es "{" ni "[": devolver nulo
    pila = 0; enCadena = nulo; escape = falso
    para i desde inicio hasta min(longitud, inicio + 3000000):
        c = texto[i]
        si enCadena:
            si escape: escape = falso
            si no, si c == "\": escape = verdadero
            si no, si c == enCadena: enCadena = nulo
            continuar
        si c es comilla doble, simple o acento grave: enCadena = c
        si no, si c es "{" o "[": pila += 1
        si no, si c es "}" o "]":
            pila -= 1
            si pila == 0: devolver texto[inicio .. i]
    devolver nulo
```

En Kotlin hay que escribir las mismas expresiones con `Regex(...)` y las barras invertidas dobladas dentro de cadenas normales, o usar cadenas crudas `"""..."""`.

### 4.1 Shopify

- **Cómo detectarla**: `cdn\.shopify\.com|ShopifyAnalytics|Shopify\.shop\s*=`.
- **Dónde está el precio**, en este orden:
  - `var\s+meta\s*=\s*(?=\{)` o `ShopifyAnalytics\.meta\s*=\s*(?=\{)`. Es un objeto `{"product":{"id":..,"variants":[{"id":..,"price":12999,...}]},"page":{"pageType":"product"}}`. **El precio va en céntimos** (12999 son 129,99 €).
  - `<script type="application/json" data-selected-variant>`: la variante elegida en los temas recientes (Dawn y derivados). Precio en céntimos.
  - `<script data-product-json>` o `<script id="ProductJson-...">`: temas antiguos. Objeto del producto con `variants[].price` en céntimos.
  - JSON-LD: Dawn ya lo trae, así que normalmente gana el paso 4.
  - Petición extra opcional: `https://<tienda>/products/<handle>.js` devuelve `price` y `variants[].price` en céntimos. En cambio, `/products/<handle>.json` da `variants[].price` como texto decimal («129.99»). Solo se usaría si no hay nada en la página, porque cuesta una segunda petición. En esta prueba, Shopify bloqueó ya la primera.
- **Variante**: si la URL tiene `?variant=<id>`, se usa la variante con ese `id`. Si no, la menor («desde»), y se avisa al usuario de que el producto tiene variantes.
- **Trampas**:
  - Céntimos en `meta`, `.js` y `data-selected-variant`; decimal en `.json` y JSON-LD.
  - `compare_at_price` es el precio tachado.
  - `og:price:amount` sale con el formato de dinero de la tienda («1.299,00» o «1,299.00»). Ya lo resuelve `importeDeMaquina`.
  - En JSON-LD, Dawn genera una oferta por variante. Con `?variant=`, conviene elegir la oferta cuya `url` contiene ese id, no la menor.
  - Bloqueo: las 8 tiendas Shopify probadas devolvieron 429 a `urllib` de Python con las cabeceras de la especificación, tanto la colección como la ficha. Hay que comprobarlo con el cliente HTTP real de cada app (requests u OkHttp). Si persiste, Shopify solo funcionará con los datos que lleguen, o no funcionará. No se debe intentar saltar.

### 4.2 WooCommerce

- **Cómo detectarla**: `woocommerce-Price-amount|wp-content/plugins/woocommerce|class="[^"]*woocommerce`.
- **Producto simple**: el primer elemento con clase `price` (`p.price`, `span.price` o `div.price`) **que sigue al título** `h1.product_title` en el orden del documento y que contiene `.woocommerce-Price-amount`.
  - Dentro, `ins .woocommerce-Price-amount` gana. Si no hay `ins`, la primera `.woocommerce-Price-amount` que no esté dentro de `del`.
  - No sirve `div.product .summary .price` a secas: en riovet.es un megamenú lleno de productos va antes del h1, y ese selector cogía un rango de otro producto (10,87 € en vez de 44,78 €).
- **Producto variable**: `form.variations_form[data-product_variations]` es un JSON con una lista de variaciones: `attributes` (por ejemplo `{"attribute_pa_peso":"1kg"}`), `display_price` (el que se enseña, con o sin IVA según la tienda), `display_regular_price` (tachado) e `is_in_stock`.
  - Si la URL trae parámetros `attribute_pa_...=valor`, se elige la variación que coincide.
  - Si no, el menor `display_price` entre las que están en stock, marcado como «desde».
  - Si el atributo vale `false`, la tienda tiene más de 30 variaciones (umbral de WooCommerce) y las carga con AJAX: no hay datos y se pregunta.
- **Rango** «12,00 € – 48,00 €» en `p.price`: importe «desde» (el menor). WooCommerce añade el texto para lectores de pantalla «Rango de precios: desde X hasta Y».
- **Trampas**:
  - `<span class="screen-reader-text">El precio original era: 47,05 €.</span>` está fuera de `del`: hay que penalizar por texto («precio original»).
  - Precios por cantidad de complementos de descuento (44,34 / 43,89 / 43,44 en riovet.es).
  - `twitter:data1` de Yoast suele ser «Tiempo de lectura»: solo vale si `twitter:label1` es «Precio».
  - Si la tienda muestra precios sin IVA, `display_price` puede ir sin IVA.

### 4.3 PrestaShop

- **Cómo detectarla**: `var prestashop\s*=|prestashop\s*=\s*\{|/modules/ps_|PrestaShop`.
- **PrestaShop 1.7 y 8**:
  - `#product-details[data-product]`: JSON (con entidades HTML que el parser ya decodifica) con:
    - `price_amount`: número con el IVA que ve el cliente (21.95);
    - `price`: texto formateado («€21.95», «7,50 €»);
    - `price_tax_exc`: sin IVA (19.95; 6.818182);
    - `price_without_reduction`: precio antes del descuento (el tachado);
    - `has_discount`, `discount_percentage` y `discount_amount`;
    - `quantity_discounts`: descuentos por cantidad.
    Verificado en dos tiendas reales. Se usa `price_amount`.
  - `.product-prices .current-price [itemprop=price][content]` o `.current-price-value[content]`: atributo `content` con el número.
  - La variable global `prestashop` lleva el carrito, la moneda y la tienda, pero no el precio del producto. Solo sirve para detectar la plataforma.
- **PrestaShop 1.6**: `#our_price_display` (atributo `content` si existe, si no el texto) y `var\s+productPrice\s*=\s*['"]?([\d.]+)`. En 1.6 existe también `productPriceTaxExcluded`, que no hay que usar.
- **Trampas**:
  - El dataLayer de los módulos de Google suele llevar `price` **sin IVA** (19.95 frente a 21.95 en complementosparaaves.com), aunque ese módulo además trae `price_tax_inc`.
  - `product:pretax_price:amount` también va sin IVA.
  - Las miniaturas de productos relacionados tienen su propio formulario de compra (cafesgranell.es). El bloque principal no puede ser «cualquier formulario de compra».

### 4.4 Magento 2

- **Cómo detectarla**: `x-magento-init|data-mage-init|Magento_[A-Z]|mage/cookies`. Ojo: la plantilla Hyvä (primor.eu) no tiene `x-magento-init`. Allí ganó el JSON-LD y, sin él, la heurística visible.
- **Dónde**: dentro de `.product-info-main` (o `.product-info-price`), el primer `[data-price-type="finalPrice"][data-price-amount]` que no esté dentro de `.old-price`. El atributo `data-price-amount` es un número de máquina («59.9»).
- **Configurables**: `"jsonConfig"\s*:\s*(?=\{)` y, dentro, `optionPrices.<id>.finalPrice.amount`. Se usa el menor, como «desde», salvo que el usuario elija opción.
- **Trampas**:
  - `data-price-type="oldPrice"` es el tachado.
  - `basePrice` es el precio sin IVA cuando la tienda muestra los dos.
  - Los bloques `related`, `upsell` y `crosssell` repiten `data-price-amount` con `finalPrice`. Hay que limitarse al bloque principal.
  - Precios escalonados (`tier`).

### 4.5 Salesforce Commerce Cloud (SFCC, antes Demandware)

- **Cómo detectarla**: `/on/demandware\.|demandware\.static|dwvar_`.
- **Dónde**: `.product-detail[data-pid] .prices .sales .value[content]` (número en `content`). El tachado está en `.strike-through .value` o `.list .value`.
- **Trampa**: las páginas de colección tienen muchos `.product-tile[data-pid]`. En hawkersco.com la URL `.html` era una colección: no hay que dar precio. Solo se acepta si hay un único `.product-detail` y un h1.

### 4.6 VTEX

- **Cómo detectarla**: `vteximg\.com|vtexassets\.com|data-varname="__STATE__"|skuJson_\d|vtex\.events`.
- **VTEX antiguo (CMS Portal)**:
  - `var\s+skuJson_\d+\s*=\s*(?=\{)` con `skus[].bestPrice` **en céntimos**. Solo cuentan los `available: true`. `listPrice` es el tachado.
  - `vtex\.events\.addData\(\s*(?=\{)` con `productPriceTo` (decimal) y `productPriceFrom`.
- **VTEX IO**: `<template data-type="json" data-varname="__STATE__"><script>{...}</script></template>`. Es un mapa plano de objetos de Apollo. Las claves que contienen `commertialOffer` llevan `Price` (venta), `ListPrice` (tachado), `PriceWithoutDiscount` y `AvailableQuantity`. Se usa el menor `Price` con `AvailableQuantity > 0`.
  - Ojo: en Jsoup y en BeautifulSoup, el texto de un `<script>` dentro de `<template>` se lee con `.data()` / `.string`, no con `text()` / `get_text()`.
- **Alternativa con petición extra**: `/api/catalog_system/pub/products/search?fq=skuId:<id>` es público en todas las tiendas VTEX (fuente: tabnews.com.br). No se propone por defecto.

### 4.7 BigCommerce

- **Cómo detectarla**: `BCData\s*=|cdn\d*\.bigcommerce\.com`.
- **Dónde**: `var\s+BCData\s*=\s*(?=\{)`. Se usa `product_attributes.price.with_tax.value`; si no existe, `without_tax.value`, marcándolo como posible precio sin IVA.

### 4.8 Otras plataformas

- **Shopware 6**: suele traer `meta[itemprop=price]` y JSON-LD, así que los pasos 5 y 6 bastan. En el HTML, el precio está en `.product-detail-price`.
- **Wix y Squarespace**: generan JSON-LD Product. Sin él, el precio lo pinta JavaScript y solo queda la heurística.
- **Plataformas propias** (mentta.com): variables de plantilla como `var scopeProduct = {...,"Name":"EVOO in Rama","Price":9.00,"OldPrice":null}`. Se cubren con el paso 8.

### 4.9 Estado de la aplicación (Next, Nuxt, Redux, Apollo)

- **Next.js**: `<script id="__NEXT_DATA__" type="application/json">`, JSON estricto. El producto suele estar en `props.pageProps`, con nombres libres (`product`, `data.product`, `initialData`...).
- **Nuxt 3**: `<script type="application/json" id="__NUXT_DATA__">` serializado con «devalue». Es una lista plana donde los enteros de los objetos son **índices** a otras posiciones de la lista, y `["Reactive", n]` o `["ShallowReactive", n]` envuelven un valor. Hay que reconstruirlo antes de buscar (función `devalue_nuxt` del prototipo).
- **Nuxt 2**: `window.__NUXT__=(function(a,b,c){return {...}}(1,"x",...))`. Es una función cuyos valores son parámetros: sin ejecutar JavaScript no se puede reconstruir con seguridad. Se ignora.
- **Redux, Apollo y otros**: `window\.(__INITIAL_STATE__|__PRELOADED_STATE__|__APOLLO_STATE__|__APP_STATE__|__STORE__)\s*=\s*(?=[{\[])`.
- **Variables de plantilla**: `(?:\b(?:var|let|const)\s+|window\.)([A-Za-z_$]*(?:[Pp]roduct|[Pp]roducto|[Ii]tem|[Pp]dp|[Ss]ku|[Oo]ffer)[A-Za-z0-9_$]*)\s*=\s*(?=\{)`.
- **Cualquier** `<script type="application/json">` de más de 50 caracteres.
- **Cómo se busca dentro**: se recorre el árbol entero. Un objeto es un producto si tiene una clave de nombre (`name`, `Name`, `title`, `productName`, `nombre`) y una de precio:
  - número o texto en `price`, `Price`, `salePrice`, `sellingPrice`, `finalPrice`, `currentPrice`, `priceValue`, `special_price`, `final_price`, `precio`, `pvp` o `amount`;
  - u objeto con `amount`, `value`, `current`, `final` o `sale`;
  - o `centAmount` (céntimos, commercetools);
  - o una clave que termina en `Cents` o `Centimos` (céntimos).
  Se descartan las claves con `old`, `was`, `list`, `regular`, `original`, `compare`, `before`, `strike`, `base`, `shipping`, `tax`, `unit`, `min`, `max` o `anterior`.
- **Parecido del nombre**: proporción de palabras de 4 letras o más del nombre del objeto que aparecen en `og:title` + h1. Con 0,5 o más es candidato oculto. Con 0,8 o más, y un único importe, puede decidir (apartado 6.6). Así se evita coger un producto relacionado del mismo JSON.

### 4.10 Analítica y píxeles

Sirven sobre todo para **corroborar** un candidato visible. Muchas implementaciones mandan el precio **sin IVA**.

- **GA4 en dataLayer**: `['"]?event['"]?\s*:\s*['"]view_item['"]`. Se retrocede a la llave que abre el objeto que la contiene (hasta 6 llaves atrás) y se extrae con llaves equilibradas. Se leen `ecommerce.items[0].price` y `ecommerce.value`. Si existe `items[0].price_tax_inc` (módulos de PrestaShop), se usa ese.
- **gtag**: `gtag\(\s*['"]event['"]\s*,\s*['"]view_item['"]\s*,\s*(?=\{)`, con `items[0].price` o `value`.
- **Universal Analytics**: `['"]?detail['"]?\s*:\s*(?=\{\s*['"]?(?:actionField|products))`, con `products[0].price`.
- **Píxel de Facebook**:
  - `fbq\(\s*['"]track['"]\s*,\s*['"]ViewContent['"]\s*,\s*(?=\{)`, con `value`;
  - en `<noscript>`: `facebook\.com/tr\?[^"'<>\s]*ev=ViewContent[^"'<>\s]*`. Tras decodificar `&amp;`, se leen los parámetros `cd[value]` o `cd[product_price]`.
- **PixelYourSite** (WordPress): `"name"\s*:\s*"ViewContent".{0,600}?"value"\s*:\s*"?([\d.]+)`, con el punto que abarca saltos de línea.
- **Klaviyo**: `['"]Viewed Product['"]\s*,\s*(?=\{)`, con `Price` o `Value`.
- **Remarketing de Google**: `['"]?ecomm_totalvalue['"]?\s*:\s*['"]?(\d+(?:\.\d+)?)`. Si al lado está `ecomm_totalvalue_tax_exc`, la primera es con IVA.
- **Criteo**: `criteo_q.push({event:"viewItem", item:"<id>"})` solo trae el identificador, no el precio. No sirve.
- **twitter:label1 / twitter:data1** (también `label2`/`data2`): solo si la etiqueta cumple `^\s*(precio|price|prix|preço|prezzo)\s*$` (sin distinguir mayúsculas). El dato es texto formateado y se lee con `analizarImporte`.
- **og:price:amount / product:price:amount**: ya están en el paso 5.

Familias para contar «fuentes independientes»: estado, dataLayer, gtag, fbq (incluye PixelYourSite y noscript), Klaviyo, ecomm y twitter.

## 5. Detección de plataforma: firmas

Se buscan en el HTML crudo, en este orden. Puede haber varias; se prueban todas en orden.

- `shopify`: `cdn\.shopify\.com|ShopifyAnalytics|Shopify\.shop\s*=`
- `woocommerce`: `woocommerce-Price-amount|wp-content/plugins/woocommerce|class="[^"]*woocommerce`
- `prestashop`: `var prestashop\s*=|prestashop\s*=\s*\{|/modules/ps_|PrestaShop`
- `magento`: `x-magento-init|data-mage-init|Magento_[A-Z]|mage/cookies`
- `sfcc`: `/on/demandware\.|demandware\.static|dwvar_`
- `vtex`: `vteximg\.com|vtexassets\.com|data-varname="__STATE__"|skuJson_\d|vtex\.events`
- `bigcommerce`: `BCData\s*=|cdn\d*\.bigcommerce\.com`

Una firma mal escogida da falsos positivos. Por ejemplo, `mage/` aparece en cualquier `image/png`. Por eso las firmas son concretas, y el extractor de cada plataforma devuelve nulo si no encuentra su estructura.

## 6. Heurística de candidatos sobre el HTML visible

Inspiración: el conjunto de reglas de Mozilla Price Tracker (Fathom). Puntuaba los `span` y `h2` por estas señales: símbolo de moneda, «price» en el id o la clase del elemento o del padre, tamaño de letra, posición en la primera pantalla y cercanía a la imagen principal, y elegía el máximo. Sin ejecutar JavaScript no hay tamaños ni posiciones, así que se sustituyen por relaciones en el árbol: cercanía al h1 y al botón de compra, y estar dentro del bloque principal. De PriceGhost se toma la idea de votar entre métodos y, si no hay mayoría, preguntar al usuario.

### 6.1 Qué es un candidato

Se recorren todos los elementos, excepto los que son o están dentro de `script`, `style`, `noscript`, `template`, `svg`, `head`, `iframe`, `select`, `option`, `button`, `label` y `title`.

Un elemento es candidato si cumple alguna de estas condiciones:

- Su texto (normalizado, de 48 caracteres o menos) contiene un importe con moneda: `RE_PRECIO_TEXTO`.
- Tiene `data-price-amount`, `data-price`, `data-product-price` o `data-price-value` con un número.
- Tiene `itemprop="price"` con `content`.
- Sus atributos contienen una palabra de precio (`RE_CLASE_PRECIO`) y su texto tiene un número con dos decimales (`\d[.,]\d{2}\b`).

Además:

- Se descarta el elemento si un descendiente suyo da el mismo importe. Así queda el más profundo, y la etiqueta «Precio:» queda como contexto, no como parte del candidato.
- Se descartan los trozos decimales de un precio partido: texto que empieza por `^[.,]\s?\d` (por ejemplo «,29 €» en Obramat). Lo recoge su contenedor («11,29 EUR»).
- Se descartan los importes ≤ 0 y los mayores de 1 000 000.

Expresiones regulares exactas, en sintaxis de Python:

```
MONEDA = (?:€|EUR|eur|euros?|\$|USD|£|GBP)
NUM = \d{1,3}(?:[.\s  ]\d{3})*(?:[.,]\d{1,2})?|\d+(?:[.,]\d{1,2})?
RE_PRECIO_TEXTO = (?:MONEDA\s*(?:NUM)|(?:NUM)\s*,?-?\s*MONEDA)
RE_CLASE_PRECIO = price|precio|prezzo|preco|preis|prix|amount|importe|pvp|cost|tarifa|money   (sin mayúsculas)
```

### 6.2 Anclas: h1, botón de compra, bloque principal y zonas ajenas

- **h1 del producto**: el primer `h1` con texto que no esté dentro de `nav` o `footer`, ni dentro de un `header` que sea la cabecera de la web.
  - Un `header` es cabecera de la web si contiene un `nav`, si su clase o id cumple `site|masthead|main-header|page-header|top-?bar|cabecera`, o si es hijo directo de `body`.
  - Un `<header>` dentro de una sección es válido: en espressocoffeeshop.com el h1 del producto está en `<section class="ecs-product"><header>`.
  - Si no hay h1: `.product_title, .product-title, .product-name, [itemprop=name]`.
- **Botón de compra**: `button`, `input` o `a` cuyo texto (de menos de 40 caracteres) cumple `RE_BOTON_CARRITO`, o cuya clase, nombre, id o `data-button-action` cumple `add-to-cart|addtocart|add_to_cart|btn-cart|tocart|buy-button`. Se descartan los que están en una zona ajena. Se elige **el primero que va después del h1** en el orden del documento; si no hay, el primero de la página.
  - `RE_BOTON_CARRITO = a[ñn]adir al carrito|a[ñn]adir a la cesta|a[ñn]adir a la bolsa|comprar ahora|comprar\b|add to (cart|bag|basket)|buy now|añadir$|reservar` (sin mayúsculas). En Obramat el botón dice «Añadir al pedido» y se encontró por la clase `a-add-to-cart`.
- **Bloque principal**: el ancestro común más bajo del h1 y del botón. No vale si es `body` o `html`, ni si tiene más de la mitad de los elementos de la página (salvo en páginas de menos de 300 elementos).
- **Zona ajena**: un ancestro que **no contiene el h1** y que cumple una de estas condiciones:
  - es `footer`, `nav` o `aside`;
  - es un `header` de la web;
  - alguna de sus clases, o su id, cumple `RE_ZONA_AJENA`.
  Nunca son zona ajena `body`, `html` y `main`. Lo de «no contiene el h1» es clave: sin ello, clases del `body` como `page-product` o el id `product-50020` del artículo marcaban la página entera como ajena.

```
RE_ZONA_AJENA = related|relacionad|recommend|recomend|upsell|up-sell|cross-?sell|carousel|carrusel|slider|swiper|similar|recent|viewed|vistos|also|tambien|bundle|accesor|complement|footer|header|navbar|menu|minicart|mini-cart|cart-drawer|widget_shopping_cart|sidebar|newsletter|popup|modal|banner|product-tile|product-item(?!-info)|product-card|miniature|grid-product|product-list|productos-|products-grid|tile|frequently|compra-junto|pack
```

### 6.3 Contexto adyacente

Las palabras que cambian el significado de un importe («/mes», «€/kg», «+ IVA», «Antes:», «Precio:») van pegadas a él. Mirar el texto del padre entero es peligroso: si el padre contiene el precio y la cuota, los dos salen penalizados. Por eso el contexto es:

- **antes**: el texto de los hermanos anteriores, hasta 40 caracteres, parando si un hermano contiene otro importe;
- **después**: lo mismo con los hermanos siguientes;
- si el elemento no tiene hermanos con texto, se sube al padre, hasta 3 niveles.

```
funcion contextoAdyacente(el):
    nodo = el
    repetir 3 veces:
        antes = texto de nodo.hermanosAnteriores (del más cercano hacia atrás),
                parando en el primero que contenga RE_PRECIO_TEXTO, como mucho 40 caracteres
        despues = igual con nodo.hermanosSiguientes
        si antes o despues no vacios, o nodo no tiene padre: salir
        nodo = nodo.padre
    devolver (antes, despues)
```

### 6.4 Pesos de la puntuación

Cada candidato empieza con 0 puntos. «Cerca» quiere decir el propio elemento y sus 3 primeros ancestros. «t» es el texto del candidato.

Suman:

- +2: el texto lleva moneda.
- +2: el id, la clase, `itemprop` o algún `data-*` de cerca contiene `RE_CLASE_PRECIO`.
- +1: además, contiene `RE_CLASE_ACTUAL` y no `RE_CLASE_TACHADO`.
- +2: tiene `itemprop="price"` o `data-price-amount`, o está dentro de `[data-price-type="finalPrice"]`.
- +4: está dentro del bloque principal.
- Hasta +2: cercanía al h1. Son 2 × (1 − d / 300), donde d es la distancia en número de elementos según el orden del documento. Si d es mayor que 300, no suma.
- Hasta +2: cercanía al botón de compra. Son 2 × (1 − d / 150).
- +1: «precio actual», «ahora», «precio final» o «tu precio» en t o justo antes. Si no, +1 por una etiqueta justo antes que cumpla `\b(precio|p\.?v\.?p\.?|price|importe)\s*:`.
- +1: «IVA incluido» en t o justo después: `iva incl|con iva|impuestos incl|vat incl|tax incl|igic incl`.
- +3: el importe coincide con un candidato oculto (pasos 8 y 9). +1 más si coincide con dos familias o más.

Restan:

- −6: tachado. Puede ser por la etiqueta `del`, `s` o `strike` en el elemento o en sus 4 ancestros; por una clase o id que cumple `RE_CLASE_TACHADO`; por `line-through` en `style`; o por `data-price-type` igual a `oldPrice` o `basePrice`.
- −6: texto de precio anterior en t o justo antes (`RE_ANTES`), si no estaba ya marcado como tachado.
- −6: cuota o financiación en t o alrededor (`RE_CUOTA`).
- −5: zona ajena, si no está dentro del bloque principal.
- −5: ahorro o descuento en t o justo antes (`RE_AHORRO`).
- −5: envío en t o justo antes (`RE_ENVIO`).
- −5: precio por kilo, litro o dosis en t o en los 15 primeros caracteres de después (`RE_UNIDAD`).
- −1: «por unidad» o «/ud» en t (`RE_UNIDAD_DEBIL`). Pesa poco porque en las tiendas de bricolaje («11,29 € IVA por Unidad» en Obramat) suele ser el precio de venta.
- −4: sin IVA alrededor (`RE_SIN_IVA`).
- −2: «desde» o «a partir de» en los 25 caracteres de antes o al principio de t.
- −2: está a más de 400 elementos por encima del h1.

Expresiones regulares (todas sin distinguir mayúsculas):

```
RE_CLASE_ACTUAL = current|final|sale|special|actual|now|offer|oferta|promo|selling|our[-_]?price|regular-price__current|price--main|main-price|product-price
RE_CLASE_TACHADO = old|was|before|regular(?!-price__current)|compare|tachad|anterior|strike|crossed|rrp|pvpr|list-?price|original|antes|precio-?base|price-?before|discount-from
RE_ANTES = precio original|precio anterior|precio de venta recomendado|pvp ?rec|pvpr|antes:?\s|\bwas\b|\brrp\b|original price|regular price|precio habitual|precio sin descuento
RE_ACTUAL_TXT = precio actual|current price|ahora:?\s|now:?\s|precio final|tu precio
RE_CUOTA = /\s*mes|al mes|mensual|cuotas?|financ|plazos|meses|month|/mo\b|aplazame|sequra|klarna|pagantis|paypal en 3|en \d+ pagos
RE_AHORRO = ahorr|descuento|dto\.?|save|you save|-\s*\d+\s*%|\d+\s*%\s*(dto|off)|rebaja de
RE_ENVIO = env[ií]o|gastos|shipping|entrega|portes|gratis a partir|pedidos? superiores?|free delivery
RE_UNIDAD = /\s*(kg|g|l|ml|m2|m²|m|100\s*g|100\s*ml|lavado|dosis|litro|kilo|cápsula|capsula)\b|por (kilo|litro|lavado|dosis|cápsula)|precio (por kilo|por litro|unitario)|\bunit price|€\s*/\s*(kg|l|m)
RE_UNIDAD_DEBIL = /\s*(ud|u|unidad|uds)\b|por unidad
RE_SIN_IVA = sin iva|iva no incl|\+\s*iva|excl\.?\s*(iva|vat|tax)|tax excl|base imponible|antes de impuestos|vat excl|pretax|sin impuestos
RE_DESDE = \b(desde|a partir de|from|ab|starting at)\b
```

### 6.5 Umbral y decisión

- `UMBRAL = 8`: puntos mínimos del mejor candidato visible.
- `MARGEN = 3`: ventaja mínima sobre el mejor candidato con **otro** importe. Varios candidatos con el mismo importe (precio y texto para lectores de pantalla, versión de escritorio y de móvil) no compiten entre sí.
- `UMBRAL_UNICO = 5`: si en toda la página solo hay **un** importe con puntos positivos, hay botón de compra y el candidato no tiene ninguna penalización, se acepta con confianza baja. Esta regla se añadió por la página reservada (alcaiceria.com: sin h1 ni datos estructurados, solo «P.V.P.: 1,80 €» junto al botón). Sin ella, la heurística se abstenía y preguntaba al usuario, lo cual también era correcto.
- Por qué 8: un precio normal del bloque principal suma 2 (moneda) + 2 (clase) + 4 (bloque) + entre 1 y 4 (cercanía) = de 9 a 12. Un precio de relacionados con moneda y clase, pero fuera del bloque, suma 4 − 5 = −1. Un precio del bloque con una penalización fuerte baja a 3-6. En las 12 páginas, los aciertos sacaron entre 9,3 y 15 puntos, y el mejor candidato de la colección de Hawkers (que no es una ficha) quedó en negativo.

### 6.6 Cuándo decide lo oculto

- Si **dos familias o más** (por ejemplo, dataLayer y píxel de Facebook) dan el mismo importe y no hay ningún otro importe oculto: se acepta con confianza media. En el vector sintético, GA4 y fbq dieron 79 €.
- Si un objeto de **estado** tiene un nombre que coincide al menos al 80 % con el título, solo hay un importe así y ningún visible pasa el umbral: se acepta con confianza media. En mentta.com, el precio lo pinta JavaScript y está en `var scopeProduct`.
- En los demás casos, lo oculto solo da el bono de +3 a los visibles. Por ejemplo, en complementosparaaves.com el dataLayer da 19,95 sin IVA, y no debe decidir.

## 7. Selección asistida por el usuario (accesible)

### 7.1 Lista de candidatos

- Se enseña cuando el resultado es «sin precio», y también desde «Editar → Elegir el precio en la página» aunque haya precio.
- **Agrupación**: los candidatos con el mismo importe y el mismo tipo de contexto se agrupan en una sola opción. Se queda el de más puntos, que es el elemento que se guardará. Como mucho 8 opciones, ordenadas por puntos. Al final van «Ninguno de estos» y «Escribir un selector».
- **Texto de cada opción** (lo que lee TalkBack o el lector de Windows): importe en formato español, una raya y el contexto en palabras, sin códigos ni puntuaciones. Ejemplos reales del prototipo:
  - «39,99 € — junto al botón de compra, coincide con los datos internos de la página — "El precio actual es: 39,99 €."»
  - «47,05 € — tachado, junto al botón de compra — "El precio original era: 47,05 €."»
  - «28,06 € — en otra zona (relacionados, carrusel o pie)»
  - «9,33 € — junto al botón de compra, sin IVA — "9,33 € sin IVA / Unidad"»
  - «12,00 € — junto al botón de compra — "Rango de precios: desde 12,00 € hasta 48,00 €"»
- Palabras del contexto, en este orden: tachado; junto al botón de compra; en otra zona (relacionados, carrusel o pie); cuota o financiación; precio por kilo o litro; envío; sin IVA; desde; coincide con los datos internos de la página. Después, entre comillas, el texto corto que rodea al importe.
- Accesibilidad:
  - En Android, un `RadioGroup` (o una lista de una sola parada) con el texto completo como nombre accesible y el botón «Usar este precio».
  - En Windows, un `wx.ListBox` o `wx.RadioBox` con el mismo texto.
  - El foco empieza en la primera opción. Al confirmar, se anuncia «Precio guardado: 39,99 €. Se usará esta posición de la página en las próximas comprobaciones.».
  - Si el selector no pasa la validación, se anuncia el motivo y la lista sigue abierta.

### 7.2 Generar un selector CSS estable

Basado en `@medv/finder` (penalizaciones: id 0, clase 1, atributo 2, etiqueta 5, `nth-of-type` 10, `nth-child` 50, y un nombre debe parecer una palabra) y en el generador de selectores de Playwright, que prefiere atributos de prueba como `data-testid`.

Orden:

1. **Atributos semánticos** del propio elemento, como `etiqueta[atributo="valor"]`, si el valor es estable: `itemprop`, `data-price-type`, `data-test`, `data-testid`, `data-test-id`, `data-qa`, `data-cy`, `data-role`, `data-element`, `data-hook`, `data-automation`, `data-ui` y `name`.
2. **`#id` estable.**
3. **Etiqueta y una clase estable**, después etiqueta y dos clases estables.
4. **Ancestro estable y descendiente**: hasta 8 niveles hacia arriba, `ancestro elemento` (por ejemplo `p.price bdi` o `#product-price meta[itemprop="price"]`).
5. **Ancestro estable y ruta corta** con `>` y `:nth-of-type`, hasta 5 niveles (por ejemplo `p.price > span:nth-of-type(2)`).
6. Si nada es único: un selector cuyo **primer** resultado sea el elegido. La especificación ya dice que se usa el primer elemento con importe válido.
7. **Último recurso**: ruta completa con `:nth-of-type` desde el ancestro con id más cercano, o desde `body`. Es frágil, así que se guarda marcada como tal y se pide volver a elegir a la primera rotura.

Un nombre (clase, id o valor de atributo) es **estable** si cumple todo esto:

- Mide entre 3 y 60 caracteres.
- No cumple `RE_GENERADO`:

```
^(?:css|sc|jsx|emotion|e|tw|svelte|astro|chakra|mui|Mui[A-Za-z]*|makeStyles|styled|ng-tns|ember|v|data-v)-[A-Za-z0-9_-]*\d[A-Za-z0-9_-]*$
|^[A-Za-z][\w-]*_{1,2}(?=[A-Za-z0-9-]*\d)[A-Za-z0-9-]{5,}$
|^_?(?=[a-zA-Z]*\d)(?=\d*[a-zA-Z])[a-zA-Z0-9]{5,8}$
|[:\[\]/!@]
|\d{3,}
```

  En orden: prefijos de CSS en JavaScript con cifras (`css-1x2y3z`, `sc-abc123`, `jsx-2847563`, `svelte-x1y2`); CSS Modules (`Price_price__a1B2c`); hashes cortos (`a1b2c3`); Tailwind (`md:text-lg`, `w-[12px]`, `w-1/2`); y tres cifras seguidas.
- No es una clase de estado o maquetación: `^(?:is-|has-|js-is-|active|selected|current-?item|open|closed|hover|focus|visible|hidden|loaded|lazy|show|fade|in|d-|col-|row|flex|grid|mt-|mb-|ml-|mr-|pt-|pb-|p-|m-|text-|font-|bg-|w-|h-|swiper-slide|slick-)`.
- Ningún trozo (separando por `-`, `_` o un cambio de minúscula a mayúscula) tiene 5 consonantes seguidas o más.

Ejemplos: `product-price`, `current-price`, `price__current`, `js-product-price` y `woocommerce-Price-amount` son estables; `css-1x2y3z`, `sc-abc123`, `Price_price__a1B2c`, `md:text-lg` e `is-active` no lo son.

Se guarda también el atributo del que se lee el valor, si lo hay (`content`, `data-price-amount`, `data-price`...). Así el importe se lee como número de máquina y no como texto.

### 7.3 Validar el selector

Antes de guardarlo:

1. `select(selector)` devuelve **exactamente un** elemento, o en el caso 6 del apartado anterior, el primero es el elegido.
2. Ese elemento es el que eligió el usuario.
3. Su importe (atributo o texto) es **el mismo** que el de la opción elegida.

Si falla, se prueba el siguiente selector de la lista de preferencia.

Se guarda junto al selector una **huella**: el importe y el texto de contexto en el momento de elegirlo. En cada comprobación:

- Si el selector devuelve 0 elementos, o el importe cambia más de un 70 %, se vuelve al extractor automático.
- Si este da otro precio, se avisa con el error «La posición del precio en la página ha cambiado. Vuelve a elegir el precio en Editar.».

Nunca se guarda en silencio un precio de un selector roto.

Selectores generados en la prueba real (los 10 válidos):

- `span.current-price-value` (atributo `content`) en cafesgranell.es
- `#product-price meta[itemprop="price"]` (atributo `content`) en primor.eu
- `div.product__price` en espressocoffeeshop.com
- `p.price bdi` en riovet.es
- `p.price > span:nth-of-type(2)` en veganmilker.com y en ferreteriadosil.es
- `p.price span.screen-reader-text` en cafelab.es
- `p.-main span.kl-hidden-accessibility` en obramat.es
- Rutas largas, frágiles, en complementosparaaves.com (Elementor, con el precio repetido para escritorio y móvil) y en alcaiceria.com (HTML de 2010 con `<font>`)

## 8. Moneda, IVA, rangos y variantes

### 8.1 Números de máquina

`importeDeMaquina` lee «12.990» como 12 990, porque sigue la regla de los miles. En los campos que siempre son de máquina (números JSON, `data-price-amount`, `content`, `price_amount`, `display_price`) conviene una lectura más estricta:

- `numeroDeMaquina(v)`:
  - si es un número JSON, tal cual;
  - si el texto cumple `^\d+(?:\.\d+)?$`, número con punto decimal y redondeo a 2 decimales («12.990» da 12,99; «19.950000» da 19,95; «59.9» da 59,9);
  - si no, `importeDeMaquina`.
- Céntimos: solo donde la plataforma lo documenta (Shopify `meta`, `.js` y `data-selected-variant`; VTEX `bestPrice`; `centAmount`; claves que terminan en `Cents`). Se divide entre 100.

### 8.2 Moneda

- En orden: la moneda del dato de plataforma (`priceCurrency`, `currency`, `ShopifyAnalytics.meta.currency`, `prestashop.currency.iso_code`), después `product:price:currency` u `og:price:currency`, después el símbolo del texto del candidato y, si no, `EUR`.
- Propuesta, todavía no implementada en el prototipo: si el candidato visible tiene un símbolo distinto del de la tienda (por ejemplo, «$» en una tienda en euros), se penaliza con −3. Puede ser un selector de país.

### 8.3 IVA

En España, la ley obliga a mostrar al consumidor el precio final con impuestos, así que el precio grande de la ficha suele llevar IVA. Lo que va sin IVA:

- `product:pretax_price:amount`, `price_tax_exc` y `productPriceTaxExcluded` (PrestaShop);
- `data-price-type="basePrice"` (Magento);
- `without_tax` (BigCommerce);
- a menudo, `items[].price` del dataLayer;
- tiendas profesionales (B2B) que enseñan «+ IVA».

Reglas:

- No leer nunca los campos sin IVA si existe el campo con IVA.
- Penalizar −4 los visibles con «sin IVA», «+ IVA» o «base imponible».
- La analítica no decide sola.
- Si el único precio de la página es sin IVA (tienda B2B), no se convierte: se pregunta, y la opción dice «sin IVA».

### 8.4 Rangos y «desde»

- Un rango («12,00 € – 48,00 €», «desde 12 €», AggregateOffer `lowPrice`) se guarda como el importe menor, con la marca `desde = verdadero`.
- La pantalla del producto dice «desde 12,00 €». Cuando el producto tiene variantes, se sugiere elegir una: pegar la URL de la variante (con `?variant=` o `attribute_pa_...`) o elegir el precio en la lista.
- Los avisos de bajada con un precio «desde» se redactan con cuidado: «El precio mínimo de <nombre> ha bajado...».

### 8.5 Variantes

La variante sale de la URL:

- Shopify: `variant=`.
- WooCommerce: `attribute_pa_*=` o `attribute_*=`.
- PrestaShop: `id_product_attribute=` o el ancla `#/<id>-<grupo>-<valor>`. PrestaShop 1.7 ya da el precio de la combinación por defecto en `data-product`; la de la URL con ancla solo se resuelve por AJAX, así que se pregunta si difiere.
- Magento: `?super_attribute`. Si no se puede resolver, «desde».

### 8.6 Precio por unidad, por cantidad y de socio

- Precio por kilo o litro: penalización −5. «Por unidad»: solo −1.
- Escalones por cantidad («2 o más: 44,34 €»), precio de socio (IKEA Family, MyMediaMarkt) y precios con cupón: no son el precio. En JSON-LD, `priceSpecification` con `validForMemberTier` se ignora (ya está en la investigación anterior).

## 9. Resultados del prototipo

### 9.1 Archivos

En `adjuntos/prototipo_extractor/`:

- `extractor_generico.py`: los pasos 7 a 11, la versión compacta de los pasos 4 a 6 (para comparar) y `describir_candidato`.
- `selector_css.py`: genera y valida selectores.
- `importes.py`: `analizar_importe` e `importe_de_maquina`, copiados de la especificación.
- `descarga.py`: la descarga con las cabeceras de la especificación. No salta bloqueos.
- `probar.py`: prueba contra páginas. Solo guarda resultados, nunca el HTML.
- `pruebas_sinteticas.py`: 19 vectores de plataformas y trampas.
- `esperados.json`, `resultados.json` y `resultados.txt`.

Uso: `python -I probar.py --urls lista.txt` descarga cada URL una vez y prueba. Necesita `beautifulsoup4`. Se usó un entorno virtual temporal, ya borrado.

### 9.2 Descargas

- Se pidió una sola vez cada página. De 11 tiendas se descargó la portada o una categoría, para elegir un producto; de las demás, directamente la ficha.
- 12 fichas válidas de 11 tiendas: WooCommerce (veganmilker.com, ferreteriadosil.es, cafelab.es, riovet.es), PrestaShop (espressocoffeeshop.com, cafesgranell.es, complementosparaaves.com), Magento 2 Hyvä (primor.eu), Salesforce Commerce Cloud (hawkersco.com, una página de colección que sirve de control negativo), Obramat (plataforma propia de Adeo), mentta.com (propia) y alcaiceria.com (PHP antiguo, página reservada).
- Bloqueadas, sin intentar saltar el bloqueo:
  - 429 en 8 tiendas Shopify: pompeiibrand.com, ineffablecoffee.com, ecoalf.com, todoanimal.es, olivarte.es, maiashop.es, santaeulalia.com y smartinnovashop.com;
  - 429 en planetahuerto.es;
  - 403 en naturitas.es, dosfarma.com, mifarma.es y recambioscoche.es.
- Las páginas se guardaron temporalmente en el scratchpad para no repetir descargas y se borraron al terminar.

### 9.3 Aciertos

Sobre 12 fichas:

- **Especificación actual** (pasos 4 a 6): 10 de 12. Falla en veganmilker.com (WooCommerce sin JSON-LD Product ni metas) y alcaiceria.com (sin datos estructurados). Ninguno de los dos fallos es un precio falso: no encuentra precio.
- **Con la ampliación**: 12 de 12, 0 precios falsos. En veganmilker.com acierta WooCommerce (39,99 € y no el tachado 47,05 €); en alcaiceria.com, el candidato único.
- **Sin JSON-LD ni metas** (simulando que la tienda no los tiene): 12 de 12, 0 falsos. Fuentes que ganan:
  - plataforma en 6: PrestaShop `data-product` (2), WooCommerce `.price` tras el título (3) y variaciones de WooCommerce (1);
  - heurística visible en 4;
  - estado embebido en 1 (mentta.com);
  - abstención correcta en 1 (la colección de Hawkers).
- **Solo heurística visible**: 11 de 12, 0 falsos. En cafelab.es (producto variable con rango 12 a 48 €) se abstiene y pregunta, que es lo deseable.
- **Página reservada** (alcaiceria.com, no usada para ajustar): la primera versión se abstuvo. Tras añadir la regla de candidato único (general, no específica de esa tienda), acierta 1,80 €.
- **Vectores sintéticos**: 19 de 19. Cubren Shopify (`meta` en céntimos con variante y `data-selected-variant`), Magento Luma, variaciones de WooCommerce con atributo en la URL, PrestaShop 1.6, SFCC, VTEX antiguo e IO, BigCommerce, Next, Nuxt 3 y analítica sola. También estas trampas: cuota mensual, precio por kilo, precio con IVA frente a sin IVA, tachado con «Ahorra», página de categoría, envío gratis como único importe y `twitter:data1`.
- Tiempo: entre 0,06 y 0,6 segundos por página en un PC, contando las tres pasadas de la prueba.

### 9.4 Límites honestos

- 12 páginas son pocas. Los pesos se ajustaron con 11 de ellas, así que el acierto real en tiendas nuevas será menor. La protección contra precios falsos es el umbral, el margen y la abstención.
- Hay que seguir ampliando `esperados.json` con cada tienda que falle, y convertir los casos en vectores compartidos (`compartido/pruebas/`) para las dos apps.
- Shopify y VTEX solo se han probado con vectores sintéticos.
- Las tiendas que pintan el precio solo con JavaScript y no lo dejan en ningún dato quedan fuera (`__NUXT__` de Nuxt 2, por ejemplo). Para ellas está la selección del usuario o el error.

## 10. Reglas recomendadas para añadir a ESPECIFICACION.md

1. Añadir los pasos 7 a 12 del apartado 2, con los extractores de plataforma del apartado 4 y las firmas del apartado 5.
2. En el paso 5, no leer nunca `product:pretax_price:amount`.
3. Añadir `numeroDeMaquina` (apartado 8.1) para los campos de máquina de plataforma (`data-price-amount`, `content`, `price_amount`, `display_price`, números de JSON incrustado). Documentar qué campos van en céntimos.
4. Shopify: con `?variant=<id>`, elegir la variante y la oferta JSON-LD de esa variante, no la menor.
5. WooCommerce: el precio es el primer `.price` después de `h1.product_title`. Dentro, `ins` gana a `del`. Las variaciones van en `data-product_variations`, eligiendo por los atributos de la URL.
6. Magento 2: `finalPrice` dentro de `.product-info-main`, nunca `oldPrice` ni `basePrice`, ni fuera del bloque principal.
7. La analítica y el estado incrustado no deciden solos, salvo las dos excepciones del apartado 6.6. Sirven para dar +3 a un candidato visible.
8. Heurística visible con los pesos del apartado 6.4, el contexto adyacente del 6.3, las anclas del 6.2 y la decisión con `UMBRAL = 8`, `MARGEN = 3` y `UMBRAL_UNICO = 5` del 6.5. Los vectores sintéticos y reales se pasan a `compartido/pruebas/extractor_generico.json` para que Windows y Android den el mismo resultado.
9. Resultado con `fuente` y `confianza`. Con confianza media o baja, un cambio de más del 50 % se comprueba otra vez antes de avisar.
10. Rango o variantes sin elegir: guardar el menor importe con `desde = 1`, mostrar «desde» y ofrecer elegir la variante.
11. Si no hay precio seguro, la lista accesible del apartado 7.1. Al elegir, se genera el selector (7.2), se valida (7.3) y se guarda en `selector_precio` del producto, con su atributo y su huella. Un selector roto da un error claro y no un precio.
12. Nuevo error: «La posición del precio en la página ha cambiado. Vuelve a elegir el precio en Editar.».
13. La respuesta 429 de Shopify es bloqueo: ya está en la especificación y no se intenta saltar. Conviene probar el cliente HTTP real de cada app con dos o tres tiendas Shopify, para saber si las apps quedan bloqueadas como `urllib`.

## 11. Fuentes

- Mozilla Price Tracker, reglas de Fathom para el precio: https://github.com/mozilla/price-tracker/blob/master/src/extraction/fathom/ruleset_factory.js
- @medv/finder, generador de selectores CSS: https://github.com/antonmedv/finder
- PriceGhost (`backend/src/services/scraper.ts`): voto entre métodos, selectores de Magento y filtro de cuotas. Clonado en `adjuntos/PriceGhost`.
- PriceBuddy (`config/price_buddy.php`): estrategias de autodetección. Clonado en `adjuntos/pricebuddy`.
- changedetection.io (`processors/restock_diff/pure_python_extractor.py`): JSON-LD, OpenGraph y microdatos sin lxml. Clonado en `adjuntos/changedetection.io`.
- price-parser de Zyte (Scrapinghub): lectura de importes y monedas. Clonado en `adjuntos/price-parser`.
- extruct de Zyte: extractor de JSON-LD, microdatos, OpenGraph y RDFa, de referencia para los pasos 4 a 6: https://github.com/scrapinghub/extruct
- API pública del catálogo de VTEX y significado de `Price` y `ListPrice`: https://www.tabnews.com.br/antoniorincon/a-api-publica-de-catalogo-da-vtex-que-quase-ninguem-usa
- Documentación de los bloques de precio de VTEX: https://developers.vtex.com/docs/apps/vtex.product-price@1.9.0
- Plantillas de PrestaShop con `rounded_display_price` y `price_amount`: https://gist.github.com/caovillanueva/e69f8981a8ba723b29d6ad5922734b06
- Listado de tiendas WooCommerce en España usado para elegir tiendas: https://www.storecensus.com/woocommerce-stores/country/spain?page=16
- Investigación anterior del proyecto: `adjuntos/investigacion-seguimiento-precios.md`.
- Estructuras comprobadas en páginas reales (2 de noviembre de 2026): `#product-details[data-product]` de PrestaShop, `p.price` y `data-product_variations` de WooCommerce, píxel de Facebook en `noscript` y PixelYourSite, `var scopeProduct` de mentta.com, y el dataLayer sin IVA de complementosparaaves.com.
