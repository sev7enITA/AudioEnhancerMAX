package com.audioenhancermax.worker

import android.content.Context
import android.net.Uri
import android.os.Build
import android.provider.OpenableColumns
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.annotation.RequiresApi
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.material3.Button
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.contentauth.c2pa.C2PAContext
import org.contentauth.c2pa.C2PASettings
import org.contentauth.c2pa.FileStream
import org.contentauth.c2pa.Reader
import org.json.JSONObject
import java.io.File
import java.io.IOException
import java.time.Instant
import java.util.Locale

private const val MaxCredentialFileBytes = 500L * 1024 * 1024
private val credentialFormats = mapOf(
    "wav" to "audio/wav", "mp3" to "audio/mpeg", "flac" to "audio/flac",
    "m4a" to "audio/mp4", "mp4" to "video/mp4", "mov" to "video/quicktime",
)
private val credentialTrustExpires = Instant.parse("2027-02-02T17:24:49Z")

internal data class CredentialSummary(
    val outcome: String,
    val detail: String = "",
    val signer: String? = null,
    val signerTrust: String? = null,
    val timestamp: String? = null,
    val reportFingerprint: String? = null,
)

@RequiresApi(28)
internal suspend fun inspectContentCredentials(context: Context, uri: Uri): CredentialSummary = withContext(Dispatchers.IO) {
    val resolver = context.contentResolver
    val name = resolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)?.use { cursor ->
        if (cursor.moveToFirst()) cursor.getString(0) else null
    } ?: uri.lastPathSegment.orEmpty()
    val format = credentialFormats[name.substringAfterLast('.', "").lowercase(Locale.ROOT)]
        ?: return@withContext CredentialSummary("Unsupported format", "Choose a WAV, MP3, FLAC, M4A, MP4 or MOV file.")
    val copy = File.createTempFile("c2pa-", ".media", context.cacheDir)
    try {
        resolver.openInputStream(uri)?.use { input ->
            copy.outputStream().use { output ->
                val buffer = ByteArray(128 * 1024)
                var total = 0L
                while (true) {
                    ensureActive()
                    val count = input.read(buffer)
                    if (count < 0) break
                    total += count
                    if (total > MaxCredentialFileBytes) {
                        return@withContext CredentialSummary("File too large", "Choose a file up to 500 MB.")
                    }
                    output.write(buffer, 0, count)
                }
            }
        } ?: throw IOException("Cannot open file")
        inspectCredentialFile(context, copy, format)
    } finally {
        copy.delete()
    }
}

@RequiresApi(28)
internal fun inspectCredentialFile(context: Context, file: File, format: String): CredentialSummary {
    val expired = Instant.now() >= credentialTrustExpires
    val anchors = if (expired) emptyList() else listOf(
        "manifest" to "C2PA-TRUST-LIST.pem",
        "tsa" to "C2PA-TSA-TRUST-LIST.pem",
    ).map { (kind, name) ->
        mapOf("trust_kind" to kind, "trust_anchors" to context.assets.open(name).bufferedReader().use { it.readText() })
    }
    val settings = JSONObject(mapOf(
        "core" to mapOf("allowed_network_hosts" to emptyList<String>(), "decode_identity_assertions" to false),
        "verify" to mapOf("verify_after_reading" to true, "verify_trust" to true, "verify_timestamp_trust" to true,
            "remote_manifest_fetch" to false, "ocsp_fetch" to false),
        "trust" to mapOf("anchors" to anchors),
    ))
    return try {
        C2PASettings.create().use { localSettings ->
            localSettings.updateFromString(settings.toString(), "json")
            C2PAContext.fromSettings(localSettings).use { verification ->
                FileStream(file, FileStream.Mode.READ, createIfNeeded = false).use { stream ->
                    Reader.fromContext(verification).use { reader ->
                        reader.withStream(format, stream)
                        summarizeCredentials(JSONObject(reader.json()), reader.isEmbedded(), expired)
                    }
                }
            }
        }
    } catch (error: Exception) {
        val reason = error.message.orEmpty().lowercase(Locale.ROOT)
        when {
            "remote manifest" in reason || "remotemanifest" in reason ->
                CredentialSummary("Remote reference", "This file points to an online manifest. The check stays offline.")
            "manifestnotfound" in reason || "manifest not found" in reason || "no manifest" in reason ||
                "jumbfnotfound" in reason ->
                CredentialSummary("No embedded credentials", "The selected file contains no readable embedded C2PA manifest.")
            else -> CredentialSummary("Could not verify", "Check that the file opens and has a supported format.")
        }
    }
}

