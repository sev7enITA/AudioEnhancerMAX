"""Native AppKit/WebKit window used by the packaged macOS application."""

from __future__ import annotations

import logging
import os
import sys
import threading
import time
from pathlib import Path
from urllib.parse import urlparse

import objc
from AppKit import (
    NSAlert,
    NSAlertFirstButtonReturn,
    NSApplication,
    NSApplicationActivationPolicyRegular,
    NSBackingStoreBuffered,
    NSMakeRect,
    NSMenu,
    NSMenuItem,
    NSModalResponseOK,
    NSOpenPanel,
    NSSavePanel,
    NSTextField,
    NSWindow,
    NSWindowStyleMaskClosable,
    NSWindowStyleMaskMiniaturizable,
    NSWindowStyleMaskResizable,
    NSWindowStyleMaskTitled,
    NSWorkspace,
)
from Foundation import NSURL, NSURLRequest
from WebKit import (
    WKNavigationActionPolicyAllow,
    WKNavigationActionPolicyCancel,
    WKNavigationActionPolicyDownload,
    WKNavigationResponsePolicyAllow,
    WKNavigationResponsePolicyDownload,
    WKWebView,
    WKWebViewConfiguration,
)


LOGGER = logging.getLogger(__name__)
LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}
WINDOW_STYLE = (
    NSWindowStyleMaskTitled
    | NSWindowStyleMaskClosable
    | NSWindowStyleMaskMiniaturizable
    | NSWindowStyleMaskResizable
)


def _is_local_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and parsed.hostname in LOCAL_HOSTS


def _frontend_resource_dir() -> Path:
    bundle_root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
    return bundle_root / "frontend"


