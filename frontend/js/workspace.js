(() => {
    const byId = (id) => document.getElementById(id);
    const stageButtons = [...document.querySelectorAll('[data-workspace-stage]')];
    const views = [...document.querySelectorAll('[data-workspace-view]')];
    const scrubber = byId('signal-position');
    const playButton = byId('btn-play');
    const levelMatch = byId('signal-level-match');
    const tracks = {};
    const previewPlayer = byId('cleanup-preview-player');
    const speechPlayer = byId('speech-editor-preview');
    const presetSelect = byId('workspace-preset-select');
    const historyPanel = byId('workspace-history');
    const historyButton = byId('workspace-history-button');
    const historyOlder = byId('workspace-history-older');
    let stage = 'clean';
    let timeline = null;
    let selectedWord = null;
    let preview = null;
    let previewRequest = null;
    let previewUrl = null;
    let choosingManual = false;
    let historyRequest = null;
    let historyBefore = null;

    function currentTrack(kind = state.currentWaveform) {
        const track = tracks[kind];
        const current = kind === 'processed' ? state.wavesurferProcessed : state.wavesurferOriginal;
        return track?.wave === current && track.ready ? track : null;
    }

    function selectStage(next, focusHeading = false) {
        if (!['clean', 'review', 'export'].includes(next)) return;
        if (next === 'export' && (!state.hasProcessed || state.isProcessing || state.isImporting)) return;
        if (next === 'review' && !state.fileId) return;
        if (next !== 'review' && state.blindAB?.status === 'open') {
            stopPlayback();
            state.blindAB = null;
            state.abMode = false;
            byId('waveform-container').classList.remove('blind-review-active');
            byId('waveform-container').querySelector('.waveform-label').textContent = 'Signal';
            resetBlindABControls();
        }
        if (next !== stage) {
            previewPlayer.pause();
            speechPlayer.pause();
        }
        stage = next;
        refreshSession();
        if (focusHeading) {
            const heading = document.querySelector(`.studio-inspector [data-workspace-view="${stage}"] h2`);
            heading?.setAttribute('tabindex', '-1');
            heading?.focus({preventScroll: true});
        }
    }

    function refreshSession() {
        const hasSource = Boolean(state.fileId);
        const hasRevision = Boolean(state.hasProcessed && state.processedRevision);
        const busy = state.isProcessing || state.isImporting;
        byId('studio-welcome').hidden = hasSource;
        byId('studio-session').hidden = !hasSource;
        byId('session-revision').textContent = hasRevision ? `Revision ${state.processedRevision.slice(0, 8)}` : 'Original';
        byId('open-another-source').disabled = busy;
        byId('close-studio-source').disabled = busy;
        byId('upload-zone').disabled = busy;
        byId('go-to-rendered-export').hidden = !hasRevision;
        byId('go-to-rendered-export').disabled = busy;
        byId('download-original-audio').disabled = busy;
        byId('review-go-export').disabled = !hasRevision || busy;
        byId('studio-blind-ab').hidden = !hasRevision || busy;
        stageButtons.forEach((button) => {
            const target = button.dataset.workspaceStage;
            button.disabled = target === 'export' && (!hasRevision || busy);
            if (target === stage) button.setAttribute('aria-current', 'step');
            else button.removeAttribute('aria-current');
        });
        views.forEach((view) => { view.hidden = view.dataset.workspaceView !== stage; });
        const verifier = byId('credentials-inspector');
        byId('studio-verify-credentials').hidden = verifier.hidden;
        refreshRecipe();
        refreshRunStatus();
        applyListeningLevels();
        refreshTransport();
    }

    function refreshPresets() {
        const items = [new Option('Choose a preset', ''), new Option('Set processing controls manually', 'custom')];
        for (const preset of state.workspacePresets) {
            items.push(new Option(preset.name, `preset:${preset.id}`));
        }
        presetSelect.replaceChildren(...items);
        refreshRecipe();
    }

    function refreshRecipe() {
        const selected = workspaceSelectedRecipe();
        const preset = state.workspacePreset;
        const rendered = state.renderedRecipe;
        presetSelect.disabled = state.isImporting || state.isProcessing;
        if (preset && state.workspacePresets.some(item => item.id === preset.id)) {
            presetSelect.value = `preset:${preset.id}`;
        } else {
            presetSelect.value = choosingManual || selected.label === 'Custom settings' ? 'custom' : '';
        }
        const description = preset?.description.trim();
        byId('workspace-preset-description').textContent = [
            description && (/[.!?]$/.test(description) ? description : `${description}.`),
            'Choose Process audio to render the selected settings.',
        ].filter(Boolean).join(' ');
        byId('workspace-selected-recipe').textContent = selected.label;
        byId('workspace-rendered-recipe').textContent = rendered && rendered.revision === state.processedRevision
            ? `${rendered.label} · ${rendered.revision.slice(0, 8)}`
            : 'None · original available';
    }

    function refreshRunStatus() {
        const status = byId('workspace-run-status');
        const run = state.workspaceRun;
        const phase = state.isImporting ? 'importing' : run.phase;
        const messages = {
            ready: 'Original ready. Select settings or open the speech editor.',
            importing: 'Importing the original file…',
            running: `Rendering with ${run.label || 'the selected settings'}…`,
            completed: 'Revision ready. Listen to the result or open export.',
            failed: 'Processing failed. The original is still available. Check your settings and try again.',
            interrupted: 'The processing connection was interrupted. Check processing status before retrying.',
        };
        const text = [messages[phase], !state.isImporting && run.message].filter(Boolean).join(' ');
        if (status.textContent !== text) status.textContent = text;
        status.dataset.phase = phase;
    }

    function closeHistory() {
        historyRequest?.abort();
        historyRequest = null;
        historyBefore = null;
        historyButton.setAttribute('aria-expanded', 'false');
        historyPanel.hidden = true;
        byId('workspace-history-events').replaceChildren();
        byId('workspace-history-status').textContent = '';
        historyOlder.hidden = true;
    }

    const historyLabels = {
        source_imported: 'Original imported',
        analysis_completed: 'Original analyzed',
        preview_generated: 'Cleanup preview prepared',
        speech_analysis_completed: 'Transcript analyzed',
        processing_started: 'Processing started',
        revision_rendered: 'Revision rendered',
        processing_failed: 'Processing reported an error',
        export_prepared: 'Download prepared',
        signed_export_prepared: 'Signed copy prepared',
    };

    function showHistoryEvent(event, list) {
        const item = document.createElement('li');
        const title = document.createElement('strong');
        const timestamp = document.createElement('time');
        const details = event.details || {};
        const date = new Date(event.occurred_at);
        title.textContent = historyLabels[event.action] || 'Workspace action';
        if (Number.isFinite(date.getTime())) {
            timestamp.dateTime = date.toISOString();
            timestamp.textContent = date.toLocaleString();
        }
        item.append(title, timestamp);
        const parts = [
            event.revision && `Revision ${event.revision.slice(0, 8)}`,
            details.mode && String(details.mode).replaceAll('_', ' '),
            details.format && String(details.format).toUpperCase(),
            Array.isArray(details.executed_steps) && details.executed_steps.length
                ? `Executed ${details.executed_steps.join(', ').replaceAll('_', ' ')}` : null,
            Array.isArray(details.changed_steps)
                ? (details.changed_steps.length
                    ? `Changed audio ${details.changed_steps.join(', ').replaceAll('_', ' ')}`
                    : 'No signal change recorded')
                : null,
        ].filter(Boolean);
        if (parts.length) {
            const line = document.createElement('p');
            line.textContent = parts.join(' · ');
            item.append(line);
        }
        const reportHash = details.report_sha256 || details.processing_report_sha256;
        if (typeof reportHash === 'string' && /^[a-f0-9]{64}$/i.test(reportHash)) {
            const row = document.createElement('p');
            const code = document.createElement('code');
            code.textContent = reportHash;
            row.append('Report SHA-256 ', code);
            item.append(row);
        }
        list.append(item);
    }

    async function loadHistory(older = false) {
        if (!state.fileId || historyPanel.hidden || older && !historyBefore) return;
        historyRequest?.abort();
        const request = historyRequest = new AbortController();
        const {fileId, sourceRequestId} = state;
        const list = byId('workspace-history-events');
        const status = byId('workspace-history-status');
        const query = new URLSearchParams({limit: '12'});
        if (older) query.set('before', historyBefore);
        status.textContent = 'Loading actions for the current source…';
        historyOlder.disabled = true;
        try {
            const response = await fetch(`/api/workspace/${encodeURIComponent(fileId)}/history?${query}`, {
                signal: request.signal, cache: 'no-store',
            });
            if (!response.ok) throw new Error('Actions history is unavailable. Try refreshing.');
            const data = await response.json();
            if (request !== historyRequest || fileId !== state.fileId || sourceRequestId !== state.sourceRequestId) return;
            if (!older) list.replaceChildren();
            for (const event of data.events || []) showHistoryEvent(event, list);
            historyBefore = data.next_before || null;
            historyOlder.hidden = !historyBefore;
            status.textContent = list.childElementCount ? '' : 'No recorded actions for this source.';
        } catch (error) {
            if (request === historyRequest && fileId === state.fileId && sourceRequestId === state.sourceRequestId) {
                status.textContent = error.message;
            }
        } finally {
            if (historyRequest === request) {
                historyRequest = null;
                historyOlder.disabled = false;
            }
        }
    }

    function refreshHistory({followDownload = false} = {}) {
        if (historyPanel.hidden) return;
        if (!followDownload) {
            loadHistory();
            return;
        }
        const {fileId, sourceRequestId} = state;
        setTimeout(() => {
            if (fileId === state.fileId && sourceRequestId === state.sourceRequestId) loadHistory();
        }, 450);
    }

    // A source point inside a cut maps to its join. During a crossfade, use
    // the louder side as the anchor and preserve exact offsets outside it.
    function alignTime(seconds, fromKind) {
        if (!timeline || timeline.revision !== state.processedRevision) return null;
        const original = currentTrack('original');
        const processed = currentTrack('processed');
        if (!original || !processed) return null;
        const durationOriginal = original.wave.getDuration();
        const durationProcessed = processed.wave.getDuration();
        if (!timeline.map) return Math.abs(durationOriginal - durationProcessed) < 0.06 ? seconds : null;

        const {sample_rate: sampleRate, source_samples: sourceCount, output_samples: outputCount, cuts} = timeline.map;
        // The players may use different decode rates, but their durations
        // must correspond to the two files this render map describes.
        if (Math.abs(durationOriginal - sourceCount / sampleRate) >= 0.06 ||
                Math.abs(durationProcessed - outputCount / sampleRate) >= 0.06) return null;
        let frame = seconds * sampleRate;
        if (fromKind === 'original') {
            for (const [start, stop, fade] of cuts) {
                const split = Math.floor(fade / 2);
                const join = start - fade + split;
                if (frame >= stop + split) frame -= stop - start + fade;
                else if (frame >= join) frame = join;
            }
        } else {
            for (let i = cuts.length - 1; i >= 0; i--) {
                const [start, stop, fade] = cuts[i];
                if (frame >= start - Math.ceil(fade / 2)) frame += stop - start + fade;
            }
        }
        return frame / sampleRate;
    }

    function estimateRms(buffer) {
        if (!buffer?.length) return 0;
        const stride = Math.max(1, Math.ceil(buffer.length / 150000));
        let energy = 0;
        let frames = 0;
        for (let channel = 0; channel < buffer.numberOfChannels; channel++) {
            const samples = buffer.getChannelData(channel);
            for (let i = 0; i < samples.length; i += stride) {
                energy += samples[i] ** 2;
                frames++;
            }
        }
        return Math.sqrt(energy / frames);
    }

    function applyListeningLevels() {
        const original = currentTrack('original');
        const processed = currentTrack('processed');
        const canMatch = original?.rms > 0.00056 && processed?.rms > 0.00056;
        levelMatch.disabled = !canMatch;
        const match = canMatch && levelMatch.checked;
        const target = match ? Math.min(original.rms, processed.rms) : 1;
        for (const track of [original, processed]) {
            if (track) track.wave.setVolume(match ? target / track.rms : 1);
        }
    }

    function refreshTransport() {
        const active = currentTrack()?.wave;
        const isPlaying = active?.isPlaying() === true;
        const duration = active?.getDuration() || 0;
        const now = active?.getCurrentTime() || 0;
        const time = formatDuration(now);
        if (Number(scrubber.max) !== duration) scrubber.max = duration;
        if (Number(scrubber.value) !== now) scrubber.value = now;
        scrubber.disabled = !duration;
        if (scrubber.getAttribute('aria-valuetext') !== time) scrubber.setAttribute('aria-valuetext', time);
        playButton.disabled = !active;
        const playLabel = isPlaying ? 'Pause audio' : 'Play audio';
        if (playButton.getAttribute('aria-label') !== playLabel) {
            playButton.setAttribute('aria-label', playLabel);
            playButton.innerHTML = svgIcon(isPlaying ? 'pause' : 'play', 'icon-img control-icon-svg');
        }
        const timeCurrent = byId('time-current');
        if (timeCurrent.textContent !== time) timeCurrent.textContent = time;
        const timeTotal = byId('time-total');
        if (timeTotal.textContent !== formatDuration(duration)) timeTotal.textContent = formatDuration(duration);
        byId('btn-show-processed').disabled = !currentTrack('processed');
        const alignment = byId('signal-alignment');
        const hideAlignment = !currentTrack('processed') || alignTime(0, 'original') !== null;
        if (alignment.hidden !== hideAlignment) {
            alignment.hidden = hideAlignment;
            alignment.textContent = hideAlignment ? '' : 'The revision changed duration. Each version keeps its own playback position.';
        }
        updateTranscriptPlayhead(now);
    }

    function updateTranscriptPlayhead(now) {
        const words = state.speechEdl?.source_words;
        const inSource = state.currentWaveform === 'original' ? now : alignTime(now, 'processed');
        const container = byId('speech-transcript-words');
        let selected = null;
        if (!state.abMode && words?.length && inSource !== null) {
            let lo = 0;
            let hi = words.length;
            while (lo < hi) {
                const mid = Math.floor((lo + hi) / 2);
                if (words[mid].start <= inSource) lo = mid + 1;
                else hi = mid;
            }
            if (lo > 0 && words[lo - 1].end >= inSource) {
                selected = container.querySelector(`[data-word-index="${lo - 1}"]`);
            }
        }
        if (selected === selectedWord) return;
        selectedWord?.classList.remove('is-at-playhead');
        selectedWord = selected;
        selectedWord?.classList.add('is-at-playhead');
    }

    function attachWaveform(kind, wave) {
        const track = tracks[kind] = {wave, rms: 0, ready: false};
        wave.on('ready', () => {
            track.ready = true;
            track.rms = estimateRms(wave.getDecodedData());
            applyListeningLevels();
            refreshTransport();
        });
        wave.on('error', () => {
            if (tracks[kind] !== track) return;
            track.ready = false;
            refreshTransport();
            showToast('error', 'Unable to load this audio for playback');
        });
        wave.on('play', () => {
            previewPlayer.pause();
            speechPlayer.pause();
            refreshTransport();
        });
        for (const event of ['pause', 'finish', 'timeupdate', 'seeking']) {
            wave.on(event, () => {
                if (kind === state.currentWaveform) refreshTransport();
            });
        }
    }

    function switchListeningVersion(kind) {
        const target = currentTrack(kind)?.wave;
        if (!target || state.currentWaveform === kind || state.abMode) return;
        const current = currentTrack()?.wave;
        const playing = current?.isPlaying();
        const aligned = current ? alignTime(current.getCurrentTime(), state.currentWaveform) : null;
        current?.pause();
        showWaveform(kind);
        if (aligned !== null) target.setTime(Math.min(target.getDuration(), aligned));
        if (playing) target.play()?.catch(() => showToast('warning', 'Unable to play this audio'));
    }

    function seekTranscriptWord(index) {
        if (state.abMode) return;
        const word = state.speechEdl?.source_words?.[index];
        if (!word) return;
        let seconds = state.currentWaveform === 'processed' ? alignTime(word.start, 'original') : word.start;
        if (seconds === null) {
            switchListeningVersion('original');
            seconds = word.start;
        }
        currentTrack()?.wave.setTime(seconds);
        updateTranscriptPlayhead(seconds);
    }

    function auditionSelection() {
        if (state.abMode || state.transcriptSelection.length !== 2) return;
        const [first, last] = [...state.transcriptSelection].sort((a, b) => a - b);
        const words = state.speechEdl?.source_words;
        if (!words?.[first] || !words[last]) return;
        let from = words[first].start;
        let to = words[last].end;
        if (state.currentWaveform === 'processed') {
            const alignedStart = alignTime(from, 'original');
            const alignedStop = alignTime(to, 'original');
            if (alignedStart === null || alignedStop - alignedStart < 0.015) {
                switchListeningVersion('original');
            } else {
                from = alignedStart;
                to = alignedStop;
            }
        }
        const wave = currentTrack()?.wave;
        if (!wave) return;
        wave.play(from, Math.min(wave.getDuration(), to))?.catch(() => showToast('warning', 'Unable to play this selection'));
    }

    function showSourceAnalysis(data) {
        const target = byId('studio-source-analysis');
        target.replaceChildren();
        if (data) {
            const intro = document.createElement('strong');
            const description = document.createElement('p');
            const profile = data.profiles?.[data.selected_profile];
            intro.textContent = profile?.name ? `Suggested preset · ${profile.name}` : 'Analysis ready';
            description.textContent = data.description || 'Local signal analysis complete.';
            target.append(intro, description);
            const issues = data.quality?.issues?.slice(0, 3) || [];
            if (issues.length) {
                const findings = document.createElement('ul');
                for (const issue of issues) {
                    const item = document.createElement('li');
                    item.textContent = String(issue.label || 'Signal issue');
                    findings.append(item);
                }
                target.append(findings);
            }
        }
        const action = document.createElement('button');
        action.type = 'button';
        action.className = 'btn btn-sm btn-secondary';
        action.textContent = data ? 'Select suggested settings' : 'Analyze original';
        action.addEventListener('click', data ? applySmartPreset : analyzeSource);
        target.append(action);
    }

    async function analyzeSource() {
        const {fileId, sourceRequestId} = state;
        const target = byId('studio-source-analysis');
        target.textContent = 'Reading the original on this Mac to suggest settings…';
        const analysis = await runSmartMode(null, {quiet: true});
        if (!analysis && fileId === state.fileId && sourceRequestId === state.sourceRequestId) showSourceAnalysis();
        if (analysis && !historyPanel.hidden) loadHistory();
    }

    function resetPreview() {
        previewRequest?.abort();
        previewRequest = null;
        preview = null;
        previewPlayer.pause();
        previewPlayer.removeAttribute('src');
        previewPlayer.load();
        if (previewUrl) URL.revokeObjectURL(previewUrl);
        previewUrl = null;
        for (const id of ['cleanup-preview-player', 'cleanup-preview-status', 'cleanup-preview-choices']) byId(id).hidden = true;
    }

    async function showPreview(variant) {
        if (!preview || preview.fileId !== state.fileId) return;
        previewRequest?.abort();
        const request = previewRequest = new AbortController();
        const {fileId, start, strength} = preview;
        const status = byId('cleanup-preview-status');
        status.textContent = 'Preparing excerpt…';
        status.hidden = false;
        const at = previewPlayer.currentTime || 0;
        const wasPlaying = !previewPlayer.paused;
        try {
            const query = new URLSearchParams({start_seconds: start, variant, strength});
            const response = await fetch(`/api/workspace/${encodeURIComponent(fileId)}/cleanup-preview?${query}`, {
                signal: request.signal, cache: 'no-store',
            });
            if (!response.ok) throw new Error(await readApiError(response, 'The preview could not be prepared.'));
            const data = await response.blob();
            if (request !== previewRequest || fileId !== state.fileId) return;
            previewPlayer.pause();
            if (previewUrl) URL.revokeObjectURL(previewUrl);
            previewUrl = URL.createObjectURL(data);
            previewPlayer.addEventListener('loadedmetadata', () => {
                if (request !== previewRequest) return;
                previewPlayer.currentTime = Math.min(at, previewPlayer.duration);
                if (wasPlaying) previewPlayer.play().catch(() => {});
            }, {once: true});
            previewPlayer.src = previewUrl;
            previewPlayer.hidden = false;
            byId('cleanup-preview-choices').hidden = false;
            status.textContent = `Up to 8 seconds from ${formatDuration(start)} · spectral noise reduction only`;
            document.querySelectorAll('[data-preview-variant]').forEach(button =>
                button.setAttribute('aria-pressed', String(button.dataset.previewVariant === variant)));
        } catch (error) {
            if (request !== previewRequest || error.name === 'AbortError') return;
            status.textContent = error.message;
        }
    }

    function beginPreview() {
        if (!state.fileId) return;
        const wave = currentTrack()?.wave;
        const currentTime = wave?.getCurrentTime() || 0;
        const aligned = state.currentWaveform === 'original' ? currentTime : alignTime(currentTime, 'processed');
        const duration = currentTrack('original')?.wave.getDuration() || state.duration;
        resetPreview();
        preview = {
            fileId: state.fileId,
            start: Math.max(0, Math.min(aligned || 0, duration - 0.05)),
            strength: options.noise_reduction_strength,
        };
        wave?.pause();
        showPreview('spectral');
    }

    function sourceOpened(data) {
        timeline = null;
        clearSpeechAnalysis();
        closeHistory();
        resetPreview();
        speechPlayer.pause();
        speechPlayer.removeAttribute('src');
        speechPlayer.load();
        state.transcriptSelection = [];
        byId('speech-editor-results').style.display = 'none';
        showSourceAnalysis();
        if (data.duration_seconds <= 60) analyzeSource();
        selectStage('clean');
        stageButtons[0].focus({preventScroll: true});
    }

    function sourceClosed() {
        tracks.original = null;
        tracks.processed = null;
        timeline = null;
        clearSpeechAnalysis();
        closeHistory();
        resetPreview();
        selectStage('clean');
        byId('upload-zone').focus({preventScroll: true});
    }

    function resultOpened(result) {
        timeline = {revision: result.revision, map: result.timeline || null};
        refreshSession();
        if (!historyPanel.hidden) loadHistory();
    }

    const commandDialog = byId('command-search-dialog');
    const search = byId('command-search-input');
    const commandResults = byId('command-search-results');

    function renderCommands() {
        const needle = search.value.trim().toLowerCase();
        const targets = [...document.querySelectorAll('#workspace-dock .sidebar-nav-item[data-panel]')];
        const quickCommands = [
            { action: 'verify', label: 'Verify C2PA Content Credentials' },
            { action: 'clean', label: 'Clean up audio' }
        ];
        commandResults.replaceChildren();
        for (const {action, label} of quickCommands) {
            const target = document.querySelector(`[data-dock-action="${action}"]`);
            if (!target || target.hidden || !label.toLowerCase().includes(needle)) continue;
            const button = document.createElement('button');
            button.type = 'button';
            button.textContent = label;
            button.addEventListener('click', () => {
                commandDialog.close();
                target.click();
            });
            commandResults.append(button);
        }
        for (const command of window.aemStudioTimeline?.commands() || []) {
            if (!`${command.label} ${command.keywords || ''}`.toLowerCase().includes(needle)) continue;
            const action = document.createElement('button');
            action.type = 'button';
            action.textContent = command.label;
            action.addEventListener('click', () => {
                commandDialog.close();
                command.run();
            });
            commandResults.append(action);
        }
        for (const target of targets) {
            const label = target.textContent.trim().replace(/\s+/g, ' ');
            if (!label.toLowerCase().includes(needle) || target.hidden || target.style.display === 'none') continue;
            const button = document.createElement('button');
            button.type = 'button';
            button.textContent = label;
            button.addEventListener('click', () => {
                commandDialog.close();
                target.click();
                const main = byId('main-content');
                const focusTarget = main.querySelector('.panel.active h1, .panel.active .card-title') || main;
                focusTarget.setAttribute('tabindex', '-1');
                focusTarget.focus();
            });
            commandResults.append(button);
        }
        byId('command-search-empty').hidden = commandResults.childElementCount > 0;
    }

    function openCommandSearch() {
        if (commandDialog.open) return;
        search.value = '';
        renderCommands();
        commandDialog.showModal();
        search.focus();
    }

    commandDialog.addEventListener('keydown', (event) => {
        if (event.key === 'Escape') {
            event.preventDefault();
            commandDialog.close();
            return;
        }
        if (event.target === search && event.key === 'Enter') {
            event.preventDefault();
            commandResults.firstElementChild?.click();
        }
        if (!['ArrowDown', 'ArrowUp'].includes(event.key)) return;
        const commands = [...commandResults.children];
        const current = commands.indexOf(event.target);
        event.preventDefault();
        const next = event.key === 'ArrowDown' ? commands[current + 1] : commands[current - 1] || search;
        next?.focus();
    });
    search.addEventListener('input', renderCommands);
    byId('command-search-button').addEventListener('click', openCommandSearch);
    document.addEventListener('keydown', (event) => {
        if (event.defaultPrevented || event.isComposing) return;
        const customPalette = window.aemStudioTimeline?.matchesPaletteShortcut(event);
        const defaultPalette = (event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k';
        if ((customPalette ?? defaultPalette) && !document.querySelector('dialog[open]')) {
            if (!(event.metaKey || event.ctrlKey) && event.target.closest?.('input, textarea, select, [contenteditable="true"]')) return;
            event.preventDefault();
            openCommandSearch();
        }
    });

    const transcript = byId('speech-transcript-words');
    transcript.addEventListener('keydown', (event) => {
        const words = [...transcript.querySelectorAll('.speech-word')];
        const at = words.indexOf(event.target);
        const next = {
            ArrowLeft: at - 1, ArrowRight: at + 1, Home: 0, End: words.length - 1,
        }[event.key];
        if (at < 0 || next === undefined || !words[next]) return;
        event.preventDefault();
        words[at].tabIndex = -1;
        words[next].tabIndex = 0;
        words[next].focus();
    });

    document.querySelectorAll('[data-workspace-stage], [data-go-to-stage]').forEach(button =>
        button.addEventListener('click', () => selectStage(button.dataset.workspaceStage || button.dataset.goToStage, !button.dataset.workspaceStage)));
    byId('btn-show-original').addEventListener('click', () => switchListeningVersion('original'));
    byId('btn-show-processed').addEventListener('click', () => switchListeningVersion('processed'));
    byId('btn-audition-range').addEventListener('click', auditionSelection);
    byId('preview-cleanup').addEventListener('click', beginPreview);
    document.querySelectorAll('[data-preview-variant]').forEach(button =>
        button.addEventListener('click', () => showPreview(button.dataset.previewVariant)));
    levelMatch.addEventListener('change', applyListeningLevels);
    scrubber.addEventListener('input', () => currentTrack()?.wave.setTime(Number(scrubber.value)));
    previewPlayer.addEventListener('play', () => { currentTrack()?.wave.pause(); speechPlayer.pause(); });
    speechPlayer.addEventListener('play', () => { currentTrack()?.wave.pause(); previewPlayer.pause(); });
    byId('download-current-format').addEventListener('click', () => downloadFile(byId('compliance-format').value));
    byId('download-original-audio').addEventListener('click', downloadOriginal);
    presetSelect.addEventListener('change', () => {
        choosingManual = presetSelect.value === 'custom';
        if (choosingManual) {
            state.workspacePreset = null;
            document.querySelector('.studio-advanced').open = true;
            refreshRecipe();
            return;
        }
        const wanted = presetSelect.value;
        const preset = state.workspacePresets.find(item => `preset:${item.id}` === wanted);
        if (preset) selectWorkspacePreset(preset);
        else refreshRecipe();
    });
    historyButton.addEventListener('click', () => {
        if (!historyPanel.hidden) {
            closeHistory();
            return;
        }
        historyPanel.hidden = false;
        historyButton.setAttribute('aria-expanded', 'true');
        loadHistory();
    });
    byId('workspace-history-reload').addEventListener('click', () => loadHistory());
    historyOlder.addEventListener('click', () => loadHistory(true));
    const verifier = byId('credentials-inspector');
    const verifierButtons = [byId('home-verify-content'), byId('studio-verify-credentials')];
    let verificationTrigger;
    function openVerifier(trigger = document.activeElement) {
        if (verifier.hidden) return false;
        verificationTrigger = trigger;
        verifier.open = true;
        verifier.querySelector('summary').focus();
        return true;
    }
    for (const button of verifierButtons) {
        button.addEventListener('click', () => openVerifier(button));
    }
    verifier.addEventListener('toggle', () => {
        const expanded = String(verifier.open);
        for (const button of verifierButtons) button.setAttribute('aria-expanded', expanded);
        if (verifier.open || !byId('upload-panel').classList.contains('active')) return;
        const active = document.activeElement;
        if (active !== document.body && !verifier.contains(active)) return;
        const target = [verificationTrigger, ...verifierButtons, byId('upload-zone'), byId('main-content')]
            .find(item => item?.getClientRects().length);
        target?.focus();
    });
    verifier.addEventListener('keydown', event => {
        if (event.key !== 'Escape' || event.defaultPrevented) return;
        event.preventDefault();
        verifier.open = false;
    });

    function syncVerifierButtons() {
        for (const button of verifierButtons) button.hidden = verifier.hidden;
    }
    const credentialObserver = new MutationObserver(syncVerifierButtons);
    credentialObserver.observe(verifier, {attributes: true, attributeFilter: ['hidden']});
    syncVerifierButtons();

    window.aemWorkspace = {selectStage, attachWaveform, refreshTransport, refreshSession, refreshPresets, refreshRecipe, refreshHistory, sourceOpened, sourceClosed, resultOpened, showSourceAnalysis, seekTranscriptWord, openVerifier};
    refreshSession();
})();
