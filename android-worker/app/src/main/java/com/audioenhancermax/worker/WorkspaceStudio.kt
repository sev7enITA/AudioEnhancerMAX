package com.audioenhancermax.worker

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Redo
import androidx.compose.material.icons.automirrored.filled.Undo
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import java.io.File
import java.util.Locale
import kotlin.math.roundToLong

@Composable
internal fun StudioScreen(
    vm: CompanionViewModel,
    importAudio: (AudioImportPolicy.Filter) -> Unit,
    share: (File) -> Unit,
    openConnection: () -> Unit,
    openVerification: () -> Unit,
) {
    WorkspaceTitle("Studio", if (vm.wave == null) "Edit a recording on this device." else null)
    if (vm.wave == null) {
        WorkspaceCard {
            WorkspaceSection("Open a recording", Icons.Default.AudioFile)
            Text("Choose a format filter or browse for an audio or video file.", color = WorkspaceMuted)
            FileActions(vm, importAudio)
        }
    }
    vm.wave?.let { wave ->
        TrackPanel(vm, wave, importAudio)
        EditPanel(vm, wave)
        StudioExports(vm, share, openConnection)
        if (vm.importAnalysis.isNotBlank()) {
            var open by rememberSaveable { mutableStateOf(false) }
            WorkspaceCard {
                TextButton(onClick = { open = !open }) { Text(if (open) "Hide recording details" else "Recording details") }
                if (open) Text(vm.importAnalysis, style = MaterialTheme.typography.bodySmall, color = WorkspaceMuted)
            }
        }
    }
    OutlinedButton(onClick = openVerification, modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp)) {
        Icon(Icons.Default.VerifiedUser, contentDescription = null, modifier = Modifier.size(18.dp))
        Spacer(Modifier.width(8.dp))
        Text("Verify an original file")
    }
    if (vm.busy) {
        val progress = if (vm.restoringStudio) "Restoring Studio…" else "Working on audio"
        if (vm.restoringStudio) Text(progress)
        LinearProgressIndicator(Modifier.fillMaxWidth().semantics { contentDescription = progress })
    }
}

@Composable
private fun FileActions(vm: CompanionViewModel, importAudio: (AudioImportPolicy.Filter) -> Unit) {
    var formatsOpen by rememberSaveable { mutableStateOf(false) }
    var compatibilityOpen by rememberSaveable { mutableStateOf(false) }
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
        Button(
            onClick = { importAudio(vm.importFilter) },
            enabled = !vm.busy,
            modifier = Modifier.weight(1f).heightIn(min = 48.dp),
        ) {
            Icon(Icons.Default.Add, contentDescription = null, modifier = Modifier.size(18.dp))
            Spacer(Modifier.width(6.dp))
            Text(if (vm.wave == null) "Import file" else "Replace file")
        }
        Box {
            OutlinedButton(onClick = { formatsOpen = true }, enabled = !vm.busy, modifier = Modifier.heightIn(min = 48.dp)) {
                Text(vm.importFilter.label)
                Icon(Icons.Default.ExpandMore, contentDescription = null, modifier = Modifier.size(17.dp))
            }
            DropdownMenu(expanded = formatsOpen, onDismissRequest = { formatsOpen = false }) {
                AudioImportPolicy.Filter.entries.forEach { filter ->
                    DropdownMenuItem(
                        text = { Text(filter.label) },
                        onClick = { vm.setImportFormat(filter); formatsOpen = false },
                        leadingIcon = if (vm.importFilter == filter) {
                            { Icon(Icons.Default.Check, contentDescription = "Selected format") }
                        } else null,
                    )
                }
            }
        }
    }
    TextButton(onClick = { compatibilityOpen = true }, modifier = Modifier.heightIn(min = 48.dp)) {
        Icon(Icons.Default.Info, contentDescription = null, modifier = Modifier.size(16.dp))
        Spacer(Modifier.width(8.dp))
        Text("Import compatibility")
    }
    if (compatibilityOpen) {
        AlertDialog(
            onDismissRequest = { compatibilityOpen = false },
            title = { Text("Import compatibility") },
            text = {
                Column(Modifier.verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    Text("Files up to 100 MiB, with one readable mono or stereo audio track. The decoded edit can use up to 64 MiB.")
                    AudioImportPolicy.Filter.entries.forEach { format ->
                        Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
                            Text(format.label, fontWeight = FontWeight.SemiBold, color = WorkspaceMint)
                            Text(format.compatibility, color = WorkspaceMuted, style = MaterialTheme.typography.bodySmall)
                        }
                    }
                }
            },
            confirmButton = { TextButton(onClick = { compatibilityOpen = false }) { Text("Done") } },
        )
    }
}

