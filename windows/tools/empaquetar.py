"""Empaqueta la compilación en ``dist/`` con la versión en el nombre.

Toma ``build/NoMeSubasLosPrecios`` (generado por ``setup_cx.py``) y crea en
``dist/``:

- ``NoMeSubasLosPrecios-<versión>-win64.zip`` con la máxima compresión. Dentro
  todo cuelga de una carpeta ``NoMeSubasLosPrecios/`` (al descomprimir no se
  esparcen archivos sueltos; el actualizador la quita al instalar).
- ``version.json`` con la versión, el nombre del ZIP (relativo a
  ``version.json``: van juntos en ``…/NoMeSubasLosPrecios/windows/``), el
  SHA-256, el tamaño, la fecha y las novedades de esta versión.

Antes de comprimir vuelve a pasar ``verificar_build.py``: nunca se empaqueta
una compilación con datos personales.

Con ``--firmar`` firma ``version.json`` (Ed25519) con la clave privada de
``../firma/windows`` (fuera del proyecto). Sin firma, el actualizador de las
instalaciones rechazaría el paquete: ``entorno.bat publicar`` usa ``--firmar``.

Basado en la plantilla del agente «entorno-virtual».
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import zipfile
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

# ── CONFIGURACIÓN ────────────────────────────────────────────────────────────
NOMBRE_APP = "NoMeSubasLosPrecios"
EJECUTABLE = "NoMeSubasLosPrecios.exe"
# Clave privada para firmar version.json (NUNCA dentro del proyecto ni de la distribución).
CLAVE_FIRMA = RAIZ.parent / "firma" / "windows" / "firma_ed25519.key"
# ─────────────────────────────────────────────────────────────────────────────

ORIGEN = RAIZ / "build" / NOMBRE_APP
DESTINO = RAIZ / "dist"


def leer_version() -> str:
	"""Lee APP_VERSION de app/core/version.py sin importar la aplicación."""
	try:
		texto = (RAIZ / "app" / "core" / "version.py").read_text(encoding="utf-8")
	except OSError:
		return "0.0.0"
	coincidencia = re.search(r"APP_VERSION\s*=\s*[\"']([^\"']+)[\"']", texto)
	return coincidencia.group(1) if coincidencia else "0.0.0"


def nombre_zip(version: str) -> str:
	"""``NoMeSubasLosPrecios-1.0.0-win64.zip``."""
	return f"{NOMBRE_APP}-{version}-win64.zip"


def sha256_de(ruta: Path) -> str:
	"""Calcula el SHA-256 de un archivo leyendo por bloques de 1 MB."""
	resumen = hashlib.sha256()
	with ruta.open("rb") as archivo:
		for bloque in iter(lambda: archivo.read(1024 * 1024), b""):
			resumen.update(bloque)
	return resumen.hexdigest()


def comprimir(origen: Path, destino: Path, carpeta_interna: str) -> int:
	"""Comprime ``origen`` en ``destino`` y devuelve el número de archivos."""
	total = 0
	with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zip_:
		for archivo in sorted(origen.rglob("*")):
			if archivo.is_file():
				interno = Path(carpeta_interna) / archivo.relative_to(origen)
				zip_.write(archivo, interno.as_posix())
				total += 1
	return total


def novedades_de(version: str) -> str:
	"""Líneas de ``novedades.md`` (recursos comunes) de esta versión, en texto llano."""
	for ruta in (RAIZ / "data" / "recursos" / "novedades.md", RAIZ.parent / "compartido" / "recursos" / "novedades.md"):
		if ruta.is_file():
			texto = ruta.read_text(encoding="utf-8-sig")
			break
	else:
		return ""
	lineas: list[str] = []
	dentro = False
	for linea in texto.splitlines():
		if linea.startswith("## "):
			dentro = re.search(rf"\b{re.escape(version)}\b", linea) is not None
			continue
		if dentro and linea.strip():
			lineas.append(linea.strip())
	return "\n".join(lineas)


def firmar(ruta_json: Path) -> None:
	"""Firma el manifiesto con ``tools/firmar_version.py``."""
	if not CLAVE_FIRMA.is_file():
		raise SystemExit(f"ERROR: falta la clave privada {CLAVE_FIRMA}. Sin firma, el actualizador rechazaría el paquete.")
	sys.path.insert(0, str(Path(__file__).resolve().parent))
	try:
		from firmar_version import firmar as firmar_manifiesto  # type: ignore[import-not-found]

		firmar_manifiesto(str(CLAVE_FIRMA), str(ruta_json))
	finally:
		sys.path.pop(0)
	print("version.json firmado (Ed25519).")


def main(argumentos: list[str] | None = None) -> int:
	"""Verifica, comprime y genera el manifiesto de la versión."""
	analizador = argparse.ArgumentParser(description="Empaqueta la compilación en dist/.")
	analizador.add_argument("--firmar", action="store_true", help="Firma version.json con la clave de ../firma/windows.")
	opciones = analizador.parse_args(argumentos)
	if not ORIGEN.is_dir():
		print(f"No existe {ORIGEN}. Compile primero con setup_cx.py.")
		return 1

	sys.path.insert(0, str(Path(__file__).resolve().parent))
	from verificar_build import verificar

	problemas = verificar(ORIGEN, EJECUTABLE)
	if problemas:
		print("No se empaqueta: la compilación no está limpia.")
		for problema in problemas:
			print(f"  - {problema}")
		return 1

	version = leer_version()
	DESTINO.mkdir(parents=True, exist_ok=True)
	zip_destino = DESTINO / nombre_zip(version)
	zip_destino.unlink(missing_ok=True)
	print(f"Comprimiendo {ORIGEN.name} en {zip_destino.name} (máxima compresión)...")
	archivos = comprimir(ORIGEN, zip_destino, NOMBRE_APP)
	tamano = zip_destino.stat().st_size
	print(f"Listo: {archivos} archivos, {tamano / (1024 * 1024):.1f} MB.")

	manifiesto = {
		"app": NOMBRE_APP,
		"version": version,
		"file": zip_destino.name,
		"sha256": sha256_de(zip_destino),
		"size": tamano,
		"date": date.today().isoformat(),
	}
	novedades = novedades_de(version)
	if novedades:
		manifiesto["novedades"] = novedades
	ruta_json = DESTINO / "version.json"
	ruta_json.write_text(json.dumps(manifiesto, indent=4, ensure_ascii=False) + "\n", encoding="utf-8")
	if opciones.firmar:
		firmar(ruta_json)
	else:
		print("version.json SIN firmar (use «entorno.bat publicar» para firmarlo).")
	print("Archivos para publicar en la carpeta windows del servidor:")
	print(f"  1) {zip_destino}")
	print(f"  2) {ruta_json}")
	return 0


if __name__ == "__main__":
	sys.exit(main())
