package com.audioenhancermax.worker

import kotlin.math.*

/**
 * AudioEnhancerMAX DSP Engine — Pure Kotlin implementation.
 * Processes audio chunks with various DSP filters, matching the
 * Python edge_worker.py processing capabilities.
 *
 * All processing is done on Float arrays representing mono audio samples
 * in the range [-1.0, 1.0].
 */
object DspEngine {

    /** Available DSP filters on this worker */
    val AVAILABLE_FILTERS = listOf(
        "remove_noise", "wind_noise_remover", "buzzing_noise_remover",
        "static_noise_remover", "reverb_echo_remover",
        "remove_breaths", "remove_long_silences", "auto_eq", "studio_sound",
        "normalize"
    )

    /**
     * Process audio with the requested filters.
     * @param audio Float array of audio samples [-1.0, 1.0]
     * @param sampleRate Sample rate in Hz
     * @param filters Map of filter names to enabled state
     * @return Processed audio samples
     */
    fun processChunk(audio: FloatArray, sampleRate: Int, filters: Map<String, Boolean>): FloatArray {
        require(sampleRate in 8000..96000 && audio.isNotEmpty() && audio.size <= (Wave.MAX_BYTES-44)/4 && audio.all { it.isFinite() }) { "Invalid audio input" }
        require(filters.filterValues { it }.keys.all { it in AVAILABLE_FILTERS }) { "Unsupported DSP filter" }
        var result = audio.copyOf()

        if (filters["remove_noise"] == true) {
            result = applyNoiseReduction(result, sampleRate)
        }
        if (filters["wind_noise_remover"] == true) {
            result = applyWindNoiseRemover(result, sampleRate)
        }
        if (filters["buzzing_noise_remover"] == true) {
            result = applyBuzzingRemover(result, sampleRate)
        }
        if (filters["static_noise_remover"] == true) {
            result = applyStaticNoiseRemover(result, sampleRate)
        }
        if (filters["reverb_echo_remover"] == true) {
            result = applyReverbRemover(result, sampleRate)
        }
        if (filters["studio_sound"] == true) {
            result = applyStudioSound(result, sampleRate)
        }
        if (filters["auto_eq"] == true) {
            result = applyAutoEq(result, sampleRate)
        }
        if (filters["normalize"] == true) {
            result = applyNormalize(result, sampleRate)
        }
        if (filters["remove_breaths"] == true) {
            result = applyBreathReduction(result, sampleRate)
        }
        if (filters["remove_long_silences"] == true) {
            result = applySilenceRemoval(result, sampleRate)
        }

        return result
    }

    // ══════════════════════════════════════════════════════════
    // Noise Reduction — Spectral Gating
    // ══════════════════════════════════════════════════════════