@Composable
private fun TrackPanel(vm: CompanionViewModel, wave: Wave, importAudio: (AudioImportPolicy.Filter) -> Unit) {
    val duration = wave.duration
    var zoom by rememberSaveable(vm.sourceRevision) { mutableIntStateOf(1) }
    var viewportStart by rememberSaveable(vm.sourceRevision) { mutableDoubleStateOf(0.0) }
    val viewportEnd = (viewportStart + duration / zoom).coerceAtMost(duration)
    val bounds = vm.currentSelection()

    WorkspaceCard {
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Icon(Icons.Default.GraphicEq, contentDescription = null, tint = WorkspaceMint, modifier = Modifier.size(23.dp))
            Text(vm.name, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold,
                maxLines = 1, overflow = TextOverflow.Ellipsis, modifier = Modifier.weight(1f))
            Text("${wave.channels} ch", style = MaterialTheme.typography.labelMedium, color = WorkspaceMint)
        }
        Text("${timelineTime(duration)}  ·  ${wave.rate} Hz  ·  ${vm.sourceRevision}",
            style = MaterialTheme.typography.labelMedium, color = WorkspaceMuted)
        val selectionColor = WorkspaceMint.copy(alpha = .12f)
        val peaks = vm.waveformPeaks
        Canvas(
            Modifier.fillMaxWidth().height(126.dp)
                .background(WorkspaceBackground, RoundedCornerShape(12.dp))
                .semantics { contentDescription = "Recording waveform" }
                .pointerInput(viewportStart, viewportEnd) {
                    detectTapGestures { position ->
                        val fraction = (position.x / size.width).coerceIn(0f, 1f)
                        vm.seekPlayback((viewportStart + fraction * (viewportEnd - viewportStart)).toFloat())
                    }
                },
        ) {
            val window = viewportEnd - viewportStart
            fun x(at: Double) = ((at - viewportStart) / window * size.width).toFloat()
            for (index in 1..7) {
                val line = size.width * index / 8f
                drawLine(WorkspaceLine.copy(alpha = .55f), Offset(line, 0f), Offset(line, size.height), strokeWidth = 1.dp.toPx())
            }
            drawLine(WorkspaceLine, Offset(0f, size.height / 2f), Offset(size.width, size.height / 2f))
            bounds?.let { range ->
                val from = x(range.start).coerceIn(0f, size.width)
                val to = x(range.endInclusive).coerceIn(0f, size.width)
                if (to > from) {
                    drawRoundRect(selectionColor, Offset(from, 0f), Size(to - from, size.height), CornerRadius(6.dp.toPx()))
                }
            }
            val barWidth = (size.width / (peaks.size / zoom).coerceAtLeast(1) * .65f).coerceAtLeast(1.dp.toPx())
            for (i in peaks.indices) {
                val time = (i + 0.5) * duration / peaks.size
                if (time < viewportStart || time > viewportEnd) continue
                val at = x(time)
                val half = (peaks[i] * size.height * .44f).coerceAtLeast(1.dp.toPx())
                val selected = bounds?.contains(time) != false
                drawLine(
                    WorkspaceMint.copy(alpha = if (selected) .9f else .4f),
                    Offset(at, size.height / 2 - half), Offset(at, size.height / 2 + half), barWidth,
                )
            }
            val position = vm.playhead.toDouble()
            if (position in viewportStart..viewportEnd && size.width > 2f) {
                val playhead = x(position).coerceIn(1f, size.width - 1f)
                drawLine(WorkspaceAmber, Offset(playhead, 0f), Offset(playhead, size.height), 2.dp.toPx())
                drawCircle(WorkspaceAmber, 4.dp.toPx(), Offset(playhead, 4.dp.toPx()))
            }
        }
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
            Text(timelineTime(viewportStart), style = MaterialTheme.typography.labelSmall, color = WorkspaceMuted)
            TextButton(onClick = {
                zoom = when (zoom) { 1 -> 2; 2 -> 4; else -> 1 }
                val width = duration / zoom
                viewportStart = (vm.playhead.toDouble() - width / 2).coerceIn(0.0, (duration - width).coerceAtLeast(0.0))
            }) {
                Icon(Icons.Default.ZoomIn, contentDescription = null, modifier = Modifier.size(17.dp))
                Spacer(Modifier.width(5.dp))
                Text(if (zoom == 1) "Fit" else "${zoom}×")
            }
            Text(timelineTime(viewportEnd), style = MaterialTheme.typography.labelSmall, color = WorkspaceMuted)
        }
        Transport(vm, wave)
        HorizontalDivider(color = WorkspaceLine)
        FileActions(vm, importAudio)
    }
}

