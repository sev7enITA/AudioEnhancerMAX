(() => {
    const inspector = document.getElementById('credentials-inspector');
    const exportPanel = document.getElementById('credentials-export');
    const exportButton = document.getElementById('credentials-export-button');
    const exportStatus = document.getElementById('credentials-export-status');
    const inspectionStatus = document.getElementById('credentials-inspection');
    const fileInput = document.getElementById('credentials-file');
    const watermarkShortcut = document.getElementById('watermark-credentials-shortcut');
    const aboutCredentials = document.getElementById('about-content-credentials');
    const trustedTimestamp = 'Trusted RFC 3161 timestamp verified.';
    const evidence = document.getElementById('media-verification-evidence');
    const fingerprint = document.getElementById('media-verification-fingerprint');
    const processingReport = document.getElementById('media-verification-processing-report');
    const audioDetails = document.getElementById('media-verification-audio');
    const waveform = document.getElementById('media-verification-waveform');
    const audioseal = document.getElementById('media-verification-audioseal');
    const watermarkDetails = document.getElementById('media-verification-watermark');
    const downloadReport = document.getElementById('media-verification-download');
    let currentReport = null;
    let canSign = false;
    let signing = false;
    let availabilityRequest = 0;

    const messages = {
        trusted: 'File binding and signature verified. The local validator trusts the signing certificate.',
        valid: 'File binding and signature verified. The local validator does not recognize the signer.',
        invalid: 'The Content Credentials did not pass validation.',
        missing: 'No embedded Content Credentials were found.',
        validator_unavailable: 'The C2PA validator is unavailable in this build.',
        format_mismatch: 'The file header does not match the selected media format.',
        unreadable: 'The C2PA verification could not read the file.',
        remote: 'The credential references an external manifest. This inspector verifies embedded credentials offline.',
    };

    async function refreshAvailability() {
        const requestId = ++availabilityRequest;
        const response = await fetch('/api/content-credentials', {cache: 'no-store'});
        if (!response.ok) return;
        const availability = await response.json();
        if (requestId !== availabilityRequest) return;
        const wasAvailable = canSign;
        canSign = availability.sign;
        inspector.hidden = false;
        exportPanel.hidden = !availability.inspect;
        watermarkShortcut.hidden = false;
        aboutCredentials.hidden = !availability.inspect;
        if (signing) return;
        exportButton.disabled = !canSign;
        if (!canSign) {
            exportStatus.textContent = availability.sign_error ||
                'Configure a C2PA signing certificate and its Keychain profile or local test key.';
        } else if (!wasAvailable) {
            exportStatus.textContent = '';
        }
    }

    exportPanel.addEventListener('toggle', () => {
        if (exportPanel.open) refreshAvailability().catch(() => {});
    });

    watermarkShortcut.addEventListener('click', () => {
        switchPanel('upload-panel', document.querySelector('[data-panel="upload-panel"]'));
        inspector.open = true;
        inspector.querySelector('summary').focus();
    });

    function showAudio(audio) {
        waveform.replaceChildren();
        waveform.style.display = audio.status === 'measured' ? '' : 'none';
        if (audio.status !== 'measured') {
            audioDetails.textContent = audio.status === 'no_audio_track'
                ? 'No audio track was found.' : 'Audio measurements could not be completed.';
            return;
        }
        const asDb = value => value === null ? '−∞ dBFS' : `${value} dBFS`;
        audioDetails.textContent = `First audio track, ${audio.analyzed_seconds} s, mono preview · ` +
            `Peak ${asDb(audio.peak_dbfs)} · RMS ${asDb(audio.rms_dbfs)} · ` +
            `${audio.near_full_scale_percent}% near full scale.`;
        const bars = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        const step = 256 / audio.waveform_peak.length;
        bars.setAttribute('d', audio.waveform_peak.map((value, index) => {
            const x = (index + 0.5) * step;
            const halfHeight = Math.max(0.5, 22 * Math.min(value, 1));
            return `M${x},${24 - halfHeight}V${24 + halfHeight}`;
        }).join(' '));
        bars.setAttribute('stroke', 'currentColor');
        bars.setAttribute('stroke-width', Math.max(1, step - 1));
        waveform.append(bars);
    }

    fileInput.addEventListener('change', async () => {
        const file = fileInput.files[0];
        if (!file) return;
        currentReport = null;
        evidence.hidden = true;
        fileInput.disabled = true;
        inspectionStatus.textContent = 'Verifying the received file…';
        try {
            const supported = /\.(wav|mp3|flac|m4a|mp4|mov)$/i.exec(file.name);
            if (!supported) throw new Error('Choose a WAV, MP3, FLAC, M4A, MP4 or MOV file.');
            const extension = supported[1];
            const parameters = new URLSearchParams({extension, audioseal: audioseal.checked ? 'true' : 'false'});
            const response = await fetch(`/api/media-verification?${parameters}`, {
                method: 'POST',
                headers: {'Content-Type': 'application/octet-stream'},
                body: file,
            });
            if (!response.ok) throw new Error(await readApiError(response, 'Verification failed.'));
            const report = await response.json();
            const result = report.credentials;
            const detail = [
                messages[result.status] || 'Verification did not complete.',
                result.timestamp_trusted && !result.trust_snapshot_expired && trustedTimestamp,
                result.trust_snapshot_expired && 'The built-in trust lists have expired. Update AudioEnhancerMAX to verify the signer and timestamp trust.',
                result.signer && `Issuer: ${result.signer}.`,
                result.actions?.length && `Actions: ${result.actions.join(', ')}.`,
                result.failure_codes?.length && `Checks: ${result.failure_codes.join(', ')}.`,
            ].filter(Boolean);
            inspectionStatus.textContent = detail.join(' ');
            fingerprint.textContent = report.asset.sha256;
            processingReport.hidden = !result.processing_report_sha256;
            const referenceLabel = ['trusted', 'valid'].includes(result.status)
                ? 'Processing report SHA-256 claimed in the manifest' : 'Unverified processing report SHA-256';
            processingReport.textContent = result.processing_report_sha256
                ? `${referenceLabel}: ${result.processing_report_sha256}` : '';
            showAudio(report.audio);
            const measurement = report.watermark;
            watermarkDetails.hidden = !measurement;
            if (measurement) {
                const status = {
                    detector_unavailable: 'Install the verified AudioSeal detector package to run this check.',
                    audio_too_short: 'AudioSeal needs at least one second of audio.',
                };
                watermarkDetails.textContent = measurement.status === 'measured'
                    ? `Experimental AudioSeal 16-bit · ${(100 * measurement.fraction_above_signal_threshold).toFixed(1)}% of analyzed samples above the signal threshold over ${measurement.analyzed_seconds} s. This measures an AudioSeal signal only.`
                    : status[measurement.status] || 'AudioSeal measurement could not be completed.';
            }
            delete report.audio.waveform_peak;
            currentReport = report;
            evidence.hidden = false;
        } catch (error) {
            inspectionStatus.textContent = error.message;
        } finally {
            fileInput.value = '';
            fileInput.disabled = false;
        }
    });

    downloadReport.addEventListener('click', () => {
        if (!currentReport) return;
        const json = new Blob([JSON.stringify(currentReport, null, 2) + '\n'], {type: 'application/json'});
        const url = URL.createObjectURL(json);
        const anchor = document.createElement('a');
        anchor.href = url;
        anchor.download = `media-verification-${currentReport.asset.sha256.slice(0, 12)}.json`;
        document.body.appendChild(anchor);
        anchor.click();
        anchor.remove();
        setTimeout(() => URL.revokeObjectURL(url), 30000);
    });

    exportButton.addEventListener('click', async () => {
        if (signing || !canSign || !state.fileId || !state.hasProcessed || state.isProcessing || !state.processedRevision) return;
        const fileId = state.fileId;
        const revision = state.processedRevision;
        const formatPicker = document.getElementById('compliance-format');
        const format = formatPicker.value;
        const version = state.processedVersion;
        const isCurrent = () => fileId === state.fileId && revision === state.processedRevision &&
            version === state.processedVersion && format === formatPicker.value;
        signing = true;
        exportButton.disabled = true;
        exportStatus.textContent = 'Signing and verifying a copy…';
        try {
            const response = await fetch(`/api/content-credentials/export/${encodeURIComponent(fileId)}`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({format, version, revision}),
            });
            if (!response.ok) throw new Error(await readApiError(response, 'Signed export failed.'));
            const blob = await response.blob();
            if (!isCurrent()) {
                exportStatus.textContent = 'The result or format changed. Export the current selection to continue.';
                return;
            }
            const url = URL.createObjectURL(blob);
            const anchor = document.createElement('a');
            anchor.href = url;
            anchor.download = `AudioEnhancerMAX-${revision.slice(0, 8)}-credentials.${format}`;
            document.body.appendChild(anchor);
            anchor.click();
            anchor.remove();
            setTimeout(() => URL.revokeObjectURL(url), 30000);
            exportStatus.textContent = [
                messages[response.headers.get('X-Content-Credentials')],
                response.headers.get('X-C2PA-Timestamp') === 'trusted' && trustedTimestamp,
            ].filter(Boolean).join(' ');
        } catch (error) {
            exportStatus.textContent = isCurrent() ? error.message : '';
        } finally {
            signing = false;
            exportButton.disabled = !canSign;
        }
    });

    refreshAvailability().catch(() => {});
})();
