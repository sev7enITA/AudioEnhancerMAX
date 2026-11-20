package com.audioenhancermax.worker

import android.content.Context
import android.content.Intent
import android.content.pm.PackageInfo
import android.content.pm.PackageInstaller
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.provider.DocumentsContract
import androidx.core.content.pm.PackageInfoCompat
import java.io.ByteArrayOutputStream
import java.io.File
import java.io.OutputStream
import java.net.HttpURLConnection
import java.net.URI
import java.security.MessageDigest
import java.time.Instant
import javax.net.ssl.HttpsURLConnection
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.runInterruptible
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeout

internal const val ApkMime = "application/vnd.android.package-archive"
private const val PlayInstaller = "com.android.vending"
private const val MiB = 1024L * 1024
private const val ScratchAge = 24 * 60 * 60 * 1000L
private val KnownStores = mapOf(
    "com.sec.android.app.samsungapps" to "Galaxy Store",
    "com.amazon.venezia" to "Amazon Appstore",
    "com.huawei.appmarket" to "AppGallery",
    "org.fdroid.fdroid" to "F-Droid",
    "org.fdroid.basic" to "F-Droid",
    "com.xiaomi.market" to "GetApps",
    "com.oppo.market" to "App Market",
)
private val PackagePattern = Regex("[a-zA-Z0-9_]+(?:\\.[a-zA-Z0-9_]+)+")
private val RedirectCodes = setOf(301, 302, 303, 307, 308)

internal sealed interface UpdateChannel {
    data object Direct : UpdateChannel
    data object Play : UpdateChannel
    data class Marketplace(val installer: String?, val label: String) : UpdateChannel
    data object Unavailable : UpdateChannel
}

internal fun chooseUpdateChannel(
    playOnlyBuild: Boolean, installer: String?, initiator: String?, updateOwner: String?, sourceIsStore: Boolean,
): UpdateChannel {
    val sources = listOfNotNull(updateOwner, installer, initiator)
    if (playOnlyBuild || PlayInstaller in sources) return UpdateChannel.Play
    val known = sources.firstOrNull(KnownStores::containsKey)
    if (known != null) return UpdateChannel.Marketplace(known, KnownStores.getValue(known))
    if (sourceIsStore || updateOwner != null) {
        val source = (updateOwner ?: installer ?: initiator)?.takeIf(PackagePattern::matches)
        return UpdateChannel.Marketplace(source, "Installation marketplace")
    }
    return UpdateChannel.Direct
}

@Suppress("DEPRECATION")
internal fun updateChannel(context: Context): UpdateChannel {
    if (BuildConfig.PLAY_STORE_ONLY) return UpdateChannel.Play
    return try {
        val manager = context.packageManager
        if (Build.VERSION.SDK_INT >= 30) {
            val source = manager.getInstallSourceInfo(context.packageName)
            chooseUpdateChannel(false, source.installingPackageName, source.initiatingPackageName,
                if (Build.VERSION.SDK_INT >= 34) source.updateOwnerPackageName else null,
                Build.VERSION.SDK_INT >= 33 && source.packageSource == PackageInstaller.PACKAGE_SOURCE_STORE)
        } else chooseUpdateChannel(false, manager.getInstallerPackageName(context.packageName), null, null, false)
    } catch (_: Exception) {
        UpdateChannel.Unavailable
    }
}

internal fun openUpdateMarketplace(context: Context, channel: UpdateChannel): Boolean {
    val encoded = Uri.encode(context.packageName)
    fun open(uri: String, target: String? = null) = runCatching {
        val intent = Intent(Intent.ACTION_VIEW, Uri.parse(uri)).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        if (target != null) intent.setPackage(target)
        context.startActivity(intent)
    }.isSuccess
    return when (channel) {
        UpdateChannel.Play -> open("market://details?id=$encoded", PlayInstaller) ||
            open("https://play.google.com/store/apps/details?id=$encoded")
        is UpdateChannel.Marketplace -> channel.installer?.let {
            open("market://details?id=$encoded", it) || runCatching {
                context.startActivity(Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER)
                    .setPackage(it).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
            }.isSuccess
        } ?: false
        else -> false
    }
}

internal data class ApkIdentity(val packageId: String, val versionName: String?, val build: Long, val signerSha256: Set<String>)

