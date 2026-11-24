package com.audioenhancermax.worker

import android.app.Application
import android.media.MediaPlayer
import android.net.Uri
import android.os.Build
import android.os.PowerManager
import android.os.SystemClock
import androidx.compose.runtime.*
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.google.gson.Gson
import com.google.gson.JsonObject
import com.google.gson.JsonParser
import kotlinx.coroutines.*
import java.io.File
import java.io.IOException
import java.util.UUID
import javax.net.ssl.SSLException
import kotlin.math.roundToInt

private data class ResultReceipt(
    val sourceSha: String,
    val resultSha: String,
    val comparison: AudioComparison?,
    val reportSha: String? = null,
    val edit: WorkspaceEdit? = null,
)

private data class RestoredSource(val wave: Wave, val sha256: String, val peaks: FloatArray)
private data class RestoredResult(val file: File, val sha256: String, val receipt: ResultReceipt?, val report: File?)

private data class WorkspaceRevision(val receipt: ResultReceipt?, val edit: WorkspaceEdit)

internal data class NearbyComparison(val name: String, val code: String, val awaitingMac: Boolean = false)

private data class NearbyAttempt(
    val mac: NearbyMac,
    val client: NearbyPairingClient,
    val reveal: Map<String, String>,
    val expiresAt: Long
)

