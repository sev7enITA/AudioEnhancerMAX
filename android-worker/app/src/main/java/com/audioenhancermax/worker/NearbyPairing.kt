package com.audioenhancermax.worker

import com.google.gson.Gson
import com.google.gson.JsonObject
import com.google.gson.JsonParser
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.net.URL
import java.security.SecureRandom
import javax.net.ssl.HostnameVerifier
import javax.net.ssl.HttpsURLConnection

internal data class NearbyMac(val name: String, val host: String, val port: Int, val fingerprint: String) {
    val endpoint: String get() = "https://$host:$port"

    companion object {
        private val address = Regex("[0-9]{1,3}(\\.[0-9]{1,3}){3}")
        private val portNumber = Regex("[1-9][0-9]{0,4}")

        fun fromRecord(name: String, servicePort: Int, attributes: Map<String, ByteArray>): NearbyMac? {
            fun field(key: String) = attributes[key]?.toString(Charsets.UTF_8)
            if (field("v") != "1") return null
            val host = field("host") ?: return null
            val port = field("port")?.takeIf(portNumber::matches)?.toIntOrNull() ?: return null
            if (port != servicePort) return null
            val fingerprint = field("fp") ?: return null
            return fromEndpoint(name, host, port, fingerprint)
        }

        fun fromEndpoint(name: String, host: String, port: Int, fingerprint: String): NearbyMac? {
            if (!address.matches(host) || port !in 1..65535 ||
                !NearbyPairingProtocol.hex64.matches(fingerprint)) return null
            val octets = host.split('.').map { it.toInt() }
            if (octets.any { it > 255 } || octets.joinToString(".") != host) return null
            val first = octets[0]
            val second = octets[1]
            if (first != 10 && !(first == 172 && second in 16..31) && !(first == 192 && second == 168)) return null
            val safeName = name.filter { !it.isISOControl() && Character.getType(it) != Character.FORMAT.toInt() }
                .trim().take(80).ifEmpty { "AudioEnhancerMAX Mac" }
            return NearbyMac(safeName, host, port, fingerprint)
        }
    }
}

internal object NearbyPairingProtocol {
    val hex64 = Regex("[0-9a-f]{64}")
    private val requestID = Regex("[0-9a-f]{32}")

    fun nonce(): String = ByteArray(32).also { SecureRandom().nextBytes(it) }.joinToString("") { "%02x".format(it) }

    fun commitment(nonce: String): String {
        require(hex64.matches(nonce))
        return sha256(nonce.toByteArray(Charsets.UTF_8))
    }

    fun comparisonCode(fingerprint: String, nonce: String, serverNonce: String): String {
        require(listOf(fingerprint, nonce, serverNonce).all(hex64::matches))
        val input = "AEMAX-PAIR-1|$fingerprint|$nonce|$serverNonce".toByteArray(Charsets.UTF_8)
        return (sha256(input).take(8).toLong(16) % 100_000_000).toString().padStart(8, '0')
    }

    fun readStart(response: JsonObject): Pair<String, String> {
        val request = response.text("request_id")
        val serverNonce = response.text("server_nonce")
        require(requestID.matches(request) && hex64.matches(serverNonce)) { "Invalid Mac pairing response" }
        return request to serverNonce
    }

    fun approvedPairing(mac: NearbyMac, response: JsonObject): Pairing {
        val payload = response.getAsJsonObject("pairing") ?: error("Missing Mac pairing")
        require(payload.get("protocol")?.toString() == "1" && payload.text("endpoint") == mac.endpoint &&
            payload.text("fingerprint") == mac.fingerprint) {
            "The approved Mac identity no longer matches discovery"
        }
        return Pairing.parse(payload.toString())
    }

    fun status(response: JsonObject): String = response.text("status")

    private fun JsonObject.text(key: String): String =
        get(key)?.takeIf { it.isJsonPrimitive && it.asJsonPrimitive.isString }?.asString
            ?: throw IllegalArgumentException("Invalid Mac pairing response")
}

internal enum class PairingStep(val path: String) {
    START("/v1/pairing/start"), REVEAL("/v1/pairing/reveal"), FINISH("/v1/pairing/finish")
}

internal class PairingExpired : IllegalStateException("The Mac pairing request expired")

internal class NearbyPairingClient(private val mac: NearbyMac, private val device: String) {
    private val socketFactory = pinnedTls(mac.fingerprint).socketFactory
    private val gson = Gson()

    suspend fun post(step: PairingStep, values: Map<String, String>): JsonObject = withContext(Dispatchers.IO) {
        val connection = URL(mac.endpoint + step.path).openConnection() as HttpsURLConnection
        connection.sslSocketFactory = socketFactory
        connection.hostnameVerifier = HostnameVerifier { host, _ -> host == mac.host }
        connection.instanceFollowRedirects = false
        connection.connectTimeout = 4000
        connection.readTimeout = 4000
        connection.requestMethod = "POST"
        connection.setRequestProperty("X-Device-ID", device)
        connection.setRequestProperty("X-Device-Name", companionDeviceName())
        connection.setRequestProperty("Content-Type", "application/json")
        connection.doOutput = true
        val body = gson.toJson(values).toByteArray(Charsets.UTF_8)
        connection.setFixedLengthStreamingMode(body.size)
        try {
            connection.outputStream.use { it.write(body) }
            val status = connection.responseCode
            if (status == 410) throw PairingExpired()
            check(status == 200) { "The Mac pairing window is unavailable. Open it again and retry." }
            val response = connection.inputStream.use { it.readBytesBounded(8192) }
            JsonParser.parseString(response.toString(Charsets.UTF_8)).asJsonObject
        } finally {
            connection.disconnect()
        }
    }
}