@Suppress("DEPRECATION")
private fun signatureFlags(): Int =
    if (Build.VERSION.SDK_INT >= 28) PackageManager.GET_SIGNING_CERTIFICATES else PackageManager.GET_SIGNATURES

@Suppress("DEPRECATION")
private fun packageIdentity(info: PackageInfo): ApkIdentity {
    val signatures = if (Build.VERSION.SDK_INT >= 28) info.signingInfo?.apkContentsSigners else info.signatures
    val digest = MessageDigest.getInstance("SHA-256")
    val signers = signatures.orEmpty().map { digest.digest(it.toByteArray()).hexDigest() }.toSet()
    return ApkIdentity(info.packageName, info.versionName, PackageInfoCompat.getLongVersionCode(info), signers)
}

internal fun installedApkIdentity(context: Context): ApkIdentity =
    packageIdentity(context.packageManager.getPackageInfo(context.packageName, signatureFlags()))

internal fun verifyApkIdentity(archive: ApkIdentity, installed: ApkIdentity, release: AndroidUpdate) {
    requireUpdate(archive.packageId == CompanionPackageId && archive.packageId == installed.packageId &&
        archive.packageId == release.packageId, "The downloaded file belongs to a different app.")
    requireUpdate(archive.build == release.build && archive.build > installed.build &&
        archive.versionName == release.version, "The downloaded version or build does not match the signed update.")
    val expected = setOf(release.signerSha256)
    requireUpdate(installed.signerSha256 == expected && archive.signerSha256 == expected,
        "The downloaded package does not match this app’s signing certificate.")
}

internal fun verifyUpdateArchive(context: Context, file: File, installed: ApkIdentity, release: AndroidUpdate) {
    val archive = context.packageManager.getPackageArchiveInfo(file.absolutePath, signatureFlags())
        ?: throw UpdateFailure("Android could not validate the downloaded APK.")
    verifyApkIdentity(packageIdentity(archive), installed, release)
}

internal data class VerifiedUpdate(val file: File, val feed: SignedAndroidFeed, val source: DirectUpdateSource)

internal class CompanionUpdateClient(private val context: Context) {
    private fun requireDirect() = requireUpdate(updateChannel(context) == UpdateChannel.Direct,
        "Updates are managed by this installation’s marketplace.")

    suspend fun check(): SignedAndroidFeed = withTimeout(35_000) {
        withContext(Dispatchers.IO) {
            requireDirect()
            val operation = currentCoroutineContext()
            val key = context.assets.open("companion-update-public.pem").bufferedReader().use { readUpdatePublicKey(it.readText()) }
            val uri = URI(UpdateFeedUrl)
            val bytes = httpsUpdateGet(uri, { it == uri }, operation::ensureActive) { connection ->
                val announced = connection.getHeaderFieldLong("Content-Length", -1)
                requireUpdate(announced <= MaxFeedBytes, "The update feed exceeds the allowed size.")
                connection.inputStream.use { input ->
                    val bytes = ByteArrayOutputStream()
                    val buffer = ByteArray(8192)
                    while (true) {
                        operation.ensureActive()
                        val count = input.read(buffer)
                        if (count < 0) break
                        requireUpdate(count > 0 && count <= MaxFeedBytes - bytes.size(), "The update feed exceeds the allowed size.")
                        bytes.write(buffer, 0, count)
                    }
                    bytes.toByteArray()
                }
            }
            verifyUpdateFeed(bytes, key, Instant.now().epochSecond)
        }
    }

