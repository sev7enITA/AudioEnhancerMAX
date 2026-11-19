package com.audioenhancermax.worker

import android.content.Intent
import android.os.Bundle
import android.provider.OpenableColumns
import android.view.WindowManager
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.compose.rememberLauncherForActivityResult
import com.journeyapps.barcodescanner.ScanContract
import com.journeyapps.barcodescanner.ScanOptions
import androidx.activity.result.contract.ActivityResultContracts
import androidx.core.content.FileProvider
import androidx.lifecycle.ViewModelProvider
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import java.io.File

class AudioDocumentContract:ActivityResultContracts.OpenDocument() {
    override fun createIntent(context:android.content.Context,input:Array<String>):Intent =
        super.createIntent(context,input).setType(if(input.size==1)input[0] else "*/*")
}

class MainActivity:ComponentActivity() {
    private lateinit var model:CompanionViewModel
    private val importer=registerForActivityResult(AudioDocumentContract()){uri ->
        if(uri!=null){
            val name=runCatching{contentResolver.query(uri,arrayOf(OpenableColumns.DISPLAY_NAME),null,null,null)?.use{if(it.moveToFirst())it.getString(0) else "Imported audio"}}.getOrNull() ?: "Imported audio"
            model.importAudio(uri,name)
        }
    }
    private val briefImporter=registerForActivityResult(ActivityResultContracts.OpenDocument()){uri->if(uri!=null)model.importBrief(uri)}
    override fun onCreate(savedInstanceState:Bundle?) {
        super.onCreate(savedInstanceState)
        model=ViewModelProvider(this)[CompanionViewModel::class.java]
        setContent {
            LaunchedEffect(model.workerRunning){if(model.workerRunning)window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)else window.clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)}
            CompanionScreen(model,{filter->model.setImportFormat(filter);importer.launch(filter.mimeTypes)},{briefImporter.launch(arrayOf("application/json"))},::share)
        }
    }
    private fun share(file:File){
        val uri=FileProvider.getUriForFile(this,"$packageName.files",file)
        val intent=Intent(Intent.ACTION_SEND).setType(when(file.extension){"json"->"application/json";"mp4"->"video/mp4";else->"audio/wav"}).putExtra(Intent.EXTRA_STREAM,uri).addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        startActivity(Intent.createChooser(intent,"Export from AudioEnhancerMAX"))
    }
    override fun onStart(){super.onStart();if(::model.isInitialized)model.startPresence()}
    override fun onStop(){if(::model.isInitialized)model.stopPresence();if(::model.isInitialized){model.stopWorker();model.stopPlayback()};window.clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);super.onStop()}
}
private val CanvasColor=Color(0xFF080A0C)
private val Violet=Color(0xFFA791FF)
private val Cyan=Color(0xFF4DD8E8)
private val Amber=Color(0xFFFFBC65)

