package com.audioenhancermax.worker

import java.nio.ByteBuffer
import java.nio.ByteOrder

/** Picker hints are not validation: classify bytes before handing them to a decoder. */
object AudioImportPolicy {
    val mimeTypes get() = Filter.ALL.mimeTypes
    enum class Filter(val label: String, val mimeTypes: Array<String>, val compatibility: String) {
        ALL("Browse media", arrayOf("audio/*", "video/mp4", "video/quicktime", "video/3gpp", "application/ogg"),
            "Lists audio and common video files. Studio checks the container and audio track after you select a file."),
        WAV("WAV", arrayOf("audio/wav", "audio/x-wav", "audio/vnd.wave"),
            "RIFF WAV with PCM 16/24/32-bit or float32, 8–96 kHz, mono or stereo. RF64 and RIFX are outside this import path."),
        MP3("MP3", arrayOf("audio/mpeg", "audio/mp3"), "MPEG Layer III audio decoded by Android."),
        M4A_AAC("M4A / AAC", arrayOf("audio/mp4", "audio/x-m4a", "audio/aac", "audio/aac-adts"),
            "Audio-only M4A and raw AAC with ADTS headers. ALAC in M4A depends on the phone’s extractor and decoder."),
        FLAC("FLAC", arrayOf("audio/flac", "audio/x-flac"), "Native FLAC files decoded by Android."),
        OGG("Ogg / Opus", arrayOf("audio/ogg", "application/ogg", "audio/opus"),
            "Ogg containers such as Vorbis or Opus. The codec must be available on this device."),
        AMR("AMR", arrayOf("audio/amr", "audio/amr-wb"), "AMR-NB and AMR-WB speech recordings decoded by Android."),
        VIDEO("MP4 / MOV / 3GP", arrayOf("video/mp4", "video/quicktime", "video/3gpp"),
            "A recognized video container with one readable audio track. Studio edits the audio. Video replacement is available only for compatible tracks.");

        fun accepts(kind:Kind, hasVideo:Boolean=false):Boolean = when(this) {
            ALL -> true
            WAV -> kind==Kind.WAV && !hasVideo
            MP3 -> kind==Kind.MP3 && !hasVideo
            M4A_AAC -> kind in listOf(Kind.MP4,Kind.AAC) && !hasVideo
            FLAC -> kind==Kind.FLAC && !hasVideo
            OGG -> kind==Kind.OGG && !hasVideo
            AMR -> kind==Kind.AMR && !hasVideo
            VIDEO -> kind==Kind.MP4 && hasVideo
        }
        fun validate(kind:Kind,hasVideo:Boolean=false) {
            require(accepts(kind,hasVideo)) { "This file does not match $label. Choose the matching import format or Browse media. Your previous recording is preserved." }
        }
    }
    enum class Kind { WAV, MP3, MP4, AAC, OGG, FLAC, AMR }
    const val VIDEO_MAX_BYTES = 100 * 1024 * 1024
    fun validateReplacement(result: Wave, source: Wave) {
        require(result.rate == source.rate && result.channels == source.channels && result.samples.size == source.samples.size) {
            "To keep video synchronized, improve the full audio without trimming. Export a trimmed result as WAV instead."
        }
    }
    fun classify(header: ByteArray): Kind {
        fun tag(start: Int, value: String) = header.size >= start + value.length &&
            value.indices.all { header[start + it].toInt() == value[it].code }
        if (tag(0, "RIFF") && tag(8, "WAVE")) return Kind.WAV
        if (tag(0, "ID3")) return Kind.MP3 // MediaExtractor must still validate the complete stream.
        if (header.size >= 4) {
            val b = header.map { it.toInt() and 255 }
            if (b[0] == 255 && b[1] and 224 == 224 && b[1] and 24 != 8 &&
                b[1] and 6 == 2 && b[2] and 240 != 240 && b[2] and 240 != 0 && b[2] and 12 != 12)
                return Kind.MP3
        }
        if (tag(4, "ftyp")) return Kind.MP4 // M4A, ALAC, MP4, MOV and 3GP are validated by MediaExtractor.
        if (tag(0,"OggS")) return Kind.OGG
        if (tag(0,"fLaC")) return Kind.FLAC
        if (tag(0,"#!AMR")) return Kind.AMR
        if (header.size>=2 && (header[0].toInt() and 255)==255 && (header[1].toInt() and 246)==240) return Kind.AAC
        throw IllegalArgumentException("Unsupported container. Choose WAV, M4A/AAC, MP3, FLAC, Ogg/Opus, AMR, MP4/MOV or 3GP. Decoding uses the codecs installed on this device.")
    }
}

/** Bounded, unboxed PCM collection, shared by the native decoder and JVM regression tests. */
internal class ImportedPcm(private val maxSamples: Int = (Wave.MAX_BYTES - 44) / 4) {
    private val chunks = ArrayList<FloatArray>()
    private var count = 0
    fun append(bytes: ByteBuffer, float32: Boolean, channels: Int) {
        require(channels in 1..2) { "Use mono or stereo audio" }
        val width = if (float32) 4 else 2
        require(bytes.remaining() % (width * channels) == 0) { "Incomplete decoded audio frame" }
        val size = bytes.remaining() / width
        require(size <= maxSamples - count) {
            "Decoded audio exceeds the 64 MiB editing limit (about 3 minutes of stereo at 48 kHz, or 17 minutes of mono at 16 kHz). Choose a shorter recording."
        }
        val source = bytes.slice().order(ByteOrder.nativeOrder())
        val samples = FloatArray(size) { if (float32) source.float else source.short / 32768f }
        require(samples.all { it.isFinite() }) { "Invalid decoded audio samples" }
        if (samples.isNotEmpty()) { chunks.add(samples); count += size }
    }
    fun finish(rate: Int, channels: Int): Wave {
        require(count > 0) { "The audio file contains no decoded samples" }
        val samples = FloatArray(count)
        var offset = 0
        chunks.forEach { it.copyInto(samples, offset); offset += it.size }
        return Wave(samples, rate, channels)
    }
}
