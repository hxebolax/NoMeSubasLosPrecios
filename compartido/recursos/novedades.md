# Novedades

## 1.1.0

Windows y Android.

- **Colores en la lista**, para quien ve la pantalla: en verde lo que ha bajado o está en oferta, en rojo lo que ha subido, en azul lo que ha llegado a tu precio deseado y en gris lo agotado o con problemas. Cada color se cambia en Preferencias, pestaña Colores (Windows) o en Ajustes, Colores de la lista (Android): doce colores o ninguno, cada uno con su muestra y su nombre, el fondo de la fila o el texto, y una vista previa. Se aplica al momento, sin reiniciar. Con lector de pantalla no cambia nada: cada fila ya decía su estado.
- **G2A ya funciona.** Su protección dejaba la descarga sin respuesta y la app lo daba como «sin conexión»; ahora va con el navegador integrado y sigue el precio normal de la oferta que G2A pone para comprar (no el de G2A Plus).
- **Más tiendas de videojuegos**: Steam, GOG, Epic Games Store, PlayStation Store, Microsoft Store (Xbox), Nintendo eShop, Humble Bundle, Fanatical, Green Man Gaming y GAMIVO, además de las que ya estaban (GAME, xtralife, Instant Gaming, Eneba y Kinguin).
- **Mejor lectura del precio en tiendas que la app no conoce**: un precio en negrita ya no se toma por un precio tachado (pasaba en muchas webs modernas) y sí se reconocen los tachados de esas webs. Si una tienda deja la descarga sin responder, se prueba con el navegador integrado antes de dar el error.
- Al pegar un enlace de G2A se quita el parámetro de seguimiento `suid`, para no guardar el mismo producto dos veces.

## 1.0.3

Solo Windows: actualizaciones más seguras.

- Si abres la aplicación justo cuando se está actualizando, la actualización ya no falla: cualquier copia de la versión nueva que se abra confirma que funciona.
- Si una actualización tiene que volver a la versión anterior, primero cierra las copias abiertas de la aplicación. Antes podía restaurar a medias y dejar archivos sin copiar (por ejemplo, el que hace falta para descargar las páginas con conexión segura, y entonces todas las comprobaciones fallaban).

## 1.0.2

Solo Windows: arreglos de errores que salían en el registro.

- «Comprobar todos» (y la comprobación automática) fallaba siempre en cuanto había dos productos de la misma tienda: «La comprobación falló. Los detalles están en el registro.» Ya comprueba todos los productos.
- Si la comprobación automática falla, ya no lo vuelve a intentar cada minuto: espera 15 minutos, luego 30, luego una hora, y como mucho el intervalo de comprobación que tengas elegido.
- Al aceptar una actualización, la aplicación se cierra de verdad para que se pueda sustituir, aunque tengas activado «minimizar a la bandeja». Antes solo se ocultaba y la actualización se cancelaba a los 90 segundos.
- Si en una sesión el registro fallo_nativo.log anota excepciones de Windows que se recuperan solas (pasa a veces con el lector de pantalla al abrir una ventana), al cerrar con normalidad se aclara en ese mismo archivo que no hubo ningún cierre.

## 1.0.1

Solo Windows: arreglos de accesibilidad.

- En «Añadir producto» y «Editar producto», el lector ya lee el campo «Avisar solo de bajadas de al menos (%)» al llegar a él con el Tabulador. Ahora es un campo de texto normal: escribe un número de 0 a 100 (por ejemplo 5 o 7,5). Lo mismo con el campo «Ignorar bajadas y subidas menores de (%)» de Preferencias.
- Los diálogos de confirmación ya no muestran dos botones «Cancelar» seguidos (por ejemplo, el de «Encontrado... ¿Guardar?» al añadir un producto). Escape equivale a Cancelar.
- Ninguna ventana repite una letra de acceso rápido. Cambian estas:
  - Añadir y Editar producto: Alt+T va a Categoría y Alt+U a Grupo para comparar (Alt+C es Cancelar y Alt+G, Guardar).
  - Gestionar categorías: Alt+T va a la lista de categorías (Alt+C es Cerrar).
  - Editar tienda: Alt+I abre la tienda en la app (Alt+A es Aceptar).
  - Importar: Alt+U va al resumen y Alt+M a Combinar (Alt+R es Reemplazar todo y Alt+C, Cancelar).
  - Manual: Alt+O va al texto del manual (Alt+C es Cerrar).

## 1.0.0

- Primera versión, para Windows y para Android, con las mismas funciones en las dos.
- Seguimiento de precios por dirección de producto, con historial, mínimo, máximo y gráfica.
- Avisos de precio deseado, mínimo histórico, bajadas, subidas, vuelta de stock, agotado y errores.
- Secciones: todos, categorías, tiendas, ofertas, favoritos, comparar entre tiendas y avisos.
- Reglas comprobadas para más de 160 tiendas españolas y extracción automática para cualquier otra (Shopify, WooCommerce, PrestaShop, Magento y más).
- Elegir el precio entre los importes de la página cuando no hay uno seguro, y elegir la variante (tamaño o color).
- Navegador integrado para las tiendas que montan el precio con JavaScript o no dejan descargar sus páginas.
- Importar y exportar en un archivo común para pasar los productos entre Windows y Android, y exportar a CSV.
- Notificaciones del sistema, comprobación en segundo plano y actualizaciones automáticas.