class CompanionViewModel(app:Application):AndroidViewModel(app) {
    private val prefs=app.getSharedPreferences("companion",0)
    var importFilter by mutableStateOf(runCatching{AudioImportPolicy.Filter.valueOf(prefs.getString("importFilter","ALL")!!)}.getOrDefault(AudioImportPolicy.Filter.ALL))
        private set
    fun setImportFormat(filter:AudioImportPolicy.Filter){importFilter=filter;prefs.edit().putString("importFilter",filter.name).apply()}
    private val secure=SecurePairing(app)
    private val gson=Gson()
    private val device=prefs.getString("device",null) ?: UUID.randomUUID().toString().also{prefs.edit().putString("device",it).apply()}
    val exports=File(app.filesDir,"exports").apply{mkdirs()}
    private val original=File(app.filesDir,"original.wav")
    var importAnalysis by mutableStateOf(prefs.getString("importAnalysis", "" ) ?: "");private set
    var wave by mutableStateOf<Wave?>(null);private set
    var waveformPeaks by mutableStateOf(FloatArray(0));private set
    var videoSource by mutableStateOf<File?>(null);private set
    var videoResult by mutableStateOf<File?>(null);private set
    var name by mutableStateOf(prefs.getString("name","No audio imported")!!);private set
    var result by mutableStateOf<File?>(null);private set
    var error by mutableStateOf<String?>(null)
    var busy by mutableStateOf(true);private set
    var restoringStudio by mutableStateOf(true);private set
    var macState by mutableStateOf("Not connected");private set
    var connected by mutableStateOf(false);private set
    var macName by mutableStateOf(prefs.getString("macName", "Saved Mac") ?: "Saved Mac");private set
    var macEndpoint by mutableStateOf("");private set
    var latencyMs by mutableStateOf<Long?>(null);private set
    internal var macAcceptsWorker by mutableStateOf<Boolean?>(null);private set
    internal var nearbyMacs by mutableStateOf<List<NearbyMac>>(emptyList());private set
    internal var nearbySearching by mutableStateOf(false);private set
    internal var nearbyMessage by mutableStateOf<String?>(null);private set
    internal var nearbyComparison by mutableStateOf<NearbyComparison?>(null);private set
    internal var phoneDiscoverable by mutableStateOf(false);private set
    internal var phoneVisibleUntil by mutableStateOf<Long?>(null);private set
    internal var phoneAdvertised by mutableStateOf(false);private set
    internal var phoneInvitations by mutableStateOf<List<NearbyMac>>(emptyList());private set
    private val discovery by lazy { NearbyMacDiscovery(app) }
    private var searchTimer: Job? = null
    private var phoneAdvertisement: PhonePairingAdvertisement? = null
    private var phoneWindow: Job? = null
    private var nearbyOperation: Job? = null
    private var nearbyEpoch = 0
    private var nearbyExpiry: Job? = null
    private var nearbyAttempt: NearbyAttempt? = null
    private var presence:Job?=null
    private suspend fun readConnection(api: CompanionClient): Pair<JsonObject,Long> {
        val began=android.os.SystemClock.elapsedRealtime()
        val state=api.request("/v1/status").json()
        return state to (android.os.SystemClock.elapsedRealtime()-began)
    }
    private fun updateConnection(api: CompanionClient, state: JsonObject, latency: Long) {
        latencyMs=latency
        DeviceAssessment.roundTripMs=latency
        assessmentText=DeviceAssessment.summary(getApplication<Application>())
        val name = state.get("mac_name")?.asString?.take(120) ?: "AudioEnhancerMAX Mac"
        if (name != macName) prefs.edit().putString("macName", name).apply()
        macName=name
        macAcceptsWorker = state.get("trusted_lan_processing")?.takeIf { it.isJsonPrimitive && it.asJsonPrimitive.isBoolean }?.asBoolean
        macEndpoint=api.pairing.endpoint;connected=true
    }
    private suspend fun checkConnection(api:CompanionClient) {
        val (state,latency)=readConnection(api)
        if(client === api) updateConnection(api,state,latency)
    }
    fun startPresence() {
        if(presence?.isActive==true)return
        presence=viewModelScope.launch {
            while(isActive) {
                val api=client
                if(api!=null && !busy) try {checkConnection(api)} catch(e:Exception) {
                    if(e is CancellationException)throw e
                    connected=false;latencyMs=null;macAcceptsWorker=null
                }
                delay(5000)
            }
        }
    }
    fun stopPresence(){presence?.cancel();presence=null;connected=false;latencyMs=null;macAcceptsWorker=null}
    var assessmentText by mutableStateOf(DeviceAssessment.summary(app));private set
    fun assessDevice()=action {
        stopWorker()
        withContext(Dispatchers.Default){DeviceAssessment.benchmark()}
        assessmentText=DeviceAssessment.summary(getApplication<Application>())
        client?.let{runCatching{checkConnection(it)}}
    }
    var paired by mutableStateOf(false);private set
    var workerRunning by mutableStateOf(false);private set
    var workerState by mutableStateOf("Stopped");private set
    internal var workerUsage by mutableStateOf(WorkerUsage());private set
    internal var workerNotice by mutableStateOf<String?>(null);private set
    var playbackState by mutableStateOf("Stopped");private set
    var playhead by mutableFloatStateOf(0f);private set
    var comparison by mutableStateOf<AudioComparison?>(null);private set
    var matchListeningLevels by mutableStateOf(true);private set
    var sourceRevision by mutableStateOf("");private set
    var resultRevision by mutableStateOf("");private set
    var hasPendingJob by mutableStateOf(prefs.contains("pendingJob"));private set
    val transferSelection: String
        get() = if (sendResult) "Current result · $resultRevision" else "Imported audio · $sourceRevision"
    var start by mutableStateOf("0");var end by mutableStateOf("1");var gain by mutableFloatStateOf(0f)
    var sendResult by mutableStateOf(false)
    var normalize by mutableStateOf(true);var voice by mutableStateOf(false)
    var fadeIn by mutableFloatStateOf(0f)
    var fadeOut by mutableFloatStateOf(0f)
    var loopPlayback by mutableStateOf(false)
    private val undoRevisions = mutableStateListOf<WorkspaceRevision>()
    private val redoRevisions = mutableStateListOf<WorkspaceRevision>()
    private var resultReceipt: ResultReceipt? = null
    val canUndoEdit: Boolean get() = undoRevisions.isNotEmpty()
    val canRedoEdit: Boolean get() = redoRevisions.isNotEmpty()
    var music by mutableStateOf(MusicDraft());private set
    var report by mutableStateOf<File?>(null);private set
    private var client:CompanionClient?=null
    private var worker:Job?=null
    private var stopJob:Job?=null
    private var workerEpoch=0
    private var player:MediaPlayer?=null
    private var playbackTracking: Job? = null
    private var playingOriginal = true
    private var playerReady = false
    private var playbackWindow: ClosedFloatingPointRange<Double>? = null
    private var sourceSha = ""
    init {
        viewModelScope.launch {withContext(Dispatchers.Default){runCatching{DeviceAssessment.benchmark()}};assessmentText=DeviceAssessment.summary(app)}
        secure.load()?.let{client=CompanionClient(it,device){DeviceAssessment.header(app)};macEndpoint=it.endpoint;paired=true;macState="Paired · reconnect to check"}
        viewModelScope.launch {
            try {
                restoreStudio()
            } finally {
                restoringStudio = false
                busy = false
            }
        }
        runCatching {prefs.getString("music",null)?.let{music=parseMusic(it)}}
    }

    private suspend fun restoreStudio() {
        val source = withContext(Dispatchers.IO) {
            runCatching {
                if (!original.exists()) return@runCatching null
                val bytes = original.readBytes()
                val audio = Wave.decode(bytes)
                RestoredSource(audio, sha256(bytes), audio.overview(320))
            }
        }.getOrElse {
            error = "Studio could not reopen the saved audio. Choose a file to start a new revision."
            return
        }
        val video = withContext(Dispatchers.IO) {
            val videoName = prefs.getString("videoSource", null)
            val attached = videoName?.takeIf {
                it.startsWith("media-import-") && "/" !in it && source != null &&
                    prefs.getString("videoWaveHash", null) == source.sha256
            }?.let { File(original.parentFile, it).takeIf(File::isFile) }
            original.parentFile?.listFiles()?.filter {
                it != attached && Regex("""media-import-[0-9]+\.bin""").matches(it.name)
            }?.forEach { it.delete() }
            exports.listFiles()?.filter {
                it.name.startsWith("enhanced-") && it.extension == "mp4" &&
                    runCatching { UUID.fromString(it.nameWithoutExtension.removePrefix("enhanced-")) }.isSuccess
            }?.forEach { it.delete() }
            attached
        }
        if (source == null) return

        val savedResult = withContext(Dispatchers.IO) {
            runCatching { readSavedResult(source.sha256) }.getOrNull()
        }
        sourceSha = source.sha256
        sourceRevision = source.sha256.take(8)
        wave = source.wave
        end = source.wave.duration.toString()
        waveformPeaks = source.peaks
        videoSource = video
        if (savedResult != null) {
            resultReceipt = savedResult.receipt
            savedResult.receipt?.edit?.let(::restoreEdit)
            result = savedResult.file
            resultRevision = savedResult.sha256.take(8)
            comparison = savedResult.receipt?.comparison
            playhead = (comparison?.sourceStart ?: 0.0).toFloat()
            report = savedResult.report
        } else if (prefs.contains("resultReceipt")) {
            error = "The last revision could not be verified. Your original audio is ready in Studio."
        }
    }

