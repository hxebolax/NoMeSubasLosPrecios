@echo off
rem ============================================================================
rem  entorno.bat - Administración de No Me Subas Los Precios (Windows)
rem  Crea el entorno virtual, instala dependencias, copia los recursos comunes,
rem  ejecuta desde código, pasa las pruebas, compila con cx_Freeze (con los
rem  runtimes de Visual C++), empaqueta y prepara la publicación firmada.
rem
rem  Uso con menú:        entorno.bat
rem  Uso sin menú:        entorno.bat <orden>
rem  Órdenes: crear, instalar, actualizar, recursos, ejecutar, depurar, pruebas,
rem           comprobar, compilar, compilar-debug, empaquetar, publicar,
rem           auditoria, limpiar, datos, registros, diagnostico, congelar
rem
rem  Basado en la plantilla del agente «entorno-virtual». Guardado con finales
rem  de línea CRLF y codificación UTF-8 SIN BOM.
rem ============================================================================
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul
cd /d "%~dp0"

rem ── Configuración ──────────────────────────────────────────────────────────
set "NOMBRE_APP=NoMeSubasLosPrecios"
rem Python portátil del proyecto; si no existe, el lanzador py con esta versión.
set "PY_PORTABLE=%~dp0..\entorno\python\python.exe"
set "VERSION_PY=3.13"
set "VENV=%~dp0.venv"
set "PY=%VENV%\Scripts\python.exe"
set "PYW=%VENV%\Scripts\pythonw.exe"
set "SETUP=setup_cx.py"
set "BUILD_DIR=build\%NOMBRE_APP%"
rem Recursos comunes con la app de Android (tiendas.json, manual, novedades).
set "RECURSOS_ORIGEN=%~dp0..\compartido\recursos"
set "RECURSOS_DESTINO=%~dp0data\recursos"
rem Vacío salvo en «publicar», que firma version.json al empaquetar.
set "FIRMAR="
rem ──────────────────────────────────────────────────────────────────────────

if not "%~1"=="" goto ORDEN

:MENU
echo.
echo  %NOMBRE_APP% - Menú de administración
echo  ==============================================
echo  1. Crear o reparar el entorno virtual e instalar dependencias
echo  2. Instalar dependencias (requirements)
echo  3. Actualizar dependencias a la última versión permitida
echo  4. Ejecutar la aplicación desde el código
echo  5. Ejecutar desde el código con consola (depuración)
echo  6. Ejecutar las pruebas
echo  7. Compilar con cx_Freeze y empaquetar en ZIP
echo  8. Publicar: compilar, empaquetar y firmar version.json en dist
echo  9. Compilar en modo depuración (con consola)
echo  10. Comprobar el arranque desde el código
echo  11. Copiar los recursos comunes a data\recursos
echo  12. Auditoría automática del código
echo  13. Limpiar compilaciones y cachés
echo  14. Abrir la carpeta data
echo  15. Abrir la carpeta de registros
echo  16. Diagnóstico del entorno
echo  17. Guardar las versiones instaladas (requirements-lock.txt)
echo  0. Salir
echo.
set "OPCION="
set /p "OPCION=Elija una opción y pulse Intro: "
if "%OPCION%"=="1" call :CREAR & goto PAUSA
if "%OPCION%"=="2" call :INSTALAR & goto PAUSA
if "%OPCION%"=="3" call :ACTUALIZAR & goto PAUSA
if "%OPCION%"=="4" call :EJECUTAR & goto PAUSA
if "%OPCION%"=="5" call :DEPURAR & goto PAUSA
if "%OPCION%"=="6" call :PRUEBAS & goto PAUSA
if "%OPCION%"=="7" call :COMPILAR & goto PAUSA
if "%OPCION%"=="8" call :PUBLICAR & goto PAUSA
if "%OPCION%"=="9" call :COMPILAR_DEBUG & goto PAUSA
if "%OPCION%"=="10" call :COMPROBAR & goto PAUSA
if "%OPCION%"=="11" call :RECURSOS & goto PAUSA
if "%OPCION%"=="12" call :AUDITORIA & goto PAUSA
if "%OPCION%"=="13" call :LIMPIAR & goto PAUSA
if "%OPCION%"=="14" call :DATOS & goto PAUSA
if "%OPCION%"=="15" call :REGISTROS & goto PAUSA
if "%OPCION%"=="16" call :DIAGNOSTICO & goto PAUSA
if "%OPCION%"=="17" call :CONGELAR & goto PAUSA
if "%OPCION%"=="0" goto FIN
echo Opción no válida: %OPCION%
goto MENU

