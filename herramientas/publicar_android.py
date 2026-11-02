# -*- coding: utf-8 -*-
"""
No Me Subas Los Precios (Android) - Prepara una actualización para el servidor.

Copia NoMeSubasLosPrecios.apk a dist\\NoMeSubasLosPrecios_v<versión>.apk y crea
dist\\version.json con la versión, el tamaño, el SHA-256 y las novedades (de la
sección «## <versión>» de compartido\\recursos\\novedades.md). Después basta con
subir los dos archivos a la carpeta NoMeSubasLosPrecios del servidor
(compilar.bat servidor lo hace).

Uso: python publicar_android.py [--apk OTRO.apk] [--dist OTRA_CARPETA]
"""

import argparse
import datetime
import hashlib
import json
import pathlib
import re
import shutil
import subprocess
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
APK = RAIZ / "NoMeSubasLosPrecios.apk"
DIST = RAIZ / "dist"
NOVEDADES = RAIZ / "compartido" / "recursos" / "novedades.md"
GRADLE_APP = RAIZ / "android" / "app" / "build.gradle.kts"
BUILD_TOOLS = RAIZ / "entorno" / "android-sdk" / "build-tools" / "35.0.0"
AAPT2 = BUILD_TOOLS / "aapt2.exe"
APKSIGNER = BUILD_TOOLS / "apksigner.bat"
# SHA-256 del certificado con el que se firmaron las versiones publicadas
HUELLA = RAIZ / "herramientas" / "huella_firma.txt"


def error(texto: str) -> None:
	print(f"[ERROR] {texto}")
	sys.exit(1)


def version_del_proyecto() -> tuple:
	gradle = GRADLE_APP.read_text(encoding="utf-8")
	nombre = re.search(r'versionName\s*=\s*"([^"]+)"', gradle)
	codigo = re.search(r"versionCode\s*=\s*(\d+)", gradle)
	if not nombre or not codigo:
		error("No se encuentran versionName y versionCode en android\\app\\build.gradle.kts")
	return nombre.group(1), int(codigo.group(1))


def comprobar_apk(apk: pathlib.Path, version: str, codigo: int) -> None:
	"""El APK compilado tiene que ser de esa versión (evita publicar uno antiguo)."""
	if not AAPT2.exists():
		print("[AVISO] Sin aapt2 no se puede comprobar la versión del APK.")
		return
	salida = subprocess.run([str(AAPT2), "dump", "badging", str(apk)], capture_output=True, text=True, errors="replace").stdout
	datos = re.search(r"versionCode='(\d+)' versionName='([^']*)'", salida)
	if not datos:
		error(f"No se pudo leer la versión de {apk.name}")
	if int(datos.group(1)) != codigo or datos.group(2) != version:
		error(f"{apk.name} es la versión {datos.group(2)} ({datos.group(1)}), no la {version} ({codigo}). Compila primero.")


def comprobar_firma(apk: pathlib.Path) -> None:
	"""
	La misma clave que lo ya publicado. Con otra (la de depuración, o una firma nueva en
	otro equipo) cada móvil bajaría el APK entero para rechazarlo y no se actualizaría nadie.
	La primera publicación guarda la huella para comparar las siguientes.
	"""
	if not APKSIGNER.exists():
		print("[AVISO] Sin apksigner no se puede comprobar la firma.")
		return
	salida = subprocess.run([str(APKSIGNER), "verify", "--print-certs", str(apk)], capture_output=True, text=True, errors="replace").stdout
	datos = re.search(r"Signer #1 certificate SHA-256 digest: ([0-9a-f]+)", salida)
	if not datos:
		error(f"No se pudo leer la firma de {apk.name}. ¿Está JAVA_HOME?")
	if "CN=Android Debug" in salida:
		error(f"{apk.name} está firmado con la clave de depuración. Falta la carpeta firma: compila con compilar.bat.")
	if not HUELLA.exists():
		HUELLA.write_text(datos.group(1) + "\n", encoding="utf-8")
		print(f"[OK] Primera publicación: huella de la firma guardada en {HUELLA.name}.")
		return
	if datos.group(1) != HUELLA.read_text(encoding="utf-8").strip():
		error(f"{apk.name} no está firmado con la clave de las versiones publicadas (carpeta firma). No se publica.")


def novedades(version: str) -> str:
	"""Texto de la sección «## <versión>» de novedades.md."""
	if not NOVEDADES.exists():
		return ""
	secciones = re.split(r"^##\s*(\S+)\s*$", NOVEDADES.read_text(encoding="utf-8"), flags=re.MULTILINE)
	for i in range(1, len(secciones) - 1, 2):
		if secciones[i] == version:
			return secciones[i + 1].strip()
	print(f"[AVISO] novedades.md no tiene la sección «## {version}»: se publica sin novedades.")
	return ""


def main() -> None:
	argumentos = argparse.ArgumentParser(description="Prepara la actualización de Android para el servidor.")
	argumentos.add_argument("--apk", type=pathlib.Path, default=APK, help="APK compilado (por defecto NoMeSubasLosPrecios.apk)")
	argumentos.add_argument("--dist", type=pathlib.Path, default=DIST, help="Carpeta de salida (por defecto dist)")
	opciones = argumentos.parse_args()
	apk, dist = opciones.apk, opciones.dist
	if not apk.exists():
		error(f"No existe {apk}. Compila primero.")
	version, codigo = version_del_proyecto()
	comprobar_apk(apk, version, codigo)
	comprobar_firma(apk)
	dist.mkdir(parents=True, exist_ok=True)
	nombre = f"NoMeSubasLosPrecios_v{version}.apk"
	destino = dist / nombre
	shutil.copy2(apk, destino)
	resumen = hashlib.sha256()
	with destino.open("rb") as archivo:
		for bloque in iter(lambda: archivo.read(1024 * 1024), b""):
			resumen.update(bloque)
	manifiesto = {
		"version": version,
		"versionCode": codigo,
		"file": nombre,
		"sha256": resumen.hexdigest(),
		"size": destino.stat().st_size,
		"date": datetime.date.today().isoformat(),
		"notas": novedades(version),
	}
	(dist / "version.json").write_text(json.dumps(manifiesto, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
	print(f"[OK] Actualización de Android {version} lista en {dist}:")
	print(f"     {nombre} ({manifiesto['size']:,} bytes)".replace(",", "."))
	print("     version.json")


if __name__ == "__main__":
	main()
