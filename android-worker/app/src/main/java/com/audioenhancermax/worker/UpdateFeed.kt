package com.audioenhancermax.worker

import com.google.gson.JsonObject
import com.google.gson.JsonParser
import java.io.InputStream
import java.io.OutputStream
import java.net.URI
import java.security.KeyFactory
import java.security.MessageDigest
import java.security.PublicKey
import java.security.Signature
import java.security.spec.X509EncodedKeySpec
import java.util.Base64
import java.util.Locale

internal const val CompanionPackageId = "com.audioenhancermax.worker"
internal const val UpdateFeedUrl = "https://www.fabriziodegni.com/AudioEnhancerMAX/updates/companion-v1.json"
internal const val MaxFeedBytes = 32 * 1024
internal const val MaxUpdateBytes = 200L * 1024 * 1024
private const val MaxPayloadBytes = 16 * 1024
private const val MaxFeedLifetime = 365 * 24 * 60 * 60L
private const val IssuerClockSkew = 5 * 60L
private val VersionPattern = Regex("[1-9][0-9]{0,3}\\.[0-9]{1,4}\\.[0-9]{1,4}")
private val DigestPattern = Regex("[A-Fa-f0-9]{64}")
private val GitHubAssetPath = Regex("/github-production-release-asset(?:-[a-f0-9]+)?/1292611395/[a-zA-Z0-9-]{16,80}")
private val SourceForgeMirror = Regex("[a-z0-9-]+\\.dl\\.sourceforge\\.net")

internal class UpdateFailure(message: String) : Exception(message)

internal fun requireUpdate(condition: Boolean, message: String) {
    if (!condition) throw UpdateFailure(message)
}

internal enum class DirectUpdateSource(val label: String) { GITHUB("GitHub"), SOURCEFORGE("SourceForge") }

internal data class AndroidUpdate(
    val version: String,
    val build: Long,
    val packageId: String,
    val filename: String,
    val sha256: String,
    val signerSha256: String,
    val sizeBytes: Long,
    val tag: String,
)

internal data class SignedAndroidFeed(val issuedAt: Long, val expiresAt: Long, val release: AndroidUpdate) {
    fun isCurrent(nowEpochSeconds: Long): Boolean =
        issuedAt > 0 && issuedAt <= nowEpochSeconds + IssuerClockSkew &&
            expiresAt > nowEpochSeconds && expiresAt > issuedAt && expiresAt - issuedAt <= MaxFeedLifetime

    fun follows(acceptedBuild: Long, acceptedIssue: Long): Boolean =
        release.build >= acceptedBuild && issuedAt >= acceptedIssue
}

internal fun readUpdatePublicKey(pem: String): PublicKey {
    requireUpdate(pem.length <= 4096, "The bundled update trust key is unavailable.")
    val lines = pem.trim().lines()
    requireUpdate(lines.firstOrNull() == "-----BEGIN PUBLIC KEY-----" &&
        lines.lastOrNull() == "-----END PUBLIC KEY-----", "The bundled update trust key is unavailable.")
    val encoded = Base64.getDecoder().decode(lines.drop(1).dropLast(1).joinToString("") { it.trim() })
    return KeyFactory.getInstance("EC").generatePublic(X509EncodedKeySpec(encoded))
}

internal fun verifyUpdateFeed(envelope: ByteArray, key: PublicKey, nowEpochSeconds: Long): SignedAndroidFeed {
    requireUpdate(envelope.isNotEmpty() && envelope.size <= MaxFeedBytes, "The update feed exceeds the allowed size.")
    val wrapper = parseObject(envelope)
    val payload = decodeBase64(wrapper.string("payload"), MaxPayloadBytes)
    val signature = decodeBase64(wrapper.string("signature"), 80)
    val verified = runCatching {
        Signature.getInstance("SHA256withECDSA").run {
            initVerify(key)
            update(payload)
            verify(signature)
        }
    }.getOrDefault(false)
    requireUpdate(verified, "The update feed signature could not be verified.")
    val root = parseObject(payload)
    requireUpdate(root.string("schema") == "audioenhancermax.mobile-updates.v1", "The update feed format is unsupported.")
    val release = root.objectField("releases").objectField("android")
    val version = release.string("version")
    val build = release.integer("build")
    val filename = release.string("filename")
    val packageId = release.string("package_id")
    val tag = release.string("tag")
    val size = release.integer("size_bytes")
    val digest = release.string("sha256")
    val signer = release.string("signer_sha256")
    requireUpdate(
        VersionPattern.matches(version) && build in 1..2_100_000_000 &&
            filename == "AudioEnhancerMAX-Companion-v$version-build-$build-Android-QA.apk" &&
            Regex("v${Regex.escape(version)}-mobile-beta\\.[1-9][0-9]{0,2}").matches(tag) &&
            packageId == CompanionPackageId && size in 1..MaxUpdateBytes &&
            DigestPattern.matches(digest) && DigestPattern.matches(signer),
        "The signed Android update details are invalid.",
    )
    val update = AndroidUpdate(version, build, packageId, filename, digest.lowercase(Locale.ROOT),
        signer.lowercase(Locale.ROOT), size, tag)
    val result = SignedAndroidFeed(root.integer("issued_at"), root.integer("expires_at"), update)
    requireUpdate(result.isCurrent(nowEpochSeconds), "The signed update feed is expired or has an invalid date.")
    return result
}

