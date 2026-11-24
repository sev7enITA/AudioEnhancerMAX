package com.audioenhancermax.worker

import android.content.Context
import android.net.nsd.NsdManager
import android.net.nsd.NsdServiceInfo
import android.net.wifi.WifiManager
import android.os.Build
import android.os.Handler
import android.os.Looper

/** Android can resolve only one legacy DNS-SD service at a time. */
@Suppress("DEPRECATION")
internal class NearbyMacDiscovery(context: Context) {
    private val nsd = context.getSystemService(NsdManager::class.java)
    private val wifi = context.applicationContext.getSystemService(WifiManager::class.java)
    private val main = Handler(Looper.getMainLooper())
    private var discovery: NsdManager.DiscoveryListener? = null
    private var resolving: NsdManager.ResolveListener? = null
    private var lock: WifiManager.MulticastLock? = null
    private val queue = LinkedHashMap<String, NsdServiceInfo>()
    private val seen = HashSet<String>()
    private val results = LinkedHashMap<String, NearbyMac>()
    private var publish: ((List<NearbyMac>) -> Unit)? = null

    fun start(update: (List<NearbyMac>) -> Unit, failure: () -> Unit) {
        stop()
        publish = update
        val listener = object : NsdManager.DiscoveryListener {
            override fun onDiscoveryStarted(serviceType: String) = Unit
            override fun onDiscoveryStopped(serviceType: String) = Unit
            override fun onStopDiscoveryFailed(serviceType: String, errorCode: Int) = Unit

            override fun onStartDiscoveryFailed(serviceType: String, errorCode: Int) {
                main.post { if (discovery === this) { stop(); failure() } }
            }

            override fun onServiceFound(service: NsdServiceInfo) {
                main.post {
                    if (discovery !== this || service.serviceType.trimEnd('.') != SERVICE.trimEnd('.')) return@post
                    if (seen.size < 32 && seen.add(service.serviceName)) {
                        queue[service.serviceName] = service
                        resolveNext()
                    }
                }
            }

            override fun onServiceLost(service: NsdServiceInfo) {
                main.post {
                    if (discovery !== this) return@post
                    seen.remove(service.serviceName)
                    queue.remove(service.serviceName)
                    if (results.remove(service.serviceName) != null) publishRecords()
                }
            }
        }
        discovery = listener
        lock = runCatching { wifi?.createMulticastLock("AudioEnhancerMAX nearby").also { it?.acquire() } }.getOrNull()
        try {
            nsd.discoverServices(SERVICE, NsdManager.PROTOCOL_DNS_SD, listener)
        } catch (_: RuntimeException) {
            stop()
            failure()
        }
    }

    fun stop() {
        val listener = discovery
        discovery = null
        if (listener != null) runCatching { nsd.stopServiceDiscovery(listener) }
        if (Build.VERSION.SDK_INT >= 34) {
            resolving?.let { runCatching { nsd.stopServiceResolution(it) } }
        }
        lock?.let { runCatching { it.release() } }
        lock = null
        queue.clear()
        seen.clear()
        results.clear()
        publish = null
    }

    private fun publishRecords() = publish?.invoke(results.values.distinctBy { it.endpoint })

    private fun resolveNext() {
        val activeDiscovery = discovery ?: return
        if (resolving != null) return
        val next = queue.entries.firstOrNull()?.value ?: return
        queue.remove(next.serviceName)
        val listener = object : NsdManager.ResolveListener {
            private fun completed(service: NsdServiceInfo?) {
                main.post {
                    if (resolving !== this) return@post
                    resolving = null
                    if (discovery === activeDiscovery && service != null && next.serviceName in seen && results.size < 16) {
                        NearbyMac.fromRecord(service.serviceName, service.port, service.attributes)?.let {
                            results[next.serviceName] = it
                            publishRecords()
                        }
                    }
                    resolveNext()
                }
            }
            override fun onResolveFailed(service: NsdServiceInfo, errorCode: Int) = completed(null)
            override fun onServiceResolved(service: NsdServiceInfo) = completed(service)
            override fun onResolutionStopped(service: NsdServiceInfo) = completed(null)
        }
        resolving = listener
        try {
            nsd.resolveService(next, listener)
        } catch (_: RuntimeException) {
            resolving = null
            resolveNext()
        }
    }

    companion object {
        const val SERVICE = "_aemax-pair._tcp."
    }
}
