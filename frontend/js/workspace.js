(() => {
    const byId = (id) => document.getElementById(id);
    const stageButtons = [...document.querySelectorAll('[data-workspace-stage]')];
    const views = [...document.querySelectorAll('[data-workspace-view]')];
    const scrubber = byId('signal-position');
    const playButton = byId('btn-play');
    const levelMatch = byId('signal-level-match');
    const tracks = {};
    const recentKey = 'aemax-studio-recent';
    const previewPlayer = byId('cleanup-preview-player');
    const speechPlayer = byId('speech-editor-preview');
    let stage = 'clean';
    let timeline = null;
    let selectedWord = null;
    let latestSourceRequest = 0;
    let preview = null;
    let previewRequest = null;
    let previewUrl = null;

    function currentTrack(kind = state.currentWaveform) {
        const track = tracks[kind];
        const current = kind === 'processed' ? state.wavesurferProcessed : state.wavesurferOriginal;
        return track?.wave === current && track.ready ? track : null;
    }

    function selectStage(next, focusHeading = false) {
        if (!['clean', 'review', 'export'].includes(next)) return;
        if (next === 'export' && (!state.hasProcessed || state.isProcessing)) return;
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
        byId('studio-welcome').hidden = hasSource;
        byId('studio-session').hidden = !hasSource;
        byId('session-revision').textContent = hasRevision ? `Revision ${state.processedRevision.slice(0, 8)}` : 'Original';
        byId('review-go-export').disabled = !hasRevision || state.isProcessing;
        byId('studio-blind-ab').hidden = !hasRevision || state.isProcessing;
        stageButtons.forEach((button) => {
            const target = button.dataset.workspaceStage;
            button.disabled = target === 'export' && (!hasRevision || state.isProcessing);
            if (target === stage) button.setAttribute('aria-current', 'step');
            else button.removeAttribute('aria-current');
        });
        views.forEach((view) => { view.hidden = view.dataset.workspaceView !== stage; });
        const verifier = byId('credentials-inspector');
        byId('studio-verify-credentials').hidden = verifier.hidden;
        renderRecent();
        applyListeningLevels();
        refreshTransport();
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

    function readRecent() {
        try {
            const stored = JSON.parse(localStorage.getItem(recentKey) || '[]');
            return Array.isArray(stored) ? stored.slice(0, 6).filter(item =>
                /^[a-z0-9-]{1,80}$/i.test(item?.file_id || '') &&
                typeof item.filename === 'string' && typeof item.format === 'string' &&
                [item.duration_seconds, item.sample_rate, item.size_bytes].every(Number.isFinite)
            ) : [];
        } catch {
            return [];
        }
    }

    function writeRecent(items) {
        try { localStorage.setItem(recentKey, JSON.stringify(items.slice(0, 6))); }
        catch { /* Storage access is optional. */ }
        renderRecent();
    }

    function renderRecent() {
        const files = readRecent();
        const list = byId('studio-recent-files');
        list.replaceChildren();
        byId('studio-recent').hidden = Boolean(state.fileId) || files.length === 0;
        if (byId('studio-recent').hidden) return;
        for (const entry of files) {
            const item = document.createElement('li');
            const button = document.createElement('button');
            button.type = 'button';
            button.title = entry.filename;
            button.textContent = entry.filename;
            button.addEventListener('click', () => openRecent(entry));
            item.append(button);
            list.append(item);
        }
    }

    function importStatus(message) {
        const status = byId('studio-import-status');
        status.hidden = !message;
        status.textContent = message;
    }

    async function openRecent(entry) {
        if (state.isProcessing) return;
        const request = ++latestSourceRequest;
        const previousResultRequest = state.resultRequestId;
        const url = `/api/audio/${encodeURIComponent(entry.file_id)}`;
        importStatus('Checking local source…');
        try {
            const response = await fetch(url, {cache: 'no-store', headers: {Range: 'bytes=0-0'}});
            await response.body?.cancel();
            if (request !== latestSourceRequest || previousResultRequest !== state.resultRequestId) return;
            if (response.status === 404) {
                writeRecent(readRecent().filter(item => item.file_id !== entry.file_id));
                throw new Error('This source was removed from local storage. Open the original file again.');
            }
            if (!response.ok) throw new Error('The local source could not be opened.');
            openCompanionImport({...entry, audio_url: url});
        } catch (error) {
            if (request === latestSourceRequest) importStatus(error.message);
        }
    }

    async function openSample() {
        const request = ++latestSourceRequest;
        const previousResultRequest = state.resultRequestId;
        const button = byId('open-workspace-sample');
        button.disabled = true;
        importStatus('Opening sample…');
        try {
            const response = await fetch('/static/media/studio-sample.wav');
            if (!response.ok) throw new Error('The bundled sample could not be opened.');
            const content = await response.blob();
            if (request === latestSourceRequest && previousResultRequest === state.resultRequestId) {
                await uploadFile(new File([content], 'Signal study.wav', {type: 'audio/wav'}));
            }
        } catch (error) {
            if (request === latestSourceRequest) importStatus(error.message);
        } finally {
            button.disabled = false;
            if (byId('studio-import-status').textContent === 'Opening sample…') importStatus('');
        }
    }

    function showSourceAnalysis(data) {
        const target = byId('studio-source-analysis');
        target.replaceChildren();
        if (data) {
            const intro = document.createElement('strong');
            const description = document.createElement('p');
            const profile = data.profiles?.[data.selected_profile];
            intro.textContent = profile?.name ? `Suggested profile · ${profile.name}` : 'Source analysis';
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
        action.textContent = data ? 'Apply suggested settings' : 'Analyze source';
        action.addEventListener('click', data ? applySmartPreset : () => analyzeSource(true));
        target.append(action);
    }

    async function analyzeSource(showProgress) {
        const requestedFile = state.fileId;
        const target = byId('studio-source-analysis');
        target.textContent = 'Analyzing the source on this Mac…';
        const analysis = await runSmartMode(null, {quiet: !showProgress});
        if (!analysis && requestedFile === state.fileId) showSourceAnalysis();
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
        latestSourceRequest++;
        timeline = null;
        clearSpeechAnalysis();
        importStatus('');
        resetPreview();
        speechPlayer.pause();
        speechPlayer.removeAttribute('src');
        speechPlayer.load();
        state.transcriptSelection = [];
        byId('speech-editor-results').style.display = 'none';
        const {file_id, filename, size_bytes, duration_seconds, sample_rate, format} = data;
        if (filename !== 'Signal study.wav') {
            writeRecent([{file_id, filename, size_bytes, duration_seconds, sample_rate, format},
                ...readRecent().filter(item => item.file_id !== file_id)]);
        }
        showSourceAnalysis();
        if (duration_seconds <= 60) analyzeSource(false);
        selectStage('clean');
        stageButtons[0].focus({preventScroll: true});
    }

    function sourceClosed() {
        latestSourceRequest++;
        tracks.original = null;
        tracks.processed = null;
        timeline = null;
        clearSpeechAnalysis();
        resetPreview();
        selectStage('clean');
        byId('upload-zone').focus({preventScroll: true});
    }

    function resultOpened(result) {
        timeline = {revision: result.revision, map: result.timeline || null};
        refreshSession();
    }

    const commandDialog = byId('command-search-dialog');
    const search = byId('command-search-input');
    const commandResults = byId('command-search-results');

    function renderCommands() {
        const needle = search.value.trim().toLowerCase();
        const targets = [...document.querySelectorAll('.sidebar-nav-item[data-panel]')];
        commandResults.replaceChildren();
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
        if (event.target === search && event.key === 'Enter') commandResults.firstElementChild?.click();
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
        if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
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
    byId('studio-clear-recent').addEventListener('click', () => writeRecent([]));
    byId('open-workspace-sample').addEventListener('click', openSample);
    byId('preview-cleanup').addEventListener('click', beginPreview);
    document.querySelectorAll('[data-preview-variant]').forEach(button =>
        button.addEventListener('click', () => showPreview(button.dataset.previewVariant)));
    levelMatch.addEventListener('change', applyListeningLevels);
    scrubber.addEventListener('input', () => currentTrack()?.wave.setTime(Number(scrubber.value)));
    previewPlayer.addEventListener('play', () => { currentTrack()?.wave.pause(); speechPlayer.pause(); });
    speechPlayer.addEventListener('play', () => { currentTrack()?.wave.pause(); previewPlayer.pause(); });
    byId('download-current-format').addEventListener('click', () => downloadFile(byId('compliance-format').value));
    byId('studio-verify-credentials').addEventListener('click', () => {
        const verifier = byId('credentials-inspector');
        if (verifier.hidden) return;
        verifier.open = true;
        verifier.querySelector('summary').focus();
    });

    const credentialObserver = new MutationObserver(() => {
        byId('studio-verify-credentials').hidden = byId('credentials-inspector').hidden;
    });
    credentialObserver.observe(byId('credentials-inspector'), {attributes: true, attributeFilter: ['hidden']});

    window.aemWorkspace = {selectStage, attachWaveform, refreshTransport, refreshSession, sourceOpened, sourceClosed, resultOpened, showSourceAnalysis, seekTranscriptWord};
    refreshSession();
})();