    private fun applyNoiseReduction(audio: FloatArray, sr: Int, strength: Float = 0.7f): FloatArray {
        val frameSize = 2048
        val hopSize = frameSize / 4
        val window = hanningWindow(frameSize)

        // Estimate noise floor from first 0.5 seconds
        val noiseFrames = (0.5 * sr / hopSize).toInt().coerceIn(1, 10)
        val noiseSpectrum = FloatArray(frameSize / 2 + 1)

        for (i in 0 until noiseFrames) {
            val start = i * hopSize
            if (start + frameSize > audio.size) break
            val frame = FloatArray(frameSize) { k -> audio[start + k] * window[k] }
            val mag = computeMagnitudeSpectrum(frame)
            for (j in mag.indices) noiseSpectrum[j] += mag[j]
        }
        for (j in noiseSpectrum.indices) noiseSpectrum[j] /= noiseFrames

        // Apply spectral gating
        val output = FloatArray(audio.size)
        val overlap = FloatArray(audio.size)

        var pos = 0
        while (pos + frameSize <= audio.size) {
            val frame = FloatArray(frameSize) { k -> audio[pos + k] * window[k] }
            val (real, imag) = computeFFT(frame)

            // Spectral gate
            val threshold = strength * 1.5f
            for (j in 0..frameSize / 2) {
                val mag = sqrt(real[j] * real[j] + imag[j] * imag[j])
                val gate = if (mag > noiseSpectrum[j.coerceAtMost(noiseSpectrum.size - 1)] * threshold) 1.0f
                else (1.0f - strength * 0.85f).coerceAtLeast(0.15f)

                real[j] *= gate
                imag[j] *= gate
                // Mirror for IFFT
                if (j > 0 && j < frameSize / 2) {
                    real[frameSize - j] *= gate
                    imag[frameSize - j] *= gate
                }
            }

            val processed = computeIFFT(real, imag)
            for (k in 0 until frameSize) {
                if (pos + k < output.size) {
                    output[pos + k] += processed[k] * window[k]
                    overlap[pos + k] += window[k] * window[k]
                }
            }
            pos += hopSize
        }

        // Normalize by overlap
        for (i in output.indices) {
            if (overlap[i] > 1e-8f) output[i] /= overlap[i]
            else output[i] = audio[i]
        }

        // Wet/dry mix
        val wet = (strength * 0.85f).coerceAtMost(0.85f)
        for (i in output.indices) {
            output[i] = output[i] * wet + audio[i] * (1.0f - wet)
        }

        return output
    }

    // ══════════════════════════════════════════════════════════
    // Wind Noise Remover — Highpass + Spectral Gating
    // ══════════════════════════════════════════════════════════

    private fun applyWindNoiseRemover(audio: FloatArray, sr: Int): FloatArray {
        // Butterworth highpass at 120Hz to remove wind rumble
        var result = applyBiquadFilter(audio, sr.toFloat(), 120f, FilterType.HIGHPASS, 0.707f)
        // Gentle noise reduction for remaining wind artifacts
        result = applyNoiseReduction(result, sr, 0.4f)
        return result
    }

    // ══════════════════════════════════════════════════════════
    // Buzzing Remover — Notch Filter at 50/60Hz + Harmonics
    // ══════════════════════════════════════════════════════════

    private fun applyBuzzingRemover(audio: FloatArray, sr: Int): FloatArray {
        var result = audio.copyOf()
        // Remove 50Hz and harmonics (European mains)
        for (harmonic in 1..4) {
            result = applyBiquadFilter(result, sr.toFloat(), 50f * harmonic, FilterType.NOTCH, 30f)
        }
        // Remove 60Hz and harmonics (US mains)
        for (harmonic in 1..4) {
            result = applyBiquadFilter(result, sr.toFloat(), 60f * harmonic, FilterType.NOTCH, 30f)
        }
        return result
    }

    // ══════════════════════════════════════════════════════════
    // Static Noise Remover — Spectral Gating (stationary)
    // ══════════════════════════════════════════════════════════

    private fun applyStaticNoiseRemover(audio: FloatArray, sr: Int): FloatArray {
        return applyNoiseReduction(audio, sr, 0.6f)
    }

    // ══════════════════════════════════════════════════════════
    // Reverb/Echo Remover — Spectral subtraction
    // ══════════════════════════════════════════════════════════