    private fun action(block:suspend()->Unit) {
        if(busy)return
        busy=true
        viewModelScope.launch {
            try{block()}catch(e:Exception){if(e !is CancellationException)error=e.message ?: "Operation failed"}finally{busy=false}
        }
    }
    private fun write(file:File,data:ByteArray) {val temp=File(file.parentFile,"${file.name}.tmp");temp.writeBytes(data);check(temp.renameTo(file)){"Could not save result"}}
    private fun readSavedResult(sourceDigest: String): RestoredResult? {
        val receipt = prefs.getString("resultReceipt", null)?.let { gson.fromJson(it, ResultReceipt::class.java) }
        if (receipt == null && prefs.getBoolean("versionedWorkspace", false)) return null
        if (receipt != null && receipt.sourceSha != sourceDigest) return null
        val audio = if (receipt == null) File(exports, "result.wav") else resultFile(receipt.resultSha)
        if (!audio.isFile) return null
        val digest = sha256(audio.readBytes())
        if (receipt != null && receipt.resultSha != digest) return null
        val metadata = if (receipt == null) File(exports, "mac-report.json") else receipt.reportSha?.let(::reportFile)
        val verifiedReport = metadata?.takeIf { it.isFile }?.let { candidate ->
            runCatching {
                val bytes = candidate.readBytes()
                val json = JsonParser.parseString(bytes.decodeToString()).asJsonObject
                candidate.takeIf {
                    json["sha256"]?.asString == digest && (receipt?.reportSha == null || sha256(bytes) == receipt.reportSha)
                }
            }.getOrNull()
        }
        return RestoredResult(audio, digest, receipt, verifiedReport)
    }

    private fun resultFile(digest: String): File {
        require(Regex("[0-9a-f]{64}").matches(digest))
        return File(exports,"result-$digest.wav")
    }
    private fun reportFile(digest: String): File {
        require(Regex("[0-9a-f]{64}").matches(digest))
        return File(exports,"mac-report-$digest.json")
    }
    private fun pruneResultFiles(keep: Set<File?>) {
        val managed=Regex("(result-[0-9a-f]{64}\\.wav|mac-report-[0-9a-f]{64}\\.json)")
        exports.listFiles()?.filter{it !in keep && managed.matches(it.name)}?.forEach{it.delete()}
    }
    private fun draftEdit() = WorkspaceEdit(start, end, gain, normalize, voice, fadeIn, fadeOut)

    fun currentSelection(): ClosedFloatingPointRange<Double>? = wave?.let { draftEdit().selection(it.duration) }

    private fun fullEdit() = WorkspaceEdit("0", (wave?.duration ?: 1.0).toString(), 0f, false, false)

    fun setStudioRange(from: Float, to: Float) {
        if (from >= to) return
        start = from.toDouble().toString()
        end = if (to >= (wave?.duration ?: 1.0).toFloat()) {
            (wave?.duration ?: 1.0).toString()
        } else to.toDouble().toString()
    }

    fun resetStudioRange() {
        start = "0"
        end = (wave?.duration ?: 1.0).toString()
    }

    private fun restoreEdit(edit: WorkspaceEdit) {
        start=edit.start;end=edit.end;gain=edit.gain;normalize=edit.normalize;voice=edit.voice
        fadeIn=edit.fadeIn;fadeOut=edit.fadeOut
    }

    private fun trimHistory(history: MutableList<WorkspaceRevision>) {
        if (history.size > 3) history.removeAt(0)
    }

    private fun savedRevision() = WorkspaceRevision(resultReceipt, resultReceipt?.edit ?: fullEdit())

    private fun moveRevision(from: MutableList<WorkspaceRevision>, to: MutableList<WorkspaceRevision>) {
        if (busy || from.isEmpty()) return
        to.add(savedRevision())
        trimHistory(to)
        showRevision(from.removeAt(from.lastIndex), restoreControls = true)
    }

    fun undoEdit() = moveRevision(undoRevisions, redoRevisions)
    fun redoEdit() = moveRevision(redoRevisions, undoRevisions)

