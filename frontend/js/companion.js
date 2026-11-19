// The pairing panel keeps access credentials in the local Mac webview.
(() => {
    const root = document.getElementById('companion-controls');
    if (!root) return;

    root.innerHTML = `
        <h3>Mobile devices and transfers</h3>
        <p>Pair your phone to send audio over the local network.</p>
        <div data-connected-devices></div>
        <label for="companion-host">Shared Wi-Fi or hotspot address</label>
        <select id="companion-host" class="setting-select"></select>
        <div class="flex gap-12">
            <button type="button" class="btn btn-secondary" data-action="refresh">Refresh networks</button>
            <button type="button" class="btn btn-primary" data-action="start" disabled>Start pairing</button>
            <button type="button" class="btn btn-secondary" data-action="show" hidden>Show pairing code</button>
            <button type="button" class="btn btn-secondary" data-action="stop" disabled>Stop and revoke</button>
        </div>
        <div data-pairing-view hidden>
            <p>Open <strong>Connection → Scan QR code</strong> on your phone. The code grants access to this session. Share it only with your devices.</p>
            <img data-pairing-qr alt="Companion pairing QR code" width="288" height="288" style="max-width:100%;height:auto;background:white;border-radius:8px" hidden>
            <details data-pairing-manual>
                <summary>Manual pairing</summary>
                <textarea aria-label="Private pairing code" readonly rows="4" style="width:100%;overflow-wrap:anywhere"></textarea>
                <button type="button" class="btn btn-secondary" data-action="copy">Copy pairing code</button>
            </details>
            <button type="button" class="btn btn-secondary" data-action="hide">Hide pairing code</button>
        </div>
        <p data-connection-status role="status">Checking local connection…</p>
        <div data-transfer-section hidden>
            <h4>Received audio this session</h4>
            <div data-transfers></div>
        </div>
        <p class="setting-supporting-text">To let a phone contribute Voice EQ, enable it on the phone and turn on Allow trusted LAN processing in Mac preferences.</p>
    `;

    const status = root.querySelector('[data-connection-status]');
    const devices = root.querySelector('[data-connected-devices]');
    const transfers = root.querySelector('[data-transfers]');
    const transferSection = root.querySelector('[data-transfer-section]');
    const host = root.querySelector('#companion-host');
    const view = root.querySelector('[data-pairing-view]');
    const manual = root.querySelector('[data-pairing-manual]');
    const code = root.querySelector('textarea');
    const qr = root.querySelector('[data-pairing-qr]');
    const action = name => root.querySelector(`[data-action="${name}"]`);

    let active = false;
    let busy = true;
    let imageURL = null;
    let deviceSnapshot = '';
    let transferSnapshot = '';
    let refreshInFlight = false;
    let sessionVersion = 0;

    function describe(message) {
        if (status.textContent !== message) status.textContent = message;
    }

    async function read(path, payload) {
        const options = {cache: 'no-store'};
        if (payload) {
            options.method = 'POST';
            options.headers = {'Content-Type': 'application/json'};
            options.body = JSON.stringify(payload);
        }
        const response = await fetch(`/api/companion/${path}`, options);
        const data = await response.json();
        if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Companion state could not be read.');
        return data;
    }

    function controls() {
        host.disabled = active || busy;
        action('refresh').disabled = active || busy;
        action('start').hidden = active;
        action('start').disabled = active || busy || !host.value;
        action('show').hidden = !active || !view.hidden;
        action('show').disabled = busy;
        action('stop').disabled = !active || busy;
    }

    function clearCode() {
        view.hidden = true;
        code.value = '';
        qr.hidden = true;
        qr.removeAttribute('src');
        manual.open = false;
        if (imageURL) URL.revokeObjectURL(imageURL);
        imageURL = null;
    }

    async function showCode(pairing) {
        clearCode();
        const value = pairing || await read('pairing');
        code.value = JSON.stringify(value);
        view.hidden = false;
        try {
            const response = await fetch('/api/companion/qr', {cache: 'no-store'});
            if (!response.ok) throw new Error('QR unavailable');
            imageURL = URL.createObjectURL(await response.blob());
            qr.src = imageURL;
            qr.hidden = false;
            describe('Pairing is ready. Scan the QR code with the companion app.');
        } catch {
            manual.open = true;
            describe('The QR image could not be displayed. You can copy the pairing code below.');
        }
    }

    async function readNetworks() {
        const chosen = host.value;
        const data = await read('addresses');
        const options = data.addresses.map(item => {
            const option = document.createElement('option');
            option.value = item.address;
            option.textContent = `${item.address} (${item.interface})`;
            return option;
        });
        host.replaceChildren(...options);
        if (options.some(option => option.value === chosen)) host.value = chosen;
    }

    function renderDevices(items) {
        const displayed = items.map(({id, name, address, cores, online, mode, assessment}) => ({id, name, address, cores, online, mode, assessment}));
        const snapshot = JSON.stringify(displayed);
        if (snapshot === deviceSnapshot) return;
        deviceSnapshot = snapshot;
        const expanded = new Set([...devices.querySelectorAll('details[open]')].map(row => row.dataset.device));
        const list = document.createElement('ul');
        for (const item of displayed) {
            const row = document.createElement('li');
            const connection = item.online ? 'Connected' : 'Offline';
            const mode = item.mode === 'worker' ? 'Voice EQ enabled' : 'Audio transfer';
            const detail = document.createElement('details');
            detail.dataset.device = item.id;
            detail.open = expanded.has(item.id);
            const heading = document.createElement('summary');
            heading.textContent = [item.name, connection, mode].join(' · ');
            detail.append(heading);
            const assessment = item.assessment || {};
            const metrics = [
                [assessment.model, assessment.os].filter(Boolean).join(' · '),
                item.address,
                item.cores ? `${item.cores} logical cores` : '',
                assessment.ram_bytes ? `${(assessment.ram_bytes / 1073741824).toFixed(1)} GiB memory` : '',
                assessment.battery_percent != null ? `${assessment.battery_percent}% battery${assessment.charging ? ' · charging' : ''}` : '',
                assessment.thermal ? `Thermal state: ${assessment.thermal}` : '',
                item.online && assessment.round_trip_ms != null ? `${assessment.round_trip_ms} ms last round trip` : '',
                assessment.voice_eq_ms ? `${assessment.voice_eq_ms.toFixed(1)} ms for 2 seconds of local Voice EQ` : '',
            ];
            for (const metric of metrics.filter(Boolean)) {
                const line = document.createElement('p');
                line.textContent = metric;
                detail.append(line);
            }
            row.append(detail);
            list.append(row);
        }
        devices.replaceChildren(...(displayed.length ? [list] : []));
    }

    const transferStates = {
        importing: 'Receiving audio',
        imported: 'Source ready',
        queued: 'Waiting for processing',
        processing: 'Processing on this Mac',
        completed: 'Processed result ready',
        failed: 'Processing failed',
    };

    function renderTransfers(items) {
        const snapshot = JSON.stringify(items);
        if (snapshot === transferSnapshot) return;
        transferSnapshot = snapshot;
        const list = document.createElement('ul');
        for (const item of items) {
            const row = document.createElement('li');
            const description = document.createElement('p');
            const parts = [item.device, transferStates[item.status] || item.status];
            if (item.revision) parts.push(`Revision ${item.revision.slice(0, 8)}`);
            if (item.message) parts.push(item.message);
            description.textContent = parts.join(' · ');
            row.append(description);
            if (item.id) {
                const button = document.createElement('button');
                button.type = 'button';
                button.className = 'btn btn-sm btn-secondary';
                button.textContent = 'Open source in Studio';
                button.addEventListener('click', async () => {
                    button.disabled = true;
                    try {
                        const info = await read(`imports/${encodeURIComponent(item.id)}`);
                        if (openCompanionImport(info)) describe('Mobile source opened in Studio.');
                    } catch (error) {
                        describe(error.message);
                    } finally {
                        button.disabled = false;
                    }
                });
                row.append(button);
            }
            if (item.revision && item.sha256) {
                const base = `/api/companion/imports/${encodeURIComponent(item.id)}`;
                const query = new URLSearchParams({revision: item.revision});
                for (const [kind, label] of [['audio', 'Download result'], ['report', 'Download report']]) {
                    const download = document.createElement('a');
                    download.className = 'btn btn-sm btn-secondary';
                    download.textContent = label;
                    download.href = `${base}/${kind}?${query}`;
                    row.append(download);
                }
            }
            list.append(row);
        }
        transfers.replaceChildren(list);
        transferSection.hidden = !items.length;
    }

    function renderSession(data) {
        if (!data.active) clearCode();
        const connected = (data.devices || []).filter(item => item.online).length;
        renderDevices(data.devices || []);
        renderTransfers(data.transfers || []);
        active = data.active;
        if (active && view.hidden) {
            describe(connected ? `${connected} device${connected === 1 ? '' : 's'} connected.` : 'Pairing session is open. Connect from your phone.');
        } else if (!active && data.reason === 'network_changed') {
            describe('The shared network changed. Refresh networks, then start a new pairing session.');
        } else if (!active && !host.value) {
            describe('Connect this Mac to Wi-Fi or a hotspot, then refresh networks.');
        }
    }

    async function refreshSession() {
        if (busy || refreshInFlight || root.closest('.panel[hidden]') || !root.isConnected) return;
        if (root.closest('.panel')?.classList.contains('active') === false) return;
        refreshInFlight = true;
        const version = sessionVersion;
        try {
            const data = await read('session');
            if (sessionVersion === version) renderSession(data);
        } catch (error) {
            if (sessionVersion === version) describe(error.message);
        } finally {
            refreshInFlight = false;
            controls();
        }
    }

    function run(task) {
        if (busy) return;
        busy = true;
        sessionVersion++;
        controls();
        task().catch(error => describe(error.message)).finally(() => {
            busy = false;
            controls();
        });
    }

    action('refresh').addEventListener('click', () => run(async () => {
        await readNetworks();
        describe(host.value ? 'Network ready. Start pairing when you’re ready to connect.' : 'No suitable shared network is available.');
    }));
    action('start').addEventListener('click', () => run(async () => {
        if (!host.value) return;
        const data = await read('start', {host: host.value});
        active = data.active;
        await showCode(data.pairing);
    }));
    action('show').addEventListener('click', () => run(() => showCode()));
    action('hide').addEventListener('click', () => {
        clearCode();
        controls();
    });
    action('stop').addEventListener('click', () => run(async () => {
        await read('stop', {});
        renderSession({active: false});
        describe('Session stopped. Its pairing code no longer grants access.');
    }));
    action('copy').addEventListener('click', async () => {
        try {
            await navigator.clipboard.writeText(code.value);
            describe('Pairing code copied to the clipboard.');
        } catch {
            code.focus();
            code.select();
            describe('Copy the selected code into your companion app.');
        }
    });
    host.addEventListener('change', controls);

    (async () => {
        try {
            const data = await read('session');
            await readNetworks();
            renderSession(data);
            if (!data.active && host.value && !data.reason) describe('Pairing is off. Select the network shared by your phone.');
        } catch (error) {
            describe(error.message);
        } finally {
            busy = false;
            controls();
        }
    })();

    const monitor = setInterval(refreshSession, 2500);
    window.addEventListener('pagehide', () => {
        clearInterval(monitor);
        clearCode();
    });
})();