@Composable
private fun Transport(vm: CompanionViewModel, wave: Wave) {
    val duration = wave.duration.toFloat()
    var desired by remember(vm.sourceRevision, vm.resultRevision) { mutableStateOf<Float?>(null) }
    Slider(
        value = (desired ?: vm.playhead).coerceIn(0f, duration),
        onValueChange = { desired = it },
        onValueChangeFinished = { desired?.let(vm::seekPlayback); desired = null },
        valueRange = 0f..duration,
        enabled = !vm.busy,
        modifier = Modifier.semantics { contentDescription = "Playback position" },
    )
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
        Text(timelineTime((desired ?: vm.playhead).toDouble()), fontWeight = FontWeight.Bold)
        Text(vm.playbackState, color = WorkspaceMuted, style = MaterialTheme.typography.bodySmall)
    }
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(6.dp), verticalAlignment = Alignment.CenterVertically) {
        FilledTonalButton(onClick = { vm.play(true) }, modifier = Modifier.weight(1f), enabled = !vm.busy) { Text("A  Original") }
        FilledTonalButton(onClick = { vm.play(false) }, modifier = Modifier.weight(1f), enabled = vm.result != null && !vm.busy) { Text("B  Edit") }
        IconButton(onClick = vm::stopPlayback, enabled = vm.playbackState != "Stopped") { Icon(Icons.Default.Pause, contentDescription = "Pause") }
        IconToggleButton(checked = vm.loopPlayback, onCheckedChange = { vm.loopPlayback = it }) {
            Icon(Icons.Default.Repeat, contentDescription = "Loop playback", tint = if (vm.loopPlayback) WorkspaceMint else WorkspaceMuted)
        }
    }
    if (vm.comparison != null) WorkspaceToggle("Match A/B listening levels", vm.matchListeningLevels, !vm.busy, vm::setListeningLevelMatched)
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun EditPanel(vm: CompanionViewModel, wave: Wave) {
    var tool by rememberSaveable { mutableIntStateOf(0) }
    val selection = vm.currentSelection()
    WorkspaceCard {
        Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.fillMaxWidth()) {
            Box(Modifier.weight(1f)) { WorkspaceSection("Edit rack", Icons.Default.Tune) }
            IconButton(onClick = vm::undoEdit, enabled = vm.canUndoEdit && !vm.busy) {
                Icon(Icons.AutoMirrored.Filled.Undo, contentDescription = "Undo rendered edit")
            }
            IconButton(onClick = vm::redoEdit, enabled = vm.canRedoEdit && !vm.busy) {
                Icon(Icons.AutoMirrored.Filled.Redo, contentDescription = "Redo rendered edit")
            }
        }
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            listOf("Trim", "Fades", "Levels").forEachIndexed { index, label ->
                FilterChip(selected = index == tool, onClick = { tool = index }, label = { Text(label) })
            }
        }
        when (tool) {
            0 -> {
                val max = wave.duration.toFloat()
                val selectedRange = (selection?.start?.toFloat() ?: 0f)..(selection?.endInclusive?.toFloat() ?: max)
                RangeSlider(
                    value = selectedRange, onValueChange = { vm.setStudioRange(it.start, it.endInclusive) },
                    valueRange = 0f..max, enabled = !vm.busy,
                    modifier = Modifier.semantics { contentDescription = "Trim range" },
                )
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    TimeField("In (seconds)", vm.start, { vm.start = it }, !vm.busy, Modifier.weight(1f))
                    TimeField("Out (seconds)", vm.end, { vm.end = it }, !vm.busy, Modifier.weight(1f))
                }
                selection?.let {
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        TextButton(
                            onClick = { vm.setStudioRange(vm.playhead, it.endInclusive.toFloat()) },
                            enabled = !vm.busy && vm.playhead < it.endInclusive,
                            modifier = Modifier.weight(1f),
                        ) { Text("Set in at cursor") }
                        TextButton(
                            onClick = { vm.setStudioRange(it.start.toFloat(), vm.playhead) },
                            enabled = !vm.busy && vm.playhead > it.start,
                            modifier = Modifier.weight(1f),
                        ) { Text("Set out at cursor") }
                    }
                }
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                    Text(selection?.let { "Keep ${timelineTime(it.endInclusive - it.start)}" } ?: "Set an in and out point",
                        style = MaterialTheme.typography.labelMedium, color = if (selection == null) WorkspaceAmber else WorkspaceMuted)
                    TextButton(onClick = vm::resetStudioRange, enabled = !vm.busy) { Text("Full file") }
                }
                OutlinedButton(
                    onClick = vm::silenceSelection,
                    enabled = selection != null && !vm.busy,
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Icon(Icons.Default.VolumeOff, contentDescription = null, modifier = Modifier.size(18.dp))
                    Spacer(Modifier.width(6.dp))
                    Text("Silence selected range")
                }
            }
            1 -> {
                val fadeLimit = ((selection?.let { it.endInclusive - it.start } ?: 0.0) / 2).toFloat().coerceIn(0f, 5f)
                FadeControl("Fade in", vm.fadeIn, fadeLimit, !vm.busy, { vm.fadeIn = it })
                FadeControl("Fade out", vm.fadeOut, fadeLimit, !vm.busy, { vm.fadeOut = it })
            }
            else -> {
                Text(String.format(Locale.US, "Gain %+.1f dB", vm.gain))
                Slider(vm.gain, { vm.gain = it }, valueRange = -24f..12f, enabled = !vm.busy,
                    modifier = Modifier.semantics { contentDescription = "Gain in decibels" })
                WorkspaceToggle("Normalize peak to −1 dBFS", vm.normalize, !vm.busy) { vm.normalize = it }
                WorkspaceToggle("Voice EQ", vm.voice, !vm.busy) { vm.voice = it }
            }
        }
        HorizontalDivider(color = WorkspaceLine)
        OutlinedButton(onClick = vm::playSelection, enabled = selection != null && !vm.busy, modifier = Modifier.fillMaxWidth()) {
            Icon(Icons.Default.PlayArrow, contentDescription = null)
            Spacer(Modifier.width(6.dp))
            Text("Play selection")
        }
        Button(onClick = vm::edit, enabled = selection != null && !vm.busy, modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp)) {
            Icon(Icons.Default.Check, contentDescription = null)
            Spacer(Modifier.width(6.dp))
            Text("Render edit")
        }
    }
}

