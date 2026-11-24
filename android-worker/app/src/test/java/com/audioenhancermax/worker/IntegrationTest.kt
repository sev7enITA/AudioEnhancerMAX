package com.audioenhancermax.worker
import org.junit.Test
import org.junit.Assert.*
import org.junit.Assume.assumeTrue
import kotlinx.coroutines.*
import com.google.gson.Gson
import java.io.File
import java.util.UUID
import kotlin.math.sin

/** JVM integration tests exercise the production TLS client and DSP against a real isolated Mac backend.
 * They do not stand in for Android device/Keystore/lifecycle tests. */
class IntegrationTest {
    @Test fun pinnedClientAndMacProcessingPreserveStereoAndBindReport()=runBlocking {
        val path=System.getenv("AEMAX_TEST_PAIRING")
        assumeTrue("Provide an isolated gateway fixture",path!=null && File(path).exists())
        val p=Pairing.parse(File(path!!).readText())
        val control=CompanionClient(p,UUID.randomUUID().toString())
        assertEquals(1,control.request("/v1/status").json()["protocol"].asInt)
        try {CompanionClient(p.copy(fingerprint="0".repeat(64)),UUID.randomUUID().toString()).request("/v1/status");fail("Wrong pin accepted")}catch(_:javax.net.ssl.SSLException){}
        val source=Wave(FloatArray(48000*2){if(it%2==0)(.2*sin((it/2)*2*Math.PI*440/48000)).toFloat() else 0f},48000,2)
        val bytes=source.encode()
        val sourceSha=sha256(bytes)
        val imported=control.request("/v1/files","POST",bytes,"wav").json()
        assertEquals(sourceSha,imported["sha256"].asString)
        val job=control.request("/v1/jobs","POST",Gson().toJson(mapOf("file_id" to imported["id"].asString,"profile" to "voice")).toByteArray()).json()["id"].asString
        repeat(60) {
            val state=control.request("/v1/jobs/$job").json()
            if(state["status"].asString=="failed")fail("Mac processing failed")
            if(state["status"].asString=="completed") {
                val audio=control.request("/v1/jobs/$job/audio").bytes
                val report=control.request("/v1/jobs/$job/report").json()
                val received=Wave.decode(audio)
                assertEquals(state["sha256"].asString,sha256(audio))
                assertEquals(sha256(audio),report["sha256"].asString)
                assertEquals(sourceSha,report["source_sha256"].asString)
                assertEquals(sourceSha,state["source_sha256"].asString)
                assertEquals(state["revision"].asString,report["revision"].asString)
                assertEquals(source.rate,received.rate)
                assertEquals(source.frames,received.frames)
                assertEquals(source.channels,received.channels)
                assertTrue((1 until received.samples.size step 2).all{received.samples[it]==0f})
                return@runBlocking
            }
            delay(500)
        }
        fail("Mac processing did not complete")
    }
}
