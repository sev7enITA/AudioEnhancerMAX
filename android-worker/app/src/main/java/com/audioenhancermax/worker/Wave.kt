package com.audioenhancermax.worker
import java.nio.ByteBuffer
import java.nio.ByteOrder
import kotlin.math.*

data class Wave(val samples: FloatArray, val rate: Int, val channels: Int) {
    init { require(rate in 8000..96000 && channels in 1..2 && samples.isNotEmpty() && samples.size % channels == 0 && samples.size <= (MAX_BYTES-44)/4 && samples.all { it.isFinite() }) { "Use bounded mono/stereo audio at 8–96 kHz" } }
    val frames get() = samples.size / channels
    val duration get() = frames.toDouble() / rate
    /** One peak per time bin, covering the complete recording including its final frame. */
    fun overview(bins:Int=100):FloatArray {
        require(bins in 1..2048)
        return FloatArray(bins){i->
            val lo=(i.toLong()*frames/bins).toInt()
            val hi=maxOf(lo+1,((i+1).toLong()*frames/bins).toInt()).coerceAtMost(frames)
            var peak=0f
            for(j in lo*channels until hi*channels)peak=maxOf(peak,abs(samples[j]))
            peak.coerceAtMost(1f)
        }
    }
    fun encode(): ByteArray {
        val b = ByteBuffer.allocate(44+samples.size*4).order(ByteOrder.LITTLE_ENDIAN)
        b.put("RIFF".toByteArray());b.putInt(36+samples.size*4);b.put("WAVEfmt ".toByteArray());b.putInt(16)
        b.putShort(3);b.putShort(channels.toShort());b.putInt(rate);b.putInt(rate*channels*4);b.putShort((channels*4).toShort());b.putShort(32)
        b.put("data".toByteArray());b.putInt(samples.size*4);samples.forEach { b.putFloat(it) };return b.array()
    }
    fun autoEQ(): Wave {
        val output = samples.copyOf()
        for (ch in 0 until channels) {
            val mono = FloatArray(frames) { samples[it*channels+ch] }
            val result = DspEngine.processChunk(mono,rate,mapOf("auto_eq" to true))
            for (i in result.indices) output[i*channels+ch] = result[i]
        }
        return Wave(output,rate,channels)
    }
    fun silence(start: Double, end: Double): Wave {
        val (first, last) = selectionFrames(start, end)
        val output = samples.copyOf()
        output.fill(0f, first * channels, last * channels)
        return Wave(output, rate, channels)
    }

    private fun selectionFrames(start: Double, end: Double): Pair<Int, Int> {
        require(start.isFinite() && end.isFinite() && start >= 0 && end <= duration + 0.000001 && end > start) {
            "Choose a valid time range"
        }
        val first = min(frames - 1, (start * rate).toInt())
        val last = min(frames, (end * rate).roundToInt())
        require(last > first) { "Selected range is empty" }
        return first to last
    }

