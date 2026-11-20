package com.audioenhancermax.worker

import android.app.Instrumentation
import android.content.Intent
import android.os.Bundle
import android.net.Uri
import android.media.MediaExtractor
import android.media.MediaFormat
import androidx.core.content.FileProvider
import com.google.gson.JsonParser
import java.io.File
import java.io.OutputStream
import java.time.Instant
import kotlinx.coroutines.runBlocking
import kotlin.math.abs
import kotlin.math.sqrt

/** Native codec regression runner using only Android's SDK, no network test dependency. */
class MediaInstrumentation: Instrumentation() {
    override fun onCreate(arguments: Bundle?) { super.onCreate(arguments); start() }
    override fun onStart() {
        val report = Bundle()
        try {
            runBlocking {
                for(filter in AudioImportPolicy.Filter.entries) {
                    val intent=AudioDocumentContract().createIntent(targetContext,filter.mimeTypes)
                    check(intent.getStringArrayExtra(android.content.Intent.EXTRA_MIME_TYPES)!!.contentEquals(filter.mimeTypes)){"Picker lost format MIME hints"}
                    check(intent.type==if(filter.mimeTypes.size==1)filter.mimeTypes[0] else "*/*")
                }
                val folder=File(targetContext.cacheDir,"media-regression").apply{mkdirs()}
                fun fixture(name:String)=File(folder,name).also { f -> context.assets.open(name).use{input->f.outputStream().use{input.copyTo(it)}} }
                if (android.os.Build.VERSION.SDK_INT >= 28) {
                    val signed = inspectCredentialFile(targetContext, fixture("signed-sample.wav"), "audio/wav")
                    val altered = inspectCredentialFile(targetContext, fixture("altered-sample.wav"), "audio/wav")
                    val unsigned = inspectCredentialFile(targetContext, fixture("phone24.wav"), "audio/wav")
                    check(signed.outcome == "Integrity verified" && signed.signerTrust != "recognized") { signed.toString() }
                    check(signed.reportFingerprint == sha256(fixture("processing-report.json").readBytes())) { signed.toString() }
                    check(altered.outcome == "Integrity inconclusive" && "assertion.dataHash.mismatch" in altered.failureCodes) { altered.toString() }
                    check(unsigned.outcome == "No embedded credentials") { unsigned.toString() }
                    report.putString("c2pa", "PASS: signed and unsigned WAVs, conservative mismatch for altered WAV, manifest actions, signer trust and exact report fingerprint")
                }
                val originalProofFile = fixture("signed-sample.wav")
                val originalProof = originalProofFile.inputStream().use {
                    copyAndHash(it, java.io.ByteArrayOutputStream(), VerifyFileLimit) {}
                }
                val checked = verifyCopiedMedia(targetContext, originalProofFile, originalProof) {}
                check(checked.asset.digest == sha256(originalProofFile.readBytes()) && checked.asset.sizeBytes == originalProofFile.length())
                check(checked.audioStatus == "measured" && requireNotNull(checked.audio).analyzedSamples > 0)
                val metadata = requireNotNull(checked.metadata)
                check(metadata.hasTechnicalMetadata && metadata.tracks.any { it.mediaType.startsWith("audio/") })
                if (android.os.Build.VERSION.SDK_INT >= 28) {
                    check(checked.credentials.actions.any { it.action == "c2pa.opened" })
                    check(checked.credentials.actions.any { it.action == "c2pa.modified" })
                }
                val reportFile = saveVerificationReport(targetContext, checked)
                val reportUri = FileProvider.getUriForFile(targetContext, "${targetContext.packageName}.files", reportFile)
                check(reportUri.scheme == "content" && !isExternalMediaUri(targetContext, reportUri))
                val exported = targetContext.contentResolver.openInputStream(reportUri)!!.use {
                    JsonParser.parseString(String(it.readBytes())).asJsonObject
                }
                check(exported["schema"].asString == MediaVerificationSchema)
                check(exported.getAsJsonObject("asset")["sha256"].asString == checked.asset.digest)
                check(exported.getAsJsonObject("credentials")["status"].asString == checked.credentials.status)
                check(exported.getAsJsonObject("metadata")["status"].asString == "read")
                verifyMetadataFixtures(report)
                val unsafeShare = Intent(Intent.ACTION_SEND).setType("audio/wav")
                    .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION).putExtra(Intent.EXTRA_STREAM, Uri.fromFile(originalProofFile))
                check(singleSharedContent(targetContext, unsafeShare) == null)
                val ungrantedShare = Intent(Intent.ACTION_SEND).setType("audio/wav")
                    .putExtra(Intent.EXTRA_STREAM, Uri.parse("content://verification.example/document/x"))
                check(singleSharedContent(targetContext, ungrantedShare) == null)
                val compressed = fixture("phone.m4a")
                val measured = AudioImporter.measure(compressed, AudioImportPolicy.Kind.MP4) {}
                check(abs(measured.analyzedSeconds - 2) < .12 && measured.complete && measured.sampleRate == 48000)
                val longMeasure = AudioImporter.measure(fixture("phone90.m4a"), AudioImportPolicy.Kind.MP4) {}
                check(!longMeasure.complete && longMeasure.analyzedSeconds == 30.0)
                report.putString("verification", "PASS: exact original bytes/hash, native audio metrics with time window, safe share rejection, versioned FileProvider report")
                val updateManifestFile = File(targetContext.cacheDir, "qa-update-feed.json")
                val updateArtifact = File(targetContext.cacheDir, "qa-update-artifact.apk")
                if (updateManifestFile.isFile && updateArtifact.isFile) {
                    try {
                        val key = targetContext.assets.open("companion-update-public.pem").bufferedReader()
                            .use { readUpdatePublicKey(it.readText()) }
                        val release = verifyUpdateFeed(updateManifestFile.readBytes(), key, Instant.now().epochSecond).release
                        val sink = object : OutputStream() {
                            override fun write(value: Int) = Unit
                            override fun write(bytes: ByteArray, offset: Int, length: Int) = Unit
                        }
                        updateArtifact.inputStream().use { copyVerifiedUpdate(it, sink, release) {} }
                        val installed = installedApkIdentity(targetContext)
                        check(installed.build >= release.build && installed.signerSha256 == setOf(release.signerSha256))
                        check(runCatching { verifyUpdateArchive(targetContext, updateArtifact, installed, release) }.isFailure)
                        verifyUpdateArchive(targetContext, updateArtifact, installed.copy(build = release.build - 1), release)
                        report.putString("updater", "PASS: bundled trust key, signed real feed, exact APK SHA/size, Android package/version/cert, installed downgrade rejection")
                    } finally {
                        updateManifestFile.delete()
                        updateArtifact.delete()
                    }
                }
                for(name in listOf("phone.m4a","phone.aac","phone.flac","phone.ogg","phone24.wav")) {
                    val file=fixture(name);val hash=sha256(file.readBytes())
                    val decoded=AudioImporter.decode(targetContext,Uri.fromFile(file))
                    check(abs(decoded.wave.duration-2)<0.12 && decoded.video==null){"Smartphone codec failed: $name, duration ${decoded.wave.duration}"}
                    check(decoded.analysis.contains(hash) && decoded.analysis.contains("48000")){"Missing source analysis for $name"}
                    check(hash==sha256(file.readBytes())){"Original changed: $name"}
                }
                val extendedPCM=Wave.decode(fixture("phone24.wav").readBytes())
                check(extendedPCM.channels==1 && extendedPCM.samples.any{it<0f} && extendedPCM.samples.any{it>0f}) {
                    "The core decoder did not preserve the signed PCM24 samples"
                }
                var filterRejected=false
                try{AudioImporter.decode(targetContext,Uri.fromFile(fixture("short.mp3")),AudioImportPolicy.Filter.WAV)}catch(e:IllegalArgumentException){filterRejected=true}
                check(filterRejected){"MP3 was accepted while WAV filter selected"}
                val m4a=AudioImporter.decode(targetContext,Uri.fromFile(fixture("phone.m4a")),AudioImportPolicy.Filter.M4A_AAC)
                check(m4a.wave.duration>0)
                filterRejected=false
                try{AudioImporter.decode(targetContext,Uri.fromFile(fixture("short.mp4")),AudioImportPolicy.Filter.M4A_AAC)}catch(e:IllegalArgumentException){filterRejected=true}
                check(filterRejected){"Video was accepted while audio-only M4A filter selected"}
                val long=AudioImporter.decode(targetContext,Uri.fromFile(fixture("phone90.m4a")))
                check(abs(long.wave.duration-90)<0.1 && long.wave.samples.size*4>20*1024*1024){"90-second stereo recording must exceed the old one-minute limit"}
                DeviceAssessment.benchmark()
                check((DeviceAssessment.snapshot(targetContext)["voice_eq_ms"] as Double)>0)
                check((DeviceAssessment.snapshot(targetContext)["ram_bytes"] as Long)>0)
                val mp3=AudioImporter.decode(targetContext,Uri.fromFile(fixture("short.mp3")))
                check(abs(mp3.wave.duration-2)<0.08 && mp3.video==null){"MP3 decode duration"}
                val original=fixture("short.mp4");val hash=sha256(original.readBytes())
                val imported=AudioImporter.decode(targetContext,Uri.fromFile(original))
                check(abs(imported.wave.duration-2)<0.08 && imported.video!=null){"MP4 extraction duration=${imported.wave.duration}, remux=${imported.video!=null}"}
                val edited=imported.wave.edit(0.0,imported.wave.duration,-12.0,false,false)
                val output=File(targetContext.filesDir,"qa-video-export.mp4")
                VideoExport.replace(requireNotNull(imported.video),edited,imported.wave,output)
                val reread=AudioImporter.decode(targetContext,Uri.fromFile(output))
                fun rms(w:Wave)=sqrt(w.samples.sumOf{(it*it).toDouble()}/w.samples.size)
                check(abs(reread.wave.duration-imported.wave.duration)<0.08){"Export duration mismatch"}
                check(abs(rms(reread.wave)/rms(imported.wave)-0.25118864)<0.04){"Replacement audio gain"}
                check(sha256(original.readBytes())==hash){"Original changed"}
                val extractor=MediaExtractor()
                try {extractor.setDataSource(output.path);check(extractor.trackCount==2);val t=VideoExport.tracks(extractor);check(extractor.getTrackFormat(t.video).getString(MediaFormat.KEY_MIME)=="video/avc")}finally{extractor.release()}
                var rejected=false
                try {AudioImporter.decode(targetContext,Uri.fromFile(fixture("silent.mp4")))} catch(e:IllegalArgumentException){rejected=true}
                check(rejected){"Video without audio accepted"}
                val offset=AudioImporter.decode(targetContext,Uri.fromFile(fixture("offset-rotated.mp4")))
                check(offset.video==null && offset.wave.duration>0){"Offset timeline must import audio without unsafe video replacement"}
                val fake=File(folder,"fake.mp3").apply{writeBytes(byteArrayOf(0xff.toByte(),0xd8.toByte(),0xff.toByte(),0xe0.toByte()))}
                rejected=false
                try{AudioImporter.decode(targetContext,Uri.fromFile(fake))}catch(e:IllegalArgumentException){rejected=true}
                check(rejected){"Renamed image accepted"}
                val pairingFile=File(targetContext.filesDir,"qa-pairing.json")
                if(pairingFile.exists()) {
                    val code=pairingFile.readText();pairingFile.delete()
                    val pair=Pairing.parse(code)
                    val api=CompanionClient(pair,"qa-android-emulator"){DeviceAssessment.header(targetContext)}
                    check(api.request("/v1/status").json()["protocol"].asInt==1)
                    val expected=Wave(FloatArray(9600){if(it%2==0)0.2f else 0f},48000,2)
                    val originalBytes=expected.encode()
                    val sourceSha=sha256(originalBytes)
                    val upload=api.request("/v1/files","POST",originalBytes,"wav").json()
                    check(upload["sha256"].asString==sourceSha)
                    val fileID=upload["id"].asString
                    val request=com.google.gson.Gson().toJson(mapOf("file_id" to fileID,"profile" to "level")).toByteArray()
                    val job=api.request("/v1/jobs","POST",request).json()["id"].asString
                    var verified=false
                    for(iteration in 0 until 30) {
                        val state=api.request("/v1/jobs/$job").json()
                        val status=state["status"].asString
                        check(status!="failed"){"The test Mac job failed"}
                        if(status=="completed"){
                            val received=api.request("/v1/jobs/$job/audio").bytes
                            val report=api.request("/v1/jobs/$job/report").json()
                            val actual=Wave.decode(received)
                            check(actual.rate==expected.rate && actual.frames==expected.frames && actual.channels==expected.channels)
                            check(report["revision"].asString==state["revision"].asString)
                            check(report["source_sha256"].asString==sourceSha && state["source_sha256"].asString==sourceSha)
                            check(report["sha256"].asString==sha256(received) && state["sha256"].asString==sha256(received))
                            verified=true
                            break
                        }
                        kotlinx.coroutines.delay(500)
                    }
                    check(verified){"The native Mac handoff did not complete"}
                    report.putString("macHandoff","PASS: pinned TLS, native upload, stereo shape, revision and report hashes")
                }
                imported.video?.delete();reread.video?.delete()
                report.putString("stream","PASS: native M4A/AAC, ADTS AAC, FLAC, Ogg/Opus, PCM24, 90-second stereo import, measured device assessment, MP3/MP4, AAC replacement, timing/gain, original preservation, silent-video and renamed-image rejection.\n")
            }
            finish(-1,report)
        } catch(e:Throwable) {report.putString("stream","FAIL: ${e.stackTraceToString()}\n");finish(0,report)}
    }

    private suspend fun verifyMetadataFixtures(report: Bundle) {
        val fixtures = File(targetContext.cacheDir, "qa-metadata").listFiles()?.filter { it.isFile && it.name.startsWith("fixture-") }
            ?.sortedBy { it.name }.orEmpty()
        if (fixtures.isEmpty()) return
        val matrix = fixtures.map { file ->
            val bytes = file.readBytes()
            val original = file.inputStream().use { copyAndHash(it, java.io.ByteArrayOutputStream(), VerifyFileLimit) {} }
            val checked = verifyCopiedMedia(targetContext, file, original) {}
            val metadata = checked.metadata
            val imported = runCatching { AudioImporter.decode(targetContext, Uri.fromFile(file)) }.getOrNull()
            check(checked.asset.digest == sha256(bytes) && bytes.contentEquals(file.readBytes()))
            if (file.name in setOf("fixture-mp3-cover-exif.mp3", "fixture-aac-cover-exif.m4a")) {
                check(metadata?.artworkExif?.get("Camera make") == "QA Camera Corp") { "Cover EXIF: $metadata" }
                check(metadata?.artworkExif?.keys?.none { it.contains("GPS", ignoreCase = true) } == true)
                check(metadata?.artworkExif?.get("Orientation") != "0")
            }
            if (file.name == "fixture-invalid.mp4") {
                check(metadata?.hasTechnicalMetadata != true && checked.credentials.status != "unsigned")
            }
            if (file.name == "fixture-pcm24-bwf.wav") check(metadata?.container == "Broadcast WAV / RIFF")
            if (file.name == "fixture-renamed.wav") {
                check(checked.asset.mediaType == "audio/mpeg")
                check(runCatching { AudioImporter.decode(targetContext, Uri.fromFile(file), AudioImportPolicy.Filter.WAV) }.isFailure)
            }
            if (metadata?.artworkExif?.isNotEmpty() == true) check(!checked.json().contains("QA Camera Corp"))
            val result = "${file.name}: ${checked.asset.mediaType}; metadata=${metadata?.hasTechnicalMetadata}; " +
                "tracks=${metadata?.tracks?.joinToString { it.mediaType }}; tags=${metadata?.tags?.keys}; " +
                "coverExif=${metadata?.artworkExif?.keys}; audio=${checked.audioStatus}; studio=${imported != null}; " +
                "videoReplacement=${imported?.video != null}; c2pa=${checked.credentials.status}"
            imported?.video?.delete()
            result
        }
        report.putString("metadataFormats", matrix.joinToString("\n"))
    }
}
