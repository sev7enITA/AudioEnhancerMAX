package com.audioenhancermax.worker

import com.google.gson.JsonParser
import java.io.ByteArrayInputStream
import java.io.ByteArrayOutputStream
import java.nio.ByteBuffer
import java.nio.ByteOrder
import org.junit.Assert.*
import org.junit.Test

class VerifyContentTest {
    @Test fun originalFingerprintAndSizeComeFromIdenticalByteStream() {
        val original = ByteArray(150000) { (it % 251).toByte() }
        val copied = ByteArrayOutputStream()
        val evidence = copyAndHash(ByteArrayInputStream(original), copied, original.size.toLong()) {}
        assertEquals(original.size.toLong(), evidence.bytes)
        assertEquals(sha256(original), evidence.digest)
        assertArrayEquals(original, copied.toByteArray())
        assertArrayEquals(original.copyOf(64), evidence.header)
        assertThrows(IllegalArgumentException::class.java) {
            copyAndHash(ByteArrayInputStream(original), ByteArrayOutputStream(), original.size.toLong() - 1) {}
        }
        assertThrows(IllegalArgumentException::class.java) {
            copyAndHash(ByteArrayInputStream(ByteArray(0)), ByteArrayOutputStream(), 1) {}
        }
    }

    @Test fun hashOnlyMismatchWithUntrustedSignerIsInconclusive() {
        val evidence = credential("Invalid", "assertion.bmffHash.mismatch", "signingCredential.untrusted")
        assertEquals("indeterminate", evidence.status)
        assertEquals("Integrity inconclusive", evidence.outcome)
        assertEquals(listOf("assertion.bmffHash.mismatch", "signingCredential.untrusted"), evidence.failureCodes)
        assertTrue(evidence.detail.contains("reader failure"))
        assertEquals("unrecognized", evidence.signerTrust)
        assertTrue(evidence.actions.isEmpty())
        assertNull(evidence.reportFingerprint)
        assertEquals("invalid", credential("Invalid", "claimSignature.mismatch", "assertion.bmffHash.mismatch").status)
        assertEquals("indeterminate", credential("Invalid").status)
    }

    @Test fun extractsOnlyManifestDeclaredActionsAndReportFingerprint() {
        val evidence = credential("Valid")
        assertEquals("valid", evidence.status)
        assertEquals("Test issuer", evidence.issuer)
        assertEquals("2026-11-20T10:09:08Z", evidence.actions.single().at)
        assertEquals("c2pa.edited", evidence.actions.single().action)
        assertEquals("Tool", evidence.actions.single().software)
        assertEquals("ab".repeat(32), evidence.reportFingerprint)
    }

    @Test fun meterHasExactMeanSquareAndCountsNearFullScale() {
        val meter = AudioMeter()
        val buffer = ByteBuffer.allocate(8).order(ByteOrder.nativeOrder())
        for (sample in listOf(16384, -32768, 0, 0)) buffer.putShort(sample.toShort())
        buffer.flip()
        assertTrue(meter.read(buffer, false, 8000, 2))
        val info = meter.result(8000, 2, "PCM", true)
        assertEquals(0.0, info.peakDbfs!!, 1e-10)
        assertEquals(-5.051499783199061, info.rmsDbfs!!, 1e-10)
        assertEquals(1, info.nearFullScaleSamples)
        assertEquals(4, info.analyzedSamples)
        assertEquals(2.0 / 8000, info.analyzedSeconds, 1e-10)
    }

    @Test fun meterLimitsFirstPortionAndDoesNotInventSilenceLevel() {
        val meter = AudioMeter()
        val samples = 8000 * AudioMeter.MaxSeconds
        val buffer = ByteBuffer.allocate((samples + 2) * 2)
        assertFalse(meter.read(buffer, false, 8000, 1))
        val info = meter.result(8000, 1, "PCM", false)
        assertEquals(30.0, info.analyzedSeconds, 1e-10)
        assertEquals(null, info.rmsDbfs)
        assertFalse(info.complete)
    }

    @Test fun shareReportUsesStableSchemaAndOmitsLocator() {
        val report = MediaVerification(
            VerifiedAsset("aa".repeat(32), 800, "audio/wav"), credential("Valid"),
            null, "unavailable", "No track",
        )
        val root = JsonParser.parseString(report.json()).asJsonObject
        assertEquals(setOf("schema", "generated_at_utc", "application", "asset", "credentials", "audio"), root.keySet())
        assertEquals(MediaVerificationSchema, root["schema"].asString)
        assertEquals(setOf("sha256", "size_bytes", "media_type"), root.getAsJsonObject("asset").keySet())
        assertEquals("unavailable", root.getAsJsonObject("audio")["status"].asString)
        assertEquals("c2pa.edited", root.getAsJsonObject("credentials").getAsJsonArray("action_timeline").first().asJsonObject["action"].asString)
    }

    private fun credential(state: String, vararg failures: String): CredentialSummary {
        val failureJson = failures.joinToString(",") { "{\"code\":\"$it\"}" }
        val root = JsonParser.parseString(
            """
            {
              "active_manifest": "asset",
              "validation_state": "$state",
              "validation_results": {"activeManifest": {"failure": [$failureJson], "success": [
                {"code": "assertion.hashedURI.match", "url": "self#jumbf=/assertions/c2pa.actions.v2"},
                {"code": "assertion.hashedURI.match", "url": "self#jumbf=/assertions/com.fabriziodegni.audioenhancermax.processing"}
              ]}},
              "manifests": {"asset": {
                "signature_info": {"issuer": "Test issuer"},
                "assertions": [
                  {"label": "c2pa.actions.v2", "data": {"actions": [
                    {"action": "c2pa.edited", "when": "2026-11-20T10:09:08Z", "softwareAgent": {"name": "Tool"}},
                    {"action": "invalid/action"}
                  ]}},
                  {"label": "com.fabriziodegni.audioenhancermax.processing",
                    "data": {"processing_report_sha256": "${"ab".repeat(32)}"}}
                ]
              }}
            }
            """.trimIndent()
        ).asJsonObject
        return summarizeCredentials(root, embedded = true, expired = false)
    }
}
