/**
 * AudioEnhancerMAX by Fd — Main Application JavaScript
 * Handles all UI interactions, API calls, and state management.
 */

// ══════════════════════════════════════════════════════════
// State
// ══════════════════════════════════════════════════════════

const state = {
    fileId: null,
    fileName: null,
    duration: 0,
    sampleRate: 0,
    isProcessing: false,
    hasProcessed: false,
    processedUrl: null,
    cloneVoiceFileId: null,
    batchFiles: [],
    smartSuggestions: null,
    wsConnection: null,
    wavesurferOriginal: null,
    wavesurferProcessed: null,
    currentWaveform: 'original',
    abMode: false,
};

const options = {
    remove_noise: false,
    noise_reduction_strength: 0.7,
    remove_long_silences: false,
    silence_threshold_db: -40,
    min_silence_duration_ms: 1000,
    mute_segments: false,
    remove_mouth_sounds: false,
    mouth_sound_sensitivity: 0.5,
    eliminate_hesitations: false,
    remove_stuttering: false,
    remove_filler_words: false,
    custom_filler_words: null,
    remove_breaths: false,
    breath_reduction_strength: 0.8,
    studio_sound: false,
    auto_eq: false,
    normalize: false,
    target_loudness_lufs: -16.0,
    keep_music: false,
    wind_noise_remover: false,
    buzzing_noise_remover: false,
    buzz_frequency_hz: 50,
    static_noise_remover: false,
    reverb_echo_remover: false,
    frequency_restoration: false,
    target_sample_rate: 48000,
    smart_mode: false,
    output_format: 'wav',
};

// ══════════════════════════════════════════════════════════
// Initialization
// ══════════════════════════════════════════════════════════

document.addEventListener('DOMContentLoaded', () => {
    initUploadZone();
    initBatchUpload();
    checkSystemHealth();
    loadPresets();
    initSettingsPanel();
    initAboutPanel();
});

async function checkSystemHealth() {
    try {
        const res = await fetch('/api/health');
        const data = await res.json();

        // Update compute label
        document.getElementById('compute-label').textContent = data.compute || 'CPU';

        // Update Gemma status
        const dot = document.getElementById('gemma-dot');
        const label = document.getElementById('gemma-label');

        const ollamaStatus = data.ollama_status || data.gemma4_status;
        const ollamaModel = data.ollama_model || data.gemma_model;

        if (ollamaStatus === 'available') {
            dot.className = 'status-dot';
            const modelName = ollamaModel || 'Ollama/Gemma';
            label.textContent = modelName + ' ✓';
        } else if (ollamaStatus === 'not_running') {
            dot.className = 'status-dot warning';
            label.textContent = 'Ollama/Gemma — Start Ollama';
        } else {
            dot.className = 'status-dot error';
            label.textContent = 'Ollama/Gemma — Unavailable';
        }
    } catch (e) {
        document.getElementById('gemma-dot').className = 'status-dot error';
        document.getElementById('gemma-label').textContent = 'Backend offline';
    }
}

// ══════════════════════════════════════════════════════════
// Navigation
// ══════════════════════════════════════════════════════════

function switchPanel(panelId, navItem) {
    document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
    document.querySelectorAll('.sidebar-nav-item').forEach(n => n.classList.remove('active'));

    document.getElementById(panelId).classList.add('active');
    if (navItem) navItem.classList.add('active');
}

function switchTab(tabId, tabBtn) {
    // Find parent card
    const parent = tabBtn.closest('.card');
    parent.querySelectorAll('.tab-content').forEach(tc => tc.classList.remove('active'));
    parent.querySelectorAll('.tab-btn').forEach(tb => tb.classList.remove('active'));

    document.getElementById(tabId).classList.add('active');
    tabBtn.classList.add('active');
}

// ══════════════════════════════════════════════════════════
// File Upload
// ══════════════════════════════════════════════════════════

function initUploadZone() {
    const zone = document.getElementById('upload-zone');
    const input = document.getElementById('file-input');

    zone.addEventListener('click', () => input.click());

    zone.addEventListener('dragover', (e) => {
        e.preventDefault();
        zone.classList.add('drag-over');
    });

    zone.addEventListener('dragleave', () => {
        zone.classList.remove('drag-over');
    });

    zone.addEventListener('drop', (e) => {
        e.preventDefault();
        zone.classList.remove('drag-over');
        if (e.dataTransfer.files.length > 0) {
            uploadFile(e.dataTransfer.files[0]);
        }
    });

    input.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            uploadFile(e.target.files[0]);
        }
    });
}

async function uploadFile(file) {
    showLoading('Uploading ' + file.name + '...');

    const formData = new FormData();
    formData.append('file', file);

    try {
        const res = await fetch('/api/upload', { method: 'POST', body: formData });
        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || 'Upload failed');
        }

        const data = await res.json();
        state.fileId = data.file_id;
        state.fileName = data.filename;
        state.duration = data.duration_seconds;
        state.sampleRate = data.sample_rate;

        // Update UI
        document.getElementById('file-info-bar').classList.add('visible');
        document.getElementById('file-name').textContent = data.filename;
        document.getElementById('file-duration').textContent = formatDuration(data.duration_seconds);
        document.getElementById('file-samplerate').textContent = data.sample_rate + ' Hz';
        document.getElementById('file-format').textContent = data.format.toUpperCase();
        document.getElementById('file-size').textContent = formatFileSize(data.size_bytes);

        // Show waveform
        initWaveform(data.audio_url);

        // Enable buttons
        document.getElementById('btn-process').disabled = false;
        document.getElementById('btn-transcribe').disabled = false;
        document.getElementById('btn-diarize').disabled = false;
        document.getElementById('btn-smart-analyze').disabled = false;
        document.getElementById('btn-watermark').disabled = false;
        document.getElementById('btn-detect-watermark').disabled = false;

        // Hide "upload first" notices
        document.querySelectorAll('.requires-file-notice').forEach(el => el.style.display = 'none');

        // Hide upload zone
        document.getElementById('upload-zone').style.display = 'none';

        hideLoading();
        showToast('success', `"${data.filename}" uploaded successfully`);

    } catch (e) {
        hideLoading();
        showToast('error', e.message);
    }
}

function removeFile() {
    state.fileId = null;
    state.fileName = null;
    state.hasProcessed = false;
    state.processedUrl = null;

    // Destroy waveforms
    if (state.wavesurferOriginal) {
        state.wavesurferOriginal.destroy();
        state.wavesurferOriginal = null;
    }
    if (state.wavesurferProcessed) {
        state.wavesurferProcessed.destroy();
        state.wavesurferProcessed = null;
    }

    document.getElementById('file-info-bar').classList.remove('visible');
    document.getElementById('waveform-container').classList.remove('visible');
    document.getElementById('upload-zone').style.display = '';
    document.getElementById('download-bar').classList.remove('visible');
    document.getElementById('smart-mode-banner').classList.remove('visible');

    // Disable buttons
    document.getElementById('btn-process').disabled = true;
    document.getElementById('btn-transcribe').disabled = true;
    document.getElementById('btn-diarize').disabled = true;
    document.getElementById('btn-smart-analyze').disabled = true;
    document.getElementById('btn-watermark').disabled = true;
    document.getElementById('btn-detect-watermark').disabled = true;

    // Show "upload first" notices again
    document.querySelectorAll('.requires-file-notice').forEach(el => el.style.display = '');
}

// ══════════════════════════════════════════════════════════
// Waveform (WaveSurfer.js)
// ══════════════════════════════════════════════════════════

async function initWaveform(audioUrl) {
    const container = document.getElementById('waveform-container');
    container.classList.add('visible');

    // Dynamic import for WaveSurfer ESM
    const WaveSurfer = (await import('https://unpkg.com/wavesurfer.js@7/dist/wavesurfer.esm.js')).default;

    // Destroy existing
    if (state.wavesurferOriginal) state.wavesurferOriginal.destroy();

    state.wavesurferOriginal = WaveSurfer.create({
        container: '#waveform-original',
        waveColor: 'rgba(124, 58, 237, 0.4)',
        progressColor: '#7c3aed',
        cursorColor: '#a855f7',
        barWidth: 2,
        barGap: 1,
        barRadius: 2,
        height: 100,
        normalize: true,
        url: audioUrl,
        backend: 'WebAudio',
    });

    state.wavesurferOriginal.on('timeupdate', (time) => {
        document.getElementById('time-current').textContent = formatDuration(time);
    });

    state.wavesurferOriginal.on('ready', () => {
        const dur = state.wavesurferOriginal.getDuration();
        document.getElementById('time-total').textContent = formatDuration(dur);
    });

    state.wavesurferOriginal.on('play', () => {
        document.getElementById('btn-play').textContent = '⏸';
    });

    state.wavesurferOriginal.on('pause', () => {
        document.getElementById('btn-play').textContent = '▶';
    });
}

async function initProcessedWaveform(audioUrl) {
    const WaveSurfer = (await import('https://unpkg.com/wavesurfer.js@7/dist/wavesurfer.esm.js')).default;

    if (state.wavesurferProcessed) state.wavesurferProcessed.destroy();

    state.wavesurferProcessed = WaveSurfer.create({
        container: '#waveform-processed',
        waveColor: 'rgba(6, 182, 212, 0.4)',
        progressColor: '#06b6d4',
        cursorColor: '#22d3ee',
        barWidth: 2,
        barGap: 1,
        barRadius: 2,
        height: 100,
        normalize: true,
        url: audioUrl,
        backend: 'WebAudio',
    });
}

function showWaveform(which) {
    const origEl = document.getElementById('waveform-original');
    const procEl = document.getElementById('waveform-processed');
    const btnOrig = document.getElementById('btn-show-original');
    const btnProc = document.getElementById('btn-show-processed');

    if (which === 'original') {
        origEl.style.display = '';
        procEl.style.display = 'none';
        btnOrig.classList.add('active');
        btnProc.classList.remove('active');
        state.currentWaveform = 'original';
    } else {
        origEl.style.display = 'none';
        procEl.style.display = '';
        btnOrig.classList.remove('active');
        btnProc.classList.add('active');
        state.currentWaveform = 'processed';
    }
}

