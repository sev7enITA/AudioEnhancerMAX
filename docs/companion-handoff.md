# Audio handoff between the phone and Mac

Connect the phone and Mac to the same Wi-Fi network or hotspot. On the direct Mac build, open **Mobile devices and transfers**, choose the shared address and select **Start pairing**. On the phone, open **Connection** and scan the QR code or paste the manual code. Pairing is off when the Mac app starts.

The pairing code contains the address, the TLS certificate fingerprint and the session credential. Keep the code private. The companion checks the fingerprint before sending credentials or audio. **Stop and revoke** closes the listener and invalidates the code. A change to the Mac's network address also ends the session.

## Receive a source or process it on the Mac

The mobile app prepares a WAV copy of the selection you send. The Mac receives WAV PCM16, PCM24, PCM32 or float32, with one or two channels at 8–96 kHz. Each transfer is limited to 20 MiB. Mobile editing and export can use different local limits.

In the Mac transfer list, **Open source in Studio** loads the received source for further work. A mobile job can also request **Voice** or **Level** processing. These jobs run on the receiving Mac and preserve the sample rate, duration and channel layout. Very short clips use peak normalization when a full loudness measurement block is unavailable.

Completed jobs have a revision, the source SHA-256, the output SHA-256 and the SHA-256 of the exact processing report. The gateway only delivers the result after confirming those relationships. The Mac's **Download result** and **Download report** buttons retrieve that revision's verified files while the session is active. Files already imported on the Mac remain local after revocation.

## Optional Voice EQ contribution

A phone can also contribute a bounded Voice EQ task to the Mac. This requires both **Allow trusted LAN processing** on the Mac and the foreground worker enabled on the phone. Pairing alone permits audio transfer. The phone's device metrics and local Voice EQ assessment describe that device's reported workload and are separate from transfer speed.
