package com.audioenhancermax.worker

import android.content.Context
import android.net.Uri
import android.os.Build
import com.google.gson.GsonBuilder
import java.io.File
import java.io.IOException
import java.security.MessageDigest
import java.time.Instant
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.runInterruptible
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeout

internal const val MediaVerificationSchema = "audioenhancermax.media-verification.v1"
private const val MiB = 1024L * 1024L
internal const val VerifyFileLimit = 100L * MiB
private val BytesHex = "0123456789abcdef"
private val FingerprintPattern = Regex("[a-f0-9]{64}")
private val ReportName = Regex("verify-[a-f0-9]{64}\\.json")
private const val ScratchMaxAgeMs = 24 * 60 * 60 * 1000L

internal data class VerifiedAsset(val digest: String, val sizeBytes: Long, val mediaType: String)
internal data class VerificationApplication(val version: String, val build: String, val platform: String = "android")

internal data class MediaVerification(
    val asset: VerifiedAsset,
    val credentials: CredentialSummary,
    val audio: AudioMeasurements?,
    val audioStatus: String,
    val audioDetail: String? = null,
    val application: VerificationApplication = VerificationApplication("unknown", "unknown"),
    val generatedAtUtc: String = Instant.now().toString(),
    val metadata: LocalMediaMetadata? = null,
) {
    fun json(): String {
        val technical = audio?.let {
            mapOf(
                "status" to audioStatus,
                "method" to "first_audio_track_native_channels_prefix_v1",
                "sample_rate_hz" to it.sampleRate,
                "channels" to it.channels,
                "analyzed_seconds" to it.analyzedSeconds,
                "preview_limit_seconds" to AudioMeter.MaxSeconds,
                "sample_count" to it.analyzedSamples,
                "peak_dbfs" to it.peakDbfs,
                "rms_dbfs" to it.rmsDbfs,
                "near_full_scale_samples" to it.nearFullScaleSamples,
                "near_full_scale_percent" to (100.0 * it.nearFullScaleSamples / it.analyzedSamples),
                "near_full_scale_threshold" to 0.999,
                "complete" to it.complete,
                "codec" to it.codec,
            )
        } ?: mapOf("status" to audioStatus, "detail" to audioDetail)
        return GsonBuilder().serializeNulls().setPrettyPrinting().create().toJson(linkedMapOf(
            "schema" to MediaVerificationSchema,
            "generated_at_utc" to generatedAtUtc,
            "application" to application,
            "asset" to mapOf("sha256" to asset.digest, "size_bytes" to asset.sizeBytes, "media_type" to asset.mediaType),
            "credentials" to mapOf(
                "status" to credentials.status,
                "outcome" to credentials.outcome,
                "detail" to credentials.detail,
                "embedded" to credentials.embedded,
                "signer" to credentials.signer,
                "issuer" to credentials.issuer,
                "signer_trust" to credentials.signerTrust,
                "timestamp_status" to credentials.timestamp,
                "timestamp_trusted" to credentials.timestamp?.let { it == "trusted" },
                "trust_snapshot_expired" to credentials.trustSnapshotExpired,
                "processing_report_sha256" to credentials.reportFingerprint,
                "actions" to credentials.actions.map { it.action },
                "action_timeline" to credentials.actions.map {
                    mapOf("action" to it.action, "when" to it.at, "when_start" to it.start, "when_end" to it.end, "software" to it.software)
                },
                "failure_codes" to credentials.failureCodes,
            ),
            "audio" to technical,
        ).apply { metadata?.let { put("metadata", it.technicalReport()) } }) + "\n"
    }
}

internal fun isExternalMediaUri(context: Context, uri: Uri): Boolean {
    val authority = uri.authority
    return uri.scheme == "content" && !authority.isNullOrBlank() &&
        authority.substringAfter('@') != "${context.packageName}.files" && uri.path != null
}