    suspend fun download(feed: SignedAndroidFeed, source: DirectUpdateSource, progress: (Long) -> Unit): VerifiedUpdate {
        var verifiedFile: File? = null
        try {
            return withTimeout(300_000) { withContext(Dispatchers.IO) {
                requireDirect()
                requireUpdate(feed.isCurrent(Instant.now().epochSecond), "The signed update feed has expired. Check again.")
                val release = feed.release
                val installed = installedApkIdentity(context)
                requireUpdate(release.build > installed.build, "The listed build is already installed or older.")
                requireUpdate(installed.signerSha256 == setOf(release.signerSha256),
                    "This update is signed for a different installation.")
                val dir = File(context.cacheDir, "companion-updates").apply { mkdirs() }
                val cutoff = System.currentTimeMillis() - ScratchAge
                dir.listFiles()?.asSequence()?.filter {
                    it.name.startsWith("update-") && it.extension == "apk" && it.lastModified() in 1 until cutoff
                }?.take(12)?.forEach { it.delete() }
                requireUpdate(dir.usableSpace >= release.sizeBytes + 16 * MiB, "Free some device storage before downloading.")
                val temp = File.createTempFile("update-", ".apk", dir)
                var keep = false
                try {
                    val operation = currentCoroutineContext()
                    httpsUpdateGet(source.downloadUri(release), { source.allows(it, release) }, operation::ensureActive) { connection ->
                        val announced = connection.getHeaderFieldLong("Content-Length", -1)
                        requireUpdate(announced < 0 || announced == release.sizeBytes,
                            "The server’s package size does not match the signed update.")
                        connection.inputStream.use { remote ->
                            temp.outputStream().use { local ->
                                copyVerifiedUpdate(remote, local, release) {
                                    operation.ensureActive()
                                    progress(it)
                                }
                            }
                        }
                    }
                    verifyUpdateArchive(context, temp, installed, release)
                    requireUpdate(feed.isCurrent(Instant.now().epochSecond), "The signed update feed has expired. Check again.")
                    operation.ensureActive()
                    verifiedFile = temp
                    keep = true
                    VerifiedUpdate(temp, feed, source)
                } finally {
                    if (!keep) temp.delete()
                }
            } }
        } catch (failure: Throwable) {
            verifiedFile?.delete()
            throw failure
        }
    }

    suspend fun save(verified: VerifiedUpdate, destination: Uri) = withTimeout(180_000) {
        withContext(Dispatchers.IO) {
            requireDirect()
            requireUpdate(destination.scheme == "content" && DocumentsContract.isDocumentUri(context, destination),
                "Choose a destination in Android Files.")
            val release = verified.feed.release
            requireUpdate(verified.feed.isCurrent(Instant.now().epochSecond), "The signed update feed has expired. Check again.")
            val operation = currentCoroutineContext()
            var written = false
            var verifiedOutput = false
            try {
                runInterruptible {
                    val local = verified.file
                    val resolver = context.contentResolver
                    written = true
                    val output = resolver.openOutputStream(destination, "wt")
                        ?: throw UpdateFailure("The selected destination is unavailable.")
                    output.use { target ->
                        local.inputStream().use { source ->
                            copyVerifiedUpdate(source, target, release) { operation.ensureActive() }
                        }
                    }
                    val input = resolver.openInputStream(destination)
                        ?: throw UpdateFailure("The provider could not confirm the saved file.")
                    input.use { saved ->
                        copyVerifiedUpdate(saved, DiscardOutput, release) { operation.ensureActive() }
                    }
                }
                operation.ensureActive()
                verifiedOutput = true
            } finally {
                if (written && !verifiedOutput) {
                    runCatching { DocumentsContract.deleteDocument(context.contentResolver, destination) }
                }
            }
        }
    }
}

private object DiscardOutput : OutputStream() {
    override fun write(value: Int) = Unit
    override fun write(bytes: ByteArray, offset: Int, length: Int) = Unit
}

private fun <T> httpsUpdateGet(
    start: URI, allowed: (URI) -> Boolean, checkpoint: () -> Unit, read: (HttpsURLConnection) -> T,
): T {
    var uri = start
    for (hop in 0..5) {
        checkpoint()
        requireUpdate(allowed(uri), "The update server redirected outside the chosen source.")
        val connection = uri.toURL().openConnection() as HttpsURLConnection
        try {
            connection.instanceFollowRedirects = false
            connection.connectTimeout = 9000
            connection.readTimeout = 12000
            connection.useCaches = false
            connection.requestMethod = "GET"
            connection.setRequestProperty("Accept-Encoding", "identity")
            val response = connection.responseCode
            if (response in RedirectCodes) {
                val location = connection.getHeaderField("Location")
                requireUpdate(hop < 5 && location != null && location.length <= 4096, "The update server returned an invalid redirect.")
                uri = try { uri.resolve(location!!) } catch (_: IllegalArgumentException) {
                    throw UpdateFailure("The update server returned an invalid redirect.")
                }
                continue
            }
            requireUpdate(response == HttpURLConnection.HTTP_OK, "The selected update source is unavailable.")
            val encoding = connection.contentEncoding
            requireUpdate(encoding == null || encoding.equals("identity", ignoreCase = true),
                "The update server returned an unsupported encoding.")
            return read(connection)
        } finally {
            connection.disconnect()
        }
    }
    throw UpdateFailure("The update server returned too many redirects.")
}