    private fun showRevision(revision: WorkspaceRevision, restoreControls: Boolean) {
        val receipt = revision.receipt
        stopPlayback()
        val target = receipt?.resultSha?.let(::resultFile)
        val metadata = receipt?.reportSha?.let(::reportFile)
        val recentShare = setOf(result, report)
        val editor = prefs.edit().putBoolean("versionedWorkspace", true)
        if (receipt == null) editor.remove("resultReceipt") else editor.putString("resultReceipt", gson.toJson(receipt))
        editor.apply()
        resultReceipt=receipt
        result=target
        resultRevision=receipt?.resultSha?.take(8).orEmpty()
        comparison=receipt?.comparison
        playhead=(comparison?.sourceStart ?: 0.0).toFloat()
        report=metadata
        sendResult=target!=null
        invalidateVideoExport()
        if (restoreControls) restoreEdit(revision.edit)
        val retained = (undoRevisions + redoRevisions).flatMap { item ->
            listOf(item.receipt?.resultSha?.let(::resultFile), item.receipt?.reportSha?.let(::reportFile))
        }.toSet()
        pruneResultFiles(retained + recentShare + setOf(target, metadata))
    }

    private fun setResult(
        resultSha: String,
        alignment: AudioComparison?,
        reportSha: String? = null,
        edit: WorkspaceEdit? = null,
    ) {
        undoRevisions.add(savedRevision())
        trimHistory(undoRevisions)
        redoRevisions.clear()
        showRevision(WorkspaceRevision(ResultReceipt(sourceSha,resultSha,alignment,reportSha,edit), edit ?: draftEdit()),
            restoreControls = false)
    }
    private fun clearPendingJob() {
        hasPendingJob=false
        prefs.edit().remove("pendingJob").remove("pendingSourceSha").remove("pendingSourceStart").remove("pendingWorkspaceSha").apply()
    }
    fun importAudio(uri:Uri,label:String) = action {
        stopWorker()
        val imported=withContext(Dispatchers.IO){AudioImporter.decode(getApplication<Application>(),uri,importFilter)}
        val parsed=imported.wave
        val analysis=imported.analysis
        val digest=try {
            withContext(Dispatchers.IO){
                val bytes=parsed.encode()
                write(original,bytes)
                sha256(bytes)
            }
        } catch(e:Exception){imported.video?.delete();throw e}
        val previousVideo=videoSource
        videoSource=imported.video;invalidateVideoExport()
        prefs.edit().putString("videoSource",imported.video?.name).putString("videoWaveHash",if(imported.video!=null)digest else null).apply()
        previousVideo?.delete()
        importAnalysis=analysis;prefs.edit().putString("importAnalysis",analysis).apply()
        withContext(Dispatchers.IO){File(exports,"result.wav").delete();File(exports,"mac-report.json").delete()}
        stopPlayback();wave=parsed;waveformPeaks=imported.overview;name=label;result=null;report=null;sendResult=false
        restoreEdit(fullEdit());resultReceipt=null;undoRevisions.clear();redoRevisions.clear()
        sourceSha=digest;sourceRevision=digest.take(8);resultRevision="";comparison=null;playhead=0f
        prefs.edit().putString("name",label).putBoolean("versionedWorkspace",true).remove("resultReceipt").apply()
        clearPendingJob()
        withContext(Dispatchers.IO){pruneResultFiles(emptySet())}
    }
    fun edit() = renderEdit(silence = false)
    fun silenceSelection() = renderEdit(silence = true)

    private fun renderEdit(silence: Boolean) = action {
        stopWorker();val source=requireNotNull(wave){"Import audio first"}
        val edit=draftEdit().copy(silence = silence)
        val (digest,alignment)=withContext(Dispatchers.IO) {
            val (edited, comparison)=edit.process(source)
            val bytes=edited.encode()
            val digest=sha256(bytes)
            write(resultFile(digest),bytes)
            File(exports,"mac-report.json").delete()
            digest to comparison
        }
        setResult(digest,alignment,edit=edit)
    }
    private fun invalidateVideoExport(){videoResult?.delete();videoResult=null}
    fun exportVideo()=action {
        val video=requireNotNull(videoSource){"Import MP4 first"}
        val audio=requireNotNull(result){"Improve the audio first"}
        val source=requireNotNull(wave)
        stopWorker();stopPlayback()
        val output=File(exports,"enhanced-${UUID.randomUUID()}.mp4")
        withContext(Dispatchers.IO){VideoExport.replace(video,Wave.decode(audio.readBytes()),source,output)}
        invalidateVideoExport();videoResult=output
    }
    internal fun findNearbyMacs() {
        if (busy || paired || nearbyComparison != null) return
        stopPhoneDiscovery()
        stopNearbyDiscovery()
        nearbySearching = true
        nearbyMacs = emptyList()
        nearbyMessage = null
        discovery.start(update = { nearbyMacs = it }, failure = {
            stopNearbyDiscovery()
            nearbyMessage = "Nearby discovery is unavailable. Check Wi-Fi or use the QR code."
        })
        if (nearbySearching) searchTimer = viewModelScope.launch {
            delay(12_000)
            stopNearbyDiscovery()
            if (nearbyMacs.isEmpty()) {
                nearbyMessage = "No Macs found. Open nearby pairing on the Mac. Use the same Wi-Fi or a hotspot that lets devices see each other."
            }
        }
    }

