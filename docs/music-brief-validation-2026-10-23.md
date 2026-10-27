# Music brief assistant: local validation, 23 October 2026

Source worktree: `/Users/fabriziodegni/Projects/AudioEnhancerMAX-music-assistant-20261023`.
Branch: `codex/music-brief-assistant-20261023`, based on `6c23240` (release 3.8.3).
The older Desktop checkout was readable in part but Git operations timed out. Work
was isolated from the clean, accessible release checkout instead of changing that tree.

The later packaged release is verified separately in
[Experimental 1 package verification](../releases/EXPERIMENTAL_1_VERIFICATION.md).

## Automated checks

| Check | Result |
| --- | --- |
| Full Python suite, isolated temporary data directory | 133 passed, 8 subtests passed |
| JavaScript state suites | 19 passed |
| Python compileall | Passed |
| JavaScript syntax, app.js and music-assistant.js | Passed |
| Ruff, new Python files and changed capability registry | Passed |
| git diff --check | Passed |

Python tests used the existing release virtual environment, with no dependency changes:

```sh
AEMAX_DATA_DIR=/tmp/aemax-music-regression-data \
  /Users/fabriziodegni/Projects/AudioEnhancerMAX-release-20261015/venv/bin/python -m pytest -q
node --test tests/test_review_state.cjs tests/test_music_assistant_state.cjs
```

The full Python suite reported existing FastAPI/Starlette deprecations and one clipping
warning in a synthetic audio regression case. Ruff reports eight existing findings in
`app/main.py`; the same findings were verified in the untouched base checkout. No new
lint findings were introduced by the music routes.

## Live local model and browser integration

The installed `gemma4:e2b` model returned a valid suggestion response in 13.46 seconds
in the first live API check. The same test first verified HTTP 403 with local editorial
permission disabled, then enabled it only in an isolated temporary test data directory.
This single timing is an observation, not a performance guarantee.

A separate Playwright browser run used the real FastAPI backend and real local Ollama:
build a brief, manually edit the prompt, request suggestions, verify the prompt is
unchanged, explicitly append suggestions, and download JSON. The downloaded artifact
matched the current prompt, original prompt, separate lyrics, applied-suggestion status
and model identity. No JavaScript page errors were observed. The initial run was
intercepted by the app's existing first-launch readiness dialog; the completed run
handled its Configure and continue action through the UI.

Test servers used dedicated `/tmp` data directories and `--lifespan off` to isolate
the feature flow from startup background services. Actual user privacy settings and
uploaded media were not changed. Model weights were already present; none were downloaded.

## Visual and interaction review

Independent review checked desktop, tablet, 375 px and 320 px layouts, JSON export,
privacy-off behavior, keyboard navigation, zoom and reduced motion. The final
Chromium correction round passed at desktop and 320 px widths: the Settings shortcut
focuses the Ollama permission switch without changing it, newly built prompts start
at selection and scroll offset zero, and settled keyboard focus uses the existing
cyan 2 px outline with 3 px offset. No JavaScript page errors were observed.

The correction round was narrow; it did not repeat the earlier export/model checks
or native browser zoom. The evaluator worked independently but used the same model
provider, since a different-provider agent was unavailable.

- [Desktop result](evidence/music-brief-20261023/desktop-result.png)
- [320 px result](evidence/music-brief-20261023/mobile320-result.png)
- [Settings focus at 320 px](evidence/music-brief-20261023/mobile320-settings.png)
- [Live local model check](evidence/music-brief-20261023/live-ollama.json)
- [Browser integration record](evidence/music-brief-20261023/browser-integration.json)

## Limits

These checks establish local source behavior, not a rebuilt or signed macOS release,
Mac App Store approval, deployment or public availability. No music generation or
perceptual audio-quality evaluation was performed. Suggestions remain subject to
human review, even when the API and export checks pass.