function togglePlayback() {
    const ws = state.currentWaveform === 'processed' && state.wavesurferProcessed
        ? state.wavesurferProcessed : state.wavesurferOriginal;
    if (ws) ws.playPause();
}

function stopPlayback() {
    if (state.wavesurferOriginal) state.wavesurferOriginal.stop();
    if (state.wavesurferProcessed) state.wavesurferProcessed.stop();
}

function zoomIn() {
    const ws = state.currentWaveform === 'processed' ? state.wavesurferProcessed : state.wavesurferOriginal;
    if (ws) {
        const cur = ws.options.minPxPerSec || 50;
        ws.zoom(cur * 1.5);
    }
}

function zoomOut() {
    const ws = state.currentWaveform === 'processed' ? state.wavesurferProcessed : state.wavesurferOriginal;
    if (ws) {
        const cur = ws.options.minPxPerSec || 50;
        ws.zoom(Math.max(1, cur / 1.5));
    }
}

// ══════════════════════════════════════════════════════════
// Feature Toggles & Options
// ══════════════════════════════════════════════════════════

function toggleFeature(checkbox) {
    const option = checkbox.dataset.option;
    options[option] = checkbox.checked;

    const item = checkbox.closest('.feature-item');
    if (checkbox.checked) {
        item.classList.add('enabled');
    } else {
        item.classList.remove('enabled');
    }

    updateProcessButton();
}

function updateSliderValue(slider, unit = '%') {
    const val = slider.value;
    const display = slider.nextElementSibling;
    const option = slider.dataset.option;

    if (unit === 'dB') {
        display.textContent = '-' + val + 'dB';
        options[option] = -parseFloat(val);
    } else if (unit === 'Hz') {
        display.textContent = val + ' Hz';
        options[option] = parseFloat(val);
    } else if (unit === 'LUFS') {
        display.textContent = val + ' LUFS';
        options[option] = parseFloat(val);
    } else {
        display.textContent = val + '%';
        options[option] = parseFloat(val) / 100;
    }
}

function updateOptions() {
    document.querySelectorAll('select[data-option]').forEach(sel => {
        const option = sel.dataset.option;
        const val = sel.value;
        options[option] = isNaN(val) ? val : parseInt(val);
    });
}

function updateProcessButton() {
    const hasFile = !!state.fileId;
    const hasOptions = Object.keys(options).some(k => {
        if (typeof options[k] === 'boolean') return options[k];
        return false;
    });
    const btn = document.getElementById('btn-process');
    btn.disabled = !hasFile || !hasOptions;

    // Show estimated time on the button when filters are selected
    if (hasFile && hasOptions) {
        const audioDur = getAudioDuration();
        const estimate = estimateFilterSetETA(options, audioDur);
        if (estimate.totalSeconds > 0) {
            btn.innerHTML = `⚡ Process Audio <span class="btn-eta-badge">${formatETA(estimate.totalSeconds)}</span>`;
        } else {
            btn.innerHTML = '⚡ Process Audio';
        }
    } else {
        btn.innerHTML = '⚡ Process Audio';
    }
}

function setOptionsFromPreset(presetOptions) {
    Object.keys(presetOptions).forEach(key => {
        if (key in options) {
            options[key] = presetOptions[key];
        }
    });

    // Update UI toggles
    document.querySelectorAll('input[type="checkbox"][data-option]').forEach(cb => {
        const opt = cb.dataset.option;
        if (opt in presetOptions) {
            cb.checked = presetOptions[opt];
            const item = cb.closest('.feature-item');
            if (item) {
                if (cb.checked) item.classList.add('enabled');
                else item.classList.remove('enabled');
            }
        }
    });

    // Update sliders
    document.querySelectorAll('input[type="range"][data-option]').forEach(slider => {
        const opt = slider.dataset.option;
        if (opt in presetOptions) {
            let val = presetOptions[opt];
            if (opt === 'silence_threshold_db') val = Math.abs(val);
            else if (opt.includes('strength') || opt === 'mouth_sound_sensitivity') val = val * 100;
            slider.value = val;
            slider.dispatchEvent(new Event('input'));
        }
    });

    // Update selects
    document.querySelectorAll('select[data-option]').forEach(sel => {
        const opt = sel.dataset.option;
        if (opt in presetOptions) {
            sel.value = presetOptions[opt];
        }
    });

    updateProcessButton();
    showToast('info', 'Preset settings applied');
}

// ══════════════════════════════════════════════════════════
// Activity Tracker + ETA Engine
// ══════════════════════════════════════════════════════════

/**
 * Per-filter benchmarks: estimated seconds to process 60 seconds of audio.
 * Calibrated on Apple Silicon M3 MAX.
 * Each filter has: secondsPer60s, firstLoadCost (one-time model init), group.
 * Filters sharing a 'group' (e.g. 'whisper') share the firstLoadCost.
 */
const FILTER_BENCHMARKS = {
    // ── Noise Filters ──
    remove_noise:           { secondsPer60s: 8.0,  firstLoadCost: 5,  group: 'deepfilter', label: 'Noise Removal (DeepFilterNet / noisereduce)' },
    wind_noise_remover:     { secondsPer60s: 2.5,  firstLoadCost: 0,  group: 'dsp',        label: 'Wind Noise Removal (Pedalboard HPF)' },
    buzzing_noise_remover:  { secondsPer60s: 0.5,  firstLoadCost: 0,  group: 'dsp',        label: 'Buzzing Removal (notch filters)' },
    static_noise_remover:   { secondsPer60s: 2.5,  firstLoadCost: 0,  group: 'dsp',        label: 'Static Noise Removal (spectral gating)' },
    reverb_echo_remover:    { secondsPer60s: 4.0,  firstLoadCost: 0,  group: 'dsp',        label: 'Reverb/Echo Removal (STFT + median filter)' },
    // ── Speech Cleanup (Whisper-based) ──
    remove_filler_words:    { secondsPer60s: 35.0, firstLoadCost: 12, group: 'whisper',    label: 'Filler Words (Whisper large-v3 transcription)' },
    eliminate_hesitations:  { secondsPer60s: 35.0, firstLoadCost: 12, group: 'whisper',    label: 'Hesitations (Whisper large-v3 transcription)' },
    remove_stuttering:      { secondsPer60s: 35.0, firstLoadCost: 12, group: 'whisper',    label: 'Stuttering (Whisper large-v3 transcription)' },
    // ── Speech Cleanup (DSP-based) ──
    remove_mouth_sounds:    { secondsPer60s: 2.0,  firstLoadCost: 0,  group: 'dsp',        label: 'Mouth Sounds (spectral flux analysis)' },
    remove_breaths:         { secondsPer60s: 3.0,  firstLoadCost: 0,  group: 'dsp',        label: 'Breath Removal (spectral features)' },
    // ── Silence ──
    remove_long_silences:   { secondsPer60s: 1.0,  firstLoadCost: 0,  group: 'dsp',        label: 'Silence Removal (RMS energy analysis)' },
    // ── Enhancement ──
    auto_eq:                { secondsPer60s: 0.3,  firstLoadCost: 0,  group: 'dsp',        label: 'AutoEQ (Pedalboard filter chain)' },
    studio_sound:           { secondsPer60s: 0.5,  firstLoadCost: 0,  group: 'dsp',        label: 'Studio Sound (compressor + limiter)' },
    normalize:              { secondsPer60s: 0.3,  firstLoadCost: 0,  group: 'dsp',        label: 'Volume Normalization (EBU R128)' },
    // ── Advanced ──
    keep_music:             { secondsPer60s: 25.0, firstLoadCost: 8,  group: 'demucs',     label: 'Keep Music (Demucs neural separation)' },
    frequency_restoration:  { secondsPer60s: 5.0,  firstLoadCost: 0,  group: 'dsp',        label: 'Frequency Restoration (STFT harmonic synthesis)' },
};

/**
 * Non-filter operation benchmarks (transcription, diarization, etc.)
 */
const OPERATION_BENCHMARKS = {
    'Speech-to-Text Transcription':        { rate: 2.5,  base: 12, reason: 'Whisper large-v3 model inference' },
    'Smart Mode — Ollama/Gemma Analysis':  { rate: 0.0,  base: 12, reason: 'Local Ollama/Gemma analysis + spectral features' },
    'Speaker Diarization (MPS)':           { rate: 1.5,  base: 5,  reason: 'Energy-based speaker segmentation (MPS)' },
    'Speech Synthesis (TTS)':              { rate: 0.0,  base: 15, reason: 'XTTS-v2 neural synthesis' },
};

// Historical timing data (auto-updated after each operation)
const etaHistory = {};

// Track which model groups have already been loaded this session
const _loadedGroups = new Set();

const activity = {
    active: false,
    startTime: null,
    timerInterval: null,
    currentOperation: '',
    completedSteps: 0,
    totalSteps: 0,
    // ETA state
    lastProgress: 0,
    lastProgressTime: null,
    progressRates: [],      // rolling window of progress/second
    etaSeconds: null,
    etaReason: '',
    etaSource: 'benchmark', // 'benchmark' | 'live' | 'history'
    audioDuration: 0,       // duration of uploaded audio in seconds
};

function getAudioDuration() {
    // Use the duration stored from the upload response
    if (state.duration && state.duration > 0) {
        return state.duration;
    }
    return 60; // default assumption: 1 minute
}

/**
 * Estimate total processing time for a set of filter options.
 * @param {object} filterOptions - The options object with boolean flags per filter
 * @param {number} audioDurationSec - Duration of audio in seconds
 * @returns {{ totalSeconds: number, breakdown: Array, reason: string }}
 */
