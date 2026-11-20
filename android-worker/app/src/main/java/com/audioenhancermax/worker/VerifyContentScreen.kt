package com.audioenhancermax.worker

import android.app.Application
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Process
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.AudioFile
import androidx.compose.material.icons.filled.Fingerprint
import androidx.compose.material.icons.filled.FolderOpen
import androidx.compose.material.icons.filled.Share
import androidx.compose.material.icons.filled.VerifiedUser
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import java.io.File
import java.util.Locale
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.TimeoutCancellationException
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/** The share channel accepts one explicitly granted external content URI. */
private val SupportedShareKinds = setOf("audio", "video")

internal fun singleSharedContent(context: Context, intent: Intent): Uri? {
    if (intent.action != Intent.ACTION_SEND ||
        intent.type?.substringBefore('/') !in SupportedShareKinds ||
        (intent.flags and Intent.FLAG_GRANT_READ_URI_PERMISSION) == 0) return null
    return runCatching {
        val clip = intent.clipData
        if (clip != null && clip.itemCount != 1) return null
        @Suppress("DEPRECATION")
        val stream = if (Build.VERSION.SDK_INT >= 33) intent.getParcelableExtra(Intent.EXTRA_STREAM, Uri::class.java)
        else intent.getParcelableExtra<Uri>(Intent.EXTRA_STREAM)
        val clipped = clip?.getItemAt(0)?.uri
        if (stream != null && clipped != null && stream != clipped) return null
        val uri = stream ?: clipped ?: return null
        if (!isExternalMediaUri(context, uri)) return null
        if (context.checkUriPermission(uri, Process.myPid(), Process.myUid(), Intent.FLAG_GRANT_READ_URI_PERMISSION)
            != PackageManager.PERMISSION_GRANTED) return null
        uri
    }.getOrNull()
}

internal class MediaVerificationViewModel(app: Application) : AndroidViewModel(app) {
    private var revision = 0
    var sharedFile by mutableStateOf<Uri?>(null)
        private set
    var navigationRequest by mutableIntStateOf(0)
        private set
    var result by mutableStateOf<MediaVerification?>(null)
        private set
    var error by mutableStateOf<String?>(null)
        private set
    var working by mutableStateOf(false)
        private set
    var saving by mutableStateOf(false)
        private set

    fun acceptShareIntent(intent: Intent) {
        if (intent.action != Intent.ACTION_SEND) return
        revision++
        sharedFile = singleSharedContent(getApplication<Application>(), intent)
        result = null
        error = if (sharedFile == null) "The shared file is unavailable. Choose one audio or video file in Verify Content." else null
        navigationRequest++
    }

    fun dismissShare() { sharedFile = null }
    fun verifyShare() { sharedFile?.let(::verify) }

    fun verify(uri: Uri) {
        if (working || saving) return
        working = true
        val request = ++revision
        sharedFile = null
        result = null
        error = null
        viewModelScope.launch {
            try {
                val checked = verifyMediaUri(getApplication<Application>(), uri)
                if (request == revision) result = checked
            } catch (_: TimeoutCancellationException) {
                if (request == revision) error = "The provider did not finish reading this file in time."
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (invalid: IllegalArgumentException) {
                if (request == revision) error = invalid.message ?: "Choose a supported file."
            } catch (_: OutOfMemoryError) {
                if (request == revision) error = "The device reached its memory limit. Choose a smaller file."
            } catch (_: Exception) {
                if (request == revision) error = "The file could not be read. Choose a local copy with read access."
            } finally {
                working = false
            }
        }
    }

    fun shareReport(onSaved: (File) -> Unit) {
        val report = result ?: return
        if (saving || working) return
        saving = true
        viewModelScope.launch {
            try {
                val file = withContext(Dispatchers.IO) { saveVerificationReport(getApplication<Application>(), report) }
                onSaved(file)
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (_: Exception) {
                error = "The verification report could not be shared."
            } finally {
                saving = false
            }
        }
    }
}

@Composable
internal fun VerifyContentScreen(model: MediaVerificationViewModel, share: (File) -> Unit) {
    val picker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { it?.let(model::verify) }
    WorkspaceTitle("Verify Content", "Read Content Credentials and measure the original file on this device.")
    if (model.sharedFile != null) {
        WorkspaceCard {
            WorkspaceSection("Shared file", Icons.Default.AudioFile)
            Text("Open the shared file for verification.", color = WorkspaceMuted)
            ActionButton("Verify shared file", !model.working && !model.saving, model::verifyShare)
            TextButton(onClick = model::dismissShare) { Text("Dismiss") }
        }
    } else {
        WorkspaceCard {
            WorkspaceSection("Choose an original file", Icons.Default.FolderOpen)
            Text("WAV, MP3, FLAC, M4A, MP4 and MOV · up to 100 MiB.", color = WorkspaceMuted,
                style = MaterialTheme.typography.bodySmall)
            ActionButton("Choose a file", !model.working && !model.saving) {
                picker.launch(arrayOf("audio/*", "video/*", "application/octet-stream"))
            }
        }
    }
    if (model.working) {
        LinearProgressIndicator(Modifier.fillMaxWidth())
        Text("Reading file and checking credentials…", color = WorkspaceMuted, style = MaterialTheme.typography.bodySmall)
    }
    model.error?.let { Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodyMedium) }
    model.result?.let { report ->
        WorkspaceCard {
            WorkspaceSection("File fingerprint", Icons.Default.Fingerprint)
            Text(String.format(Locale.US, "%,d bytes · %s", report.asset.sizeBytes, report.asset.mediaType),
                color = WorkspaceMuted, style = MaterialTheme.typography.bodyMedium)
            VerificationText("SHA-256", report.asset.digest)
        }
        VerificationCredentials(report.credentials)
        VerificationAudio(report.audio, report.audioDetail)
        Button(
            onClick = { model.shareReport(share) },
            enabled = !model.saving && !model.working,
            modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp),
        ) {
            Icon(Icons.Default.Share, contentDescription = null, modifier = Modifier.size(18.dp))
            Spacer(Modifier.width(8.dp))
            Text(if (model.saving) "Preparing report…" else "Share JSON report")
        }
    }
}

