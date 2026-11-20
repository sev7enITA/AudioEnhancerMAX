package com.audioenhancermax.worker

import android.app.Application
import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.selection.selectableGroup
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.DialogProperties
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import java.util.Locale
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.TimeoutCancellationException
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

internal enum class UpdateActivity { CHECK, DOWNLOAD, SAVE }

internal class CompanionUpdateViewModel(app: Application) : AndroidViewModel(app) {
    private val client = CompanionUpdateClient(app)
    private val preferences = app.getSharedPreferences("verified-updates", 0)
    var source by mutableStateOf(DirectUpdateSource.entries.firstOrNull {
        it.name == preferences.getString("direct-source", null)
    } ?: DirectUpdateSource.GITHUB)
        private set
    var channel by mutableStateOf(updateChannel(app))
        private set
    var installed by mutableStateOf<ApkIdentity?>(null)
        private set
    var candidate by mutableStateOf<SignedAndroidFeed?>(null)
        private set
    var verified by mutableStateOf<VerifiedUpdate?>(null)
        private set
    var activity by mutableStateOf<UpdateActivity?>(null)
        private set
    var status by mutableStateOf<String?>(null)
        private set
    var error by mutableStateOf<String?>(null)
        private set
    private val bytesCopied = MutableStateFlow(0L)
    val progress: kotlinx.coroutines.flow.StateFlow<Long> get() = bytesCopied
    private var work: Job? = null

    fun opened() {
        channel = updateChannel(getApplication<Application>())
        installed = runCatching { installedApkIdentity(getApplication<Application>()) }.getOrNull()
    }

    fun chooseSource(next: DirectUpdateSource) {
        if (activity != null || channel != UpdateChannel.Direct || source == next) return
        clearCandidate()
        source = next
        preferences.edit().putString("direct-source", next.name).apply()
        status = null
        error = null
    }

    fun check() {
        val current = installed ?: return
        if (activity != null || channel != UpdateChannel.Direct) return
        clearCandidate()
        perform(UpdateActivity.CHECK) {
            val feed = client.check()
            requireUpdate(feed.follows(preferences.getLong("highest-build", 0), preferences.getLong("latest-issue", 0)),
                "The signed feed is older than a feed already checked on this phone.")
            val saved = withContext(Dispatchers.IO) {
                preferences.edit().putLong("highest-build", feed.release.build).putLong("latest-issue", feed.issuedAt).commit()
            }
            requireUpdate(saved, "The update check could not be saved safely.")
            val release = feed.release
            if (release.build > current.build) {
                requireUpdate(current.signerSha256 == setOf(release.signerSha256),
                    "This update is signed for a different installation.")
                candidate = feed
            } else {
                status = if (release.build == current.build) "This build is up to date."
                    else "The signed feed lists an older build than the one installed."
            }
        }
    }

    fun download() {
        val available = candidate ?: return
        val repo = source
        perform(UpdateActivity.DOWNLOAD) {
            bytesCopied.value = 0
            verified = client.download(available, repo) { bytesCopied.value = it }
            status = "Package verified. Save it in Android Files to install it manually."
        }
    }

    fun save(uri: Uri?) {
        if (uri == null) return
        val packageFile = verified ?: return
        perform(UpdateActivity.SAVE) {
            client.save(packageFile, uri)
            packageFile.file.delete()
            verified = null
            candidate = null
            status = "Saved and verified. In Android Files, open the APK to install it."
        }
    }

    fun cancel() { work?.cancel() }

    fun closed() {
        clearCandidate()
        status = null
        error = null
    }

    private fun clearCandidate() {
        verified?.file?.delete()
        verified = null
        candidate = null
        bytesCopied.value = 0
    }

    private fun perform(step: UpdateActivity, block: suspend () -> Unit) {
        if (activity != null || channel != UpdateChannel.Direct) return
        activity = step
        status = null
        error = null
        work = viewModelScope.launch {
            try {
                block()
            } catch (_: TimeoutCancellationException) {
                error = "The operation timed out. Try again when the connection is stable."
            } catch (cancelled: CancellationException) {
                status = "Cancelled."
                throw cancelled
            } catch (failed: UpdateFailure) {
                error = failed.message
            } catch (_: Exception) {
                error = "The update could not be verified or saved."
            } finally {
                activity = null
                work = null
            }
        }
    }

    override fun onCleared() {
        work?.cancel()
        clearCandidate()
        super.onCleared()
    }
}