internal suspend fun verifyMediaUri(context: Context, uri: Uri): MediaVerification {
    require(isExternalMediaUri(context, uri)) { "Choose an audio or video document with read access." }
    return withContext(Dispatchers.IO) {
        val coroutine = currentCoroutineContext()
        val directory = File(context.cacheDir, "verify-content").apply { mkdirs() }
        val expiry = System.currentTimeMillis() - ScratchMaxAgeMs
        directory.listFiles()?.asSequence()
            ?.filter { it.name.startsWith("verify-media-") && it.extension == "bin" && it.lastModified() in 1 until expiry }
            ?.take(16)?.forEach { it.delete() }
        val copyLimit = minOf(VerifyFileLimit, (directory.usableSpace - 16 * MiB).coerceAtLeast(0))
        require(copyLimit > 0) { "Free some device storage before checking a file." }
        val copy = File.createTempFile("verify-media-", ".bin", directory)
        try {
            val asset = withTimeout(45_000) {
                val timeout = currentCoroutineContext()
                runInterruptible {
                    val descriptor = context.contentResolver.openAssetFileDescriptor(uri, "r")
                        ?: throw IOException("Cannot open file")
                    descriptor.use { local ->
                        val declaredLength = local.declaredLength
                        require(declaredLength <= copyLimit) { "File exceeds the size limit or free storage." }
                        local.createInputStream().use { source ->
                            copy.outputStream().use { target ->
                                copyAndHash(source, target, copyLimit) { timeout.ensureActive() }.also {
                                    check(declaredLength < 0 || it.bytes == declaredLength) {
                                        "The provider returned a file with an unexpected size."
                                    }
                                }
                            }
                        }
                    }
                }
            }
            coroutine.ensureActive()
            verifyCopiedMedia(context, copy, asset, coroutine::ensureActive)
        } finally {
            copy.delete()
        }
    }
}

internal data class CopiedMedia(val digest: String, val bytes: Long, val header: ByteArray)

internal fun copyAndHash(
    source: java.io.InputStream,
    target: java.io.OutputStream,
    limit: Long,
    checkActive: () -> Unit,
): CopiedMedia {
    val sha = MessageDigest.getInstance("SHA-256")
    val buffer = ByteArray(65536)
    val header = ByteArray(64)
    var head = 0
    var bytes = 0L
    while (true) {
        checkActive()
        val count = source.read(buffer)
        if (count < 0) break
        if (count == 0) throw IOException("The provider returned an incomplete stream")
        require(count <= limit - bytes) { "File exceeds the size limit or free storage." }
        val headerCount = minOf(count, header.size - head)
        if (headerCount > 0) {
            buffer.copyInto(header, head, 0, headerCount)
            head += headerCount
        }
        target.write(buffer, 0, count)
        sha.update(buffer, 0, count)
        bytes += count
    }
    require(bytes > 0) { "The selected file is empty." }
    val hex = buildString(64) {
        for (value in sha.digest()) {
            append(BytesHex[(value.toInt() and 255) ushr 4])
            append(BytesHex[value.toInt() and 15])
        }
    }
    return CopiedMedia(hex, bytes, header.copyOf(head))
}

