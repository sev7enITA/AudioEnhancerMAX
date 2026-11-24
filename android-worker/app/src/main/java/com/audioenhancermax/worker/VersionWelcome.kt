package com.audioenhancermax.worker

import android.content.Context
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowForward
import androidx.compose.material.icons.filled.AudioFile
import androidx.compose.material.icons.filled.Fingerprint
import androidx.compose.material.icons.filled.PhotoCamera
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.core.content.pm.PackageInfoCompat

internal data class InstalledBuild(val version: String, val number: Long)

internal fun readInstalledBuild(context: Context): InstalledBuild {
    val info = context.packageManager.getPackageInfo(context.packageName, 0)
    return InstalledBuild(info.versionName.orEmpty(), PackageInfoCompat.getLongVersionCode(info))
}

private data class BuildHighlight(val icon: ImageVector, val title: String, val description: String)

private fun highlights(build: Long): List<BuildHighlight> = when (build) {
    23L -> listOf(
        BuildHighlight(Icons.Default.AudioFile, "Review Desk", "Check SRT and WebVTT, edit chapters, and export matching WAV and subtitle clips."),
        BuildHighlight(Icons.Default.Fingerprint, "Listening evidence", "Compare two versions blind and include your decision and the file fingerprints in a local publishing pack."),
    )
    22L -> listOf(
        BuildHighlight(Icons.Default.AudioFile, "Studio restores in the background", "Saved audio and edits load while the interface opens. Studio tells you if a saved revision needs attention."),
        BuildHighlight(Icons.Default.Fingerprint, "Verify recordings on your device", "Inspect technical metadata, SHA-256 and Content Credentials before sharing a report."),
    )
    21L -> listOf(
        BuildHighlight(Icons.Default.Fingerprint, "New release signature", "This BETA is signed with the AudioEnhancerMAX release key. Direct updates verify the signature and file fingerprint before saving."),
        BuildHighlight(Icons.Default.PhotoCamera, "Inspect media offline", "Use Verify for codec and track metadata, embedded Content Credentials, and available cover artwork EXIF."),
    )
    20L -> listOf(
        BuildHighlight(Icons.Default.Fingerprint, "Compare file fingerprints", "Paste an expected SHA-256 in Verify Content and see whether it matches the inspected file. Include the comparison in the local JSON report."),
    )
    19L -> listOf(
        BuildHighlight(Icons.Default.Fingerprint, "Inspect media offline", "See codecs, duration and track properties alongside the file fingerprint and Content Credentials."),
        BuildHighlight(Icons.Default.PhotoCamera, "Read cover artwork EXIF", "Reveal available camera and exposure tags from embedded JPEG covers without adding them to a shared report."),
        BuildHighlight(Icons.Default.AudioFile, "Choose a Studio format", "Check which containers and audio tracks Studio can open before picking a file."),
    )
    else -> emptyList()
}

@Composable
internal fun VersionWelcomeScreen(build: InstalledBuild, onDismiss: () -> Unit) {
    val links = LocalUriHandler.current
    var couldNotOpen by remember { mutableStateOf(false) }
    BackHandler(onBack = onDismiss)

    Scaffold(
        containerColor = WorkspaceBackground,
        bottomBar = {
            Column(Modifier.fillMaxWidth().background(WorkspaceSurface).navigationBarsPadding().padding(horizontal = 22.dp, vertical = 12.dp)) {
                Button(onClick = onDismiss, modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp)) {
                    Text("Continue")
                    Spacer(Modifier.width(9.dp))
                    Icon(Icons.AutoMirrored.Filled.ArrowForward, contentDescription = null, modifier = Modifier.size(18.dp))
                }
            }
        },
    ) { padding ->
        Box(Modifier.fillMaxSize().padding(padding), contentAlignment = Alignment.TopCenter) {
            Column(
                Modifier.widthIn(max = 520.dp).fillMaxWidth().verticalScroll(rememberScrollState()).padding(horizontal = 22.dp, vertical = 26.dp),
                verticalArrangement = Arrangement.spacedBy(18.dp),
            ) {
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(13.dp)) {
                    Image(painterResource(R.drawable.aemax_original_mark), contentDescription = null, modifier = Modifier.size(52.dp))
                    Column {
                        Text(stringResource(R.string.app_name), style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                        Text(stringResource(R.string.about_version, build.version, build.number), color = WorkspaceMint,
                            style = MaterialTheme.typography.labelMedium)
                    }
                }
                Text("Edit recordings on your phone, inspect media and Content Credentials, and continue on your Mac.",
                    style = MaterialTheme.typography.titleLarge)
                Text("What's new", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
                val notes = highlights(build.number)
                if (notes.isEmpty()) {
                    Text("See the product website for release notes.", color = WorkspaceMuted)
                } else {
                    Column(Modifier.fillMaxWidth().background(WorkspaceSurface, RoundedCornerShape(18.dp)).padding(horizontal = 17.dp, vertical = 18.dp),
                        verticalArrangement = Arrangement.spacedBy(17.dp)) {
                        notes.forEach { note ->
                            Row(horizontalArrangement = Arrangement.spacedBy(13.dp)) {
                                Icon(note.icon, contentDescription = null, tint = WorkspaceMint, modifier = Modifier.size(23.dp))
                                Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                                    Text(note.title, style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.SemiBold)
                                    Text(note.description, color = WorkspaceMuted, style = MaterialTheme.typography.bodyMedium)
                                }
                            }
                        }
                    }
                }
                Column {
                    TextButton(onClick = { couldNotOpen = runCatching { links.openUri("${ProductWebsite}companion.html") }.isFailure }) { Text("Companion guide") }
                    TextButton(onClick = { couldNotOpen = runCatching { links.openUri(ProductSupport) }.isFailure }) { Text("Support") }
                    if (couldNotOpen) Text(stringResource(R.string.about_open_link_error), color = MaterialTheme.colorScheme.error)
                }
            }
        }
    }
}