private fun parseObject(body: ByteArray): JsonObject = try {
    JsonParser.parseString(body.decodeToString(throwOnInvalidSequence = true)).asJsonObject
} catch (_: Exception) {
    throw UpdateFailure("The signed update feed format is invalid.")
}

private fun JsonObject.objectField(name: String): JsonObject =
    get(name)?.takeIf { it.isJsonObject }?.asJsonObject ?: throw UpdateFailure("The signed update feed is incomplete.")

private fun JsonObject.string(name: String): String =
    get(name)?.takeIf { it.isJsonPrimitive && it.asJsonPrimitive.isString }?.asString
        ?: throw UpdateFailure("The signed update feed is incomplete.")

private fun JsonObject.integer(name: String): Long {
    val value = get(name)?.takeIf { it.isJsonPrimitive && it.asJsonPrimitive.isNumber }?.asString
    return value?.takeIf { it.all(Char::isDigit) }?.toLongOrNull()
        ?: throw UpdateFailure("The signed update feed contains an invalid number.")
}

private fun decodeBase64(value: String, maxBytes: Int): ByteArray {
    requireUpdate(value.isNotEmpty() && value.length <= (maxBytes + 2) / 3 * 4, "The update feed encoding is invalid.")
    val decoded = try { Base64.getDecoder().decode(value) } catch (_: IllegalArgumentException) {
        throw UpdateFailure("The update feed encoding is invalid.")
    }
    requireUpdate(decoded.isNotEmpty() && decoded.size <= maxBytes, "The update feed encoding is invalid.")
    return decoded
}

internal fun DirectUpdateSource.downloadUri(update: AndroidUpdate): URI = URI(
    when (this) {
        DirectUpdateSource.GITHUB -> "https://github.com${gitHubPath(update)}"
        DirectUpdateSource.SOURCEFORGE -> "https://downloads.sourceforge.net${sourceForgePath(update)}"
    },
)

private fun gitHubPath(update: AndroidUpdate) = "/sev7enITA/AudioEnhancerMAX/releases/download/${update.tag}/${update.filename}"
private fun sourceForgePath(update: AndroidUpdate) = "/project/audioenhancermax/${update.tag}/${update.filename}"

internal fun DirectUpdateSource.allows(uri: URI, update: AndroidUpdate): Boolean {
    if (!uri.scheme.equals("https", ignoreCase = true) || uri.rawUserInfo != null ||
        uri.rawFragment != null || uri.port !in setOf(-1, 443)) return false
    val host = uri.host?.lowercase(Locale.ROOT) ?: return false
    return when (this) {
        DirectUpdateSource.GITHUB -> when (host) {
            "github.com" -> uri.rawPath == gitHubPath(update) && uri.rawQuery == null
            "release-assets.githubusercontent.com", "objects.githubusercontent.com", "github-releases.githubusercontent.com" ->
                GitHubAssetPath.matches(uri.rawPath.orEmpty())
            else -> false
        }
        DirectUpdateSource.SOURCEFORGE -> when {
            host == "sourceforge.net" ->
                uri.rawPath == "/projects/audioenhancermax/files/${update.tag}/${update.filename}/download"
            host == "downloads.sourceforge.net" || SourceForgeMirror.matches(host) -> uri.rawPath == sourceForgePath(update)
            else -> false
        }
    }
}

internal fun copyVerifiedUpdate(
    source: InputStream,
    destination: OutputStream,
    update: AndroidUpdate,
    checkpoint: (Long) -> Unit,
) {
    requireUpdate(update.sizeBytes in 1..MaxUpdateBytes, "The signed package size is outside the allowed range.")
    val digest = MessageDigest.getInstance("SHA-256")
    val buffer = ByteArray(64 * 1024)
    var length = 0L
    while (true) {
        checkpoint(length)
        val count = source.read(buffer)
        if (count < 0) break
        requireUpdate(count > 0 && count <= update.sizeBytes - length, "The package size does not match the signed update.")
        destination.write(buffer, 0, count)
        digest.update(buffer, 0, count)
        length += count
    }
    requireUpdate(length == update.sizeBytes, "The package size does not match the signed update.")
    requireUpdate(digest.digest().hexDigest() == update.sha256, "The package checksum does not match the signed update.")
    checkpoint(length)
}

internal fun ByteArray.hexDigest(): String = joinToString("") { "%02x".format(Locale.ROOT, it) }