    private fun stopNearbyDiscovery() {
        searchTimer?.cancel()
        searchTimer = null
        if (nearbySearching) discovery.stop()
        nearbySearching = false
    }

    internal fun makePhoneDiscoverable() {
        if (busy || paired || nearbyComparison != null || phoneDiscoverable) return
        stopNearbyDiscovery()
        nearbyMacs = emptyList()
        nearbyMessage = null
        phoneDiscoverable = true
        phoneVisibleUntil = SystemClock.elapsedRealtime() + 90_000
        val announcement = PhonePairingAdvertisement(getApplication<Application>())
        phoneAdvertisement = announcement
        phoneWindow = viewModelScope.launch {
            try {
                withTimeout(90_000) {
                    announcement.listen(ready = { phoneAdvertised = true }) { mac ->
                        if (phoneAdvertisement === announcement && phoneInvitations.size < 8 &&
                            phoneInvitations.none { it.endpoint == mac.endpoint }) {
                            phoneInvitations = phoneInvitations + mac
                        }
                    }
                }
            } catch (_: TimeoutCancellationException) {
                if (phoneAdvertisement === announcement)
                    nearbyMessage = "Phone discovery ended. Make this phone discoverable again to retry."
            } catch (e: Exception) {
                if (e is CancellationException) throw e
                if (phoneAdvertisement === announcement)
                    nearbyMessage = "The phone could not advertise on this network. Check Wi-Fi or try Find nearby Macs."
            } finally {
                announcement.close()
                if (phoneAdvertisement === announcement) {
                    phoneAdvertisement = null
                    phoneWindow = null
                    phoneDiscoverable = false
                    phoneVisibleUntil = null
                    phoneAdvertised = false
                    phoneInvitations = emptyList()
                }
            }
        }
    }

    private fun stopPhoneDiscovery() {
        val announcement = phoneAdvertisement
        phoneAdvertisement = null
        phoneWindow?.cancel()
        phoneWindow = null
        announcement?.close()
        phoneDiscoverable = false
        phoneVisibleUntil = null
        phoneAdvertised = false
        phoneInvitations = emptyList()
    }

    internal fun beginNearbyPairing(mac: NearbyMac) {
        if (busy || paired || (mac !in nearbyMacs && mac !in phoneInvitations)) return
        stopNearbyDiscovery()
        stopPhoneDiscovery()
        nearbyMacs = emptyList()
        nearbyMessage = "Connecting to ${mac.name}…"
        runNearby {
            stopWorker()
            val client = NearbyPairingClient(mac, device)
            val nonce = NearbyPairingProtocol.nonce()
            val expiresAt = android.os.SystemClock.elapsedRealtime() + 90_000
            val start = client.post(PairingStep.START, mapOf("commitment" to NearbyPairingProtocol.commitment(nonce)))
            val (requestID, serverNonce) = NearbyPairingProtocol.readStart(start)
            val reveal = mapOf("request_id" to requestID, "client_nonce" to nonce)
            val response = client.post(PairingStep.REVEAL, reveal)
            check(NearbyPairingProtocol.status(response) == "pending")
            nearbyAttempt = NearbyAttempt(mac, client, reveal, expiresAt)
            nearbyMessage = null
            nearbyComparison = NearbyComparison(mac.name, NearbyPairingProtocol.comparisonCode(mac.fingerprint, nonce, serverNonce))
            nearbyExpiry = viewModelScope.launch {
                delay((expiresAt - android.os.SystemClock.elapsedRealtime()).coerceAtLeast(0))
                cancelNearbyPairing()
                nearbyMessage = "The comparison code expired. Find your Mac again."
            }
        }
    }

    internal fun confirmNearbyCode() {
        val attempt = nearbyAttempt ?: return
        val comparison = nearbyComparison ?: return
        if (busy || comparison.awaitingMac) return
        nearbyExpiry?.cancel()
        nearbyExpiry = null
        nearbyComparison = comparison.copy(awaitingMac = true)
        runNearby {
            while (android.os.SystemClock.elapsedRealtime() < attempt.expiresAt) {
                val response = try {
                    attempt.client.post(PairingStep.FINISH, attempt.reveal)
                } catch (e: IOException) {
                    if (e is SSLException) throw e
                    delay(1500)
                    continue
                }
                if (android.os.SystemClock.elapsedRealtime() >= attempt.expiresAt) throw PairingExpired()
                when (NearbyPairingProtocol.status(response)) {
                    "pending" -> delay(1300)
                    "approved" -> {
                        val pairing = NearbyPairingProtocol.approvedPairing(attempt.mac, response)
                        completePairing(pairing)
                        nearbyAttempt = null
                        nearbyComparison = null
                        return@runNearby
                    }
                    "rejected" -> {
                        nearbyAttempt = null
                        nearbyComparison = null
                        nearbyMessage = "The Mac declined pairing. Open nearby pairing again to retry."
                        return@runNearby
                    }
                    else -> throw IllegalStateException("Invalid Mac approval response")
                }
            }
            throw PairingExpired()
        }
    }

