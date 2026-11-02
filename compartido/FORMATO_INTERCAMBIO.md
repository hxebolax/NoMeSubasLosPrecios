# Formato de intercambio entre Windows y Android

Un archivo JSON en UTF-8 sin BOM que escriben y leen las dos apps. Sirve para pasar los productos del PC al móvil y al revés, y como copia de seguridad legible.

- Nombre propuesto al exportar: `NoMeSubasLosPrecios-AAAA-MM-DD.json`.
- Tipo MIME en Android: `application/json`.
- Ejemplo completo y válido: [pruebas/exportacion-ejemplo.json](pruebas/exportacion-ejemplo.json).

## Estructura

Objeto raíz:

| Campo | Tipo | Obligatorio | Notas |
|---|---|---|---|
| formato | texto | sí | Siempre `NoMeSubasLosPrecios` |
| version_formato | entero | sí | 1 |
| app | texto | sí | `windows` o `android` |
| version_app | texto | sí | `1.0.0` |
| exportado | texto | sí | Fecha ISO 8601 en UTC con `Z` |
| categorias | lista | sí | Puede estar vacía |
| tiendas | lista | sí | |
| productos | lista | sí | Cada uno con su historial |
| avisos | lista | no | |
| ajustes | objeto | no | Solo si el usuario lo marca al exportar; claves de la especificación |

### categorias[]

`uuid`, `nombre`, `descripcion` (texto o nulo), `orden` (entero).

### tiendas[]

`uuid`, `nombre`, `dominio`, `selector_precio`, `selector_titulo`, `selector_disponible`, `notas` (texto o nulo), `modo_descarga` (`auto`, `directo` o `navegador`; `auto` si falta).

### productos[]

| Campo | Tipo |
|---|---|
| uuid | texto |
| nombre | texto |
| url | texto |
| tienda | texto: `uuid` de la tienda |
| categoria | texto o nulo: `uuid` de la categoría |
| grupo | texto o nulo |
| moneda | texto |
| precio_actual, precio_inicial, precio_minimo, precio_maximo, precio_anterior, precio_objetivo | número o nulo |
| fecha_minimo, fecha_maximo, fecha_cambio, fecha_alta, ultima_comprobacion | texto o nulo |
| disponible, avisar_disponible, favorito, activo | booleano (`true` o `false`) |
| alerta_porcentaje | número |
| selector_precio, imagen_url, notas, ultimo_error | texto o nulo |
| errores_seguidos | entero |
| variante, origen_precio, confianza, huella_selector | texto o nulo (pueden faltar) |
| desde | booleano (`false` si falta) |
| historial | lista de `{ "fecha": texto, "precio": número o nulo, "disponible": booleano }`, de la más vieja a la más nueva |

### avisos[]

`producto` (uuid o nulo), `fecha`, `tipo`, `titulo`, `mensaje`, `leido` (booleano).

## Reglas de lectura

- Si `formato` no es `NoMeSubasLosPrecios`, el archivo se rechaza: «Este archivo no es una exportación de No Me Subas Los Precios.»
- Si `version_formato` es mayor que la que entiende la app: «El archivo es de una versión más nueva de la app. Actualízala para importarlo.»
- Los campos que falten toman su valor por defecto; los desconocidos se ignoran. Así una versión futura puede añadir campos sin romper las anteriores.
- Un producto sin `url` o sin `uuid` se salta y se cuenta en el resumen como «no válido».
- Un producto cuya `tienda` no esté en la lista se asocia a la tienda de su dominio (creándola si hace falta).
- Los números siempre con punto decimal (JSON). Nunca importes como texto.
- La importación es **atómica**: dentro de una transacción; si algo falla, no se cambia nada y se explica el error.

## Reglas de escritura

- Sangría de 2 espacios y claves en el orden de este documento, para que el archivo se pueda leer y comparar.
- Sin los `id` internos de SQLite: las relaciones van por `uuid`.
- Escritura atómica: primero a un archivo temporal y después se renombra (en Windows). En Android, se escribe en el `Uri` elegido de una vez.
