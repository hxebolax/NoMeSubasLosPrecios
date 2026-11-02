# Especificación común de No Me Subas Los Precios

Este documento es el contrato entre la app de **Windows** (Python y wxPython) y la de **Android** (Kotlin). Las dos hacen lo mismo, guardan lo mismo y se pasan los datos con el mismo archivo. Si se cambia algo aquí, se cambia en las dos.

## Identidad

- Nombre visible: **No Me Subas Los Precios**.
- Nombre corto (archivos, carpetas): `NoMeSubasLosPrecios`.
- Paquete Android: `com.xebolax.nomesubaslosprecios` (la versión de pruebas añade `.pruebas`).
- Autor: Héctor J. Benítez Corredera.
- Versión inicial: 1.0.0 en las dos apps. Las dos llevan siempre el mismo número de versión.
- Todo en español de España: interfaz, mensajes, registros, comentarios y documentación.

## Qué hace

Sigue el precio de productos de tiendas online. El usuario pega (o comparte desde el navegador, en Android) la dirección de un producto; la app descarga la página, saca el nombre, el precio, la moneda, la imagen y si está disponible, y lo vuelve a comprobar cada cierto tiempo. Guarda el historial y avisa con una notificación cuando el precio baja, sube, llega al precio deseado, marca un mínimo histórico o el producto vuelve a estar disponible.

No hay servidor propio: cada app descarga las páginas de las tiendas directamente.

## Recursos compartidos (`compartido/recursos`)

Estos archivos se incluyen tal cual en las dos apps:

- `tiendas.json`: reglas de extracción por tienda (ver más abajo).
- `manual.md`: manual de usuario único para las dos apps. Las diferencias se marcan con «En Windows» y «En Android».
- `novedades.md`: novedades de cada versión.

Windows los copia a `data/recursos/` al ejecutar desde código y al compilar. Android los añade como `assets` desde Gradle (`assets.srcDir("../../compartido/recursos")`).

Las pruebas de las dos apps usan `compartido/pruebas/` (vectores de importes y páginas HTML de ejemplo, ver «Pruebas comunes»).

## Modelo de datos (SQLite en las dos)

Mismos nombres de tablas y columnas en las dos apps. Fechas en texto ISO 8601 en UTC con `Z` (`2026-11-02T20:15:00Z`). Importes en `REAL` redondeados a 2 decimales al guardar. Booleanos en `INTEGER` 0 o 1. Cada fila exportable tiene un `uuid` (texto, UUID v4) para combinar datos entre dispositivos.

### categorias

| Columna | Tipo | Notas |
|---|---|---|
| id | INTEGER PK | |
| uuid | TEXT UNIQUE NOT NULL | |
| nombre | TEXT NOT NULL | Único sin distinguir mayúsculas |
| descripcion | TEXT | |
| orden | INTEGER | Para ordenar a mano; por defecto, alfabético |

Los productos sin categoría se muestran en «Sin categoría» (no es una fila de la tabla).

### tiendas

| Columna | Tipo | Notas |
|---|---|---|
| id | INTEGER PK | |
| uuid | TEXT UNIQUE NOT NULL | |
| nombre | TEXT NOT NULL | «Amazon», «PcComponentes»… |
| dominio | TEXT UNIQUE NOT NULL | Sin `www.` ni `m.`: `amazon.es` |
| selector_precio | TEXT | CSS propio del usuario; vacío = reglas de `tiendas.json` y genéricas |
| selector_titulo | TEXT | |
| selector_disponible | TEXT | |
| notas | TEXT | |

Una tienda se crea sola al añadir el primer producto de un dominio. Su nombre sale de `tiendas.json` si el dominio está allí; si no, de la etiqueta del dominio que va justo antes del sufijo público, con la primera letra en mayúscula: `tiendaejemplo.es` → «Tiendaejemplo»; `informatica.ejemplo.es` → «Ejemplo»; `tienda.ejemplo.co.uk` → «Ejemplo». Sufijos de dos niveles que se reconocen: `co.uk`, `org.uk`, `com.mx`, `com.ar`, `com.br`, `com.au`, `co.jp`, `com.es`, `nom.es`, `org.es`, `com.pt`, `com.tr`, `co.nz`, `co.za`.

### productos

| Columna | Tipo | Notas |
|---|---|---|
| id | INTEGER PK | |
| uuid | TEXT UNIQUE NOT NULL | |
| nombre | TEXT NOT NULL | El de la página si el usuario no pone otro |
| url | TEXT NOT NULL | Dirección limpia (ver «Direcciones») |
| tienda_id | INTEGER | FK tiendas |
| categoria_id | INTEGER NULL | FK categorias; NULL = sin categoría |
| grupo | TEXT | Nombre libre para comparar el mismo producto en varias tiendas |
| moneda | TEXT | `EUR` por defecto |
| precio_actual | REAL NULL | NULL si nunca se pudo leer |
| disponible | INTEGER | 1 disponible, 0 agotado |
| precio_inicial | REAL NULL | Primer precio leído |
| precio_minimo | REAL NULL | |
| fecha_minimo | TEXT | |
| precio_maximo | REAL NULL | |
| fecha_maximo | TEXT | |
| precio_anterior | REAL NULL | Precio antes del último cambio (para «bajó 10 €») |
| fecha_cambio | TEXT | Último cambio de precio |
| precio_objetivo | REAL NULL | Avisar cuando el precio sea igual o menor |
| alerta_porcentaje | REAL | 0 = cualquier bajada; si no, solo bajadas de al menos ese % |
| avisar_disponible | INTEGER | Avisar cuando vuelva a estar disponible (1 por defecto) |
| selector_precio | TEXT | CSS propio de este producto; gana a todo lo demás |
| imagen_url | TEXT | |
| notas | TEXT | |
| favorito | INTEGER | |
| activo | INTEGER | 0 = en pausa: no se comprueba |
| fecha_alta | TEXT | |
| ultima_comprobacion | TEXT | |
| ultimo_error | TEXT | Vacío si la última comprobación fue bien |
| errores_seguidos | INTEGER | |

