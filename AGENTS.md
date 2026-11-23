# No Me Subas Los Precios: instrucciones para una IA

Seguimiento de precios de productos de tiendas online, con dos apps gemelas: **Windows** (Python + wxPython, en `windows/`) y **Android** (Kotlin, en `android/`). Todo en español de España. Cómo se compila, se prueba y se publica está en `LEEME.md`.

## Regla principal: las dos apps hacen lo mismo

- El contrato está en `compartido/ESPECIFICACION.md` (datos, extracción, avisos, secciones, ajustes) y `compartido/FORMATO_INTERCAMBIO.md` (importar y exportar). Cualquier cambio de funciones se hace **en las dos apps** y se anota allí.
- Los recursos de `compartido/recursos/` (reglas de tiendas, manual, novedades) son los mismos para las dos: Android los empaqueta como assets y Windows los copia a `windows/data/recursos`. No se duplican.
- Las pruebas de `compartido/pruebas/` las pasan las dos apps con los mismos resultados. Si se añade una tienda o una regla de extracción, se añade una página de ejemplo y su resultado esperado.
- Versiones (`windows/app/core/version.py` y `android/app/build.gradle.kts`): un cambio que afecta a las dos sube las dos al mismo número. Un arreglo de una sola plataforma sube solo esa (la 1.0.1 fue solo de Windows, con Android en 1.0.0) y se anota en `compartido/recursos/novedades.md` con «Solo Windows» o «Solo Android».

## Agentes que se usan

- Windows: los de `E:\Antigravity\Agentes` (proyecto-nuevo, entorno-virtual, accesibilidad-wx, base-datos-sqlite, configuracion, hilos-y-tareas, red-http, logging-profesional, actualizador, documentacion-usuario, pruebas, auditoria-proyecto).
- Android: android-accesible y entorno-android-portable.

## Antes de dar algo por terminado

- `compilar.bat pruebas` sin fallos y `compilar.bat todo` sin errores.
- Comprobar el cambio en la app de verdad: Windows desde el código (`compilar.bat ejecutar`) y Android en el emulador. TalkBack se activa solo en el emulador, nunca en un móvil real.
- No inventar resultados: decir qué se ejecutó y qué salió.

## Repositorio local (regla permanente)

El proyecto se guarda en git para poder volver atrás si algo falla. El remoto es GitHub, público: https://github.com/hxebolax/NoMeSubasLosPrecios (desde la 1.2.0). Solo se sube (`git push`, releases) cuando el usuario lo pide, por ejemplo al pedir que se publique una versión.

- Antes de empezar se mira `git status`: si hay cambios sin guardar de antes, se guardan primero en su propio commit.
- Al terminar cada encargo se hace commit de todo lo cambiado, sin esperar a que se pida. Un commit por encargo, con el mensaje en español.
- Cada versión publicada lleva su etiqueta: `v1.0.0`, `v1.0.1`...
- Nada de `reset --hard`, `push --force` ni borrar etiquetas o historial sin que se pida.
- Para ver una versión anterior sin perder lo actual: `git switch -c prueba v1.0.0`. Para deshacer un commit ya hecho: `git revert`.
- Antes de cada subida a GitHub, comprobar que no entra nada de `firma`, `entorno`, `adjuntos` ni claves (`git ls-files` y el `.gitignore`).
- Cada versión publicada lleva su release en GitHub con el APK, el ZIP y sus `version.json` (`compilar.bat github` o `publicar-todo`).

## Carpetas que no se comparten

`entorno` (se prepara con `compilar.bat`), `firma` (claves de Android y de Windows: guardarlas aparte; sin ellas no se puede actualizar), `dist`, compilaciones y la carpeta `adjuntos` entera (informes y repositorios clonados: solo en la copia local).