def _about_html(*, version: str, build_number: str, distribution: str) -> str:
    channel = "Mac App Store" if distribution == "app-store" else "Direct / development"
    return f"""
    <!doctype html>
    <html lang="en">
      <head>
        <meta charset="utf-8">
        <meta name="color-scheme" content="dark">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
          :root {{ --bg:#080b0f; --card:#11171d; --line:#28333d; --text:#eef3f6;
                  --muted:#9aa7b3; --cyan:#43dce5; --purple:#aa83ff; --coral:#ff766d; }}
          * {{ box-sizing:border-box; }}
          body {{ margin:0; background:var(--bg); color:var(--text);
                  font:14px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }}
          main {{ max-width:880px; margin:0 auto; padding:34px; }}
          .hero {{ display:grid; grid-template-columns:92px 1fr; gap:22px; align-items:center;
                   padding-bottom:26px; border-bottom:1px solid var(--line); }}
          .logo {{ width:88px; height:88px; border-radius:20px; }}
          .kicker {{ color:var(--cyan); font-size:11px; font-weight:700; letter-spacing:.12em;
                     text-transform:uppercase; }}
          h1 {{ font-size:30px; line-height:1.15; margin:4px 0 6px; }}
          h2 {{ font-size:18px; margin:0 0 12px; }}
          h3 {{ font-size:14px; margin:0 0 5px; }}
          p {{ margin:5px 0; }}
          .byline,.muted {{ color:var(--muted); }}
          .meta {{ display:grid; grid-template-columns:repeat(4,1fr); gap:10px; margin:22px 0; }}
          .meta div,.card {{ background:var(--card); border:1px solid var(--line); border-radius:12px; }}
          .meta div {{ padding:12px; }}
          .meta span {{ display:block; color:var(--muted); font-size:11px; text-transform:uppercase; }}
          .meta strong {{ display:block; margin-top:3px; }}
          section {{ padding:22px 0; border-top:1px solid var(--line); }}
          .grid {{ display:grid; grid-template-columns:repeat(2,1fr); gap:12px; }}
          .card {{ padding:15px; }}
          ul,ol {{ margin:8px 0 0; padding-left:20px; }}
          code {{ color:var(--cyan); }}
          .notice {{ border-left:3px solid var(--coral); padding:9px 12px; margin-top:14px;
                     color:#ffd3cf; background:#271516; border-radius:0 8px 8px 0; }}
          .actions {{ display:flex; flex-wrap:wrap; gap:9px; margin-top:14px; }}
          a.button {{ color:var(--text); text-decoration:none; border:1px solid #3a4a57;
                     background:#162029; border-radius:8px; padding:8px 11px; font-weight:600; }}
          a.button.primary {{ border-color:#238e95; color:#9af5fa; }}
          footer {{ color:var(--muted); font-size:12px; padding-top:22px; border-top:1px solid var(--line); }}
          @media(max-width:700px) {{ .meta,.grid {{ grid-template-columns:1fr 1fr; }} }}
        </style>
      </head>
      <body>
        <main>
          <div class="hero">
            <img class="logo" src="img/audioenhancermax-logo.png" alt="AudioEnhancerMAX logo">
            <div><span class="kicker">Local-first audio workspace</span>
              <h1>AudioEnhancerMAX</h1>
              <p>Audio processing, transcription, monitoring and trusted-LAN edge workers in one suite.</p>
              <p class="byline">Created and maintained by <strong>Fabrizio Degni</strong></p>
            </div>
          </div>

          <div class="meta">
            <div><span>Version</span><strong>{version} ({build_number})</strong></div>
            <div><span>Distribution</span><strong>{channel}</strong></div>
            <div><span>License</span><strong>MIT</strong></div>
            <div><span>Support</span><strong>Open-source community</strong></div>
          </div>

          <section><h2>Purpose and core capabilities</h2>
            <div class="grid">
              <div class="card"><h3>Enhance audio locally</h3><p class="muted">Import, inspect, clean, compare and export recordings while preserving the original.</p></div>
              <div class="card"><h3>Speech tools</h3><p class="muted">Local Faster-Whisper transcription plus clearly identified optional speech services.</p></div>
              <div class="card"><h3>Native macOS experience</h3><p class="muted">Apple Silicon app with native Open and Save panels and no Terminal command required.</p></div>
              <div class="card"><h3>Optional trusted devices</h3><p class="muted">User-enabled local-network workers can extend selected processing tasks.</p></div>
            </div>
          </section>

          <section><h2>Privacy and data flow</h2>
            <div class="grid">
              <div class="card"><h3>Local by default</h3><p class="muted">Core audio processing and packaged transcription run on this Mac. The private desktop service listens only on <code>127.0.0.1</code> and stops with the app.</p></div>
              <div class="card"><h3>Network use is contextual</h3><p class="muted">Text leaves the Mac only when an online TTS option is explicitly selected. Audio crosses the LAN only when a trusted edge worker is enabled and used.</p></div>
              <div class="card"><h3>No maintainer telemetry</h3><p class="muted">Recordings, outputs and diagnostics are not automatically uploaded to the maintainer.</p></div>
              <div class="card"><h3>User-controlled files</h3><p class="muted">You choose source files and export destinations with standard macOS panels.</p></div>
            </div>
            <div class="actions">
              <a class="button primary" href="https://fabriziodegni.com/AudioEnhancerMAX/privacy.html" target="_blank">Privacy notice</a>
              <a class="button" href="https://fabriziodegni.com/AudioEnhancerMAX/accessibility.html" target="_blank">Accessibility</a>
            </div>
          </section>

          <section><h2>System requirements and supported files</h2>
            <ul>
              <li>Apple Silicon Mac (arm64), macOS 13.0 or later.</li>
              <li>Core Mac App Store workflow is self-contained; optional Ollama, online TTS and LAN workers are not required.</li>
              <li>Import limit: 500 MB per file.</li>
              <li>Supported inputs include WAV, MP3, MP4, FLAC, OGG, M4A, AAC and WMA.</li>
            </ul>
          </section>

          <section><h2>Support and issue reporting</h2>
            <p>Support is community-based and does not require an AudioEnhancerMAX account. Search existing GitHub tickets before opening a new issue.</p>
            <p class="muted">Include the app version and distribution, macOS version, Mac model and chip, exact reproduction steps, selected modules, output format and the complete redacted error message.</p>
            <div class="notice"><strong>Do not publish sensitive material.</strong><br>Never attach confidential recordings, transcripts, credentials, personal identifiers or unreviewed logs to a public ticket. Use a synthetic or redacted sample.</div>
            <div class="actions">
              <a class="button primary" href="https://fabriziodegni.com/AudioEnhancerMAX/support.html" target="_blank">Official support page</a>
              <a class="button" href="https://github.com/sev7enITA/AudioEnhancerMAX/issues/new/choose" target="_blank">Open support ticket</a>
              <a class="button" href="https://github.com/sev7enITA/AudioEnhancerMAX/issues" target="_blank">Search tickets</a>
              <a class="button" href="https://github.com/sev7enITA/AudioEnhancerMAX/releases" target="_blank">Releases</a>
            </div>
          </section>

          <section><h2>Architecture</h2>
            <div class="grid">
              <div class="card"><h3>Backend</h3><p class="muted">FastAPI + Python 3.11</p></div>
              <div class="card"><h3>Native shell</h3><p class="muted">AppKit + WKWebView</p></div>
              <div class="card"><h3>Audio and AI</h3><p class="muted">PyAV, scipy, pedalboard, PyTorch MPS and Faster-Whisper</p></div>
              <div class="card"><h3>Project</h3><p class="muted">Source code, documentation and release history are available on GitHub.</p></div>
            </div>
            <div class="actions"><a class="button" href="https://github.com/sev7enITA/AudioEnhancerMAX" target="_blank">GitHub repository</a><a class="button" href="https://sourceforge.net/projects/audioenhancermax/" target="_blank">SourceForge project</a></div>
          </section>

          <section><h2>Support scope and warranty</h2>
            <p class="muted">Support is provided on a reasonable-effort basis by the maintainer and contributors. No guaranteed response or resolution time is offered unless a separate written agreement exists. AudioEnhancerMAX is provided under the MIT License without warranty.</p>
          </section>

          <footer><strong>AudioEnhancerMAX {version} (build {build_number})</strong><br>
            Copyright (c) 2026 Fabrizio Degni. Open source under the MIT License.</footer>
        </main>
      </body>
    </html>
    """


