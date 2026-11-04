# Novedades

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
