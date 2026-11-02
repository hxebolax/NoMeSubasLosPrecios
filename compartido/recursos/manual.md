# Manual de No Me Subas Los Precios

No Me Subas Los Precios vigila el precio de los productos que te interesan en las tiendas online y te avisa cuando bajan, cuando llegan al precio que quieres, cuando marcan un mínimo histórico, cuando vuelven a estar disponibles y, como dice su nombre, cuando te los suben.

Hay una versión para **Windows** y otra para **Android**. Hacen lo mismo y se pasan los datos entre ellas con un archivo. Las diferencias se señalan con «En Windows» y «En Android».

Creada por Héctor J. Benítez Corredera. Está pensada para usarse con lector de pantalla: NVDA, JAWS o Narrador en Windows, y TalkBack en Android.

## Cómo funciona

- Le das la dirección de la página de un producto.
- La app descarga esa página, igual que haría tu navegador, y saca el nombre, el precio y si está disponible.
- Cada cierto tiempo (cada 6 horas, si no lo cambias) la vuelve a comprobar.
- Guarda un historial con cada cambio y te avisa con una notificación.
- No hay ningún servidor intermedio ni cuenta: todo se hace en tu equipo o en tu móvil, y tus productos no salen de ahí salvo que los exportes tú.

## Instalar

### En Windows

1. Descomprime `NoMeSubasLosPrecios-<versión>-win64.zip` en la carpeta que quieras (por ejemplo, en Documentos o en un USB).
2. Abre `NoMeSubasLosPrecios.exe`.

Es una aplicación portable: no se instala ni escribe nada fuera de su carpeta. Todo lo que guarda va en la subcarpeta `data`. Para llevarla a otro equipo, copia la carpeta entera.

La versión de Windows necesita Windows 10 u 11 de 64 bits. Para las tiendas que se leen con el navegador integrado usa el motor de Edge (WebView2), que ya viene con Windows 11 y con Windows 10 actualizado.

### En Android

1. Copia `NoMeSubasLosPrecios.apk` al móvil y ábrelo. Si Android lo pide, permite instalar aplicaciones de esa fuente.
2. Abre la app. Al añadir el primer producto te pedirá permiso para enviar notificaciones: acéptalo para recibir los avisos.

Necesita Android 7.0 o posterior.

## Primeros pasos

1. **Añade un producto** (ver el apartado siguiente).
2. Si quieres, ponle un **precio deseado**: te avisará cuando el precio sea igual o menor.
3. Organízalo en una **categoría** (por ejemplo, Perfumes, Animales, Electrónica).
4. Deja la app trabajando:
   - En Windows, al cerrar la ventana se queda en la bandeja del sistema y sigue comprobando. Para salir del todo, usa Archivo, Salir.
   - En Android, las comprobaciones se hacen en segundo plano aunque la app esté cerrada.

## Añadir un producto

### En Windows

- Copia la dirección del producto en el navegador (Ctrl+L y Ctrl+C) y pulsa **Ctrl+N** en la app. Si el portapapeles tiene una dirección, ya aparece escrita.
- Rellena lo que quieras y pulsa Aceptar.

### En Android

- Desde el navegador: abre el producto, pulsa **Compartir** y elige **No Me Subas Los Precios**. Se abre Añadir producto con la dirección escrita.
- Desde la app: botón **Añadir producto**, y pega la dirección.

### Los campos

- **Dirección**: la única obligatoria. La app la limpia sola: quita los parámetros de seguimiento y, en Amazon, la reduce a la forma corta.
- **Nombre**: si lo dejas vacío, se usa el de la página.
- **Categoría**: elige una o crea una nueva desde la propia lista.
- **Grupo para comparar**: si sigues el mismo producto en varias tiendas, ponles el mismo grupo (por ejemplo, «Robot R5») y la sección Comparar te dirá cuál es el más barato.
- **Precio deseado**: aviso cuando el precio sea igual o menor.
- **Avisar solo de bajadas de al menos este porcentaje**: 0 avisa de cualquier bajada.
- **Avisar si vuelve a estar disponible**.
- **Selector CSS propio** (avanzado): solo si la app no encuentra el precio y sabes qué elemento de la página lo contiene. Normalmente no hace falta: es mejor usar «Elegir el precio en la página».
- **Notas**.

