package com.audioenhancermax.worker

import com.google.gson.JsonParser
import org.junit.Assert.*
import org.junit.Test

class NearbyPairingTest {
    private val fingerprint = "2".repeat(64)

    private fun record(host: String = "192.168.12.4", port: String = "7210",
                       pin: String = fingerprint, version: String = "1"): Map<String, ByteArray> =
        mapOf("v" to version, "host" to host, "port" to port, "fp" to pin).mapValues { it.value.toByteArray() }

    @Test fun onlyCanonicalPrivateAddressesAndMatchingPortsCanBeDiscovered() {
        for (host in listOf("10.0.0.15", "172.16.0.9", "172.31.255.11", "192.168.12.4")) {
            val found = requireNotNull(NearbyMac.fromRecord("My Mac", 7210, record(host=host)))
            assertEquals("https://$host:7210", found.endpoint)
        }
        for (host in listOf("127.0.0.1", "100.64.0.1", "172.15.0.1", "172.32.0.1", "192.169.0.1",
            "192.168.012.4", "192.168.256.0", "192.168.1.2/path", "localhost", "::1", "8.8.8.8")) {
            assertNull(host, NearbyMac.fromRecord("Mac", 7210, record(host=host)))
        }
        assertNull(NearbyMac.fromRecord("Mac", 7211, record()))
        assertNull(NearbyMac.fromRecord("Mac", 0, record(port="0")))
        assertNull(NearbyMac.fromRecord("Mac", 65536, record(port="65536")))
        assertNull(NearbyMac.fromRecord("Mac", 7210, record(pin="A".repeat(64))))
        assertNull(NearbyMac.fromRecord("Mac", 7210, record(version="2")))
        assertNull(NearbyMac.fromRecord("Mac", 7210, record() - "fp"))
    }

    @Test fun comparisonUsesUnsignedIntegerAndPreservesLeadingZero() {
        val nonce = "0".repeat(64)
        val serverNonce = "b".repeat(64)
        assertEquals("60e05bd1b195af2f94112fa7197a5c88289058840ce7c6df9693756bc6250f55", NearbyPairingProtocol.commitment(nonce))
        assertEquals("01956450", NearbyPairingProtocol.comparisonCode(fingerprint,nonce,serverNonce))
        val generated=NearbyPairingProtocol.nonce()
        assertTrue(NearbyPairingProtocol.hex64.matches(generated))
        assertNotEquals(nonce,generated)
    }

    @Test fun approvalMustMatchDiscoveredAddressAndPin() {
        val mac=requireNotNull(NearbyMac.fromRecord("Mac",7210,record()))
        fun approval(endpoint: String, pin: String, version: String="1") = JsonParser.parseString(
            """{"status":"approved","pairing":{"protocol":$version,"endpoint":"$endpoint","fingerprint":"$pin","token":"${"t".repeat(43)}"}}"""
        ).asJsonObject
        val pairing=NearbyPairingProtocol.approvedPairing(mac,approval(mac.endpoint,fingerprint))
        assertEquals(mac.endpoint,pairing.endpoint)
        assertEquals(fingerprint,pairing.fingerprint)
        assertThrows(IllegalArgumentException::class.java) {
            NearbyPairingProtocol.approvedPairing(mac,approval("https://192.168.12.5:7210",fingerprint))
        }
        assertThrows(IllegalArgumentException::class.java) {
            NearbyPairingProtocol.approvedPairing(mac,approval(mac.endpoint,"3".repeat(64)))
        }
    }

    @Test fun requestIdentifiersAndNonceAreStrictlyChecked() {
        val id="a".repeat(32)
        val nonce="3".repeat(64)
        fun start(request: String, server: String) =
            JsonParser.parseString("""{"request_id":"$request","server_nonce":"$server"}""").asJsonObject
        assertEquals(id to nonce, NearbyPairingProtocol.readStart(start(id,nonce)))
        assertThrows(IllegalArgumentException::class.java) { NearbyPairingProtocol.readStart(start("a",nonce)) }
        assertThrows(IllegalArgumentException::class.java) { NearbyPairingProtocol.readStart(start(id,"f".repeat(63))) }
    }
}
