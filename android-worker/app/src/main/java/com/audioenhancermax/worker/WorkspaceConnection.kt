package com.audioenhancermax.worker

import android.os.SystemClock
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.journeyapps.barcodescanner.ScanContract
import com.journeyapps.barcodescanner.ScanOptions
import kotlinx.coroutines.delay
import java.io.File
import java.util.Locale

@Composable
internal fun WorkspaceConnection(vm: CompanionViewModel, share: (File) -> Unit) {
    WorkspaceTitle("Mac link", if (vm.paired) null else "Pair over the same Wi-Fi or hotspot.")
    LinkStatus(vm)
    if (!vm.paired) PairingPanel(vm)
    if (vm.paired) {
        ContributionPanel(vm)
        MacTransferPanel(vm, share)
        DevicePanel(vm)
    }
}

@Composable
private fun LinkStatus(vm: CompanionViewModel) {
    WorkspaceCard {
        val primary = if (vm.connected) WorkspaceMint else WorkspaceMuted
        Row(
            Modifier.fillMaxWidth().background(
                Brush.horizontalGradient(listOf(WorkspaceBackground, WorkspaceSurface)),
                RoundedCornerShape(15.dp),
            ).padding(vertical = 15.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.Center,
        ) {
            Icon(Icons.Default.Smartphone, contentDescription = null, modifier = Modifier.size(35.dp), tint = primary)
            Spacer(Modifier.width(14.dp))
            Icon(if (vm.connected) Icons.Default.Lock else Icons.Default.WifiTethering,
                contentDescription = null, modifier = Modifier.size(19.dp), tint = primary)
            Spacer(Modifier.width(14.dp))
            Icon(Icons.Default.Computer, contentDescription = null, modifier = Modifier.size(42.dp), tint = primary)
        }
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            Box(Modifier.size(8.dp).background(primary, CircleShape))
            Spacer(Modifier.width(8.dp))
            Text(
                when {
                    vm.connected -> "Connected · encrypted"
                    vm.paired -> "Saved Mac · offline"
                    else -> "No Mac paired"
                },
                style = MaterialTheme.typography.labelMedium, color = primary,
            )
        }
        if (vm.paired) {
            Text(vm.macName, style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold,
                maxLines = 2, overflow = TextOverflow.Ellipsis)
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                TextButton(onClick = { vm.reconnect() }, enabled = !vm.connected && !vm.busy) { Text("Reconnect") }
                TextButton(onClick = vm::disconnect, enabled = !vm.busy) { Text("Forget Mac") }
            }
        } else {
            Text("Open Connections & Edge Cluster on the Mac, then choose how to find it here.", color = WorkspaceMuted)
        }
    }
}