Al aceptar, la app **comprueba la página en ese momento** (con una espera que puedes cancelar) y te dice lo que ha encontrado: «Encontrado: nombre, precio, disponible. ¿Guardar?».

### Si el producto tiene varios tamaños o colores

En perfumería, moda o comida de animales es normal que una página tenga varias variantes con precios distintos. Si la dirección no dice cuál es, la app te ofrece:

- **Elegir variante**: una lista con cada tamaño o color y su precio. La elegida es la que se seguirá.
- **Guardar el precio «desde»**: el más barato de todos. En la lista aparece como «desde 51,95 €».

### Si no encuentra el precio con seguridad

La app nunca se inventa un precio. Si no está segura, te muestra **la lista de importes que hay en la página**, cada uno con su contexto, por ejemplo:

- «39,99 €, junto al botón de compra»
- «47,05 €, tachado»
- «4,99 €, gastos de envío»

Elige el correcto y la app recordará dónde está en la página para las siguientes comprobaciones. Puedes marcar **«Usar también para todos los productos de esta tienda»**. Si un día la tienda cambia su diseño y ese sitio ya no existe, la app te lo dirá («La posición del precio en la página ha cambiado») en vez de guardar un precio dudoso.

Esta lista también se puede abrir cuando quieras: **Elegir el precio en la página**, en los detalles o al editar el producto.

## Las secciones

En Android están en el **menú lateral** (botón Abrir menú, arriba a la izquierda). En Windows están en la lista **Secciones**, a la izquierda de la ventana, y en el menú Ver (Ctrl+1 a Ctrl+7).

1. **Todos los productos.**
2. **Categorías**: primero la lista de categorías con cuántos productos tiene cada una (y «Sin categoría»); al entrar en una, sus productos.
3. **Tiendas**: lo mismo, por tienda.
4. **Ofertas**: lo que ha bajado en los últimos 7 días, lo que está en su mínimo histórico y lo que está en tu precio deseado o por debajo, de la mayor bajada a la menor.
5. **Favoritos.**
6. **Comparar**: los grupos de productos; al entrar en uno, sus tiendas de la más barata a la más cara y cuánto más cuesta cada una.
7. **Avisos**: todo lo que te ha notificado la app, con los no leídos primero. Puedes marcarlos como leídos y borrarlos.

### La lista de productos

Cada producto se lee de una vez, empezando por su estado si tiene alguno: «En pausa», «Agotado», «Bloqueado por la tienda», «Error» o «En oferta». Después, el nombre, el precio, el cambio («bajó 10,00 € (7 %)»), la tienda y la categoría.

- **Buscar**: por nombre, tienda, categoría, notas o grupo. En Windows, Ctrl+F; en Android, el botón Buscar productos.
- **Ordenar**: por nombre, precio, mayor bajada, último cambio, fecha de alta o tienda. Se recuerda.
- **Filtrar**: solo activos, solo con error, solo agotados.

### Acciones de un producto

- Abrir en el navegador.
- Ver detalles.
- Comprobar ahora.
- Editar.
- Mover a categoría.
- Marcar como favorito o quitar de favoritos.
- Pausar o reanudar la comprobación.
- Copiar o compartir el enlace.
- Eliminar. En Windows pide confirmación; en Android se puede deshacer.

En Windows están en el menú Producto y en el menú contextual (tecla Aplicaciones o Mayúsculas+F10). En Android, toca el producto para ver sus detalles; con TalkBack, las acciones están en el menú de acciones (deslizar arriba y a la derecha, o tocar con tres dedos según tu configuración) y con una pulsación larga.

## Detalles de un producto

- Nombre, precio actual y si está disponible.
- Tienda, categoría, grupo, precio deseado y alerta de porcentaje.
- Precio inicial, mínimo y máximo con sus fechas, y la media.
- De dónde sale el precio («JSON-LD», «regla de la tienda», «API de la tienda», «elegido por ti»...) y la confianza.
- Última comprobación y, si lo hubo, el último error.
- Un **resumen en una línea**, pensado para oírlo de una vez: «Ahora 129,99 €. Mínimo 119,00 € el 3 de octubre. Máximo 149,00 €. Está un 9,2 % por encima del mínimo.»
- El **historial** como lista: fecha, precio y cambio respecto al anterior. Solo se guarda una fila cuando algo cambia.
- Una gráfica del precio. Es solo visual: lo mismo está en el resumen y en el historial.

## Los avisos

