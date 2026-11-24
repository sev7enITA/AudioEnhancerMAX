package com.audioenhancermax.worker

import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalClipboardManager
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import com.google.gson.Gson
import java.io.File
import kotlin.math.roundToInt

data class MusicDraft(
    val description: String = "",
    val style: String = "Ambient",
    val instruments: String = "Piano, soft strings",
    val exclusions: String = "",
    val vocals: String = "Instrumental",
    val duration: String = "30",
    val bpm: String = "90",
    val lyrics: String = "",
    val arrangement: String = "Opening; development; ending",
    val prompt: String = "",
    val builtSource: String = "",
) {
    private val source get() = listOf(description, style, instruments, exclusions, vocals, duration, bpm, lyrics, arrangement)
        .joinToString("\u001F")
    val ready get() = description.isNotBlank() && duration.toIntOrNull() in 5..600 &&
        bpm.toIntOrNull() in 30..240 && source.toByteArray().size <= 12000
    val canExport get() = ready && prompt.isNotEmpty() && builtSource == source && prompt.toByteArray().size <= 12000

    fun build(): MusicDraft {
        require(ready) { "Add a direction, duration 5–600 seconds and tempo 30–240 BPM." }
        val metadata = buildList {
            add("GLOBAL METADATA")
            add(description.trim())
            add("Target: ${duration.toInt()} seconds · ${bpm.toInt()} BPM")
            if (style.isNotBlank()) add("Style: ${style.trim()}")
            if (instruments.isNotBlank()) add("Palette: ${instruments.trim()}")
            if (exclusions.isNotBlank()) add("Avoid: ${exclusions.trim()}")
        }.joinToString("\n")
        val vocalDirection = vocals.trim().ifBlank { "Instrumental" }
        val structure = arrangement.trim().ifBlank { "Opening, development and controlled ending." }
        val text = "$metadata\n\nVOCAL DETAILS\n$vocalDirection\n\nARRANGEMENT\n$structure"
        require(text.toByteArray().size <= 12000) { "Shorten the brief before sharing." }
        return copy(prompt = text, builtSource = source)
    }
}

private data class BriefPreset(
    val name: String,
    val summary: String,
    val style: String,
    val instruments: String,
    val exclusions: String,
    val vocals: String,
    val duration: String,
    val bpm: String,
    val arrangement: String,
) {
    fun applyTo(draft: MusicDraft) = draft.copy(
        style = style, instruments = instruments, exclusions = exclusions, vocals = vocals,
        duration = duration, bpm = bpm, arrangement = arrangement,
    )
}

@Composable
internal fun MusicBriefScreen(vm: CompanionViewModel, importBrief: () -> Unit, share: (File) -> Unit) {
    val context = LocalContext.current
    val clipboard = LocalClipboardManager.current
    val presets = remember(context) {
        context.assets.open("music-brief-presets.json").bufferedReader().use {
            Gson().fromJson(it, Array<BriefPreset>::class.java).toList()
        }
    }
    val draft = vm.music
    val clipSeconds = vm.wave?.duration?.roundToInt()?.takeIf { it in 5..600 }
    var selected by remember { mutableStateOf<BriefPreset?>(null) }
    var details by remember { mutableStateOf(false) }
    var copied by remember(draft.prompt) { mutableStateOf(false) }

    Column(verticalArrangement = Arrangement.spacedBy(16.dp)) {
        Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text("Music brief", style = MaterialTheme.typography.headlineMedium)
            Text("Turn a scene, recording or project into a shareable music direction.",
                color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        WorkspaceCard {
            Text("Start from a use case", style = MaterialTheme.typography.titleLarge)
            Row(Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()),
                horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                presets.forEach { preset ->
                    OutlinedButton(onClick = { selected = preset }) { Text(preset.name) }
                }
            }
            selected?.let { template ->
                Text(template.summary)
                TextButton(onClick = { vm.updateMusic(template.applyTo(vm.music)); selected = null }) {
                    Text("Apply ${template.name} preset")
                }
            }
        }
        WorkspaceCard {
            Text("Direction", style = MaterialTheme.typography.titleLarge)
            BriefInput(draft.description, { vm.updateMusic(draft.copy(description = it)) },
                "What should the music do?", lines = 3)
            Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                BriefInput(draft.duration, { vm.updateMusic(draft.copy(duration = it)) }, "Seconds",
                    Modifier.weight(1f), number = true)
                BriefInput(draft.bpm, { vm.updateMusic(draft.copy(bpm = it)) }, "BPM",
                    Modifier.weight(1f), number = true)
            }
            if (clipSeconds != null && draft.duration.toIntOrNull() != clipSeconds) {
                TextButton(onClick = { vm.updateMusic(draft.copy(duration = clipSeconds.toString())) }) {
                    Text("Match recording · $clipSeconds s")
                }
            }
            BriefInput(draft.style, { vm.updateMusic(draft.copy(style = it)) }, "Style and mood")
            BriefInput(draft.arrangement, { vm.updateMusic(draft.copy(arrangement = it)) }, "Structure and timing", lines = 2)
            TextButton(onClick = { details = !details }) {
                Text(if (details) "Hide palette and vocals" else "Edit palette and vocals")
            }
            if (details) {
                BriefInput(draft.instruments, { vm.updateMusic(draft.copy(instruments = it)) }, "Instrument palette")
                BriefInput(draft.exclusions, { vm.updateMusic(draft.copy(exclusions = it)) }, "Avoid")
                BriefInput(draft.vocals, { vm.updateMusic(draft.copy(vocals = it)) }, "Vocal direction")
                BriefInput(draft.lyrics, { vm.updateMusic(draft.copy(lyrics = it)) }, "Separate lyrics for the JSON", lines = 2)
            }
        }
        WorkspaceCard {
            Text("Brief preview", style = MaterialTheme.typography.titleLarge)
            if (!draft.canExport) {
                if (!draft.ready) {
                    Text("Add a direction, 5–600 seconds and 30–240 BPM.", color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                Button(onClick = vm::buildBrief, enabled = draft.ready) {
                    Text(if (draft.prompt.isEmpty()) "Build preview" else "Refresh preview")
                }
            } else {
                SelectionContainer { Text(draft.prompt) }
                Button(onClick = {
                    clipboard.setText(AnnotatedString(draft.prompt))
                    copied = true
                }) { Text(if (copied) "Copied" else "Copy brief") }
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedButton(onClick = { vm.exportBriefText()?.let(share) }) { Text("Share text") }
                    OutlinedButton(onClick = { vm.exportBrief()?.let(share) }) { Text("Share JSON") }
                }
            }
            TextButton(onClick = importBrief) { Text("Import brief JSON") }
        }
    }
}

@Composable
private fun BriefInput(
    value: String, onChange: (String) -> Unit, label: String, modifier: Modifier = Modifier,
    lines: Int = 1, number: Boolean = false,
) {
    OutlinedTextField(value, onChange, modifier = modifier.fillMaxWidth(), label = { Text(label) },
        minLines = lines, maxLines = maxOf(1, lines + 2), singleLine = lines == 1,
        keyboardOptions = KeyboardOptions(keyboardType = if (number) KeyboardType.Number else KeyboardType.Text))
}