function estimateFilterSetETA(filterOptions, audioDurationSec) {
    const durationScale = audioDurationSec / 60.0;
    let totalSeconds = 3; // base overhead: file I/O, save
    const breakdown = [];
    const groupsNeeded = new Set();
    const groupCostAdded = new Set();

    // Collect all active filters and their groups
    const activeFilters = [];
    for (const [key, bench] of Object.entries(FILTER_BENCHMARKS)) {
        if (filterOptions[key]) {
            activeFilters.push({ key, bench });
            groupsNeeded.add(bench.group);
        }
    }

    if (activeFilters.length === 0) {
        return { totalSeconds: 0, breakdown: [], reason: 'Nessun filtro selezionato' };
    }

    // Calculate per-filter cost
    for (const { key, bench } of activeFilters) {
        let filterTime = bench.secondsPer60s * durationScale;

        // Add one-time model load cost per group (not per filter)
        if (bench.firstLoadCost > 0 && !groupCostAdded.has(bench.group) && !_loadedGroups.has(bench.group)) {
            filterTime += bench.firstLoadCost;
            groupCostAdded.add(bench.group);
        }

        totalSeconds += filterTime;
        breakdown.push({
            filter: key,
            label: bench.label,
            estimatedSeconds: Math.round(filterTime),
        });
    }

    totalSeconds = Math.max(3, Math.round(totalSeconds));

    // Build reason string
    const heavyFilters = breakdown.filter(b => b.estimatedSeconds >= 10);
    let reason;
    if (heavyFilters.length > 0) {
        const heavyNames = heavyFilters.map(h => h.label.split('(')[0].trim()).join(', ');
        reason = `${activeFilters.length} filtri attivi — più costosi: ${heavyNames} — stima per ${formatElapsed(Math.round(audioDurationSec))} di audio`;
    } else {
        reason = `${activeFilters.length} filtri DSP leggeri — stima per ${formatElapsed(Math.round(audioDurationSec))} di audio`;
    }

    return { totalSeconds, breakdown, reason };
}

/**
 * Format seconds as a human-readable ETA string.
 * e.g. 95 → "~1:35", 8 → "~8s"
 */
function formatETA(seconds) {
    if (seconds <= 0) return '';
    if (seconds < 60) return `~${seconds}s`;
    return `~${formatElapsed(seconds)}`;
}

function estimateInitialETA(operationName) {
    const audioDur = getAudioDuration();
    activity.audioDuration = audioDur;

    // 1. Check history first (most accurate)
    const hist = etaHistory[operationName];
    if (hist && hist.length >= 2) {
        const avgTime = hist.reduce((a, b) => a + b, 0) / hist.length;
        const adjusted = avgTime * (audioDur / (hist._avgAudioDur || 60));
        activity.etaSource = 'history';
        activity.etaReason = `Media di ${hist.length} esecuzioni precedenti (~${formatElapsed(Math.round(avgTime))} per ${formatElapsed(Math.round(hist._avgAudioDur || 60))} di audio)`;
        return Math.max(3, Math.round(adjusted));
    }

    // 2. For 'Audio Processing', use per-filter estimation
    if (operationName === 'Audio Processing') {
        const estimate = estimateFilterSetETA(options, audioDur);
        activity.etaSource = 'benchmark';
        activity.etaReason = estimate.reason;
        return estimate.totalSeconds;
    }

    // 3. Non-filter operations benchmark
    const bench = OPERATION_BENCHMARKS[operationName];
    if (bench) {
        const estimated = bench.base + (audioDur * bench.rate);
        activity.etaSource = 'benchmark';
        activity.etaReason = `${bench.reason} — stima per ${formatElapsed(Math.round(audioDur))} di audio`;
        return Math.max(3, Math.round(estimated));
    }

    // 4. Generic fallback
    activity.etaSource = 'benchmark';
    activity.etaReason = 'Stima generica — nessun benchmark disponibile per questa operazione';
    return Math.max(5, Math.round(audioDur * 0.5 + 5));
}

function refineLiveETA(progress) {
    if (progress <= 0.01 || !activity.startTime) return;

    const now = Date.now();
    const elapsedMs = now - activity.startTime;
    const elapsedSec = elapsedMs / 1000;

    // Method: elapsed / progress = total estimated time
    const totalEstSec = elapsedSec / progress;
    const remainingSec = totalEstSec - elapsedSec;

    // Also track rate of progress change for confidence
    if (activity.lastProgressTime && progress > activity.lastProgress) {
        const dt = (now - activity.lastProgressTime) / 1000;
        const dp = progress - activity.lastProgress;
        const rate = dp / dt; // progress per second
        activity.progressRates.push(rate);
        // Keep rolling window of 5
        if (activity.progressRates.length > 5) activity.progressRates.shift();
    }

    activity.lastProgress = progress;
    activity.lastProgressTime = now;

    // Use average rate for smoothed ETA
    if (activity.progressRates.length >= 2) {
        const avgRate = activity.progressRates.reduce((a, b) => a + b, 0) / activity.progressRates.length;
        const remainingProgress = 1.0 - progress;
        const rateETA = remainingProgress / avgRate;

        // Blend rate-based and simple ETA (70/30) for stability
        const blended = rateETA * 0.7 + remainingSec * 0.3;

        activity.etaSeconds = Math.max(1, Math.round(blended));
        activity.etaSource = 'live';
        activity.etaReason = `Stima in tempo reale — progresso ${(progress * 100).toFixed(0)}% in ${formatElapsed(Math.round(elapsedSec))}`;
    } else {
        // Not enough data points yet, use simple ratio
        activity.etaSeconds = Math.max(1, Math.round(remainingSec));
        activity.etaSource = 'live';
        activity.etaReason = `Estrapolazione lineare — ${(progress * 100).toFixed(0)}% completato in ${formatElapsed(Math.round(elapsedSec))}`;
    }
}

function updateETADisplay() {
    const eta = activity.etaSeconds;
    if (eta === null || eta <= 0) {
        hideETAElements();
        return;
    }

    const etaStr = formatElapsed(eta);
    const sourceIcon = activity.etaSource === 'history' ? '📊' :
                       activity.etaSource === 'live' ? '📈' : '🧮';

    // Activity bar ETA badge
    const barEta = document.getElementById('activity-bar-eta');
    if (barEta) {
        barEta.textContent = `~${etaStr}`;
        barEta.style.display = '';
    }

    // Progress panel ETA
    const panelEta = document.getElementById('progress-eta');
    const panelEtaValue = document.getElementById('progress-eta-value');
    if (panelEta && panelEtaValue) {
        panelEtaValue.textContent = `~${etaStr}`;
        panelEta.style.display = '';
    }

    // Reason text
    const reasonEl = document.getElementById('progress-eta-reason');
    if (reasonEl && activity.etaReason) {
        reasonEl.textContent = `${sourceIcon} ${activity.etaReason}`;
        reasonEl.style.display = '';
    }

    // Loading overlay ETA
    const loadingEta = document.getElementById('loading-eta');
    const loadingReason = document.getElementById('loading-eta-reason');
    if (loadingEta) {
        loadingEta.textContent = `⏳ ~${etaStr} restanti`;
        loadingEta.style.display = '';
    }
    if (loadingReason && activity.etaReason) {
        loadingReason.textContent = `${sourceIcon} ${activity.etaReason}`;
        loadingReason.style.display = '';
    }
}

function hideETAElements() {
    ['activity-bar-eta', 'progress-eta', 'progress-eta-reason', 'loading-eta', 'loading-eta-reason']
        .forEach(id => {
            const el = document.getElementById(id);
            if (el) el.style.display = 'none';
        });
}

function saveOperationTiming(operationName, elapsedSeconds) {
    if (!etaHistory[operationName]) {
        etaHistory[operationName] = [];
        etaHistory[operationName]._avgAudioDur = activity.audioDuration;
    }
    etaHistory[operationName].push(elapsedSeconds);
    // Keep last 5 entries
    if (etaHistory[operationName].length > 5) etaHistory[operationName].shift();
    // Update average audio duration
    etaHistory[operationName]._avgAudioDur =
        (etaHistory[operationName]._avgAudioDur + activity.audioDuration) / 2;
}

function startActivity(operationName, totalSteps = 0) {
    activity.active = true;
    activity.startTime = Date.now();
    activity.currentOperation = operationName;
    activity.completedSteps = 0;
    activity.totalSteps = totalSteps;
    activity.lastProgress = 0;
    activity.lastProgressTime = null;
    activity.progressRates = [];

    // Calculate initial ETA
    activity.etaSeconds = estimateInitialETA(operationName);

    // Show global activity bar
    const bar = document.getElementById('activity-bar');
    bar.classList.add('visible');
    document.getElementById('activity-bar-text').innerHTML = `<strong>${operationName}</strong> starting...`;
    document.getElementById('activity-bar-fill').style.width = '0%';
    document.getElementById('activity-elapsed').textContent = '0:00';

    // Show loading overlay
    document.getElementById('loading-text').textContent = operationName;
    document.getElementById('loading-overlay').classList.add('visible');

    // Initialize processing pipeline dashboard — build immediately, update workers async
    if (operationName === 'Audio Processing') {
        // Build pipeline SYNCHRONOUSLY first so WS messages can update it immediately
        try { buildProcessingPipeline(); } catch(e) { console.error('buildProcessingPipeline error:', e); }
        try { startProcDashHWPolling(); } catch(e) { console.error('startProcDashHWPolling error:', e); }

        // Then async update worker nodes when cluster data arrives
        fetch('/api/cluster/status')
            .then(r => r.json())
            .then(data => {
                _lastClusterData = data;
                // Re-check if workers are online and update badges + worker nodes
                if (data.online_workers > 0) {
                    _procHasEdgeWorkers = true;
                    // Update badge labels for DSP filters
                    document.querySelectorAll('.proc-step').forEach(el => {
                        const key = el.id.replace('proc-step-', '');
                        if (DSP_FILTERS && DSP_FILTERS.has && DSP_FILTERS.has(key)) {
                            const badge = el.querySelector('.proc-device-badge');
                            if (badge) {
                                badge.className = 'proc-device-badge edge';
                                badge.textContent = '📱 Edge Cluster';
                            }
                        }
                    });
                }
                try { renderWorkerNodes(); } catch(e) {}
            })
            .catch(() => {});
    }

    // Show initial ETA
    updateETADisplay();

    // Start elapsed timer (and countdown ETA)
    clearInterval(activity.timerInterval);
    activity.timerInterval = setInterval(() => {
        const elapsed = Math.floor((Date.now() - activity.startTime) / 1000);
        const timeStr = formatElapsed(elapsed);
        document.getElementById('activity-elapsed').textContent = timeStr;

        // Update progress panel elapsed time
        const progressElapsed = document.getElementById('progress-elapsed');
        if (progressElapsed) progressElapsed.textContent = timeStr;

        // Countdown ETA (if using benchmark/initial estimate)
        if (activity.etaSource === 'benchmark' || activity.etaSource === 'history') {
            const initialEta = estimateInitialETA(activity.currentOperation);
            activity.etaSeconds = Math.max(0, initialEta - elapsed);
        }

        // Update loading overlay with elapsed
        document.getElementById('loading-text').textContent =
            `${activity.currentOperation} (${timeStr})`;

        // Update ETA display
        updateETADisplay();
    }, 1000);
}