internal fun verifyCopiedMedia(context: Context, file: File, copy: CopiedMedia, checkActive: () -> Unit): MediaVerification {
    checkActive()
    val kind = try { AudioImportPolicy.classify(copy.header) } catch (_: IllegalArgumentException) { null }
    val metadata = kind?.let { inspectMediaMetadata(file, it, copy.header, checkActive) }
    val mime = when (kind) {
        AudioImportPolicy.Kind.WAV -> "audio/wav"
        AudioImportPolicy.Kind.MP3 -> "audio/mpeg"
        AudioImportPolicy.Kind.FLAC -> "audio/flac"
        AudioImportPolicy.Kind.MP4 -> mp4Type(metadata?.tracks.orEmpty(), copy.header)
        AudioImportPolicy.Kind.AAC -> "audio/aac"
        AudioImportPolicy.Kind.OGG -> "audio/ogg"
        AudioImportPolicy.Kind.AMR -> if (isAmrWideband(copy.header)) "audio/amr-wb" else "audio/amr"
        null -> "application/octet-stream"
    }
    val asset = VerifiedAsset(copy.digest, copy.bytes, mime)
    val packageInfo = context.packageManager.getPackageInfo(context.packageName, 0)
    @Suppress("DEPRECATION")
    val build = if (Build.VERSION.SDK_INT >= 28) packageInfo.longVersionCode else packageInfo.versionCode.toLong()
    val app = VerificationApplication(packageInfo.versionName ?: "unknown", build.toString())
    if (kind == null) {
        return MediaVerification(asset, CredentialSummary("unsupported", "Unsupported format", "Choose an audio or video format listed above."),
            null, "unsupported", "This format is outside the local media analysis scope.", app)
    }
    val credential = when {
        mime !in CredentialMediaTypes -> CredentialSummary("unsupported", "Credential check unavailable", "The app reads media metadata for this format. Embedded C2PA checks cover WAV, MP3, FLAC, M4A, MP4 and MOV.")
        Build.VERSION.SDK_INT < 28 -> unavailableCredentials("On-device credential checks require Android 9 or later.")
        else -> inspectCredentialFile(context, file, mime).let { result ->
            if (result.status == "unsigned" && metadata?.hasTechnicalMetadata != true)
                unavailableCredentials("The file signature was recognized, but Android could not confirm a readable media container.")
            else result
        }
    }
    checkActive()
    val report = try {
        val measured = AudioImporter.measure(file, kind, checkActive)
        MediaVerification(asset, credential, measured, "measured", application = app)
    } catch (cancelled: CancellationException) {
        throw cancelled
    } catch (_: OutOfMemoryError) {
        MediaVerification(asset, credential, null, "decode_limit", "The decoder reached the device’s memory limit.", app)
    } catch (_: LinkageError) {
        MediaVerification(asset, credential, null, "unavailable", "The native audio decoder is unavailable.", app)
    } catch (_: Exception) {
        MediaVerification(asset, credential, null, "unreadable_audio", "The local decoder could not read a supported audio track.", app)
    }
    return report.copy(metadata = metadata)
}

private val CredentialMediaTypes = setOf("audio/wav", "audio/mpeg", "audio/flac", "audio/mp4", "video/mp4", "video/quicktime")

private fun mp4Type(tracks: List<MetadataTrack>, header: ByteArray): String {
    val brand = bmffMajorBrand(header)
    val hasAudio = tracks.any { it.mediaType.startsWith("audio/") }
    val hasVideo = tracks.any { it.mediaType.startsWith("video/") }
    return when {
        brand == "qt  " -> "video/quicktime"
        brand?.startsWith("3gp") == true || brand?.startsWith("3g2") == true -> if (hasAudio && !hasVideo) "audio/3gpp" else "video/3gpp"
        brand == "M4A " || brand == "M4B " || (hasAudio && !hasVideo) -> "audio/mp4"
        else -> "video/mp4"
    }
}

internal fun saveVerificationReport(context: Context, verification: MediaVerification): File {
    val hash = verification.asset.digest
    require(FingerprintPattern.matches(hash))
    val exports = File(context.filesDir, "exports").apply { mkdirs() }
    val path = File(exports, "verify-$hash.json")
    val temp = File.createTempFile("verification-", ".tmp", exports)
    try {
        temp.writeText(verification.json())
        check(temp.renameTo(path)) { "The verification report could not be saved." }
    } finally {
        temp.delete()
    }
    // Keep a bounded share history and leave Studio and Music Brief exports untouched.
    exports.listFiles()?.asSequence()?.filter { ReportName.matches(it.name) && it != path }
        ?.sortedByDescending { it.lastModified() }?.drop(15)?.forEach { it.delete() }
    return path
}
