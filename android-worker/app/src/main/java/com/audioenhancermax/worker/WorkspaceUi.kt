package com.audioenhancermax.worker

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp

internal val WorkspaceBackground = Color(0xff0d151a)
internal val WorkspaceSurface = Color(0xff152127)
internal val WorkspaceLine = Color(0xff304048)
internal val WorkspaceMint = Color(0xff68e5cb)
internal val WorkspaceMuted = Color(0xffa8b9c0)
internal val WorkspaceAmber = Color(0xffffb881)
internal val workspaceColorScheme = darkColorScheme(
    primary = WorkspaceMint, onPrimary = Color(0xff042c25),
    secondary = Color(0xffb3baf8), onSecondary = Color(0xff162252),
    secondaryContainer = Color(0xff273b45), onSecondaryContainer = Color(0xffe1f3f5),
    background = WorkspaceBackground, surface = WorkspaceSurface,
    onBackground = Color(0xffedf6f5), onSurface = Color(0xffedf6f5),
    onSurfaceVariant = WorkspaceMuted, outline = WorkspaceLine, outlineVariant = WorkspaceLine,
)

@Composable
internal fun WorkspaceCard(
    modifier: Modifier = Modifier,
    content: @Composable ColumnScope.() -> Unit,
) {
    Card(
        modifier = modifier.fillMaxWidth(),
        shape = RoundedCornerShape(22.dp),
        border = BorderStroke(1.dp, WorkspaceLine),
        colors = CardDefaults.cardColors(containerColor = WorkspaceSurface),
    ) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp), content = content)
    }
}

@Composable
internal fun WorkspaceTitle(title: String, help: String? = null) {
    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Text(title, style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.Bold)
        if (help != null) Text(help, style = MaterialTheme.typography.bodyMedium, color = WorkspaceMuted)
    }
}

@Composable
internal fun WorkspaceSection(title: String, icon: ImageVector) {
    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(9.dp)) {
        Icon(icon, contentDescription = null, tint = WorkspaceMint, modifier = Modifier.size(20.dp))
        Text(title, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
    }
}

@Composable
internal fun WorkspaceToggle(title: String, checked: Boolean, enabled: Boolean = true, onChange: (Boolean) -> Unit) {
    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
        Text(title, modifier = Modifier.weight(1f), style = MaterialTheme.typography.bodyMedium)
        Switch(checked = checked, onCheckedChange = onChange, enabled = enabled)
    }
}
