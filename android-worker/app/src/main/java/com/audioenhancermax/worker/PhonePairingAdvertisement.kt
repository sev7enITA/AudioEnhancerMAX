package com.audioenhancermax.worker

import android.content.Context
import android.net.nsd.NsdManager
import android.net.nsd.NsdServiceInfo
import com.google.gson.JsonParser
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.delay
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.isActive
import kotlinx.coroutines.withContext
import java.io.Closeable
import java.net.DatagramPacket
import java.net.DatagramSocket
import java.net.Inet4Address
import java.net.InetAddress
import java.net.InetSocketAddress
import java.net.SocketTimeoutException
import java.util.UUID

internal object PhonePairingInvitation {
    const val MAX_BYTES = 1024
    private val identifier = Regex("[0-9a-f]{32}")
    private val portText = Regex("[1-9][0-9]{0,4}")
    private val fields = setOf("v", "id", "host", "port", "fp", "name")

    fun decode(id: String, data: ByteArray, size: Int, sender: InetAddress?): NearbyMac? {
        if (!identifier.matches(id) || size !in 1..MAX_BYTES || size > data.size || sender !is Inet4Address) return null
        val json = runCatching { JsonParser.parseString(String(data, 0, size, Charsets.UTF_8)).asJsonObject }
            .getOrNull() ?: return null
        if (json.keySet() != fields) return null
        fun text(key: String): String? = json.get(key)
            ?.takeIf { it.isJsonPrimitive && it.asJsonPrimitive.isString }?.asString
        if (json.get("v")?.toString() != "1" || text("id") != id) return null
        val host = text("host") ?: return null
        if (sender.hostAddress != host) return null
        val port = json.get("port")?.toString()?.takeIf(portText::matches)?.toIntOrNull() ?: return null
        val fingerprint = text("fp") ?: return null
        val name = text("name") ?: return null
        return NearbyMac.fromEndpoint(name, host, port, fingerprint)
    }
}

internal class PhonePairingAdvertisement(context: Context) : Closeable {
    private val nsd = context.getSystemService(NsdManager::class.java)
    private val id = UUID.randomUUID().toString().replace("-", "")
    private val socketLock = Any()
    private var socket: DatagramSocket? = null
    private var closed = false
    private var listener: NsdManager.RegistrationListener? = null

    suspend fun listen(ready: () -> Unit, invitation: (NearbyMac) -> Unit) {
        val active = withContext(Dispatchers.IO) { openSocket() }
        val registered = CompletableDeferred<Unit>()
        val registration = object : NsdManager.RegistrationListener {
            override fun onServiceRegistered(serviceInfo: NsdServiceInfo) {
                if (synchronized(socketLock) { closed }) {
                    runCatching { nsd.unregisterService(this) }
                } else {
                    registered.complete(Unit)
                }
            }
            override fun onRegistrationFailed(serviceInfo: NsdServiceInfo, errorCode: Int) {
                registered.completeExceptionally(IllegalStateException("Phone service registration failed"))
            }
            override fun onServiceUnregistered(serviceInfo: NsdServiceInfo) = Unit
            override fun onUnregistrationFailed(serviceInfo: NsdServiceInfo, errorCode: Int) = Unit
        }
        val service = NsdServiceInfo().apply {
            serviceName = companionDeviceName().ifEmpty { "Android companion" }.take(55)
            serviceType = SERVICE
            port = active.localPort
            setAttribute("v", "1")
            setAttribute("id", id)
        }
        listener = registration
        nsd.registerService(service, NsdManager.PROTOCOL_DNS_SD, registration)
        registered.await()
        ready()
        val packet = DatagramPacket(ByteArray(PhonePairingInvitation.MAX_BYTES + 1), PhonePairingInvitation.MAX_BYTES + 1)
        while (currentCoroutineContext().isActive) {
            val mac = readInvitation(active, packet)
            if (mac != null) invitation(mac)
            delay(if (mac == null) 25 else 80)
        }
    }

    private fun openSocket(): DatagramSocket {
        val next = DatagramSocket(null)
        synchronized(socketLock) {
            if (closed) { next.close(); throw IllegalStateException("Phone service already ended") }
            socket = next
        }
        next.bind(InetSocketAddress("0.0.0.0", 0))
        next.soTimeout = 500
        next.receiveBufferSize = 16 * 1024
        return next
    }

    private suspend fun readInvitation(socket: DatagramSocket, packet: DatagramPacket): NearbyMac? =
        withContext(Dispatchers.IO) {
            repeat(16) {
                ensureActive()
                packet.length = packet.data.size
                try { socket.receive(packet) }
                catch (_: SocketTimeoutException) { return@withContext null }
                PhonePairingInvitation.decode(id, packet.data, packet.length, packet.address)?.let { return@withContext it }
            }
            null
        }

    override fun close() {
        synchronized(socketLock) {
            closed = true
            socket?.close()
            socket = null
        }
        listener?.let { runCatching { nsd.unregisterService(it) } }
        listener = null
    }

    companion object {
        const val SERVICE = "_aemax-phone._udp."
    }
}
