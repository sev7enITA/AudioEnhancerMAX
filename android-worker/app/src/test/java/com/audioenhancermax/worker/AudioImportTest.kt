package com.audioenhancermax.worker

import org.junit.Test
import org.junit.Assert.*
import java.nio.ByteBuffer
import java.nio.ByteOrder

class AudioImportTest {
    @Test fun pickerOnlyAdvertisesImplementedAudioFormats() {
        assertTrue(AudioImportPolicy.mimeTypes.contains("audio/*"))
        assertTrue(AudioImportPolicy.mimeTypes.contains("video/quicktime"))
        assertFalse(AudioImportPolicy.mimeTypes.any { it.startsWith("image/") })
    }
    @Test fun waveformBinsCoverTailShortClipsAndBothChannels() {
        val tail=Wave(FloatArray(149){if(it==148)0.8f else 0f},48000,1).overview()
        assertEquals(0.8f,tail.last(),0f)
        assertEquals(100,tail.size)
        assertTrue(Wave(floatArrayOf(-0.5f),48000,1).overview().all{it==0.5f})
        val stereo=Wave(floatArrayOf(0f,0.9f,0.3f,0f),48000,2).overview(2)
        assertArrayEquals(floatArrayOf(0.9f,0.3f),stereo,0f)
    }
    @Test fun selectedFormatRejectsOtherContainersAndSeparatesAudioFromVideo() {
        assertTrue(AudioImportPolicy.Filter.WAV.accepts(AudioImportPolicy.Kind.WAV))
        assertFalse(AudioImportPolicy.Filter.MP3.accepts(AudioImportPolicy.Kind.WAV))
        assertTrue(AudioImportPolicy.Filter.M4A_AAC.accepts(AudioImportPolicy.Kind.MP4,false))
        assertFalse(AudioImportPolicy.Filter.M4A_AAC.accepts(AudioImportPolicy.Kind.MP4,true))
        assertTrue(AudioImportPolicy.Filter.VIDEO.accepts(AudioImportPolicy.Kind.MP4,true))
        assertFalse(AudioImportPolicy.Filter.VIDEO.accepts(AudioImportPolicy.Kind.MP4,false))
        assertThrows(IllegalArgumentException::class.java){AudioImportPolicy.Filter.FLAC.validate(AudioImportPolicy.Kind.MP3)}
        for(filter in AudioImportPolicy.Filter.entries.filter{it!=AudioImportPolicy.Filter.ALL}) {
            assertFalse(filter.mimeTypes.any{it=="*/*" || it=="audio/*"})
        }
    }
    @Test fun detectsWaveAndBothMp3HeaderStyles() {
        assertEquals(AudioImportPolicy.Kind.WAV, AudioImportPolicy.classify(Wave(floatArrayOf(.1f), 44100, 1).encode().take(12).toByteArray()))
        assertEquals(AudioImportPolicy.Kind.MP3, AudioImportPolicy.classify("ID3\u0004\u0000\u0000".toByteArray()))
        assertEquals(AudioImportPolicy.Kind.MP3, AudioImportPolicy.classify(byteArrayOf(0xff.toByte(), 0xfb.toByte(), 0x90.toByte(), 0)))
    }
    @Test fun rejectsImagesAndOtherFormatsRegardlessOfTheirFileName() {
        for (bytes in listOf(byteArrayOf(0xff.toByte(), 0xd8.toByte(), 0xff.toByte(), 0xe0.toByte()),
            byteArrayOf(0x89.toByte(), 0x50, 0x4e, 0x47),
            "RIFF1234AVI ".toByteArray(), byteArrayOf(), byteArrayOf(0xff.toByte(), 0xff.toByte(), 0x90.toByte(), 0))) {
            assertThrows(IllegalArgumentException::class.java) { AudioImportPolicy.classify(bytes) }
        }
    }
    @Test fun mp4ContainerAndReplacementTimelineValidation() {
        assertEquals(AudioImportPolicy.Kind.MP4, AudioImportPolicy.classify(byteArrayOf(0,0,0,32)+"ftypisom".toByteArray()))
        assertEquals(AudioImportPolicy.Kind.MP4, AudioImportPolicy.classify(byteArrayOf(0,0,0,32)+"ftypqt  ".toByteArray()))
        val source=Wave(FloatArray(48000){.1f},48000,1)
        AudioImportPolicy.validateReplacement(source.edit(0.0,1.0,-6.0,false,true),source)
        assertThrows(IllegalArgumentException::class.java) { AudioImportPolicy.validateReplacement(source.edit(0.0,0.5,0.0,false,false),source) }
        assertThrows(IllegalArgumentException::class.java) { AudioImportPolicy.validateReplacement(Wave(source.samples,44100,1),source) }
    }
    @Test fun decodesPcm16OffsetAndBothChannelsWithoutChangingInputPosition() {
        val buffer = ByteBuffer.allocate(12).order(ByteOrder.nativeOrder())
        buffer.putInt(1234).putShort(Short.MIN_VALUE).putShort(Short.MAX_VALUE).putShort(0).putShort(16384)
        buffer.flip(); buffer.position(4)
        val pcm = ImportedPcm()
        pcm.append(buffer, false, 2)
        assertEquals(4, buffer.position())
        val wave = pcm.finish(44100, 2)
        assertEquals(2, wave.frames)
        assertArrayEquals(floatArrayOf(-1f, 32767f/32768f, 0f, .5f), wave.samples, 0f)
    }
    @Test fun collectsFloatChunksAndEnforcesDecodedBudgetAcrossChunks() {
        val pcm = ImportedPcm(3)
        fun chunk(vararg samples: Float) = ByteBuffer.allocate(samples.size * 4).order(ByteOrder.nativeOrder()).apply {
            samples.forEach { putFloat(it) }; flip()
        }
        pcm.append(chunk(.1f, -.2f), true, 1)
        pcm.append(chunk(.3f), true, 1)
        assertThrows(IllegalArgumentException::class.java) { pcm.append(chunk(.4f), true, 1) }
        assertArrayEquals(floatArrayOf(.1f, -.2f, .3f), pcm.finish(48000, 1).samples, 0f)
    }
    @Test fun rejectsInvalidPcmAndEmptyAudio() {
        assertThrows(IllegalArgumentException::class.java) { ImportedPcm().append(ByteBuffer.allocate(3), false, 1) }
        assertThrows(IllegalArgumentException::class.java) { ImportedPcm().append(ByteBuffer.allocate(2), false, 2) }
        assertThrows(IllegalArgumentException::class.java) { ImportedPcm().finish(44100, 1) }
        val nan = ByteBuffer.allocate(4).order(ByteOrder.nativeOrder()).putFloat(Float.NaN).apply { flip() }
        assertThrows(IllegalArgumentException::class.java) { ImportedPcm().append(nan, true, 1) }
    }
}