### historial

| Columna | Tipo | Notas |
|---|---|---|
| id | INTEGER PK | |
| producto_id | INTEGER NOT NULL | FK productos, borrado en cascada |
| fecha | TEXT NOT NULL | |
| precio | REAL NULL | NULL si estaba agotado sin precio |
| disponible | INTEGER | |

Se añade una fila **solo cuando cambia** el precio o la disponibilidad (y siempre en la primera lectura). Así el historial es corto y cada fila es un cambio real. Índice único `(producto_id, fecha)`.

### avisos

| Columna | Tipo | Notas |
|---|---|---|
| id | INTEGER PK | |
| producto_id | INTEGER NULL | FK productos, `ON DELETE SET NULL` |
| fecha | TEXT | |
| tipo | TEXT | `objetivo`, `minimo`, `bajada`, `subida`, `disponible`, `agotado`, `error` |
| titulo | TEXT | Lo mismo que la notificación |
| mensaje | TEXT | |
| leido | INTEGER | |

Es la sección «Avisos»: el registro de todo lo notificado. Se pueden marcar como leídos y borrar.

### ajustes

Cada app guarda sus ajustes a su manera (Windows en `data/config`, Android en `SharedPreferences`), pero con **estas claves** para poder exportarlos:

| Clave | Tipo | Por defecto | Qué hace |
|---|---|---|---|
| intervalo_horas | entero | 6 | Cada cuánto se comprueban los precios: 1, 2, 3, 6, 12 o 24 |
| comprobar_al_iniciar | booleano | true | Comprobar al abrir la app si toca |
| avisar_bajadas | booleano | true | |
| avisar_subidas | booleano | true | El nombre de la app lo pide |
| avisar_objetivo | booleano | true | |
| avisar_minimo | booleano | true | Nuevo mínimo histórico |
| avisar_disponible | booleano | true | Vuelve a estar disponible |
| avisar_agotado | booleano | false | |
| avisar_errores | booleano | false | Tras 3 errores seguidos del mismo producto |
| cambio_minimo_porcentaje | real | 0 | Ignorar bajadas y subidas menores que este % (0 = todas) |
| pausa_entre_peticiones | entero | 3 | Segundos entre una página y la siguiente de la misma tienda |
| tiempo_espera | entero | 25 | Segundos máximos por página |
| conservar_avisos_dias | entero | 90 | 0 = siempre |
| buscar_actualizaciones | booleano | true | |

Ajustes incluye además un botón **«Enviar una notificación de prueba»** en las dos apps, para comprobar que las notificaciones llegan.

En la lista y en los detalles, el estado de la última comprobación se distingue siempre: correcta, sin precio, **bloqueada por la tienda** (nunca se confunde con agotado) o sin conexión.

Solo Windows: `iniciar_con_windows` (false), `minimizar_a_bandeja` (true), `sonidos` (true).
Solo Android: `solo_wifi` (false).

## Direcciones

Antes de guardar una URL:

1. Se quitan espacios y se añade `https://` si no tiene esquema.
2. Se quitan los parámetros de seguimiento: `utm_*`, `gclid`, `fbclid`, `ref`, `ref_`, `tag`, `psc`, `smid`, `spLa`, `th`, `_encoding`, `pd_rd_*`, `pf_rd_*`, `qid`, `sr`, `keywords`, `crid`, `sprefix`, `dib`, `dib_tag`, `linkCode`, `linkId`, `srsltid`.
3. Amazon: se reduce a `https://www.amazon.<tld>/dp/<ASIN>` (el ASIN sale de `/dp/`, `/gp/product/` o `/gp/aw/d/`).
4. Se quita el fragmento `#...`.
5. Dominio de la tienda: el host en minúsculas sin `www.` ni `m.`.

Si al añadir ya existe un producto con la misma URL limpia, se avisa y se ofrece abrirlo.

## Descarga de páginas

