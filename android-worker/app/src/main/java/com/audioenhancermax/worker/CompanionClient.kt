package com.audioenhancermax.worker

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import com.google.gson.Gson
import com.google.gson.JsonParser
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.ByteArrayOutputStream
import java.net.URL
import java.security.KeyStore
import java.security.MessageDigest
import java.security.cert.X509Certificate
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec
import javax.net.ssl.*

fun sha256(data:ByteArray):String = MessageDigest.getInstance("SHA-256").digest(data).joinToString("") { "%02x".format(it) }

internal fun pinnedTls(fingerprint: String): SSLContext = SSLContext.getInstance("TLS").apply {
    init(null,arrayOf<TrustManager>(object:X509TrustManager {
        override fun getAcceptedIssuers()=emptyArray<X509Certificate>()
        override fun checkClientTrusted(chain:Array<X509Certificate>?,authType:String?) {
            throw java.security.cert.CertificateException("Client trust not supported")
        }
        override fun checkServerTrusted(chain:Array<X509Certificate>?,authType:String?) {
            if (chain.isNullOrEmpty() || sha256(chain[0].encoded)!=fingerprint) {
                throw java.security.cert.CertificateException("Mac identity changed. Pair again.")
            }
        }
    }),null)
}

internal fun companionDeviceName() = ("Android " + android.os.Build.MODEL).filter{it.code in 32..126}.take(80)

data class Pairing(val protocol:Int,val endpoint:String,val fingerprint:String,val token:String) {
    companion object {
        fun parse(text:String):Pairing {
            require(text.length<4096) { "Pairing code too large" }
            val obj=JsonParser.parseString(text).asJsonObject
            val p=Pairing(obj["protocol"].asInt,obj["endpoint"].asString.trimEnd('/'),obj["fingerprint"].asString,obj["token"].asString)
            val u=URL(p.endpoint)
            require(p.protocol==1 && u.protocol=="https" && u.host.isNotBlank() && u.userInfo==null && u.query==null && u.ref==null && u.path.isEmpty() && p.fingerprint.matches(Regex("[a-f0-9]{64}")) && p.token.matches(Regex("[a-zA-Z0-9_-]{32,128}"))) { "Use the complete pairing code from this Mac’s Settings" }
            return p
        }
    }
}
class SecurePairing(context:Context) {
    private val prefs=context.getSharedPreferences("secure_pairing",Context.MODE_PRIVATE)
    private fun key():SecretKey {
        val store=KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        (store.getKey("aemax-pairing",null) as? SecretKey)?.let{return it}
        return KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES,"AndroidKeyStore").apply {
            init(KeyGenParameterSpec.Builder("aemax-pairing",KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT).setBlockModes(KeyProperties.BLOCK_MODE_GCM).setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE).build())
        }.generateKey()
    }
    fun save(pairing:Pairing) {
        val cipher=Cipher.getInstance("AES/GCM/NoPadding");cipher.init(Cipher.ENCRYPT_MODE,key())
        val bytes=cipher.iv+cipher.doFinal(Gson().toJson(pairing).toByteArray())
        check(prefs.edit().putString("value",Base64.encodeToString(bytes,Base64.NO_WRAP)).commit()) { "Could not store pairing" }
    }
    fun load():Pairing? = runCatching {
        val bytes=Base64.decode(prefs.getString("value",null) ?: return null,Base64.NO_WRAP)
        require(bytes.size>28)
        val cipher=Cipher.getInstance("AES/GCM/NoPadding");cipher.init(Cipher.DECRYPT_MODE,key(),GCMParameterSpec(128,bytes.copyOfRange(0,12)))
        Pairing.parse(String(cipher.doFinal(bytes.copyOfRange(12,bytes.size))))
    }.getOrNull()
    fun clear(){prefs.edit().clear().apply()}
}
data class ApiResponse(val bytes:ByteArray,val taskID:String?=null,val filter:String?=null) {
    fun json()=JsonParser.parseString(String(bytes)).asJsonObject
}
class CompanionClient(val pairing:Pairing,private val device:String,private val assessment:(()->String)?=null) {
    private val ssl=pinnedTls(pairing.fingerprint)
    suspend fun request(path:String,method:String="GET",body:ByteArray?=null,extension:String?=null):ApiResponse=withContext(Dispatchers.IO) {
        require(path.startsWith("/v1/"))
        val connection=URL(pairing.endpoint+path).openConnection() as HttpsURLConnection
        connection.sslSocketFactory=ssl.socketFactory
        connection.hostnameVerifier=HostnameVerifier { host,_ -> host==URL(pairing.endpoint).host }
        connection.instanceFollowRedirects=false;connection.connectTimeout=10000;connection.readTimeout=30000
        connection.requestMethod=method;connection.setRequestProperty("Authorization","Bearer ${pairing.token}")
        connection.setRequestProperty("X-Device-Name",companionDeviceName())
        assessment?.let{connection.setRequestProperty("X-Device-Assessment",it())}
        connection.setRequestProperty("X-Device-Cores",Runtime.getRuntime().availableProcessors().toString())
        connection.setRequestProperty("X-Device-ID",device);connection.setRequestProperty("Content-Type","application/json")
        if(extension!=null){connection.setRequestProperty("X-Audio-Extension",extension);connection.setRequestProperty("Content-Type","application/octet-stream")}
        try {
            if (method=="POST") {connection.doOutput=true;val data=body ?: byteArrayOf();connection.setFixedLengthStreamingMode(data.size);connection.outputStream.use { it.write(data) }}
            val code=connection.responseCode
            val output=ByteArrayOutputStream()
            val limit=if(code==200) 32*1024*1024 else 65536
            (if(code==200)connection.inputStream else connection.errorStream)?.use { stream ->
                val buffer=ByteArray(8192)
                while(true){val n=stream.read(buffer);if(n<0)break;require(output.size()+n<=limit){"Mac response too large"};output.write(buffer,0,n)}
            }
            val bytes=output.toByteArray()
            if(code!=200) throw IllegalStateException(runCatching {JsonParser.parseString(String(bytes)).asJsonObject["error"].asString}.getOrDefault("Mac returned HTTP $code"))
            ApiResponse(bytes,connection.getHeaderField("X-Task-ID"),connection.getHeaderField("X-Filter"))
        } finally {connection.disconnect()}
    }
}