function updateActivity(message, progress = -1) {
    if (!activity.active) return;

    // Update activity bar text
    document.getElementById('activity-bar-text').innerHTML =
        `<strong>${activity.currentOperation}</strong> — ${message}`;

    // Update progress if provided
    if (progress >= 0) {
        const pct = Math.round(progress * 100);
        document.getElementById('activity-bar-fill').style.width = pct + '%';

        // In-panel progress
        const progressBar = document.getElementById('progress-bar');
        const progressPercent = document.getElementById('progress-percent');
        if (progressBar) progressBar.style.width = pct + '%';
        if (progressPercent) progressPercent.textContent = pct + '%';

        // Refine ETA with live progress data
        refineLiveETA(progress);
        updateETADisplay();
    }

    // Update current step label
    const currentStep = document.getElementById('progress-current-step');
    if (currentStep) currentStep.textContent = message;
}

function addActivityStep(message, status = 'completed') {
    activity.completedSteps++;

    const elapsed = Math.floor((Date.now() - activity.startTime) / 1000);
    const progressSteps = document.getElementById('progress-steps');
    if (!progressSteps) return;

    // Mark previous active step as completed
    const activeStep = progressSteps.querySelector('.progress-step.active');
    if (activeStep) {
        activeStep.classList.remove('active');
        activeStep.classList.add('completed');
        activeStep.querySelector('.step-icon').textContent = '✓';
    }

    const stepEl = document.createElement('div');
    stepEl.className = `progress-step ${status}`;

    const icon = status === 'completed' ? '✓' : status === 'error' ? '✕' : '⟳';
    stepEl.innerHTML = `<span class="step-icon">${icon}</span> ${message} <span class="step-time">${formatElapsed(elapsed)}</span>`;

    progressSteps.appendChild(stepEl);
    progressSteps.scrollTop = progressSteps.scrollHeight;
}

function stopActivity(success = true) {
    const elapsed = Math.floor((Date.now() - activity.startTime) / 1000);

    // Save timing for future ETA accuracy
    if (success && activity.currentOperation) {
        saveOperationTiming(activity.currentOperation, elapsed);

        // Mark model groups as loaded so next run has lower ETA
        if (activity.currentOperation === 'Audio Processing') {
            for (const [key, bench] of Object.entries(FILTER_BENCHMARKS)) {
                if (options[key] && bench.firstLoadCost > 0) {
                    _loadedGroups.add(bench.group);
                }
            }
            // Update process button to reflect reduced ETA
            updateProcessButton();
        }
    }

    activity.active = false;
    clearInterval(activity.timerInterval);

    // Update activity bar
    const bar = document.getElementById('activity-bar');
    if (success) {
        document.getElementById('activity-bar-fill').style.width = '100%';
        document.getElementById('activity-bar-text').innerHTML =
            `<strong>${activity.currentOperation}</strong> — Completato in ${formatElapsed(elapsed)} ✓`;
    }

    // Hide ETA elements
    hideETAElements();

    // Hide after delay
    setTimeout(() => {
        bar.classList.remove('visible');
    }, success ? 3000 : 5000);

    // Hide loading overlay
    document.getElementById('loading-overlay').classList.remove('visible');

    // Stop spinner in progress panel
    const spinner = document.getElementById('progress-spinner');
    if (spinner) spinner.style.display = 'none';

    // Stop HW utilization polling
    if (typeof stopProcDashHWPolling === 'function') stopProcDashHWPolling();
}

function formatElapsed(seconds) {
    if (seconds < 60) return `0:${seconds.toString().padStart(2, '0')}`;
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${m}:${s.toString().padStart(2, '0')}`;
}

// ══════════════════════════════════════════════════════════
// Processing
// ══════════════════════════════════════════════════════════

async function startProcessing() {
    if (!state.fileId || state.isProcessing) return;
    state.isProcessing = true;

    // Count processing steps
    const stepCount = Object.keys(options).filter(k => typeof options[k] === 'boolean' && options[k]).length;

    startActivity('Audio Processing', stepCount);

    const progressContainer = document.getElementById('progress-container');
    const progressBar = document.getElementById('progress-bar');
    const progressSteps = document.getElementById('progress-steps');
    progressContainer.classList.add('visible');
    progressBar.style.width = '0%';
    progressSteps.innerHTML = '';
    document.getElementById('progress-percent').textContent = '0%';
    document.getElementById('progress-current-step').textContent = 'Starting pipeline...';
    const spinner = document.getElementById('progress-spinner');
    if (spinner) spinner.style.display = '';

    document.getElementById('btn-process').disabled = true;
    document.getElementById('btn-process').innerHTML = '⏳ Processing...';

    // Connect WebSocket for progress
    connectProgressWS(state.fileId);

    try {
        const res = await fetch('/api/process', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                file_id: state.fileId,
                options: options,
            }),
        });

        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || 'Processing failed');
        }

        const result = await res.json();
        state.hasProcessed = true;
        state.processedUrl = result.output_url;

        // Show processed waveform
        await initProcessedWaveform(result.output_url);
        showWaveform('processed');

        // Show download bar
        const dlBar = document.getElementById('download-bar');
        dlBar.classList.add('visible');
        document.getElementById('download-info-text').textContent =
            `${formatDuration(result.duration_seconds)} • ${result.sample_rate}Hz • ${result.format.toUpperCase()}`;

        updateActivity('Complete!', 1.0);
        addActivityStep('Processing complete — audio ready for download');
        stopActivity(true);
        showToast('success', 'Processing complete! Download your enhanced audio.');

    } catch (e) {
        addActivityStep(`Error: ${e.message}`, 'error');
        stopActivity(false);
        showToast('error', e.message);
    } finally {
        state.isProcessing = false;
        document.getElementById('btn-process').disabled = false;
        document.getElementById('btn-process').innerHTML = '⚡ Process Audio';
    }
}

function connectProgressWS(fileId) {
    try {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const ws = new WebSocket(`${protocol}//${window.location.host}/ws/progress/${fileId}`);

        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);

            // Update progress visuals
            updateActivity(data.message || 'Processing...', data.progress || 0);

            if (data.message) {
                addActivityStep(data.message);
            }

            // Pipeline dashboard update
            if (data.step) {
                console.log('[WS] step:', data.step, 'message:', data.message, 'pipelineState:', JSON.stringify(_procPipelineState));
                updatePipelineStep(data.step, data.message);
            } else if (data.message) {
                // Infer step from message
                for (const [stepKey, filterKey] of Object.entries(STEP_TO_FILTER)) {
                    if (filterKey.startsWith('_')) continue;
                    const label = FILTER_LABELS[filterKey] || '';
                    if (data.message.toLowerCase().includes(label.toLowerCase()) ||
                        data.message.toLowerCase().includes(stepKey)) {
                        console.log('[WS] inferred step:', stepKey, 'from message:', data.message);
                        updatePipelineStep(stepKey, data.message);
                        break;
                    }
                }
            }
        };

        ws.onerror = () => {};
        ws.onclose = () => {};
        state.wsConnection = ws;
    } catch (e) {
        // WebSocket not critical
    }
}

// ══════════════════════════════════════════════════════════
// Smart Mode (Ollama/Gemma)
// ══════════════════════════════════════════════════════════

async function runSmartMode() {
    if (!state.fileId) return;

    startActivity('Smart Mode — Ollama/Gemma Analysis');
    updateActivity('Analyzing audio features...', 0.1);

    try {
        const res = await fetch(`/api/smart-mode/${state.fileId}`, { method: 'POST' });
        if (!res.ok) throw new Error('Smart mode analysis failed');

        const data = await res.json();
        state.smartSuggestions = data;

        // Show banner
        const banner = document.getElementById('smart-mode-banner');
        banner.classList.add('visible');
        document.getElementById('smart-mode-type').textContent =
            `Detected: ${data.detected_type.replace('_', ' ').toUpperCase()}`;
        document.getElementById('smart-mode-description').textContent = data.description;
        document.getElementById('smart-engine-badge').textContent =
            data.engine && data.engine !== 'heuristics' ? data.engine : 'Heuristics';

        // Show in smart panel
        const resultsDiv = document.getElementById('smart-results');
        resultsDiv.style.display = 'block';

        let html = `<p><strong>Content Type:</strong> ${data.detected_type}</p>`;
        html += `<p><strong>Confidence:</strong> ${(data.confidence * 100).toFixed(0)}%</p>`;
        html += `<p><strong>Engine:</strong> ${data.engine}</p>`;
        html += `<p>${data.description}</p>`;

        if (data.ai_suggestions && data.ai_suggestions.length > 0) {
            html += '<div class="mt-12"><strong>AI Suggestions:</strong><ul>';
            data.ai_suggestions.forEach(s => {
                html += `<li style="color:var(--text-secondary);font-size:0.85rem;margin:4px 0">${s}</li>`;
            });
            html += '</ul></div>';
        }

        document.getElementById('smart-analysis-content').innerHTML = html;

        stopActivity(true);
        showToast('success', `Smart Mode: detected "${data.detected_type}" (${data.engine})`);

    } catch (e) {
        stopActivity(false);
        showToast('error', e.message);
    }
}

function applySmartPreset() {
    if (state.smartSuggestions && state.smartSuggestions.suggested_options) {
        setOptionsFromPreset(state.smartSuggestions.suggested_options);
        switchPanel('upload-panel', document.querySelector('[data-panel="upload-panel"]'));
        showToast('success', 'Smart Mode settings applied!');
    }
}

// ══════════════════════════════════════════════════════════
// Speech-to-Text
// ══════════════════════════════════════════════════════════

