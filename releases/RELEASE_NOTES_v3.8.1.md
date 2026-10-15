# AudioEnhancerMAX 3.8.1

Release date: 15 October 2026.

This maintenance release corrects presentation text. It removes long-dash punctuation from the website, the desktop interface, documentation and release copy. The repository check now catches HTML entities and JavaScript/CSS escapes as well as literal Unicode characters.

The SourceForge project description and features now describe the 3.8 revision-based workflow, optional runtimes and distribution status. Audio processing behavior is unchanged from [3.8.0](https://github.com/sev7enITA/AudioEnhancerMAX/releases/tag/v3.8.0).

## Validation and distribution

The existing 75 Python tests, 4 JavaScript state tests and repository presentation checks are used for this release. The packaged interface is checked against the source after rebuilding.

The macOS arm64 DMG is a Developer ID signed preview for macOS 13+. Apple notarization remains blocked by HTTP 403 pending the developer-team agreement. The notarized 3.7.0 remains the stable Mac download. No new App Store submission or approval is claimed.

Source archives exclude user recordings, private voice profiles and credentials. Third-party vendored sources and licenses are preserved.