class NativeAppDelegate(objc.lookUpClass("NSObject")):
    """Own the native window and coordinate it with the embedded server."""

    def init(self):
        self = objc.super(NativeAppDelegate, self).init()
        if self is None:
            return None
        self.app_name = "AudioEnhancerMAX"
        self.app_version = "3.8.1"
        self.build_number = "development"
        self.distribution = "direct"
        self.frontend_url = None
        self.health_check = None
        self.server = None
        self.server_thread = None
        self.shutdown_callback = None
        self.window = None
        self.web_view = None
        self.about_window = None
        self.about_web_view = None
        self._ready_thread = None
        self._terminating = False
        return self

    def applicationDidFinishLaunching_(self, _notification):
        application = NSApplication.sharedApplication()
        application.setActivationPolicy_(NSApplicationActivationPolicyRegular)
        self._build_menu(application)

        frame = NSMakeRect(0.0, 0.0, 1440.0, 900.0)
        self.window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            frame,
            WINDOW_STYLE,
            NSBackingStoreBuffered,
            False,
        )
        self.window.setTitle_(self.app_name)
        self.window.setMinSize_((1024.0, 700.0))
        self.window.setFrameAutosaveName_("AudioEnhancerMAXMainWindow")
        self.window.setRestorable_(False)
        self.window.setDelegate_(self)

        configuration = WKWebViewConfiguration.alloc().init()
        self.web_view = WKWebView.alloc().initWithFrame_configuration_(frame, configuration)
        self.web_view.setNavigationDelegate_(self)
        self.web_view.setUIDelegate_(self)
        self.window.setContentView_(self.web_view)
        self._show_loading_screen()

        self.window.center()
        self.window.makeKeyAndOrderFront_(None)
        application.activateIgnoringOtherApps_(True)

        self._ready_thread = threading.Thread(
            target=self._wait_for_server,
            name="AudioEnhancerMAX readiness",
            daemon=True,
        )
        self._ready_thread.start()

    def _build_menu(self, application):
        main_menu = NSMenu.alloc().init()

        app_menu_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            self.app_name, None, ""
        )
        main_menu.addItem_(app_menu_item)
        app_menu = NSMenu.alloc().initWithTitle_(self.app_name)
        about_item = app_menu.addItemWithTitle_action_keyEquivalent_(
            f"About {self.app_name}", "showAbout:", ""
        )
        about_item.setTarget_(self)
        app_menu.addItem_(NSMenuItem.separatorItem())
        app_menu.addItemWithTitle_action_keyEquivalent_(
            f"Hide {self.app_name}", "hide:", "h"
        )
        app_menu.addItemWithTitle_action_keyEquivalent_("Hide Others", "hideOtherApplications:", "")
        app_menu.addItemWithTitle_action_keyEquivalent_("Show All", "unhideAllApplications:", "")
        app_menu.addItem_(NSMenuItem.separatorItem())
        app_menu.addItemWithTitle_action_keyEquivalent_(
            f"Quit {self.app_name}", "terminate:", "q"
        )
        app_menu_item.setSubmenu_(app_menu)

        edit_menu_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "Edit", None, ""
        )
        main_menu.addItem_(edit_menu_item)
        edit_menu = NSMenu.alloc().initWithTitle_("Edit")
        edit_menu.addItemWithTitle_action_keyEquivalent_("Undo", "undo:", "z")
        edit_menu.addItemWithTitle_action_keyEquivalent_("Redo", "redo:", "Z")
        edit_menu.addItem_(NSMenuItem.separatorItem())
        edit_menu.addItemWithTitle_action_keyEquivalent_("Cut", "cut:", "x")
        edit_menu.addItemWithTitle_action_keyEquivalent_("Copy", "copy:", "c")
        edit_menu.addItemWithTitle_action_keyEquivalent_("Paste", "paste:", "v")
        edit_menu.addItemWithTitle_action_keyEquivalent_("Select All", "selectAll:", "a")
        edit_menu_item.setSubmenu_(edit_menu)

        view_menu_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "View", None, ""
        )
        main_menu.addItem_(view_menu_item)
        view_menu = NSMenu.alloc().initWithTitle_("View")
        reload_item = view_menu.addItemWithTitle_action_keyEquivalent_("Reload", "reload:", "r")
        reload_item.setTarget_(self)
        view_menu.addItem_(NSMenuItem.separatorItem())
        view_menu.addItemWithTitle_action_keyEquivalent_(
            "Enter Full Screen", "toggleFullScreen:", "f"
        )
        view_menu_item.setSubmenu_(view_menu)

        window_menu_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "Window", None, ""
        )
        main_menu.addItem_(window_menu_item)
        window_menu = NSMenu.alloc().initWithTitle_("Window")
        window_menu.addItemWithTitle_action_keyEquivalent_("Minimize", "performMiniaturize:", "m")
        window_menu.addItemWithTitle_action_keyEquivalent_("Zoom", "performZoom:", "")
        window_menu_item.setSubmenu_(window_menu)
        application.setWindowsMenu_(window_menu)

        application.setMainMenu_(main_menu)
        app_menu_item.setTitle_(self.app_name)

    def showAbout_(self, _sender):
        if self.about_window is None:
            frame = NSMakeRect(0.0, 0.0, 820.0, 720.0)
            self.about_window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
                frame,
                WINDOW_STYLE,
                NSBackingStoreBuffered,
                False,
            )
            self.about_window.setTitle_(f"About {self.app_name}")
            self.about_window.setMinSize_((680.0, 560.0))
            self.about_window.setRestorable_(False)
            self.about_window.setReleasedWhenClosed_(False)
            self.about_window.setDelegate_(self)

            configuration = WKWebViewConfiguration.alloc().init()
            self.about_web_view = WKWebView.alloc().initWithFrame_configuration_(frame, configuration)
            self.about_web_view.setNavigationDelegate_(self)
            self.about_web_view.setUIDelegate_(self)
            self.about_window.setContentView_(self.about_web_view)

            base_url = NSURL.fileURLWithPath_isDirectory_(
                str(_frontend_resource_dir()), True
            )
            self.about_web_view.loadHTMLString_baseURL_(
                _about_html(
                    version=self.app_version,
                    build_number=self.build_number,
                    distribution=self.distribution,
                ),
                base_url,
            )
            self.about_window.center()

        self.about_window.makeKeyAndOrderFront_(None)
        NSApplication.sharedApplication().activateIgnoringOtherApps_(True)

    def _show_loading_screen(self):
        html = """
        <!doctype html>
        <html lang="en">
          <head>
            <meta charset="utf-8">
            <meta name="color-scheme" content="dark">
            <style>
              html, body { height: 100%; margin: 0; }
              body { display: grid; place-items: center; background: #080b0f;
                     color: #f4f7fa; font: 15px -apple-system, BlinkMacSystemFont, sans-serif; }
              main { text-align: center; }
              .mark { width: 58px; height: 58px; margin: 0 auto 20px; border-radius: 14px;
                      border: 1px solid #3fe4ea; box-shadow: 0 0 28px #18cbd144;
                      display: grid; place-items: center; color: #50e6ed; font-size: 28px; }
              h1 { font-size: 22px; margin: 0 0 8px; }
              p { color: #8e9aa7; margin: 0; }
            </style>
          </head>
          <body><main><div class="mark">∿</div><h1>AudioEnhancerMAX</h1>
          <p>Starting the private audio engine…</p></main></body>
        </html>
        """
        self.web_view.loadHTMLString_baseURL_(html, None)

    def _wait_for_server(self):
        for _ in range(160):
            if self._terminating:
                return
            if self.health_check():
                url = NSURL.URLWithString_(self.frontend_url)
                self.performSelectorOnMainThread_withObject_waitUntilDone_(
                    "loadApplicationURL:", url, False
                )
                return
            if self.server_thread is not None and not self.server_thread.is_alive():
                break
            time.sleep(0.25)
        self.performSelectorOnMainThread_withObject_waitUntilDone_(
            "showStartupError:", "The private audio engine could not be started.", False
        )

    def loadApplicationURL_(self, url):
        request = NSURLRequest.requestWithURL_(url)
        self.web_view.loadRequest_(request)

    def showStartupError_(self, message):
        alert = NSAlert.alloc().init()
        alert.setMessageText_("AudioEnhancerMAX could not start")
        alert.setInformativeText_(message)
        alert.addButtonWithTitle_("Quit")
        alert.runModal()
        NSApplication.sharedApplication().terminate_(None)

    def reload_(self, _sender):
        if self.web_view is not None:
            self.web_view.reload()

    def applicationShouldTerminateAfterLastWindowClosed_(self, _application):
        return True

    def windowWillClose_(self, notification):
        closing_window = notification.object()
        if closing_window is self.window and not self._terminating:
            NSApplication.sharedApplication().terminate_(None)

    def application_shouldSaveApplicationState_(self, _application, _coder):
        return False

    def application_shouldRestoreApplicationState_(self, _application, _coder):
        return False

    def applicationWillTerminate_(self, _notification):
        self._terminating = True
        if self.server is not None:
            self.server.should_exit = True
        if self.server_thread is not None and self.server_thread.is_alive():
            self.server_thread.join(timeout=10.0)
        if self.shutdown_callback is not None:
            try:
                self.shutdown_callback()
            except Exception:
                LOGGER.exception("Native shutdown cleanup failed")

    def webView_decidePolicyForNavigationAction_decisionHandler_(
        self, _web_view, navigation_action, decision_handler
    ):
        request_url = navigation_action.request().URL()
        value = request_url.absoluteString() if request_url is not None else ""
        if navigation_action.shouldPerformDownload():
            decision_handler(WKNavigationActionPolicyDownload)
        elif value.startswith("blob:") or _is_local_url(value):
            decision_handler(WKNavigationActionPolicyAllow)
        elif request_url is not None and request_url.scheme() in {"http", "https"}:
            NSWorkspace.sharedWorkspace().openURL_(request_url)
            decision_handler(WKNavigationActionPolicyCancel)
        else:
            decision_handler(WKNavigationActionPolicyAllow)

    def webView_decidePolicyForNavigationResponse_decisionHandler_(
        self, _web_view, navigation_response, decision_handler
    ):
        response = navigation_response.response()
        headers = response.allHeaderFields() if hasattr(response, "allHeaderFields") else {}
        disposition = str(headers.get("Content-Disposition", "")).lower()
        if "attachment" in disposition or not navigation_response.canShowMIMEType():
            decision_handler(WKNavigationResponsePolicyDownload)
        else:
            decision_handler(WKNavigationResponsePolicyAllow)

    def webView_navigationAction_didBecomeDownload_(self, _web_view, _action, download):
        download.setDelegate_(self)

    def webView_navigationResponse_didBecomeDownload_(self, _web_view, _response, download):
        download.setDelegate_(self)

    def download_decideDestinationUsingResponse_suggestedFilename_completionHandler_(
        self, _download, _response, suggested_filename, completion_handler
    ):
        panel = NSSavePanel.alloc().init()
        if panel is None:
            LOGGER.error("Could not create the native save panel")
            completion_handler(None)
            return
        panel.setNameFieldStringValue_(suggested_filename or "AudioEnhancerMAX export")
        if panel.runModal() == NSModalResponseOK:
            completion_handler(panel.URL())
        else:
            completion_handler(None)

    def download_didFailWithError_resumeData_(self, _download, error, _resume_data):
        LOGGER.error("WebKit download failed: %s", error)

    def webView_runOpenPanelWithParameters_initiatedByFrame_completionHandler_(
        self, _web_view, parameters, _frame, completion_handler
    ):
        panel = NSOpenPanel.alloc().init()
        if panel is None:
            LOGGER.error("Could not create the native open panel")
            completion_handler(None)
            return
        panel.setCanChooseFiles_(True)
        panel.setCanChooseDirectories_(parameters.allowsDirectories())
        panel.setAllowsMultipleSelection_(parameters.allowsMultipleSelection())
        if panel.runModal() == NSModalResponseOK:
            completion_handler(panel.URLs())
        else:
            completion_handler(None)

    def webView_runJavaScriptAlertPanelWithMessage_initiatedByFrame_completionHandler_(
        self, _web_view, message, _frame, completion_handler
    ):
        alert = NSAlert.alloc().init()
        alert.setMessageText_(self.app_name)
        alert.setInformativeText_(message)
        alert.addButtonWithTitle_("OK")
        alert.runModal()
        completion_handler()

    def webView_runJavaScriptConfirmPanelWithMessage_initiatedByFrame_completionHandler_(
        self, _web_view, message, _frame, completion_handler
    ):
        alert = NSAlert.alloc().init()
        alert.setMessageText_(self.app_name)
        alert.setInformativeText_(message)
        alert.addButtonWithTitle_("OK")
        alert.addButtonWithTitle_("Cancel")
        completion_handler(alert.runModal() == NSAlertFirstButtonReturn)

    def webView_runJavaScriptTextInputPanelWithPrompt_defaultText_initiatedByFrame_completionHandler_(
        self, _web_view, prompt, default_text, _frame, completion_handler
    ):
        alert = NSAlert.alloc().init()
        alert.setMessageText_(self.app_name)
        alert.setInformativeText_(prompt)
        field = NSTextField.alloc().initWithFrame_(NSMakeRect(0.0, 0.0, 320.0, 24.0))
        field.setStringValue_(default_text or "")
        alert.setAccessoryView_(field)
        alert.addButtonWithTitle_("OK")
        alert.addButtonWithTitle_("Cancel")
        result = alert.runModal()
        completion_handler(field.stringValue() if result == NSAlertFirstButtonReturn else None)

    def webView_createWebViewWithConfiguration_forNavigationAction_windowFeatures_(
        self, _web_view, _configuration, navigation_action, _window_features
    ):
        request_url = navigation_action.request().URL()
        value = request_url.absoluteString() if request_url is not None else ""
        if request_url is not None and _is_local_url(value):
            self.web_view.loadRequest_(navigation_action.request())
        elif request_url is not None:
            NSWorkspace.sharedWorkspace().openURL_(request_url)
        return None


def run_native_application(
    *,
    app_name: str,
    app_version: str,
    build_number: str,
    distribution: str,
    frontend_url: str,
    health_check,
    server,
    server_thread: threading.Thread,
    shutdown_callback,
) -> None:
    """Run the native AppKit event loop until the user quits the application."""
    application = NSApplication.sharedApplication()
    delegate = NativeAppDelegate.alloc().init()
    delegate.app_name = app_name
    delegate.app_version = app_version
    delegate.build_number = build_number
    delegate.distribution = distribution
    delegate.frontend_url = frontend_url
    delegate.health_check = health_check
    delegate.server = server
    delegate.server_thread = server_thread
    delegate.shutdown_callback = shutdown_callback
    application.setDelegate_(delegate)
    application.run()


def activate_existing_application(bundle_identifier: str) -> bool:
    """Bring the existing application instance to the foreground."""
    running_application = objc.lookUpClass("NSRunningApplication")
    instances = running_application.runningApplicationsWithBundleIdentifier_(bundle_identifier)
    for instance in instances:
        if instance.processIdentifier() != os.getpid():
            return bool(instance.activateWithOptions_(1 << 1))
    return False