    private fun applyReverbRemover(audio: FloatArray, sr: Int): FloatArray {
        val frameSize = 2048
        val hopSize = frameSize / 4
        val window = hanningWindow(frameSize)
        val output = FloatArray(audio.size)
        val overlap = FloatArray(audio.size)

        // Simple spectral subtraction with harmonic preservation
        var prevMag: FloatArray? = null
        var pos = 0
        while (pos + frameSize <= audio.size) {
            val frame = FloatArray(frameSize) { k -> audio[pos + k] * window[k] }
            val (real, imag) = computeFFT(frame)
            val currentMag = FloatArray(frameSize / 2 + 1) { j ->
                sqrt(real[j] * real[j] + imag[j] * imag[j])
            }

            if (prevMag != null) {
                for (j in 0..frameSize / 2) {
                    // Reduce components that persist across frames (reverb tail)
                    val reverbEstimate = minOf(currentMag[j], prevMag!![j]) * 0.5f
                    val gain = ((currentMag[j] - reverbEstimate) / (currentMag[j] + 1e-10f))
                        .coerceIn(0.3f, 1.0f)
                    real[j] *= gain
                    imag[j] *= gain
                    if (j > 0 && j < frameSize / 2) {
                        real[frameSize - j] *= gain
                        imag[frameSize - j] *= gain
                    }
                }
            }
            prevMag = currentMag

            val processed = computeIFFT(real, imag)
            for (k in 0 until frameSize) {
                if (pos + k < output.size) {
                    output[pos + k] += processed[k] * window[k]
                    overlap[pos + k] += window[k] * window[k]
                }
            }
            pos += hopSize
        }

        for (i in output.indices) {
            if (overlap[i] > 1e-8f) output[i] /= overlap[i]
            else output[i] = audio[i]
        }
        return output
    }

    // ══════════════════════════════════════════════════════════
    // Studio Sound — Broadcast chain
    // ══════════════════════════════════════════════════════════

    private fun applyStudioSound(audio: FloatArray, sr: Int): FloatArray {
        var result = audio.copyOf()
        val srf = sr.toFloat()

        // Highpass 80Hz — remove rumble
        result = applyBiquadFilter(result, srf, 80f, FilterType.HIGHPASS, 0.707f)
        // Warm shelf at 150Hz (+1dB)
        result = applyBiquadFilter(result, srf, 150f, FilterType.LOW_SHELF, 0.707f, 1.0f)
        // Presence boost at 4kHz (+1.5dB)
        result = applyBiquadFilter(result, srf, 4000f, FilterType.HIGH_SHELF, 0.707f, 1.5f)
        // De-esser at 6kHz (-3dB)
        result = applyBiquadFilter(result, srf, 6000f, FilterType.PEAKING, 2.0f, -3.0f)
        // Gentle compression 2:1
        result = applyCompressor(result, sr, thresholdDb = -18f, ratio = 2.0f, attackMs = 25f, releaseMs = 150f)
        // Makeup gain +1.5dB
        val gain = 10f.pow(1.5f / 20f)
        for (i in result.indices) result[i] *= gain
        // Limiter at -1dB
        result = applyLimiter(result, -1.0f)

        return result
    }

    // ══════════════════════════════════════════════════════════
    // Auto EQ — Broadcast voice profile
    // ══════════════════════════════════════════════════════════

    private fun applyAutoEq(audio: FloatArray, sr: Int): FloatArray {
        var result = audio.copyOf()
        val srf = sr.toFloat()

        // Highpass 80Hz
        result = applyBiquadFilter(result, srf, 80f, FilterType.HIGHPASS, 0.707f)
        // Low shelf 150Hz (+1dB) — warmth
        result = applyBiquadFilter(result, srf, 150f, FilterType.LOW_SHELF, 0.707f, 1.0f)
        // Cut mud at 250Hz (-1.5dB)
        result = applyBiquadFilter(result, srf, 250f, FilterType.PEAKING, 1.0f, -1.5f)
        // Presence at 2.5kHz (+1.5dB)
        result = applyBiquadFilter(result, srf, 2500f, FilterType.PEAKING, 1.0f, 1.5f)
        // Clarity at 5kHz (+1dB)
        result = applyBiquadFilter(result, srf, 5000f, FilterType.PEAKING, 0.7f, 1.0f)
        // Air at 8kHz (+0.5dB)
        result = applyBiquadFilter(result, srf, 8000f, FilterType.HIGH_SHELF, 0.707f, 0.5f)
        // Lowpass at 16kHz to remove harsh highs
        result = applyBiquadFilter(result, srf, 16000f, FilterType.LOWPASS, 0.707f)

        return result
    }

