# No Me Subas Los Precios

[![Última versión](https://img.shields.io/github/v/release/hxebolax/NoMeSubasLosPrecios?label=versi%C3%B3n)](https://github.com/hxebolax/NoMeSubasLosPrecios/releases/latest)
[![Licencia: GPL v3](https://img.shields.io/badge/licencia-GPL%20v3-blue.svg)](LICENSE)
![Windows 10 y 11](https://img.shields.io/badge/Windows-10%20%7C%2011-0078D6)
![Android 7.0 o posterior](https://img.shields.io/badge/Android-7.0%2B-3DDC84)

Sigue el precio de los productos que te interesan en las tiendas online y te avisa cuando **baja**, cuando **llega al precio que quieres**, cuando marca **su mínimo histórico**, cuando **vuelve a estar disponible** o cuando **te lo suben**.

Son dos aplicaciones gemelas, con las mismas funciones y el mismo archivo de datos, **pensadas desde el principio para usarse con lector de pantalla**: una para **Windows** (NVDA, JAWS, Narrador) y otra para **Android** (TalkBack). También son cómodas para quien ve la pantalla: colores configurables en la lista, gráfica del precio y una interfaz limpia.

Creadas por **Héctor J. Benítez Corredera**. Todo en español de España.

- [Para usuarios](#para-usuarios)
- [Para programadores](#para-programadores)
- [Licencia](#licencia)

---

## Para usuarios

### Qué hace

- **Pegas o compartes la dirección de un producto** y la app saca su nombre, precio, imagen y disponibilidad.
- **Lo vuelve a comprobar sola** cada 1, 2, 3, 6, 12 o 24 horas y guarda el historial de precios.
- **Te avisa con una notificación** cuando:

  | Aviso | Cuándo |
  |---|---|
  | ¡Precio deseado alcanzado! | Llega a tu precio deseado o lo baja |
  | Mínimo histórico | Es el precio más bajo que ha visto |
  | Ha bajado de precio | Cualquier bajada, o solo las del porcentaje que elijas |
  | ¡Te han subido el precio! | Sube de precio |
  | Vuelve a estar disponible | Estaba agotado y ya no |

- **Secciones** para encontrarlo todo: todos los productos, categorías, tiendas, ofertas, favoritos, comparar el mismo producto en varias tiendas y el historial de avisos.
- **Detalles de cada producto**: precio inicial, mínimo y máximo con sus fechas, media, historial y un resumen pensado para oírlo de una vez («Ahora 129,99 €. Mínimo 119,00 € el 3 de octubre...»).
- **Colores en la lista** (para quien ve la pantalla): verde lo que baja, rojo lo que sube, azul lo que llega a tu precio y gris lo agotado. Cada color se puede cambiar, y se pueden quitar.
- **Pasa tus productos entre Windows y Android** con un solo archivo (exportar e importar), y exporta a CSV para hojas de cálculo.
- **Se actualiza sola** desde el servidor del autor, desde GitHub, desde los dos o desde una dirección tuya, y solo instala versiones firmadas por el autor.

### Tiendas

Trae reglas comprobadas para **más de 170 tiendas**: supermercados (Mercadona, Alcampo, Eroski, Consum...), perfumerías y farmacias (Primor, Druni, PromoFarma...), animales (Tiendanimal, Kiwoko, zooplus...), moda, deporte, hogar, electrónica (Amazon, PcComponentes, MediaMarkt, Coolmod...), libros, juguetes y **videojuegos** (Steam, GOG, Epic Games Store, PlayStation Store, Microsoft Store, Nintendo eShop, Humble Bundle, Fanatical, Green Man Gaming, GAME, xtralife, Instant Gaming, G2A, Eneba, Kinguin y GAMIVO).

**Con cualquier otra tienda también funciona**: reconoce las plataformas de tienda más usadas (Shopify, WooCommerce, PrestaShop, Magento y otras) y los datos que las tiendas publican para los buscadores. Si no está segura de cuál es el precio, **te pregunta** con una lista de los importes de la página y recuerda tu elección.

Las tiendas que no dejan leer sus páginas a un programa, o que las montan con JavaScript, se leen con un **navegador integrado** (el motor web del sistema), como si las abrieras tú. La app no hace nada para engañar a las tiendas.

### Descargar e instalar

Descarga la última versión en la [página de versiones](https://github.com/hxebolax/NoMeSubasLosPrecios/releases/latest).

#### Windows

- **Requisitos**: Windows 10 u 11 de 64 bits. Para las tiendas que se leen con el navegador integrado usa WebView2 (el motor de Edge), que ya viene con Windows 11 y con Windows 10 actualizado.
- **Instalar**: descarga `NoMeSubasLosPrecios-<versión>-win64.zip`, descomprímelo donde quieras (Documentos, un USB...) y abre `NoMeSubasLosPrecios.exe`.
- **Es portable**: no se instala ni escribe fuera de su carpeta. Todo lo tuyo va en la subcarpeta `data`; para llevarla a otro equipo, copia la carpeta entera.
- Puede quedarse en la **bandeja del sistema** comprobando precios e **iniciarse con Windows** (las dos cosas se eligen en Preferencias).

#### Android

- **Requisitos**: Android 7.0 o posterior.
- **Instalar**: descarga `NoMeSubasLosPrecios_v<versión>.apk` en el móvil, ábrelo y, si Android lo pide, permite instalar aplicaciones de esa fuente.
- Para añadir un producto, **compártelo desde el navegador** o la app de la tienda y elige No Me Subas Los Precios.
- Comprueba los precios en segundo plano. Si tu móvil retrasa las comprobaciones para ahorrar batería, en Ajustes tienes un botón para quitar la optimización de batería.

> Los archivos `version.json` y `version-windows.json` de cada versión son para las actualizaciones automáticas: no hace falta descargarlos.

### Accesibilidad

- **Windows**: controles nativos con su etiqueta, letras de acceso en todo, **Ctrl+H** lee la ayuda del control con el foco, **F1** abre el manual y **Ctrl+F1** la lista de teclas. Las listas se recorren por columnas con las flechas izquierda y derecha, y lo que se lee (número de fila, nombre de la columna, contenido) es configurable. Nunca se bloquea la interfaz: las comprobaciones van en segundo plano con espera cancelable. Respeta el contraste alto de Windows.
- **Android**: filas de una sola parada con acciones de TalkBack, foco que vuelve donde estaba al cerrar un diálogo, elementos de 48 dp, texto al 200 %, tema claro y oscuro.
- **Las dos**: los importes se escriben para que se lean bien (`129,99 €`) y cada fila empieza por su estado («En oferta», «Agotado», «Bloqueado por la tienda»...). Los colores son solo una ayuda visual: no se pierde nada sin verlos.

### Tus datos

- Todo se guarda **en tu dispositivo**: en Windows, en la carpeta `data` (con una copia de seguridad diaria de la base de datos); en Android, en el almacenamiento de la app, incluido en la copia de seguridad de Android.
- **No hay servidor propio**: la app solo se conecta a las tiendas de tus productos y al origen de actualizaciones que elijas. No envía tus productos a ningún sitio.

### Ayuda

- [Manual de usuario](compartido/recursos/manual.md) (el mismo para las dos; dentro de la app, con F1 en Windows o en el menú lateral, Manual, en Android).
- [Novedades de cada versión](compartido/recursos/novedades.md).
- ¿Un fallo o una idea? Abre una [incidencia](https://github.com/hxebolax/NoMeSubasLosPrecios/issues). Si es de una tienda, pon la dirección del producto y qué precio ves en la página.

---

## Para programadores

### Cómo está hecho

| | Windows | Android |
|---|---|---|
| Lenguaje | Python 3.13 | Kotlin |
| Interfaz | wxPython 4.2 (controles nativos) | Views con Material Components 3 |
| Descarga | requests + navegador integrado WebView2 (`wx.html2`) | OkHttp + `WebView` |
| Análisis | BeautifulSoup | Jsoup |
| Datos | SQLite | SQLite |
| Segundo plano | Hilos y bandeja del sistema | WorkManager |
| Compilación | cx_Freeze (ZIP portable) | Gradle 8.11 (APK firmado), SDK 35, mínimo 24 |
| Actualizaciones | `version.json` firmado con Ed25519 + ZIP | `version.json` + APK (SHA-256 y misma firma) |

**La regla principal: las dos apps hacen lo mismo.** El contrato común está en [`compartido/`](compartido):

- [`ESPECIFICACION.md`](compartido/ESPECIFICACION.md): base de datos, extracción del precio, avisos, secciones, ajustes, colores, notificaciones y actualizaciones.
- [`EXTRACTOR_GENERICO.md`](compartido/EXTRACTOR_GENERICO.md): cómo se encuentra el precio en tiendas sin reglas propias (plataformas, datos incrustados, puntuación de candidatos y elección por el usuario).
- [`FORMATO_INTERCAMBIO.md`](compartido/FORMATO_INTERCAMBIO.md): el archivo JSON para pasar los datos entre las dos apps.
- `recursos/`: `tiendas.json` (reglas por tienda), `manual.md` y `novedades.md`. Android los empaqueta como assets y Windows los copia a `windows/data/recursos`. No se duplican.
- `pruebas/`: importes, direcciones, páginas de ejemplo, vectores del extractor y un archivo de exportación que **las dos apps deben pasar con los mismos resultados**.
- `referencia_extractor/`: el prototipo en Python del extractor genérico.

Cualquier cambio de funciones se hace en las dos apps y se anota en la especificación.

### Estructura del repositorio

```
compilar.bat            Menú y órdenes para compilar, probar y publicar las dos apps
compartido/             Contrato común, recursos y pruebas compartidas
windows/                App de Windows
  main.py               Arranque
  app/core/             Rutas, configuración, base de datos, registro, versión
  app/services/         Lógica sin wx: extracción, comprobación, avisos, colores, actualizador...
  app/ui/               Ventanas y diálogos (app/ui/accesibilidad: controles accesibles)
  tests/                Pruebas (pytest)
  tools/                Empaquetado, firma de version.json, auditoría, vectores del extractor
  entorno.bat           Menú propio de Windows (entorno virtual, pruebas, compilar, auditoría...)
android/                App de Android (Gradle)
  app/src/main/java/com/xebolax/nomesubaslosprecios/
    nucleo/             Lógica pura (extracción, avisos, colores...): se prueba en la JVM
    datos/ motor/ ui/   Base de datos, comprobación en segundo plano, pantallas
    accesibilidad/      Ayudas para TalkBack
    actualizaciones/    Actualizador
herramientas/           Preparar el entorno portátil y publicar (servidor y GitHub)
```

### Requisitos

- **Windows 10 u 11 de 64 bits** (para compilar las dos apps; la de Android también se compila desde aquí).
- **Unos 1,5 GB libres** para el entorno portátil.
- Opcional: **[GitHub CLI](https://cli.github.com/)** (`gh`) con la sesión iniciada, solo para publicar versiones en GitHub.

No hace falta instalar nada más: todo lo necesario vive en la carpeta `entorno` del proyecto.

### Preparar el entorno

```
git clone https://github.com/hxebolax/NoMeSubasLosPrecios.git
cd NoMeSubasLosPrecios
compilar.bat entorno
```

[`herramientas/preparar_entorno.ps1`](herramientas/preparar_entorno.ps1) deja en `entorno/`, sin tocar el sistema: **JDK 17**, **Android SDK** (plataforma 35, build-tools 35.0.0 y adb), **Gradle 8.11.1** y su caché, **Python 3.13** portátil y, si lo pides, el emulador `pruebas` (Android 15). Al instalar el SDK se aceptan las licencias del Android SDK de Google. Si ya tienes una carpeta `entorno` de otro proyecto, puedes copiarla en vez de descargarlo todo (te lo pregunta).

El entorno virtual de Windows (`windows/.venv`) se crea solo la primera vez que compilas o ejecutas; también con `windows\entorno.bat crear`.

### Compilar, ejecutar y probar

`compilar.bat` sin nada abre un menú. Con una orden:

| Orden | Qué hace |
|---|---|
| `compilar.bat todo` | Compila las dos |
| `compilar.bat windows` | ZIP portable en `windows\dist` |
| `compilar.bat android` | APK firmado: `NoMeSubasLosPrecios.apk` en la raíz |
| `compilar.bat ejecutar` | Ejecuta la de Windows desde el código |
| `compilar.bat pruebas` | Pasa las pruebas de las dos apps |
| `compilar.bat emulador` | Abre el emulador de Android |
| `compilar.bat instalar` | Instala en el móvil conectado el APK ya compilado |
| `compilar.bat android-instalar` | Compila Android e instala en el móvil conectado |
| `compilar.bat dispositivos` | Lista los móviles conectados |
| `compilar.bat publicar` | Deja en `dist` el APK, el ZIP y sus `version.json` firmados |
| `compilar.bat servidor` | `publicar` y copia a la carpeta del servidor de actualizaciones |
| `compilar.bat github` | `publicar` y crea la release `v<versión>` en GitHub |
| `compilar.bat publicar-todo` | Servidor y GitHub con una sola compilación |
| `compilar.bat entorno` | Prepara o repara el entorno |

**Pruebas**

- Windows (pytest): `windows\entorno.bat pruebas`. Incluyen comprobaciones de accesibilidad reales con MSAA (lo que lee un lector de pantalla) y las pruebas comunes de `compartido/pruebas`.
- Android (JUnit en la JVM): `compilar.bat pruebas` las pasa junto con las de Windows.
- Accesibilidad de Android con TalkBack, **solo en el emulador** (nunca en un móvil real):

  ```
  set ANDROID_SERIAL=emulator-5554
  entorno\gradle\bin\gradle.bat --no-daemon -p android connectedDebugAndroidTest
  ```

**Windows tiene además su menú propio** (`windows\entorno.bat`): crear el entorno virtual, actualizar dependencias, ejecutar con consola, auditoría automática del código, diagnóstico, limpiar compilaciones...

### Firmas y claves

Las claves viven en la carpeta `firma/`, que **nunca se sube** al repositorio (está en `.gitignore`):

- **Android**: `firma/nomesubas.jks` y `firma/firma.properties`. `compilar.bat` las crea la primera vez. Android no deja actualizar una app firmada con otra clave.
- **Windows**: `firma/windows/firma_ed25519.key`, la clave privada con la que se firma `version.json`. La pública va en `CLAVES_PUBLICAS_ED25519` de `windows/app/services/actualizador.py`, y la app rechaza cualquier `version.json` que no esté firmado con ella.

**Si haces tu propia versión** (un *fork*), crea tus claves y cambia lo que apunta al autor:

1. Clave de Windows: `windows\.venv\Scripts\python.exe windows\tools\firmar_version.py generar`, guarda la privada en `firma/windows/` y pega la pública en `CLAVES_PUBLICAS_ED25519`.
2. Direcciones de actualización: `URL_MANIFIESTO` y `URL_GITHUB` en `windows/app/services/actualizador.py`; la del servidor de Android en `android/app/build.gradle.kts` (`URL_ACTUALIZACIONES`) y la de GitHub en `MANIFIESTO_GITHUB` de `android/app/src/main/java/com/xebolax/nomesubaslosprecios/nucleo/OrigenActualizaciones.kt`; y `REPOSITORIO` en `herramientas/publicar_github.py`.
3. Borra `herramientas/huella_firma.txt` (la huella del certificado de Android publicado); se vuelve a crear con tu clave en la primera publicación.

### Publicar una versión

1. Sube la versión en `windows/app/core/version.py` (`APP_VERSION`), `windows/pyproject.toml` y `android/app/build.gradle.kts` (`versionName` y `versionCode`). Si el cambio es de las dos apps, el mismo número en las dos.
2. Escribe las novedades en `compartido/recursos/novedades.md` (sección `## <versión>`).
3. `compilar.bat pruebas` sin fallos.
4. Commit y etiqueta: `git tag v<versión>` y `git push --follow-tags`.
5. `compilar.bat publicar-todo`: compila las dos, firma, copia al servidor y crea la release en GitHub con estos archivos:
   - `NoMeSubasLosPrecios_v<versión>.apk` y `version.json` (Android).
   - `NoMeSubasLosPrecios-<versión>-win64.zip` y `version-windows.json` (Windows: el `windows/version.json` firmado).

Las apps buscan las actualizaciones en `https://github.com/hxebolax/NoMeSubasLosPrecios/releases/latest/download/`, en el servidor del autor o en una carpeta con su misma estructura (`version.json` y APK en la raíz; `windows/version.json` y ZIP en `windows/`).

### Añadir o arreglar una tienda

1. Mira cómo publica el precio (JSON-LD, metadatos, microdatos o el HTML visible) y si deja descargar la página o hace falta el navegador integrado.
2. Añade o corrige su entrada en [`compartido/recursos/tiendas.json`](compartido/recursos/tiendas.json): reglas `precio`, `titulo`, `imagen` y `disponible` (selectores CSS, con `atributo` opcional), textos de `bloqueo`, `"navegador": true` si hace falta, y en `notas` y `comprobado` lo que viste y cuándo.
3. Añade una página de ejemplo reducida en `compartido/pruebas/paginas/` y su resultado esperado en `paginas.json`.
4. `compilar.bat pruebas`: las dos apps deben dar el mismo resultado.

El orden en que se busca el precio y el formato de `tiendas.json` están en la especificación.

### Convenciones

- **Todo en español de España**: interfaz, mensajes, registros, comentarios y documentación.
- **Accesibilidad primero**: en Windows, etiqueta creada justo antes de cada control, letras de acceso sin repetirse en la misma ventana, ayuda con Ctrl+H; en Android, filas de una sola parada, acciones de TalkBack y foco que vuelve.
- **Nada de trucos contra las tiendas**: ni cambiar huellas ni resolver verificaciones automáticamente.
- Un commit por cambio, con el mensaje en español, y una etiqueta `v<versión>` por cada versión publicada.
- [`LEEME.md`](LEEME.md) tiene más detalle del entorno y de la publicación, y [`AGENTS.md`](AGENTS.md) las instrucciones para asistentes de IA que trabajen en el proyecto.

---

## Licencia

[GNU General Public License v3.0](LICENSE). Puedes usar, estudiar, cambiar y compartir este programa; si distribuyes una versión modificada, debe seguir siendo libre bajo la misma licencia.

© Héctor J. Benítez Corredera.
