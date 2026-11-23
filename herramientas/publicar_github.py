# -*- coding: utf-8 -*-
"""
No Me Subas Los Precios - Publica la versión actual como release de GitHub.

Toma de la carpeta dist lo que ya prepararon «compilar.bat publicar» o
«compilar.bat servidor» y crea la release v<versión> con estos cuatro archivos
(ESPECIFICACION.md, «Publicación en GitHub»):

- NoMeSubasLosPrecios_v<versión>.apk y version.json (Android).
- NoMeSubasLosPrecios-<versión>-win64.zip y version-windows.json (el
  windows/version.json firmado, con otro nombre porque una release no tiene
  carpetas).

Las apps los buscan en https://github.com/<repositorio>/releases/latest/download/.
Antes comprueba que las versiones de Windows y Android coinciden con los
version.json, que la etiqueta v<versión> existe en el repositorio local y la
sube a GitHub si falta. Las notas salen de la sección «## <versión>» de
compartido/recursos/novedades.md.

Necesita la herramienta gh con la sesión iniciada (gh auth login).

Uso: python publicar_github.py [--repositorio hxebolax/NoMeSubasLosPrecios] [--borrador]
"""

import argparse
import json
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

RAIZ = pathlib.Path(__file__).resolve().parent.parent
DIST = RAIZ / "dist"
NOVEDADES = RAIZ / "compartido" / "recursos" / "novedades.md"
VERSION_PY = RAIZ / "windows" / "app" / "core" / "version.py"
GRADLE_APP = RAIZ / "android" / "app" / "build.gradle.kts"
REPOSITORIO = "hxebolax/NoMeSubasLosPrecios"
NOMBRE = "NoMeSubasLosPrecios"


def error(texto: str) -> None:
	print(f"[ERROR] {texto}")
	sys.exit(1)


def ejecutar(*orden: str, comprobar: bool = True) -> subprocess.CompletedProcess:
	resultado = subprocess.run(orden, cwd=RAIZ, capture_output=True, text=True, encoding="utf-8", errors="replace")
	if comprobar and resultado.returncode != 0:
		error(f"Falló «{' '.join(orden)}»:\n{resultado.stderr.strip() or resultado.stdout.strip()}")
	return resultado


def version_windows() -> str:
	coincidencia = re.search(r'^APP_VERSION\s*=\s*"([^"]+)"', VERSION_PY.read_text(encoding="utf-8"), re.M)
	if not coincidencia:
		error(f"No se encontró APP_VERSION en {VERSION_PY}")
	return coincidencia.group(1)


def version_android() -> str:
	coincidencia = re.search(r'versionName\s*=\s*"([^"]+)"', GRADLE_APP.read_text(encoding="utf-8"))
	if not coincidencia:
		error(f"No se encontró versionName en {GRADLE_APP}")
	return coincidencia.group(1)


def notas(version: str) -> str:
	texto = NOVEDADES.read_text(encoding="utf-8")
	coincidencia = re.search(rf"^## {re.escape(version)}\s*\n(.*?)(?=^## |\Z)", texto, re.M | re.S)
	if not coincidencia:
		error(f"Falta la sección «## {version}» en {NOVEDADES}")
	cuerpo = coincidencia.group(1).strip()
	return (
		f"{cuerpo}\n\n"
		"## Descargas\n\n"
		f"- **Android**: `{NOMBRE}_v{version}.apk`. Ábrelo en el móvil y permite instalar apps de esta fuente.\n"
		f"- **Windows**: `{NOMBRE}-{version}-win64.zip`. Descomprímelo en una carpeta y abre `{NOMBRE}.exe` "
		"(es portable: no necesita instalación).\n\n"
		"`version.json` y `version-windows.json` son para las actualizaciones automáticas de las apps.\n"
	)


def main() -> None:
	argumentos = argparse.ArgumentParser(description=__doc__.splitlines()[1])
	argumentos.add_argument("--repositorio", default=REPOSITORIO)
	argumentos.add_argument("--borrador", action="store_true", help="crearla como borrador (no la verán las apps)")
	opciones = argumentos.parse_args()

	if shutil.which("gh") is None:
		error("No se encuentra gh (GitHub CLI). Instálalo y ejecuta «gh auth login».")
	ejecutar("gh", "auth", "status")

	version = version_windows()
	if version_android() != version:
		error(f"Windows está en {version} y Android en {version_android()}: una release lleva las dos con el mismo número.")
	apk = DIST / f"{NOMBRE}_v{version}.apk"
	json_android = DIST / "version.json"
	zip_windows = DIST / "windows" / f"{NOMBRE}-{version}-win64.zip"
	json_windows = DIST / "windows" / "version.json"
	for archivo in (apk, json_android, zip_windows, json_windows):
		if not archivo.is_file():
			error(f"Falta {archivo}. Ejecuta antes «compilar.bat publicar» o «compilar.bat servidor».")
	for archivo, paquete in ((json_android, apk), (json_windows, zip_windows)):
		datos = json.loads(archivo.read_text(encoding="utf-8"))
		if datos.get("version") != version or datos.get("file") != paquete.name:
			error(f"{archivo} es de otra versión ({datos.get('version')}, {datos.get('file')}).")
		if datos.get("size") != paquete.stat().st_size:
			error(f"El tamaño de {paquete.name} no coincide con {archivo.name}: vuelve a prepararlo.")
	if "firma_ed25519" not in json.loads(json_windows.read_text(encoding="utf-8")):
		error(f"{json_windows} no está firmado: Windows lo rechazaría.")

	etiqueta = f"v{version}"
	if not ejecutar("git", "tag", "--list", etiqueta).stdout.strip():
		error(f"No existe la etiqueta {etiqueta}. Haz el commit de la versión y «git tag {etiqueta}» antes de publicar.")
	if etiqueta not in ejecutar("git", "ls-remote", "--tags", "origin", etiqueta).stdout:
		print(f"Subiendo la etiqueta {etiqueta} a GitHub...")
		ejecutar("git", "push", "origin", etiqueta)
	if ejecutar("gh", "release", "view", etiqueta, "-R", opciones.repositorio, comprobar=False).returncode == 0:
		error(f"La release {etiqueta} ya existe en {opciones.repositorio}. Bórrala en GitHub si quieres rehacerla.")

	with tempfile.TemporaryDirectory() as carpeta:
		carpeta = pathlib.Path(carpeta)
		copia_windows = carpeta / "version-windows.json"
		shutil.copyfile(json_windows, copia_windows)
		archivo_notas = carpeta / "notas.md"
		archivo_notas.write_text(notas(version), encoding="utf-8")
		orden = [
			"gh", "release", "create", etiqueta, "-R", opciones.repositorio, "--verify-tag",
			"--title", f"No Me Subas Los Precios {version}", "--notes-file", str(archivo_notas),
			str(apk), str(json_android), str(zip_windows), str(copia_windows),
		]
		if opciones.borrador:
			orden.append("--draft")
		print(f"Creando la release {etiqueta} en {opciones.repositorio}...")
		print(ejecutar(*orden).stdout.strip())
	print(f"[OK] Release {etiqueta} publicada con el APK, el ZIP y sus version.json.")


if __name__ == "__main__":
	main()
