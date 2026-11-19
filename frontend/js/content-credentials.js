(() => {
    const inspector = document.getElementById('credentials-inspector');
    const exportPanel = document.getElementById('credentials-export');
    const exportButton = document.getElementById('credentials-export-button');
    const exportStatus = document.getElementById('credentials-export-status');
    const inspectionStatus = document.getElementById('credentials-inspection');
    const fileInput = document.getElementById('credentials-file');
    const trustedTimestamp = 'Trusted RFC 3161 timestamp verified.';

    const messages = {
        trusted: 'File binding and signature verified. The local validator trusts the signing certificate.',
        valid: 'File binding and signature verified. The local validator does not recognize the signer.',
        invalid: 'The Content Credentials did not pass validation.',
        missing: 'No embedded Content Credentials were found.',
        remote: 'The credential references an external manifest. This inspector verifies embedded credentials offline.',
    };

    async function refreshAvailability() {
        const response = await fetch('/api/content-credentials', {cache: 'no-store'});
        if (!response.ok) return;
        const availability = await response.json();
        inspector.hidden = !availability.inspect;
        exportPanel.hidden = !availability.inspect;
        exportButton.disabled = !availability.sign;
        exportStatus.textContent = availability.sign ? '' :
            'Configure a C2PA signing certificate and its Keychain profile or local test key.';
    }

    exportPanel.addEventListener('toggle', () => {
        if (exportPanel.open) refreshAvailability().catch(() => {});
    });

    fileInput.addEventListener('change', async () => {
        const file = fileInput.files[0];
        if (!file) return;
        fileInput.disabled = true;
        inspectionStatus.textContent = 'Checking Content Credentials…';
        try {
            const form = new FormData();
            form.append('file', file);
            const response = await fetch('/api/content-credentials/inspect', {method: 'POST', body: form});
            if (!response.ok) throw new Error(await readApiError(response, 'Verification failed.'));
            const result = await response.json();
            const detail = [
                messages[result.status] || 'Verification did not complete.',
                result.timestamp_trusted && trustedTimestamp,
                result.signer && `Issuer: ${result.signer}.`,
                result.actions?.length && `Actions: ${result.actions.join(', ')}.`,
                result.failure_codes?.length && `Checks: ${result.failure_codes.join(', ')}.`,
            ].filter(Boolean);
            inspectionStatus.textContent = detail.join(' ');
        } catch (error) {
            inspectionStatus.textContent = error.message;
        } finally {
            fileInput.value = '';
            fileInput.disabled = false;
        }
    });

    exportButton.addEventListener('click', async () => {
        if (!state.fileId || !state.hasProcessed || state.isProcessing || !state.processedRevision) return;
        const fileId = state.fileId;
        const revision = state.processedRevision;
        const format = document.getElementById('compliance-format').value;
        const version = state.processedVersion;
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
            if (fileId !== state.fileId || revision !== state.processedRevision) {
                exportStatus.textContent = 'The current result changed. Export its revision to continue.';
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
            exportStatus.textContent = error.message;
        } finally {
            exportButton.disabled = false;
        }
    });

    refreshAvailability().catch(() => {});
})();
