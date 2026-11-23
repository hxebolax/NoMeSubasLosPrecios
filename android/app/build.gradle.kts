import java.util.Properties

plugins {
	id("com.android.application")
	id("org.jetbrains.kotlin.android")
}

// Servidor de actualizaciones: ahí van version.json y NoMeSubasLosPrecios_v<versión>.apk.
// Para probar con un servidor local: gradle assembleRelease -PurlActualizaciones=http://localhost:8765
val urlActualizaciones = (project.findProperty("urlActualizaciones") as String?) ?: "https://xebolax.synology.me/NoMeSubasLosPrecios"

// Firma propia guardada en la carpeta «firma» de la raíz del repositorio (la crea compilar.bat).
// «archivo» es relativo a esa raíz (p. ej. firma/nomesubas.jks).
val propiedadesFirma = Properties().apply {
	val archivo = rootProject.file("../firma/firma.properties")
	if (archivo.exists()) archivo.inputStream().use { load(it) }
}

// Archivos comunes con la app de Windows
val carpetaCompartida = rootProject.file("../compartido")

android {
	namespace = "com.xebolax.nomesubaslosprecios"
	compileSdk = 35

	defaultConfig {
		applicationId = "com.xebolax.nomesubaslosprecios"
		minSdk = 24
		targetSdk = 35
		versionCode = 3
		versionName = "1.2.0"

		// Prueba de accesibilidad con TalkBack en el emulador (src/androidTest)
		testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"

		buildConfigField("String", "URL_ACTUALIZACIONES", "\"$urlActualizaciones\"")
	}

	signingConfigs {
		if (propiedadesFirma.isNotEmpty()) {
			create("propia") {
				storeFile = rootProject.file("../" + propiedadesFirma.getProperty("archivo"))
				storePassword = propiedadesFirma.getProperty("clave")
				keyAlias = propiedadesFirma.getProperty("alias")
				keyPassword = propiedadesFirma.getProperty("clave")
			}
		}
	}

	buildTypes {
		debug {
			// Versión de pruebas: se instala junto a la normal
			applicationIdSuffix = ".pruebas"
		}
		release {
			isMinifyEnabled = false
			signingConfig = signingConfigs.findByName("propia") ?: signingConfigs.getByName("debug")
		}
	}

	sourceSets {
		getByName("main") {
			// tiendas.json, manual.md y novedades.md, los mismos que usa la app de Windows
			assets.srcDir("../../compartido/recursos")
		}
	}

	compileOptions {
		sourceCompatibility = JavaVersion.VERSION_17
		targetCompatibility = JavaVersion.VERSION_17
	}

	kotlinOptions {
		jvmTarget = "17"
	}

	buildFeatures {
		viewBinding = true
		buildConfig = true
	}

	packaging {
		resources.excludes += listOf("META-INF/*.kotlin_module", "META-INF/AL2.0", "META-INF/LGPL2.1")
	}

	testOptions {
		unitTests {
			isReturnDefaultValues = true
			// Las pruebas JVM leen los vectores comunes de compartido/pruebas y las reglas de compartido/recursos
			all {
				it.systemProperty("pruebas.dir", File(carpetaCompartida, "pruebas").absolutePath)
				it.systemProperty("recursos.dir", File(carpetaCompartida, "recursos").absolutePath)
			}
		}
	}
}

dependencies {
	implementation("androidx.core:core-ktx:1.15.0")
	implementation("androidx.appcompat:appcompat:1.7.0")
	implementation("androidx.activity:activity-ktx:1.9.3")
	implementation("androidx.fragment:fragment-ktx:1.8.5")
	implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.8.7")
	implementation("androidx.recyclerview:recyclerview:1.3.2")
	implementation("androidx.preference:preference-ktx:1.2.1")
	implementation("androidx.drawerlayout:drawerlayout:1.2.0")
	implementation("androidx.work:work-runtime-ktx:2.9.1")
	implementation("com.google.android.material:material:1.12.0")
	implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.9.0")

	// Red y HTML
	implementation("com.squareup.okhttp3:okhttp:4.12.0")
	implementation("org.jsoup:jsoup:1.18.3")

	testImplementation("junit:junit:4.13.2")
	testImplementation("org.json:json:20240303")

	// Prueba instrumentada de accesibilidad: recorrido con TalkBack y Accessibility Test Framework
	androidTestImplementation("androidx.test:runner:1.6.2")
	androidTestImplementation("androidx.test:core:1.6.1")
	androidTestImplementation("androidx.test.ext:junit:1.2.1")
	androidTestImplementation("com.google.android.apps.common.testing.accessibility.framework:accessibility-test-framework:4.1.1")
	androidTestImplementation("com.google.guava:guava:33.3.1-android")
}