@Composable
private fun PairingPanel(vm: CompanionViewModel) {
    var showFallback by rememberSaveable { mutableStateOf(false) }
    var manual by rememberSaveable { mutableStateOf(false) }
    var code by remember { mutableStateOf("") }
    var scanError by remember { mutableStateOf<String?>(null) }
    val scanner = rememberLauncherForActivityResult(ScanContract()) { result ->
        result.contents?.let { text ->
            if (runCatching { Pairing.parse(text) }.isSuccess) {
                scanError = null
                vm.connect(text)
            } else {
                scanError = "Show a fresh AudioEnhancerMAX pairing QR code on the Mac."
            }
        }
        if (result.originalIntent?.getBooleanExtra("MISSING_CAMERA_PERMISSION", false) == true)
            scanError = "Allow camera access in Settings, or paste the private pairing code."
    }

    val comparison = vm.nearbyComparison
    WorkspaceCard {
        if (comparison != null) {
            WorkspaceSection("Compare codes", Icons.Default.Shield)
            Text(comparison.name, style = MaterialTheme.typography.titleSmall)
            Text(comparison.code.chunked(4).joinToString("  "), color = WorkspaceMint,
                style = MaterialTheme.typography.headlineLarge, fontFamily = FontFamily.Monospace)
            Text(if (comparison.awaitingMac) "Waiting for approval on the Mac." else
                "Confirm only if the same eight digits appear on the Mac.", color = WorkspaceMuted)
            if (comparison.awaitingMac) LinearProgressIndicator(Modifier.fillMaxWidth())
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedButton(onClick = vm::cancelNearbyPairing, modifier = Modifier.weight(1f)) { Text("Cancel") }
                Button(onClick = vm::confirmNearbyCode, enabled = !comparison.awaitingMac && !vm.busy,
                    modifier = Modifier.weight(1f)) { Text("Codes match") }
            }
            return@WorkspaceCard
        }
        WorkspaceSection("Pair nearby", Icons.Default.Wifi)
        if (vm.phoneDiscoverable) {
            DiscoverablePanel(vm)
            return@WorkspaceCard
        }

        Button(onClick = vm::findNearbyMacs, enabled = !vm.busy && !vm.nearbySearching,
            modifier = Modifier.fillMaxWidth().heightIn(min = 50.dp)) {
            Icon(Icons.Default.Search, contentDescription = null)
            Spacer(Modifier.width(8.dp));Text("Find nearby Macs")
        }
        FilledTonalButton(onClick = vm::makePhoneDiscoverable, enabled = !vm.busy,
            modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp)) {
            Icon(Icons.Default.Smartphone, contentDescription = null)
            Spacer(Modifier.width(8.dp));Text("Make this phone discoverable")
        }

        if (vm.nearbySearching) {
            LinearProgressIndicator(Modifier.fillMaxWidth())
            Text("Looking for Macs on this network.", color = WorkspaceMuted, style = MaterialTheme.typography.bodySmall)
        }
        vm.nearbyMacs.forEach { NearbyDevice(it, "Pair") { vm.beginNearbyPairing(it) } }
        vm.nearbyMessage?.let { Text(it, color = WorkspaceMuted) }
        if (vm.nearbySearching || vm.busy && vm.nearbyMessage != null)
            TextButton(onClick = vm::cancelNearbyPairing) { Text("Cancel search") }
        if (vm.busy && vm.nearbyMessage == null) {
            LinearProgressIndicator(Modifier.fillMaxWidth())
            Text(vm.macState, color = WorkspaceMuted)
        }

        HorizontalDivider(color = WorkspaceLine)
        TextButton(onClick = { showFallback = !showFallback }) {
            Text(if (showFallback) "Hide other pairing methods" else "Other pairing methods")
        }
        if (showFallback) {
            OutlinedButton(onClick = {
                vm.cancelNearbyPairing()
                scanError = null
                scanner.launch(
                    ScanOptions().setCaptureActivity(PairingCaptureActivity::class.java)
                        .setDesiredBarcodeFormats(ScanOptions.QR_CODE).setPrompt("Scan the QR shown on the Mac")
                        .setBeepEnabled(false).setBarcodeImageEnabled(false),
                )
            }, enabled = !vm.busy, modifier = Modifier.fillMaxWidth()) {
                Icon(Icons.Default.QrCodeScanner, contentDescription = null)
                Spacer(Modifier.width(8.dp));Text("Scan a QR code")
            }
            scanError?.let { Text(it, color = MaterialTheme.colorScheme.error) }
            TextButton(onClick = { manual = !manual }, enabled = !vm.busy) { Text("Paste a private code") }
            if (manual) {
                OutlinedTextField(
                    value = code, onValueChange = { code = it.take(4095) }, label = { Text("Private pairing code") },
                    visualTransformation = PasswordVisualTransformation(), modifier = Modifier.fillMaxWidth(), enabled = !vm.busy,
                )
                Button(onClick = { vm.cancelNearbyPairing();vm.connect(code);code = "" },
                    enabled = code.isNotBlank() && !vm.busy, modifier = Modifier.fillMaxWidth()) { Text("Pair with code") }
            }
        }
    }
}

@Composable
private fun DiscoverablePanel(vm: CompanionViewModel) {
    val expires = vm.phoneVisibleUntil
    fun secondsRemaining(): Long = ((expires?.minus(SystemClock.elapsedRealtime()) ?: 0L) + 999L)
        .div(1000).coerceIn(0L, 90L)
    var remaining by remember(expires) { mutableLongStateOf(secondsRemaining()) }
    LaunchedEffect(expires) {
        while (remaining > 0L) {
            delay(250)
            remaining = secondsRemaining()
        }
    }
    Text(if (vm.phoneAdvertised) "Visible for ${remaining}s" else "Making this phone visible…",
        style = MaterialTheme.typography.titleLarge, color = WorkspaceMint)
    Text("On your Mac, select Find nearby phones and invite this phone.", color = WorkspaceMuted)
    LinearProgressIndicator(progress = { remaining.toFloat() / 90 }, modifier = Modifier.fillMaxWidth())
    vm.phoneInvitations.forEach { NearbyDevice(it, "Accept") { vm.beginNearbyPairing(it) } }
    TextButton(onClick = vm::cancelNearbyPairing) { Text("Stop discovery") }
}

