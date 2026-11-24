package com.audioenhancermax.worker

import android.content.ClipData
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.util.Base64
import android.webkit.JavascriptInterface
import android.webkit.ValueCallback
import android.webkit.WebChromeClient
import android.webkit.WebResourceRequest
import android.webkit.WebResourceResponse
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.result.contract.ActivityResultContracts
import androidx.core.content.FileProvider
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import androidx.lifecycle.lifecycleScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.ByteArrayInputStream
import java.io.File
import java.util.UUID
import java.util.concurrent.atomic.AtomicBoolean

class ReviewDeskActivity : ComponentActivity() {
    private lateinit var desk: WebView
    private var pendingPicker: ValueCallback<Array<Uri>>? = null
    private val exporting = AtomicBoolean(false)
    private val pick = registerForActivityResult(ActivityResultContracts.StartActivityForResult()) { result ->
        val selected = result.data?.clipData
        val urls = if (result.resultCode != RESULT_OK) null
        else if (selected != null && selected.itemCount in 1..2) Array(selected.itemCount) { selected.getItemAt(it).uri }
        else if (selected == null) result.data?.data?.let { arrayOf(it) }
        else null
        val safe = urls
            ?.takeIf { items -> items.size in 1..2 && items.all { it.scheme == "content" } }
        pendingPicker?.onReceiveValue(safe)
        pendingPicker = null
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        desk = WebView(this)
        desk.settings.apply {
            javaScriptEnabled = true
            allowFileAccess = false
            allowContentAccess = true
            javaScriptCanOpenWindowsAutomatically = false
            setSupportMultipleWindows(false)
        }
        desk.setBackgroundColor(0xff121519.toInt())
        desk.addJavascriptInterface(ExportBridge(), "ReviewExport")
        desk.webViewClient = DeskClient()
        desk.webChromeClient = object : WebChromeClient() {
            override fun onShowFileChooser(
                view: WebView, callback: ValueCallback<Array<Uri>>, params: FileChooserParams,
            ): Boolean {
                pendingPicker?.onReceiveValue(null)
                pendingPicker = callback
                try {
                    val audio = params.acceptTypes.any { it.startsWith("audio/") || it == ".wav" }
                    val intent = Intent(Intent.ACTION_OPEN_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE)
                        .setType(if (audio) "audio/*" else "*/*")
                        .putExtra(Intent.EXTRA_ALLOW_MULTIPLE, params.mode == FileChooserParams.MODE_OPEN_MULTIPLE)
                    pick.launch(intent)
                } catch (_: Exception) {
                    callback.onReceiveValue(null)
                    pendingPicker = null
                }
                return true
            }
        }
        ViewCompat.setOnApplyWindowInsetsListener(desk) { view, insets ->
            val safe = insets.getInsets(WindowInsetsCompat.Type.systemBars() or
                WindowInsetsCompat.Type.displayCutout() or WindowInsetsCompat.Type.ime())
            view.setPadding(safe.left, safe.top, safe.right, safe.bottom)
            WindowInsetsCompat.CONSUMED
        }
        setContentView(desk)
        desk.loadUrl(ENTRY)
    }

    override fun onStop() {
        desk.evaluateJavascript("document.getElementById('listener')?.pause()", null)
        super.onStop()
    }

    override fun onDestroy() {
        pendingPicker?.onReceiveValue(null)
        desk.removeJavascriptInterface("ReviewExport")
        desk.destroy()
        super.onDestroy()
    }

    private inner class DeskClient : WebViewClient() {
        override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean =
            request.url.toString() != ENTRY

        override fun shouldInterceptRequest(view: WebView, request: WebResourceRequest): WebResourceResponse {
            val address = request.url.toString()
            val name = address.removePrefix(ROOT)
            val mime = if (request.method == "GET" && address == ROOT + name) CONTENT[name] else null
            if (mime != null) {
                val data = runCatching { assets.open("review-desk/$name") }.getOrNull()
                if (data != null) return WebResourceResponse(mime, "utf-8", data)
            }
            return WebResourceResponse("text/plain", "utf-8", 403, "Blocked", emptyMap(),
                ByteArrayInputStream(ByteArray(0)))
        }
    }

    private inner class ExportBridge {
        @JavascriptInterface
        fun save(name: String, encoded: String) {
            val mime = EXPORTS[name] ?: return
            if (encoded.length > 11_184_812 || !exporting.compareAndSet(false, true)) return
            runOnUiThread {
                lifecycleScope.launch {
                    try {
                        val file = withContext(Dispatchers.IO) {
                            val bytes = Base64.decode(encoded, Base64.DEFAULT)
                            require(bytes.isNotEmpty() && bytes.size <= 8 * 1024 * 1024)
                            val directory = File(cacheDir, "review-exports/${UUID.randomUUID()}")
                            check(directory.mkdirs())
                            File(directory, name).apply { writeBytes(bytes) }
                        }
                        val uri = FileProvider.getUriForFile(this@ReviewDeskActivity, "$packageName.files", file)
                        val outgoing = Intent(Intent.ACTION_SEND).setType(mime)
                            .putExtra(Intent.EXTRA_STREAM, uri).addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                        outgoing.clipData = ClipData.newRawUri(name, uri)
                        startActivity(Intent.createChooser(outgoing, "Export from Review Desk"))
                    } catch (error: Exception) {
                        if (error is kotlinx.coroutines.CancellationException) throw error
                        Toast.makeText(this@ReviewDeskActivity, "The export could not be prepared.", Toast.LENGTH_LONG).show()
                    } finally {
                        exporting.set(false)
                    }
                }
            }
        }
    }

    private companion object {
        const val ROOT = "https://appassets.androidplatform.net/review-desk/"
        const val ENTRY = ROOT + "index.html"
        val CONTENT = mapOf("index.html" to "text/html", "review.css" to "text/css",
            "engine.js" to "application/javascript", "review.js" to "application/javascript")
        val EXPORTS = mapOf("aemax-review-pack.json" to "application/json", "aemax-clip.wav" to "audio/wav",
            "aemax-clip.srt" to "text/plain", "aemax-chapters.txt" to "text/plain")
    }
}