    // ══════════════════════════════════════════════════════════
    // Normalize — Peak normalization
    // ══════════════════════════════════════════════════════════

    private fun applyNormalize(audio: FloatArray, sr: Int, targetLufs: Float = -16f): FloatArray {
        val peak = audio.maxOfOrNull { abs(it) } ?: return audio
        if (peak <= 0f) return audio

        val targetPeak = 10f.pow(targetLufs / 20f)
        val gain = targetPeak / peak
        val result = FloatArray(audio.size) { (audio[it] * gain).coerceIn(-1f, 1f) }
        return result
    }

    // ══════════════════════════════════════════════════════════
    // Breath Reduction
    // ══════════════════════════════════════════════════════════

    private fun applyBreathReduction(audio: FloatArray, sr: Int): FloatArray {
        val result = audio.copyOf()
        val frameMs = 30
        val frameSamples = sr * frameMs / 1000
        val crossfadeSamples = sr * 30 / 1000 // 30ms crossfade
        val maxAttenuation = 0.2f // Cap at 80% reduction

        var i = 0
        while (i + frameSamples < audio.size) {
            val frameEnd = minOf(i + frameSamples, audio.size)
            val frame = audio.sliceArray(i until frameEnd)

            // Breath detection: low energy, concentrated in 200-2000Hz range
            val rms = sqrt(frame.map { it * it }.average().toFloat())
            val isLikelyBreath = rms in 0.001f..0.05f

            if (isLikelyBreath) {
                for (j in i until frameEnd) {
                    // Apply smooth attenuation
                    val distFromEdge = minOf(j - i, frameEnd - 1 - j).toFloat()
                    val fade = if (distFromEdge < crossfadeSamples) distFromEdge / crossfadeSamples else 1f
                    val attenuation = maxAttenuation + (1f - maxAttenuation) * (1f - fade)
                    result[j] = audio[j] * attenuation
                }
            }
            i += frameSamples
        }
        return result
    }

    // ══════════════════════════════════════════════════════════
    // Silence Removal
    // ══════════════════════════════════════════════════════════

    private fun applySilenceRemoval(audio: FloatArray, sr: Int): FloatArray {
        val frameSamples = (sr / 100).coerceAtLeast(1)
        val result = ArrayList<Float>(audio.size)
        var silenceStart = -1
        fun flush(end: Int) {
            if (silenceStart >= 0) {
                val count = end - silenceStart
                val kept = if (count > sr) sr / 2 else count
                for (j in silenceStart until silenceStart + kept) result.add(audio[j])
                silenceStart = -1
            }
        }
        var pos = 0
        while (pos < audio.size) {
            val end = minOf(pos + frameSamples, audio.size)
            var energy = 0.0
            for (j in pos until end) energy += audio[j] * audio[j]
            if (sqrt(energy / (end - pos)) <= 0.01) {
                if (silenceStart < 0) silenceStart = pos
            } else {
                flush(pos)
                for (j in pos until end) result.add(audio[j])
            }
            pos = end
        }
        flush(audio.size)
        return result.toFloatArray()
    }

    // ══════════════════════════════════════════════════════════
    // Biquad Filter (IIR)
    // ══════════════════════════════════════════════════════════

    enum class FilterType {
        LOWPASS, HIGHPASS, PEAKING, LOW_SHELF, HIGH_SHELF, NOTCH
    }

