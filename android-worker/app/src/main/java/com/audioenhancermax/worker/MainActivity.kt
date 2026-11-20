package com.audioenhancermax.worker

import android.content.Intent
import android.content.ClipData
import android.graphics.Color
import android.os.Bundle
import android.provider.OpenableColumns
import android.view.WindowManager
import androidx.activity.ComponentActivity
import androidx.activity.SystemBarStyle
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import androidx.core.content.FileProvider
import androidx.lifecycle.ViewModelProvider
import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Computer
import androidx.compose.material.icons.filled.GraphicEq
import androidx.compose.material.icons.filled.Info
import androidx.compose.material.icons.filled.MusicNote
import androidx.compose.material.icons.filled.VerifiedUser
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import java.io.File

class AudioDocumentContract:ActivityResultContracts.OpenDocument() {
    override fun createIntent(context:android.content.Context,input:Array<String>):Intent =
        super.createIntent(context,input).setType(if(input.size==1)input[0] else "*/*")
}

class MainActivity:ComponentActivity() {
    private lateinit var model:CompanionViewModel
    private lateinit var verification: MediaVerificationViewModel
    private val importer=registerForActivityResult(AudioDocumentContract()){uri ->
        if(uri!=null){
            val name=runCatching{contentResolver.query(uri,arrayOf(OpenableColumns.DISPLAY_NAME),null,null,null)?.use{if(it.moveToFirst())it.getString(0) else "Imported audio"}}.getOrNull() ?: "Imported audio"
            model.importAudio(uri,name)
        }
    }
    private val briefImporter=registerForActivityResult(ActivityResultContracts.OpenDocument()){uri->if(uri!=null)model.importBrief(uri)}
    override fun onCreate(savedInstanceState:Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge(SystemBarStyle.dark(Color.TRANSPARENT), SystemBarStyle.dark(Color.TRANSPARENT))
        model=ViewModelProvider(this)[CompanionViewModel::class.java]
        verification = ViewModelProvider(this)[MediaVerificationViewModel::class.java]
        if (savedInstanceState == null) verification.acceptShareIntent(intent)
        setContent {
            LaunchedEffect(model.workerRunning){if(model.workerRunning)window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)else window.clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)}
            CompanionScreen(model, verification,
                {filter->model.setImportFormat(filter);importer.launch(filter.mimeTypes)},
                {briefImporter.launch(arrayOf("application/json"))}, ::share)
        }
    }
    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        verification.acceptShareIntent(intent)
    }
    private fun share(file:File){
        val uri=FileProvider.getUriForFile(this,"$packageName.files",file)
        val mediaType = when (file.extension) {
            "json" -> "application/json"
            "txt" -> "text/plain"
            "mp4" -> "video/mp4"
            else -> "audio/wav"
        }
        val intent = Intent(Intent.ACTION_SEND).setType(mediaType).putExtra(Intent.EXTRA_STREAM, uri)
            .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        intent.clipData = ClipData.newRawUri(file.name, uri)
        startActivity(Intent.createChooser(intent,"Export from AudioEnhancerMAX"))
    }
    override fun onStart(){super.onStart();if(::model.isInitialized)model.startPresence()}
    override fun onPause(){
        if(::model.isInitialized)model.cancelNearbyPairing()
        super.onPause()
    }
    override fun onStop(){
        if(::model.isInitialized){
            model.stopPresence()
            model.stopWorker()
            model.stopPlayback()
        }
        window.clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        super.onStop()
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
internal fun CompanionScreen(
    vm: CompanionViewModel,
    verification: MediaVerificationViewModel,
    importAudio: (AudioImportPolicy.Filter) -> Unit,
    importBrief: () -> Unit,
    share: (File) -> Unit,
) {
    var tab by rememberSaveable { mutableIntStateOf(0) }
    var aboutOpen by rememberSaveable { mutableStateOf(false) }
    var handledShare by rememberSaveable { mutableIntStateOf(0) }

    LaunchedEffect(verification.navigationRequest) {
        if (verification.navigationRequest != handledShare) {
            handledShare = verification.navigationRequest
            aboutOpen = false
            tab = 3
        }
    }

    if (tab == 1 && !aboutOpen) {
        DisposableEffect(vm) { onDispose { vm.cancelNearbyPairing() } }
    }

    MaterialTheme(colorScheme = workspaceColorScheme) {
        Scaffold(
            topBar = {
                TopAppBar(
                    title = {
                        Row(horizontalArrangement = Arrangement.spacedBy(10.dp), verticalAlignment = Alignment.CenterVertically) {
                            Image(painterResource(R.drawable.aemax_original_mark), contentDescription = null, modifier = Modifier.size(29.dp))
                            Text(stringResource(R.string.app_name), style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                        }
                    },
                    actions = {
                        IconButton(onClick = { aboutOpen = true }) {
                            Icon(Icons.Default.Info, contentDescription = stringResource(R.string.about_title), tint = WorkspaceMuted)
                        }
                    },
                    colors = TopAppBarDefaults.topAppBarColors(containerColor = WorkspaceBackground),
                )
            },
            bottomBar = {
                NavigationBar(containerColor = WorkspaceSurface) {
                    listOf(
                        Triple(0, "Studio", Icons.Default.GraphicEq),
                        Triple(3, "Verify", Icons.Default.VerifiedUser),
                        Triple(1, "Mac link", Icons.Default.Computer),
                        Triple(2, "Music brief", Icons.Default.MusicNote),
                    ).forEach { (index, label, icon) ->
                        NavigationBarItem(
                            selected = tab == index, onClick = { tab = index },
                            icon = { Icon(icon, contentDescription = null) },
                            label = { Text(label) },
                            colors = NavigationBarItemDefaults.colors(
                                indicatorColor = WorkspaceMint.copy(alpha = .15f),
                                selectedIconColor = WorkspaceMint, selectedTextColor = WorkspaceMint,
                                unselectedIconColor = WorkspaceMuted, unselectedTextColor = WorkspaceMuted,
                            ),
                        )
                    }
                }
            },
        ) { padding ->
            key(tab) {
                Column(
                    Modifier.fillMaxSize().padding(padding).imePadding()
                        .verticalScroll(rememberScrollState())
                        .padding(horizontal = 18.dp).padding(bottom = 24.dp),
                    verticalArrangement = Arrangement.spacedBy(16.dp),
                ) {
                    when (tab) {
                        0 -> StudioScreen(vm, importAudio, share, { tab = 1 }, { tab = 3 })
                        1 -> WorkspaceConnection(vm, share)
                        2 -> MusicBriefScreen(vm, importBrief, share)
                        3 -> VerifyContentScreen(verification, share)
                    }
                }
            }
        }

        if (aboutOpen) AboutDialog(onDismiss = { aboutOpen = false })
        vm.error?.let { message ->
            AlertDialog(
                onDismissRequest = { vm.error = null },
                title = { Text("AudioEnhancerMAX") },
                text = { Text(message) },
                confirmButton = { TextButton(onClick = { vm.error = null }) { Text("OK") } },
            )
        }
    }
}
