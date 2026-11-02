@echo off
rem ============================================================================
rem  compilar.bat - No Me Subas Los Precios para Windows y Android
rem  Compila, prueba, instala y publica las dos aplicaciones. Todo lo necesario
rem  vive en la carpeta "entorno": no se instala nada en el sistema.
rem
rem  Uso con menu:   compilar.bat
rem  Uso sin menu:   compilar.bat todo ^| windows ^| android ^| instalar ^| android-instalar
rem                  ^| ejecutar ^| pruebas ^| emulador ^| dispositivos ^| publicar ^| servidor ^| entorno
rem ============================================================================
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul
title No Me Subas Los Precios - Compilar
cd /d "%~dp0"

set "NOMBRE_APP=NoMeSubasLosPrecios"
set "PAQUETE=com.xebolax.nomesubaslosprecios"
set "RAIZ=%~dp0"
set "RAIZ=%RAIZ:~0,-1%"
set "ANDROID=%RAIZ%\android"
set "WINDOWS=%RAIZ%\windows"
set "JAVA_HOME=%RAIZ%\entorno\jdk"
set "ANDROID_HOME=%RAIZ%\entorno\android-sdk"
set "ANDROID_SDK_ROOT=%ANDROID_HOME%"
set "ANDROID_AVD_HOME=%RAIZ%\entorno\avd"
set "GRADLE_USER_HOME=%RAIZ%\entorno\gradle-home"
set "PATH=%JAVA_HOME%\bin;%ANDROID_HOME%\platform-tools;%PATH%"
set "GRADLE=%RAIZ%\entorno\gradle\bin\gradle.bat"
set "ADB=%ANDROID_HOME%\platform-tools\adb.exe"
set "EMULADOR=%ANDROID_HOME%\emulator\emulator.exe"
set "PYTHON=%RAIZ%\entorno\python\python.exe"
set "APK=%RAIZ%\%NOMBRE_APP%.apk"
set "FIRMA=%RAIZ%\firma"
set "DIST=%RAIZ%\dist"
set "SERVIDOR=%USERPROFILE%\SynologyDrive\web\%NOMBRE_APP%"

if "%~1"=="" goto :menu
if /i "%~1"=="todo" call :todo & exit /b !errorlevel!
if /i "%~1"=="windows" call :windows & exit /b !errorlevel!
if /i "%~1"=="android" call :android & exit /b !errorlevel!
if /i "%~1"=="instalar" call :instalar & exit /b !errorlevel!
if /i "%~1"=="android-instalar" (
	call :android || exit /b 1
	call :instalar
	exit /b !errorlevel!
)
if /i "%~1"=="ejecutar" call :ejecutar & exit /b !errorlevel!
if /i "%~1"=="pruebas" call :pruebas & exit /b !errorlevel!
if /i "%~1"=="emulador" call :emulador & exit /b !errorlevel!
if /i "%~1"=="dispositivos" call :dispositivos & exit /b !errorlevel!
if /i "%~1"=="publicar" call :publicar & exit /b !errorlevel!
if /i "%~1"=="servidor" call :servidor & exit /b !errorlevel!
if /i "%~1"=="entorno" call :preparar & exit /b !errorlevel!
echo Orden desconocida: %~1
exit /b 1

:menu
echo.
echo  No Me Subas Los Precios - Compilar
echo  ==================================
echo  1. Compilar todo (Windows y Android)
echo  2. Compilar la version de Windows (ZIP)
echo  3. Compilar la version de Android (APK firmado)
echo  4. Compilar Android e instalar en el movil conectado
echo  5. Instalar en el movil el APK ya compilado
echo  6. Ejecutar la version de Windows desde el codigo
echo  7. Pasar todas las pruebas
echo  8. Abrir el emulador de Android
echo  9. Ver los moviles conectados
echo  10. Preparar las actualizaciones (carpeta dist)
echo  11. Preparar y copiar las actualizaciones al servidor
echo  12. Preparar o reparar el entorno
echo  0. Salir
echo.
set "OPCION="
set /p "OPCION=Elige una opcion y pulsa Intro: "
if "%OPCION%"=="1" call :todo & goto :pausa
if "%OPCION%"=="2" call :windows & goto :pausa
if "%OPCION%"=="3" call :android & goto :pausa
if "%OPCION%"=="4" (
	call :android && call :instalar
	goto :pausa
)
if "%OPCION%"=="5" call :instalar & goto :pausa
if "%OPCION%"=="6" call :ejecutar & goto :pausa
if "%OPCION%"=="7" call :pruebas & goto :pausa
if "%OPCION%"=="8" call :emulador & goto :pausa
if "%OPCION%"=="9" call :dispositivos & goto :pausa
if "%OPCION%"=="10" call :publicar & goto :pausa
if "%OPCION%"=="11" call :servidor & goto :pausa
if "%OPCION%"=="12" call :preparar & goto :pausa
if "%OPCION%"=="0" exit /b 0
echo Opcion no valida.
goto :menu