- Cabeceras de un navegador de escritorio: `User-Agent` de Chrome reciente para Windows, `Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8`, `Accept-Language: es-ES,es;q=0.9,en;q=0.5`. Compresión gzip. Redirecciones seguidas. Cookies de sesión en memoria (algunas tiendas las necesitan entre la primera y la segunda petición).
- Tiempo de espera: `tiempo_espera`. Un reintento tras 5 segundos si falla la red o responde 5xx. Nunca más de 2 intentos.
- Entre dos productos de la misma tienda, `pausa_entre_peticiones` segundos, más un pequeño valor al azar (0 a 2 s). Las tiendas distintas se pueden comprobar en paralelo, como mucho 3 a la vez.
- Respuesta 403, 429, 202 sin precio (desafío AWS WAF de Amazon) o página de verificación (textos de `bloqueo` de `tiendas.json`, o `captcha` en la página): error «La tienda ha pedido comprobar que no eres un robot. Se volverá a intentar en la próxima comprobación.»
- Mensajes de error siempre en español y entendibles: sin conexión, tiempo agotado, página no encontrada (404), la tienda bloquea, no se encontró el precio.

## Extracción del precio

Se hace sobre el HTML descargado, en este orden. **Se usa el primer resultado válido** (precio mayor que 0):

1. `selector_precio` del producto (CSS).
2. `selector_precio` de la tienda (CSS, el que escribe el usuario).
3. Reglas de `tiendas.json` para ese dominio (`precio`, en orden).
4. **JSON-LD**: todos los `<script type="application/ld+json">`. Se recorre el JSON **entero y de forma recursiva** (dentro de `@graph`, de listas y de cualquier clave: MediaMarkt, por ejemplo, mete el producto en `BuyAction.object`) buscando objetos con `@type` `Product` (o lista que lo contenga); se usa el primer Product que tenga precio. De sus `offers` (objeto o lista; `Offer` o `AggregateOffer`, que a su vez puede tener `offers`) se toma `price`, o `lowPrice` si no hay `price`, o `priceSpecification.price` (o el primero de la lista) si no hay ninguno de los dos; se descartan las ofertas de 0 € (servicios como «Retirada del antiguo»). Si hay varias ofertas válidas, la de menor precio. `priceCurrency` da la moneda y `availability` la disponibilidad. Un JSON-LD mal formado se ignora (se registra en depuración), no rompe la extracción.
5. **Metadatos**: `<meta property="product:price:amount">`, `<meta property="og:price:amount">`, `<meta itemprop="price">` (atributo `content`). Moneda en `product:price:currency` u `og:price:currency`.
6. **Microdatos**: el primer elemento con `itemprop="price"`: su `content` si lo tiene, si no su texto.

Cada regla CSS puede leer un atributo (`"atributo": "content"`) en vez del texto. Si un selector encuentra varios elementos, se usa el primero cuyo texto dé un importe válido.

**Nombre**: regla `titulo` de la tienda → `name` del JSON-LD Product → `og:title` → `<title>` (sin el sufijo « | Tienda» o « - Tienda» si coincide con el nombre de la tienda). Espacios normalizados.

**Imagen**: regla `imagen` → `image` del JSON-LD (texto, lista o objeto con `url`) → `og:image`.

**Moneda**: JSON-LD o metadatos; si no, por el símbolo del texto (€ EUR, $ USD, £ GBP); si no, `EUR`.

**Disponibilidad**: JSON-LD `availability` (termina en `InStock`, `LimitedAvailability`, `OnlineOnly`, `PreOrder`, `PreSale`, `InStoreOnly`: disponible; `OutOfStock`, `SoldOut`, `Discontinued`: agotado) → `product:availability` u `og:availability` (`instock`, `in stock`, `available for order`, `preorder`: disponible; `oos`, `out of stock`: agotado) → regla `disponible` de la tienda (si el texto contiene alguno de sus `agotado`, agotado) → disponible si hay precio.

### Extracción ampliada (versión 1.0.0, obligatoria)

Resultado de probar 166 tiendas españolas reales y un extractor genérico con fichas de tiendas pequeñas (informes en `adjuntos/`). Corrige y amplía lo anterior; **si algo choca, gana esta sección**.

**Correcciones a los pasos 4 a 6:**