async function startTranscription() {
    if (!state.fileId) return;

    startActivity('Speech-to-Text Transcription');
    updateActivity('Loading whisper model...', 0.05);
    document.getElementById('btn-transcribe').disabled = true;

    try {
        const language = document.getElementById('stt-language').value || null;
        const format = document.getElementById('stt-format').value;

        const res = await fetch('/api/transcribe', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                file_id: state.fileId,
                language: language,
                output_format: format,
            }),
        });

        if (!res.ok) throw new Error('Transcription failed');

        const data = await res.json();

        const output = document.getElementById('transcript-output');
        output.style.display = 'block';
        output.textContent = data.formatted || data.text;

        document.getElementById('stt-actions').style.display = 'flex';
        state.transcriptData = data;

        updateActivity('Transcription complete', 1.0);
        addActivityStep(`Transcribed (${data.language || 'auto'})`);
        stopActivity(true);
        showToast('success', `Transcription complete (${data.language || 'auto'})`);

    } catch (e) {
        stopActivity(false);
        showToast('error', e.message);
    } finally {
        document.getElementById('btn-transcribe').disabled = false;
    }
}

function copyTranscript() {
    const text = document.getElementById('transcript-output').textContent;
    navigator.clipboard.writeText(text);
    showToast('info', 'Transcript copied to clipboard');
}

function downloadTranscript() {
    if (!state.transcriptData) return;
    const format = document.getElementById('stt-format').value;
    const text = state.transcriptData.formatted || state.transcriptData.text;
    const blob = new Blob([text], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `transcript_${state.fileId}.${format}`;
    a.click();
    URL.revokeObjectURL(url);
}

// ══════════════════════════════════════════════════════════
// Text-to-Speech
// ══════════════════════════════════════════════════════════

async function handleCloneUpload(event) {
    const file = event.target.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);

    try {
        const res = await fetch('/api/upload', { method: 'POST', body: formData });
        const data = await res.json();
        state.cloneVoiceFileId = data.file_id;
        document.getElementById('clone-status').textContent = `✓ Loaded: ${file.name}`;
        showToast('success', 'Voice sample loaded for cloning');
    } catch (e) {
        showToast('error', 'Failed to upload voice sample');
    }
}

async function synthesizeSpeech() {
    const text = document.getElementById('tts-text').value.trim();
    if (!text) {
        showToast('warning', 'Please enter text to synthesize');
        return;
    }

    startActivity('Speech Synthesis (TTS)');
    updateActivity('Generating speech...', 0.1);

    try {
        const res = await fetch('/api/tts/synthesize', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                text: text,
                language: document.getElementById('tts-language').value,
                style: document.getElementById('tts-style').value,
                speed: parseFloat(document.getElementById('tts-speed').value) / 100,
                pitch: parseFloat(document.getElementById('tts-pitch').value) / 100,
                warmth: parseFloat(document.getElementById('tts-warmth').value) / 100,
                clone_voice_file_id: state.cloneVoiceFileId || null,
            }),
        });

        if (!res.ok) throw new Error('Speech synthesis failed');

        const data = await res.json();
        const audio = document.getElementById('tts-audio');
        audio.src = data.audio_url;
        document.getElementById('tts-result').style.display = 'block';

        stopActivity(true);
        showToast('success', `Speech generated (${data.duration.toFixed(1)}s)`);

    } catch (e) {
        stopActivity(false);
        showToast('error', e.message);
    }
}

// ══════════════════════════════════════════════════════════
// Speaker Diarization
// ══════════════════════════════════════════════════════════

async function startDiarization() {
    if (!state.fileId) return;

    startActivity('Speaker Diarization (MPS)');
    updateActivity('Analyzing speakers...', 0.1);

    try {
        const numSpeakers = parseInt(document.getElementById('diarize-speakers').value) || null;

        const res = await fetch('/api/diarize', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                file_id: state.fileId,
                num_speakers: numSpeakers > 0 ? numSpeakers : null,
            }),
        });

        if (!res.ok) throw new Error('Diarization failed');

        const data = await res.json();
        renderDiarization(data);

        stopActivity(true);
        showToast('success', `Found ${data.total_speakers} speaker(s)`);

    } catch (e) {
        stopActivity(false);
        showToast('error', e.message);
    }
}

function renderDiarization(data) {
    document.getElementById('diarize-results').style.display = 'block';

    const colors = ['#7c3aed', '#06b6d4', '#f59e0b', '#10b981', '#ef4444', '#ec4899'];
    const totalDuration = state.duration || 1;
    const bar = document.getElementById('diarization-bar');

    let html = '';
    data.segments.forEach(seg => {
        const left = (seg.start / totalDuration) * 100;
        const width = ((seg.end - seg.start) / totalDuration) * 100;
        const speakerIdx = parseInt(seg.speaker.replace('SPEAKER_', '')) || 0;
        const color = colors[speakerIdx % colors.length];

        html += `<div class="diarization-segment" style="left:${left}%;width:${width}%;background:${color}">${seg.speaker_label}</div>`;
    });
    bar.innerHTML = html;

    // Speaker stats
    const statsDiv = document.getElementById('speaker-stats');
    let statsHtml = '<div class="feature-grid">';
    Object.entries(data.speaker_stats).forEach(([speaker, stats], idx) => {
        const color = colors[idx % colors.length];
        statsHtml += `
            <div class="feature-item">
                <div class="feature-icon" style="background:${color}33;color:${color}">👤</div>
                <div class="feature-info">
                    <div class="feature-name">${speaker}</div>
                    <div class="feature-desc">${stats.total_duration}s • ${stats.segment_count} segments • ${stats.percentage}%</div>
                </div>
            </div>`;
    });
    statsHtml += '</div>';
    statsDiv.innerHTML = statsHtml;
}

// ══════════════════════════════════════════════════════════
// Watermarking
// ══════════════════════════════════════════════════════════

async function embedWatermark() {
    if (!state.fileId) return;

    const identifier = document.getElementById('watermark-id').value || '';

    try {
        const res = await fetch(`/api/watermark/${state.fileId}?identifier=${encodeURIComponent(identifier)}`, {
            method: 'POST',
        });
        if (!res.ok) throw new Error('Watermarking failed');

        const data = await res.json();
        document.getElementById('watermark-result').style.display = 'block';
        document.getElementById('watermark-result').innerHTML =
            `<div class="card" style="border-color:var(--success)"><div class="card-title">✓ Watermark Embedded</div>
            <p class="text-sm text-muted mt-12">Invisible watermark has been embedded. <a href="${data.watermarked_url}" download style="color:var(--accent-primary-light)">Download watermarked file</a></p></div>`;

        showToast('success', 'Watermark embedded');
    } catch (e) {
        showToast('error', e.message);
    }
}

async function detectWatermark() {
    if (!state.fileId) return;

    try {
        const res = await fetch(`/api/watermark/detect/${state.fileId}`, { method: 'POST' });
        if (!res.ok) throw new Error('Detection failed');

        const data = await res.json();
        document.getElementById('watermark-result').style.display = 'block';

        if (data.watermark && data.watermark.detected) {
            document.getElementById('watermark-result').innerHTML =
                `<div class="card" style="border-color:var(--success)"><div class="card-title">🔍 Watermark Detected</div>
                <p class="text-sm mt-12">Method: ${data.watermark.method}</p>
                <p class="text-xs text-muted">Payload: ${data.watermark.payload}</p></div>`;
        } else {
            document.getElementById('watermark-result').innerHTML =
                `<div class="card" style="border-color:var(--warning)"><div class="card-title">No Watermark Found</div></div>`;
        }
    } catch (e) {
        showToast('error', e.message);
    }
}

// ══════════════════════════════════════════════════════════
// Presets
// ══════════════════════════════════════════════════════════

async function loadPresets() {
    try {
        const res = await fetch('/api/presets');
        if (!res.ok) return;

        const data = await res.json();

        // Render built-in presets
        const builtinGrid = document.getElementById('builtin-presets');
        builtinGrid.innerHTML = (data.builtin || []).map(p => {
            // Calculate ETA for this preset (use 60s as reference)
            const presetETA = estimateFilterSetETA(p.options, 60);
            const etaBadge = presetETA.totalSeconds > 0
                ? `<div class="preset-card-eta" title="Tempo stimato per 1 min di audio">⏱ ${formatETA(presetETA.totalSeconds)} per 1 min</div>`
                : '';
            const filterCount = Object.keys(p.options).filter(k => p.options[k] === true).length;
            return `
            <div class="preset-card" onclick="applyPreset(${JSON.stringify(p.options).replace(/"/g, '&quot;')})">
                <div class="preset-card-name">${p.name}</div>
                <div class="preset-card-desc">${p.description}</div>
                <div class="preset-card-meta">
                    <span class="preset-filter-count">${filterCount} filtri</span>
                    ${etaBadge}
                </div>
            </div>
        `;
        }).join('');

        // Render custom presets
        const customGrid = document.getElementById('custom-presets');
        if (data.custom && data.custom.length > 0) {
            customGrid.innerHTML = data.custom.map(p => `
                <div class="preset-card" onclick="loadAndApplyPreset('${p.id}')">
                    <div class="preset-card-name">${p.name}</div>
                    <div class="preset-card-desc">${p.description}</div>
                </div>
            `).join('');
        } else {
            customGrid.innerHTML = '<p class="text-sm text-muted">No custom presets saved yet.</p>';
        }
    } catch (e) {
        // Presets will load when backend is ready
    }
}

function applyPreset(presetOptions) {
    setOptionsFromPreset(presetOptions);
    switchPanel('upload-panel', document.querySelector('[data-panel="upload-panel"]'));
}

async function loadAndApplyPreset(presetId) {
    try {
        const res = await fetch(`/api/presets/${presetId}`);
        if (!res.ok) throw new Error('Preset not found');
        const data = await res.json();
        setOptionsFromPreset(data.options);
        switchPanel('upload-panel', document.querySelector('[data-panel="upload-panel"]'));
    } catch (e) {
        showToast('error', e.message);
    }
}

async function saveCurrentAsPreset() {
    const name = prompt('Preset name:');
    if (!name) return;

    const description = prompt('Description (optional):') || '';

    try {
        const res = await fetch('/api/presets', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, description, options }),
        });
        if (!res.ok) throw new Error('Save failed');
        showToast('success', `Preset "${name}" saved`);
        loadPresets();
    } catch (e) {
        showToast('error', e.message);
    }
}

