package com.audioenhancermax.worker

import android.media.MediaExtractor
import android.media.MediaFormat
import android.media.MediaMetadataRetriever
import android.os.Build
import androidx.exifinterface.media.ExifInterface
import java.io.File
import java.io.IOException
import java.io.RandomAccessFile
import kotlinx.coroutines.CancellationException

internal data class MetadataTrack(val number: Int, val mediaType: String, val facts: Map<String, Number>)

internal data class LocalMediaMetadata(
    val container: String,
    val facts: Map<String, Number>,
    val tracks: List<MetadataTrack>,
    val tags: Map<String, String>,
    val artworkExif: Map<String, String>,
    val artworkScanLimited: Boolean,
) {
    val hasTechnicalMetadata get() = facts.isNotEmpty() || tracks.isNotEmpty()

    fun technicalReport(): Map<String, Any> = mapOf(
        "status" to if (hasTechnicalMetadata) "read" else "header_only",
        "container" to container,
        "properties" to facts,
        "tracks" to tracks.map { mapOf("number" to it.number, "media_type" to it.mediaType, "properties" to it.facts) },
    )
}

private const val ArtworkSourceLimit = 12L * 1024 * 1024
private const val ArtworkByteLimit = 2 * 1024 * 1024
private val NativeTrackType = Regex("[A-Za-z0-9_.+-]{1,32}/[A-Za-z0-9_.+-]{1,64}")

internal fun inspectMediaMetadata(
    file: File,
    kind: AudioImportPolicy.Kind,
    header: ByteArray,
    checkActive: () -> Unit,
): LocalMediaMetadata {
    val tracks = readTracks(file, checkActive).orEmpty()
    val allowsArtwork = kind == AudioImportPolicy.Kind.MP3 || kind == AudioImportPolicy.Kind.MP4
    val artworkScanLimited = allowsArtwork && file.length() > ArtworkSourceLimit
    val bwfTags = if (kind == AudioImportPolicy.Kind.WAV) safelyReadMetadata { readBroadcastWav(file, checkActive) } else null
    val retrieved = safelyReadMetadata {
        val retriever = MediaMetadataRetriever()
        try {
            file.inputStream().use { retriever.setDataSource(it.fd) }
            checkActive()
            readContainerMetadata(retriever, allowsArtwork && !artworkScanLimited, checkActive)
        } finally {
            safelyReadMetadata { retriever.release() }
        }
    }
    val container = if (bwfTags != null) "Broadcast WAV / RIFF" else mediaContainer(kind, header)
    return LocalMediaMetadata(container, retrieved?.facts.orEmpty(), tracks, retrieved?.tags.orEmpty() + bwfTags.orEmpty(),
        retrieved?.artwork.orEmpty(), artworkScanLimited || retrieved?.artworkTooLarge == true)
}

private fun readBroadcastWav(file: File, checkActive: () -> Unit): Map<String, String>? = RandomAccessFile(file, "r").use { input ->
    val header = ByteArray(8)
    fun riffLength() = (0..3).fold(0L) { size, index -> size or ((header[4 + index].toLong() and 255) shl (index * 8)) }
    input.readFully(header)
    val payloadEnd = minOf(input.length(), 8 + riffLength())
    input.seek(12)
    repeat(256) {
        checkActive()
        if (input.filePointer > payloadEnd - header.size) return@use null
        input.readFully(header)
        val length = riffLength()
        if (length > payloadEnd - input.filePointer) return@use null
        if (String(header, 0, 4, Charsets.US_ASCII) == "bext" && length >= 602) {
            fun readLabel(lengthInBytes: Int): String? {
                val field = ByteArray(lengthInBytes)
                input.readFully(field)
                return cleanMetadataText(String(field, Charsets.US_ASCII).substringBefore('\u0000'))
            }
            val description = readLabel(256)
            val originator = readLabel(32)
            return@use listOfNotNull(description?.let { "Broadcast description" to it },
                originator?.let { "Broadcast originator" to it }).toMap()
        }
        input.seek(input.filePointer + length + (length and 1))
    }
    null
}

private fun mediaContainer(kind: AudioImportPolicy.Kind, header: ByteArray): String = when (kind) {
    AudioImportPolicy.Kind.WAV -> "WAV / RIFF"
    AudioImportPolicy.Kind.MP3 -> "MP3"
    AudioImportPolicy.Kind.FLAC -> "FLAC"
    AudioImportPolicy.Kind.OGG -> "Ogg"
    AudioImportPolicy.Kind.AAC -> "AAC / ADTS"
    AudioImportPolicy.Kind.AMR -> if (isAmrWideband(header)) "AMR-WB" else "AMR-NB"
    AudioImportPolicy.Kind.MP4 -> when (val brand = bmffMajorBrand(header)) {
        "qt  " -> "QuickTime / MOV"
        "M4A ", "M4B " -> "MPEG-4 audio / M4A"
        else -> if (brand?.startsWith("3gp") == true || brand?.startsWith("3g2") == true) "3GPP / 3GP"
            else "ISO Base Media / MP4"
    }
}

