import SwiftUI
import AVFoundation
import UIKit

struct PairingScannerSheet: View {
    let onScan: (String) -> Void
    @Environment(\.dismiss) private var dismiss
    @State private var failure: String?
    var body: some View {
        NavigationStack {
            VStack(spacing: 20) {
                Text("Show the pairing QR code in your Mac's AudioEnhancerMAX Edge Cluster, then point this camera at it.")
                    .padding(.horizontal)
                if let failure {
                    ContentUnavailableView("Camera unavailable", systemImage: "camera", description: Text(failure))
                } else {
                    PairingCamera(onScan: onScan, onFailure: { failure = $0 })
                        .clipShape(RoundedRectangle(cornerRadius: 16)).padding(.horizontal)
                }
                Text("Read locally. No photo is saved or uploaded.").font(.footnote).foregroundStyle(.secondary)
            }.padding(.vertical).navigationTitle("Scan QR code").navigationBarTitleDisplayMode(.inline)
                .toolbar { ToolbarItem(placement: .cancellationAction) { Button("Cancel") { dismiss() } } }
        }
    }
}

private struct PairingCamera: UIViewControllerRepresentable {
    let onScan: (String) -> Void
    let onFailure: (String) -> Void
    func makeUIViewController(context: Context) -> PairingCameraController {
        PairingCameraController(onScan: onScan, onFailure: onFailure)
    }
    func updateUIViewController(_ controller: PairingCameraController, context: Context) {}
    static func dismantleUIViewController(_ controller: PairingCameraController, coordinator: ()) {
        controller.setRunning(false)
    }
}

private final class PairingCameraController: UIViewController, AVCaptureMetadataOutputObjectsDelegate {
    private let session = AVCaptureSession()
    private let queue = DispatchQueue(label: "com.audioenhancermax.pairing-camera")
    private var preview: AVCaptureVideoPreviewLayer?
    private var configured = false // Session state belongs to queue.
    private var wanted = false
    private var visible = false // UI state belongs to main.
    private var delivered = false
    private let onScan: (String) -> Void
    private let onFailure: (String) -> Void
    init(onScan: @escaping (String) -> Void, onFailure: @escaping (String) -> Void) {
        self.onScan = onScan; self.onFailure = onFailure
        super.init(nibName: nil, bundle: nil)
    }
    required init?(coder: NSCoder) { fatalError("Use programmatic initialisation") }
    override func viewDidLoad() {
        super.viewDidLoad()
        view.backgroundColor = .black
        let layer = AVCaptureVideoPreviewLayer(session: session)
        layer.videoGravity = .resizeAspectFill
        view.layer.addSublayer(layer); preview = layer
        NotificationCenter.default.addObserver(self, selector: #selector(background), name: UIApplication.willResignActiveNotification, object: nil)
        NotificationCenter.default.addObserver(self, selector: #selector(foreground), name: UIApplication.didBecomeActiveNotification, object: nil)
    }
    override func viewDidLayoutSubviews() {
        super.viewDidLayoutSubviews(); preview?.frame = view.bounds
    }
    override func viewDidAppear(_ animated: Bool) {
        super.viewDidAppear(animated); visible = true; requestCamera()
    }
    override func viewWillDisappear(_ animated: Bool) {
        visible = false; setRunning(false); super.viewWillDisappear(animated)
    }
    @objc private func background() { setRunning(false) }
    @objc private func foreground() { if visible && !delivered { requestCamera() } }
    private func requestCamera() {
        switch AVCaptureDevice.authorizationStatus(for: .video) {
        case .authorized: setRunning(true)
        case .notDetermined:
            AVCaptureDevice.requestAccess(for: .video) { [weak self] granted in
                DispatchQueue.main.async {
                    guard let self, self.visible, !self.delivered else { return }
                    if granted { self.setRunning(true) } else { self.denied() }
                }
            }
        default: denied()
        }
    }
    private func denied() {
        onFailure("Allow Camera access in iOS Settings to scan, or close this screen and use manual pairing.")
    }
    func setRunning(_ running: Bool) {
        queue.async { [self] in
            wanted = running
            if !running { if session.isRunning { session.stopRunning() }; return }
            if !configured {
                do { try configure() }
                catch {
                    DispatchQueue.main.async { [weak self] in
                        guard let self, self.visible else { return }
                        self.onFailure("This device cannot open a camera. Close this screen and use manual pairing.")
                    }
                    return
                }
            }
            if wanted && !session.isRunning { session.startRunning() }
        }
    }
    private func configure() throws {
        guard let device = AVCaptureDevice.default(.builtInWideAngleCamera, for: .video, position: .back)
                ?? AVCaptureDevice.default(for: .video) else { throw CompanionError.message("No camera") }
        let input = try AVCaptureDeviceInput(device: device)
        let output = AVCaptureMetadataOutput()
        session.beginConfiguration()
        defer { session.commitConfiguration() }
        guard session.canAddInput(input) else { throw CompanionError.message("Camera input unavailable") }
        session.addInput(input)
        guard session.canAddOutput(output) else {
            session.removeInput(input); throw CompanionError.message("QR reader unavailable")
        }
        session.addOutput(output)
        guard output.availableMetadataObjectTypes.contains(.qr) else {
            session.removeOutput(output); session.removeInput(input); throw CompanionError.message("QR unsupported")
        }
        output.setMetadataObjectsDelegate(self, queue: .main)
        output.metadataObjectTypes = [.qr]
        configured = true
    }
    func metadataOutput(_ output: AVCaptureMetadataOutput, didOutput objects: [AVMetadataObject], from connection: AVCaptureConnection) {
        guard visible, !delivered,
              let raw = objects.compactMap({ ($0 as? AVMetadataMachineReadableCodeObject)?.stringValue }).first else { return }
        delivered = true; setRunning(false); onScan(raw)
    }
    deinit { NotificationCenter.default.removeObserver(self) }
}