1. `@type` se compara **sin distinguir mayúsculas** (PcComponentes usa `"product"`) y se aceptan `Product`, `ProductGroup`, `Book`, `IndividualProduct`, `ProductModel` y `Vehicle`. Las claves también sin distinguir mayúsculas (`"Price"` en Casa del Libro).
2. **ProductGroup y variantes** (`hasVariant`): primero se busca la variante que corresponde a la dirección: su `url` o `offers.url` igual a la de la página (sin parámetros de seguimiento), o su `sku`, `gtin*` o `productID` presente en la dirección (`?variant=` de Shopify incluido). Si no hay, se usan las `offers` del propio ProductGroup. Si tampoco tiene, y las variantes tienen precios distintos, el resultado es «varias variantes» (ver **Variantes**).
3. **Varias ofertas**: si tienen `url` distintas, son variantes (se aplica lo anterior); si no, se prefieren las que están **en stock** y, entre ellas, la de menor precio. Las de 0 € se descartan.
4. Se ignoran los Product que estén dentro de un `ItemList`, `itemListElement`, `isRelatedTo`, `isSimilarTo` o `offers` de otro (productos relacionados) y, si la dirección final tras las redirecciones es claramente una categoría (el JSON-LD es un `ItemList` o `CollectionPage`), se da el error «El producto ya no existe: la tienda redirige a una categoría.». Lo mismo, **aunque alguna regla haya dado precio**, si el `<title>` de la página empieza (sin distinguir mayúsculas ni tildes) por «Buscador», «Búsqueda», «Resultado», «Search», «Buscar», «Página no encontrada», «404» o «Not found» (expresión `^\s*(buscador|b[uú]squeda|resultados?\b|search\b|buscar\b|p[aá]gina no encontrada|404\b|not found\b)`): una ficha retirada de Zara lleva al buscador y la regla de la tienda daría el precio de otro artículo.
5. El **nombre** se toma del ProductGroup antes que de la variante (las variantes llevan talla o color) y, si viene de JSON-LD con entidades HTML (`&ntilde;`, `&oacute;`), se decodifican.
6. Metadatos: un `og:price:amount` o `product:price:amount` de 0 se ignora y se sigue buscando; **nunca** se lee `product:pretax_price:amount` (sin IVA). Un `meta itemprop=price` dentro de un tachado (`del`, `s`, `strike`, clase con `strike`, `old`, `was`, `before`, `antes`) se salta.
7. **Disponibilidad también por microdatos**: `[itemprop=availability]` con `href` o `content` (`InStock`… igual que en JSON-LD), comparando por el final del texto y sin distinguir mayúsculas.
8. **Precios partidos**: al leer un importe del **texto** de un elemento (reglas CSS, microdatos, heurística), se unen sus partes sin separador y se normaliza `(\d)\s*([.,])\s*(\d{2})(?!\d)` → `\1\2\3` antes de `analizar_importe` («74 , 99 €», «109€ 95» → 74,99 y 109,95). Al leer un **atributo**, no hace falta.
9. **`numero_de_maquina`** (`numeroDeMaquina` en Android) para campos de máquina de plataformas y estados incrustados, con la regla del apartado 8.1 de [EXTRACTOR_GENERICO.md](EXTRACTOR_GENERICO.md). Los campos en **céntimos** (Shopify `price`, VTEX `skuJson`) se dividen entre 100 solo donde ese documento lo dice. El `centAmount` de la API de Consum y BM ya viene en euros, pese a su nombre: no se divide.

**Pasos nuevos después del 6:** los pasos 7 a 12 de [EXTRACTOR_GENERICO.md](EXTRACTOR_GENERICO.md) (plataforma, estado incrustado, analítica, heurística visible con puntuación, decisión y pregunta al usuario), con sus firmas de plataforma, expresiones regulares, pesos y umbrales **exactos**: `UMBRAL = 8`, `MARGEN = 3`, `UMBRAL_UNICO = 5`. El prototipo de referencia en Python está en `compartido/referencia_extractor/` (Windows puede partir de él; Android lo traduce). Los vectores sintéticos de `referencia_extractor/pruebas_sinteticas.py` se pasan a `compartido/pruebas/extractor_generico.json` (HTML pequeño + resultado esperado) y los pasan las dos apps.

**Bloqueo**: la palabra suelta «captcha» **no** cuenta (aparece en páginas normales con reCAPTCHA); solo los textos de `bloqueo_general` y de la tienda, y solo cuando no hay precio ni disponibilidad. Las comparaciones de textos de bloqueo son sin distinguir mayúsculas. También es bloqueo una respuesta 400 si la tienda tiene ese texto en `bloqueo` (Douglas: «Request Too Long»).

**Resultado con origen y confianza.** Cada extracción devuelve el `origen` («selector del producto», «regla de la tienda», «API de la tienda», «JSON-LD», «metadatos», «microdatos», «plataforma <nombre>», «análisis de la página», «elegido por ti») y la `confianza` (`alta` en los pasos 1 a 7 y en la API; `media` en una decisión de la heurística; `baja` si se aceptó por datos ocultos). Se guardan en el producto (`origen_precio`, `confianza`) y se muestran en los detalles. Con confianza media o baja, un cambio de más del 50 % respecto al precio anterior **se vuelve a comprobar** una vez antes de guardarlo y avisar.

#### Variantes

Si el resultado es «varias variantes» y el producto no tiene `variante` elegida, se guarda el precio menor con la marca «desde» (en la lista: «desde 51,95 €») y en los detalles y al añadirlo se ofrece **«Elegir variante»**: una lista con el nombre de cada variante (tamaño, color) y su precio. La elegida se guarda en la columna nueva `variante` del producto (su `sku`, o su nombre si no tiene) y en las comprobaciones siguientes se usa esa variante.

#### Elegir el precio (selección asistida, accesible)

Si ningún paso da un precio seguro, en vez de un error se guardan los **candidatos** (como mucho 10, ordenados por puntuación) y:

- Al añadir: «No he encontrado el precio con seguridad. Elige el correcto:» y una lista de una línea por candidato con su contexto, como dice el apartado 7.1 de [EXTRACTOR_GENERICO.md](EXTRACTOR_GENERICO.md) («39,99 €, junto al botón de compra», «47,05 €, tachado», «4,99 €, gastos de envío»), más «Ninguno es el precio».
- Al elegir: se genera un selector CSS estable (apartado 7.2), se valida (7.3: un único elemento y el mismo importe) y se guarda en `selector_precio` del producto, junto con su `huella_selector`: el texto JSON `{"importe": 39.99, "contexto": "junto al botón de compra", "atributo": "content"}` (`atributo` vacío si el importe se lee del texto del elemento; al leer se acepta `texto` como sinónimo de `contexto`). Al comprobar, el selector del producto lee el `atributo` de su huella. Opción «Usar también para todos los productos de esta tienda» → se guarda en la tienda.
- En una comprobación en segundo plano sin precio seguro: error «No se pudo decidir cuál es el precio. Abre el producto y elige el precio correcto.» (aviso de tipo `error` si `avisar_errores`).
- Si un selector elegido deja de encontrar el elemento: error «La posición del precio en la página ha cambiado. Vuelve a elegir el precio en Editar.», nunca un precio dudoso.
- En detalles y en Editar hay siempre **«Elegir el precio en la página»**, que descarga la página y muestra la lista aunque la extracción automática funcione.

#### API de la tienda

Si la tienda tiene `api` en `tiendas.json`, se usa **antes** que el HTML (paso 2 bis, tras el selector de la tienda del usuario):

```json
"api": {
  "id_desde_url": "/product/(\\d+)",
  "url": "https://tienda.mercadona.es/api/products/{id}/",
  "precio": ["price_instructions.unit_price"],
  "nombre": ["display_name"],
  "imagen": ["photos.0.regular"],
  "disponible": {"ruta": "published", "igual": true}
}
```

- `id_desde_url`: expresión regular sobre la dirección; el grupo 1 sustituye `{id}` en `url`. Si no casa, se sigue con el HTML.
- Rutas: claves separadas por puntos; un número es una posición de lista; `[clave=valor]` elige el primer elemento de una lista con ese valor. Cada lista de rutas se prueba en orden.
- Los importes de la API se leen con `importe_de_maquina` si son texto.
- La petición lleva `Accept: application/json` y las mismas cabeceras y cookies.

#### Navegador integrado

Muchas tiendas grandes (Inditex, Amazon a veces, Notino, Sephora, Carrefour, Worten, Decathlon, El Corte Inglés…) no dan la página a una descarga normal, y otras montan el precio con JavaScript (AliExpress, Temu, Xiaomi, Uniqlo). Para ellas, las dos apps tienen un **navegador integrado** que carga la página con el motor web del sistema, como lo haría el usuario, y extrae del HTML ya cargado:

- Windows: `wx.html2.WebView` con el motor Edge (WebView2) en una ventana oculta; Android: un `WebView` sin mostrar, creado en el hilo principal.
- Carga la dirección, espera al final de la carga y después hasta 8 segundos más mientras no haya precio (comprobando cada segundo con `document.documentElement.outerHTML`), y pasa ese HTML por la extracción normal. Tiempo máximo total: 30 segundos. Uno a la vez.
- Mismo User-Agent del motor (no se cambia) y sus propias cookies, que se conservan entre comprobaciones (así, si la tienda pidió una verificación y se superó una vez, las siguientes suelen pasar).
- **Nada para engañar a la tienda**: ni cambiar huellas, ni ocultar que es un navegador automatizado, ni resolver verificaciones automáticamente.
- Columna nueva de la tienda `modo_descarga`: `auto` (por defecto), `directo` o `navegador`. En `auto`: si `tiendas.json` marca la tienda con `"navegador": true`, va directamente con el navegador; si no, descarga normal y, si da bloqueo o no hay precio y la página parece montada con JavaScript (muy poco texto visible, o `__NEXT_DATA__`/`app-root`/`id="root"` vacío), se repite con el navegador.
- **«Abrir la tienda en la app»** (en Gestionar tiendas y en los detalles de un producto bloqueado): muestra la página en el navegador integrado, visible, para que el usuario resuelva una verificación o acepte cookies; se cierra con Escape (Windows) o Atrás (Android) y las cookies se quedan.
- Si el motor no está disponible (Windows sin WebView2), se dice en el error y se ofrece la página de descarga del runtime WebView2 de Microsoft.

#### Columnas nuevas (migración 2 de la base de datos)

- `productos`: `variante` TEXT, `origen_precio` TEXT, `confianza` TEXT, `huella_selector` TEXT, `desde` INTEGER (1 si el precio guardado es un «desde»).
- `tiendas`: `modo_descarga` TEXT (`auto` por defecto).
- Se exportan e importan con esos mismos nombres (ver [FORMATO_INTERCAMBIO.md](FORMATO_INTERCAMBIO.md)); al leer un archivo sin ellos, toman su valor por defecto.

### Formato de `tiendas.json`

- `bloqueo_general`: textos que, si aparecen en el HTML, indican una página de verificación de cualquier tienda.
- `tiendas[]`: `id`, `nombre`, `dominios` (el dominio del producto coincide si es igual o termina en `.` + dominio), `precio`, `titulo`, `imagen` (listas de reglas `{ "css": ..., "atributo": ... }`), `disponible` (lista de `{ "css": ..., "agotado": [textos] }`: si el elemento existe y su texto, en minúsculas, contiene alguno de esos textos, está agotado; el texto vacío `""` significa «si existe, agotado»; si existe y no contiene ninguno, disponible), `bloqueo` (textos propios de verificación) y `notas`.
- La comprobación de bloqueo solo se hace **cuando no se ha encontrado ni precio ni disponibilidad** (así un texto como «Access Denied» en una página normal no da un falso bloqueo), o cuando la respuesta es 403 o 429.
- El usuario no edita este archivo: sus selectores van en la tienda (tabla `tiendas`) o en el producto, que ganan a estas reglas.