:pausa
echo.
pause
goto :menu

rem -----------------------------------------------------------------------------
:todo
call :windows || exit /b 1
call :android || exit /b 1
echo.
echo [OK] Las dos versiones estan compiladas.
exit /b 0

rem -----------------------------------------------------------------------------
rem Entorno: JDK, Android SDK, Gradle y Python portatil (agente entorno-android-portable).
:entorno
if exist "%JAVA_HOME%\bin\java.exe" if exist "%GRADLE%" if exist "%ANDROID_HOME%\platforms\android-35" if exist "%PYTHON%" exit /b 0
echo.
echo [Entorno] Falta el entorno de compilacion. Se preparara en la carpeta "entorno":
echo           JDK 17, Android SDK, Gradle y Python 3.13 (unos 1,5 GB la primera vez).
echo           Al instalar el Android SDK se aceptan sus licencias de Google.
:preparar
set "ORIGEN="
set /p "ORIGEN=Carpeta entorno de otro proyecto para copiarla (Intro = descargar): "
if defined ORIGEN (
	powershell -NoProfile -ExecutionPolicy Bypass -File "%RAIZ%\herramientas\preparar_entorno.ps1" -ConPython -Origen "!ORIGEN!"
) else (
	powershell -NoProfile -ExecutionPolicy Bypass -File "%RAIZ%\herramientas\preparar_entorno.ps1" -ConPython
)
if errorlevel 1 (
	echo [ERROR] No se pudo preparar el entorno.
	exit /b 1
)
exit /b 0

rem -----------------------------------------------------------------------------
rem Windows: lo hace windows\entorno.bat (entorno virtual con el Python portatil,
rem pruebas, cx_Freeze con los runtimes de Visual C++, verificacion y ZIP).
:windows
call :entorno || exit /b 1
echo.
echo [Windows] Compilando la version de Windows...
call "%WINDOWS%\entorno.bat" compilar
if errorlevel 1 (
	echo [ERROR] La compilacion de Windows ha fallado.
	exit /b 1
)
echo [OK] Version de Windows compilada (ZIP en windows\dist).
exit /b 0

:ejecutar
call :entorno || exit /b 1
call "%WINDOWS%\entorno.bat" ejecutar
exit /b %errorlevel%

rem -----------------------------------------------------------------------------
rem Firma propia de Android: sin ella no se puede actualizar la app sin desinstalarla.
:firma
if exist "%FIRMA%\firma.properties" exit /b 0
echo.
echo [Firma] Creando la firma propia de la app de Android (firma\nomesubas.jks).
echo         GUARDALA APARTE: sin ella no podras actualizar la app sin desinstalarla.
if not exist "%FIRMA%" mkdir "%FIRMA%"
for /f %%c in ('powershell -NoProfile -Command "-join ((48..57)+(65..90)+(97..122) | Get-Random -Count 24 | ForEach-Object {[char]$_})"') do set "CLAVE=%%c"
"%JAVA_HOME%\bin\keytool.exe" -genkeypair -keystore "%FIRMA%\nomesubas.jks" -alias nomesubas -keyalg RSA -keysize 2048 -validity 10000 -storepass !CLAVE! -keypass !CLAVE! -dname "CN=No Me Subas Los Precios, O=XeBoLaX, C=ES" >nul 2>&1
if errorlevel 1 (
	echo [ERROR] No se pudo crear la firma.
	exit /b 1
)
(
	echo archivo=firma/nomesubas.jks
	echo alias=nomesubas
	echo clave=!CLAVE!
) > "%FIRMA%\firma.properties"
exit /b 0

:android
call :entorno || exit /b 1
call :firma || exit /b 1
echo.
echo [Android] Compilando el APK firmado. La primera vez tarda varios minutos...
call "%GRADLE%" --no-daemon -p "%ANDROID%" assembleRelease
if errorlevel 1 (
	echo [ERROR] La compilacion de Android ha fallado. Revisa los mensajes de arriba.
	exit /b 1
)
copy /y "%ANDROID%\app\build\outputs\apk\release\app-release.apk" "%APK%" >nul
echo [OK] APK listo: %APK%
exit /b 0

rem -----------------------------------------------------------------------------
:pruebas
call :entorno || exit /b 1
set "FALLOS=0"
echo.
echo [Pruebas] Windows...
call "%WINDOWS%\entorno.bat" pruebas
if errorlevel 1 set "FALLOS=1"
echo.
echo [Pruebas] Android...
call "%GRADLE%" --no-daemon -p "%ANDROID%" testDebugUnitTest
if errorlevel 1 set "FALLOS=1"
if "%FALLOS%"=="1" (
	echo [ERROR] Alguna prueba ha fallado. Revisa los mensajes de arriba.
	exit /b 1
)
echo [OK] Todas las pruebas han pasado.
exit /b 0

