package com.audioenhancermax.worker

import android.content.Context
import android.media.AudioFormat
import android.media.MediaCodec
import android.media.MediaExtractor
import android.media.MediaFormat
import android.net.Uri
import android.os.SystemClock
import java.io.File
import java.nio.ByteBuffer
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.ensureActive

/** Offline import. The source document is never modified, and temporary copies are always removed. */
object AudioImporter {
    data class Imported(val wave: Wave, val video: File?, val analysis:String,val overview:FloatArray=wave.overview(320))
    suspend fun decode(context: Context, uri: Uri, filter:AudioImportPolicy.Filter=AudioImportPolicy.Filter.ALL): Imported {
        val cancellation = currentCoroutineContext()
        val copy = File.createTempFile("media-import-", ".bin", context.filesDir)
        var retained = false
        try {
            val source = context.contentResolver.openInputStream(uri)
                ?: throw IllegalArgumentException("The selected file could not be opened")
            source.use { input ->
                copy.outputStream().use { output ->
                    val header = input.readHeader(64)
                    AudioImportPolicy.classify(header)
                    val limit = AudioImportPolicy.VIDEO_MAX_BYTES
                    output.write(header)
                    val buffer = ByteArray(65536)
                    var total = header.size
                    while (true) {
                        cancellation.ensureActive()
                        val n = input.read(buffer)
                        if (n < 0) break
                        require(n <= limit - total) { "The source exceeds the 100 MiB import limit" }
                        output.write(buffer, 0, n); total += n
                    }
                }
            }
            val header = copy.inputStream().use { it.readHeader(64) }
            val kind=AudioImportPolicy.classify(header)
            val decoded=if(kind==AudioImportPolicy.Kind.WAV) {
                filter.validate(kind)
                runCatching { Decoded(Wave.decode(copy.readBytes()), "WAV / PCM", false) }.getOrElse {
                    decodeCompressed(copy,kind,filter) { cancellation.ensureActive() }
                }
            } else decodeCompressed(copy,kind,filter) { cancellation.ensureActive() }
            retained=decoded.remux
            return Imported(decoded.wave,if(retained)copy else null,AudioAnalysis.describe(decoded.wave,kind.name,decoded.codec,copy.length(),sourceHash(copy),decoded.remux))

        } finally { if (!retained) copy.delete() }
    }

    private fun sourceHash(file:File):String {
        val digest=java.security.MessageDigest.getInstance("SHA-256")
        file.inputStream().use{input->val buffer=ByteArray(65536);while(true){val size=input.read(buffer);if(size<0)break;digest.update(buffer,0,size)}}
        return digest.digest().joinToString(""){"%02x".format(it)}
    }

    private fun java.io.InputStream.readHeader(size: Int): ByteArray {
        val header = ByteArray(size)
        var count = 0
        while (count < size) {
            val n = read(header, count, size - count)
            if (n < 0) break
            count += n
        }
        return header.copyOf(count)
    }

    private data class Decoded(val wave:Wave,val codec:String,val remux:Boolean)
    private data class DecodedFormat(val rate: Int, val channels: Int, val codec: String, val remux: Boolean, val complete: Boolean)

    private fun decodeCompressed(file: File, kind:AudioImportPolicy.Kind, filter:AudioImportPolicy.Filter, checkActive: () -> Unit): Decoded {
        val pcm = ImportedPcm()
        val decoded = readPcm(file, kind, filter, 180_000, checkActive) { bytes, float32, _, channels ->
            pcm.append(bytes, float32, channels)
            true
        }
        return Decoded(pcm.finish(decoded.rate, decoded.channels), decoded.codec, decoded.remux)
    }

    /** Uses the same native decoder without retaining a waveform or allocating a second file copy. */
    internal fun measure(file: File, kind: AudioImportPolicy.Kind, checkActive: () -> Unit): AudioMeasurements {
        val meters = AudioMeter()
        if (kind == AudioImportPolicy.Kind.WAV && file.length() <= 12L * 1024 * 1024) {
            val wave = try { Wave.decode(file.readBytes()) } catch (_: IllegalArgumentException) { null }
            if (wave != null) {
                val maxSamples = minOf(wave.samples.size, wave.rate * wave.channels * AudioMeter.MaxSeconds)
                for (index in 0 until maxSamples) {
                    if (index % 16384 == 0) checkActive()
                    meters.add(wave.samples[index])
                }
                return meters.result(wave.rate, wave.channels, "PCM / WAV", maxSamples == wave.samples.size)
            }
        }
        val decoded = readPcm(file, kind, AudioImportPolicy.Filter.ALL, 15_000, checkActive, meters::read)
        return meters.result(decoded.rate, decoded.channels, decoded.codec, decoded.complete)
    }

