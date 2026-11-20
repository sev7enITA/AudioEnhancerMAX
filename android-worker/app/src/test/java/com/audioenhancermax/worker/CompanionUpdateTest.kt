package com.audioenhancermax.worker

import com.google.gson.JsonObject
import java.io.ByteArrayInputStream
import java.io.ByteArrayOutputStream
import java.io.File
import java.net.URI
import java.security.KeyPair
import java.security.KeyPairGenerator
import java.security.MessageDigest
import java.security.Signature
import java.security.spec.ECGenParameterSpec
import java.time.Instant
import java.util.Base64
import org.junit.Assert.*
import org.junit.Assume.assumeTrue
import org.junit.Test

class CompanionUpdateTest {
    private val clock = 1_795_152_545L
    private val signingKey = KeyPairGenerator.getInstance("EC").run {
        initialize(ECGenParameterSpec("secp256r1"))
        generateKeyPair()
    }

    @Test fun verifiesExactSignedBytesAndRejectsTampering() {
        val payload = payload()
        val good = envelope(payload)
        val update = verifyUpdateFeed(good, signingKey.public, clock)
        assertEquals("4.1.1", update.release.version)
        assertEquals(17L, update.release.build)
        val bad = envelope(payload.replace("4.1.1", "4.1.2"), signed = signature(payload))
        assertThrows(UpdateFailure::class.java) { verifyUpdateFeed(bad, signingKey.public, clock) }
        assertThrows(UpdateFailure::class.java) {
            verifyUpdateFeed(envelope(payload, signed = ByteArray(64)), signingKey.public, clock)
        }
        assertThrows(UpdateFailure::class.java) {
            verifyUpdateFeed(ByteArray(MaxFeedBytes + 1), signingKey.public, clock)
        }
    }

    @Test fun enforcesClockAndPreventsAcceptedFeedRollback() {
        fun feed(body: String, now: Long = clock) = verifyUpdateFeed(envelope(body), signingKey.public, now)
        assertTrue(feed(payload(issued = clock + 300)).isCurrent(clock))
        assertThrows(UpdateFailure::class.java) { feed(payload(issued = clock + 301)) }
        assertThrows(UpdateFailure::class.java) { feed(payload(expires = clock), now = clock) }
        assertThrows(UpdateFailure::class.java) { feed(payload(expires = clock + 366 * 24 * 60 * 60L)) }
        val current = feed(payload(issued = clock - 5))
        assertFalse(current.follows(18, 0))
        assertFalse(current.follows(17, clock))
        assertTrue(current.follows(16, clock - 5))
    }

    @Test fun requiresCanonicalAndroidReleaseEvenWhenSigned() {
        val base = payload()
        val damaged = listOf(
            base.replace("-Android-QA.apk", "/../../anything.apk"),
            base.replace("-mobile-beta.1", "-preview.1"),
            base.replace(CompanionPackageId, "example.unrelated.app"),
            base.replace("\"size_bytes\":12", "\"size_bytes\":209715201"),
            base.replace("\"size_bytes\":12", "\"size_bytes\":12.1"),
        )
        for (input in damaged) {
            assertThrows(UpdateFailure::class.java) { verifyUpdateFeed(envelope(input), signingKey.public, clock) }
        }
    }

    @Test fun restrictsEveryRedirectToTheSelectedRepoAndKnownPath() {
        val update = verifyUpdateFeed(envelope(payload()), signingKey.public, clock).release
        val github = DirectUpdateSource.GITHUB
        val sf = DirectUpdateSource.SOURCEFORGE
        val gh = github.downloadUri(update)
        val forge = sf.downloadUri(update)
        assertTrue(github.allows(gh, update))
        assertTrue(sf.allows(forge, update))
        assertTrue(github.allows(URI("https://release-assets.githubusercontent.com/github-production-release-asset/1292611395/fb8d6fa8-0387-4e93-aa52-4ffd1f59c4e2?token=qa"), update))
        assertTrue(sf.allows(URI("https://netix.dl.sourceforge.net${forge.rawPath}?download=true"), update))
        assertFalse(github.allows(forge, update))
        assertFalse(sf.allows(gh, update))
        val unsafe = listOf(
            "http://github.com${gh.rawPath}",
            "https://github.com:444${gh.rawPath}",
            "https://user@github.com${gh.rawPath}",
            "https://github.com${gh.rawPath}#local",
            "https://github.com.evil.example${gh.rawPath}",
            "https://github.com${gh.rawPath}?host=elsewhere",
            "https://github.com/another-owner/project/releases/download/${update.tag}/${update.filename}",
            "https://release-assets.githubusercontent.com/github-production-release-asset/22222222/fb8d6fa8-0387-4e93-aa52-4ffd1f59c4e2",
            "https://release-assets.githubusercontent.com/anyotherpath",
        )
        unsafe.forEach { assertFalse(it, github.allows(URI(it), update)) }
        assertFalse(sf.allows(URI("https://netix.dl.sourceforge.net.evil.example${forge.rawPath}"), update))
        assertFalse(sf.allows(URI("https://netix.dl.sourceforge.net/project/unknown/${update.filename}"), update))
    }