rem -----------------------------------------------------------------------------
:emulador
if not exist "%EMULADOR%" (
	echo [AVISO] El emulador no esta instalado. Preparalo con:
	echo         powershell -File herramientas\preparar_entorno.ps1 -ConEmulador
	exit /b 1
)
start "" "%EMULADOR%" -avd pruebas -gpu swiftshader_indirect
echo [OK] Emulador abriendose.
exit /b 0

:dispositivos
if not exist "%ADB%" call :entorno || exit /b 1
"%ADB%" start-server >nul 2>&1
"%ADB%" devices -l
exit /b 0

:instalar
if not exist "%APK%" (
	echo [ERROR] No existe %APK%. Compila primero.
	exit /b 1
)
if not exist "%ADB%" call :entorno || exit /b 1
"%ADB%" start-server >nul 2>&1
set "DISPOSITIVOS=0"
for /f "skip=1 tokens=1,2" %%a in ('call "%ADB%" devices') do (
	if "%%b"=="device" set /a DISPOSITIVOS+=1
	if "%%b"=="unauthorized" echo [AVISO] El movil %%a no ha autorizado la depuracion USB: acepta el aviso en su pantalla.
)
if "%DISPOSITIVOS%"=="0" (
	echo [AVISO] No hay ningun movil conectado y autorizado.
	echo         1. Activa las Opciones de desarrollador y la Depuracion USB.
	echo         2. Conecta el movil por USB y acepta el aviso de depuracion.
	echo         Tambien puedes copiar %NOMBRE_APP%.apk al movil e instalarlo a mano.
	exit /b 1
)
echo [Instalar] Instalando No Me Subas Los Precios en el movil...
"%ADB%" -d install -r "%APK%" > "%TEMP%\%NOMBRE_APP%_adb.txt" 2>&1
type "%TEMP%\%NOMBRE_APP%_adb.txt"
findstr /c:"Success" "%TEMP%\%NOMBRE_APP%_adb.txt" >nul
if not errorlevel 1 (
	echo [OK] Instalada. Abriendola...
	"%ADB%" -d shell monkey -p %PAQUETE% -c android.intent.category.LAUNCHER 1 >nul 2>&1
	exit /b 0
)
findstr /c:"INSTALL_FAILED_UPDATE_INCOMPATIBLE" "%TEMP%\%NOMBRE_APP%_adb.txt" >nul
if not errorlevel 1 (
	echo [AVISO] Hay otra No Me Subas Los Precios instalada con una firma distinta.
	set "RESPUESTA="
	set /p "RESPUESTA=Desinstalarla (se borran sus datos) e instalar esta? (s/n): "
	if /i "!RESPUESTA!"=="s" (
		"%ADB%" -d uninstall %PAQUETE%
		"%ADB%" -d install "%APK%"
		exit /b !errorlevel!
	)
)
echo [ERROR] No se pudo instalar.
exit /b 1

rem -----------------------------------------------------------------------------
rem Deja en dist lo que se sube al servidor: el APK y su version.json, y en
rem dist\windows el ZIP y el version.json firmado de Windows.
:publicar
call :android || exit /b 1
"%PYTHON%" "%RAIZ%\herramientas\publicar_android.py" || exit /b 1
call "%WINDOWS%\entorno.bat" publicar
if errorlevel 1 (
	echo [ERROR] No se pudo preparar la actualizacion de Windows.
	exit /b 1
)
if not exist "%DIST%\windows" mkdir "%DIST%\windows"
copy /y "%WINDOWS%\dist\%NOMBRE_APP%-*-win64.zip" "%DIST%\windows\" >nul
copy /y "%WINDOWS%\dist\version.json" "%DIST%\windows\" >nul
echo [OK] Actualizaciones listas en %DIST%
exit /b 0

rem Primero los paquetes y despues los version.json: asi nadie ve una version
rem cuyo archivo aun no ha llegado.
:servidor
call :publicar || exit /b 1
if not exist "%SERVIDOR%" (
	echo [ERROR] No existe la carpeta %SERVIDOR%
	exit /b 1
)
if not exist "%SERVIDOR%\windows" mkdir "%SERVIDOR%\windows"
copy /y "%DIST%\%NOMBRE_APP%_v*.apk" "%SERVIDOR%\" >nul
copy /y "%DIST%\windows\%NOMBRE_APP%-*-win64.zip" "%SERVIDOR%\windows\" >nul
copy /y "%DIST%\version.json" "%SERVIDOR%\" >nul
copy /y "%DIST%\windows\version.json" "%SERVIDOR%\windows\" >nul
echo [OK] Actualizaciones copiadas en %SERVIDOR%
exit /b 0