@Composable
private fun ActionButton(label: String, enabled: Boolean, onClick: () -> Unit) {
    Button(onClick = onClick, enabled = enabled, modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp)) { Text(label) }
}

@Composable
private fun VerificationCredentials(summary: CredentialSummary) {
    WorkspaceCard {
        WorkspaceSection("Embedded C2PA", Icons.Default.VerifiedUser)
        val statusColor = when (summary.status) {
            "valid", "trusted" -> WorkspaceMint
            "unsigned", "remote_reference" -> WorkspaceMuted
            else -> WorkspaceAmber
        }
        Text(summary.outcome, color = statusColor, style = MaterialTheme.typography.titleLarge)
        Text(summary.detail, color = WorkspaceMuted, style = MaterialTheme.typography.bodyMedium)
        summary.signer?.let { VerificationText("Signer name", it) }
        summary.issuer?.let { VerificationText("Certificate issuer", it) }
        summary.signerTrustLabel?.let { VerificationText("Signer trust", it) }
        summary.timestampLabel?.let { VerificationText("Timestamp trust", it) }
        summary.reportFingerprint?.let { VerificationText("Processing report SHA-256", it) }
        if (summary.actions.isNotEmpty()) {
            HorizontalDivider(color = WorkspaceLine)
            Text("Manifest actions", fontWeight = FontWeight.SemiBold)
            summary.actions.forEach { action ->
                VerificationText(action.action, listOfNotNull(action.at, action.start, action.end, action.software).joinToString(" · ")
                    .ifEmpty { "Recorded in the manifest" })
            }
        }
        if (summary.failureCodes.isNotEmpty()) {
            HorizontalDivider(color = WorkspaceLine)
            VerificationText("Reader findings", summary.failureCodes.joinToString("\n"))
        }
    }
}

@Composable
private fun VerificationAudio(audio: AudioMeasurements?, detail: String?) {
    WorkspaceCard {
        WorkspaceSection("Audio measurements", Icons.Default.AudioFile)
        if (audio == null) {
            Text(detail ?: "Audio measurements are unavailable.", color = WorkspaceMuted)
            return@WorkspaceCard
        }
        fun db(value: Double?) = if (value == null) "Silence" else String.format(Locale.US, "%.1f dBFS", value)
        val window = if (audio.complete) "Full decoded track" else "First analyzed portion"
        Text(String.format(Locale.US, "%s · %.2f s · %,d Hz · %d ch", window,
            audio.analyzedSeconds, audio.sampleRate, audio.channels), color = WorkspaceMuted,
            style = MaterialTheme.typography.bodySmall)
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
            VerificationText("Sample peak", db(audio.peakDbfs))
            VerificationText("RMS level", db(audio.rmsDbfs))
        }
        VerificationText("Samples at or above 99.9% full scale",
            String.format(Locale.US, "%,d / %,d", audio.nearFullScaleSamples, audio.analyzedSamples))
        Text("These are signal measurements. They do not identify how the audio was created.", color = WorkspaceMuted,
            style = MaterialTheme.typography.bodySmall)
    }
}

@Composable
private fun VerificationText(title: String, value: String) {
    Column(verticalArrangement = Arrangement.spacedBy(3.dp)) {
        Text(title, color = WorkspaceMuted, style = MaterialTheme.typography.labelMedium)
        SelectionContainer {
            Text(value, fontFamily = if (title.contains("SHA-256")) FontFamily.Monospace else FontFamily.Default,
                style = MaterialTheme.typography.bodyMedium)
        }
    }
}