    internal fun cancelNearbyPairing() {
        stopNearbyDiscovery()
        stopPhoneDiscovery()
        nearbyEpoch++
        if (nearbyOperation?.isActive == true) busy = false
        nearbyOperation?.cancel()
        nearbyOperation = null
        nearbyExpiry?.cancel()
        nearbyExpiry = null
        nearbyAttempt = null
        nearbyComparison = null
        nearbyMacs = emptyList()
        nearbyMessage = null
    }

    private fun runNearby(block: suspend () -> Unit) {
        val epoch = ++nearbyEpoch
        busy = true
        nearbyOperation = viewModelScope.launch {
            try {
                block()
            } catch (e: Exception) {
                if (e is CancellationException) throw e
                if (nearbyEpoch == epoch) {
                    nearbyAttempt = null
                    nearbyComparison = null
                    nearbyMessage = when (e) {
                        is PairingExpired -> "The comparison code expired. Find your Mac again."
                        is SSLException -> "The Mac identity could not be verified. Reopen pairing on the Mac and try again."
                        is IOException -> "The Mac did not respond. Use the same Wi-Fi or hotspot, or try the QR code."
                        else -> "Pairing could not complete. Reopen nearby pairing on the Mac and try again."
                    }
                }
            } finally {
                if (nearbyEpoch == epoch) {
                    busy = false
                    nearbyOperation = null
                }
            }
        }
    }

    private suspend fun completePairing(pairing: Pairing) {
        val next = CompanionClient(pairing,device){DeviceAssessment.header(getApplication<Application>())}
        val (state,latency)=readConnection(next)
        currentCoroutineContext().ensureActive()
        secure.save(pairing)
        clearPendingJob()
        workerUsage=WorkerUsage()
        workerNotice=null
        client=next;paired=true;macState="Connected · encrypted"
        updateConnection(next,state,latency)
    }