// ══════════════════════════════════════════════════════════
// Batch Processing
// ══════════════════════════════════════════════════════════

function initBatchUpload() {
    const zone = document.getElementById('batch-upload-zone');
    const input = document.getElementById('batch-file-input');

    zone.addEventListener('click', () => input.click());

    zone.addEventListener('dragover', (e) => { e.preventDefault(); zone.classList.add('drag-over'); });
    zone.addEventListener('dragleave', () => { zone.classList.remove('drag-over'); });

    zone.addEventListener('drop', (e) => {
        e.preventDefault();
        zone.classList.remove('drag-over');
        handleBatchFiles(e.dataTransfer.files);
    });

    input.addEventListener('change', (e) => {
        handleBatchFiles(e.target.files);
    });
}

async function handleBatchFiles(files) {
    const list = document.getElementById('batch-file-list');

    for (const file of files) {
        const formData = new FormData();
        formData.append('file', file);

        try {
            const res = await fetch('/api/upload', { method: 'POST', body: formData });
            const data = await res.json();
            state.batchFiles.push({ fileId: data.file_id, name: data.filename, status: 'pending' });
        } catch (e) {
            state.batchFiles.push({ fileId: null, name: file.name, status: 'error' });
        }
    }

    renderBatchList();
    document.getElementById('btn-batch-process').disabled = state.batchFiles.length === 0;
}

function renderBatchList() {
    const list = document.getElementById('batch-file-list');
    list.innerHTML = state.batchFiles.map((f, i) => `
        <div class="batch-file-item">
            <span>${i + 1}.</span>
            <span style="flex:1">${f.name}</span>
            <span class="batch-file-status ${f.status}">${f.status}</span>
        </div>
    `).join('');
}

async function startBatchProcessing() {
    const fileIds = state.batchFiles.filter(f => f.fileId).map(f => f.fileId);
    if (fileIds.length === 0) return;

    showToast('info', `Starting batch processing of ${fileIds.length} files...`);

    try {
        const res = await fetch('/api/batch', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ file_ids: fileIds, options }),
        });

        if (!res.ok) throw new Error('Batch start failed');

        const data = await res.json();
        // Poll for progress
        pollBatchStatus(data.job_id);

    } catch (e) {
        showToast('error', e.message);
    }
}

async function pollBatchStatus(jobId) {
    const poll = async () => {
        try {
            const res = await fetch(`/api/batch/${jobId}`);
            const data = await res.json();

            // Update file statuses
            state.batchFiles.forEach(f => {
                if (f.fileId && data.results[f.fileId]) {
                    f.status = data.results[f.fileId].status;
                }
            });
            renderBatchList();

            if (data.status !== 'completed') {
                setTimeout(poll, 2000);
            } else {
                showToast('success', `Batch processing complete! ${data.processed_files}/${data.total_files} files done.`);
            }
        } catch (e) {
            showToast('error', 'Lost connection to batch job');
        }
    };
    poll();
}

// ══════════════════════════════════════════════════════════
// Download & A/B Compare
// ══════════════════════════════════════════════════════════

function downloadFile(format) {
    if (!state.fileId) return;
    window.open(`/api/download/${state.fileId}?format=${format}&version=processed`, '_blank');
}

function compareAB() {
    if (!state.wavesurferOriginal || !state.wavesurferProcessed) {
        showToast('warning', 'Process audio first to compare');
        return;
    }

    state.abMode = !state.abMode;

    if (state.abMode) {
        // Play both alternating
        showToast('info', 'A/B Mode: Toggle between Original and Processed waveforms');
        showWaveform('original');
    }
}

// ══════════════════════════════════════════════════════════
// UI Utilities
// ══════════════════════════════════════════════════════════

function showLoading(text = 'Processing...') {
    // If activity system is not running, show simple overlay
    if (!activity.active) {
        document.getElementById('loading-text').textContent = text;
        document.getElementById('loading-overlay').classList.add('visible');
    }
}

function hideLoading() {
    if (!activity.active) {
        document.getElementById('loading-overlay').classList.remove('visible');
    }
}

