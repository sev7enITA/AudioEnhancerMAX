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
import androidx.core.content.pm.PackageInfoCompat

private const val WEBSITE = "https://www.fabriziodegni.com/AudioEnhancerMAX/"
private const val SOURCE_LICENSE = "https://github.com/sev7enITA/AudioEnhancerMAX/blob/main/LICENSE"

@Composable
internal fun AboutDialog(onDismiss: () -> Unit) {
    val context = LocalContext.current
    val info = remember(context) { context.packageManager.getPackageInfo(context.packageName, 0) }
    val uriHandler = LocalUriHandler.current
    var couldNotOpen by remember { mutableStateOf(false) }
    val links = listOf(
        R.string.about_website to WEBSITE,
        R.string.about_support to "${WEBSITE}support.html",
        R.string.about_privacy to "${WEBSITE}privacy.html",
        R.string.about_license to SOURCE_LICENSE,
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
                Text(
                    stringResource(
                        R.string.about_version,
                        info.versionName.orEmpty(),
                        PackageInfoCompat.getLongVersionCode(info),
                    ),
                )
                Text(stringResource(R.string.about_developer))
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
