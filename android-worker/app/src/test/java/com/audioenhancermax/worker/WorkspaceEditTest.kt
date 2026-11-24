package com.audioenhancermax.worker

import org.junit.Assert.*
import org.junit.Test

class WorkspaceEditTest {
    @Test fun stereoTrimAndFadesPreserveOriginalAndReferenceTimes() {
        val samples = FloatArray(8_000 * 2) { if (it % 2 == 0) .8f else -.4f }
        val source = Wave(samples.copyOf(), 8_000, 2)
        val selection = WorkspaceEdit("0.125", "0.875", 0f, false, false, .1f, .1f)
        val (edited, comparison) = selection.process(source)
        assertEquals(6000, edited.frames)
        assertEquals(2, edited.channels)
        assertEquals(.125, requireNotNull(comparison).sourceStart, 0.0)
        assertEquals(.75, comparison.duration, 0.0)
        assertEquals(0f, edited.samples[0], 0f)
        assertEquals(0f, edited.samples[edited.samples.lastIndex], 0f)
        assertEquals(.8f, edited.samples[4000], 0f)
        assertEquals(-.4f, edited.samples[4001], 0f)
        assertArrayEquals(samples, source.samples, 0f)
    }

    @Test fun invalidSelectionIsRejectedAndTrimCanShrinkOldFades() {
        val source = Wave(FloatArray(8000) { .5f }, 8000, 1)
        val draft = WorkspaceEdit("0.85", "0.95", 0f, true, false, 5f, 5f)
        assertNotNull(draft.selection(source.duration))
        assertNull(draft.copy(start = "0.95").selection(source.duration))
        assertNull(draft.copy(end = "Infinity").selection(source.duration))
        assertThrows(IllegalArgumentException::class.java) { draft.copy(start = "NaN").process(source) }
        val (output, _) = draft.process(source)
        assertEquals(800, output.frames)
        assertEquals(0f, output.samples.first(), 0f)
        assertEquals(0f, output.samples.last(), 0f)
        assertEquals(.89125f, output.samples.max(), 1e-5f)
    }

    @Test fun workerThroughputAggregatesActualReturnedAudioAndMeasuredCompute() {
        val initial = WorkerUsage()
        assertNull(initial.realtimeFactor)
        val usage = initial.add(2.0, 40.0).add(4.0, 100.0)
        assertEquals(2, usage.chunks)
        assertEquals(6.0, usage.audioSeconds, 0.0)
        assertEquals(140.0, usage.dspMilliseconds, 0.0)
        assertEquals(100.0, requireNotNull(usage.lastDspMilliseconds), 0.0)
        assertEquals(6000.0 / 140, requireNotNull(usage.realtimeFactor), 1e-6)
        assertEquals(0, initial.chunks)
    }

    @Test fun silenceKeepsStereoAndTimelineWithOriginalUntouched() {
        val source = Wave(FloatArray(16_000) { if (it % 2 == 0) .5f else -.2f }, 8000, 2)
        val effect = WorkspaceEdit("0.25", "0.5", 0f, false, false, silence = true)
        val (edited, comparison) = effect.process(source)
        assertEquals(source.frames, edited.frames)
        assertTrue((4_000 until 8_000).all { edited.samples[it] == 0f })
        assertEquals(-.2f, edited.samples[3999], 0f)
        assertEquals(.5f, edited.samples[8000], 0f)
        assertEquals(-.2f, source.samples[4001], 0f)
        assertEquals(0.0, requireNotNull(comparison).sourceStart, 0.0)
        assertEquals(source.duration, comparison.duration, 0.0)
    }
}
