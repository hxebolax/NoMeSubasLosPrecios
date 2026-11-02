"""«Iniciar con Windows»: acceso directo en la carpeta Inicio del usuario.

Se usa un acceso directo (``.lnk``) y no el registro de Windows: la app es
portable y el usuario lo ve y lo borra desde el Explorador si quiere. El
acceso directo abre la app con ``--bandeja`` (minimizada en la bandeja).

Se crea con PowerShell y ``WScript.Shell`` (presentes en todo Windows), sin
dependencias. La carpeta Inicio la resuelve el propio PowerShell con
``[Environment]::GetFolderPath('Startup')``: así la app no lee rutas del
perfil por su cuenta.

Sin wx; el ejecutor de PowerShell se puede sustituir en las pruebas.
"""

from __future__ import annotations

import logging
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

from app.core import paths
from app.core.version import NOMBRE_APLICACION

log = logging.getLogger(__name__)

ARGUMENTO_BANDEJA = "--bandeja"
NOMBRE_ACCESO = f"{NOMBRE_APLICACION}.lnk"
TIEMPO_MAXIMO = 30

Ejecutor = Callable[[str], subprocess.CompletedProcess]


class ErrorInicio(Exception):
	"""No se pudo crear o borrar el acceso directo (mensaje para el usuario)."""


def _comillas(texto: str) -> str:
	"""Cadena literal de PowerShell entre comillas simples."""
	return "'" + str(texto).replace("'", "''") + "'"


def _ejecutar_powershell(script: str) -> subprocess.CompletedProcess:
	return subprocess.run(  # noqa: S603 - orden fija, sin datos del usuario sin escapar
		["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", script],
		capture_output=True,
		text=True,
		timeout=TIEMPO_MAXIMO,
		creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
		check=False,
	)


_ejecutor: Ejecutor = _ejecutar_powershell


def establecer_ejecutor(ejecutor: Ejecutor | None) -> None:
	"""Sustituye el ejecutor de PowerShell (pruebas). ``None`` restaura el real."""
	global _ejecutor
	_ejecutor = ejecutor or _ejecutar_powershell


def destino_y_argumentos() -> tuple[str, str, str]:
	"""(programa, argumentos, carpeta de trabajo) que abre la app en la bandeja."""
	carpeta = paths.ruta_base()
	if paths.CONGELADA:
		return str(Path(sys.executable).resolve()), ARGUMENTO_BANDEJA, str(carpeta)
	ejecutable = Path(sys.executable)
	sin_consola = ejecutable.with_name("pythonw.exe")
	programa = sin_consola if sin_consola.is_file() else ejecutable
	return str(programa), f'"{carpeta / "main.py"}" {ARGUMENTO_BANDEJA}', str(carpeta)


def _lanzar(script: str, accion: str) -> str:
	try:
		resultado = _ejecutor(script)
	except (OSError, subprocess.SubprocessError) as error:
		log.exception("No se pudo ejecutar PowerShell para %s", accion)
		raise ErrorInicio(f"No se pudo {accion}: PowerShell no está disponible ({error}).") from error
	if resultado.returncode != 0:
		log.error("PowerShell falló al %s (código %s): %s", accion, resultado.returncode, (resultado.stderr or "").strip()[:500])
		raise ErrorInicio(f"No se pudo {accion}. Los detalles están en el registro.")
	return (resultado.stdout or "").strip()


def activar() -> None:
	"""Crea (o rehace) el acceso directo en la carpeta Inicio."""
	programa, argumentos, carpeta = destino_y_argumentos()
	script = (
		"$ErrorActionPreference = 'Stop'; "
		f"$ruta = Join-Path ([Environment]::GetFolderPath('Startup')) {_comillas(NOMBRE_ACCESO)}; "
		"$acceso = (New-Object -ComObject WScript.Shell).CreateShortcut($ruta); "
		f"$acceso.TargetPath = {_comillas(programa)}; "
		f"$acceso.Arguments = {_comillas(argumentos)}; "
		f"$acceso.WorkingDirectory = {_comillas(carpeta)}; "
		f"$acceso.Description = {_comillas(NOMBRE_APLICACION + ': seguimiento de precios en la bandeja')}; "
		"$acceso.WindowStyle = 7; "
		"$acceso.Save(); Write-Output $ruta"
	)
	ruta = _lanzar(script, "crear el acceso directo de inicio")
	log.info("Acceso directo de inicio creado: %s", ruta)


def desactivar() -> None:
	"""Borra el acceso directo de la carpeta Inicio (si existe)."""
	script = (
		"$ErrorActionPreference = 'Stop'; "
		f"$ruta = Join-Path ([Environment]::GetFolderPath('Startup')) {_comillas(NOMBRE_ACCESO)}; "
		"if (Test-Path -LiteralPath $ruta) { Remove-Item -LiteralPath $ruta -Force; Write-Output 'borrado' }"
	)
	salida = _lanzar(script, "borrar el acceso directo de inicio")
	log.info("Acceso directo de inicio %s", "borrado" if salida else "no existía")


def esta_activado() -> bool:
	"""``True`` si el acceso directo existe."""
	script = (
		f"Test-Path -LiteralPath (Join-Path ([Environment]::GetFolderPath('Startup')) {_comillas(NOMBRE_ACCESO)})"
	)
	try:
		return _lanzar(script, "consultar el acceso directo de inicio").lower() == "true"
	except ErrorInicio:
		return False


def aplicar(activado: bool) -> None:
	"""Deja el acceso directo como pide el ajuste ``iniciar_con_windows``."""
	if activado:
		activar()
	else:
		desactivar()
