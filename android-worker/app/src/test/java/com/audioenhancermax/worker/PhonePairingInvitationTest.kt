package com.audioenhancermax.worker

import java.net.InetAddress
import org.junit.Assert.*
import org.junit.Test

class PhonePairingInvitationTest {
    private val invitationId = "a".repeat(32)
    private val localhost = InetAddress.getByAddress(byteArrayOf(192.toByte(), 168.toByte(), 1, 30))
    private val fingerprint = "f".repeat(64)

    private fun message(id: String = invitationId, host: String = "192.168.1.30",
                        port: String = "20482", pin: String = fingerprint): String =
        """{"v":1,"id":"$id","host":"$host","port":$port,"fp":"$pin","name":"QA Mac"}"""

    private fun decode(message: String, sender: InetAddress = localhost): NearbyMac? =
        message.toByteArray().let { PhonePairingInvitation.decode(invitationId, it, it.size, sender) }

    @Test fun acceptsMatchingPrivateOriginAndEndpoint() {
        val mac = requireNotNull(decode(message()))
        assertEquals("https://192.168.1.30:20482", mac.endpoint)
        assertEquals(fingerprint, mac.fingerprint)
        assertEquals("QA Mac", mac.name)
    }

    @Test fun rejectsWrongWindowMismatchedSenderAndNonPrivateOrigin() {
        assertNull(decode(message(id = "b".repeat(32))))
        assertNull(decode(message(host = "192.168.1.31")))
        assertNull(decode(message(host = "192.168.001.030")))
        assertNull(decode(message(host = "8.8.8.8"), InetAddress.getByAddress(byteArrayOf(8,8,8,8))))
        assertNull(decode(message(), InetAddress.getByAddress(ByteArray(16))))
    }

    @Test fun rejectsInvalidSchemaSecretFieldsPinsAndOversizedDatagrams() {
        assertNull(decode(message(port = "0")))
        assertNull(decode(message(port = "65536")))
        assertNull(decode(message(port = "\"20482\"")))
        assertNull(decode(message(pin = "F".repeat(64))))
        assertNull(decode(message().replace("\"v\":1", "\"v\":\"1\"")))
        assertNull(decode(message().dropLast(1) + ""","token":"never in an invitation"}"""))
        assertNull(decode(message().replace("QA Mac", "x".repeat(PhonePairingInvitation.MAX_BYTES))))
    }
}
