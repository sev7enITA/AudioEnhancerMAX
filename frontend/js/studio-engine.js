(() => {
    const el = id => document.getElementById(id);
    const panel = el('project-studio-panel');
    if (!panel) return;

    const studio = el('project-studio');
    const path = '/api/studio/projects';
    const audio = el('studio-audio');
    const video = el('studio-video');
    const select = el('studio-project-select');
    const stage = el('studio-active-project');
    const status = el('studio-status');
    const progress = el('studio-progress');
    const duration = clip => clip.out_point - clip.in_point;
    const copy = value => JSON.parse(JSON.stringify(value));
    const token = () => crypto.randomUUID();
    const wait = ms => new Promise(resolve => setTimeout(resolve, ms));
    const asDocument = ({name, tracks, clips, markers, bpm, aspect}) => ({name, tracks, clips, markers, bpm, aspect});
    const studioTimeline = () => window.aemStudioTimeline;
    const items = new Map();
    const undo = [];
    const redo = [];
    let project;
    let selected;
    let playhead = 0;
    let pending = null;
    let saving = null;
    let saveTimer;
    let conflict = false;
    let previewRevision = 0;
    let activeJob = 0;
    let playToken = 0;
    let recorder = null;
    let relinkId;
    let reverseTimer;
    let isolationAvailable = false;
    let lastVideo;
    let projectTransition = 0;
    let microphonePending = false;
    let welcomePending = false;
    let playbackFrame = 0;
    let nextMeterUpdate = 0;
    let audioContext;
    let meterChannels = [];

    const tell = message => { status.textContent = message; };
    const selectedClip = () => project?.clips.find(clip => clip.id === selected);
    const assetFor = clip => project?.assets.find(asset => asset.id === clip?.asset_id);
    const location = () => `${path}/${project.id}`;

    async function request(url, body, method = 'POST') {
        const options = body === undefined ? {} : body instanceof FormData
            ? {method, body}
            : {method, headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)};
        const response = await fetch(url, {...options, cache:'no-store'});
        const result = await response.json().catch(() => ({}));
        if (!response.ok) {
            const error = new Error(typeof result.detail === 'string' ? result.detail : 'Studio could not complete the request.');
            error.status = response.status;
            throw error;
        }
        return result;
    }

    function action(label, handler, modifier) {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'studio-control';
        button.textContent = label;
        if (modifier) button.setAttribute('aria-label', modifier);
        button.addEventListener('click', () => perform(handler));
        return button;
    }

    function perform(handler) {
        Promise.resolve().then(handler).catch(error => tell(error.message));
    }

    function change(document, label, remember = true, affectsAudio = true) {
        if (!project) return;
        if (conflict) {
            tellsConflict();
            studioTimeline()?.setProject(project);
            return;
        }
        if (remember) {
            undo.push({document: copy(asDocument(project)), label});
            if (undo.length > 74) undo.shift();
            redo.length = 0;
        }
        Object.assign(project, copy(asDocument(document)));
        if (!selectedClip()) selected = null;
        if (affectsAudio) clearPreview();
        pending = {document: copy(asDocument(project)), label};
        clearTimeout(saveTimer);
        saveTimer = setTimeout(() => perform(flush), 450);
        refresh();
        tell('Saving changes…');
    }

    function tellsConflict() {
        el('studio-reload').hidden = false;
        tell('Project changed in another window. Use Reload project to continue.');
    }

    function flush() {
        clearTimeout(saveTimer);
        if (conflict) return Promise.reject(new Error('Reload the latest project before saving edits.'));
        if (!saving && pending) saving = drainSaves().finally(() => { saving = null; });
        return saving || Promise.resolve();
    }

    async function drainSaves() {
        while (pending) {
            const submitted = pending;
            pending = null;
            try {
                const saved = await request(location(), {...submitted, revision: project.revision}, 'PUT');
                project.revision = saved.revision;
                project.history = saved.history;
                const assets = new Map([...project.assets, ...saved.assets].map(asset => [asset.id, asset]));
                project.assets = [...assets.values()];
                renderHistory();
                if (!pending) tell(`Saved · revision ${saved.revision}`);
            } catch (error) {
                pending ||= submitted;
                conflict = error.status === 409;
                if (conflict) tellsConflict();
                throw error;
            }
        }
    }

    function clearPreview() {
        audio.pause();
        video.pause();
        clearInterval(reverseTimer);
        reverseTimer = null;
        previewRevision = 0;
        playToken += 1;
    }

    async function showProject(id, discard = false) {
        if (recorder || microphonePending) throw new Error('Stop the recording before switching projects.');
        const transition = ++projectTransition;
        if (!discard) await flush();
        else if (saving) await saving.catch(() => {});
        clearPreview();
        const loaded = await request(`${path}/${encodeURIComponent(id)}`);
        if (transition !== projectTransition) return;
        project = loaded;
        pending = null;
        conflict = false;
        selected = null;
        playhead = 0;
        lastVideo = null;
        audio.removeAttribute('src');
        video.removeAttribute('src');
        video.load();
        audio.load();
        items.clear();
        undo.length = redo.length = 0;
        const option = [...select.options].find(entry => entry.value === id);
        if (!option) select.add(new Option(project.name, id));
        select.value = id;
        stage.disabled = false;
        el('studio-reload').hidden = true;
        clearDownloads();
        refresh();
        seek(0);
        const missing = project.assets.filter(asset => !asset.available).length;
        tell(missing ? `${missing} source files need to be relinked.` : `Opened · revision ${project.revision}`);
    }

    async function initialize(preferredProject) {
        const loaded = await request(path);
        isolationAvailable = loaded.isolation_available;
        const isolate = panel.querySelector('[data-studio-action=isolate-voice]');
        if (isolate) {
            isolate.disabled = isolate.hidden = !isolationAvailable;
            isolate.title = isolationAvailable ? 'Create a separate voice asset' : 'Requires a local Demucs runtime and model';
        }
        select.replaceChildren(new Option('Choose a project', ''), ...loaded.projects.map(entry => new Option(entry.name, entry.id)));
        const requested = preferredProject || loaded.projects[0]?.id;
        if (requested) await showProject(requested);
    }

    function refresh() {
        if (!project) return;
        studio.dataset.aspect = project.aspect;
        const activeName = el('studio-active-name');
        if (activeName) activeName.textContent = project.name;
        for (const button of panel.querySelectorAll('[data-studio-aspect]')) {
            button.setAttribute('aria-pressed', String(button.dataset.studioAspect === project.aspect));
        }
        if (el('studio-bpm') !== document.activeElement) el('studio-bpm').value = project.bpm ?? '';
        studioTimeline()?.setProject(project);
        studioTimeline()?.setSelection(selected);
        studioTimeline()?.setPlayhead(playhead);
        el('studio-undo').disabled = !undo.length;
        el('studio-redo').disabled = !redo.length;
        const inspector = selectedClip();
        el('studio-inspector-empty').hidden = Boolean(inspector);
        el('studio-clip-fields').hidden = !inspector;
        el('studio-add-track').disabled = project.tracks.length >= 32;
        el('studio-add-marker').disabled = project.markers.length >= 128;
        el('studio-export').disabled = !project.clips.length;
        el('studio-play').disabled = !project.clips.length;
        const option = select.options[select.selectedIndex];
        if (option && option.value === project.id) option.text = project.name;
        el('studio-use-current').disabled = !state.fileId;
        renderAssets();
        renderHistory();
        renderInspector();
        renderVideo();
        loadTranscript();
    }

    function renderAssets() {
        const rows = project.assets.map(asset => {
            const row = document.createElement('li');
            row.className = 'studio-list-item';
            const title = document.createElement('span');
            title.textContent = asset.available ? asset.name : `${asset.name} · offline`;
            row.append(title, asset.available
                ? action('Add', () => addClip(asset), `Add ${asset.name} to timeline`)
                : action('Relink', () => {
                    relinkId = asset.id;
                    el('studio-relink-input').click();
                }, `Relink ${asset.name}`));
            return row;
        });
        el('studio-assets').replaceChildren(...rows);
    }

    function renderHistory() {
        const rows = project.history.map(entry => {
            const row = document.createElement('li');
            row.className = 'studio-list-item';
            const copy = document.createElement('span');
            copy.textContent = `r${entry.revision} · ${entry.label}`;
            copy.title = new Date(entry.time).toLocaleString();
            const restore = action('Restore', async () => {
                await flush();
                const before = asDocument(project);
                project = await request(`${location()}/restore`, {revision:project.revision,target:entry.revision});
                undo.push({document:copy(before),label:'Restore revision'});
                redo.length = 0;
                selected = null;
                clearPreview();
                refresh();
                tell(`Restored revision ${entry.revision}`);
            }, `Restore revision ${entry.revision}: ${entry.label}`);
            restore.disabled = entry.revision === project.revision;
            row.append(copy, restore);
            return row;
        });
        el('studio-history').replaceChildren(...rows);
    }

    const fields = {
        start:'start', in:'in_point', out:'out_point', 'fade-in':'fade_in', 'fade-out':'fade_out',
        gain:'gain_db', clarity:'clarity', warmth:'warmth', echo:'echo', eq:'eq_hz', ratio:'ratio', threshold:'threshold_db',
    };

    function renderInspector() {
        const clip = selectedClip();
        const t = el('studio-transcript');
        t.replaceChildren();
        if (!clip) return;
        for (const [id,key] of Object.entries(fields)) {
            const input = el(`studio-clip-${id}`);
            input.value = Number(clip[key] ?? {eq_hz:2200,ratio:1,threshold_db:-18}[key] ?? 0).toFixed(['start','in','out','fade-in','fade-out'].includes(id) ? 3 : 1);
        }
        el('studio-clip-bypass').checked = Boolean(clip.effects_bypass);
        const track = el('studio-clip-track');
        track.replaceChildren(...project.tracks.map(item => new Option(item.name, item.id)));
        track.value = clip.track_id;
        const points = el('studio-automation-points');
        points.replaceChildren(...(clip.automation || []).map((point, index) => {
            const row = document.createElement('li');
            row.className = 'studio-list-item';
            const caption = document.createElement('span');
            caption.textContent = `${point.time.toFixed(2)} s · ${point.db.toFixed(1)} dB`;
            row.append(caption, action('Remove', () => updateClip({...clip,
                automation:clip.automation.filter((_, position) => position !== index)}), 'Remove gain keyframe'));
            return row;
        }));
        for (const segment of (items.get(clip.asset_id) || []).filter(item => item.end > clip.in_point && item.start < clip.out_point)) {
            const row = document.createElement('li');
            const phrase = document.createElement('p');
            phrase.textContent = segment.text;
            row.append(phrase,
                action('Seek', () => seek(clip.start + Math.max(0, segment.start - clip.in_point)), `Seek to phrase ${segment.text}`),
                action('Cut', () => editPhrase(clip, segment, false), `Cut phrase ${segment.text}`),
                action('Move to playhead', () => editPhrase(clip, segment, true), `Move phrase ${segment.text} to playhead`));
            t.append(row);
        }
    }

    const transcriptReads = new Set();
    function loadTranscript() {
        const clip = selectedClip();
        const asset = assetFor(clip);
        if (!asset?.has_transcript || items.has(asset.id) || transcriptReads.has(asset.id)) return;
        const root = location();
        transcriptReads.add(asset.id);
        request(`${root}/assets/${asset.id}/transcript`).then(result => {
            if (location() !== root) return;
            items.set(asset.id, result.segments);
            if (selectedClip()?.asset_id === asset.id) renderInspector();
        }).catch(error => tell(error.message)).finally(() => transcriptReads.delete(asset.id));
    }

    function renderVideo() {
        const clip = selectedClip();
        const asset = assetFor(clip);
        const show = Boolean(asset?.available && asset.video);
        studio.dataset.media = show ? 'video' : clip ? 'audio' : 'empty';
        video.hidden = !show;
        const next = show ? asset.id : null;
        if (next !== lastVideo) {
            lastVideo = next;
            if (show) video.src = `${location()}/assets/${asset.id}/media?original=true`;
            else {
                video.pause();
                video.removeAttribute('src');
                video.load();
            }
        }
        alignVideo();
    }

    function alignVideo() {
        if (video.hidden || video.readyState === 0) return;
        const clip = selectedClip();
        const time = clip.in_point + playhead - clip.start;
        const position = Math.max(clip.in_point, Math.min(clip.out_point, time));
        if (Math.abs(video.currentTime - position) > 0.18) video.currentTime = position;
        if (audio.paused || time < clip.in_point || time >= clip.out_point) video.pause();
        else {
            if (video.playbackRate !== audio.playbackRate) video.playbackRate = audio.playbackRate;
            if (video.paused) video.play().catch(() => {});
        }
    }

    function makeClip(asset, trackId, start) {
        return {id:token(), asset_id:asset.id, track_id:trackId, start,
            in_point:0, out_point:asset.duration, fade_in:0, fade_out:0, gain_db:0,
            clarity:0, warmth:0, echo:0, automation:[]};
    }

    function addClip(asset, append = false) {
        if (project.clips.length >= 256) throw new Error('This project already contains 256 clips.');
        const trackId = selectedClip()?.track_id || project.tracks[0].id;
        const ends = project.clips.filter(item => item.track_id === trackId).map(item => item.start + duration(item));
        const start = append ? Math.max(playhead, ...ends) : playhead;
        const clip = makeClip(asset, trackId, start);
        if (clip.start + asset.duration > 7200) throw new Error('The clip would extend beyond the two-hour timeline.');
        selected = clip.id;
        change({...project, clips:[...project.clips, clip]}, 'Added clip');
    }

    function updateClip(clip, label = 'Adjusted clip') {
        const length = duration(clip);
        const asset = assetFor(clip);
        if (!asset || length < 0.01 || clip.start < 0 || clip.in_point < 0 || clip.out_point > asset.duration + 0.00002
            || clip.start + length > 7200 || Math.max(clip.fade_in, clip.fade_out) > length + 0.00002) {
            throw new Error('The adjustment goes beyond the clip or source.');
        }
        clip.automation = (clip.automation || []).filter(point => point.time <= length);
        change({...project, clips:project.clips.map(item => item.id === clip.id ? clip : item)}, label);
    }

    function substitute(clip, replacements, label) {
        const updated = project.clips.flatMap(item => item.id === clip.id ? replacements : [item]);
        if (updated.length > 256) throw new Error('This edit would create too many clips.');
        selected = replacements[0]?.id || null;
        change({...project, clips:updated}, label);
    }

    function slice(clip, first, last, start) {
        if (last - first < 0.01 - 1e-8) return null;
        return {...clip, id:token(), start, in_point:first, out_point:last,
            fade_in:first === clip.in_point ? Math.min(clip.fade_in, last - first) : 0,
            fade_out:last === clip.out_point ? Math.min(clip.fade_out, last - first) : 0,
            automation:(clip.automation || []).filter(point => point.time + clip.in_point >= first && point.time + clip.in_point <= last)
                .map(point => ({...point, time:point.time + clip.in_point - first}))};
    }

    function editPhrase(clip, phrase, move) {
        const first = Math.max(clip.in_point, phrase.start);
        const last = Math.min(clip.out_point, phrase.end);
        if (last - first < 0.01) return;
        if (move && playhead + last - first > 7200) throw new Error('The phrase would exceed the timeline.');
        const before = slice(clip, clip.in_point, first, clip.start);
        const after = slice(clip, last, clip.out_point, clip.start + first - clip.in_point);
        const moved = move ? slice(clip, first, last, playhead) : null;
        substitute(clip, [before, after, moved].filter(Boolean), move ? 'Moved spoken phrase' : 'Cut spoken phrase');
    }

    async function importInput(file, appending, relink) {
        if (!file || !project) return;
        const id = project.id;
        await flush();
        if (project.id !== id) return;
        const data = new FormData();
        data.set('file', file);
        const suffix = relink ? `/${relink}/relink` : '';
        const item = await busy('Importing media…', () => request(`${location()}/assets${suffix}`, data));
        if (project.id !== id) return;
        acceptAsset(item, appending);
        return item;
    }

    function acceptAsset(item, appending) {
        const index = project.assets.findIndex(asset => asset.id === item.id);
        if (index === -1) project.assets.push(item);
        else project.assets[index] = item;
        if (appending) addClip(item, true);
        else refresh();
        if (!pending) tell(item.name);
    }

    async function busy(label, operation) {
        activeJob += 1;
        progress.hidden = false;
        progress.removeAttribute('value');
        tell(label);
        try {
            return await operation();
        } finally {
            activeJob -= 1;
            progress.hidden = !activeJob;
        }
    }

    async function runJob(kind, asset_id = null, format = 'wav') {
        await flush();
        const root = location();
        const revision = project.revision;
        const response = await busy({
            preview:'Preparing mix preview…', render:'Rendering audio…', consolidate:'Collecting original sources…',
            transcribe:'Transcribing locally…', subtitles:'Preparing subtitles…', silences:'Finding silent gaps…', isolate:'Separating voice…',
        }[kind], async () => {
            let job = await request(`${root}/jobs`, {kind,revision,asset_id,format});
            while (job.status === 'running') {
                if (location() === root && activeJob === 1) progress.value = job.progress * 100;
                await wait(320);
                job = await request(`${root}/jobs/${job.id}`);
            }
            if (job.status !== 'complete') throw new Error(job.error || 'Studio job failed.');
            return job.result;
        });
        if (location() !== root) return null;
        return {...response, revision};
    }

    function seek(time) {
        const maximum = studioTimeline()?.duration() || 0;
        playhead = Math.max(0, Math.min(maximum, time));
        if (audio.src && Number.isFinite(audio.duration) && Math.abs(audio.currentTime - playhead) > 0.01) {
            audio.currentTime = Math.min(audio.duration, playhead);
        }
        drawPlayhead();
    }

    function drawPlayhead() {
        studioTimeline()?.setPlayhead(playhead);
        alignVideo();
    }

    function preparePlaybackMeter() {
        const meter = el('studio-live-meter');
        const AudioContext = window.AudioContext || window.webkitAudioContext;
        if (!meter || !AudioContext) return;
        if (!audioContext) {
            try {
                audioContext = new AudioContext();
                const source = audioContext.createMediaElementSource(audio);
                source.connect(audioContext.destination);
                const splitter = audioContext.createChannelSplitter(2);
                source.connect(splitter);
                meterChannels = ['left', 'right'].map((side, index) => {
                    const analyser = audioContext.createAnalyser();
                    analyser.fftSize = 1024;
                    splitter.connect(analyser, index);
                    return {analyser, samples:new Float32Array(analyser.fftSize), fill:el(`studio-level-${side}`)};
                });
            } catch {
                meterChannels = [];
                meter.hidden = true;
            }
        }
        if (audioContext?.state === 'suspended') audioContext.resume().catch(() => {});
    }

    function readPlaybackMeter() {
        if (!meterChannels.length) return;
        const hasSignal = meterChannels.map(({analyser, samples, fill}) => {
            analyser.getFloatTimeDomainData(samples);
            let peak = 0;
            for (const sample of samples) peak = Math.max(peak, Math.abs(sample));
            const level = Math.max(0, Math.min(1, (20 * Math.log10(peak) + 60) / 60));
            fill.style.setProperty('--studio-level', level.toFixed(3));
            return level > 0;
        }).some(Boolean);
        el('studio-live-meter').dataset.signal = hasSignal ? 'on' : 'off';
    }

    function playbackTick(timestamp) {
        if (audio.paused || audio.ended) return;
        playhead = audio.currentTime;
        drawPlayhead();
        if (timestamp >= nextMeterUpdate) {
            readPlaybackMeter();
            nextMeterUpdate = timestamp + 48;
        }
        playbackFrame = requestAnimationFrame(playbackTick);
    }

    function playbackState(playing) {
        const button = el('studio-play');
        const label = playing ? 'Pause' : 'Play';
        button.setAttribute('aria-pressed', String(playing));
        button.setAttribute('aria-label', label);
        const visibleLabel = button.querySelector('[data-studio-play-label]');
        if (visibleLabel) visibleLabel.textContent = label;
        studio.dataset.playing = String(playing);
        cancelAnimationFrame(playbackFrame);
        if (playing) {
            nextMeterUpdate = 0;
            playbackFrame = requestAnimationFrame(playbackTick);
        } else {
            for (const {fill} of meterChannels) fill.style.setProperty('--studio-level', '0');
            const meter = el('studio-live-meter');
            if (meter) meter.dataset.signal = 'off';
            video.pause();
        }
    }

    async function play(rate = 1) {
        if (!project || !project.clips.length) return;
        preparePlaybackMeter();
        clearInterval(reverseTimer);
        reverseTimer = null;
        const token = ++playToken;
        if (!previewRevision) {
            const result = await runJob('preview');
            if (!result || token !== playToken) return;
            audio.src = result.url;
            previewRevision = result.revision;
        }
        if (token !== playToken) return;
        if (audio.ended) seek(0);
        audio.currentTime = playhead;
        audio.playbackRate = Math.min(4, Math.max(0.5, rate));
        await audio.play();
        tell('Playing project');
    }

    function pause() {
        const wasPlaying = !audio.paused;
        playToken += 1;
        audio.pause();
        video.pause();
        clearInterval(reverseTimer);
        reverseTimer = null;
        if (wasPlaying) tell('Playback paused');
    }

    function transport(event) {
        const {action, rate} = event.detail;
        if (action === 'pause') pause();
        if (action === 'toggle') {
            if (audio.paused && !reverseTimer) return play();
            pause();
        }
        if (action === 'shuttle') {
            if (rate >= 0) return play(rate || 1);
            pause();
            reverseTimer = setInterval(() => {
                seek(playhead + rate * 0.045);
                if (playhead === 0) pause();
            }, 45);
        }
    }

    function clearDownloads() {
        for (const id of ['studio-consolidation-download', 'studio-render-download', 'studio-render-report', 'studio-subtitles-link']) {
            const link = el(id);
            if (!link) continue;
            if (link.href.startsWith('blob:')) URL.revokeObjectURL(link.href);
            link.removeAttribute('href');
            link.hidden = true;
        }
    }

    async function exportFile(kind) {
        const result = await runJob(kind, null, el('studio-format').value || 'wav');
        if (!result) return;
        const link = el(kind === 'consolidate' ? 'studio-consolidation-download' : 'studio-render-download');
        link.href = result.url;
        link.hidden = false;
        if (kind === 'consolidate') link.click();
        link.textContent = kind === 'render' ? `Download audio · r${result.revision}` : `Download project · r${result.revision}`;
        if (kind === 'render' && el('studio-render-report')) {
            el('studio-render-report').href = result.report_url;
            el('studio-render-report').hidden = false;
        }
        tell(result.clipped ? 'Render complete. The mix exceeded 0 dBFS. Lower gain and render again.' :
            kind === 'render' ? 'Audio render complete' : 'Portable project folder is ready to download');
    }

    function undoOrRedo(isUndo) {
        const from = isUndo ? undo : redo;
        const to = isUndo ? redo : undo;
        const step = from.pop();
        if (!step) return;
        to.push({document:copy(asDocument(project)),label:step.label});
        change(step.document, `${isUndo ? 'Undid' : 'Redid'} ${step.label}`.slice(0,100), false);
    }

    function addTrack() {
        if (project.tracks.length >= 32) return;
        change({...project, tracks:[...project.tracks, {id:token(),name:`Audio ${project.tracks.length + 1}`,muted:false}]}, 'Added track');
    }

    function addMarker() {
        if (project.markers.length >= 128) return;
        change({...project, markers:[...project.markers,{time:playhead,label:`Marker ${project.markers.length + 1}`}]}, 'Added marker');
    }

    async function contextAction(kind) {
        const clip = selectedClip();
        if (!clip) return;
        if (kind === 'remove-clip') substitute(clip, [], 'Removed clip');
        if (kind === 'automation') {
            const time = Math.max(0, Math.min(duration(clip), playhead - clip.start));
            const field = el('studio-keyframe-gain');
            if (!field.reportValidity()) return;
            const db = Number(field.value);
            const automation = (clip.automation || []).filter(point => Math.abs(point.time - time) > 0.01);
            if (automation.length >= 100) throw new Error('A clip can have up to 100 gain points.');
            automation.push({time,db});
            updateClip({...clip, automation}, 'Set gain automation');
        }
        if (kind === 'align-beat') {
            if (!project.bpm) throw new Error('Set a tempo before aligning a clip.');
            const beat = 60 / project.bpm;
            updateClip({...clip, start:Math.round(clip.start / beat) * beat}, 'Aligned clip to beat');
        }
        const jobs = {'remove-silences':'silences','isolate-voice':'isolate',transcribe:'transcribe',subtitles:'subtitles'};
        if (!jobs[kind]) return;
        const result = await runJob(jobs[kind], clip.asset_id);
        if (!result) return;
        const current = project.clips.find(item => item.id === clip.id);
        if (kind === 'isolate-voice') {
            acceptAsset(result, false);
            tell('Voice asset added. Use Add to place it on the timeline.');
            return;
        }
        if (kind === 'remove-silences') {
            if (!current || pending || project.revision !== result.revision) {
                tell('The clip changed while it was being analysed. Run the analysis again.');
                return;
            }
            let cursor = current.in_point;
            let next = current.start;
            const remaining = [];
            for (const [start, end] of result.regions) {
                if (end <= cursor || start >= current.out_point) continue;
                const part = slice(current, cursor, Math.max(cursor, start), next);
                if (part) { remaining.push(part); next += duration(part); }
                cursor = Math.min(current.out_point, end);
            }
            const last = slice(current, cursor, current.out_point, next);
            if (last) remaining.push(last);
            if (remaining.length === 1 && duration(remaining[0]) === duration(current)) tell('No long silences found in this clip.');
            else substitute(current, remaining, 'Removed long silences');
            return;
        }
        items.set(clip.asset_id, result.segments);
        renderInspector();
        if (kind === 'subtitles') {
            const link = el('studio-subtitles-link');
            if (link.href.startsWith('blob:')) URL.revokeObjectURL(link.href);
            link.href = URL.createObjectURL(new Blob([result.srt], {type:'application/x-subrip'}));
            link.download = 'AudioEnhancerMAX-subtitles.srt';
            link.hidden = false;
        }
        tell(kind === 'subtitles' ? 'Subtitles ready' : 'Transcript ready');
    }

    async function record() {
        if (recorder || microphonePending) return;
        if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) throw new Error('Microphone recording is unavailable in this runtime.');
        microphonePending = true;
        let stream;
        try { stream = await navigator.mediaDevices.getUserMedia({audio:true}); }
        finally { microphonePending = false; }
        const candidates = ['audio/mp4','audio/webm;codecs=opus','audio/webm'];
        const mimeType = candidates.find(type => MediaRecorder.isTypeSupported(type));
        const chunks = [];
        let recordedBytes = 0;
        let session;
        try {
            session = new MediaRecorder(stream, mimeType ? {mimeType} : {});
            session.addEventListener('dataavailable', event => {
                if (!event.data.size) return;
                recordedBytes += event.data.size;
                if (recordedBytes <= 480 * 1024 * 1024) chunks.push(event.data);
                else if (session.state === 'recording') session.stop();
            });
            session.addEventListener('stop', () => {
                stream.getTracks().forEach(track => track.stop());
                recorder = null;
                studio.dataset.recording = 'false';
                el('studio-record-start').disabled = false;
                el('studio-record-stop').disabled = el('studio-record-stop').hidden = true;
                el('studio-record-status').textContent = 'Recording finished';
                const type = session.mimeType || mimeType || 'audio/webm';
                const extension = type.includes('mp4') ? 'm4a' : 'webm';
                if (chunks.length) perform(() => importInput(new File(chunks, `Recording ${new Date().toISOString().slice(0,19).replaceAll(':','-')}.${extension}`, {type}), true));
            }, {once:true});
            session.start(1000);
        } catch (error) {
            stream.getTracks().forEach(track => track.stop());
            throw error;
        }
        recorder = session;
        studio.dataset.recording = 'true';
        el('studio-record-start').disabled = true;
        el('studio-record-stop').disabled = el('studio-record-stop').hidden = false;
        el('studio-record-status').textContent = 'Microphone recording';
        tell('Microphone recording');
    }

    el('studio-project-form').addEventListener('submit', event => {
        event.preventDefault();
        perform(async () => {
            await flush();
            const created = await request(path,{name:el('studio-project-name').value.trim()});
            await addOptionAndOpen(created);
        });
    });
    async function addOptionAndOpen(created) {
        await showProject(created.id);
        el('studio-new-dialog').close();
    }
    select.addEventListener('change', () => {
        if (!select.value) return;
        const requested = select.value;
        if (project) select.value = project.id;
        perform(() => showProject(requested));
    });
    const on = (id, handler) => el(id)?.addEventListener('click', () => perform(handler));
    on('studio-import', () => el('studio-file-input').click());
    el('studio-welcome-import')?.addEventListener('click', () => el('studio-file-input').click());
    on('studio-welcome-sample', () => startWithFile());
    on('studio-reload', () => {
        if (window.confirm('Reload the saved project and discard the current unsaved changes?')) return showProject(project.id, true);
    });
    on('studio-project-bundle', () => el('studio-bundle-input').click());
    el('studio-bundle-input')?.addEventListener('change', event => {
        const [file] = event.target.files;
        event.target.value = '';
        if (!file) return;
        perform(async () => {
            await flush();
            const body = new FormData();
            body.set('file', file);
            const restored = await busy('Opening consolidated project…', () => request(`${path}/from-package`,body));
            await showProject(restored.id);
        });
    });
    on('studio-use-current', async () => {
        if (!state.fileId) throw new Error('Open an audio file in Home first.');
        await flush();
        const id = project.id;
        const item = await busy('Copying the source into the project…', () => request(`${location()}/assets/from-workspace`,
            {file_id:state.fileId,name:state.fileName}));
        if (project?.id === id) acceptAsset(item, true);
    });
    el('studio-file-input').addEventListener('change', event => {
        const [file] = event.target.files;
        event.target.value = '';
        if (file) perform(() => project ? importInput(file, true) : startWithFile(file));
    });
    async function startWithFile(file) {
        if (welcomePending) return;
        welcomePending = true;
        const welcomeButtons = ['studio-welcome-import', 'studio-welcome-sample'].map(el).filter(Boolean);
        for (const button of welcomeButtons) button.disabled = true;
        try {
            const isSample = !file;
            if (isSample) {
                const response = await fetch('/static/media/studio-sample.wav');
                if (!response.ok) throw new Error('The bundled sample could not be opened.');
                file = new File([await response.blob()], 'Studio sample.wav', {type:'audio/wav'});
            }
            const name = isSample ? 'Studio sample' : file.name.replace(/\.[^.]+$/, '').trim().slice(0, 100) || 'New project';
            await flush();
            const created = await request(path, {name});
            await showProject(created.id);
            if (project.id !== created.id) return;
            const item = await importInput(file, !isSample);
            if (isSample && item) {
                const [firstTrack] = project.tracks;
                const secondTrack = {id:token(), name:'Audio 2', muted:false};
                const cut = 5;
                const first = {...makeClip(item, firstTrack.id, 0), out_point:cut};
                const second = {...makeClip(item, secondTrack.id, cut), in_point:cut};
                selected = first.id;
                change({...project, tracks:[firstTrack, secondTrack], clips:[first, second]}, 'Opened sample edit');
            }
            el('studio-timeline').focus({preventScroll:true});
        } finally {
            welcomePending = false;
            for (const button of welcomeButtons) button.disabled = false;
        }
    }
    el('studio-relink-input').addEventListener('change', event => {
        const [file] = event.target.files;
        const identity = relinkId;
        event.target.value = '';
        relinkId = null;
        perform(() => importInput(file, false, identity));
    });
    on('studio-add-track', addTrack);
    on('studio-add-marker', addMarker);
    on('studio-play', () => transport({detail:{action:'toggle'}}));
    on('studio-stop', () => { pause(); seek(0); });
    on('studio-export', () => exportFile('render'));
    on('studio-consolidate', () => exportFile('consolidate'));
    on('studio-undo', () => undoOrRedo(true));
    on('studio-redo', () => undoOrRedo(false));
    on('studio-record-start', record);
    on('studio-record-stop', () => recorder?.stop());
    el('studio-bpm').addEventListener('change', event => {
        if (project && event.target.reportValidity()) change({...project, bpm:event.target.value ? Number(event.target.value) : null}, 'Set beat grid');
    });
    for (const [id,key] of Object.entries(fields)) {
        el(`studio-clip-${id}`).addEventListener('change', event => perform(() => {
            if (event.target.reportValidity()) updateClip({...selectedClip(),[key]:Number(event.target.value)});
        }));
    }
    el('studio-clip-bypass').addEventListener('change', event => perform(() => updateClip({...selectedClip(),effects_bypass:event.target.checked}, 'Changed effect bypass')));
    el('studio-clip-track').addEventListener('change', event => perform(() => updateClip({...selectedClip(),track_id:event.target.value})));
    for (const button of panel.querySelectorAll('[data-studio-action]')) {
        button.addEventListener('click', () => perform(() => contextAction(button.dataset.studioAction)));
    }
    audio.addEventListener('timeupdate', () => {
        if (!audio.paused || audio.ended) {
            playhead = audio.currentTime;
            drawPlayhead();
        }
    });
    audio.addEventListener('play', () => playbackState(true));
    audio.addEventListener('pause', () => playbackState(false));
    audio.addEventListener('ended', () => {
        playbackState(false);
        tell('Playback finished');
    });
    video.addEventListener('loadedmetadata', alignVideo);
    video.addEventListener('error', () => tell('This video codec cannot be previewed. Its audio is available.'));
    document.addEventListener('studio:aspect', event => {
        if (project && project.aspect !== event.detail.aspect) change({...project, aspect:event.detail.aspect}, 'Changed preview aspect', true, false);
    });
    document.addEventListener('aem-studio-change', event => change(event.detail.project, event.detail.label));
    document.addEventListener('aem-studio-select', event => {
        selected = event.detail.clipId;
        refresh();
    });
    document.addEventListener('aem-studio-seek', event => seek(event.detail.time));
    document.addEventListener('aem-studio-transport', event => perform(() => transport(event)));
    document.addEventListener('aem-studio-notice', event => tell(event.detail.message));
    document.addEventListener('aem-studio-command', event => {
        if (!project) return;
        const handlers = {undo:()=>undoOrRedo(true), redo:()=>undoOrRedo(false), render:()=>exportFile('render'),
            consolidate:()=>exportFile('consolidate'), import:()=>el('studio-file-input').click(), marker:addMarker,
            'track-add':addTrack, 'remove-silences':()=>contextAction('remove-silences'), transcribe:()=>contextAction('transcribe')};
        if (handlers[event.detail.action]) perform(handlers[event.detail.action]);
    });
    window.addEventListener('beforeunload', event => {
        if (pending || saving || recorder || microphonePending) {
            event.preventDefault();
            event.returnValue = '';
        }
    });
    let checkingMedia = false;
    setInterval(async () => {
        if (!panel.classList.contains('active') || !project || !project.assets.length || checkingMedia) return;
        const root = location();
        checkingMedia = true;
        try {
            const result = await request(`${root}/availability`);
            if (location() !== root) return;
            let missing = 0;
            let changed = false;
            for (const asset of project.assets) {
                const available = result[asset.id];
                if (typeof available !== 'boolean' || available === asset.available) continue;
                asset.available = available;
                changed = true;
                if (!available) missing += 1;
            }
            if (changed) {
                renderAssets();
                renderVideo();
            }
            if (missing) tell(missing === 1 ? 'A source went offline. Use Relink in Media.' :
                `${missing} sources went offline. Use Relink in Media.`);
        } catch {
            // A transient status request must not overwrite an active job message.
        } finally {
            checkingMedia = false;
        }
    }, 3500);
    let initialized = false;
    let initializing;
    async function loadStudio(preferredProject) {
        if (initializing) await initializing;
        if (initialized) {
            if (preferredProject && preferredProject !== project?.id) await showProject(preferredProject);
            else if (project) refresh();
            return;
        }
        studio.dataset.loading = 'true';
        tell('Loading projects…');
        initializing = initialize(preferredProject).then(() => {
            initialized = true;
            if (!project) tell('Ready.');
        }).finally(() => {
            initializing = null;
            delete studio.dataset.loading;
        });
        await initializing;
    }
    window.aemStudioProjects = {
        open: loadStudio,
        async openSample() {
            await loadStudio();
            await startWithFile();
        },
    };
    function activateStudio() {
        if (panel.classList.contains('active')) perform(() => loadStudio());
    }
    new MutationObserver(activateStudio).observe(panel, {attributes:true, attributeFilter:['class']});
    activateStudio();
})();
