package com.audioenhancermax.worker
import org.junit.Test
import org.junit.Assert.*

class CoreTest {
    @Test fun comparesExactTrimAndOnlyAttenuatesListening() {
        val source=Wave(FloatArray(24000){if(it in 8000 until 16000) 0.2f else 0.8f},8000,1)
        val result=source.edit(1.0,2.0,20*Math.log10(2.0),false,false)
        val span=requireNotNull(AudioComparison.match(source,result,1.0))
        assertEquals(1.0,span.sourceStart,0.0)
        assertEquals(1.0,span.duration,0.0)
        assertTrue(span.contains(1.5))
        assertFalse(span.contains(0.9))
        assertFalse(span.contains(2.0))
        assertEquals(1f,span.originalGain,0f)
        assertEquals(0.5f,span.resultGain,1e-6f)
        assertEquals(0.4f,result.samples[0],1e-6f)
        assertNull(AudioComparison.match(source,result,2.5))
        val silence=Wave(FloatArray(8000),8000,1)
        assertEquals(1f,requireNotNull(AudioComparison.match(source,silence,1.0)).originalGain,0f)
    }
    @Test fun stereoRoundTripAndIndependentChannels() {
        val wave=Wave(floatArrayOf(.25f,-.5f,.1f,.7f),48000,2)
        assertArrayEquals(wave.samples,Wave.decode(wave.encode()).samples,0f)
        val result=Wave(FloatArray(200){if(it%2==0).2f else 0f},8000,2).autoEQ()
        assertEquals(200,result.samples.size);assertTrue((1 until 200 step 2).all{result.samples[it]==0f})
    }
    @Test fun preservesUntrimmedTailAndOriginal() {
        val wave=Wave(FloatArray(4811){.2f},48000,1)
        assertArrayEquals(wave.samples,wave.edit(0.0,wave.duration,0.0,false,false).samples,0f)
        assertEquals(1920,wave.edit(.01,.05,6.0,false,false).frames);assertEquals(4811,wave.frames)
    }
    @Test fun silenceRegression() {
        val short=FloatArray(38400)
        assertEquals(short.size,DspEngine.processChunk(short,48000,mapOf("remove_long_silences" to true)).size)
        val tail=FloatArray(4811){.4f}
        assertArrayEquals(tail,DspEngine.processChunk(tail,48000,mapOf("remove_long_silences" to true)),0f)
        assertEquals(24000,DspEngine.processChunk(FloatArray(96000),48000,mapOf("remove_long_silences" to true)).size)
    }
    @Test fun rejectsFalseCapabilitiesAndBadAudio() {
        assertFalse("remove_mouth_sounds" in DspEngine.AVAILABLE_FILTERS)
        assertFalse("frequency_restoration" in DspEngine.AVAILABLE_FILTERS)
        assertThrows(IllegalArgumentException::class.java){DspEngine.processChunk(floatArrayOf(.2f),48000,mapOf("remove_mouth_sounds" to true))}
        assertThrows(IllegalArgumentException::class.java){Wave(floatArrayOf(Float.NaN),48000,1)}
        assertThrows(IllegalArgumentException::class.java){Wave.decode(Wave(floatArrayOf(.2f),48000,1).encode().dropLast(1).toByteArray())}
    }
    @Test fun portableEQGolden() {
        val result=Wave(FloatArray(64){if(it==0).5f else 0f},48000,1).autoEQ()
        val expected=floatArrayOf(0.2537388801574707f,0.3574135899543762f,-0.017744405195116997f,-0.0826520249247551f,0.025471916422247887f,-0.03540879487991333f,-0.026337983086705208f,-0.016061006113886833f,-0.021267317235469818f,-0.016432220116257668f,-0.014093846082687378f,-0.012847471050918102f,-0.010575912892818451f,-0.008943693712353706f,-0.007497862447053194f,-0.006224635522812605f)
        expected.indices.forEach{assertEquals(expected[it],result.samples[it],0.00001f)}
    }
    @Test fun musicDraftInvalidationAndSeparateLyrics() {
        val draft=MusicDraft(description="A calm opening",lyrics="Separate words").build()
        assertTrue(draft.canExport);assertFalse(draft.prompt.contains(draft.lyrics));assertFalse(draft.copy(bpm="100").canExport)
        assertThrows(IllegalArgumentException::class.java){draft.copy(duration="0").build()}
    }
    @Test fun pairingValidation() {
        fun code(url:String)="""{"protocol":1,"endpoint":"$url","fingerprint":"${"a".repeat(64)}","token":"${"b".repeat(32)}"}"""
        assertEquals(1,Pairing.parse(code("https://192.168.1.2:4321")).protocol)
        for(url in listOf("http://localhost","https://user:pass@localhost","https://localhost/path"))assertThrows(IllegalArgumentException::class.java){Pairing.parse(code(url))}
    }
}
