package com.audioenhancermax.worker

import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp

internal const val ProductWebsite = "https://www.fabriziodegni.com/AudioEnhancerMAX/"
internal const val ProductSupport = "${ProductWebsite}support.html"
private const val SourceLicense = "https://github.com/sev7enITA/AudioEnhancerMAX/blob/main/LICENSE"

@Composable
internal fun AboutDialog(onDismiss: () -> Unit, onUpdates: () -> Unit, onWelcome: () -> Unit) {
    val context = LocalContext.current
    val build = remember(context) { readInstalledBuild(context) }
    val uriHandler = LocalUriHandler.current
    var couldNotOpen by remember { mutableStateOf(false) }
    val links = listOf(
        R.string.about_website to ProductWebsite,
        R.string.about_support to ProductSupport,
        R.string.about_privacy to "${ProductWebsite}privacy.html",
        R.string.about_license to SourceLicense,
    )

    AlertDialog(
        onDismissRequest = onDismiss,
        title = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Image(
                    painter = painterResource(R.drawable.aemax_original_mark),
                    contentDescription = null,
                    modifier = Modifier.size(48.dp),
                )
                Text(stringResource(R.string.app_name), style = MaterialTheme.typography.titleLarge)
            }
        },
        text = {
            Column(Modifier.verticalScroll(rememberScrollState())) {
                Text(stringResource(R.string.about_edition), style = MaterialTheme.typography.titleSmall)
                Text(stringResource(R.string.about_version, build.version, build.number))
                Text(stringResource(R.string.about_developer))
                TextButton(onClick = onUpdates) { Text("Updates") }
                TextButton(onClick = onWelcome) { Text("What's new") }
                links.forEach { (label, url) ->
                    TextButton(onClick = {
                        couldNotOpen = runCatching { uriHandler.openUri(url) }.isFailure
                    }) { Text(stringResource(label)) }
                }
                if (couldNotOpen) {
                    Text(
                        stringResource(R.string.about_open_link_error),
                        color = MaterialTheme.colorScheme.error,
                    )
                }
            }
        },
        confirmButton = { TextButton(onClick = onDismiss) { Text(stringResource(R.string.about_done)) } },
    )
}