function showToast(type, message) {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;

    const icons = { success: '✓', error: '✕', warning: '⚠', info: 'ℹ' };
    toast.innerHTML = `<span>${icons[type] || '•'}</span> ${message}`;

    container.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(20px)';
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

function formatDuration(seconds) {
    if (!seconds || isNaN(seconds)) return '0:00';
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m}:${s.toString().padStart(2, '0')}`;
}

function formatFileSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

// ══════════════════════════════════════════════════════════
// Edge Cluster Management
// ══════════════════════════════════════════════════════════

let clusterPollInterval = null;

function startClusterPolling() {
    pollClusterStatus();
    clusterPollInterval = setInterval(pollClusterStatus, 5000);
}

async function pollClusterStatus() {
    try {
        const res = await fetch('/api/cluster/status');
        if (!res.ok) return;
        const data = await res.json();
        updateClusterUI(data);
    } catch (e) {
        // Silently fail — cluster polling is non-critical
    }
}

async function refreshCluster() {
    try {
        const res = await fetch('/api/cluster/health-check', { method: 'POST' });
        const data = await res.json();
        updateClusterUI(data);
        showToast('info', 'Cluster status refreshed');
    } catch (e) {
        showToast('error', 'Failed to refresh cluster');
    }
}

function updateClusterUI(data) {
    const { workers, online_workers, total_workers, orchestrator_ip } = data;

    // Update header badge
    const badge = document.getElementById('cluster-badge');
    const dot = document.getElementById('cluster-dot');
    const label = document.getElementById('cluster-label');
    const sidebarBadge = document.getElementById('sidebar-cluster-count');

    if (online_workers > 0) {
        badge.style.display = '';
        dot.className = 'status-dot';
        label.textContent = `${online_workers} Worker${online_workers > 1 ? 's' : ''}`;
        if (sidebarBadge) {
            sidebarBadge.style.display = '';
            sidebarBadge.textContent = online_workers;
        }
    } else {
        badge.style.display = 'none';
        if (sidebarBadge) sidebarBadge.style.display = 'none';
    }

    // Update master node
    const masterChip = document.getElementById('master-chip');
    const masterName = document.getElementById('master-node-name');
    if (masterChip) masterChip.textContent = document.getElementById('compute-label')?.textContent || 'M3 MAX';
    if (masterName) masterName.textContent = `Mac (${masterChip?.textContent || 'M3 MAX'})`;

    // Update worker count text
    const countEl = document.getElementById('cluster-worker-count');
    if (countEl) countEl.textContent = `(${online_workers} connected)`;

    // Render worker cards
    const list = document.getElementById('cluster-workers-list');
    const empty = document.getElementById('cluster-empty');

    if (workers.length === 0) {
        if (empty) empty.style.display = '';
        // Remove any worker cards but keep empty state
        list.querySelectorAll('.cluster-node.worker-node').forEach(n => n.remove());
        return;
    }

    if (empty) empty.style.display = 'none';

    // Remove old worker cards
    list.querySelectorAll('.cluster-node.worker-node').forEach(n => n.remove());

    // Render new worker cards
    workers.forEach(worker => {
        const card = createWorkerCard(worker);
        list.appendChild(card);
    });
}

function createWorkerCard(worker) {
    const card = document.createElement('div');
    card.className = 'cluster-node worker-node';

    const isOnline = worker.status === 'online' || worker.status === 'busy';
    const isBusy = worker.status === 'busy';
    const statusClass = isBusy ? 'busy' : (isOnline ? 'online' : 'offline');
    const statusText = isBusy ? 'Processing' : (isOnline ? 'Online' : 'Offline');

    // Compute benchmark score: estimate relative power based on cores and RAM
    const benchmarkScore = computeBenchmark(worker);
    const benchmarkPct = Math.min(95, benchmarkScore); // Max 95% (master is 100%)

    // Estimate power tier
    const powerTier = benchmarkPct >= 70 ? 'High Performance' :
                      benchmarkPct >= 40 ? 'Mid Range' : 'Light Compute';
    const tierClass = benchmarkPct >= 70 ? 'high' : (benchmarkPct >= 40 ? 'mid' : 'low');

    card.innerHTML = `
        <div class="cluster-node-header">
            <div class="cluster-node-status ${statusClass}"></div>
            <div class="cluster-node-name">${escapeHtml(worker.name || worker.device_model || 'Unknown')}</div>
            <span class="cluster-node-role worker">${statusText}</span>
            <button class="btn btn-xs btn-ghost" onclick="removeWorker('${worker.ip}', ${worker.port})" title="Remove">✕</button>
        </div>
        <div class="cluster-node-stats">
            <div class="cluster-stat"><span class="cluster-stat-label">Model</span><span class="cluster-stat-value">${escapeHtml(worker.device_model || '—')}</span></div>
            <div class="cluster-stat"><span class="cluster-stat-label">IP</span><span class="cluster-stat-value">${worker.ip}:${worker.port}</span></div>
            <div class="cluster-stat"><span class="cluster-stat-label">CPU</span><span class="cluster-stat-value">${worker.cpu_cores || '?'} cores</span></div>
            <div class="cluster-stat"><span class="cluster-stat-label">RAM</span><span class="cluster-stat-value">${worker.ram_gb || '?'} GB</span></div>
            <div class="cluster-stat"><span class="cluster-stat-label">DSP Filters</span><span class="cluster-stat-value">${(worker.available_filters || []).length}</span></div>
            <div class="cluster-stat"><span class="cluster-stat-label">Tasks Done</span><span class="cluster-stat-value">${worker.tasks_completed || 0}</span></div>
            <div class="cluster-stat"><span class="cluster-stat-label">Avg Speed</span><span class="cluster-stat-value">${worker.avg_speed ? worker.avg_speed + 's' : '—'}</span></div>
            ${worker.current_task ? `<div class="cluster-stat"><span class="cluster-stat-label">Current</span><span class="cluster-stat-value highlight">${escapeHtml(worker.current_task)}</span></div>` : ''}
        </div>
        <div class="cluster-benchmark">
            <div class="cluster-benchmark-label">Benchmark Power — <span class="tier-${tierClass}">${powerTier}</span></div>
            <div class="cluster-benchmark-bar"><div class="cluster-benchmark-fill ${tierClass}" style="width:${benchmarkPct}%"></div></div>
            <span class="cluster-benchmark-value">${benchmarkPct}% — ${(worker.available_filters || []).length} DSP filters</span>
        </div>
    `;

    return card;
}

function computeBenchmark(worker) {
    // Simple benchmark based on CPU cores, RAM, and number of filters
    // Master M3 MAX ~baseline: 16 cores, 96GB RAM, 16 filters = 100%
    const coreScore = Math.min(100, (worker.cpu_cores || 4) / 16 * 40); // up to 40pts
    const ramScore = Math.min(30, (worker.ram_gb || 4) / 96 * 30);     // up to 30pts
    const filterScore = Math.min(30, ((worker.available_filters || []).length / 16) * 30); // up to 30pts
    return Math.round(coreScore + ramScore + filterScore);
}

async function addWorkerManually() {
    const ip = document.getElementById('add-worker-ip').value.trim();
    const port = parseInt(document.getElementById('add-worker-port').value) || 8877;

    if (!ip) {
        showToast('error', 'Please enter an IP address');
        return;
    }

    try {
        const res = await fetch('/api/cluster/add', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ip, port })
        });
        const data = await res.json();
        if (data.status === 'ok') {
            showToast('success', `Worker ${data.worker?.name || ip} added!`);
            document.getElementById('add-worker-ip').value = '';
            pollClusterStatus();
        } else {
            showToast('error', data.message || 'Failed to add worker');
        }
    } catch (e) {
        showToast('error', `Failed to connect to ${ip}:${port}`);
    }
}

async function removeWorker(ip, port) {
    try {
        const res = await fetch('/api/cluster/remove', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ip, port })
        });
        const data = await res.json();
        if (data.status === 'ok') {
            showToast('info', 'Worker removed');
            pollClusterStatus();
        }
    } catch (e) {
        showToast('error', 'Failed to remove worker');
    }
}

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

// Start cluster polling on page load
document.addEventListener('DOMContentLoaded', () => {
    startClusterPolling();
});

// ══════════════════════════════════════════════════════════
// Processing Dashboard — per-filter pipeline + HW utilization
// ══════════════════════════════════════════════════════════

const FILTER_LABELS = {
    remove_noise: 'Noise Removal',
    wind_noise_remover: 'Wind Noise',
    buzzing_noise_remover: 'Buzzing Noise',
    static_noise_remover: 'Static Noise',
    reverb_echo_remover: 'Reverb / Echo',
    remove_mouth_sounds: 'Mouth Sounds',
    remove_filler_words: 'Filler Words',
    eliminate_hesitations: 'Hesitations',
    remove_stuttering: 'Stuttering',
    remove_breaths: 'Breaths',
    remove_long_silences: 'Long Silences',
    keep_music: 'Music Separation',
    auto_eq: 'Auto EQ',
    studio_sound: 'Studio Sound',
    frequency_restoration: 'Frequency Restore',
    normalize: 'Loudness Normalize',
};

// Which filters are ML-based (always local) vs DSP (can be distributed)
const ML_FILTERS = new Set([
    'remove_filler_words', 'eliminate_hesitations', 'remove_stuttering', 'keep_music'
]);
const DSP_FILTERS = new Set([
    'remove_noise', 'wind_noise_remover', 'buzzing_noise_remover',
    'static_noise_remover', 'reverb_echo_remover', 'remove_mouth_sounds',
    'remove_breaths', 'remove_long_silences', 'auto_eq', 'studio_sound',
    'normalize', 'frequency_restoration'
]);

let _procDashInterval = null;
let _procPipelineState = {};    // filterKey -> { status, startTime, endTime }
let _procHasEdgeWorkers = false;

function buildProcessingPipeline() {
    const pipeline = document.getElementById('proc-pipeline');
    if (!pipeline) return;
    pipeline.innerHTML = '';
    _procPipelineState = {};

    // Determine if there are online edge workers
    _procHasEdgeWorkers = false;
    try {
        if (_lastClusterData && _lastClusterData.online_workers > 0) {
            _procHasEdgeWorkers = true;
        }
    } catch (_) {}

    // Build ordered list of active filters
    const filterOrder = Object.keys(FILTER_LABELS);
    for (const key of filterOrder) {
        if (!options[key]) continue;

        const label = FILTER_LABELS[key] || key;
        const isML = ML_FILTERS.has(key);
        const isDSP = DSP_FILTERS.has(key);

        // Determine execution device
        let deviceLabel, deviceClass;
        if (isML) {
            deviceLabel = '🧠 ML · Mac';
            deviceClass = 'ml';
        } else if (isDSP && _procHasEdgeWorkers) {
            deviceLabel = '📱 Edge Cluster';
            deviceClass = 'edge';
        } else {
            deviceLabel = '🖥️ Mac';
            deviceClass = 'mac';
        }

        _procPipelineState[key] = { status: 'queued', startTime: null, endTime: null };

        const stepEl = document.createElement('div');
        stepEl.className = 'proc-step queued';
        stepEl.id = `proc-step-${key}`;
        stepEl.innerHTML = `
            <div class="proc-step-icon">○</div>
            <span class="proc-step-name">${label}</span>
            <span class="proc-device-badge ${deviceClass}">${deviceLabel}</span>
            <span class="proc-step-time" id="proc-time-${key}"></span>
        `;
        pipeline.appendChild(stepEl);
    }

    // Inject worker nodes into the node utilization section
    renderWorkerNodes();
}

function renderWorkerNodes() {
    const container = document.getElementById('proc-nodes');
    if (!container) return;

    // Remove old worker nodes (keep master)
    container.querySelectorAll('.proc-node.worker').forEach(el => el.remove());

    if (!_lastClusterData || !_lastClusterData.workers) return;

    for (const w of _lastClusterData.workers) {
        if (w.status === 'offline') continue;

        const node = document.createElement('div');
        node.className = 'proc-node worker';
        node.id = `proc-node-${w.ip.replace(/\./g, '-')}`;
        node.innerHTML = `
            <div class="proc-node-head">
                <span class="proc-node-dot ${w.status === 'busy' ? 'busy' : 'online'}"></span>
                <span class="proc-node-label">📱 ${w.device_model || w.name}</span>
            </div>
            <div class="proc-node-chip">${w.cpu_cores} cores · ${w.ram_gb} GB RAM · ${(w.available_filters || []).length} DSP filters</div>
            <div class="proc-node-meters">
                <div class="proc-meter">
                    <span class="proc-meter-label">Tasks</span>
                    <div class="proc-meter-bar"><div class="proc-meter-fill" style="width:100%"></div></div>
                    <span class="proc-meter-val">${w.tasks_completed || 0}</span>
                </div>
                <div class="proc-meter">
                    <span class="proc-meter-label">Avg</span>
                    <div class="proc-meter-bar"><div class="proc-meter-fill gpu" style="width:60%"></div></div>
                    <span class="proc-meter-val">${w.avg_speed ? w.avg_speed + 's' : '—'}</span>
                </div>
            </div>
        `;
        container.appendChild(node);
    }
}

function startProcDashHWPolling() {
    if (_procDashInterval) clearInterval(_procDashInterval);
    console.log('[ProcDash] HW polling STARTED');

    // Do one immediate poll
    _pollHWMetrics();

    // Then repeat every 2s
    _procDashInterval = setInterval(_pollHWMetrics, 2000);
}

async function _pollHWMetrics() {
    try {
        const health = await fetch('/api/health').then(r => r.json());
        if (health.system) {
            const cpu = health.system.cpu_percent || 0;
            const gpu = health.system.gpu_percent || 0;
            const ram = health.system.ram_percent || 0;

            const cpuFill = document.getElementById('proc-master-cpu');
            const gpuFill = document.getElementById('proc-master-gpu');
            const ramFill = document.getElementById('proc-master-ram');
            const cpuVal = document.getElementById('proc-master-cpu-val');
            const gpuVal = document.getElementById('proc-master-gpu-val');
            const ramVal = document.getElementById('proc-master-ram-val');

            if (cpuFill) cpuFill.style.width = cpu + '%';
            if (gpuFill) gpuFill.style.width = gpu + '%';
            if (ramFill) ramFill.style.width = ram + '%';
            if (cpuVal) cpuVal.textContent = Math.round(cpu) + '%';
            if (gpuVal) gpuVal.textContent = Math.round(gpu) + '%';
            if (ramVal) ramVal.textContent = Math.round(ram) + '%';

            // Update chip name
            const chipEl = document.getElementById('proc-master-chip');
            if (chipEl && health.system.chip) chipEl.textContent = health.system.chip;

            // Per-core CPU heatmap + extra metrics (power, benchmark)
            const extrasEl = document.getElementById('proc-master-extras');
            if (extrasEl) {
                const cores = health.system.cpu_per_core || [];
                const power = health.system.power_watts || 0;
                const freq = health.system.cpu_freq_ghz || 0;
                const bench = health.system.benchmark_score || 0;
                const ane = health.system.ane_percent || 0;

                // Build core heatmap
                let coreHtml = '<div class="proc-core-map">';
                for (let i = 0; i < cores.length; i++) {
                    const pct = cores[i] || 0;
                    const hue = pct > 70 ? 0 : pct > 30 ? 40 : 120; // red/yellow/green
                    const opacity = Math.max(0.15, pct / 100);
                    coreHtml += `<div class="proc-core-cell" style="background:hsla(${hue},80%,50%,${opacity})" title="Core ${i}: ${Math.round(pct)}%"></div>`;
                }
                coreHtml += '</div>';

                // Build extra metrics row
                let extrasHtml = coreHtml;
                extrasHtml += `<div class="proc-extras-row">`;
                if (power > 0) extrasHtml += `<span class="proc-extra-chip">⚡ ${power.toFixed(1)}W</span>`;
                if (freq > 0) extrasHtml += `<span class="proc-extra-chip">🔄 ${freq.toFixed(1)} GHz</span>`;
                if (ane > 0) extrasHtml += `<span class="proc-extra-chip">🧠 ANE ${Math.round(ane)}%</span>`;
                if (bench > 0) extrasHtml += `<span class="proc-extra-chip bench">🏁 ${Math.round(bench)} ops/s</span>`;
                extrasHtml += `</div>`;

                extrasEl.innerHTML = extrasHtml;
            }
        }

        // Poll cluster status to update worker nodes
        const cluster = await fetch('/api/cluster/status').then(r => r.json());
        if (cluster) {
            _lastClusterData = cluster;
            renderWorkerNodes();
        }
    } catch (e) {
        console.warn('[ProcDash] HW poll error:', e);
    }
}

function stopProcDashHWPolling() {
    if (_procDashInterval) {
        clearInterval(_procDashInterval);
        _procDashInterval = null;
    }
}

// Map WebSocket step names to filter keys
const STEP_TO_FILTER = {
    'remove_noise': 'remove_noise',
    'wind': 'wind_noise_remover',
    'buzz': 'buzzing_noise_remover',
    'static': 'static_noise_remover',
    'reverb': 'reverb_echo_remover',
    'mouth': 'remove_mouth_sounds',
    'fillers': 'remove_filler_words',
    'hesitations': 'eliminate_hesitations',
    'stutter': 'remove_stuttering',
    'breaths': 'remove_breaths',
    'silence': 'remove_long_silences',
    'music': 'keep_music',
    'eq': 'auto_eq',
    'studio': 'studio_sound',
    'superres': 'frequency_restoration',
    'normalize': 'normalize',
    'tuning': '_tuning',
    'loading': '_loading',
    'cluster': '_cluster',
    'cluster_done': '_cluster_done',
};

function updatePipelineStep(stepName, message) {
    const filterKey = STEP_TO_FILTER[stepName] || stepName;

    // Handle cluster distribution messages
    if (stepName === 'cluster' || stepName === 'cluster_done') {
        // Mark DSP filters as distributed
        if (stepName === 'cluster_done' && _procHasEdgeWorkers) {
            for (const key of Object.keys(_procPipelineState)) {
                if (DSP_FILTERS.has(key) && _procPipelineState[key].status !== 'done') {
                    markStepDone(key, true);
                }
            }
        }
        return;
    }

    // If message contains ✓, mark the step as done
    if (message && message.includes('✓')) {
        // If still queued, mark active first (set startTime for elapsed calc)
        if (_procPipelineState[filterKey] && _procPipelineState[filterKey].status === 'queued') {
            _procPipelineState[filterKey].status = 'active';
            _procPipelineState[filterKey].startTime = _procPipelineState[filterKey].startTime || (Date.now() - 1000);
        }
        markStepDone(filterKey, false);
    } else if (_procPipelineState[filterKey] && _procPipelineState[filterKey].status === 'queued') {
        markStepActive(filterKey);
    }
}

function markStepActive(filterKey) {
    const pstate = _procPipelineState[filterKey];
    if (!pstate) return;

    // Deactivate previous active step (mark completed if not already)
    for (const [k, v] of Object.entries(_procPipelineState)) {
        if (v.status === 'active' && k !== filterKey) {
            const el = document.getElementById(`proc-step-${k}`);
            if (el) {
                el.className = 'proc-step active'; // keep as active, don't force done
            }
        }
    }

    pstate.status = 'active';
    pstate.startTime = Date.now();

    const el = document.getElementById(`proc-step-${filterKey}`);
    if (el) {
        el.className = 'proc-step active';
        el.querySelector('.proc-step-icon').textContent = '⟳';
    }
}

function markStepDone(filterKey, isDistributed) {
    const state = _procPipelineState[filterKey];
    if (!state) return;

    const prevActive = state.status === 'active';
    state.status = 'done';
    state.endTime = Date.now();

    const el = document.getElementById(`proc-step-${filterKey}`);
    if (el) {
        el.className = `proc-step done${isDistributed ? ' distributed' : ''}`;
        el.querySelector('.proc-step-icon').textContent = '✓';

        // Show elapsed time
        if (state.startTime) {
            const elapsed = ((state.endTime - state.startTime) / 1000).toFixed(1);
            const timeEl = document.getElementById(`proc-time-${filterKey}`);
            if (timeEl) timeEl.textContent = elapsed + 's';
        }

        // Update device badge if distributed
        if (isDistributed) {
            const badge = el.querySelector('.proc-device-badge');
            if (badge) {
                badge.className = 'proc-device-badge edge';
                badge.textContent = '📱 Edge Cluster';
            }
        }
    }

    // Activate next queued step
    for (const [k, v] of Object.entries(_procPipelineState)) {
        if (v.status === 'queued') {
            markStepActive(k);
            break;
        }
    }
}

// Cluster data cache for processing dashboard
let _lastClusterData = null;

// ══════════════════════════════════════════════════════════
// Settings Panel
// ══════════════════════════════════════════════════════════

function initSettingsPanel() {
    // LUFS slider live value
    const slider = document.getElementById('setting-loudness');
    const val = document.getElementById('setting-loudness-val');
    if (slider && val) {
        slider.addEventListener('input', () => {
            val.textContent = slider.value + ' LUFS';
        });
    }
}

// ══════════════════════════════════════════════════════════
// About Panel
// ══════════════════════════════════════════════════════════

async function initAboutPanel() {
    // Fetch acceleration info
    try {
        const accel = await fetch('/api/acceleration').then(r => r.json());
        const accelEl = document.getElementById('about-accel-list');
        if (accelEl && accel.accelerations) {
            accelEl.innerHTML = accel.accelerations.map(a =>
                `<div class="about-accel-item">${a}</div>`
            ).join('');
            if (accel.mps_available) {
                accelEl.innerHTML += `<div class="about-accel-item">✅ MPS Available</div>`;
            }
        }
    } catch (e) {
        console.warn('Accel info unavailable:', e);
    }

    // Fetch system + benchmark info
    try {
        const health = await fetch('/api/health').then(r => r.json());
        const sysEl = document.getElementById('about-sysinfo');
        if (sysEl && health.system) {
            const s = health.system;
            const items = [
                ['Chip', s.chip || 'Unknown'],
                ['CPU Cores', (s.cpu_per_core || []).length + ' cores'],
                ['CPU Freq', (s.cpu_freq_ghz || 0) + ' GHz'],
                ['RAM', (s.ram_used_gb || 0).toFixed(1) + ' / ' + (s.ram_total_gb || 0).toFixed(1) + ' GB'],
                ['GPU', health.compute || 'N/A'],
                ['MPS', health.mps_available ? '✅ Active' : '❌ Unavailable'],
                ['Version', health.version || '3.5.1'],
                ['Benchmark', (s.benchmark_score || 0) + ' ops/s'],
            ];
            sysEl.innerHTML = items.map(([label, value]) =>
                `<div class="about-sysinfo-item"><span class="label">${label}</span><span class="value">${value}</span></div>`
            ).join('');
        }

        // Update sidebar chip
        const sideChip = document.getElementById('sidebar-chip');
        if (sideChip && health.system && health.system.chip) {
            sideChip.textContent = health.system.chip.replace('Apple ', '');
        }
    } catch (e) {
        console.warn('System info unavailable:', e);
    }
}

// ══════════════════════════════════════════════════════════
// Sidebar Filter Labels — Edge / ML badges
// ══════════════════════════════════════════════════════════

function injectFilterCapabilityBadges() {
    // DSP filters that can run on edge workers
    const edgeCapable = {
        'remove_noise': true, 'wind_noise_remover': true, 'buzzing_noise_remover': true,
        'static_noise_remover': true, 'reverb_echo_remover': true, 'remove_mouth_sounds': true,
        'remove_breaths': true, 'remove_long_silences': true, 'auto_eq': true,
        'studio_sound': true, 'normalize': true, 'frequency_restoration': true,
    };
    // ML filters — local Whisper (ARM NEON optimized)
    const mlLocal = {
        'remove_filler_words': true, 'eliminate_hesitations': true,
        'remove_stuttering': true,
    };
    // GPU Metal filters — PyTorch MPS
    const gpuMetal = {
        'keep_music': true,  // Demucs uses MPS
    };

    document.querySelectorAll('.feature-item input[data-option]').forEach(input => {
        const key = input.dataset.option;
        const featureItem = input.closest('.feature-item');
        if (!featureItem) return;

        const nameEl = featureItem.querySelector('.feature-name');
        if (!nameEl || nameEl.querySelector('.feat-cap-badge')) return; // already injected

        let badge = null;
        if (gpuMetal[key]) {
            badge = document.createElement('span');
            badge.className = 'feat-cap-badge gpu';
            badge.textContent = '⬡ Metal';
            badge.title = 'GPU-accelerated via Apple Metal (MPS)';
        } else if (edgeCapable[key]) {
            badge = document.createElement('span');
            badge.className = 'feat-cap-badge edge';
            badge.textContent = 'Edge';
            badge.title = 'Can be offloaded to connected smartphones';
        } else if (mlLocal[key]) {
            badge = document.createElement('span');
            badge.className = 'feat-cap-badge ml';
            badge.textContent = 'ML';
            badge.title = 'AI inference via ARM NEON (CTranslate2)';
        }

        if (badge) {
            nameEl.appendChild(badge);
        }
    });
}

// CSS for the capability badges
(function() {
    const style = document.createElement('style');
    style.textContent = `
        .feat-cap-badge {
            display: inline-block;
            font-size: 0.55rem;
            font-weight: 700;
            padding: 1px 5px;
            border-radius: 6px;
            margin-left: 6px;
            vertical-align: middle;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        .feat-cap-badge.edge {
            background: rgba(6, 182, 212, 0.12);
            color: #67e8f9;
            border: 1px solid rgba(6, 182, 212, 0.2);
        }
        .feat-cap-badge.ml {
            background: rgba(245, 158, 11, 0.12);
            color: #fbbf24;
            border: 1px solid rgba(245, 158, 11, 0.2);
        }
        .feat-cap-badge.gpu {
            background: rgba(16, 185, 129, 0.12);
            color: #6ee7b7;
            border: 1px solid rgba(16, 185, 129, 0.25);
        }
    `;
    document.head.appendChild(style);
})();

// Inject badges on page load
document.addEventListener('DOMContentLoaded', () => {
    setTimeout(injectFilterCapabilityBadges, 500);
});
