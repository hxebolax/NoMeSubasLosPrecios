# No Me Subas Los Precios

Creado por Héctor J. Benítez Corredera.

Seguimiento de precios de productos de tiendas online, con avisos cuando bajan, llegan al precio deseado, marcan un mínimo histórico, vuelven a estar disponibles o suben. Dos apps gemelas con las mismas funciones, accesibles con lector de pantalla:

- **Windows**: Python + wxPython, portable, compilada con cx_Freeze (carpeta `windows`).
- **Android**: Kotlin con Views y Material 3, accesible con TalkBack (carpeta `android`).

El manual de usuario, común a las dos, está en [compartido/recursos/manual.md](compartido/recursos/manual.md). Dentro de las apps se abre con F1 (Windows) o desde el menú lateral, Manual (Android).

## compilar.bat

Haz doble clic y elige:

1. Compilar todo (Windows y Android).
2. Compilar la versión de Windows (ZIP en `windows\dist`).
3. Compilar la versión de Android (`NoMeSubasLosPrecios.apk` en esta carpeta).
4. Compilar Android e instalar en el móvil conectado.
5. Instalar en el móvil el APK ya compilado.
6. Ejecutar la versión de Windows desde el código.
7. Pasar todas las pruebas (las de las dos apps).
8. Abrir el emulador de Android.
9. Ver los móviles conectados.
10. Preparar las actualizaciones en `dist`.
11. Preparar y copiar las actualizaciones al servidor.
12. Preparar o reparar el entorno.

También acepta una orden: `compilar.bat todo`, `windows`, `android`, `instalar`, `android-instalar`, `ejecutar`, `pruebas`, `emulador`, `dispositivos`, `publicar`, `servidor` o `entorno`.

La versión de Windows tiene además su propio `windows\entorno.bat` (crear el entorno virtual, pruebas, compilar, auditoría, diagnóstico...).

## Entorno (carpeta `entorno`)

Todo lo necesario para compilar vive en `entorno`; no se instala nada en el sistema:

- JDK 17, Android SDK (plataforma 35, build-tools 35.0.0, adb), Gradle 8.11.1 y su caché.
- Python 3.13 portátil, con el que se crea el entorno virtual de Windows (`windows\.venv`).
- Emulador `pruebas` (Android 15, x86_64).

Si falta, `compilar.bat` lo prepara con `herramientas\preparar_entorno.ps1`: lo descarga o, mucho más rápido, lo copia de la carpeta `entorno` de otro proyecto (por ejemplo, el de YouTubeRO). Al instalar el SDK se aceptan las licencias del Android SDK de Google. El script viene del agente `entorno-android-portable` de la carpeta de agentes.

## Firmas (carpeta `firma`)

- `firma\nomesubas.jks` y `firma\firma.properties`: firma de la app de Android. La crea `compilar.bat` la primera vez.
- `firma\windows\firma_ed25519.key`: clave privada con la que se firma el `version.json` de las actualizaciones de Windows. La pública va dentro de la app.

**Guarda la carpeta `firma` aparte.** Sin ella no se pueden publicar actualizaciones: Android no deja actualizar una app firmada con otra clave, y Windows rechaza un `version.json` sin la firma correcta.

## Actualizaciones

Las dos apps buscan versiones nuevas en `https://xebolax.synology.me/NoMeSubasLosPrecios/`, que es la carpeta `SynologyDrive\web\NoMeSubasLosPrecios` del usuario:

- Android: `version.json` y `NoMeSubasLosPrecios_v<versión>.apk` en la raíz. La app comprueba el tamaño, el SHA-256 y que el APK esté firmado con la misma clave, y abre el instalador.
- Windows: `windows/version.json` (firmado con Ed25519) y `windows/NoMeSubasLosPrecios-<versión>-win64.zip`. El actualizador sustituye el programa sin tocar `data` y vuelve atrás si la versión nueva no arranca.

Para publicar una versión nueva:

1. Sube la versión en `windows\app\core\version.py` y en `android\app\build.gradle.kts` (`versionName` y `versionCode`). Si el cambio es de las dos, el mismo número en las dos; si es solo de una, sube solo esa y publica solo su parte (`windows\entorno.bat publicar` y copiar `windows\dist` a la carpeta `windows` del servidor).
2. Escribe sus novedades en `compartido\recursos\novedades.md` (sección `## <versión>`).
3. `compilar.bat servidor`: compila las dos, deja en `dist` el APK, el ZIP y sus `version.json`, y los copia a la carpeta del servidor (primero los paquetes y después los `version.json`). Antes comprueba que el APK esté firmado con la clave de las versiones publicadas (`herramientas\huella_firma.txt`, que se crea en la primera publicación).

## Cómo está organizado

- `compartido/`: lo común a las dos apps.
  - [ESPECIFICACION.md](compartido/ESPECIFICACION.md): el contrato (base de datos, extracción del precio, avisos, secciones, ajustes, notificaciones, actualizaciones).
  - [FORMATO_INTERCAMBIO.md](compartido/FORMATO_INTERCAMBIO.md): el archivo JSON para pasar los datos entre Windows y Android.
  - [EXTRACTOR_GENERICO.md](compartido/EXTRACTOR_GENERICO.md): cómo se encuentra el precio en tiendas sin reglas propias (plataformas, datos incrustados, puntuación de candidatos, selección por el usuario).
  - `recursos/`: `tiendas.json` (reglas de más de 160 tiendas españolas, con la fecha y el resultado de su comprobación), `manual.md` y `novedades.md`. Android los empaqueta como assets y Windows los copia a `windows\data\recursos`.
  - `pruebas/`: importes, direcciones, páginas de ejemplo, vectores del extractor genérico y un archivo de exportación que deben pasar las dos apps con los mismos resultados.
  - `referencia_extractor/`: el prototipo en Python del extractor genérico.
- `windows/`: la app de Windows (`main.py`, `app/core`, `app/services` sin wx, `app/ui`, `tests`, `setup_cx.py`).
- `android/`: la app de Android (`app/src/main/java/com/xebolax/nomesubaslosprecios`: `nucleo` con la lógica pura, `datos`, `motor`, `ui`, `accesibilidad`, `actualizaciones`).
- `herramientas/`: `preparar_entorno.ps1` y `publicar_android.py`.
- `adjuntos/`: investigación (informes de tiendas, del extractor y de apps de seguimiento de precios) y repositorios clonados de referencia. No forma parte de las apps.

## Cómo se obtiene el precio

En este orden, se usa el primer resultado seguro:

1. El selector propio del producto (por ejemplo, el elegido por el usuario).
2. El selector propio de la tienda.
3. La API pública de la tienda (Mercadona, Consum, BM).
4. Las reglas de la tienda en `tiendas.json`.
5. Los datos para buscadores: JSON-LD, metadatos y microdatos, eligiendo la variante de la dirección y las ofertas en stock.
6. Los datos de la plataforma (Shopify, WooCommerce, PrestaShop, Magento, Salesforce, VTEX, BigCommerce).
7. El estado incrustado y la analítica de la página, solo como apoyo.
8. Una puntuación de los importes visibles (cerca del título y del botón de compra; tachados, cuotas, envío y precio por kilo restan).
9. Si nada es seguro, se pregunta al usuario con una lista de candidatos y se guarda un selector estable.

Las tiendas que no dejan descargar sus páginas o que montan el precio con JavaScript se leen con el navegador integrado (WebView2 en Windows, WebView en Android), sin trucos para engañar a la tienda. La investigación con 166 tiendas reales está en `adjuntos/investigacion-tiendas`.

## Pruebas

- `compilar.bat pruebas` pasa las de las dos apps.
- Windows: `windows\entorno.bat pruebas` (pytest).
- Android: `testDebugUnitTest` (JUnit en la JVM). La prueba de accesibilidad `AccesibilidadTest` se pasa solo en el emulador:

```
set ANDROID_SERIAL=emulator-5554
entorno\gradle\bin\gradle.bat --no-daemon -p android connectedDebugAndroidTest
```

TalkBack se activa solo en el emulador, nunca en un móvil real. Si hay un móvil conectado, fija antes `ANDROID_SERIAL` para que no se instale en él.

## Repositorios de referencia

En `adjuntos` están clonados, solo para consulta: PriceBuddy, Discount Bandit, PriceGhost, changedetection.io y price-parser. No se usa su código; sirvieron para comparar cómo extraen los precios.