:PAUSA
echo.
pause
goto MENU

:ORDEN
set "ORDEN=%~1"
if /i "%ORDEN%"=="crear" call :CREAR & goto SALIR
if /i "%ORDEN%"=="instalar" call :INSTALAR & goto SALIR
if /i "%ORDEN%"=="actualizar" call :ACTUALIZAR & goto SALIR
if /i "%ORDEN%"=="recursos" call :RECURSOS & goto SALIR
if /i "%ORDEN%"=="ejecutar" call :EJECUTAR & goto SALIR
if /i "%ORDEN%"=="depurar" call :DEPURAR & goto SALIR
if /i "%ORDEN%"=="pruebas" call :PRUEBAS & goto SALIR
if /i "%ORDEN%"=="comprobar" call :COMPROBAR & goto SALIR
if /i "%ORDEN%"=="compilar" call :COMPILAR & goto SALIR
if /i "%ORDEN%"=="compilar-debug" call :COMPILAR_DEBUG & goto SALIR
if /i "%ORDEN%"=="empaquetar" call :EMPAQUETAR & goto SALIR
if /i "%ORDEN%"=="publicar" call :PUBLICAR & goto SALIR
if /i "%ORDEN%"=="auditoria" call :AUDITORIA & goto SALIR
if /i "%ORDEN%"=="limpiar" call :LIMPIAR & goto SALIR
if /i "%ORDEN%"=="datos" call :DATOS & goto SALIR
if /i "%ORDEN%"=="registros" call :REGISTROS & goto SALIR
if /i "%ORDEN%"=="diagnostico" call :DIAGNOSTICO & goto SALIR
if /i "%ORDEN%"=="congelar" call :CONGELAR & goto SALIR
echo Orden desconocida: %ORDEN%
echo Órdenes válidas: crear, instalar, actualizar, recursos, ejecutar, depurar, pruebas, comprobar,
echo compilar, compilar-debug, empaquetar, publicar, auditoria, limpiar, datos, registros,
echo diagnostico, congelar
exit /b 2

:SALIR
exit /b %ERRORLEVEL%

rem ============================================================================
rem  Subrutinas. Cada una termina con "exit /b <código>" (0 = correcto).
rem ============================================================================

:CREAR
echo.
echo === Creando el entorno virtual en %VENV% ===
if exist "%PY%" (
	echo El entorno virtual ya existe; se reutiliza.
	goto CREAR_INSTALAR
)
if exist "%PY_PORTABLE%" (
	echo Se usa el Python portátil del proyecto: %PY_PORTABLE%
	"%PY_PORTABLE%" -m venv "%VENV%"
	goto CREAR_COMPROBAR
)
where py >nul 2>nul
if errorlevel 1 goto CREAR_SIN_PY
echo No está el Python portátil; se usa el lanzador: py -%VERSION_PY%
py -%VERSION_PY% -m venv "%VENV%"
if errorlevel 1 (
	echo ERROR: no está instalado Python %VERSION_PY%. Instálelo con: py install %VERSION_PY%
	echo o prepare el Python portátil en ..\entorno\python, y vuelva a intentarlo.
	exit /b 1
)
goto CREAR_COMPROBAR

:CREAR_SIN_PY
echo ERROR: no hay Python portátil en ..\entorno\python ni lanzador py.
echo Instale Python %VERSION_PY% de 64 bits desde python.org y vuelva a intentarlo.
exit /b 1

:CREAR_COMPROBAR
if not exist "%PY%" (
	echo ERROR: no se pudo crear el entorno virtual.
	exit /b 1
)

:CREAR_INSTALAR
"%PY%" --version
call :INSTALAR
exit /b %ERRORLEVEL%