| Aviso | Cuándo |
|---|---|
| ¡Precio deseado alcanzado! | El precio baja hasta tu precio deseado o menos |
| Mínimo histórico | Es el precio más bajo que ha visto la app |
| Ha bajado de precio | Cualquier bajada, o la del porcentaje que elegiste |
| ¡Te han subido el precio! | El precio sube |
| Vuelve a estar disponible | Estaba agotado y ya no |
| Agotado | Se agota (desactivado por defecto) |
| No se puede leer el precio | Tres errores seguidos (desactivado por defecto) |

Cada comprobación da como mucho un aviso por producto, el más importante. En Ajustes puedes desactivar cada tipo y elegir que no se avise de cambios menores que un porcentaje.

## Las tiendas

La app trae reglas comprobadas para **más de 160 tiendas** españolas: perfumerías (Primor, Druni, Arenal, Perfumes Club...), farmacias (PromoFarma, Farmacia Barata...), animales (Tiendanimal, Kiwoko, zooplus, Miscota...), supermercados (Mercadona, Alcampo, Eroski, Consum...), moda, deporte, hogar, electrónica (Amazon, PcComponentes, MediaMarkt, Coolmod...), libros y juguetes.

Con cualquier otra tienda también funciona: la app reconoce las plataformas de tienda más usadas (Shopify, WooCommerce, PrestaShop, Magento y otras) y los datos que las tiendas publican para los buscadores. Si aun así no está segura, te pregunta (ver «Si no encuentra el precio con seguridad»).

### Tiendas que bloquean o que necesitan el navegador

Algunas tiendas grandes (las del grupo Inditex, a veces Amazon, Notino, Sephora, Carrefour, Worten, Decathlon, El Corte Inglés...) no dejan descargar sus páginas a un programa, y otras montan el precio con JavaScript (AliExpress, Temu, Xiaomi...). Para ellas la app usa un **navegador integrado**: carga la página con el motor web del sistema, como si la abrieras tú, y lee el precio de la página ya cargada.

- Si aun así la tienda pide verificar que no eres un robot, el producto aparece como **«Bloqueado por la tienda»** (nunca como agotado) y se vuelve a intentar en la siguiente comprobación.
- Puedes usar **«Abrir la tienda en la app»** (en los detalles del producto o en Gestionar tiendas): se abre la página dentro de la app para que aceptes las cookies o pases la verificación. Ciérrala con Escape en Windows o con Atrás en Android. Lo que aceptes ahí se recuerda para las comprobaciones siguientes.
- La app no hace nada para engañar a las tiendas: si una tienda no quiere que se lea su página, no se fuerza.

### Gestionar tiendas

Ver, renombrar, poner selectores propios, elegir cómo se descarga (automático, siempre directo o siempre con el navegador), **probar** las reglas con un producto de la tienda y borrar las que no tengan productos.

### Gestionar categorías

Añadir, renombrar, borrar (sus productos pasan a «Sin categoría») y cambiar el orden.

## Pasar los productos entre Windows y Android

Las dos apps usan el mismo archivo, así que puedes empezar en el PC y seguir en el móvil, o al revés.

### Exportar

- En Windows: Archivo, Exportar (Ctrl+E). Elige si incluir los ajustes y dónde guardar el archivo.
- En Android: menú lateral, Importar y exportar, Exportar. Se abre el selector de archivos de Android: puedes guardarlo en Descargas, en Drive o en otra app.

El archivo se llama `NoMeSubasLosPrecios-AAAA-MM-DD.json` y lleva productos, categorías, tiendas, historial y avisos.

### Importar

- En Windows: Archivo, Importar (Ctrl+I).
- En Android: menú lateral, Importar y exportar, Importar.

Antes de cambiar nada se muestra un resumen («El archivo tiene 42 productos... se añadirán 10 y se actualizarán 32») y eliges:

- **Combinar** (recomendado): añade lo nuevo y actualiza lo que ya tenías, sin duplicar. El historial se une.
- **Reemplazar todo**: borra lo que hay y carga el archivo. En Windows se hace antes una copia de seguridad.

### Para hojas de cálculo

**Exportar a CSV** guarda la lista de productos para abrirla con Excel o LibreOffice. Ese archivo no se puede volver a importar.

## Ajustes