Si no hay precio pero la página dice agotado, la comprobación es válida: se guarda agotado y se conserva el último precio conocido. Si no hay precio ni se sabe nada: error «No se encontró el precio en la página. Puede que la tienda haya cambiado su diseño: prueba con un selector propio en Editar.»

### Importes de texto

Una sola función, `analizar_importe(texto)` en Windows y `analizarImporte(texto)` en Android, con los mismos resultados (vectores en `compartido/pruebas/importes.json`):

1. Se toma la primera coincidencia de la expresión regular `\d+(?:[.,'’]\d+|[   ]\d{3}(?!\d))*`: dígitos separados por `.`, `,` o apóstrofo, o por un espacio (normal, duro U+00A0 o fino U+202F) seguido de exactamente 3 dígitos. Así un punto final de frase no cuenta («129,99.» → 129,99).
2. Se quitan los espacios y apóstrofos (separadores de miles).
3. Con `.` y `,` a la vez: el que aparece **el último** es el decimal; el otro, de miles.
4. Con un solo tipo de separador:
   - Si aparece más de una vez, es de miles (`1.299.000` → 1299000).
   - Si aparece una vez y le siguen exactamente 3 dígitos, es de miles (`1.299` → 1299; `1,299` → 1299).
   - Si no, es decimal (`12,5` → 12.5; `129.99` → 129.99).
5. Sin dígitos o resultado ≤ 0 → sin importe.
6. Se redondea a 2 decimales.

Los valores que vienen de JSON-LD como **número** JSON se usan tal cual. Si vienen como **texto**, se leen en formato de máquina (punto decimal) cuando son exactamente `^\d+(\.\d{1,2})?$` (`"1299.99"`, `"12.5"`, `"1299"`); cualquier otro texto pasa por `analizar_importe` (`"1.299"` → 1299; `"1.299,00"` → 1299). Los atributos `content` de metadatos y los que pida una regla con `atributo` siguen la misma regla. Esta lectura es `importe_de_maquina(texto)` en Windows e `importeDeMaquina(texto)` en Android.

## Comprobación y avisos

Para cada producto activo, en cada comprobación:

1. Se descarga y se extrae. Si falla: `ultimo_error` = mensaje, `errores_seguidos` + 1, `ultima_comprobacion` = ahora. Si `avisar_errores` y `errores_seguidos` llega a 3, aviso de tipo `error`. No se toca nada más.
2. Si va bien: `ultimo_error` vacío, `errores_seguidos` = 0, `ultima_comprobacion` = ahora. Si el nombre del producto estaba vacío, se rellena; la imagen se actualiza si había cambiado.
3. Sea `P0` el `precio_actual` anterior y `P1` el nuevo (redondeados a céntimos), `D0` y `D1` la disponibilidad.
4. **Primera lectura** (`P0` nulo): `precio_inicial`, `precio_minimo`, `precio_maximo` = `P1` con su fecha; fila de historial. Si hay objetivo y `P1` ≤ objetivo, aviso `objetivo`.
5. **Cambio de precio** (`P1` ≠ `P0`): `precio_anterior` = `P0`, `fecha_cambio` = ahora, fila de historial, mínimo y máximo al día. El cambio en % es `(P1 - P0) / P0 × 100`. Si su valor absoluto es menor que `cambio_minimo_porcentaje`, se guarda pero no se avisa. Si no, **un solo aviso** por producto y comprobación, el primero que se cumpla:
   1. `objetivo`: hay objetivo, `P1` ≤ objetivo y `P0` > objetivo (y `avisar_objetivo`).
   2. `minimo`: `P1` < mínimo anterior (y `avisar_minimo`).
   3. `bajada`: `P1` < `P0`, `avisar_bajadas` y (`alerta_porcentaje` = 0 o la bajada ≥ `alerta_porcentaje`).
   4. `subida`: `P1` > `P0` y `avisar_subidas`.
6. **Cambio de disponibilidad** sin cambio de precio: fila de historial; `disponible` si pasa de 0 a 1 (con `avisar_disponible` global y del producto), `agotado` si pasa de 1 a 0 (con `avisar_agotado`). Si también cambió el precio, el aviso de disponibilidad va en el mismo mensaje.
7. Cada aviso se guarda en `avisos` y se muestra como notificación del sistema. Si en una comprobación hay más de 3 avisos, además de los individuales hay un resumen («5 productos han cambiado de precio»). En Android, las notificaciones de una comprobación van en un grupo.

### Textos de los avisos

Títulos y mensajes iguales en las dos apps (importes con formato español `1.299,99 €`):