:INSTALAR
echo.
echo === Instalando dependencias ===
call :COMPROBAR_VENV || exit /b 1
"%PY%" -m pip install --upgrade pip setuptools wheel
if exist requirements.txt (
	"%PY%" -m pip install -r requirements.txt
	if errorlevel 1 (
		echo ERROR: falló la instalación de requirements.txt.
		exit /b 1
	)
)
if exist requirements-dev.txt (
	"%PY%" -m pip install -r requirements-dev.txt
	if errorlevel 1 (
		echo ERROR: falló la instalación de requirements-dev.txt.
		exit /b 1
	)
)
echo Dependencias instaladas correctamente.
exit /b 0

:ACTUALIZAR
echo.
echo === Actualizando dependencias ===
call :COMPROBAR_VENV || exit /b 1
"%PY%" -m pip install --upgrade pip
if exist requirements.txt "%PY%" -m pip install --upgrade -r requirements.txt || exit /b 1
if exist requirements-dev.txt "%PY%" -m pip install --upgrade -r requirements-dev.txt || exit /b 1
echo Dependencias actualizadas.
exit /b 0

:RECURSOS
rem Copia tiendas.json, manual.md y novedades.md de ..\compartido\recursos.
if not exist "%RECURSOS_ORIGEN%" (
	if exist "%RECURSOS_DESTINO%\tiendas.json" (
		echo Aviso: no está %RECURSOS_ORIGEN%; se usan los recursos que ya hay en data\recursos.
		exit /b 0
	)
	echo ERROR: no se encuentra %RECURSOS_ORIGEN% ni hay recursos en data\recursos.
	exit /b 1
)
"%SystemRoot%\System32\robocopy.exe" "%RECURSOS_ORIGEN%" "%RECURSOS_DESTINO%" /E /R:2 /W:1 /NJH /NJS /NFL /NDL /NP >nul
if errorlevel 8 (
	echo ERROR: no se pudieron copiar los recursos comunes a data\recursos.
	exit /b 1
)
echo Recursos comunes copiados a data\recursos.
exit /b 0

:EJECUTAR
echo.
echo === Ejecutando %NOMBRE_APP% desde el código ===
call :COMPROBAR_VENV || exit /b 1
call :RECURSOS || exit /b 1
start "" "%PYW%" main.py
exit /b 0

:DEPURAR
echo.
echo === Ejecutando %NOMBRE_APP% con consola (depuración) ===
call :COMPROBAR_VENV || exit /b 1
call :RECURSOS || exit /b 1
set "APP_DEPURACION=1"
"%PY%" -X dev -X faulthandler main.py
set "CODIGO=!ERRORLEVEL!"
set "APP_DEPURACION="
echo La aplicación terminó con el código !CODIGO!.
exit /b !CODIGO!

:PRUEBAS
echo.
echo === Ejecutando las pruebas ===
call :COMPROBAR_VENV || exit /b 1
call :RECURSOS || exit /b 1
"%PY%" -m pytest tests -q
if errorlevel 1 (
	echo Hay pruebas que fallan.
	exit /b 1
)
echo Todas las pruebas pasan.
exit /b 0

:COMPROBAR
echo.
echo === Comprobando el arranque desde el código ===
call :COMPROBAR_VENV || exit /b 1
call :RECURSOS || exit /b 1
"%PY%" main.py --comprobar-arranque
if errorlevel 1 (
	echo ERROR: la aplicación no arranca. Revise data\logs.
	exit /b 1
)
echo Arranque correcto.
exit /b 0

:COMPILAR
echo.
echo === Compilando %NOMBRE_APP% con cx_Freeze ===
call :COMPROBAR_VENV || exit /b 1
call :RECURSOS || exit /b 1
if not exist "%SETUP%" (
	echo ERROR: no existe %SETUP% en la raíz del proyecto.
	exit /b 1
)
"%PY%" "%SETUP%" build
if errorlevel 1 (
	echo ERROR: la compilación ha fallado. Revise los mensajes anteriores.
	exit /b 1
)
if not exist "%BUILD_DIR%\%NOMBRE_APP%.exe" (
	echo ERROR: no se generó %BUILD_DIR%\%NOMBRE_APP%.exe.
	exit /b 1
)
call :EMPAQUETAR
exit /b %ERRORLEVEL%