@Composable
private fun NearbyDevice(mac: NearbyMac, action: String, activate: () -> Unit) {
    Row(
        Modifier.fillMaxWidth().background(WorkspaceBackground, RoundedCornerShape(12.dp)).padding(start = 10.dp, end = 2.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(9.dp),
    ) {
        Icon(Icons.Default.Computer, contentDescription = null, tint = WorkspaceMint, modifier = Modifier.size(21.dp))
        Text(mac.name, maxLines = 2, overflow = TextOverflow.Ellipsis, modifier = Modifier.weight(1f))
        TextButton(onClick = activate) { Text(action) }
    }
}

@Composable
private fun ContributionPanel(vm: CompanionViewModel) {
    val usage = vm.workerUsage
    WorkspaceCard {
        WorkspaceSection("Help the Mac process audio", Icons.Default.Bolt)
        Text(
            when {
                vm.workerRunning -> vm.workerState
                !vm.connected -> "Mac offline"
                vm.macAcceptsWorker == false -> "Waiting for permission on the Mac"
                else -> if (vm.workerState == "Paused") "Paused" else "Contribution off"
            },
            style = MaterialTheme.typography.titleMedium,
            color = if (vm.workerRunning) WorkspaceMint else WorkspaceMuted,
        )
        Text("This phone can process Voice EQ chunks while the app is open.", color = WorkspaceMuted, style = MaterialTheme.typography.bodySmall)
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            StatCell("Chunks returned", usage.chunks.toString(), Modifier.weight(1f))
            StatCell("Audio processed", String.format(Locale.US, "%.1f s", usage.audioSeconds), Modifier.weight(1f))
        }
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            StatCell("DSP throughput", usage.realtimeFactor?.let { String.format(Locale.US, "%.1f× realtime", it) } ?: "—", Modifier.weight(1f))
            StatCell("Mac round trip", vm.latencyMs?.let { "$it ms" } ?: "—", Modifier.weight(1f))
        }
        usage.lastDspMilliseconds?.let {
            Text(String.format(Locale.US, "Last chunk %.1f ms on this phone. Throughput excludes network time.", it),
                style = MaterialTheme.typography.bodySmall, color = WorkspaceMuted)
        }
        vm.workerNotice?.let { Text(it, style = MaterialTheme.typography.bodySmall, color = WorkspaceAmber) }
        if (vm.macAcceptsWorker == false)
            Text("Enable trusted local network processing in Mac Preferences.", style = MaterialTheme.typography.bodySmall, color = WorkspaceAmber)
        WorkspaceToggle("Contribute Voice EQ", vm.workerRunning, !vm.busy && (vm.workerRunning || vm.connected && vm.macAcceptsWorker != false)) {
            if (it) vm.startWorker() else vm.stopWorker()
        }
    }
}

@Composable
private fun StatCell(label: String, value: String, modifier: Modifier) {
    Column(modifier.background(WorkspaceBackground, RoundedCornerShape(11.dp)).padding(11.dp),
        verticalArrangement = Arrangement.spacedBy(2.dp)) {
        Text(value, style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.Bold, color = WorkspaceMint)
        Text(label, style = MaterialTheme.typography.labelSmall, color = WorkspaceMuted)
    }
}

@Composable
private fun MacTransferPanel(vm: CompanionViewModel, share: (File) -> Unit) {
    var profile by rememberSaveable { mutableStateOf("voice") }
    WorkspaceCard {
        WorkspaceSection("Process audio on the Mac", Icons.Default.Upload)
        if (vm.wave == null) {
            Text("Import a recording in Studio to send it here.", color = WorkspaceMuted)
            return@WorkspaceCard
        }
        Text(vm.name, maxLines = 2, overflow = TextOverflow.Ellipsis, style = MaterialTheme.typography.titleSmall)
        if (vm.result != null) WorkspaceToggle("Send rendered edit", vm.sendResult, !vm.busy) { vm.sendResult = it }
        Text(vm.transferSelection, style = MaterialTheme.typography.labelMedium, color = WorkspaceMint)
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            FilterChip(selected = profile == "voice", onClick = { profile = "voice" }, enabled = !vm.busy,
                label = { Text("Voice EQ + level") })
            FilterChip(selected = profile == "level", onClick = { profile = "level" }, enabled = !vm.busy,
                label = { Text("Level only") })
        }
        Button(onClick = { vm.processOnMac(profile) }, enabled = vm.connected && !vm.busy && !vm.hasPendingJob,
            modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp)) { Text("Send to Mac") }
        if (vm.hasPendingJob) OutlinedButton(onClick = { vm.recover() }, enabled = vm.connected && !vm.busy,
            modifier = Modifier.fillMaxWidth()) { Text("Recover job") }
        if (vm.busy) LinearProgressIndicator(Modifier.fillMaxWidth())
        Text(vm.macState, color = WorkspaceMuted, style = MaterialTheme.typography.bodySmall)
        vm.report?.let { report -> TextButton(onClick = { share(report) }) { Text("Export Mac report") } }
    }
}

@Composable
private fun DevicePanel(vm: CompanionViewModel) {
    var expanded by rememberSaveable { mutableStateOf(false) }
    WorkspaceCard {
        TextButton(onClick = { expanded = !expanded }) {
            Icon(Icons.Default.Info, contentDescription = null, modifier = Modifier.size(18.dp))
            Spacer(Modifier.width(8.dp));Text(if (expanded) "Hide connection details" else "Connection details")
        }
        if (expanded) {
            Text(vm.macEndpoint, color = WorkspaceMuted, style = MaterialTheme.typography.bodySmall)
            Text(vm.assessmentText, style = MaterialTheme.typography.bodySmall)
            OutlinedButton(onClick = { vm.assessDevice() }, enabled = !vm.busy && !vm.workerRunning) { Text("Run local assessment") }
        }
    }
}
