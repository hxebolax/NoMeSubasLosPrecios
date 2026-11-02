"""Genera ``compartido/pruebas/extractor_generico.json`` (vectores comunes con Android).

Toma los casos de ``compartido/referencia_extractor/pruebas_sinteticas.py`` y
añade casos de las correcciones a JSON-LD, metadatos y microdatos de la
«Extracción ampliada». Cada caso lleva el resultado ESPERADO escrito a mano
(no el que da la app): si la app no lo cumple, este guion falla en vez de
escribir un vector equivocado.

Uso (desde windows/): ``.venv/Scripts/python.exe tools/generar_vectores_extractor.py``
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from app.services import direcciones, extractor, reglas  # noqa: E402

COMPARTIDO = RAIZ.parent / "compartido"
DESTINO = COMPARTIDO / "pruebas" / "extractor_generico.json"
URL_POR_DEFECTO = "https://tiendaejemplo.es/p/1"
BOTON = '<form><button type="submit" name="add">Añadir al carrito</button></form>'

# (nombre, url, html, precio esperado, origen esperado, extra esperado)
CASOS_JSONLD = [
	("JSON-LD con @type en minúsculas (PcComponentes)", None,
	 '<script type="application/ld+json">{"@type":"product","name":"Ratón","offers":{"@type":"Offer","price":"24.99","priceCurrency":"EUR"}}</script>',
	 24.99, "JSON-LD", {}),
	("JSON-LD con claves en mayúsculas (Casa del Libro)", None,
	 '<script type="application/ld+json">{"@type":"Book","name":"Novela","offers":{"@type":"Offer","Price":"18.90","priceCurrency":"EUR"}}</script>',
	 18.9, "JSON-LD", {}),
	("ProductGroup: variante por sku en la dirección", "https://tiendaejemplo.es/p/camiseta?sku=CAM-M",
	 '<script type="application/ld+json">{"@type":"ProductGroup","name":"Camiseta","hasVariant":['
	 '{"@type":"Product","sku":"CAM-S","name":"Camiseta S","offers":{"price":19.95}},'
	 '{"@type":"Product","sku":"CAM-M","name":"Camiseta M","offers":{"price":21.95}}]}</script>',
	 21.95, "JSON-LD", {"nombre": "Camiseta"}),
	("ProductGroup sin variante en la dirección y precios distintos: desde", None,
	 '<script type="application/ld+json">{"@type":"ProductGroup","name":"Café","hasVariant":['
	 '{"@type":"Product","sku":"C250","name":"Café 250 g","offers":{"price":12}},'
	 '{"@type":"Product","sku":"C1K","name":"Café 1 kg","offers":{"price":40}}]}</script>',
	 12.0, "JSON-LD", {"desde": True}),
	("Varias ofertas sin URL: la más barata EN STOCK; la de 0 € se descarta", None,
	 '<script type="application/ld+json">{"@type":"Product","name":"Tostadora","offers":['
	 '{"price":0,"availability":"https://schema.org/InStock"},'
	 '{"price":29.9,"availability":"https://schema.org/OutOfStock"},'
	 '{"price":34.5,"availability":"https://schema.org/InStock"}]}</script>',
	 34.5, "JSON-LD", {}),
	("Producto relacionado en isRelatedTo e ItemList: se ignoran", None,
	 '<script type="application/ld+json">{"@type":"ItemList","itemListElement":[{"@type":"Product","name":"Otro","offers":{"price":5}}]}</script>'
	 '<script type="application/ld+json">{"@type":"Product","name":"Lámpara","isRelatedTo":{"@type":"Product","name":"Bombilla","offers":{"price":3}},'
	 '"offers":{"price":45}}</script>',
	 45.0, "JSON-LD", {}),
	("Nombre con entidades HTML", None,
	 '<script type="application/ld+json">{"@type":"Product","name":"Pa&ntilde;uelo de algod&oacute;n","offers":{"price":"9.95"}}</script>',
	 9.95, "JSON-LD", {"nombre": "Pañuelo de algodón"}),
	("Metadatos: og:price:amount a 0 se salta; nunca pretax", None,
	 '<meta property="product:pretax_price:amount" content="82.64"><meta property="og:price:amount" content="0">'
	 '<meta property="product:price:amount" content="99.99"><h1>Taladro</h1>',
	 99.99, "metadatos", {}),
	("Metadatos: meta itemprop=price dentro de un tachado se salta", None,
	 '<div class="price-old"><meta itemprop="price" content="120.00"></div><div class="price"><meta itemprop="price" content="99.00"></div>',
	 99.0, "metadatos", {}),
	("Microdatos: precio partido «74 , 99 €» y disponibilidad agotado", None,
	 '<div itemscope itemtype="https://schema.org/Product"><h1 itemprop="name">Freidora</h1>'
	 '<span itemprop="price">74 <sup>, 99</sup> €</span><link itemprop="availability" href="https://schema.org/OutOfStock"></div>',
	 74.99, "microdatos", {"disponible": False}),
	("Página de categoría (CollectionPage) sin producto: error de categoría", None,
	 '<script type="application/ld+json">{"@type":"CollectionPage","name":"Zapatillas"}</script><h1>Zapatillas</h1>',
	 None, None, {"categoria": True}),
	("La palabra suelta «captcha» no es un bloqueo", None,
	 '<h1>Libro</h1><span itemprop="price" content="15.00">15,00 €</span><script src="https://www.google.com/recaptcha/api.js"></script>',
	 15.0, "microdatos", {"bloqueo": False}),
]


def _casos_sinteticos() -> list[tuple]:
	ruta = COMPARTIDO / "referencia_extractor" / "pruebas_sinteticas.py"
	sys.path.insert(0, str(ruta.parent))
	especificacion = importlib.util.spec_from_file_location("pruebas_sinteticas", ruta)
	modulo = importlib.util.module_from_spec(especificacion)
	especificacion.loader.exec_module(modulo)
	return [(n, u, h, p, None, {}) for n, u, h, p in modulo.CASOS]


def main() -> int:
	catalogo = reglas.cargar_catalogo(COMPARTIDO / "recursos" / "tiendas.json")
	vectores, fallos = [], []
	for nombre, url, html, precio, origen, extra in _casos_sinteticos() + CASOS_JSONLD:
		direccion = url or URL_POR_DEFECTO
		resultado = extractor.extraer(html, direcciones.dominio_de(direccion), catalogo, url=direccion)
		if resultado.precio != precio or (origen and resultado.origen_precio != origen):
			fallos.append(f"{nombre}: {resultado.precio} ({resultado.origen_precio}), se esperaba {precio} ({origen})")
		for clave, valor in extra.items():
			if getattr(resultado, clave) != valor:
				fallos.append(f"{nombre}: {clave} = {getattr(resultado, clave)!r}, se esperaba {valor!r}")
		vector = {"nombre": nombre, "url": direccion, "html": html, "precio": precio}
		if resultado.plataforma:
			vector["plataforma"] = resultado.plataforma
		vector["origen"] = resultado.origen_precio or None
		vector["decision"] = "acepta" if precio is not None else "pregunta"
		if "categoria" in extra and extra["categoria"]:
			vector["decision"] = "error"
		vector.update({("nombre_producto" if k == "nombre" else k): v for k, v in extra.items()})
		vectores.append(vector)
	if fallos:
		print("No se escribe el archivo: la app no da lo esperado:")
		for fallo in fallos:
			print("  -", fallo)
		return 1
	datos = {
		"_comentario": (
			"Vectores del extractor ampliado (pasos 4 a 12). Los genera windows/tools/generar_vectores_extractor.py "
			"a partir de referencia_extractor/pruebas_sinteticas.py y de casos de las correcciones a JSON-LD, metadatos "
			"y microdatos. url: dirección de la página. precio nulo: no hay precio seguro. origen: «JSON-LD», "
			"«metadatos», «microdatos», «plataforma <nombre>» o «análisis de la página». plataforma: la que dio el "
			"precio en el paso 7. decision: «acepta» (hay precio), «pregunta» (se ofrecen candidatos al usuario) o "
			"«error» (categoria: la página es una categoría). Campos extra (nombre_producto, desde, disponible, bloqueo, categoria) se "
			"comprueban si están."
		),
		"casos": vectores,
	}
	DESTINO.write_text(json.dumps(datos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
	print(f"Escritos {len(vectores)} vectores en {DESTINO}")
	return 0


if __name__ == "__main__":
	sys.exit(main())