- **Cada cuánto comprobar**: 1, 2, 3, 6, 12 o 24 horas.
- **Comprobar al abrir la app** si ya toca.
- **Qué avisar**: bajadas, subidas, precio deseado, mínimo histórico, disponible, agotado y errores.
- **Ignorar cambios menores que** un porcentaje.
- **Pausa entre páginas de la misma tienda** y **tiempo máximo por página**: para no cargar a las tiendas.
- **Cuántos días guardar los avisos.**
- **Buscar actualizaciones** al abrir.
- **Enviar una notificación de prueba**: para comprobar que los avisos te llegan.
- Solo en Windows: **minimizar a la bandeja** al cerrar, **iniciar con Windows** (en la bandeja) y **sonidos**.
- Solo en Android: **comprobar solo con wifi** y el botón para la **optimización de batería**.

### Si en Android no llegan los avisos a tiempo

Algunos fabricantes retrasan o cortan las tareas en segundo plano para ahorrar batería. Si las comprobaciones se retrasan mucho:

1. En Ajustes, pulsa el botón de optimización de batería y quita la optimización para No Me Subas Los Precios.
2. Mira las instrucciones para tu marca de móvil en dontkillmyapp.com.

## Actualizaciones

Las dos versiones buscan versiones nuevas al abrirse (como mucho una vez al día) y cuando lo pides con **Buscar actualizaciones**. Muestran las novedades y:

- En Windows descargan la nueva versión, comprueban su firma y la instalan sin tocar tus datos de la carpeta `data`. Si la nueva no arrancara, vuelven a la anterior.
- En Android descargan el APK, comprueban que es auténtico y abren el instalador de Android.

## Teclas en Windows

### Generales

- Ctrl+N: añadir producto.
- Ctrl+I: importar.
- Ctrl+E: exportar.
- F5: comprobar todos ahora.
- Ctrl+1 a Ctrl+7: ir a cada sección.
- Ctrl+F: buscar.
- Ctrl+coma: preferencias.
- F1: este manual.
- Ctrl+F1: lista de teclas.
- Ctrl+H: ayuda del control que tiene el foco.
- Tabulador y Mayúsculas+Tabulador: pasar entre la lista de secciones, la de grupos, la búsqueda y la lista de productos.

### En la lista de productos

- Intro: detalles.
- Ctrl+Intro: abrir en el navegador.
- Mayúsculas+F5: comprobar este producto.
- F2: editar.
- Ctrl+M: mover a categoría.
- Ctrl+D: favorito.
- Ctrl+P: pausar o reanudar.
- Ctrl+Mayúsculas+C: copiar el enlace.
- Suprimir: eliminar.
- Flechas izquierda y derecha: leer las columnas una a una.
- Tecla Aplicaciones: menú contextual.

## Tus datos

- En Windows, todo está en la carpeta `data`, junto al programa: la base de datos, los ajustes, los registros y una copia de seguridad diaria de la base de datos (se guardan las 7 últimas en `data\backups`). Ayuda, Abrir carpeta de datos la abre.
- En Android, en el almacenamiento interno de la app, incluido en la copia de seguridad de Android.
- La app solo se conecta a las tiendas de tus productos y al servidor de actualizaciones. No envía tus productos a ningún sitio.

## Preguntas frecuentes

### Un producto sale «Bloqueado por la tienda»

La tienda ha pedido comprobar que no eres un robot. Prueba «Abrir la tienda en la app», acepta las cookies o pasa la verificación y ciérrala. Si sigue igual, esa tienda no deja leer sus precios desde programas: la app lo seguirá intentando en cada comprobación.

### El precio que muestra no es el de la página

Abre el producto y usa **Elegir el precio en la página**. Si el producto tiene tamaños o colores, usa **Elegir variante**.

### «No se encontró el precio en la página»

Puede que la tienda haya cambiado su diseño o que la dirección ya no sea de un producto (por ejemplo, si lo han retirado y la página lleva a una categoría). Abre la dirección en el navegador para comprobarlo y, si el producto sigue ahí, usa Elegir el precio en la página.

### ¿Por qué Amazon a veces funciona y a veces no?

Amazon decide en cada visita si pide una verificación. Cuando la pide, el producto queda como bloqueado hasta la siguiente comprobación, sin perder su historial.

### ¿Cuántos productos puedo seguir?

Los que quieras. Con muchos, cada comprobación tarda más, porque la app deja unos segundos entre las páginas de una misma tienda para no saturarla.
