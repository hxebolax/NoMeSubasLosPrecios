"""Migraciones del esquema de la base de datos (``PRAGMA user_version``).

La migración 1 es el modelo de datos de la especificación común con Android:
mismas tablas y columnas, fechas ISO 8601 en UTC con ``Z``, importes ``REAL``
y booleanos 0/1. La migración 2 es la de la «Extracción ampliada» del
contrato, más ``productos.estado`` (solo de Windows; no se exporta).

Reglas: una migración por cambio, siempre al final de la lista, y nunca se
edita una ya publicada.
"""

from __future__ import annotations

from app.core.base_datos import Migracion

ESQUEMA_V1 = """
CREATE TABLE categorias (
	id INTEGER PRIMARY KEY,
	uuid TEXT UNIQUE NOT NULL,
	nombre TEXT NOT NULL,
	descripcion TEXT,
	orden INTEGER NOT NULL DEFAULT 0
);
CREATE UNIQUE INDEX ix_categorias_nombre ON categorias (nombre COLLATE NOCASE);

CREATE TABLE tiendas (
	id INTEGER PRIMARY KEY,
	uuid TEXT UNIQUE NOT NULL,
	nombre TEXT NOT NULL,
	dominio TEXT UNIQUE NOT NULL,
	selector_precio TEXT,
	selector_titulo TEXT,
	selector_disponible TEXT,
	notas TEXT
);

CREATE TABLE productos (
	id INTEGER PRIMARY KEY,
	uuid TEXT UNIQUE NOT NULL,
	nombre TEXT NOT NULL DEFAULT '',
	url TEXT NOT NULL,
	tienda_id INTEGER REFERENCES tiendas (id),
	categoria_id INTEGER REFERENCES categorias (id) ON DELETE SET NULL,
	grupo TEXT,
	moneda TEXT NOT NULL DEFAULT 'EUR',
	precio_actual REAL,
	disponible INTEGER NOT NULL DEFAULT 1,
	precio_inicial REAL,
	precio_minimo REAL,
	fecha_minimo TEXT,
	precio_maximo REAL,
	fecha_maximo TEXT,
	precio_anterior REAL,
	fecha_cambio TEXT,
	precio_objetivo REAL,
	alerta_porcentaje REAL NOT NULL DEFAULT 0,
	avisar_disponible INTEGER NOT NULL DEFAULT 1,
	selector_precio TEXT,
	imagen_url TEXT,
	notas TEXT,
	favorito INTEGER NOT NULL DEFAULT 0,
	activo INTEGER NOT NULL DEFAULT 1,
	fecha_alta TEXT,
	ultima_comprobacion TEXT,
	ultimo_error TEXT,
	errores_seguidos INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX ix_productos_url ON productos (url);
CREATE INDEX ix_productos_tienda ON productos (tienda_id);
CREATE INDEX ix_productos_categoria ON productos (categoria_id);

CREATE TABLE historial (
	id INTEGER PRIMARY KEY,
	producto_id INTEGER NOT NULL REFERENCES productos (id) ON DELETE CASCADE,
	fecha TEXT NOT NULL,
	precio REAL,
	disponible INTEGER NOT NULL DEFAULT 1
);
CREATE UNIQUE INDEX ix_historial_producto_fecha ON historial (producto_id, fecha);

CREATE TABLE avisos (
	id INTEGER PRIMARY KEY,
	producto_id INTEGER REFERENCES productos (id) ON DELETE SET NULL,
	fecha TEXT,
	tipo TEXT,
	titulo TEXT,
	mensaje TEXT,
	leido INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX ix_avisos_fecha ON avisos (fecha);
"""

# Extracción ampliada (columnas comunes con Android: variante, origen_precio,
# confianza, huella_selector, desde y tiendas.modo_descarga) y, solo en
# Windows, el estado de la última comprobación (correcta, sin precio,
# bloqueada, sin conexión...), que no se exporta.
ESQUEMA_V2 = """
ALTER TABLE productos ADD COLUMN variante TEXT;
ALTER TABLE productos ADD COLUMN origen_precio TEXT;
ALTER TABLE productos ADD COLUMN confianza TEXT;
ALTER TABLE productos ADD COLUMN huella_selector TEXT;
ALTER TABLE productos ADD COLUMN desde INTEGER NOT NULL DEFAULT 0;
ALTER TABLE productos ADD COLUMN estado TEXT;
ALTER TABLE tiendas ADD COLUMN modo_descarga TEXT NOT NULL DEFAULT 'auto';
"""

MIGRACIONES: tuple[Migracion, ...] = (
	Migracion("Modelo de datos común con Android", sql=ESQUEMA_V1),
	Migracion("Extracción ampliada: variantes, origen, confianza, huella y modo de descarga", sql=ESQUEMA_V2),
)
