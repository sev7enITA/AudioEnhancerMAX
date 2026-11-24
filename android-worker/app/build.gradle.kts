plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
}

val playStoreOnly = providers.gradleProperty("aemax.playStoreOnly").orElse("false").map { value ->
    require(value in setOf("true", "false")) { "aemax.playStoreOnly must be true or false" }
    value.toBoolean()
}.get()

android {
    namespace = "com.audioenhancermax.worker"
    compileSdk = 36

    defaultConfig {
        applicationId = "com.audioenhancermax.worker"
        minSdk = 26
        testInstrumentationRunner = "com.audioenhancermax.worker.MediaInstrumentation"
        targetSdk = if (playStoreOnly) 36 else 35
        versionCode = 23
        versionName = "4.1.9"
        buildConfigField("boolean", "PLAY_STORE_ONLY", playStoreOnly.toString())
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
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
        compose = true
        buildConfig = true
    }

    sourceSets.getByName("main").assets.srcDir("../../app/resources/c2pa")
    sourceSets.getByName("main").assets.srcDir("../../app/resources/mobile")
    sourceSets.getByName("main").assets.srcDir(layout.buildDirectory.dir("generated/reviewDeskAssets"))
    sourceSets.getByName("androidTest").assets.srcDir("../../web/c2pa/v4.0.0-beta.1")
}

val stageReviewDesk by tasks.registering(Sync::class) {
    from("../../frontend/review-desk")
    into(layout.buildDirectory.dir("generated/reviewDeskAssets/review-desk"))
}
tasks.named("preBuild") { dependsOn(stageReviewDesk) }

dependencies {
    // Compose BOM
    val composeBom = platform("androidx.compose:compose-bom:2024.06.00")
    implementation(composeBom)

    // Compose UI
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-graphics")
    implementation("androidx.compose.ui:ui-tooling-preview")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.material:material-icons-extended")

    // Activity Compose
    implementation("androidx.activity:activity-compose:1.9.0")

    // Lifecycle
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.8.2")
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.8.2")

    // Core KTX
    implementation("androidx.core:core-ktx:1.13.1")
    implementation("androidx.exifinterface:exifinterface:1.4.2")

    // Foreground lifecycle and regression tests
    implementation("androidx.lifecycle:lifecycle-viewmodel-ktx:2.8.2")
    testImplementation("junit:junit:4.13.2")
    
    implementation("com.journeyapps:zxing-android-embedded:4.3.0")

    // JSON
    implementation("com.google.code.gson:gson:2.11.0")
    implementation("com.github.contentauth:c2pa-android:0.1.1")
}
