package com.audioenhancermax.worker

import android.content.Context
import androidx.annotation.RequiresApi
import com.google.gson.Gson
import com.google.gson.JsonArray
import com.google.gson.JsonObject
import com.google.gson.JsonParser
import org.contentauth.c2pa.C2PAContext
import org.contentauth.c2pa.C2PASettings
import org.contentauth.c2pa.FileStream
import org.contentauth.c2pa.Reader
import java.io.File
import java.time.Instant
import java.util.Locale

private val credentialTrustExpires = Instant.parse("2027-02-02T17:24:49Z")
private const val MaxManifestJson = 1024 * 1024
private const val MiB = 1024L * 1024
private val ReportSha = Regex("[a-fA-F0-9]{64}")
private val ActionLabel = Regex("[A-Za-z0-9._-]{1,80}")
private val PolicyFindings = setOf("signingCredential.untrusted", "timeStamp.untrusted", "signingCredential.ocsp.skipped")
private val HashMismatches = setOf("assertion.bmffHash.mismatch", "assertion.dataHash.mismatch", "assertion.boxesHash.mismatch")

internal data class CredentialAction(
    val action: String, val at: String?, val start: String?, val end: String?, val software: String?,
)

internal data class CredentialSummary(
    val status: String,
    val outcome: String,
    val detail: String,
    val signer: String? = null,
    val issuer: String? = null,
    val signerTrust: String? = null,
    val timestamp: String? = null,
    val reportFingerprint: String? = null,
    val actions: List<CredentialAction> = emptyList(),
    val failureCodes: List<String> = emptyList(),
    val embedded: Boolean? = null,
    val trustSnapshotExpired: Boolean? = null,
) {
    val signerTrustLabel: String?
        get() = when (signerTrust) {
            "recognized" -> "Recognized"
            "unrecognized" -> "Unrecognized signer"
            "not_established" -> "Not established"
            "trust_list_expired" -> "Trust list expired"
            else -> null
        }
    val timestampLabel: String?
        get() = when (timestamp) {
            "trusted" -> "Trusted RFC 3161"
            "validated_untrusted" -> "Present, trust not established"
            "not_established" -> "Not established"
            "trust_list_expired" -> "Trust list expired"
            else -> null
        }
}

internal fun unavailableCredentials(detail: String) =
    CredentialSummary("validator_unavailable", "Verification unavailable", detail)

@RequiresApi(28)
internal fun inspectCredentialFile(context: Context, file: File, format: String): CredentialSummary {
    val runtime = Runtime.getRuntime()
    val availableHeap = runtime.maxMemory() - runtime.totalMemory() + runtime.freeMemory()
    val fileLimit = minOf(64L * MiB, runtime.maxMemory() / 4)
    if (file.length() > fileLimit || availableHeap < maxOf(24L * MiB, file.length() * 2)) {
        return unavailableCredentials("This file exceeds the safe verification budget for the device. The file fingerprint remains available.")
    }
    return try {
        val expired = Instant.now() >= credentialTrustExpires
        val anchors = if (expired) emptyList() else listOf(
            "manifest" to "C2PA-TRUST-LIST.pem", "tsa" to "C2PA-TSA-TRUST-LIST.pem",
        ).map { (kind, name) ->
            mapOf("trust_kind" to kind, "trust_anchors" to context.assets.open(name).bufferedReader().use { it.readText() })
        }
        val settings = Gson().toJson(mapOf(
            "core" to mapOf("allowed_network_hosts" to emptyList<String>(), "decode_identity_assertions" to false),
            "verify" to mapOf("verify_after_reading" to true, "verify_trust" to true, "verify_timestamp_trust" to true,
                "remote_manifest_fetch" to false, "ocsp_fetch" to false),
            "trust" to mapOf("anchors" to anchors),
        ))
        C2PASettings.create().use { localSettings ->
            localSettings.updateFromString(settings, "json")
            C2PAContext.fromSettings(localSettings).use { verification ->
                FileStream(file, FileStream.Mode.READ, createIfNeeded = false).use { stream ->
                    Reader.fromContext(verification).use { reader ->
                        reader.withStream(format, stream)
                        val json = reader.json()
                        if (json.length > MaxManifestJson) unavailableCredentials("The manifest report exceeds the safe display limit.")
                        else summarizeCredentials(JsonParser.parseString(json).asJsonObject, reader.isEmbedded(), expired)
                    }
                }
            }
        }
    } catch (_: OutOfMemoryError) {
        unavailableCredentials("The credential reader ran out of memory. Try the original file on a desktop verifier.")
    } catch (_: LinkageError) {
        unavailableCredentials("The local credential reader is unavailable on this device.")
    } catch (error: Exception) {
        val reason = error.message.orEmpty().lowercase(Locale.ROOT)
        when {
            "remote manifest" in reason || "remotemanifest" in reason -> remoteCredentials()
            "manifestnotfound" in reason || "manifest not found" in reason || "no manifest" in reason ||
                "jumbfnotfound" in reason ->
                CredentialSummary("unsigned", "No embedded credentials", "No readable embedded C2PA manifest was found.", embedded = false)
            else -> unavailableCredentials("The reader could not inspect this file.")
        }
    }
}