    private fun readPcm(
        file: File,
        kind: AudioImportPolicy.Kind,
        filter: AudioImportPolicy.Filter,
        timeoutMs: Long,
        checkActive: () -> Unit,
        consume: (ByteBuffer, Boolean, Int, Int) -> Boolean,
    ): DecodedFormat {
        val extractor = MediaExtractor()
        var codec: MediaCodec? = null
        var started = false
        try {
            file.inputStream().use { extractor.setDataSource(it.fd) }
            require(extractor.trackCount in 1..32) { "The file has an unsupported number of tracks" }
            val hasVideo=(0 until extractor.trackCount).any{extractor.getTrackFormat(it).getString(MediaFormat.KEY_MIME)?.startsWith("video/")==true}
            filter.validate(kind,hasVideo)
            val tracks=(0 until extractor.trackCount).filter{extractor.getTrackFormat(it).getString(MediaFormat.KEY_MIME)?.startsWith("audio/")==true}
            require(tracks.size==1){"Choose a recording with exactly one audio track. Found ${tracks.size}."}
            val track=tracks.first()
            val format=extractor.getTrackFormat(track)
            val mime=requireNotNull(format.getString(MediaFormat.KEY_MIME))
            var remux=runCatching{VideoExport.tracks(extractor);true}.getOrDefault(false)
            val bitrate=if(format.containsKey(MediaFormat.KEY_BIT_RATE))format.getInteger(MediaFormat.KEY_BIT_RATE) else null
            var rate = format.getInteger(MediaFormat.KEY_SAMPLE_RATE)
            var channels = format.getInteger(MediaFormat.KEY_CHANNEL_COUNT)
            fun validateFormat() { require(rate in 8000..96000 && channels in 1..2) { "Use mono/stereo audio at 8–96 kHz" } }
            validateFormat()
            extractor.selectTrack(track)
            if(extractor.sampleTime > 0L)remux=false
            val decoder = try {MediaCodec.createDecoderByType(mime)} catch(e:Exception){throw IllegalArgumentException("This Android device has no local decoder for $mime. Export the recording as M4A/AAC or WAV from its recorder.",e)}
            codec = decoder
            format.setInteger(MediaFormat.KEY_PCM_ENCODING, AudioFormat.ENCODING_PCM_16BIT)
            decoder.configure(format, null, null, 0)
            decoder.start(); started = true
            val info = MediaCodec.BufferInfo()
            var inputEnded = false
            var outputEnded = false
            var receivedPcm = false
            var expectedPcmTime: Long? = null
            var encoding = AudioFormat.ENCODING_PCM_16BIT
            var stoppedByConsumer = false
            val deadline = SystemClock.elapsedRealtime() + timeoutMs
            while (!outputEnded && !stoppedByConsumer) {
                checkActive()
                check(SystemClock.elapsedRealtime() < deadline) { "Audio decoding timed out. Try a shorter clip." }
                if (!inputEnded) {
                    val index = decoder.dequeueInputBuffer(10000)
                    if (index >= 0) {
                        val buffer = requireNotNull(decoder.getInputBuffer(index))
                        buffer.clear()
                        val size = extractor.readSampleData(buffer, 0)
                        if (size < 0) {
                            decoder.queueInputBuffer(index, 0, 0, 0, MediaCodec.BUFFER_FLAG_END_OF_STREAM)
                            inputEnded = true
                        } else {
                            decoder.queueInputBuffer(index, 0, size, extractor.sampleTime, 0)
                            extractor.advance()
                        }
                    }
                }
                val index = decoder.dequeueOutputBuffer(info, 10000)
                if (index == MediaCodec.INFO_OUTPUT_FORMAT_CHANGED) {
                    val decoded = decoder.outputFormat
                    val newRate = decoded.getInteger(MediaFormat.KEY_SAMPLE_RATE)
                    val newChannels = decoded.getInteger(MediaFormat.KEY_CHANNEL_COUNT)
                    require(!receivedPcm || (rate == newRate && channels == newChannels)) { "Audio format changed during decoding" }
                    rate = newRate; channels = newChannels; validateFormat()
                    encoding = if (decoded.containsKey(MediaFormat.KEY_PCM_ENCODING)) decoded.getInteger(MediaFormat.KEY_PCM_ENCODING) else AudioFormat.ENCODING_PCM_16BIT
                    require(encoding == AudioFormat.ENCODING_PCM_16BIT || encoding == AudioFormat.ENCODING_PCM_FLOAT) { "Unsupported decoder PCM format" }
                } else if (index >= 0) {
                    try {
                        if (info.size > 0 && info.flags and MediaCodec.BUFFER_FLAG_CODEC_CONFIG == 0) {
                            val output = requireNotNull(decoder.getOutputBuffer(index)).duplicate()
                            output.position(info.offset); output.limit(info.offset + info.size)
                            if (remux) {
                                val expected = expectedPcmTime ?: 0L
                                if(kotlin.math.abs(info.presentationTimeUs-expected) > 2000L)remux=false
                                val width = if (encoding == AudioFormat.ENCODING_PCM_FLOAT) 4 else 2
                                expectedPcmTime = info.presentationTimeUs + (info.size/(width*channels)).toLong()*1000000/rate
                            }
                            stoppedByConsumer = !consume(output, encoding == AudioFormat.ENCODING_PCM_FLOAT, rate, channels)
                            receivedPcm = true
                        }
                        outputEnded = info.flags and MediaCodec.BUFFER_FLAG_END_OF_STREAM != 0
                    } finally { decoder.releaseOutputBuffer(index, false) }
                }
            }
            return DecodedFormat(rate, channels, mime+(bitrate?.let{" · ${it/1000} kbps declared"} ?: " · bitrate not declared"),
                remux, outputEnded && !stoppedByConsumer)
        } finally {
            if (started) runCatching { codec?.stop() }
            runCatching { codec?.release() }
            extractor.release()
        }
    }
}