@Composable
private fun TimeField(
    label: String, value: String, change: (String) -> Unit, enabled: Boolean, modifier: Modifier,
) {
    val draft = value.toDoubleOrNull()?.let {
        if (value.length > 9) String.format(Locale.US, "%.3f", it) else value
    } ?: value
    OutlinedTextField(
        value = draft, onValueChange = { change(it.take(12).replace(',', '.')) },
        label = { Text(label) }, modifier = modifier, enabled = enabled, singleLine = true,
        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
    )
}

@Composable
private fun FadeControl(label: String, value: Float, max: Float, enabled: Boolean, onChange: (Float) -> Unit) {
    val shown = value.coerceAtMost(max)
    Text(if (shown < .001f) "$label off" else String.format(Locale.US, "%s %.2f s", label, shown))
    Slider(
        value = shown, onValueChange = onChange, valueRange = 0f..max.coerceAtLeast(.001f),
        enabled = enabled && max > 0, modifier = Modifier.semantics { contentDescription = "$label duration" },
    )
}

@Composable
private fun StudioExports(vm: CompanionViewModel, share: (File) -> Unit, openConnection: () -> Unit) {
    WorkspaceCard {
        WorkspaceSection("Export and handoff", Icons.Default.IosShare)
        if (vm.result == null) Text("Render an edit to export WAV.", color = WorkspaceMuted)
        else {
            Text("Revision ${vm.resultRevision}", style = MaterialTheme.typography.labelMedium, color = WorkspaceMint)
            vm.result?.let { file ->
                Button(onClick = { share(file) }, enabled = !vm.busy, modifier = Modifier.fillMaxWidth()) { Text("Export WAV") }
            }
        }
        if (vm.videoSource != null) {
            Text("Use a full-length edit to keep exported MP4 audio in sync.", color = WorkspaceMuted, style = MaterialTheme.typography.bodySmall)
            OutlinedButton(onClick = vm::exportVideo, enabled = vm.result != null && !vm.busy, modifier = Modifier.fillMaxWidth()) {
                Text("Prepare MP4")
            }
            vm.videoResult?.let { file -> TextButton(onClick = { share(file) }) { Text("Export MP4 copy") } }
        }
        vm.report?.let { file -> TextButton(onClick = { share(file) }) { Text("Export Mac report") } }
        OutlinedButton(onClick = openConnection, enabled = !vm.busy, modifier = Modifier.fillMaxWidth()) {
            Icon(Icons.Default.Computer, contentDescription = null, modifier = Modifier.size(20.dp))
            Spacer(Modifier.width(8.dp))
            Text(if (vm.connected) "Send to Mac" else "Connect a Mac")
        }
    }
}

internal fun timelineTime(seconds: Double): String {
    val milliseconds = (seconds * 1000).roundToLong().coerceAtLeast(0)
    return String.format(Locale.US, "%d:%02d.%03d", milliseconds / 60000, milliseconds / 1000 % 60, milliseconds % 1000)
}
