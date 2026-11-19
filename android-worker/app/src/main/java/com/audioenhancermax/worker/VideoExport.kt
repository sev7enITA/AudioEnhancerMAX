package com.audioenhancermax.worker

import android.media.*
import android.os.SystemClock
import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.ensureActive

/** AAC encoding plus compressed video copy; never writes to the imported source document. */
object VideoExport {
    data class Tracks(val video: Int, val audio: Int)
    fun tracks(extractor: MediaExtractor): Tracks {
        val video = (0 until extractor.trackCount).filter { extractor.getTrackFormat(it).getString(MediaFormat.KEY_MIME)?.startsWith("video/") == true }
        val audio = (0 until extractor.trackCount).filter { extractor.getTrackFormat(it).getString(MediaFormat.KEY_MIME)?.startsWith("audio/") == true }
        require(video.size == 1 && audio.size == 1) { "Choose MP4 with exactly one video and one audio track" }
        require(extractor.getTrackFormat(video[0]).getString(MediaFormat.KEY_MIME) == "video/avc" &&
            extractor.getTrackFormat(audio[0]).getString(MediaFormat.KEY_MIME) == "audio/mp4a-latm") {
            "This preview supports MP4 with H.264 video and AAC audio. Convert other codecs first."
        }
        return Tracks(video[0], audio[0])
    }
    suspend fun replace(video: File, result: Wave, source: Wave, output: File) {
        AudioImportPolicy.validateReplacement(result, source)
        val cancellation = currentCoroutineContext()
        val aac = File.createTempFile("replacement-", ".m4a", output.parentFile)
        try {
            encode(result, aac) { cancellation.ensureActive() }
            mux(video, aac, source, output) { cancellation.ensureActive() }
        } catch (e: Exception) { output.delete(); throw e }
        finally { aac.delete() }
    }
    private fun encode(wave: Wave, output: File, checkActive: () -> Unit) {
        val codec = MediaCodec.createEncoderByType("audio/mp4a-latm")
        var muxer: MediaMuxer? = null
        var codecStarted = false; var muxStarted = false
        try {
            val format = MediaFormat.createAudioFormat("audio/mp4a-latm", wave.rate, wave.channels)
            format.setInteger(MediaFormat.KEY_AAC_PROFILE, MediaCodecInfo.CodecProfileLevel.AACObjectLC)
            format.setInteger(MediaFormat.KEY_BIT_RATE, if (wave.channels == 1) 128000 else 192000)
            codec.configure(format, null, null, MediaCodec.CONFIGURE_FLAG_ENCODE)
            codec.start(); codecStarted = true
            val writer = MediaMuxer(output.path, MediaMuxer.OutputFormat.MUXER_OUTPUT_MPEG_4); muxer = writer
            var track = -1; var position = 0; var inputEnded = false; var ended = false
            val info = MediaCodec.BufferInfo(); val deadline = SystemClock.elapsedRealtime() + 60000
            while (!ended) {
                checkActive(); check(SystemClock.elapsedRealtime() < deadline) { "AAC encoding timed out" }
                if (!inputEnded) {
                    val index = codec.dequeueInputBuffer(10000)
                    if (index >= 0) {
                        val buffer = requireNotNull(codec.getInputBuffer(index)).order(ByteOrder.nativeOrder()); buffer.clear()
                        val count = minOf(buffer.remaining()/2/wave.channels*wave.channels, wave.samples.size-position)
                        require(count > 0 || position == wave.samples.size) { "Encoder buffer too small" }
                        val pts = position.toLong()/wave.channels*1000000/wave.rate
                        for (i in 0 until count) buffer.putShort((wave.samples[position+i].coerceIn(-1f,1f)*32767).toInt().toShort())
                        position += count
                        val flag = if (count == 0) MediaCodec.BUFFER_FLAG_END_OF_STREAM else 0
                        codec.queueInputBuffer(index,0,count*2,pts,flag); inputEnded = count == 0
                    }
                }
                val index = codec.dequeueOutputBuffer(info,10000)
                if (index == MediaCodec.INFO_OUTPUT_FORMAT_CHANGED) {
                    check(!muxStarted) { "Encoder format changed twice" }
                    track = writer.addTrack(codec.outputFormat);writer.start();muxStarted = true
                } else if (index >= 0) {
                    try {
                        if (info.size > 0 && info.flags and MediaCodec.BUFFER_FLAG_CODEC_CONFIG == 0 && info.presentationTimeUs >= 0) {
                            check(muxStarted)
                            val buffer = requireNotNull(codec.getOutputBuffer(index))
                            buffer.position(info.offset);buffer.limit(info.offset+info.size)
                            writer.writeSampleData(track,buffer,info)
                        }
                        ended = info.flags and MediaCodec.BUFFER_FLAG_END_OF_STREAM != 0
                    } finally { codec.releaseOutputBuffer(index,false) }
                }
            }
            check(muxStarted) { "No AAC audio was encoded" }
            writer.stop();muxStarted = false
        } finally {
            if (codecStarted) runCatching {codec.stop()};codec.release()
            if (muxStarted) runCatching {muxer?.stop()};muxer?.release()
        }
    }
    private fun mux(video: File, audio: File, source: Wave, output: File, checkActive: () -> Unit) {
        val original = MediaExtractor();val replacement = MediaExtractor()
        var muxer: MediaMuxer? = null;var started = false
        try {
            original.setDataSource(video.path);replacement.setDataSource(audio.path)
            val tracks = tracks(original)
            val sourceAudio = original.getTrackFormat(tracks.audio)
            require(sourceAudio.containsKey(MediaFormat.KEY_DURATION) && kotlin.math.abs(sourceAudio.getLong(MediaFormat.KEY_DURATION)/1e6-source.duration) < 0.1) {
                "Audio duration does not match the video. Export WAV instead."
            }
            original.selectTrack(tracks.audio)
            // AAC decoder priming can be exposed as a negative source timestamp.
            // Import enables remux only after verifying decoded PCM starts at zero.
            val offset = original.sampleTime.coerceAtLeast(0)
            original.unselectTrack(tracks.audio)
            val vf = original.getTrackFormat(tracks.video)
            val writer = MediaMuxer(output.path,MediaMuxer.OutputFormat.MUXER_OUTPUT_MPEG_4);muxer = writer
            if (vf.containsKey(MediaFormat.KEY_ROTATION)) writer.setOrientationHint(vf.getInteger(MediaFormat.KEY_ROTATION))
            val vt = writer.addTrack(vf)
            require(replacement.trackCount == 1) { "Invalid encoded audio" }
            val at = writer.addTrack(replacement.getTrackFormat(0));writer.start();started = true
            original.selectTrack(tracks.video);replacement.selectTrack(0)
            val info = MediaCodec.BufferInfo();val deadline = SystemClock.elapsedRealtime()+60000
            fun copy(extractor: MediaExtractor, track: Int, shift: Long, maxTime: Long?) {
                val buffer = ByteBuffer.allocateDirect(8*1024*1024)
                while (extractor.sampleTime >= 0) {
                    checkActive();check(SystemClock.elapsedRealtime() < deadline) { "Video export timed out" }
                    val time = extractor.sampleTime
                    if (maxTime != null && time >= maxTime) break
                    require(android.os.Build.VERSION.SDK_INT < 28 || extractor.sampleSize in 1..buffer.capacity().toLong()) { "Video frame exceeds the 8 MiB copy limit" }
                    require(extractor.sampleFlags and (MediaExtractor.SAMPLE_FLAG_ENCRYPTED or MediaExtractor.SAMPLE_FLAG_PARTIAL_FRAME) == 0) { "Encrypted or fragmented samples are unsupported" }
                    buffer.clear();val size = extractor.readSampleData(buffer,0)
                    check(size in 1..buffer.capacity()) { "Truncated or oversized media sample" }
                    info.set(0,size,time+shift,if (extractor.sampleFlags and MediaExtractor.SAMPLE_FLAG_SYNC != 0) MediaCodec.BUFFER_FLAG_KEY_FRAME else 0)
                    writer.writeSampleData(track,buffer,info);extractor.advance()
                }
            }
            copy(original,vt,0,null)
            copy(replacement,at,offset,(source.duration*1000000).toLong())
            writer.stop();started = false
        } finally {
            if (started) runCatching {muxer?.stop()};muxer?.release();original.release();replacement.release()
        }
    }
}