    private fun applyBiquadFilter(
        audio: FloatArray,
        sr: Float,
        freq: Float,
        type: FilterType,
        q: Float,
        gainDb: Float = 0f
    ): FloatArray {
        val w0 = 2.0 * PI * minOf(freq, sr * 0.45f) / sr
        val sinW0 = sin(w0)
        val cosW0 = cos(w0)
        val alpha = sinW0 / (2.0 * q)
        val a = 10.0.pow(gainDb / 40.0)

        val b0: Double
        val b1: Double
        val b2: Double
        val a0: Double
        val a1: Double
        val a2: Double

        when (type) {
            FilterType.LOWPASS -> {
                b0 = (1.0 - cosW0) / 2.0
                b1 = 1.0 - cosW0
                b2 = (1.0 - cosW0) / 2.0
                a0 = 1.0 + alpha
                a1 = -2.0 * cosW0
                a2 = 1.0 - alpha
            }
            FilterType.HIGHPASS -> {
                b0 = (1.0 + cosW0) / 2.0
                b1 = -(1.0 + cosW0)
                b2 = (1.0 + cosW0) / 2.0
                a0 = 1.0 + alpha
                a1 = -2.0 * cosW0
                a2 = 1.0 - alpha
            }
            FilterType.PEAKING -> {
                b0 = 1.0 + alpha * a
                b1 = -2.0 * cosW0
                b2 = 1.0 - alpha * a
                a0 = 1.0 + alpha / a
                a1 = -2.0 * cosW0
                a2 = 1.0 - alpha / a
            }
            FilterType.LOW_SHELF -> {
                val sqrtA = sqrt(a)
                b0 = a * ((a + 1.0) - (a - 1.0) * cosW0 + 2.0 * sqrtA * alpha)
                b1 = 2.0 * a * ((a - 1.0) - (a + 1.0) * cosW0)
                b2 = a * ((a + 1.0) - (a - 1.0) * cosW0 - 2.0 * sqrtA * alpha)
                a0 = (a + 1.0) + (a - 1.0) * cosW0 + 2.0 * sqrtA * alpha
                a1 = -2.0 * ((a - 1.0) + (a + 1.0) * cosW0)
                a2 = (a + 1.0) + (a - 1.0) * cosW0 - 2.0 * sqrtA * alpha
            }
            FilterType.HIGH_SHELF -> {
                val sqrtA = sqrt(a)
                b0 = a * ((a + 1.0) + (a - 1.0) * cosW0 + 2.0 * sqrtA * alpha)
                b1 = -2.0 * a * ((a - 1.0) + (a + 1.0) * cosW0)
                b2 = a * ((a + 1.0) + (a - 1.0) * cosW0 - 2.0 * sqrtA * alpha)
                a0 = (a + 1.0) - (a - 1.0) * cosW0 + 2.0 * sqrtA * alpha
                a1 = 2.0 * ((a - 1.0) - (a + 1.0) * cosW0)
                a2 = (a + 1.0) - (a - 1.0) * cosW0 - 2.0 * sqrtA * alpha
            }
            FilterType.NOTCH -> {
                b0 = 1.0
                b1 = -2.0 * cosW0
                b2 = 1.0
                a0 = 1.0 + alpha
                a1 = -2.0 * cosW0
                a2 = 1.0 - alpha
            }
        }

        // Apply Direct Form II
        val output = FloatArray(audio.size)
        var x1 = 0.0; var x2 = 0.0
        var y1 = 0.0; var y2 = 0.0

        val nb0 = b0 / a0; val nb1 = b1 / a0; val nb2 = b2 / a0
        val na1 = a1 / a0; val na2 = a2 / a0

        for (i in audio.indices) {
            val x = audio[i].toDouble()
            val y = nb0 * x + nb1 * x1 + nb2 * x2 - na1 * y1 - na2 * y2
            output[i] = y.toFloat()
            x2 = x1; x1 = x
            y2 = y1; y1 = y
        }

        return output
    }

    // ══════════════════════════════════════════════════════════
    // Compressor
    // ══════════════════════════════════════════════════════════