    fun edit(
        start: Double,
        end: Double,
        gain: Double,
        normalize: Boolean,
        voice: Boolean,
        fadeIn: Double = 0.0,
        fadeOut: Double = 0.0,
    ): Wave {
        require(gain in -24.0..12.0) { "Choose a gain between −24 and +12 dB" }
        require(fadeIn in 0.0..5.0 && fadeOut in 0.0..5.0) { "Choose fades between 0 and 5 seconds" }
        val (lo, hi) = selectionFrames(start, end)
        var w = Wave(samples.copyOfRange(lo*channels,hi*channels),rate,channels)
        if (voice) w = w.autoEQ()
        val factor = 10.0.pow(gain/20).toFloat()
        val inFrames = (fadeIn * rate).roundToInt().coerceAtMost(w.frames)
        val outFrames = (fadeOut * rate).roundToInt().coerceAtMost(w.frames)
        val output = w.samples
        for (frame in 0 until w.frames) {
            val incoming = if (frame < inFrames) frame.toFloat() / max(1, inFrames - 1) else 1f
            val remaining = w.frames - 1 - frame
            val outgoing = if (remaining < outFrames) remaining.toFloat() / max(1, outFrames - 1) else 1f
            val amplitude = factor * incoming * outgoing
            for (channel in 0 until channels) output[frame * channels + channel] *= amplitude
        }
        val peak = output.maxOf { abs(it) }
        if (normalize && peak>0) { val scale = 10.0.pow(-1.0/20).toFloat()/peak;for (i in output.indices) output[i] *= scale }
        for (i in output.indices) output[i] = output[i].coerceIn(-1f,1f)
        return Wave(output,rate,channels)
    }
    companion object {
        const val MAX_BYTES = 64*1024*1024
        private val WAVE_SUBFORMAT_GUID_SUFFIX = byteArrayOf(0,0,0,0,0x10,0,0x80.toByte(),0,0,0xaa.toByte(),0,0x38,0x9b.toByte(),0x71)
        fun decode(data: ByteArray): Wave {
            require(data.size in 44..MAX_BYTES) { "Invalid or oversized WAV" }
            val b=ByteBuffer.wrap(data).order(ByteOrder.LITTLE_ENDIAN)
            fun text(p:Int) = String(data,p,4,Charsets.US_ASCII)
            require(text(0)=="RIFF" && text(8)=="WAVE" && b.getInt(4).toLong()+8==data.size.toLong()) { "Incomplete WAV header" }
            var pos=12;var kind=0;var channels=0;var rate=0;var bits=0;var align=0;var byteRate=0;var payload:ByteArray?=null;var formatSeen=false
            while (pos+8 <= data.size) {
                val tag=text(pos);val size=b.getInt(pos+4).toLong() and 0xffffffffL;pos+=8
                require(size <= data.size-pos) { "Truncated WAV chunk" }
                if (tag=="fmt ") {
                    require(size>=16 && !formatSeen) { "Invalid WAV format" };formatSeen=true
                    kind=b.getShort(pos).toInt() and 65535;channels=b.getShort(pos+2).toInt() and 65535;rate=b.getInt(pos+4);byteRate=b.getInt(pos+8);align=b.getShort(pos+12).toInt() and 65535;bits=b.getShort(pos+14).toInt() and 65535
                    if (kind==0xfffe) {
                        require(size>=40)
                        val extensionSize=b.getShort(pos+16).toInt() and 65535
                        val validBits=b.getShort(pos+18).toInt() and 65535
                        require(extensionSize>=22 && 18+extensionSize<=size && validBits==bits &&
                            WAVE_SUBFORMAT_GUID_SUFFIX.indices.all { data[pos+26+it]==WAVE_SUBFORMAT_GUID_SUFFIX[it] }) {
                            "Unsupported extended WAV format"
                        }
                        kind=b.getShort(pos+24).toInt() and 65535
                    }
                } else if (tag=="data") {require(payload==null) { "Duplicate WAV data" };payload=data.copyOfRange(pos,pos+size.toInt())}
                pos+=size.toInt()+(size%2).toInt()
            }
            require(pos==data.size){"Invalid WAV padding"}
            val raw=requireNotNull(payload) { "No WAV audio data" }
            require((kind==1 && bits in listOf(16,24,32) || kind==3 && bits==32) && channels in 1..2 && rate in 8000..96000 && align==channels*bits/8 && byteRate==rate*align && align>0 && raw.size%align==0) { "Local editing supports PCM16/24/32 or float32 WAV, mono/stereo, 8–96 kHz" }
            val audio=ByteBuffer.wrap(raw).order(ByteOrder.LITTLE_ENDIAN)
            return Wave(FloatArray(raw.size/(bits/8)) {if(kind==3) audio.float else when(bits) {
                16 -> audio.short/32768f
                24 -> {val value=(audio.get().toInt() and 255) or ((audio.get().toInt() and 255) shl 8) or (audio.get().toInt() shl 16);value/8388608f}
                else -> audio.int/2147483648f
            }},rate,channels)
        }
    }
}

data class AudioComparison(
    val sourceStart: Double,
    val duration: Double,
    val originalGain: Float,
    val resultGain: Float
) {
    fun contains(position: Double): Boolean =
        position >= sourceStart && position < sourceStart + duration

    companion object {
        fun match(source: Wave, result: Wave, sourceStart: Double): AudioComparison? {
            if (!sourceStart.isFinite() || sourceStart < 0 || source.rate != result.rate ||
                source.channels != result.channels
            ) return null
            val firstFrame = (sourceStart * source.rate).roundToInt()
            if (firstFrame > source.frames - result.frames) return null
            var sourceEnergy = 0.0
            var resultEnergy = 0.0
            for (index in result.samples.indices) {
                val original = source.samples[firstFrame * source.channels + index].toDouble()
                val revised = result.samples[index].toDouble()
                sourceEnergy += original * original
                resultEnergy += revised * revised
            }
            // Skip level matching for near silence. Apply attenuation to listening only.
            val floor = result.samples.size * 1e-8
            val originalGain = if (resultEnergy > floor && sourceEnergy > resultEnergy) sqrt(resultEnergy / sourceEnergy) else 1.0
            val resultGain = if (sourceEnergy > floor && resultEnergy > sourceEnergy) sqrt(sourceEnergy / resultEnergy) else 1.0
            return AudioComparison(firstFrame.toDouble() / source.rate, result.duration, originalGain.toFloat(), resultGain.toFloat())
        }
    }
}