@OptIn(ExperimentalMaterial3Api::class)
@Composable fun CompanionScreen(vm:CompanionViewModel,importAudio:(AudioImportPolicy.Filter)->Unit,importBrief:()->Unit,share:(File)->Unit) {
    var tab by rememberSaveable{mutableIntStateOf(0)}
    var code by remember{mutableStateOf("")}
    var manualPairing by remember{mutableStateOf(false)}
    var scanError by remember{mutableStateOf<String?>(null)}
    val scanner=rememberLauncherForActivityResult(ScanContract()){result ->
        result.contents?.let { raw ->
            if(runCatching{Pairing.parse(raw)}.isSuccess) { code=""; scanError=null; vm.connect(raw) }
            else scanError="This is not an AudioEnhancerMAX pairing QR code. Show a new code in the Mac app's Edge Cluster."
        }
        if(result.originalIntent?.getBooleanExtra("MISSING_CAMERA_PERMISSION",false)==true)
            scanError="Camera access is needed to scan. Allow it in Android Settings, or use manual pairing."
    }
    var profile by remember{mutableStateOf("voice")}
    val context=androidx.compose.ui.platform.LocalContext.current
    val installedVersion = remember(context) {
        val info = context.packageManager.getPackageInfo(context.packageName, 0)
        "${info.versionName} (${androidx.core.content.pm.PackageInfoCompat.getLongVersionCode(info)})"
    }
    MaterialTheme(colorScheme=darkColorScheme(primary=Violet,secondary=Cyan,background=CanvasColor,surface=Color(0xFF101418),onPrimary=Color(0xFF151020))) {
        Scaffold(containerColor=CanvasColor,
            topBar={TopAppBar(title={Text("AudioEnhancerMAX",fontWeight=FontWeight.Bold)})},
            bottomBar={NavigationBar{listOf("Studio" to Icons.Default.GraphicEq,"Connection" to Icons.Default.Computer,"Music brief" to Icons.Default.Notes).forEachIndexed{index,item->NavigationBarItem(selected=tab==index,onClick={tab=index},icon={Icon(item.second,contentDescription=null)},label={Text(item.first)})}}}
        ){padding->
            Column(Modifier.padding(padding).imePadding().fillMaxSize().verticalScroll(rememberScrollState()).padding(20.dp),verticalArrangement=Arrangement.spacedBy(16.dp)) {
                when(tab){
                    0->{
                        if(vm.wave==null) Text("Open a recording",style=MaterialTheme.typography.headlineLarge,fontWeight=FontWeight.Bold)
                        var formatMenu by remember{mutableStateOf(false)}
                        Box {
                            OutlinedButton(onClick={formatMenu=true},enabled=!vm.busy){Text("Format: ${vm.importFilter.label}");Icon(Icons.Default.ExpandMore,contentDescription=null)}
                            DropdownMenu(expanded=formatMenu,onDismissRequest={formatMenu=false}) {
                                AudioImportPolicy.Filter.entries.forEach{filter->DropdownMenuItem(text={Text(filter.label)},onClick={vm.setImportFormat(filter);formatMenu=false})}
                            }
                        }
                        Button(onClick={importAudio(vm.importFilter)},enabled=!vm.busy,modifier=Modifier.fillMaxWidth().heightIn(min=52.dp)){
                            Icon(Icons.Default.AudioFile,contentDescription=null)
                            Spacer(Modifier.width(8.dp))
                            Text(if(vm.wave==null)"Import recording or video" else "Import another file")
                        }
                        vm.wave?.let{wave->
                            Text(vm.name,style=MaterialTheme.typography.headlineSmall)
                            Text("%.2f s · %d Hz · %d channels · source %s".format(wave.duration,wave.rate,wave.channels,vm.sourceRevision),color=Cyan)
                            Canvas(Modifier.fillMaxWidth().height(100.dp).semantics{contentDescription="Original waveform"}){
                                val peaks=vm.waveformPeaks
                                vm.comparison?.let{span->
                                    val from=(span.sourceStart/wave.duration).toFloat()*size.width
                                    val width=(span.duration/wave.duration).toFloat()*size.width
                                    drawRect(Amber.copy(alpha=0.13f),topLeft=Offset(from,0f),size=Size(width,size.height))
                                }
                                for(i in peaks.indices){val h=peaks[i]*size.height/2;val x=i*size.width/peaks.size;drawLine(Cyan,Offset(x,size.height/2-h),Offset(x,size.height/2+h),2f)}
                                val play=(vm.playhead/wave.duration).toFloat().coerceIn(0f,1f)*size.width
                                drawLine(Amber,Offset(play,0f),Offset(play,size.height),2f)
                            }
                            ReviewPlayback(vm)
                            var showAdvanced by rememberSaveable{mutableStateOf(false)}
                            Text("Clean up",style=MaterialTheme.typography.titleMedium)
                            ToggleRow("Voice EQ",vm.voice,{vm.voice=it},!vm.busy)
                            TextButton(onClick={showAdvanced=!showAdvanced}){Text(if(showAdvanced)"Hide range and levels" else "Range and levels")}
                            if(showAdvanced) {
                                Field("Start (seconds)",vm.start,{vm.start=it},!vm.busy)
                                Field("End (seconds)",vm.end,{vm.end=it},!vm.busy)
                                Text("Gain %.1f dB".format(vm.gain));Slider(value=vm.gain,onValueChange={vm.gain=it},valueRange=-24f..12f,enabled=!vm.busy)
                                ToggleRow("Normalize peak to −1 dBFS",vm.normalize,{vm.normalize=it},!vm.busy)
                                if(vm.importAnalysis.isNotBlank())Text(vm.importAnalysis,style=MaterialTheme.typography.bodySmall)
                            }
                            Button(onClick={vm.edit()},enabled=!vm.busy,modifier=Modifier.fillMaxWidth().heightIn(min=48.dp)){Text("Improve on this device")}
                            ReviewExports(vm,share)
                            OutlinedButton(onClick={tab=1},enabled=!vm.busy){Icon(Icons.Default.Computer,contentDescription=null);Spacer(Modifier.width(8.dp));Text(if(vm.connected)"Send to ${vm.macName}" else "Connect a Mac")}
                        } ?: Text("Edit locally. Files are filtered by the chosen format. Some providers show disabled files.",color=MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                    1->{
                        Heading("ENCRYPTED CONNECTION","Your Mac connection",if(vm.paired)"Your connection and processing mode at a glance." else "On the Mac, open Edge Cluster → Mobile devices & connections. Show the pairing QR code, then scan it here. Keep both devices on the same Wi-Fi or hotspot.")
                        if(vm.paired) {
                            Card(Modifier.fillMaxWidth()) { Column(Modifier.padding(18.dp),verticalArrangement=Arrangement.spacedBy(8.dp)) {
                                Text(if(vm.connected)"CONNECTED · ENCRYPTED" else "SAVED MAC · CHECKING / OFFLINE",color=if(vm.connected)Cyan else MaterialTheme.colorScheme.onSurfaceVariant)
                                Text(vm.macName,style=MaterialTheme.typography.titleLarge)
                                Text(vm.macEndpoint,style=MaterialTheme.typography.bodyMedium)
                                Text(if(vm.workerRunning)"Mode: Audio transfer + help Mac with Voice EQ" else "Mode: Audio transfer · processing contribution off")
                                Text(vm.latencyMs?.let{"Last round trip: $it ms (not Wi-Fi signal strength)"} ?: "No recent response. Keep the Mac session and this app open.",style=MaterialTheme.typography.bodySmall)

                            } }
                        }
                        if(!vm.paired) {
                        Button(onClick={scanError=null;scanner.launch(ScanOptions().setCaptureActivity(PairingCaptureActivity::class.java).setDesiredBarcodeFormats(ScanOptions.QR_CODE).setPrompt("Scan the QR in your Mac's AudioEnhancerMAX Edge Cluster").setBeepEnabled(false).setBarcodeImageEnabled(false))},enabled=!vm.busy,modifier=Modifier.fillMaxWidth().heightIn(min=52.dp)) {
                            Icon(Icons.Default.QrCodeScanner,contentDescription=null);Spacer(Modifier.width(10.dp));Text("Scan QR code")
                        }
                        Text("The camera reads the code locally. No photo is saved or uploaded.",style=MaterialTheme.typography.bodySmall)
                        scanError?.let{Text(it,color=MaterialTheme.colorScheme.error)}
                        TextButton(onClick={manualPairing=!manualPairing}){Text(if(manualPairing)"Hide manual pairing" else "Manual pairing alternative")}
                        if(manualPairing){
                            OutlinedTextField(value=code,onValueChange={code=it.take(4096)},label={Text("Private pairing code")},visualTransformation=PasswordVisualTransformation(),modifier=Modifier.fillMaxWidth(),enabled=!vm.busy)
                            Button(onClick={vm.connect(code);code=""},enabled=code.isNotBlank() && !vm.busy){Text("Connect")}
                        }
                        }
                        if(vm.busy)Text(vm.macState,color=Cyan)
                        if(vm.paired){Row{TextButton(onClick={vm.reconnect()},enabled=!vm.busy){Text("Reconnect")};TextButton(onClick={vm.disconnect()},enabled=!vm.busy){Text("Disconnect / change Mac")}}}
                        Card(Modifier.fillMaxWidth()){Column(Modifier.padding(18.dp),verticalArrangement=Arrangement.spacedBy(12.dp)){
                            Text("Device assessment",style=MaterialTheme.typography.titleLarge)
                            Text(vm.assessmentText,style=MaterialTheme.typography.bodyMedium)
                            OutlinedButton(onClick={vm.assessDevice()},enabled=!vm.busy && !vm.workerRunning){Text("Run local assessment again")}
                            HorizontalDivider()
                            ToggleRow("Help Mac process audio",vm.workerRunning,{if(it)vm.startWorker() else vm.stopWorker()},!vm.busy && (vm.connected || vm.workerRunning))
                            Text(if(vm.workerRunning)"Voice EQ active · ${vm.completions} chunks completed · ${vm.workerState}" else "Optional. Uses this same connection, with no second pairing.")
                            Text("Voice EQ only. Keep the app open. Backgrounding, heat, local editing or sending audio stops the contribution. On the Mac, enable trusted-LAN processing to use it. No AI models are delegated to this phone.",style=MaterialTheme.typography.bodySmall)
                        }}
                        HorizontalDivider();Text("Process on Mac",style=MaterialTheme.typography.titleMedium);Text(vm.name)
                        ToggleRow("Send current result",vm.sendResult,{vm.sendResult=it},!vm.busy && vm.result!=null)
                        if(vm.wave!=null)Text(vm.transferSelection)
                        ToggleRow("Voice EQ + level",profile=="voice",{profile=if(it)"voice" else "level"},!vm.busy)
                        Button(onClick={vm.processOnMac(profile)},enabled=vm.connected && vm.wave!=null && !vm.busy && !vm.hasPendingJob,modifier=Modifier.fillMaxWidth().heightIn(min=48.dp)){Text(if(vm.connected)"Send to ${vm.macName}" else "Send to Mac")}
                        if(vm.hasPendingJob)TextButton(onClick={vm.recover()},enabled=vm.connected && !vm.busy){Text("Recover job")}
                        Text(vm.macState,style=MaterialTheme.typography.bodyMedium,color=Cyan)
                        Text("This sends the selected audio over the encrypted local connection. Results are checked against their SHA-256. Keep the Mac app and session open.",style=MaterialTheme.typography.bodySmall)
                        if(vm.result!=null)ReviewExports(vm,share)
                    }
                    2->{
                        Heading("LOCAL · TEXT ONLY","Shape the music.","Build a music brief without a model or network. Drafts save automatically. This does not generate audio.")
                        var presetsOpen by remember{mutableStateOf(false)}
                        Box{OutlinedButton(onClick={presetsOpen=true}){Text("Choose a preset")};DropdownMenu(expanded=presetsOpen,onDismissRequest={presetsOpen=false}){listOf("Podcast intro","Narration bed","Documentary arc","Calm focus","Energetic opener","Acoustic story").forEach{preset->DropdownMenuItem(text={Text(preset)},onClick={vm.updateMusic(vm.music.copy(style=preset,instruments=if(preset=="Acoustic story")"Acoustic guitar, piano" else "Piano, strings, gentle percussion"));presetsOpen=false})}}}
                        Field("Describe the music",vm.music.description,{vm.updateMusic(vm.music.copy(description=it))})
                        Field("Style",vm.music.style,{vm.updateMusic(vm.music.copy(style=it))})
                        Field("Instruments",vm.music.instruments,{vm.updateMusic(vm.music.copy(instruments=it))})
                        Field("Avoid",vm.music.exclusions,{vm.updateMusic(vm.music.copy(exclusions=it))})
                        Field("Vocals",vm.music.vocals,{vm.updateMusic(vm.music.copy(vocals=it))})
                        Field("Duration (seconds)",vm.music.duration,{vm.updateMusic(vm.music.copy(duration=it))})
                        Field("BPM",vm.music.bpm,{vm.updateMusic(vm.music.copy(bpm=it))})
                        Field("Arrangement",vm.music.arrangement,{vm.updateMusic(vm.music.copy(arrangement=it))})
                        Field("Separate lyrics",vm.music.lyrics,{vm.updateMusic(vm.music.copy(lyrics=it))})
                        Button(onClick={vm.buildBrief()}){Text("Build brief")}
                        Field("Editable prompt",vm.music.prompt,{vm.updateMusic(vm.music.copy(prompt=it))})
                        if(!vm.music.canExport)Text("Rebuild after changing directions. Lyrics stay separate.",style=MaterialTheme.typography.bodySmall)
                        OutlinedButton(onClick={context.startActivity(Intent.createChooser(Intent(Intent.ACTION_SEND).setType("text/plain").putExtra(Intent.EXTRA_TEXT,vm.music.prompt),"Share music prompt"))},enabled=vm.music.canExport){Text("Share prompt")}
                        Button(onClick={vm.exportBrief()?.let(share)},enabled=vm.music.canExport){Text("Export JSON")}
                        OutlinedButton(onClick=importBrief){Text("Import saved JSON")}
                    }
                }
                if(vm.busy){LinearProgressIndicator(Modifier.fillMaxWidth());Text(if(tab==1)vm.macState else "Working…")}
                Text("Companion preview · $installedVersion",style=MaterialTheme.typography.labelSmall,color=MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
        vm.error?.let{message->AlertDialog(onDismissRequest={vm.error=null},title={Text("AudioEnhancerMAX")},text={Text(message)},confirmButton={TextButton(onClick={vm.error=null}){Text("OK")}})}
    }
}
@Composable private fun Heading(eyebrow:String,title:String,description:String){Text(eyebrow,color=Cyan,style=MaterialTheme.typography.labelMedium);Text(title,fontSize=32.sp,fontWeight=FontWeight.Bold,lineHeight=38.sp);Text(description,color=MaterialTheme.colorScheme.onSurfaceVariant)}
@Composable private fun Field(label:String,value:String,change:(String)->Unit,enabled:Boolean=true){OutlinedTextField(value=value,onValueChange={change(it.take(12000))},label={Text(label)},modifier=Modifier.fillMaxWidth(),enabled=enabled)}
@Composable private fun ToggleRow(label:String,value:Boolean,change:(Boolean)->Unit,enabled:Boolean=true){Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.SpaceBetween){Text(label,modifier=Modifier.weight(1f).padding(top=12.dp));Switch(checked=value,onCheckedChange=change,enabled=enabled)}}
@Composable private fun ReviewPlayback(vm:CompanionViewModel){
    Text("Listen",style=MaterialTheme.typography.titleMedium)
    val span=vm.comparison
    if(span!=null || vm.result==null) {
        val start=span?.sourceStart?.toFloat() ?: 0f
        val end=(span?.let{it.sourceStart+it.duration} ?: vm.wave?.duration ?: 0.01).toFloat()
        var draft by remember(vm.sourceRevision,vm.resultRevision){mutableStateOf<Float?>(null)}
        Slider(value=(draft ?: vm.playhead).coerceIn(start,end),onValueChange={draft=it},
            onValueChangeFinished={draft?.let(vm::seekPlayback);draft=null},valueRange=start..end,
            modifier=Modifier.semantics{contentDescription="Playback position in the original recording"})
    }
    Row(horizontalArrangement=Arrangement.spacedBy(8.dp)){
        OutlinedButton(onClick={vm.play(true)},modifier=Modifier.weight(1f)){Text("A · Original")}
        OutlinedButton(onClick={vm.play(false)},enabled=vm.result!=null,modifier=Modifier.weight(1f)){Text("B · Result")}
        IconButton(onClick=vm::stopPlayback,enabled=vm.playbackState!="Stopped"){Icon(Icons.Default.Stop,contentDescription="Stop playback")}
    }
    Text("%.1f s · %s".format(vm.playhead,vm.playbackState),style=MaterialTheme.typography.bodySmall)
    if(span!=null)ToggleRow("Match listening levels",vm.matchListeningLevels,vm::setListeningLevelMatched)
    else if(vm.result!=null)Text("Independent playback for this saved result.",style=MaterialTheme.typography.bodySmall)
}
@Composable private fun ReviewExports(vm:CompanionViewModel,share:(File)->Unit){
    vm.result?.let{file->
        Text("Result · ${vm.resultRevision}",style=MaterialTheme.typography.titleSmall)
        Button(onClick={share(file)},enabled=!vm.busy){Text("Export WAV")}
    }
    if(vm.videoSource!=null){
        Text("Video audio extracted. Improve the full duration without trimming to keep the video synchronized. Auxiliary tracks are not exported.",style=MaterialTheme.typography.bodySmall)
        Button(onClick={vm.exportVideo()},enabled=vm.result!=null && !vm.busy){Text("Prepare MP4 with improved audio")}
        vm.videoResult?.let{file->Button(onClick={share(file)},enabled=!vm.busy){Text("Export MP4 copy")}}
    }
    vm.report?.let{file->TextButton(onClick={share(file)},enabled=!vm.busy){Text("Export Mac report")}}
}