    fun connect(code:String) = action {
        stopWorker();macState="Connecting…"
        try {
            completePairing(Pairing.parse(code))
        } catch(e:Exception) {
            if (e is CancellationException) throw e
            connected=false
            macState="Connection failed"
            error=when (e) {
                is SSLException -> "The Mac identity could not be verified. Show a fresh QR code on the Mac."
                is IOException -> "The Mac did not respond. Check that both devices use the same Wi-Fi or hotspot, then try Find nearby Macs."
                else -> e.message ?: "Connection failed"
            }
        }
    }
    fun reconnect() = action {
        macState="Connecting…"
        try {checkConnection(requireNotNull(client));macState="Connected · encrypted"}catch(e:Exception){connected=false;macState="Mac unavailable";throw e}
    }
    fun disconnect(){
        stopWorker()
        connected=false;macEndpoint="";latencyMs=null;macAcceptsWorker=null;client=null;paired=false
        secure.clear();prefs.edit().remove("macName").apply();macName="Saved Mac";macState="Not connected"
        workerUsage=WorkerUsage();workerNotice=null
        clearPendingJob()
    }
    fun processOnMac(profile:String) = action {
        stopWorker();val api=requireNotNull(client){"Pair with a Mac first"};val selected=if(sendResult)requireNotNull(result){"Improve audio first"} else original;require(selected.exists()){"Import audio first"}
        try {
            require(selected.length()<=20*1024*1024){"This edit exceeds the Mac transfer limit of 20 MiB. Select and improve a shorter range, then send the result. Local export supports the full imported recording."}
            macState="Sending $transferSelection to $macName…"
            val (bytes,digest)=withContext(Dispatchers.IO){ selected.readBytes().let{it to sha256(it)} }
            val uploaded=api.request("/v1/files","POST",bytes,"wav").json()
            require(uploaded["sha256"]?.asString?.let {it==digest} != false) {"Mac upload integrity check failed"}
            val file=uploaded["id"].asString
            macState="Starting the Mac job…"
            val id=api.request("/v1/jobs","POST",gson.toJson(mapOf("file_id" to file,"profile" to profile)).toByteArray()).json()["id"].asString
            val offset=if (sendResult) comparison?.sourceStart else 0.0
            prefs.edit().putString("pendingJob",id).putString("pendingSourceSha",digest)
                .putString("pendingSourceStart",offset?.toString()).putString("pendingWorkspaceSha",sourceSha).apply()
            hasPendingJob=true
            retrieve(api,id)
        }catch(e:Exception){macState=if(hasPendingJob)"Job interrupted · use Recover job" else "Send failed · retry";throw e}
    }
    fun recover()=action{retrieve(requireNotNull(client){"Pair with a Mac first"},prefs.getString("pendingJob",null) ?: throw IllegalStateException("No pending job"))}
    private suspend fun retrieve(api:CompanionClient,id:String) {
        if(prefs.getString("pendingWorkspaceSha",sourceSha)!=sourceSha) {
            clearPendingJob()
            throw IllegalStateException("This Mac job belongs to a different recording")
        }
        repeat(90) {
            val state=api.request("/v1/jobs/$id").json()
            when(state["status"].asString) {
                "failed" -> {
                    clearPendingJob()
                    macState="Mac processing failed"
                    throw IllegalStateException(state["message"]?.asString ?: "Mac processing failed")
                }
                "completed" -> {
                    macState="Downloading and verifying the Mac result…"
                    val bytes=api.request("/v1/jobs/$id/audio").bytes
                    val digest=withContext(Dispatchers.Default){sha256(bytes)}
                    require(digest==state["sha256"].asString){"Result integrity check failed"}
                    val pendingSha=prefs.getString("pendingSourceSha",null)
                    require(state["source_sha256"]?.asString?.let {pendingSha==null || it==pendingSha} != false) {"Mac result refers to a different source"}
                    val json=api.request("/v1/jobs/$id/report").bytes
                    val contents=JsonParser.parseString(String(json)).asJsonObject
                    require(contents["sha256"].asString==digest){"Report integrity check failed"}
                    require(contents["source_sha256"]?.asString?.let {pendingSha==null || it==pendingSha} != false) {"Mac report refers to a different source"}
                    val offset=prefs.getString("pendingSourceStart",null)?.toDoubleOrNull()
                    val (reportSha,alignment)=withContext(Dispatchers.IO){
                        val output=Wave.decode(bytes)
                        val aligned=wave?.let { source -> offset?.let {AudioComparison.match(source,output,it)} }
                        val reportSha=sha256(json)
                        write(resultFile(digest),bytes)
                        write(reportFile(reportSha),json)
                        reportSha to aligned
                    }
                    setResult(digest,alignment,reportSha)
                    macState="Completed · revision $resultRevision · SHA-256 verified"
                    clearPendingJob()
                    return
                }
            }
            macState="Processing on Mac…";delay(2000)
        }
        throw IllegalStateException("Still working on the Mac. Use Recover job later")
    }
    fun startWorker() {
        if(busy || workerRunning)return
        val api=client ?: run{error="Pair with your Mac first";return}
        workerEpoch++;val epoch=workerEpoch;val previousStop=stopJob
        workerRunning=true;workerState="Checking Mac";workerNotice=null
        worker=viewModelScope.launch {
            var stoppedState="Stopped"
            try {
                previousStop?.join();ensureActive()
                while(isActive) {
                    if(Build.VERSION.SDK_INT>=29) {
                        val power=getApplication<Application>().getSystemService(PowerManager::class.java)
                        check(power.currentThermalStatus<PowerManager.THERMAL_STATUS_SEVERE){"Worker paused: device is warm"}
                    }
                    val response=api.request("/v1/worker/next");ensureActive()
                    response.taskID?.let{id ->
                        require(response.filter=="auto_eq" && response.bytes.size<=2*1024*1024){"Unsupported worker task"}
                        workerState="Processing · Voice EQ"
                        val (bytes, stats) = withContext(Dispatchers.Default) {
                            val source = Wave.decode(response.bytes)
                            val began = SystemClock.elapsedRealtimeNanos()
                            val processed = source.autoEQ()
                            val elapsed = (SystemClock.elapsedRealtimeNanos() - began) / 1e6
                            processed.encode() to (source.duration to elapsed)
                        }
                        ensureActive()
                        workerState="Returning chunk"
                        api.request("/v1/worker/result/$id","POST",bytes)
                        ensureActive()
                        workerUsage=workerUsage.add(stats.first, stats.second)
                    }
                    workerState="Waiting for Mac";delay(2000)
                }
            } catch (e: Exception) {
                if (e !is CancellationException && epoch == workerEpoch) {
                    workerNotice = if (e is IOException) "The connection dropped. Keep both apps open on the same Wi-Fi."
                        else e.message ?: "Reconnect to the Mac and try again."
                    stoppedState = "Paused"
                }
            } finally {
                if(epoch==workerEpoch)stopWorker(stoppedState)
            }
        }
    }
    fun stopWorker(state:String="Stopped"){
        val wasRunning=workerRunning;workerEpoch++;workerRunning=false;workerState=state;worker?.cancel();worker=null
        if(wasRunning){val api=client;stopJob=viewModelScope.launch{runCatching{api?.request("/v1/worker/stop","POST")}}}
    }
    private fun playingOffset(): Double = if (playingOriginal) 0.0 else comparison?.sourceStart ?: 0.0
    private fun updatePlayhead() {
        val current=player ?: return
        if (playerReady) runCatching { playhead=(playingOffset()+current.currentPosition/1000.0).toFloat() }
    }
    private fun applyListeningLevel() {
        val gain=if (!matchListeningLevels) 1f else if (playingOriginal) {
            comparison?.originalGain ?: 1f
        } else comparison?.resultGain ?: 1f
        player?.takeIf{playerReady}?.setVolume(gain,gain)
    }
    fun setListeningLevelMatched(enabled: Boolean) {
        matchListeningLevels=enabled
        applyListeningLevel()
    }
    fun seekPlayback(position: Float) {
        val pending = playbackWindow
        if (pending != null && position.toDouble() !in pending) stopPlayback()
        playhead=position
        val current=player ?: return
        if (!playerReady) return
        val target=((position-playingOffset())*1000).roundToInt().coerceIn(0,maxOf(0,current.duration-1))
        current.seekTo(target.toLong(),MediaPlayer.SEEK_CLOSEST)
    }
    fun play(originalAudio: Boolean) = startPlayback(originalAudio)