internal fun bmffMajorBrand(header: ByteArray): String? =
    if (header.size >= 12) String(header, 8, 4, Charsets.US_ASCII) else null

internal fun isAmrWideband(header: ByteArray): Boolean =
    header.size >= 8 && String(header, 0, 8, Charsets.US_ASCII) == "#!AMR-WB"

private fun readTracks(file: File, checkActive: () -> Unit): List<MetadataTrack>? = safelyReadMetadata {
    val extractor = MediaExtractor()
    try {
        file.inputStream().use { extractor.setDataSource(it.fd) }
        (0 until extractor.trackCount.coerceIn(0, 32)).mapNotNull { index ->
            checkActive()
            val format = safelyReadMetadata { extractor.getTrackFormat(index) } ?: return@mapNotNull null
            val mime = safelyReadMetadata { format.getString(MediaFormat.KEY_MIME) }
                ?.takeIf { NativeTrackType.matches(it) } ?: return@mapNotNull null
            val facts = buildMap {
                format.whole(MediaFormat.KEY_DURATION)?.let { put("duration_ms", it / 1000) }
                format.whole(MediaFormat.KEY_BIT_RATE)?.let { put("bit_rate_bps", it) }
                if (mime.startsWith("audio/")) {
                    format.whole(MediaFormat.KEY_SAMPLE_RATE)?.let { put("sample_rate_hz", it) }
                    format.whole(MediaFormat.KEY_CHANNEL_COUNT)?.let { put("channels", it) }
                }
                if (mime.startsWith("video/")) {
                    format.whole(MediaFormat.KEY_WIDTH)?.let { put("width_px", it) }
                    format.whole(MediaFormat.KEY_HEIGHT)?.let { put("height_px", it) }
                    format.whole(MediaFormat.KEY_ROTATION, allowZero = true)?.let { put("rotation_degrees", it) }
                    format.decimal(MediaFormat.KEY_FRAME_RATE)?.let { put("frame_rate_fps", it) }
                }
            }
            MetadataTrack(index + 1, mime, facts)
        }
    } finally {
        safelyReadMetadata { extractor.release() }
    }
}

private fun MediaFormat.whole(key: String, allowZero: Boolean = false): Long? {
    if (!containsKey(key)) return null
    return (safelyReadMetadata { getLong(key) } ?: safelyReadMetadata { getInteger(key).toLong() })
        ?.takeIf { it > 0 || (allowZero && it == 0L) }
}

private fun MediaFormat.decimal(key: String): Double? {
    if (!containsKey(key)) return null
    return (safelyReadMetadata { getFloat(key).toDouble() } ?: whole(key)?.toDouble())
        ?.takeIf { it.isFinite() && it > 0 }
}

private data class RetrievedMetadata(
    val facts: Map<String, Number>, val tags: Map<String, String>, val artwork: Map<String, String>, val artworkTooLarge: Boolean,
)

private fun readContainerMetadata(retriever: MediaMetadataRetriever, allowsArtwork: Boolean, checkActive: () -> Unit): RetrievedMetadata =
    with(MediaMetadataRetrieverKeys) {
        val facts = linkedMapOf<String, Number>()
        containerFacts.forEach { (key, label) ->
            retriever.extractMetadata(key)?.toLongOrNull()?.takeIf { it > 0 || (label == "rotation_degrees" && it == 0L) }
                ?.let { facts[label] = it }
        }
        if (Build.VERSION.SDK_INT >= 31) {
            retriever.extractMetadata(MediaMetadataRetriever.METADATA_KEY_SAMPLERATE)?.toLongOrNull()?.takeIf { it > 0 }
                ?.let { facts["sample_rate_hz"] = it }
            retriever.extractMetadata(MediaMetadataRetriever.METADATA_KEY_BITS_PER_SAMPLE)?.toLongOrNull()?.takeIf { it > 0 }
                ?.let { facts["bits_per_sample"] = it }
        }
        val tags = contentTags.mapNotNull { (key, label) ->
            checkActive()
            cleanMetadataText(retriever.extractMetadata(key))?.let { label to it }
        }.toMap()
        checkActive()
        val artwork = if (allowsArtwork) safelyReadMetadata { retriever.embeddedPicture } else null
        RetrievedMetadata(facts, tags, artwork?.let(::readCoverExif).orEmpty(), (artwork?.size ?: 0) > ArtworkByteLimit)
    }