- `objetivo`: «¡Precio deseado alcanzado!» / «<nombre>: <P1> en <tienda> (querías <objetivo> o menos).»
- `minimo`: «Mínimo histórico» / «<nombre>: <P1> en <tienda>, el precio más bajo visto (antes <P0>).»
- `bajada`: «Ha bajado de precio» / «<nombre>: de <P0> a <P1> en <tienda> (−<diferencia>, −<porcentaje> %).»
- `subida`: «¡Te han subido el precio!» / «<nombre>: de <P0> a <P1> en <tienda> (+<diferencia>, +<porcentaje> %).»
- `disponible`: «Vuelve a estar disponible» / «<nombre> vuelve a estar disponible en <tienda> a <P1>.»
- `agotado`: «Agotado» / «<nombre> se ha agotado en <tienda>.»
- `error`: «No se puede leer el precio» / «<nombre> (<tienda>): <ultimo_error>»

Porcentajes con una decimal y coma (`7,5 %`); sin decimal si es entero (`10 %`).

## Funciones de las dos apps

Las dos tienen **las mismas secciones** (en Android, en el menú lateral; en Windows, en la lista «Secciones» de la izquierda y en el menú Ver), en este orden:

1. **Todos los productos.**
2. **Categorías**: lista de categorías con su número de productos (y «Sin categoría»); al entrar, sus productos.
3. **Tiendas**: lista de tiendas con su número de productos; al entrar, sus productos.
4. **Ofertas**: productos con precio por debajo del anterior en los últimos 7 días, en su mínimo histórico o en el precio deseado o por debajo. Ordenados por porcentaje de bajada.
5. **Favoritos.**
6. **Comparar**: los grupos (productos con el mismo `grupo`); al entrar, sus productos de más barato a más caro, con la diferencia con el más barato.
7. **Avisos**: el historial de avisos, del más nuevo al más viejo, con los no leídos primero.

Acciones generales (en Android, tras el divisor del menú lateral; en Windows, en los menús): **Añadir producto**, **Comprobar todos ahora**, **Gestionar categorías**, **Gestionar tiendas**, **Importar y exportar**, **Ajustes**, **Manual**, **Buscar actualizaciones**, **Acerca de**.

### Lista de productos

- Cada fila se lee de una vez, con el estado primero: «[En pausa | Agotado | Error | En oferta,] <nombre>, <precio>, <cambio>, <tienda>, <categoría>». Cambio: «bajó 10,00 € (7 %)», «subió 5,00 € (3 %)» o «sin cambios». Si el precio está en el objetivo o por debajo: «precio deseado alcanzado».
- Orden elegible: nombre, precio, mayor bajada, último cambio, fecha de alta, tienda. Se recuerda.
- Búsqueda por texto (nombre, tienda, categoría, notas, grupo).
- Filtros rápidos: solo activos, solo con error, solo agotados.

### Acciones sobre un producto

Abrir en el navegador, Ver detalles, Comprobar ahora, Editar, Mover a categoría, Marcar o quitar de favoritos (según el estado), Pausar o reanudar (según el estado), Copiar o compartir enlace, Eliminar (con confirmación en Windows y con «Deshacer» en Android).

### Detalles del producto

Nombre, precio actual y disponibilidad, tienda, categoría, grupo, precio deseado, alerta de %, precio inicial, mínimo y máximo con fechas, media del historial, diferencia con el mínimo, última comprobación y último error. Un **resumen hablado** de una línea: «Ahora 129,99 €. Mínimo 119,00 € el 3 de octubre. Máximo 149,00 €. Está un 9,2 % por encima del mínimo.» El **historial** como lista (fecha, precio, cambio con el anterior) y una **gráfica** de línea del precio en el tiempo (decorativa para el lector: lo importante ya está en el resumen y la lista).

### Añadir y editar

Campos: dirección (obligatoria; en Windows se rellena con el portapapeles si contiene una dirección; en Android llega con «Compartir» desde el navegador), nombre (opcional: si se deja vacío se usa el de la página), categoría (lista con «Sin categoría» y «Nueva categoría…»), grupo para comparar, precio deseado, alerta por % de bajada, avisar si vuelve a estar disponible, selector CSS propio (avanzado), notas.

Al añadir, **se comprueba en el momento** con espera cancelable y se muestra lo encontrado: «Encontrado: <nombre>, <precio>, <disponible>. ¿Guardar?». Si no se encuentra el precio, se ofrece guardarlo igualmente (se volverá a intentar) o editar el selector.

### Gestionar categorías y tiendas

- Categorías: añadir, renombrar, borrar (los productos pasan a «Sin categoría», tras confirmar), subir y bajar en el orden.
- Tiendas: ver, renombrar, editar selectores propios y notas, **probar** los selectores con un producto de la tienda (muestra lo que saca), borrar si no tiene productos.

## Importar y exportar

### Formato de intercambio

Un único archivo JSON en UTF-8 que las dos apps leen y escriben. Nombre propuesto: `NoMeSubasLosPrecios-AAAA-MM-DD.json`. Detalle y ejemplo: [FORMATO_INTERCAMBIO.md](FORMATO_INTERCAMBIO.md).

### Opciones