    fun playSelection() {
        val selected = currentSelection() ?: return
        startPlayback(true, selected)
    }

    private fun startPlayback(
        originalAudio: Boolean,
        selected: ClosedFloatingPointRange<Double>? = null,
        restart: Boolean = false,
    ) {
        val file=if(originalAudio)original.takeIf{it.isFile} else result
        if (file == null) return
        val differentTrack=originalAudio!=playingOriginal
        stopPlayback()
        val span=comparison
        val bounds=selected ?: span?.let { it.sourceStart..(it.sourceStart+it.duration) }
        if (bounds != null && (restart || playhead < bounds.start || playhead >= bounds.endInclusive)) {
            playhead=bounds.start.toFloat()
        } else if (bounds==null && (differentTrack || restart)) {
            playhead=0f
        }
        playbackWindow=bounds
        playingOriginal=originalAudio
        val next=MediaPlayer()
        player=next
        playbackState="Loading audio…"
        runCatching {
            next.setDataSource(file.path)
            next.setOnPreparedListener { ready ->
                if(player!==ready)return@setOnPreparedListener
                playerReady=true
                applyListeningLevel()
                fun startPlayer() {
                    if(player!==ready)return
                    ready.start()
                    playbackState=when {
                        selected!=null -> "Selection"
                        originalAudio -> "A · Original"
                        else -> "B · Result"
                    }
                    playbackTracking=viewModelScope.launch {
                        while(isActive && player===ready) {
                            updatePlayhead()
                            if (originalAudio && bounds!=null && playhead>=bounds.endInclusive) {
                                if (loopPlayback) startPlayback(originalAudio, selected, restart = true)
                                else {
                                    stopPlayback()
                                    playhead=bounds.start.toFloat()
                                }
                                break
                            }
                            delay(60)
                        }
                    }
                }
                val target=((playhead-playingOffset())*1000).roundToInt().coerceIn(0,maxOf(0,ready.duration-1))
                if (target>0) {
                    ready.setOnSeekCompleteListener { it.setOnSeekCompleteListener(null);startPlayer() }
                    ready.seekTo(target.toLong(),MediaPlayer.SEEK_CLOSEST)
                } else startPlayer()
            }
            next.setOnErrorListener { failed, _, _ ->
                if(player===failed){stopPlayback();playbackState="Playback error";error="This audio could not be played"}
                true
            }
            next.setOnCompletionListener { completed ->
                if(player===completed) {
                    if (loopPlayback) startPlayback(originalAudio, selected, restart = true)
                    else { stopPlayback();playhead=(bounds?.start ?: 0.0).toFloat() }
                }
            }
            next.prepareAsync()
        }.onFailure { stopPlayback();error=it.message;playbackState="Playback error" }
    }
    fun stopPlayback(){
        updatePlayhead()
        playbackTracking?.cancel()
        playbackTracking=null
        player?.release()
        player=null
        playerReady=false
        playbackWindow=null
        playbackState="Stopped"
    }
    fun updateMusic(value:MusicDraft){music=value;prefs.edit().putString("music",gson.toJson(value)).apply()}
    fun buildBrief(){runCatching{updateMusic(music.build())}.onFailure{error=it.message}}
    fun exportBriefText(): File? = runCatching {
        require(music.canExport) { "Update the brief before sharing" }
        File(exports, "music-brief.txt").also { write(it, music.prompt.toByteArray()) }
    }.onFailure { error = it.message }.getOrNull()
    fun exportBrief():File?=runCatching{require(music.canExport){"Rebuild after changing directions"};File(exports,"music-brief.json").also{val bytes=gson.toJson(music).toByteArray();require(bytes.size<=65536){"Shorten the brief before exporting"};write(it,bytes)}}.onFailure{error=it.message}.getOrNull()
    fun importBrief(uri:Uri)=action{val text=withContext(Dispatchers.IO){getApplication<Application>().contentResolver.openInputStream(uri)!!.use{String(it.readBytesBounded(65536))}};updateMusic(parseMusic(text))}
    private fun parseMusic(text:String):MusicDraft {
        val obj=JsonParser.parseString(text).asJsonObject
        listOf("description","style","instruments","exclusions","vocals","duration","bpm","lyrics","arrangement","prompt","builtSource").forEach { key -> require(obj.has(key) && obj[key].isJsonPrimitive && obj[key].asJsonPrimitive.isString){"Invalid brief JSON"} }
        return gson.fromJson(obj,MusicDraft::class.java)
    }
    override fun onCleared(){cancelNearbyPairing();stopWorker();stopPlayback();super.onCleared()}
}
fun java.io.InputStream.readBytesBounded(limit:Int):ByteArray {
    val out=java.io.ByteArrayOutputStream();val buffer=ByteArray(8192)
    while(true){val count=read(buffer);if(count<0)break;require(out.size()+count<=limit){"File exceeds the size limit"};out.write(buffer,0,count)}
    return out.toByteArray()
}
