package com.audioenhancermax.worker

internal data class WorkspaceEdit(
    val start: String,
    val end: String,
    val gain: Float,
    val normalize: Boolean,
    val voice: Boolean,
    val fadeIn: Float = 0f,
    val fadeOut: Float = 0f,
    val silence: Boolean = false,
) {
    fun selection(duration: Double): ClosedFloatingPointRange<Double>? {
        val first = start.toDoubleOrNull() ?: return null
        val last = end.toDoubleOrNull() ?: return null
        return if (first in 0.0..duration && last > first && last <= duration + 0.000001) {
            first..last.coerceAtMost(duration)
        } else null
    }

    fun process(source: Wave): Pair<Wave, AudioComparison?> {
        val selected = requireNotNull(selection(source.duration)) { "Choose a valid selection before rendering" }
        if (silence) {
            val muted = source.silence(selected.start, selected.endInclusive)
            return muted to AudioComparison.match(source, muted, 0.0)
        }
        val fadeLimit = ((selected.endInclusive - selected.start) / 2).coerceAtMost(5.0)
        val edited = source.edit(
            selected.start, selected.endInclusive, gain.toDouble(), normalize, voice,
            fadeIn.toDouble().coerceAtMost(fadeLimit), fadeOut.toDouble().coerceAtMost(fadeLimit),
        )
        val offset = minOf(source.frames - 1, (selected.start * source.rate).toInt()).toDouble() / source.rate
        return edited to AudioComparison.match(source, edited, offset)
    }
}

internal data class WorkerUsage(
    val chunks: Int = 0,
    val audioSeconds: Double = 0.0,
    val dspMilliseconds: Double = 0.0,
    val lastDspMilliseconds: Double? = null,
) {
    val realtimeFactor: Double?
        get() = if (dspMilliseconds > 0) audioSeconds * 1000 / dspMilliseconds else null

    fun add(audioDuration: Double, elapsedMilliseconds: Double): WorkerUsage =
        WorkerUsage(chunks + 1, audioSeconds + audioDuration,
            dspMilliseconds + elapsedMilliseconds, elapsedMilliseconds)
}