internal fun summarizeCredentials(root: JSONObject, embedded: Boolean, expired: Boolean): CredentialSummary {
    if (!embedded) return CredentialSummary("Remote reference", "This check reads only embedded manifests.")
    val manifestId = root.optString("active_manifest")
    val manifest = root.optJSONObject("manifests")?.optJSONObject(manifestId)
        ?: return CredentialSummary("Could not verify", "The active manifest could not be read.")
    val result = root.optJSONObject("validation_results")?.optJSONObject("activeManifest")
    val checks = result?.optJSONArray("success")
    val codes = (0 until (checks?.length() ?: 0)).mapNotNull { checks?.optJSONObject(it)?.optString("code") }.toSet()
    val assertions = manifest.optJSONArray("assertions")
    val report = (0 until (assertions?.length() ?: 0)).mapNotNull {
        assertions?.optJSONObject(it)?.takeIf { assertion ->
            assertion.optString("label") == "com.fabriziodegni.audioenhancermax.processing"
        }?.optJSONObject("data")?.optString("processing_report_sha256")
    }.firstOrNull { it.matches(Regex("[a-fA-F0-9]{64}")) }
    val state = root.optString("validation_state")
    val integrity = when (state) {
        "Valid", "Trusted" -> "Integrity verified"
        "Invalid" -> "Integrity check failed"
        else -> "Integrity not established"
    }
    val detail = when (state) {
        "Valid", "Trusted" -> "The asset matches its signed manifest."
        "Invalid" -> "The signature or a verification check failed."
        else -> "The reader did not report a usable integrity result."
    }
    val signerTrust = when {
        expired -> "Trust list expired"
        "signingCredential.trusted" in codes -> "Recognized"
        else -> "Not established"
    }
    val timestamp = when {
        expired -> "Trust list expired"
        "timeStamp.validated" in codes && "timeStamp.trusted" in codes -> "Trusted RFC 3161"
        "timeStamp.validated" in codes -> "Present, trust not established"
        else -> "Not established"
    }
    return CredentialSummary(integrity, detail, manifest.optJSONObject("signature_info")?.optString("issuer")
        ?.take(160)?.takeIf { it.isNotBlank() }, signerTrust, timestamp, report)
}

@Composable
internal fun ContentCredentialsCard() {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var result by remember { mutableStateOf<CredentialSummary?>(null) }
    var working by remember { mutableStateOf(false) }
    val picker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        if (uri != null && Build.VERSION.SDK_INT >= 28) {
            scope.launch {
                working = true
                result = null
                try {
                    result = inspectContentCredentials(context, uri)
                } catch (cancelled: kotlinx.coroutines.CancellationException) {
                    throw cancelled
                } catch (_: Exception) {
                    result = CredentialSummary("Could not verify", "The selected file could not be read.")
                } catch (_: LinkageError) {
                    result = CredentialSummary("Reader unavailable", "This device cannot load the local Content Credentials reader.")
                } finally {
                    working = false
                }
            }
        }
    }
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Text("Content Credentials", style = MaterialTheme.typography.titleLarge)
        Text("Inspect C2PA in the original file. Verification runs on this phone without uploading the file.",
            style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        if (Build.VERSION.SDK_INT < 28) {
            Text("On-device verification requires Android 9 or later.",
                color = MaterialTheme.colorScheme.onSurfaceVariant)
        } else {
            Button(onClick = { picker.launch(arrayOf("audio/*", "video/*", "application/octet-stream")) },
                enabled = !working, modifier = Modifier.heightIn(min = 48.dp)) {
                Text(if (working) "Checking credentials…" else "Check a file")
            }
            if (working) LinearProgressIndicator(Modifier.fillMaxWidth())
        }
        result?.let { summary ->
            HorizontalDivider()
            Text(summary.outcome, style = MaterialTheme.typography.titleMedium)
            Text(summary.detail)
            summary.signer?.let { Text("Signer · " + it) }
            summary.signerTrust?.let { Text("Signer trust · " + it) }
            summary.timestamp?.let { Text("Timestamp · " + it) }
            summary.reportFingerprint?.let {
                Text("Processing report SHA-256", style = MaterialTheme.typography.labelMedium)
                androidx.compose.foundation.text.selection.SelectionContainer {
                    Text(it, style = MaterialTheme.typography.bodySmall)
                }
            }
        }
    }
}
