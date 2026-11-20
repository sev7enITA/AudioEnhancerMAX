package com.audioenhancermax.worker

import java.nio.ByteBuffer
import java.nio.ByteOrder
import kotlin.math.abs
import kotlin.math.log10
import kotlin.math.sqrt

internal data class AudioMeasurements(
    val sampleRate: Int,
    val channels: Int,
    val analyzedSeconds: Double,
    val analyzedSamples: Int,
    val peakDbfs: Double?,
    val rmsDbfs: Double?,
    val nearFullScaleSamples: Int,
    val complete: Boolean,
    val codec: String,
)

internal class AudioMeter {
    companion object {
        const val MaxSeconds = 30
    }
    private var count = 0
    private var peak = 0.0
    private var power = 0.0
    private var nearFullScale = 0

    fun add(sample: Float) {
        val amplitude = abs(sample.toDouble())
        require(amplitude.isFinite() && amplitude <= 32) { "The decoder supplied invalid audio" }
        count++
        peak = maxOf(peak, amplitude)
        power += amplitude * amplitude
        if (amplitude >= 0.999) nearFullScale++
    }

    /** Retains no samples. Returns false if the remainder of the decoded stream was skipped. */
    fun read(bytes: ByteBuffer, float32: Boolean, rate: Int, channels: Int): Boolean {
        val width = if (float32) 4 else 2
        check(bytes.remaining() % (width * channels) == 0) { "Incomplete decoded frame" }
        val source = bytes.slice().order(ByteOrder.nativeOrder())
        val requested = source.remaining() / width
        val amount = minOf(requested, rate * channels * MaxSeconds - count)
        repeat(amount) { add(if (float32) source.float else source.short / 32768f) }
        return amount == requested
    }

    fun result(rate: Int, channels: Int, codec: String, complete: Boolean): AudioMeasurements {
        check(count > 0) { "No audio samples available" }
        fun dbfs(value: Double): Double? = if (value > 0) 20 * log10(value) else null
        return AudioMeasurements(rate, channels, count.toDouble() / (channels * rate), count,
            dbfs(peak), dbfs(sqrt(power / count)), nearFullScale, complete, codec)
    }
}