    @Test fun rejectsWrongApkBuildPackageAndCertificate() {
        val cert = "cd".repeat(32)
        val update = verifyUpdateFeed(envelope(payload()), signingKey.public, clock).release
        val installed = ApkIdentity(CompanionPackageId, "4.1.0", 16, setOf(cert))
        val archive = ApkIdentity(CompanionPackageId, "4.1.1", 17, setOf(cert))
        verifyApkIdentity(archive, installed, update)
        for (invalid in listOf(
            archive.copy(packageId = "example.unrelated"),
            archive.copy(build = 16),
            archive.copy(versionName = "4.1.0"),
            archive.copy(signerSha256 = setOf("ef".repeat(32))),
            archive.copy(signerSha256 = setOf(cert, "ef".repeat(32))),
        )) assertThrows(UpdateFailure::class.java) { verifyApkIdentity(invalid, installed, update) }
        assertThrows(UpdateFailure::class.java) { verifyApkIdentity(archive, installed.copy(build = 17), update) }
    }

    @Test fun streamsExactSizeAndRejectsShortLongAndWrongDigest() {
        val bytes = "verify these bytes".toByteArray()
        val actual = MessageDigest.getInstance("SHA-256").digest(bytes).hexDigest()
        val item = verifyUpdateFeed(envelope(payload()), signingKey.public, clock).release.copy(sizeBytes = bytes.size.toLong(), sha256 = actual)
        val copy = ByteArrayOutputStream()
        copyVerifiedUpdate(ByteArrayInputStream(bytes), copy, item) {}
        assertArrayEquals(bytes, copy.toByteArray())
        val changed = bytes.clone().apply { this[0] = 0 }
        for (bad in listOf(bytes.copyOf(bytes.size - 1), bytes + 0, changed)) {
            assertThrows(UpdateFailure::class.java) {
                copyVerifiedUpdate(ByteArrayInputStream(bad), ByteArrayOutputStream(), item) {}
            }
        }
    }

    @Test fun installerAndStoreBuildChooseOnlyTheCorrespondingUpdateRoute() {
        assertEquals(UpdateChannel.Play, chooseUpdateChannel(true, null, null, null, false))
        assertEquals(UpdateChannel.Play, chooseUpdateChannel(false, "com.android.vending", null, null, false))
        assertEquals(UpdateChannel.Play, chooseUpdateChannel(false, "com.android.packageinstaller", null, "com.android.vending", false))
        assertEquals(UpdateChannel.Direct, chooseUpdateChannel(false, null, "com.android.shell", null, false))
        assertEquals(UpdateChannel.Direct, chooseUpdateChannel(false, "com.google.android.packageinstaller", null, null, false))
        assertEquals(UpdateChannel.Marketplace("com.sec.android.app.samsungapps", "Galaxy Store"),
            chooseUpdateChannel(false, "com.sec.android.app.samsungapps", null, null, false))
        assertEquals(UpdateChannel.Marketplace(null, "Installation marketplace"),
            chooseUpdateChannel(false, null, null, null, true))
    }

    @Test fun acceptsRealBundledTrustKeyAndSignedFixtureWhenSupplied() {
        val fixture = System.getenv("AEMAX_UPDATE_SIGNED_FEED")?.let(::File)
        assumeTrue("Provide the root-generated signed fixture", fixture?.isFile == true)
        val key = File("../../app/resources/mobile/companion-update-public.pem")
        assertTrue(key.isFile)
        val release = verifyUpdateFeed(fixture!!.readBytes(), readUpdatePublicKey(key.readText()), Instant.now().epochSecond).release
        assertEquals(CompanionPackageId, release.packageId)
        assertTrue(release.build >= 16)
        assertTrue(release.sizeBytes > 0)
    }

    private fun signature(payload: String): ByteArray = Signature.getInstance("SHA256withECDSA").run {
        initSign(signingKey.private)
        update(payload.toByteArray(Charsets.UTF_8))
        sign()
    }

    private fun envelope(payload: String, signed: ByteArray = signature(payload)): ByteArray = JsonObject().apply {
        addProperty("payload", Base64.getEncoder().encodeToString(payload.toByteArray(Charsets.UTF_8)))
        addProperty("signature", Base64.getEncoder().encodeToString(signed))
    }.toString().toByteArray(Charsets.UTF_8)

    private fun payload(issued: Long = clock, expires: Long = clock + 60 * 60): String =
        """{"schema":"audioenhancermax.mobile-updates.v1","issued_at":$issued,"expires_at":$expires,
            "releases":{"android":{"version":"4.1.1","build":17,"package_id":"$CompanionPackageId",
            "filename":"AudioEnhancerMAX-Companion-v4.1.1-build-17-Android-QA.apk",
            "sha256":"${"ab".repeat(32)}","signer_sha256":"${"cd".repeat(32)}","size_bytes":12,"tag":"v4.1.1-mobile-beta.1"}}}"""
}
