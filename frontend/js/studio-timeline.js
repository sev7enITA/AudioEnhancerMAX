(() => {
    'use strict';

    const LABEL_WIDTH = 96;
    // Leave one edit tick past the 10 ms API minimum to avoid rounding a trim below it.
    const MIN_CLIP_SECONDS = 0.0101;
    const MAX_PROJECT_SECONDS = 7200;
    const MAX_STAGE_WIDTH = 3_000_000;
    const DEFAULT_SHORTCUTS = Object.freeze({
        toggle: 'Space',
        backward: 'J',
        pause: 'K',
        forward: 'L',
        split: 'S',
        undo: 'Mod+Z',
        redo: 'Mod+Shift+Z',
        marker: 'M',
        palette: 'Mod+K',
    });
    const SHORTCUT_LABELS = {
        toggle: 'Play or pause', backward: 'Shuttle backward', pause: 'Pause',
        forward: 'Shuttle forward', split: 'Split clip', undo: 'Undo',
        redo: 'Redo', marker: 'Add marker', palette: 'Find a tool or action',
    };
    const SHORTCUTS_KEY = 'aemax.studio.shortcuts.v1';

    const byId = id => document.getElementById(id);
    const viewport = byId('studio-timeline');
    const zoom = byId('studio-zoom');
    const snapping = byId('studio-snap');
    if (!viewport || !zoom || !snapping) return;

    const make = (tag, className, label) => {
        const node = document.createElement(tag);
        node.className = className;
        if (label) node.textContent = label;
        return node;
    };
    const emit = (type, detail) => document.dispatchEvent(new CustomEvent(`aem-studio-${type}`, {detail}));
    const clamp = (value, minimum, maximum) => Math.max(minimum, Math.min(maximum, value));
    const roundTime = value => Math.round(value * 10_000) / 10_000;
    const clipLength = clip => clip.out_point - clip.in_point;
    const clipEnd = clip => clip.start + clipLength(clip);
    const px = value => `${value}px`;

    const surface = make('div', 'studio-waveform-layer');
    const stage = make('div', 'studio-timeline-stage');
    const ruler = make('div', 'studio-ruler');
    const ticks = make('div', 'studio-ruler-ticks');
    const markers = make('div', 'studio-marker-layer');
    ruler.append(ticks, markers);
    const tracks = make('div', 'studio-tracks');
    const playhead = make('div', 'studio-playhead');
    const guide = make('div', 'studio-snap-guide');
    guide.hidden = true;
    [surface, playhead, guide].forEach(node => node.setAttribute('aria-hidden', 'true'));
    stage.append(ruler, tracks, playhead, guide);
    viewport.append(surface, stage);

    let project = null;
    let selectedId = null;
    let playheadTime = 0;
    let pixelsPerSecond = 80;
    let duration = 0;
    let drag = null;
    let drawFrame = 0;
    let rulerFrame = 0;
    let rulerKey = '';
    let shuttleRate = 0;
    let shortcuts = loadShortcuts();
    let renderedView;
    let assetById = new Map();
    let rowById = new Map();
    let clipNodes = new Map();

    const waves = makeWavePainter(surface);

    function loadShortcuts() {
        try {
            const saved = JSON.parse(localStorage.getItem(SHORTCUTS_KEY) || '{}');
            const merged = {...DEFAULT_SHORTCUTS};
            for (const action of Object.keys(merged)) {
                if (typeof saved?.[action] === 'string') merged[action] = saved[action];
            }
            return merged;
        } catch {
            return {...DEFAULT_SHORTCUTS};
        }
    }

    function timeLabel(seconds, fractions = false) {
        const milliseconds = Math.round(Math.max(0, seconds) * 1000);
        const hours = Math.floor(milliseconds / 3_600_000);
        const minutes = Math.floor(milliseconds / 60_000) % 60;
        const whole = Math.floor(milliseconds / 1000) % 60;
        const suffix = fractions ? `.${String(milliseconds % 1000).padStart(3, '0')}` : '';
        const lead = hours ? `${hours}:${String(minutes).padStart(2, '0')}` : String(minutes);
        return `${lead}:${String(whole).padStart(2, '0')}${suffix}`;
    }

    function setPlayhead(seconds) {
        if (!Number.isFinite(seconds)) return;
        playheadTime = clamp(seconds, 0, duration);
        playhead.style.left = px(LABEL_WIDTH + playheadTime * pixelsPerSecond);
        const display = byId('studio-time');
        if (display) display.textContent = `${timeLabel(playheadTime, true)} / ${timeLabel(duration, true)}`;
    }

    function seek(seconds) {
        setPlayhead(seconds);
        emit('seek', {time: playheadTime});
    }

    function setSelection(clipId) {
        const next = clipId && clipNodes.has(clipId) ? clipId : null;
        if (next === selectedId) return;
        clipNodes.get(selectedId)?.setAttribute('aria-pressed', 'false');
        selectedId = next;
        clipNodes.get(selectedId)?.setAttribute('aria-pressed', 'true');
    }

    function select(id) {
        setSelection(id);
        emit('select', {clipId: selectedId});
    }

    function setProject(next) {
        const changedProject = next?.id !== project?.id;
        const wasEmpty = !duration;
        if (changedProject) {
            playheadTime = 0;
            selectedId = null;
            viewport.scrollLeft = 0;
        }
        project = next;
        const assets = project?.assets || [];
        if (!changedProject && renderedView && renderedView.clips === project?.clips && renderedView.tracks === project?.tracks
                && renderedView.markers === project?.markers && renderedView.bpm === project?.bpm
                && renderedView.assets.length === assets.length && renderedView.assets.every((asset, index) => asset === assets[index])) return;
        renderedView = {clips: project?.clips, tracks: project?.tracks, markers: project?.markers, bpm: project?.bpm, assets: [...assets]};
        duration = Math.max(0, ...(project?.clips || []).map(clipEnd));
        assetById = new Map(assets.map(asset => [asset.id, asset]));
        if (changedProject || (wasEmpty && duration)) updateScale();
        drawLayout();
    }

    function updateScale() {
        const available = Math.max(280, viewport.clientWidth - LABEL_WIDTH);
        const fit = available / Math.max(duration * 1.06, 5);
        pixelsPerSecond = clamp(Math.min(100, fit) * Number(zoom.value || 1), 0.002, 1500);
        pixelsPerSecond = Math.min(pixelsPerSecond, (MAX_STAGE_WIDTH - LABEL_WIDTH) / Math.max(duration, 5));
    }

    function drawLayout() {
        const focusId = document.activeElement?.closest('.studio-clip')?.dataset.clipId;
        const focusedTrack = document.activeElement?.closest('.studio-track-mute')?.dataset.muteTrackId;
        const width = Math.max(viewport.clientWidth, LABEL_WIDTH + duration * pixelsPerSecond + 28, 300);
        stage.style.width = px(Math.min(MAX_STAGE_WIDTH, width));
        rowById = new Map();
        clipNodes = new Map();
        tracks.replaceChildren();
        if (!project?.tracks?.length) {
            tracks.append(make('p', 'studio-timeline-empty', 'Add a recording or an audio file to start editing.'));
        }
        for (const track of project?.tracks || []) {
            const lane = make('div', 'studio-track-lane');
            lane.dataset.trackId = track.id;
            lane.setAttribute('aria-label', track.muted ? `${track.name}, muted` : track.name);
            lane.classList.toggle('is-muted', Boolean(track.muted));
            const label = make('div', 'studio-track-label');
            const mute = make('button', 'studio-track-mute', 'M');
            mute.type = 'button';
            mute.dataset.muteTrackId = track.id;
            mute.title = `Mute ${track.name}`;
            mute.setAttribute('aria-label', mute.title);
            mute.setAttribute('aria-pressed', String(Boolean(track.muted)));
            mute.addEventListener('click', () => {
                const next = project.tracks.map(item => item.id === track.id ? {...item, muted: !item.muted} : item);
                const message = track.muted ? 'Unmute track' : 'Mute track';
                setProject({...project, tracks: next});
                emit('change', {project, label: message});
            });
            label.append(make('span', 'studio-track-name', track.name), mute);
            lane.append(label);
            tracks.append(lane);
            rowById.set(track.id, lane);
        }
        for (const clip of project?.clips || []) {
            const lane = rowById.get(clip.track_id);
            if (!lane) continue;
            const asset = assetById.get(clip.asset_id);
            const button = make('button', 'studio-clip');
            button.type = 'button';
            button.dataset.clipId = clip.id;
            button.setAttribute('aria-pressed', String(clip.id === selectedId));
            const label = asset?.name || 'Audio clip';
            const availability = asset?.available === false ? ', offline' : '';
            button.setAttribute('aria-label', `${label}, ${timeLabel(clip.start, true)} to ${timeLabel(clipEnd(clip), true)}${availability}`);
            button.classList.toggle('is-offline', asset?.available === false);
            button.append(make('span', 'studio-clip-title', asset?.available === false ? `${label} · offline` : label));
            button.append(make('span', 'studio-fade studio-fade-in'), make('span', 'studio-fade studio-fade-out'));
            drawAutomation(button, clip);
            lane.append(button);
            clipNodes.set(clip.id, button);
            positionClip(button, clip);
        }
        drawCrossfades();
        setSelection(selectedId);
        setPlayhead(playheadTime);
        drawRuler();
        drawMarkers();
        requestWaves();
        if (focusId) clipNodes.get(focusId)?.focus({preventScroll: true});
        if (focusedTrack) rowById.get(focusedTrack)?.querySelector('.studio-track-mute')?.focus({preventScroll: true});
    }

    function positionClip(node, clip) {
        const length = Math.max(MIN_CLIP_SECONDS, clipLength(clip));
        node.style.left = px(LABEL_WIDTH + clip.start * pixelsPerSecond);
        node.style.width = px(Math.max(8, length * pixelsPerSecond));
        node.style.setProperty('--fade-in', `${100 * clamp(clip.fade_in || 0, 0, length) / length}%`);
        node.style.setProperty('--fade-out', `${100 * clamp(clip.fade_out || 0, 0, length) / length}%`);
    }

    function drawCrossfades() {
        for (const track of project?.tracks || []) {
            const clips = project.clips.filter(clip => clip.track_id === track.id).sort((a, b) => a.start - b.start);
            const intervals = new Map(clips.map(clip => [clip.id, []]));
            // The mixer applies these ramps only to partial overlaps on a track.
            for (const [index, left] of clips.entries()) {
                const end = clipEnd(left);
                for (const right of clips.slice(index + 1)) {
                    if (right.start >= end) break;
                    if (right.start > left.start && clipEnd(right) > end) {
                        intervals.get(left.id).push([right.start, end]);
                        intervals.get(right.id).push([right.start, end]);
                    }
                }
            }
            for (const clip of clips) {
                const bands = [];
                for (const interval of intervals.get(clip.id).sort((a, b) => a[0] - b[0])) {
                    const previous = bands.at(-1);
                    if (previous && interval[0] <= previous[1]) previous[1] = Math.max(previous[1], interval[1]);
                    else bands.push(interval);
                }
                for (const [start, end] of bands) {
                    const node = make('span', 'studio-crossfade');
                    node.style.left = `${100 * (start - clip.start) / clipLength(clip)}%`;
                    node.style.width = `${100 * (end - start) / clipLength(clip)}%`;
                    node.title = `Equal-power crossfade, ${(end - start).toFixed(2)} seconds`;
                    clipNodes.get(clip.id)?.append(node);
                }
            }
        }
    }

    function drawAutomation(button, clip) {
        if (!clip.automation?.length) return;
        const width = Math.max(8, clipLength(clip) * pixelsPerSecond);
        const height = 62;
        const overlay = make('span', 'studio-automation');
        overlay.setAttribute('aria-hidden', 'true');
        let previous = null;
        const points = [...clip.automation].sort((a, b) => a.time - b.time);
        if (points[0].time > 0) points.unshift({...points[0], time: 0});
        if (points.at(-1).time < clipLength(clip)) points.push({...points.at(-1), time: clipLength(clip)});
        for (const point of points) {
            const x = clamp(point.time / clipLength(clip), 0, 1) * width;
            const y = height * (0.15 + 0.8 * (1 - clamp((point.db + 48) / 60, 0, 1)));
            const dot = make('span', 'studio-automation-dot');
            dot.style.left = px(x);
            dot.style.top = px(y);
            overlay.append(dot);
            if (previous) {
                const dx = x - previous.x;
                const dy = y - previous.y;
                const line = make('span', 'studio-automation-segment');
                line.style.left = px(previous.x);
                line.style.top = px(previous.y);
                line.style.width = px(Math.hypot(dx, dy));
                line.style.transform = `rotate(${Math.atan2(dy, dx)}rad)`;
                overlay.append(line);
            }
            previous = {x, y};
        }
        button.append(overlay);
    }

    function drawRuler() {
        const candidates = [0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10, 15, 30, 60, 120, 300, 600, 1800, 3600];
        const interval = candidates.find(value => value * pixelsPerSecond >= 70) || 7200;
        const first = Math.max(0, (viewport.scrollLeft - LABEL_WIDTH) / pixelsPerSecond);
        const last = (viewport.scrollLeft + viewport.clientWidth) / pixelsPerSecond;
        const key = `${pixelsPerSecond},${viewport.clientWidth},${project?.bpm},${Math.floor(first / interval)},${Math.ceil(last / interval)}`;
        if (key === rulerKey) return;
        rulerKey = key;
        stage.style.setProperty('--studio-grid-step', px(interval * pixelsPerSecond));
        stage.style.setProperty('--studio-grid-start', px(LABEL_WIDTH));
        const fragment = document.createDocumentFragment();
        for (let index = Math.floor(first / interval); index <= Math.ceil(last / interval); index++) {
            const time = index * interval;
            const tick = make('span', 'studio-ruler-tick', timeLabel(time, interval < 1));
            tick.style.left = px(LABEL_WIDTH + time * pixelsPerSecond);
            tick.setAttribute('aria-hidden', 'true');
            fragment.append(tick);
        }
        if (project?.bpm > 0) {
            const timePerBeat = 60 / project.bpm;
            const visibleStep = timePerBeat * pixelsPerSecond >= 16 ? 1 : 4;
            if (timePerBeat * pixelsPerSecond * visibleStep >= 12) {
                const lower = Math.floor(first / interval) * interval;
                const upper = Math.ceil(last / interval) * interval;
                for (let beat = Math.ceil(lower / timePerBeat / visibleStep) * visibleStep; beat * timePerBeat <= upper; beat += visibleStep) {
                    const tick = make('span', 'studio-beat-tick');
                    tick.style.left = px(LABEL_WIDTH + beat * timePerBeat * pixelsPerSecond);
                    tick.setAttribute('aria-hidden', 'true');
                    fragment.append(tick);
                }
            }
        }
        ticks.replaceChildren(fragment);
    }

    function drawMarkers() {
        const markerFocus = document.activeElement?.closest('.studio-marker')?.dataset.markerIndex;
        const fragment = document.createDocumentFragment();
        for (const [index, marker] of (project?.markers || []).entries()) {
            const node = make('button', 'studio-marker', marker.label || 'Marker');
            node.type = 'button';
            node.dataset.markerIndex = index;
            node.style.left = px(LABEL_WIDTH + marker.time * pixelsPerSecond);
            node.setAttribute('aria-label', `${marker.label || 'Marker'} at ${timeLabel(marker.time, true)}`);
            node.addEventListener('click', event => {
                event.stopPropagation();
                seek(marker.time);
            });
            fragment.append(node);
        }
        markers.replaceChildren(fragment);
        if (markerFocus !== undefined) markers.children[Number(markerFocus)]?.focus({preventScroll: true});
    }

    function closestSnap(target, excludeId, event) {
        if (!snapping.checked || event?.altKey) return null;
        const tolerance = Math.min(0.3, 8 / pixelsPerSecond);
        const targets = [0, playheadTime, ...(project?.markers || []).map(marker => marker.time)];
        for (const clip of project?.clips || []) {
            if (clip.id !== excludeId) targets.push(clip.start, clipEnd(clip));
        }
        if (project?.bpm > 0) {
            const period = 60 / project.bpm;
            targets.push(Math.round(target / period) * period);
        }
        let best = null;
        for (const time of targets) {
            if (Math.abs(time - target) <= tolerance && (best === null || Math.abs(time - target) < Math.abs(best - target))) best = time;
        }
        return best;
    }

    function hitMode(button, event) {
        const bounds = button.getBoundingClientRect();
        const x = event.clientX - bounds.left;
        const y = event.clientY - bounds.top;
        const edge = Math.min(11, bounds.width / 4);
        if (bounds.width >= 42 && y <= 20 && x < 24) return 'fade-in';
        if (bounds.width >= 42 && y <= 20 && x > bounds.width - 24) return 'fade-out';
        if (x < edge) return 'trim-in';
        if (x > bounds.width - edge) return 'trim-out';
        return 'move';
    }

    function viewTime(clientX) {
        return (clientX - viewport.getBoundingClientRect().left + viewport.scrollLeft - LABEL_WIDTH) / pixelsPerSecond;
    }

    function applyEdit(session, event) {
        const original = session.original;
        const elapsed = viewTime(event.clientX) - session.origin;
        const limit = assetById.get(original.asset_id)?.duration ?? original.out_point;
        const clip = {...original};
        const end = clipEnd(original);
        let snapped = null;

        if (session.mode === 'move') {
            let start = clamp(original.start + elapsed, 0, MAX_PROJECT_SECONDS - clipLength(original));
            const leftSnap = closestSnap(start, original.id, event);
            const rightSnap = closestSnap(start + clipLength(original), original.id, event);
            if (leftSnap !== null && (rightSnap === null || Math.abs(leftSnap - start) <= Math.abs(rightSnap - start - clipLength(original)))) {
                start = snapped = leftSnap;
            } else if (rightSnap !== null && rightSnap >= clipLength(original)) {
                start = rightSnap - clipLength(original);
                snapped = rightSnap;
            }
            clip.start = clamp(roundTime(start), 0, MAX_PROJECT_SECONDS - clipLength(original));
            const lane = document.elementFromPoint(event.clientX, event.clientY)?.closest('.studio-track-lane');
            clip.track_id = lane?.dataset.trackId || original.track_id;
        } else if (session.mode.startsWith('trim')) {
            const trimIn = session.mode === 'trim-in';
            const boundary = (trimIn ? original.start : end) + elapsed;
            const minimum = trimIn ? Math.max(0, original.start - original.in_point) : original.start + MIN_CLIP_SECONDS;
            const maximum = trimIn ? end - MIN_CLIP_SECONDS : Math.min(MAX_PROJECT_SECONDS, original.start + limit - original.in_point);
            const target = closestSnap(boundary, original.id, event);
            const time = clamp(roundTime(target ?? boundary), minimum, maximum);
            if (target !== null && Math.abs(target - time) < 0.001) snapped = target;
            if (trimIn) {
                clip.start = time;
                clip.in_point = clamp(roundTime(original.in_point + time - original.start), 0, original.out_point - MIN_CLIP_SECONDS);
            } else {
                clip.out_point = clamp(roundTime(original.in_point + time - original.start), original.in_point + MIN_CLIP_SECONDS, limit);
            }
            clip.automation = adjustedAutomation(original, clip.in_point, clip.out_point);
        } else {
            const key = session.mode === 'fade-in' ? 'fade_in' : 'fade_out';
            const boundary = session.mode === 'fade-in'
                ? original.start + (original.fade_in || 0) + elapsed
                : end - (original.fade_out || 0) + elapsed;
            const target = closestSnap(boundary, original.id, event);
            const time = clamp(target ?? boundary, original.start, end);
            clip[key] = roundTime(key === 'fade_in' ? time - original.start : end - time);
            if (target === time) snapped = time;
        }
        shortenFades(clip);
        return {clip, snapped};
    }

    function shortenFades(clip) {
        const length = clipLength(clip);
        clip.fade_in = roundTime(clamp(clip.fade_in || 0, 0, length));
        clip.fade_out = roundTime(clamp(clip.fade_out || 0, 0, length));
    }

    function commit(clips, label, clipId = selectedId) {
        selectedId = clipId;
        setProject({...project, clips});
        emit('change', {project, label});
        emit('select', {clipId: selectedId});
    }

    function split() {
        const clip = project?.clips.find(item => item.id === selectedId);
        if (!clip || playheadTime < clip.start + MIN_CLIP_SECONDS || playheadTime > clipEnd(clip) - MIN_CLIP_SECONDS) {
            emit('notice', {message: 'Place the playhead inside a selected clip to split it.'});
            return;
        }
        const boundary = roundTime(clip.in_point + playheadTime - clip.start);
        const left = {...clip, out_point: boundary, fade_out: 0,
            automation: adjustedAutomation(clip, clip.in_point, boundary)};
        const right = {...clip, id: crypto.randomUUID(), start: roundTime(playheadTime), in_point: boundary, fade_in: 0,
            automation: adjustedAutomation(clip, boundary, clip.out_point)};
        shortenFades(left);
        shortenFades(right);
        commit(project.clips.flatMap(item => item.id === clip.id ? [left, right] : [item]), 'Split clip', right.id);
    }

    function restorePreview() {
        if (!drag) return;
        drag.button.style.transform = '';
        positionClip(drag.button, drag.original);
        guide.hidden = true;
        viewport.classList.remove('is-editing');
    }

    viewport.addEventListener('pointerdown', event => {
        const button = event.target.closest('.studio-clip');
        if (!button || event.button !== 0 || !project || drag) return;
        const original = project.clips.find(clip => clip.id === button.dataset.clipId);
        if (!original) return;
        button.focus({preventScroll: true});
        select(original.id);
        drag = {
            original, button, mode: hitMode(button, event), origin: viewTime(event.clientX),
            clientX: event.clientX, clientY: event.clientY, pointerId: event.pointerId, edited: null,
        };
        viewport.setPointerCapture(event.pointerId);
        event.preventDefault();
    });

    viewport.addEventListener('pointermove', event => {
        if (!drag) {
            const button = event.target.closest('.studio-clip');
            if (button) button.dataset.hoverTool = hitMode(button, event);
            return;
        }
        if (event.pointerId !== drag.pointerId) return;
        if (!drag.edited && Math.hypot(event.clientX - drag.clientX, event.clientY - drag.clientY) < 2) return;
        const {clip, snapped} = applyEdit(drag, event);
        drag.edited = clip;
        viewport.classList.add('is-editing');
        positionClip(drag.button, clip);
        const sourceLane = rowById.get(drag.original.track_id);
        const lane = rowById.get(clip.track_id);
        drag.button.style.transform = lane ? `translateY(${lane.offsetTop - sourceLane.offsetTop}px)` : '';
        guide.hidden = snapped === null;
        if (snapped !== null) guide.style.left = px(LABEL_WIDTH + snapped * pixelsPerSecond);
        requestWaves();
    });

    function endDrag(event, cancelled) {
        if (!drag || drag.pointerId !== event.pointerId) return;
        const {original, edited, mode} = drag;
        const changed = edited && ['start', 'track_id', 'in_point', 'out_point', 'fade_in', 'fade_out'].some(field => (
            (edited[field] ?? 0) !== (original[field] ?? 0)
        ));
        restorePreview();
        drag = null;
        if (!cancelled && changed) {
            const label = mode === 'move' ? 'Move clip' : mode.startsWith('trim') ? 'Trim clip' : 'Change clip fade';
            commit(project.clips.map(clip => clip.id === original.id ? edited : clip), label);
        } else requestWaves();
    }

    viewport.addEventListener('pointerup', event => endDrag(event, false));
    viewport.addEventListener('pointercancel', event => endDrag(event, true));
    viewport.addEventListener('lostpointercapture', event => endDrag(event, true));

    viewport.addEventListener('click', event => {
        const clip = event.target.closest('.studio-clip');
        if (clip) select(clip.dataset.clipId);
        else if (event.target.closest('.studio-ruler, .studio-track-lane') && !event.target.closest('.studio-track-label')) seek(viewTime(event.clientX));
    });

    viewport.addEventListener('scroll', () => {
        if (!rulerFrame) rulerFrame = requestAnimationFrame(() => {
            rulerFrame = 0;
            drawRuler();
        });
        requestWaves();
    }, {passive: true});

    zoom.addEventListener('input', () => {
        const center = Math.max(0, (viewport.scrollLeft + viewport.clientWidth / 2 - LABEL_WIDTH) / pixelsPerSecond);
        updateScale();
        drawLayout();
        viewport.scrollLeft = Math.max(0, center * pixelsPerSecond + LABEL_WIDTH - viewport.clientWidth / 2);
    });
    byId('studio-split')?.addEventListener('click', split);
    byId('studio-stop')?.addEventListener('click', () => { shuttleRate = 0; });
    new ResizeObserver(() => {
        if (!viewport.clientWidth) return;
        updateScale();
        drawLayout();
    }).observe(viewport);

    function adjustedAutomation(clip, sourceFrom, sourceTo) {
        if (!Array.isArray(clip.automation) || !clip.automation.length) return clip.automation;
        const points = [...clip.automation].sort((a, b) => a.time - b.time);
        const from = sourceFrom - clip.in_point;
        const to = sourceTo - clip.in_point;
        function valueAt(time) {
            if (time <= points[0].time) return points[0].db;
            const index = points.findIndex(point => point.time >= time);
            if (index < 0) return points.at(-1).db;
            const left = points[index - 1];
            const right = points[index];
            return left.db + (right.db - left.db) * (time - left.time) / (right.time - left.time);
        }
        const keep = points.filter(point => point.time >= from && point.time <= to)
            .map(point => ({...point, time: roundTime(point.time - from)}));
        if (from > points[0].time && from < points.at(-1).time && keep[0]?.time !== 0) {
            keep.unshift({time: 0, db: valueAt(from)});
        }
        const length = roundTime(to - from);
        if (to > points[0].time && to < points.at(-1).time && keep.at(-1)?.time !== length) {
            keep.push({time: length, db: valueAt(to)});
        }
        return keep.length ? keep : [{time: 0, db: valueAt(from)}];
    }

    function requestWaves() {
        if (drawFrame) return;
        drawFrame = requestAnimationFrame(() => {
            drawFrame = 0;
            if (!viewport.clientWidth || !viewport.clientHeight) return;
            const rect = viewport.getBoundingClientRect();
            const width = viewport.clientWidth;
            const height = viewport.clientHeight;
            const segments = [];
            const samples = project?.clips || [];
            let budget = Math.max(1400, width * 8);
            // Cap samples by the visible area, independently of the duration or zoomable stage width.
            for (const stored of samples) {
                if (budget <= 0) break;
                const clip = drag?.original.id === stored.id && drag.edited ? drag.edited : stored;
                const asset = assetById.get(clip.asset_id);
                const peaks = asset?.peaks;
                const node = clipNodes.get(clip.id);
                if (!node || !peaks?.length || !asset.duration || asset.available === false) continue;
                const bounds = node.getBoundingClientRect();
                const x = bounds.left - rect.left;
                const y = bounds.top - rect.top + 17;
                const waveHeight = Math.max(1, bounds.height - 19);
                if (y > height || y + waveHeight < 0 || x + bounds.width < LABEL_WIDTH || x > width) continue;
                const low = Math.max(LABEL_WIDTH + 1, x + 3);
                const high = Math.min(width, x + bounds.width - 3);
                if (high <= low) continue;
                const step = Math.max(2, (high - low) / budget);
                const midpoint = y + waveHeight / 2;
                for (let horizontal = low; horizontal < high; horizontal += step) {
                    const relative = (horizontal - x) / bounds.width;
                    const next = (horizontal + step - x) / bounds.width;
                    const point = (clip.in_point + relative * clipLength(clip)) / asset.duration;
                    const nextPoint = (clip.in_point + next * clipLength(clip)) / asset.duration;
                    const start = clamp(Math.floor(point * peaks.length), 0, peaks.length - 1);
                    const finish = clamp(Math.ceil(nextPoint * peaks.length), start + 1, peaks.length);
                    let max = 0;
                    for (let index = start; index < finish; index++) max = Math.max(max, peaks[index]);
                    const amplitude = Math.max(1, clamp(max, 0, 1) * waveHeight * 0.45);
                    segments.push(horizontal - 0.5, midpoint - amplitude, horizontal - 0.5, midpoint + amplitude);
                    budget--;
                }
            }
            waves.draw(width, height, segments);
        });
    }

    function makeWavePainter(host) {
        let canvas = make('canvas', 'studio-waveform-canvas');
        host.append(canvas);
        let gl, buffer, program, position, scale;
        let fallback;
        const setFallback = () => {
            const fresh = make('canvas', 'studio-waveform-canvas');
            canvas.replaceWith(fresh);
            canvas = fresh;
            gl = null;
            fallback = canvas.getContext('2d');
            host.dataset.renderer = 'canvas2d';
        };
        try {
            gl = canvas.getContext('webgl', {alpha: true, antialias: false, powerPreference: 'high-performance'});
            if (!gl) {
                setFallback();
            } else {
                const shader = (type, source) => {
                    const object = gl.createShader(type);
                    gl.shaderSource(object, source);
                    gl.compileShader(object);
                    if (!gl.getShaderParameter(object, gl.COMPILE_STATUS)) throw new Error('Waveform shader compilation unavailable');
                    return object;
                };
                program = gl.createProgram();
                gl.attachShader(program, shader(gl.VERTEX_SHADER,
                    'attribute vec2 a; uniform vec2 s; void main(){gl_Position=vec4(a.x*2.0/s.x-1.0,1.0-a.y*2.0/s.y,0.0,1.0);}'));
                gl.attachShader(program, shader(gl.FRAGMENT_SHADER,
                    'precision mediump float; void main(){gl_FragColor=vec4(0.47,0.90,0.99,0.95);}'));
                gl.linkProgram(program);
                if (!gl.getProgramParameter(program, gl.LINK_STATUS)) throw new Error('Waveform shader link unavailable');
                position = gl.getAttribLocation(program, 'a');
                scale = gl.getUniformLocation(program, 's');
                buffer = gl.createBuffer();
                gl.clearColor(0, 0, 0, 0);
                host.dataset.renderer = 'webgl';
                canvas.addEventListener('webglcontextlost', () => {
                    setFallback();
                    requestWaves();
                }, {once: true});
            }
        } catch {
            setFallback();
        }
        return {
            draw(width, height, segments) {
                const ratio = Math.min(devicePixelRatio || 1, 2);
                const rasterWidth = Math.round(width * ratio);
                const rasterHeight = Math.round(height * ratio);
                if (canvas.width !== rasterWidth || canvas.height !== rasterHeight) {
                    canvas.width = rasterWidth;
                    canvas.height = rasterHeight;
                    canvas.style.width = px(width);
                    canvas.style.height = px(height);
                }
                if (gl) {
                    gl.viewport(0, 0, rasterWidth, rasterHeight);
                    gl.clear(gl.COLOR_BUFFER_BIT);
                    if (!segments.length) return;
                    gl.useProgram(program);
                    gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
                    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(segments), gl.DYNAMIC_DRAW);
                    gl.enableVertexAttribArray(position);
                    gl.vertexAttribPointer(position, 2, gl.FLOAT, false, 0, 0);
                    gl.uniform2f(scale, width, height);
                    gl.drawArrays(gl.LINES, 0, segments.length / 2);
                } else if (fallback) {
                    fallback.setTransform(ratio, 0, 0, ratio, 0, 0);
                    fallback.clearRect(0, 0, width, height);
                    fallback.strokeStyle = '#78e6fc';
                    fallback.beginPath();
                    for (let i = 0; i < segments.length; i += 4) {
                        fallback.moveTo(segments[i], segments[i + 1]);
                        fallback.lineTo(segments[i + 2], segments[i + 3]);
                    }
                    fallback.stroke();
                }
            },
        };
    }

    function keyFor(event) {
        const value = event.key === ' ' ? 'Space' : event.key?.length === 1 ? event.key.toUpperCase() : event.key;
        if (!value || ['Alt', 'AltGraph', 'Control', 'Meta', 'Shift', 'Dead', 'Unidentified'].includes(value)) return '';
        return [event.metaKey || event.ctrlKey ? 'Mod' : '', event.altKey ? 'Alt' : '', event.shiftKey ? 'Shift' : '', value]
            .filter(Boolean).join('+');
    }

    function activeStudio() {
        return byId('project-studio-panel')?.classList.contains('active');
    }

    function runTransport(action) {
        if (action === 'backward' || action === 'forward') {
            const sign = action === 'backward' ? -1 : 1;
            shuttleRate = Math.sign(shuttleRate) === sign ? sign * Math.min(4, Math.abs(shuttleRate) * 2) : sign;
            emit('transport', {action: 'shuttle', rate: shuttleRate});
        } else {
            shuttleRate = 0;
            emit('transport', {action});
        }
    }

    const actions = {
        toggle: () => runTransport('toggle'),
        backward: () => runTransport('backward'),
        pause: () => runTransport('pause'),
        forward: () => runTransport('forward'),
        split,
        undo: () => emit('command', {action: 'undo'}),
        redo: () => emit('command', {action: 'redo'}),
        marker: () => emit('command', {action: 'marker'}),
    };
    document.addEventListener('keydown', event => {
        if (!activeStudio() || event.defaultPrevented || event.isComposing || event.repeat || !project) return;
        if (drag && event.key === 'Escape') {
            event.preventDefault();
            const {pointerId} = drag;
            endDrag({pointerId}, true);
            if (viewport.hasPointerCapture(pointerId)) viewport.releasePointerCapture(pointerId);
            return;
        }
        if (event.target.closest?.('input, textarea, select, [contenteditable="true"], dialog[open]')) return;
        if (event.key === ' ' && event.target.closest?.('button:not(.studio-clip), a, summary')) return;
        const focused = event.target.closest?.('.studio-clip');
        if (focused && !event.ctrlKey && !event.metaKey && ['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'].includes(event.key)) {
            const clip = project.clips.find(item => item.id === focused.dataset.clipId);
            if (!clip) return;
            const direction = ['ArrowRight', 'ArrowDown'].includes(event.key) ? 1 : -1;
            const edited = {...clip};
            if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') {
                edited.start = roundTime(clamp(clip.start + direction * (event.shiftKey ? 1 : 0.1),
                    0, MAX_PROJECT_SECONDS - clipLength(clip)));
            } else {
                const trackIndex = project.tracks.findIndex(track => track.id === clip.track_id);
                const lane = project.tracks[trackIndex + direction];
                if (!lane) return;
                edited.track_id = lane.id;
            }
            event.preventDefault();
            commit(project.clips.map(item => item.id === clip.id ? edited : item), 'Move clip with keyboard', clip.id);
            return;
        }
        const key = keyFor(event);
        const action = Object.keys(actions).find(candidate => shortcuts[candidate] === key) ||
            (key === 'B' && shortcuts.split === DEFAULT_SHORTCUTS.split && !Object.values(shortcuts).includes('B') ? 'split' : null);
        if (!action) return;
        event.preventDefault();
        actions[action]();
    });

    const shortcutDialog = byId('studio-shortcuts');
    const fields = byId('studio-shortcuts-fields');

    function updateShortcutHints() {
        const targets = {
            palette: 'command-search-button', toggle: 'studio-play', split: 'studio-split',
            undo: 'studio-undo', redo: 'studio-redo', marker: 'studio-add-marker',
        };
        for (const [action, id] of Object.entries(targets)) {
            const key = shortcuts[action];
            const aliases = key.includes('Mod+') ? [key.replace('Mod+', 'Meta+'), key.replace('Mod+', 'Control+')] : [key];
            if (action === 'split' && key === DEFAULT_SHORTCUTS.split && !Object.values(shortcuts).includes('B')) aliases.push('B');
            byId(id)?.setAttribute('aria-keyshortcuts', aliases.join(' '));
        }
        const hint = byId('command-search-button')?.querySelector('kbd');
        if (hint) hint.textContent = shortcuts.palette.replace('Mod+', '⌘').replace('Shift+', '⇧').replace('Alt+', '⌥');
    }

    function saveShortcuts() {
        updateShortcutHints();
        try {
            localStorage.setItem(SHORTCUTS_KEY, JSON.stringify(shortcuts));
        } catch {
            emit('notice', {message: 'Shortcuts are available for this session only.'});
        }
    }

    function editShortcuts() {
        if (!shortcutDialog || !fields) return;
        const status = make('p', 'studio-shortcut-status');
        status.setAttribute('role', 'status');
        const rows = Object.keys(SHORTCUT_LABELS).map(action => {
            const label = make('label', 'studio-shortcut-field', SHORTCUT_LABELS[action]);
            const input = make('input', 'studio-shortcut-input');
            input.type = 'text';
            input.readOnly = true;
            input.value = shortcuts[action];
            input.setAttribute('aria-label', SHORTCUT_LABELS[action]);
            input.addEventListener('keydown', event => {
                if (event.key === 'Tab' || event.key === 'Escape') return;
                event.preventDefault();
                event.stopPropagation();
                const key = keyFor(event);
                if (!key) return;
                if (Object.entries(shortcuts).some(([other, bound]) => other !== action && key === bound)) {
                    status.textContent = `The ${key} shortcut is already assigned.`;
                    return;
                }
                shortcuts = {...shortcuts, [action]: key};
                input.value = key;
                status.textContent = `${SHORTCUT_LABELS[action]} uses ${key}.`;
                saveShortcuts();
            });
            label.append(input);
            return label;
        });
        fields.replaceChildren(...rows, status);
        if (!shortcutDialog.open) shortcutDialog.showModal();
        fields.querySelector('input')?.focus();
    }

    byId('studio-shortcuts-action')?.addEventListener('click', editShortcuts);
    byId('studio-shortcuts-reset')?.addEventListener('click', () => {
        shortcuts = {...DEFAULT_SHORTCUTS};
        saveShortcuts();
        editShortcuts();
    });

    function showStudio() {
        if (!activeStudio()) document.querySelector('[data-panel="project-studio-panel"]')?.click();
    }

    function commands() {
        const timelineCommands = Object.entries(actions).map(([action, run]) => ({
            label: `${SHORTCUT_LABELS[action]} · ${shortcuts[action]}`,
            keywords: `studio timeline ${action}`,
            run: () => {
                showStudio();
                run();
            },
        }));
        const toolbar = [...document.querySelectorAll('#project-studio [data-studio-action], #project-studio [data-studio-phase]')]
            .filter(node => node.textContent.trim() && !node.hidden && !node.matches(':disabled'));
        return [
            {label: 'Open Project Studio', keywords: 'edit timeline record mix export', run: showStudio},
            {label: 'Customize shortcuts', keywords: 'remap keyboard bindings', run: () => { showStudio(); editShortcuts(); }},
            ...timelineCommands,
            ...toolbar.map(node => ({
                label: node.getAttribute('aria-label') || node.textContent.trim(),
                keywords: 'studio workspace effect action',
                run: () => { showStudio(); node.click(); },
            })),
        ];
    }

    window.aemStudioTimeline = {
        setProject, setPlayhead, setSelection, split, commands,
        matchesPaletteShortcut: event => keyFor(event) === shortcuts.palette,
        duration: () => duration,
        inspect: () => ({clipId: selectedId, time: playheadTime}),
        renderer: () => surface.dataset.renderer,
    };
    updateShortcutHints();
    drawLayout();
})();
