# Prepara un entorno portatil para compilar apps Android (plantilla del agente
# entorno-android-portable).
#
# Deja dentro de la carpeta "entorno" del proyecto, sin instalar nada en el sistema:
#   - jdk          JDK 17 (Eclipse Temurin)
#   - android-sdk  cmdline-tools, platform-tools (adb), plataforma y build-tools
#   - gradle       Gradle (distribucion binaria)
#   - gradle-home  cache de Gradle (GRADLE_USER_HOME), se llena al compilar
#   - python       Python portatil (opcional: -ConPython; Chaquopy o apps de escritorio)
#   - avd          emulador "pruebas" (opcional: -ConEmulador)
#
# Con -Origen <carpeta entorno de otro proyecto> copia lo que ya exista alli en vez
# de descargarlo (mucho mas rapido). Lo que falte despues se descarga.
# Con -Simular solo dice lo que haria, sin descargar, copiar ni crear nada.
#
# Al instalar el SDK se ACEPTAN las licencias del Android SDK de Google.
# Es idempotente: lo que ya esta no se vuelve a descargar ni a copiar.
# Sin tildes a proposito: PowerShell 5.1 lee los .ps1 sin BOM como ANSI.

param(
	[string]$Raiz = "",
	[string]$Origen = "",
	[switch]$ConPython,
	[switch]$ConEmulador,
	[switch]$SinCacheGradle,
	[switch]$Simular,
	[int]$Api = 35,
	[string]$BuildTools = "35.0.0",
	[string]$GradleVersion = "8.11.1",
	[string]$PythonVersion = "3.13.16",
	[string]$JdkUrl = "https://github.com/adoptium/temurin17-binaries/releases/download/jdk-17.0.20.1%2B1/OpenJDK17U-jdk_x64_windows_hotspot_17.0.20.1_1.zip",
	[string]$SdkToolsUrl = "https://dl.google.com/android/repository/commandlinetools-win-16111833_latest.zip",
	[string]$NombreAvd = "pruebas"
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

if (-not $Raiz) { $Raiz = Split-Path -Parent $PSScriptRoot }
$Raiz = (Resolve-Path $Raiz).Path
$Entorno = Join-Path $Raiz "entorno"
$Descargas = Join-Path $Entorno "descargas"
$Jdk = Join-Path $Entorno "jdk"
$Gradle = Join-Path $Entorno "gradle"
$GradleHome = Join-Path $Entorno "gradle-home"
$Python = Join-Path $Entorno "python"
$Sdk = Join-Path $Entorno "android-sdk"
$Avd = Join-Path $Entorno "avd"
$SdkManager = Join-Path $Sdk "cmdline-tools\latest\bin\sdkmanager.bat"
$AvdManager = Join-Path $Sdk "cmdline-tools\latest\bin\avdmanager.bat"
$ImagenSistema = "system-images;android-$Api;google_apis;x86_64"
$PaquetesSdk = @("platform-tools", "platforms;android-$Api", "build-tools;$BuildTools")
if ($ConEmulador) { $PaquetesSdk += @("emulator", $ImagenSistema) }

function Paso($texto) { Write-Host ""; Write-Host "==> $texto" }
function Nota($texto) { Write-Host "    $texto" }

if ($Simular) { Paso "Modo simulacion: no se descarga, copia ni crea nada" }
if (-not $Simular) { New-Item -ItemType Directory -Force $Entorno, $Descargas | Out-Null }

# --- Copia desde otro entorno --------------------------------------------------
# robocopy copia en paralelo y conserva lo que ya hay; sus codigos menores que 8 son exito.
function Copiar($origenCarpeta, $destinoCarpeta, [string[]]$excluir = @()) {
	if ($Simular) { Nota "Copiaria $origenCarpeta en $destinoCarpeta"; return }
	Nota "Copiando $(Split-Path -Leaf $origenCarpeta)... (puede tardar varios minutos)"
	$argumentos = @($origenCarpeta, $destinoCarpeta, "/E", "/MT:16", "/R:2", "/W:2", "/NFL", "/NDL", "/NJH", "/NJS", "/NP")
	if ($excluir.Count -gt 0) { $argumentos += "/XD"; $argumentos += $excluir }
	& robocopy @argumentos | Out-Null
	if ($LASTEXITCODE -ge 8) { throw "robocopy fallo copiando $origenCarpeta (codigo $LASTEXITCODE)" }
	$global:LASTEXITCODE = 0
}

if ($Origen) {
	$Origen = (Resolve-Path $Origen).Path
	Paso "Copiando desde $Origen lo que falte"
	if ((Test-Path (Join-Path $Origen "jdk\bin\java.exe")) -and -not (Test-Path (Join-Path $Jdk "bin\java.exe"))) {
		Copiar (Join-Path $Origen "jdk") $Jdk
	}
	if ((Test-Path (Join-Path $Origen "gradle\bin\gradle.bat")) -and -not (Test-Path (Join-Path $Gradle "bin\gradle.bat"))) {
		Copiar (Join-Path $Origen "gradle") $Gradle
	}
	if ($ConPython -and (Test-Path (Join-Path $Origen "python\python.exe")) -and -not (Test-Path (Join-Path $Python "python.exe"))) {
		Copiar (Join-Path $Origen "python") $Python @("__pycache__")
	}
	if (Test-Path (Join-Path $Origen "android-sdk\cmdline-tools")) {
		# Sin emulador no hacen falta ni el emulador ni las imagenes de sistema (varios GB)
		$excluir = @()
		if (-not $ConEmulador) { $excluir = @((Join-Path $Origen "android-sdk\emulator"), (Join-Path $Origen "android-sdk\system-images")) }
		Copiar (Join-Path $Origen "android-sdk") $Sdk $excluir
	}
	if (-not $SinCacheGradle -and (Test-Path (Join-Path $Origen "gradle-home\caches"))) {
		# La cache evita volver a bajar las dependencias; los demonios y bloqueos no se copian
		Copiar (Join-Path $Origen "gradle-home") $GradleHome @((Join-Path $Origen "gradle-home\daemon"), (Join-Path $Origen "gradle-home\native"))
	}
	# Los AVD no se copian: su .ini apunta a la carpeta del otro proyecto. Se crean con -ConEmulador.
}

# --- Descargas -----------------------------------------------------------------
function Descargar($url, $destino) {
	if (Test-Path $destino) { Nota "Ya descargado: $(Split-Path -Leaf $destino)"; return }
	if ($Simular) { Nota "Descargaria $url"; return }
	Nota "Descargando $(Split-Path -Leaf $destino)..."
	$temporal = "$destino.parcial"
	for ($intento = 1; $intento -le 3; $intento++) {
		try {
			Invoke-WebRequest -Uri $url -OutFile $temporal -UseBasicParsing
			Move-Item -Force $temporal $destino
			return
		} catch {
			if ($intento -eq 3) { throw "No se pudo descargar $url : $_" }
			Start-Sleep -Seconds (5 * $intento)
		}
	}
}

function Extraer($zip, $destino) {
	if ($Simular) { Nota "Extraeria $(Split-Path -Leaf $zip) en $destino"; return }
	$temporal = "$destino.tmp"
	if (Test-Path $temporal) { Remove-Item -Recurse -Force $temporal }
	Expand-Archive -Path $zip -DestinationPath $temporal -Force
	# Si el zip contiene una unica carpeta, se usa su contenido
	$hijos = @(Get-ChildItem $temporal)
	if ($hijos.Count -eq 1 -and $hijos[0].PSIsContainer) {
		Move-Item $hijos[0].FullName $destino
		Remove-Item -Recurse -Force $temporal
	} else {
		Move-Item $temporal $destino
	}
}

# --- JDK -----------------------------------------------------------------------
if (-not (Test-Path (Join-Path $Jdk "bin\java.exe"))) {
	Paso "JDK 17"
	$zip = Join-Path $Descargas "jdk17.zip"
	Descargar $JdkUrl $zip
	Extraer $zip $Jdk
} else { Paso "JDK ya instalado" }

# --- Gradle --------------------------------------------------------------------
if (-not (Test-Path (Join-Path $Gradle "bin\gradle.bat"))) {
	Paso "Gradle $GradleVersion"
	$zip = Join-Path $Descargas "gradle-$GradleVersion-bin.zip"
	Descargar "https://services.gradle.org/distributions/gradle-$GradleVersion-bin.zip" $zip
	Extraer $zip $Gradle
} else { Paso "Gradle ya instalado" }

# --- Python portatil (opcional) --------------------------------------------------
if ($ConPython) {
	if (-not (Test-Path (Join-Path $Python "python.exe"))) {
		Paso "Python $PythonVersion portatil"
		# El paquete NuGet "python" es un Python completo (con venv y pip) que no toca el registro
		$nupkg = Join-Path $Descargas "python.$PythonVersion.zip"
		Descargar "https://api.nuget.org/v3-flatcontainer/python/$PythonVersion/python.$PythonVersion.nupkg" $nupkg
		if (-not $Simular) {
			$temporal = Join-Path $Entorno "python_nupkg"
			if (Test-Path $temporal) { Remove-Item -Recurse -Force $temporal }
			Expand-Archive -Path $nupkg -DestinationPath $temporal -Force
			Move-Item (Join-Path $temporal "tools") $Python
			Remove-Item -Recurse -Force $temporal
			& (Join-Path $Python "python.exe") -m ensurepip --upgrade | Out-Null
		}
	} else { Paso "Python portatil ya instalado" }
}

# --- Android SDK ---------------------------------------------------------------
if (-not (Test-Path $SdkManager)) {
	Paso "Android SDK command-line tools"
	$zip = Join-Path $Descargas "commandlinetools.zip"
	Descargar $SdkToolsUrl $zip
	if (-not $Simular) {
		$destino = Join-Path $Sdk "cmdline-tools"
		New-Item -ItemType Directory -Force $destino | Out-Null
		$temporal = Join-Path $destino "tmp"
		if (Test-Path $temporal) { Remove-Item -Recurse -Force $temporal }
		Expand-Archive -Path $zip -DestinationPath $temporal -Force
		Move-Item (Join-Path $temporal "cmdline-tools") (Join-Path $destino "latest")
		Remove-Item -Recurse -Force $temporal
	}
}

$env:JAVA_HOME = $Jdk
$env:ANDROID_HOME = $Sdk
$env:ANDROID_SDK_ROOT = $Sdk
$env:ANDROID_AVD_HOME = $Avd
$env:Path = "$Jdk\bin;$env:Path"

$faltan = @($PaquetesSdk | Where-Object {
	-not (Test-Path (Join-Path $Sdk ($_ -replace ";", "\")))
})
if ($faltan.Count -gt 0) {
	Paso "Paquetes del SDK que faltan: $($faltan -join ', ')"
	if ($Simular) {
		Nota "Aceptaria las licencias del Android SDK e instalaria esos paquetes con sdkmanager"
	} else {
		$respuestas = ("y`n" * 30)
		$respuestas | & $SdkManager --sdk_root="$Sdk" --licenses | Out-Null
		# Entre comillas: cmd.exe trata ";" como separador de argumentos
		$argumentos = @($faltan | ForEach-Object { '"' + $_ + '"' })
		$respuestas | & $SdkManager --sdk_root="$Sdk" @argumentos
		if ($LASTEXITCODE -ne 0) { throw "sdkmanager fallo con codigo $LASTEXITCODE" }
	}
} else { Paso "Paquetes del Android SDK ya instalados" }

# --- Emulador (opcional) -------------------------------------------------------
if ($ConEmulador) {
	if (-not (Test-Path (Join-Path $Avd "$NombreAvd.ini"))) {
		Paso "Creando el emulador $NombreAvd ($ImagenSistema)"
		if (-not $Simular) {
			New-Item -ItemType Directory -Force $Avd | Out-Null
			"no" | & $AvdManager create avd -n $NombreAvd -k $ImagenSistema -d pixel_6 --force | Out-Null
			if ($LASTEXITCODE -ne 0) { throw "avdmanager fallo con codigo $LASTEXITCODE" }
		}
	} else { Paso "Emulador $NombreAvd ya creado" }
}

# --- Resumen -------------------------------------------------------------------
if (-not $Simular) {
	New-Item -ItemType Directory -Force $GradleHome | Out-Null
	@(
		"Entorno preparado el $(Get-Date -Format 'yyyy-MM-dd HH:mm')",
		"JDK: $Jdk",
		"Gradle: $GradleVersion",
		"Android SDK: plataforma android-$Api, build-tools $BuildTools",
		"Python portatil: $(if (Test-Path (Join-Path $Python 'python.exe')) { $PythonVersion } else { 'no' })",
		"Emulador: $(if (Test-Path (Join-Path $Avd "$NombreAvd.ini")) { $NombreAvd } else { 'no' })"
	) | Set-Content -Encoding UTF8 (Join-Path $Entorno "versiones.txt")
}
Paso "Entorno listo en $Entorno"
exit 0
