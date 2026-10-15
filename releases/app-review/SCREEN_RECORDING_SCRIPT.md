# Physical Mac Screen Recording Script

Apple requested a recording made on a physical device running the latest public OS. Immediately before recording, verify the public version in Software Update and note its exact build number. Do not use the current macOS 27 beta installation for this final evidence.

## Before recording

- Use a physical Apple silicon Mac running the latest public macOS release available on the recording date.
- Install build 3.7.1 through TestFlight or the same App Store delivery path used for review, not from the source tree.
- Use a clean macOS user account without Homebrew, Python, FFmpeg, Whisper models, Ollama, or developer tools where practical.
- Disconnect from the internet for the local processing and transcription portion. Reconnect only if demonstrating optional Microsoft TTS.
- Place `AudioEnhancerMAX-review-sample.wav` on the Desktop.
- Enable the macOS menu bar clock so the OS environment is visible.

## Recording sequence

1. Open About This Mac and show the physical Mac model, Apple silicon chip, and the latest public macOS available on the recording date. Apple lists macOS Tahoe 26.6 as the latest public release on 14 August 2026; verify again immediately before recording. Do not expose the serial number.
2. Launch AudioEnhancerMAX from Applications and show that its interface opens in a native app window, without opening the default browser.
3. Show that the app becomes ready without asking to install dependencies or download a model.
4. Show that Edge Cluster is disabled until the user enables it. Do not enable it unless Apple specifically asks to see the optional LAN workflow.
5. Upload `AudioEnhancerMAX-review-sample.wav`.
6. Run Smart Enhance with the Balanced profile and show the measured diagnosis.
7. Play a short original/processed comparison.
8. Choose a fixed delivery profile, export the processed result, and open the processing report.
9. Open Precision Speech Editor, create or accept one cut/mute decision, preview it, undo, redo, and render.
10. Open Transcription, select English or automatic language detection, and transcribe the sample while still offline.
11. Show the returned text and export format choices.
12. Before launch, optionally open Terminal and run the lifecycle monitor below. Keep it visible beside the app when launching and quitting.
13. Quit AudioEnhancerMAX or close its main window and show that the process disappears and the loopback listener is released.

## Optional lifecycle monitor for the recording

Paste this into Terminal before launching the TestFlight-installed app:

```zsh
while true; do
  clear
  date
  echo
  PID="$(/usr/bin/pgrep -f '^/Applications/AudioEnhancerMAX[.]app/Contents/MacOS/AudioEnhancerMAX$' | /usr/bin/head -1)"
  if [[ -n "$PID" ]]; then
    echo "APP: RUNNING (PID $PID)"
    /usr/sbin/lsof -nP -a -p "$PID" -iTCP -sTCP:LISTEN 2>/dev/null || echo "LOCAL SERVER: STARTING"
  else
    echo "APP: NOT RUNNING"
    echo "LOCAL SERVER: NOT LISTENING"
  fi
  sleep 1
done
```

This proves the listener belongs to the app process, is bound to loopback, and disappears when the app exits.

Keep the recording continuous and readable. Avoid editing out waits that would make the evidence ambiguous. A duration of roughly three to five minutes is sufficient.

## File name

Use `AudioEnhancerMAX-3.7.0-build-3.7.1-physical-macOS.mov` and attach it in App Store Connect under App Review Information.