@Composable
internal fun UpdatesDialog(model: CompanionUpdateViewModel, onDismiss: () -> Unit) {
    val context = LocalContext.current
    var storeError by remember { mutableStateOf(false) }
    val save = rememberLauncherForActivityResult(ActivityResultContracts.CreateDocument(ApkMime), model::save)
    val busy = model.activity != null
    val bytesCopied by model.progress.collectAsState()
    val channel = model.channel
    val dismiss = {
        if (!busy) {
            model.closed()
            onDismiss()
        }
    }
    AlertDialog(
        onDismissRequest = dismiss,
        properties = DialogProperties(dismissOnBackPress = !busy, dismissOnClickOutside = !busy),
        title = { Text("Updates") },
        text = {
            Column(Modifier.verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                model.installed?.let {
                    Text("Installed ${it.versionName.orEmpty()} · Build ${it.build}", style = MaterialTheme.typography.labelLarge)
                }
                when (channel) {
                    UpdateChannel.Play -> {
                        Text("Google Play manages updates for this installation.", color = WorkspaceMuted)
                        Button(onClick = { storeError = !openUpdateMarketplace(context, channel) }, modifier = Modifier.fillMaxWidth()) {
                            Text("Check in Google Play")
                        }
                    }
                    is UpdateChannel.Marketplace -> {
                        Text("${channel.label} manages updates for this installation.", color = WorkspaceMuted)
                        if (channel.installer != null) {
                            Button(onClick = { storeError = !openUpdateMarketplace(context, channel) }, modifier = Modifier.fillMaxWidth()) {
                                Text("Open marketplace")
                            }
                        } else Text("Check for updates in the marketplace where you installed the app.", color = WorkspaceMuted)
                    }
                    UpdateChannel.Unavailable -> Text("The installation source is unavailable.", color = WorkspaceMuted)
                    UpdateChannel.Direct -> DirectUpdates(model, busy, bytesCopied) { save.launch(it) }
                }
                if (storeError) Text("The marketplace listing could not be opened on this device.", color = MaterialTheme.colorScheme.error)
            }
        },
        confirmButton = {
            if (busy) TextButton(onClick = model::cancel) { Text("Cancel") }
            else TextButton(onClick = dismiss) { Text("Done") }
        },
    )
}

@Composable
private fun DirectUpdates(
    model: CompanionUpdateViewModel,
    busy: Boolean,
    bytesCopied: Long,
    saveFile: (String) -> Unit,
) {
    Text("Direct installation", fontWeight = androidx.compose.ui.text.font.FontWeight.SemiBold)
    Text("Choose the repository for this APK download.", color = WorkspaceMuted, style = MaterialTheme.typography.bodySmall)
    Column(Modifier.selectableGroup()) {
        DirectUpdateSource.entries.forEach { source ->
            Row(
                Modifier.fillMaxWidth().heightIn(min = 48.dp).selectable(
                    selected = model.source == source, onClick = { model.chooseSource(source) },
                    enabled = !busy, role = Role.RadioButton,
                ),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                RadioButton(selected = model.source == source, onClick = null, enabled = !busy)
                Spacer(Modifier.width(10.dp))
                Text(source.label)
            }
        }
    }
    OutlinedButton(onClick = model::check, enabled = !busy && model.installed != null, modifier = Modifier.fillMaxWidth()) {
        Text("Check for updates")
    }
    val release = model.candidate?.release
    if (release != null) {
        HorizontalDivider(color = WorkspaceLine)
        Text("Available ${release.version} · Build ${release.build}", style = MaterialTheme.typography.titleMedium)
        Text(String.format(Locale.US, "%.1f MiB · %s", release.sizeBytes / 1048576.0, model.source.label),
            color = WorkspaceMuted, style = MaterialTheme.typography.bodySmall)
        if (model.verified == null) {
            Button(onClick = model::download, enabled = !busy, modifier = Modifier.fillMaxWidth()) {
                Text("Download from ${model.source.label}")
            }
        } else {
            Button(onClick = { saveFile(release.filename) }, enabled = !busy, modifier = Modifier.fillMaxWidth()) {
                Text("Save verified APK")
            }
        }
    }
    when (model.activity) {
        UpdateActivity.CHECK -> LinearProgressIndicator(Modifier.fillMaxWidth())
        UpdateActivity.DOWNLOAD -> {
            val total = release?.sizeBytes ?: 1
            LinearProgressIndicator(progress = { (bytesCopied.toDouble() / total).toFloat().coerceIn(0f, 1f) },
                modifier = Modifier.fillMaxWidth())
        }
        UpdateActivity.SAVE -> {
            LinearProgressIndicator(Modifier.fillMaxWidth())
            Text("Checking the saved copy…", color = WorkspaceMuted, style = MaterialTheme.typography.bodySmall)
        }
        null -> Unit
    }
    model.status?.let { Text(it, color = WorkspaceMint, style = MaterialTheme.typography.bodySmall) }
    model.error?.let { Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall) }
}