private object MediaMetadataRetrieverKeys {
    val containerFacts = mapOf(
        MediaMetadataRetriever.METADATA_KEY_DURATION to "duration_ms",
        MediaMetadataRetriever.METADATA_KEY_BITRATE to "bit_rate_bps",
        MediaMetadataRetriever.METADATA_KEY_NUM_TRACKS to "track_count",
        MediaMetadataRetriever.METADATA_KEY_VIDEO_WIDTH to "width_px",
        MediaMetadataRetriever.METADATA_KEY_VIDEO_HEIGHT to "height_px",
        MediaMetadataRetriever.METADATA_KEY_VIDEO_ROTATION to "rotation_degrees",
    )
    val contentTags = mapOf(
        MediaMetadataRetriever.METADATA_KEY_TITLE to "Title",
        MediaMetadataRetriever.METADATA_KEY_ARTIST to "Artist",
        MediaMetadataRetriever.METADATA_KEY_ALBUM to "Album",
        MediaMetadataRetriever.METADATA_KEY_ALBUMARTIST to "Album artist",
        MediaMetadataRetriever.METADATA_KEY_GENRE to "Genre",
        MediaMetadataRetriever.METADATA_KEY_YEAR to "Year",
        MediaMetadataRetriever.METADATA_KEY_COMPOSER to "Composer",
        MediaMetadataRetriever.METADATA_KEY_WRITER to "Writer",
        MediaMetadataRetriever.METADATA_KEY_CD_TRACK_NUMBER to "Track number",
        MediaMetadataRetriever.METADATA_KEY_DISC_NUMBER to "Disc number",
    )
}

internal fun cleanMetadataText(value: String?): String? = value?.take(256)?.filterNot {
    it.isISOControl() || it in '\u202A'..'\u202E' || it in '\u2066'..'\u2069'
}?.trim()?.takeIf { it.isNotBlank() }

private val CoverExifFields = mapOf(
    ExifInterface.TAG_MAKE to "Camera make",
    ExifInterface.TAG_MODEL to "Camera model",
    ExifInterface.TAG_EXPOSURE_TIME to "Exposure time",
    ExifInterface.TAG_F_NUMBER to "Aperture",
    ExifInterface.TAG_PHOTOGRAPHIC_SENSITIVITY to "ISO sensitivity",
    ExifInterface.TAG_FOCAL_LENGTH to "Focal length",
    ExifInterface.TAG_ORIENTATION to "Orientation",
)

private fun readCoverExif(bytes: ByteArray): Map<String, String>? {
    if (bytes.size > ArtworkByteLimit || !hasJpegExif(bytes)) return null
    return safelyReadMetadata {
        val exif = ExifInterface(bytes.inputStream())
        CoverExifFields.mapNotNull { (key, label) ->
            val value = cleanMetadataText(exif.getAttribute(key)) ?: return@mapNotNull null
            val display = when (key) {
                ExifInterface.TAG_ORIENTATION -> value.takeIf { (it.toIntOrNull() ?: 0) in 1..8 }
                ExifInterface.TAG_EXPOSURE_TIME -> "$value s"
                ExifInterface.TAG_F_NUMBER -> "f/$value"
                else -> value
            }
            display?.let { label to it }
        }.toMap()
    }
}

internal fun hasJpegExif(bytes: ByteArray): Boolean {
    fun octet(index: Int) = bytes[index].toInt() and 255
    if (bytes.size < 12 || octet(0) != 255 || octet(1) != 216) return false
    var offset = 2
    while (offset + 4 <= bytes.size && octet(offset) == 255) {
        while (offset + 1 < bytes.size && octet(offset + 1) == 255) offset++
        if (offset + 4 > bytes.size) return false
        val marker = octet(offset + 1)
        if (marker == 218 || marker == 217) return false
        val length = (octet(offset + 2) shl 8) or octet(offset + 3)
        if (length < 2 || length > bytes.size - offset - 2) return false
        if (marker == 225 && length >= 8 && String(bytes, offset + 4, 6, Charsets.US_ASCII) == "Exif\u0000\u0000") return true
        offset += 2 + length
    }
    return false
}

private inline fun <T> safelyReadMetadata(read: () -> T): T? = try {
    read()
} catch (cancelled: CancellationException) {
    throw cancelled
} catch (_: IOException) {
    null
} catch (_: RuntimeException) {
    null
} catch (_: LinkageError) {
    null
} catch (_: OutOfMemoryError) {
    null
}