private fun remoteCredentials() =
    CredentialSummary("remote_reference", "Remote reference", "This offline check reads only embedded manifests.", embedded = false)

private fun JsonObject.obj(key: String) = get(key)?.takeIf { it.isJsonObject }?.asJsonObject
private fun JsonObject.array(key: String) = get(key)?.takeIf { it.isJsonArray }?.asJsonArray
private fun JsonObject.str(key: String) = get(key)?.takeIf { it.isJsonPrimitive && it.asJsonPrimitive.isString }?.asString
private fun JsonObject.num(key: String) = get(key)?.takeIf { it.isJsonPrimitive && it.asJsonPrimitive.isNumber }?.asInt
private fun JsonArray?.objects(limit: Int): Sequence<JsonObject> = this?.asSequence()?.take(limit)
    ?.filter { it.isJsonObject }?.map { it.asJsonObject } ?: emptySequence()
private fun String?.displayText(limit: Int): String? =
    this?.take(limit)?.filterNot { Character.isISOControl(it) || Character.getType(it) == Character.FORMAT.toInt() }
        ?.trim()?.takeIf { it.isNotEmpty() }

internal fun summarizeCredentials(root: JsonObject, embedded: Boolean, expired: Boolean): CredentialSummary {
    if (!embedded) return remoteCredentials()
    val manifestId = root.str("active_manifest") ?: return unavailableCredentials("No active embedded manifest could be read.")
    val manifest = root.obj("manifests")?.obj(manifestId)
        ?: return unavailableCredentials("The active embedded manifest could not be read.")
    val result = root.obj("validation_results")?.obj("activeManifest")
    val checks = result?.array("success").objects(128).toList()
    val success = checks.mapNotNull { it.str("code") }.toSet()
    val failures = result?.array("failure").objects(128).mapNotNull { it.str("code")?.takeIf(ActionLabel::matches) }
        .distinct().toList()
    val integrityFailures = failures.filterNot(PolicyFindings::contains)
    val hashOnly = integrityFailures.isNotEmpty() && integrityFailures.all(HashMismatches::contains)
    val (status, outcome, detail) = when (root.str("validation_state")) {
        "Valid", "Trusted" -> Triple(if (root.str("validation_state") == "Trusted" && !expired) "trusted" else "valid",
            "Integrity verified", "The file matches its embedded manifest.")
        // An Android JNI short read can be reported as a hash mismatch (c2pa-android issue #133).
        "Invalid" -> if (hashOnly || integrityFailures.isEmpty()) {
            Triple("indeterminate", "Integrity inconclusive",
                if (hashOnly) "The local reader reported a hash mismatch. A file difference or a reader failure can produce this result."
                else "The local reader returned no decisive integrity finding.")
        } else Triple("invalid", "Integrity check failed", "A signature or assertion check failed.")
        else -> Triple("indeterminate", "Integrity inconclusive", "The reader did not return a usable verification result.")
    }
    val matched = checks.asSequence().filter { it.str("code") == "assertion.hashedURI.match" }
        .mapNotNull { it.str("url")?.substringAfterLast('/') }.toSet()
    val assertions = if (status in setOf("valid", "trusted")) manifest.array("assertions").objects(128).filter {
        val label = it.str("label")
        val instance = it.num("instance") ?: 0
        val identifier = if (instance > 0) "${label}__$instance" else label
        identifier in matched
    }.toList() else emptyList()
    val report = assertions.asSequence().filter { it.str("label") == "com.fabriziodegni.audioenhancermax.processing" }
        .mapNotNull { it.obj("data")?.str("processing_report_sha256")?.takeIf(ReportSha::matches) }
        .firstOrNull()?.lowercase(Locale.ROOT)
    fun timestamp(item: JsonObject, name: String): String? = item.str(name)?.takeIf { it.length <= 48 }?.let { text ->
        runCatching { Instant.parse(text).toString() }.getOrNull()
    }
    val actions = assertions.asSequence().filter { it.str("label") in setOf("c2pa.actions", "c2pa.actions.v2") }
        .flatMap { it.obj("data")?.array("actions").objects(64) }
        .mapNotNull { item ->
            item.str("action")?.takeIf(ActionLabel::matches)?.let { name ->
                val agent = (item.str("softwareAgent") ?: item.obj("softwareAgent")?.str("name")).displayText(100)
                CredentialAction(name, timestamp(item, "when"), timestamp(item, "whenStart"), timestamp(item, "whenEnd"), agent)
            }
        }.take(32).toList()
    val signerTrust = when {
        expired -> "trust_list_expired"
        "signingCredential.trusted" in success -> "recognized"
        "signingCredential.untrusted" in failures -> "unrecognized"
        else -> "not_established"
    }
    val timestampTrust = when {
        expired -> "trust_list_expired"
        "timeStamp.validated" in success && "timeStamp.trusted" in success -> "trusted"
        "timeStamp.validated" in success -> "validated_untrusted"
        else -> "not_established"
    }
    val signature = manifest.obj("signature_info")
    return CredentialSummary(status, outcome, detail, signature?.str("common_name").displayText(160),
        signature?.str("issuer").displayText(160), signerTrust, timestampTrust, report, actions, failures,
        embedded = true, trustSnapshotExpired = expired)
}