- **Exportar todo** (con historial y avisos, opcionalmente con ajustes).
- **Importar** con dos modos:
  - **Combinar** (por defecto): se busca cada elemento por `uuid`; si no está, el producto se busca por URL limpia, la tienda por dominio y la categoría por nombre. Si existe, se actualiza con el dato más reciente (`ultima_comprobacion` mayor gana para los precios; lo que puso el usuario, como nombre, categoría, objetivo o notas, se toma del archivo). El historial se une sin duplicar (por fecha). Lo que no existe se crea.
  - **Reemplazar todo**: tras confirmar, se borra todo y se carga el archivo. Antes se hace una copia de seguridad automática.
- Antes de importar se muestra un resumen: «El archivo tiene 42 productos, 6 categorías y 9 tiendas. Se añadirán 10 productos y se actualizarán 32.»
- **Exportar a CSV** (solo productos, para hojas de cálculo; separador `;`, decimales con coma, UTF-8 con BOM para Excel). No se importa.
- **Copias de seguridad**: Windows hace una copia diaria de la base de datos en `data/backups` (se guardan las 7 últimas). Android usa la copia de seguridad automática de Android para la base de datos y los ajustes.

En Android, importar y exportar usan el selector de archivos del sistema (`ACTION_CREATE_DOCUMENT` y `ACTION_OPEN_DOCUMENT`), así que se puede guardar en Drive, en la carpeta Descargas o en un USB, y pasarlo al PC. En Windows, el diálogo de archivos normal.

## Notificaciones y segundo plano

### Windows

- La app puede quedarse en la **bandeja del sistema** al cerrar la ventana (`minimizar_a_bandeja`) y sigue comprobando cada `intervalo_horas`. Menú de la bandeja: Mostrar, Comprobar ahora, Salir.
- Notificaciones con `wx.adv.NotificationMessage` asociado al icono de la bandeja (salen como notificaciones de Windows). Al pulsarla se abre el producto.
- **Iniciar con Windows** (desactivado por defecto): acceso directo en la carpeta Inicio del usuario que abre la app minimizada en la bandeja (`--bandeja`). Al desactivarlo se borra.
- Sonidos opcionales al terminar una comprobación con cambios.
- Al arrancar, si `comprobar_al_iniciar` y la última comprobación es más vieja que el intervalo, comprueba en segundo plano.

### Android

- **WorkManager** periódico cada `intervalo_horas`, con red conectada (o sin medir si `solo_wifi`) y batería no baja. Se reprograma al cambiar el ajuste (`ExistingPeriodicWorkPolicy.UPDATE`).
- **Canales**: «Bajadas y ofertas» (alta importancia), «Subidas de precio», «Disponibilidad», «Problemas» (baja), «Comprobación en curso» (baja, notificación de progreso de la comprobación manual).
- Permiso `POST_NOTIFICATIONS` pedido en contexto (al añadir el primer producto o desde Ajustes), explicando para qué. Si se deniega, la app funciona y Avisos sigue registrando todo.
- Ajustes ofrece abrir la pantalla de optimización de batería del sistema para la app, explicando que algunos fabricantes retrasan las comprobaciones.
- Pulsar la notificación abre los detalles del producto. Acción en la notificación: «Abrir en la tienda».
- Recibe enlaces compartidos (`ACTION_SEND` de tipo `text/plain`): abre Añadir producto con la dirección (se extrae la primera URL del texto compartido).

## Actualizaciones

Las dos buscan versión nueva en `https://xebolax.synology.me/NoMeSubasLosPrecios/` al arrancar (como mucho una vez al día, si `buscar_actualizaciones`) y desde el menú:

- Android: `version.json` y `NoMeSubasLosPrecios_v<versión>.apk`, con SHA-256 y comprobación de que el APK está firmado con la misma clave, como YouTubeRO.
- Windows: `windows/version.json` firmado (Ed25519) y `windows/NoMeSubasLosPrecios-<versión>-win64.zip`, con el actualizador que sustituye el programa sin tocar `data/`.

Si no hay conexión o el servidor no responde, se registra y no se molesta al usuario (salvo en la comprobación manual, que dice el motivo).

## Accesibilidad (las dos)

- Windows: lo que piden los agentes `accesibilidad-wx` y `proyecto-nuevo` (etiquetas antes de cada control, `&` en todo, botones en español, Escape cierra diálogos, Ctrl+H, listas que leen bien con NVDA y JAWS, interfaz nunca bloqueada, foco que vuelve).
- Android: lo que pide el agente `android-accesible` (menú lateral de `MenuLateral.kt`, filas de una sola parada, acciones de TalkBack, `MemoriaFoco`, `conEspera`, 48 dp, fuente al 200 %, borde a borde, DayNight).
- Los importes se escriben para que el lector los lea bien: `129,99 €`, nunca `€129.99`.

## Pruebas comunes (`compartido/pruebas`)

- `importes.json`: lista de `{ "texto": ..., "valor": ... }` (`valor` nulo si no hay importe). Las dos suites de pruebas deben dar exactamente esos valores.
- `paginas/*.html` y `paginas.json`: páginas de ejemplo con lo que se debe extraer (`precio`, `moneda`, `nombre`, `disponible`, `dominio`). Las dos apps las pasan con las reglas de `recursos/tiendas.json`.
- `exportacion-ejemplo.json`: un archivo de intercambio válido que las dos apps deben poder importar, y cuya exportación tras importarlo debe contener los mismos productos, categorías, tiendas e historial.
