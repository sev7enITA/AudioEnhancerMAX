# Audio handoff between the phone and Mac

Connect the phone and Mac to the same Wi-Fi network or personal hotspot. Choose either direction:

- On the phone, open **Connection** and select **Make this phone discoverable**. On the Mac, open **Mobile devices and transfers → Find nearby phones** and invite the phone. Accept the invitation on the phone.
- On the Mac, select **Start nearby pairing**. On the phone, open **Connection → Find nearby Macs** and choose the Mac.

Compare the eight digits on both screens and select **Codes match** on both devices. A request expires after 90 seconds. The phone receives a device-specific credential after Mac approval.

Discovery uses Bonjour on the selected network. The Mac can resolve an explicitly discoverable phone's service and send it a local unicast invitation. The invitation contains the Mac's local listener and certificate fingerprint. The matching code is derived independently on each device from the TLS identity and the current exchange. If several interfaces are active, the Mac selects its preferred IPv4 route. Use **Shared network** to choose another interface.

**Use QR instead** opens the existing alternative. The QR and manual code grant access to the current session and should be kept private. All transfers require the pinned TLS connection. **Stop and revoke** closes the listener and withdraws the announcement and credentials. A change to the Mac's network address also ends the session.

If neither method connects, check local-network permission, ensure the phone is using Wi-Fi and try a personal hotspot. Guest and enterprise networks can prevent devices from communicating even when both show the same network name.

## Receive a source or process it on the Mac

The mobile app prepares a WAV copy of the selection you send. The Mac receives WAV PCM16, PCM24, PCM32 or float32, with one or two channels at 8–96 kHz. Each transfer is limited to 20 MiB. Mobile editing and export can use different local limits.

In the Mac transfer list, **Open source in Studio** loads the received source for further work. A mobile job can also request **Voice** or **Level** processing. These jobs run on the receiving Mac and preserve the sample rate, duration and channel layout. Very short clips use peak normalization when a full loudness measurement block is unavailable.

Completed jobs have a revision, the source SHA-256, the output SHA-256 and the SHA-256 of the exact processing report. The gateway only delivers the result after confirming those relationships. The Mac's **Download result** and **Download report** buttons retrieve that revision's verified files while the session is active. Files already imported on the Mac remain local after revocation.

## Optional Voice EQ contribution

A phone can also contribute a bounded Voice EQ task to the Mac. This requires both **Allow trusted LAN processing** on the Mac and the foreground worker enabled on the phone. Pairing alone permits audio transfer. The phone's device metrics and local Voice EQ assessment describe that device's reported workload and are separate from transfer speed.