:COMPILAR_DEBUG
echo.
echo === Compilando %NOMBRE_APP% en modo depuración (con consola) ===
call :COMPROBAR_VENV || exit /b 1
call :RECURSOS || exit /b 1
"%PY%" "%SETUP%" build --debug
if errorlevel 1 (
	echo ERROR: la compilación ha fallado.
	exit /b 1
)
echo Compilación de depuración en %BUILD_DIR%. No la distribuya: muestra consola.
exit /b 0

:EMPAQUETAR
echo.
echo === Empaquetando la distribución (ZIP y version.json en dist) ===
call :COMPROBAR_VENV || exit /b 1
"%PY%" tools\empaquetar.py %FIRMAR%
if errorlevel 1 (
	echo ERROR: no se pudo empaquetar la distribución.
	exit /b 1
)
exit /b 0

:PUBLICAR
echo.
echo === Publicando: compilar, empaquetar y firmar ===
rem Compila y empaqueta UNA vez, firmando version.json con la clave de ..\firma\windows.
set "FIRMAR=--firmar"
call :COMPILAR
set "CODIGO=!ERRORLEVEL!"
set "FIRMAR="
if not "!CODIGO!"=="0" (
	echo ERROR: no se pudo compilar o firmar. Compruebe la clave en ..\firma\windows.
	exit /b 1
)
echo Listo para publicar: el ZIP y version.json de la carpeta dist.
echo Súbalos a la carpeta windows del servidor: primero el ZIP y después version.json.
exit /b 0

:AUDITORIA
echo.
echo === Auditoría automática del código ===
call :COMPROBAR_VENV || exit /b 1
"%PY%" tools\auditoria_rapida.py --severidad-minima media
exit /b %ERRORLEVEL%

:LIMPIAR
echo.
echo === Limpiando compilaciones y cachés ===
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist .pytest_cache rmdir /s /q .pytest_cache
if exist .ruff_cache rmdir /s /q .ruff_cache
for /d /r . %%D in (__pycache__) do if exist "%%D" (
	set "RUTA=%%D"
	if "!RUTA:\.venv\=!"=="!RUTA!" if "!RUTA:\venv\=!"=="!RUTA!" rmdir /s /q "%%D"
)
echo Limpieza terminada. El entorno virtual y la carpeta data no se tocan.
exit /b 0

:DATOS
if not exist data mkdir data
start "" explorer "%~dp0data"
exit /b 0

:REGISTROS
if not exist data\logs mkdir data\logs
start "" explorer "%~dp0data\logs"
exit /b 0

:DIAGNOSTICO
echo.
echo === Diagnóstico del entorno ===
if exist "%PY_PORTABLE%" (echo Python portátil: %PY_PORTABLE%) else (echo No hay Python portátil en ..\entorno\python.)
where py >nul 2>nul && py -0p
if exist "%PY%" (
	echo Python del entorno virtual:
	"%PY%" -c "import sys, platform; print(sys.version); print(platform.platform())"
	"%PY%" -c "import wx; print('wxPython', wx.version())" 2>nul || echo wxPython no está instalado.
	"%PY%" -c "import cx_Freeze; print('cx_Freeze', cx_Freeze.__version__)" 2>nul || echo cx_Freeze no está instalado.
	"%PY%" -m pip check
) else (
	echo El entorno virtual no existe todavía. Use la opción 1.
)
tasklist /fi "imagename eq nvda.exe" 2>nul | "%SystemRoot%\System32\find.exe" /i "nvda.exe" >nul && echo NVDA está en ejecución. || echo NVDA no está en ejecución.
tasklist /fi "imagename eq jfw.exe" 2>nul | "%SystemRoot%\System32\find.exe" /i "jfw.exe" >nul && echo JAWS está en ejecución. || echo JAWS no está en ejecución.
exit /b 0

:CONGELAR
echo.
echo === Guardando las versiones exactas instaladas ===
call :COMPROBAR_VENV || exit /b 1
"%PY%" -m pip freeze > requirements-lock.txt
echo Versiones guardadas en requirements-lock.txt.
exit /b 0

:COMPROBAR_VENV
if exist "%PY%" exit /b 0
echo El entorno virtual no existe. Ejecute primero: entorno.bat crear
exit /b 1

:FIN
endlocal
exit /b 0