    private fun applyCompressor(
        audio: FloatArray, sr: Int,
        thresholdDb: Float, ratio: Float,
        attackMs: Float, releaseMs: Float
    ): FloatArray {
        val output = audio.copyOf()
        val attackCoeff = exp(-1.0f / (sr * attackMs / 1000f))
        val releaseCoeff = exp(-1.0f / (sr * releaseMs / 1000f))
        val threshold = 10f.pow(thresholdDb / 20f)

        var envelope = 0f

        for (i in output.indices) {
            val inputLevel = abs(output[i])

            // Envelope follower
            envelope = if (inputLevel > envelope) {
                attackCoeff * envelope + (1f - attackCoeff) * inputLevel
            } else {
                releaseCoeff * envelope + (1f - releaseCoeff) * inputLevel
            }

            // Compute gain reduction
            if (envelope > threshold) {
                val overDb = 20f * log10(envelope / threshold)
                val reductionDb = overDb * (1f - 1f / ratio)
                val gain = 10f.pow(-reductionDb / 20f)
                output[i] *= gain
            }
        }
        return output
    }

    // ══════════════════════════════════════════════════════════
    // Limiter
    // ══════════════════════════════════════════════════════════

    private fun applyLimiter(audio: FloatArray, thresholdDb: Float): FloatArray {
        val threshold = 10f.pow(thresholdDb / 20f)
        return FloatArray(audio.size) {
            audio[it].coerceIn(-threshold, threshold)
        }
    }

    // ══════════════════════════════════════════════════════════
    // FFT Utilities (Radix-2 Cooley-Tukey)
    // ══════════════════════════════════════════════════════════

    private fun hanningWindow(size: Int): FloatArray {
        return FloatArray(size) { i ->
            (0.5 * (1.0 - cos(2.0 * PI * i / (size - 1)))).toFloat()
        }
    }

    private fun computeMagnitudeSpectrum(frame: FloatArray): FloatArray {
        val (real, imag) = computeFFT(frame)
        return FloatArray(frame.size / 2 + 1) { j ->
            sqrt(real[j] * real[j] + imag[j] * imag[j])
        }
    }

    private fun computeFFT(input: FloatArray): Pair<FloatArray, FloatArray> {
        val n = input.size
        val real = input.copyOf()
        val imag = FloatArray(n)
        fftInPlace(real, imag, false)
        return Pair(real, imag)
    }

    private fun computeIFFT(real: FloatArray, imag: FloatArray): FloatArray {
        val n = real.size
        val r = real.copyOf()
        val im = imag.copyOf()
        fftInPlace(r, im, true)
        val scale = 1.0f / n
        for (i in r.indices) r[i] *= scale
        return r
    }

    private fun fftInPlace(real: FloatArray, imag: FloatArray, inverse: Boolean) {
        val n = real.size
        if (n <= 1) return

        // Bit-reversal permutation
        var j = 0
        for (i in 1 until n) {
            var bit = n shr 1
            while (j and bit != 0) {
                j = j xor bit
                bit = bit shr 1
            }
            j = j xor bit
            if (i < j) {
                var tmp = real[i]; real[i] = real[j]; real[j] = tmp
                tmp = imag[i]; imag[i] = imag[j]; imag[j] = tmp
            }
        }

        // Cooley-Tukey
        var len = 2
        while (len <= n) {
            val angle = (2.0 * PI / len * if (inverse) -1.0 else 1.0)
            val wReal = cos(angle).toFloat()
            val wImag = sin(angle).toFloat()

            var i = 0
            while (i < n) {
                var curReal = 1.0f
                var curImag = 0.0f
                for (k in 0 until len / 2) {
                    val uR = real[i + k]
                    val uI = imag[i + k]
                    val vR = real[i + k + len / 2] * curReal - imag[i + k + len / 2] * curImag
                    val vI = real[i + k + len / 2] * curImag + imag[i + k + len / 2] * curReal
                    real[i + k] = uR + vR
                    imag[i + k] = uI + vI
                    real[i + k + len / 2] = uR - vR
                    imag[i + k + len / 2] = uI - vI
                    val newCurReal = curReal * wReal - curImag * wImag
                    val newCurImag = curReal * wImag + curImag * wReal
                    curReal = newCurReal
                    curImag = newCurImag
                }
                i += len
            }
            len = len shl 1
        }
    }
}
