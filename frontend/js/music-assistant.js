/* Music brief: local text composition with optional, explicit Ollama suggestions. */
const musicAssistantState = {
    initialized: false,
    presets: [],
    presetId: 'podcast_intro',
    revision: 0,
    formRevision: 0,
    builtFormRevision: -1,
    built: null,
    building: false,
    refining: false,
    refineRequest: 0,
    permission: null,
    suggestion: null,
    appliedSuggestions: [],
};

function musicElement(id) { return document.getElementById(`music-${id}`); }

function musicStatus(message, level = 'neutral') {
    const element = musicElement('status');
    element.textContent = message;
    element.dataset.level = level;
}

function musicPermission() {
    return typeof state !== 'undefined' && state.runtimePrivacy?.ollama_editorial_allowed === true;
}

function refreshMusicAssistantPrivacy() {
    if (!musicAssistantState.initialized) return;
    const permitted = musicPermission();
    if (musicAssistantState.permission !== permitted) {
        musicAssistantState.permission = permitted;
        musicAssistantState.refineRequest++;
        musicAssistantState.refining = false;
        musicAssistantState.suggestion = null;
        musicElement('suggestions').hidden = true;
    }
    musicUpdateControls();
}

function musicUpdateControls() {
    const s = musicAssistantState;
    const current = !!s.built && s.builtFormRevision === s.formRevision;
    const caption = musicElement('caption').value.trim();
    musicElement('build').disabled = s.building || !s.presets.length;
    musicElement('build').textContent = s.building ? 'Building brief…' : s.built ? 'Rebuild brief' : 'Build brief';
    musicElement('copy').disabled = !caption;
    musicElement('export').disabled = !current || !caption || s.building;
    musicElement('refine').disabled = !current || !caption || !musicPermission() || s.refining || s.building;
    musicElement('refine').textContent = s.refining ? 'Thinking locally…' : 'Suggest refinements';
    musicElement('append').disabled = !s.suggestion || s.suggestion.revision !== s.revision || s.refining || s.building;
    musicElement('output').setAttribute('aria-busy', String(s.building));
    musicElement('refinement').setAttribute('aria-busy', String(s.refining));
    musicElement('output-state').textContent = s.built ? (current ? 'Ready to edit' : 'Rebuild needed') : 'No brief yet';
    musicElement('output-state').dataset.stale = String(!!s.built && !current);
    const privacyNote = musicElement('privacy-note');
    if (!musicPermission()) {
        privacyNote.textContent = 'To enable suggestions, allow local Ollama editorial assistance in Settings. Building a brief works without it.';
    } else if (!current || !caption) {
        privacyNote.textContent = 'Build a brief first. Suggestions use your local Ollama model; the separate lyrics field is not sent to the model.';
    } else {
        privacyNote.textContent = 'Optional: send this brief and prompt to your local Ollama model. The separate lyrics field is excluded. No cloud fallback.';
    }
}

function musicRevise(formChanged) {
    const s = musicAssistantState;
    s.revision++;
    if (formChanged) s.formRevision++;
    s.refineRequest++;
    s.refining = false;
    s.suggestion = null;
    musicElement('suggestions').hidden = true;
    if (formChanged && s.built) {
        musicStatus('Directions changed. Rebuild to update the prompt and export. Your previous prompt is still here.', 'warning');
    } else if (s.built) {
        musicStatus('Prompt edited. Copy or export your version, or request new suggestions.');
    }
    musicUpdateControls();
}

function musicReadBrief() {
    return {
        description: musicElement('description').value.trim(),
        preset_id: musicAssistantState.presetId,
        style: musicElement('style').value.trim(),
        secondary_style: musicElement('secondary-style').value.trim(),
        instrumental: musicElement('vocals').value === 'instrumental',
        bpm: musicElement('bpm').value === '' ? null : Number(musicElement('bpm').value),
        duration_seconds: Number(musicElement('duration').value),
        instruments: musicElement('instruments').value.trim(),
        exclusions: musicElement('exclusions').value.trim(),
        sections: [0, 1, 2].map(index => ({
            name: musicElement(`section-${index}-name`).value,
            direction: musicElement(`section-${index}-direction`).value.trim(),
        })),
        // Keep lyrics byte-for-byte as entered; they are never part of the caption.
        lyrics: musicElement('lyrics').value,
    };
}

function musicApplyPreset() {
    const preset = musicAssistantState.presets.find(item => item.id === musicElement('preset').value);
    if (!preset) return;
    const d = preset.defaults;
    musicAssistantState.presetId = preset.id;
    for (const [id, field] of [
        ['style', 'style'], ['secondary-style', 'secondary_style'], ['bpm', 'bpm'],
        ['duration', 'duration_seconds'], ['instruments', 'instruments'], ['exclusions', 'exclusions'],
    ]) musicElement(id).value = d[field] ?? '';
    musicElement('vocals').value = d.instrumental === false ? 'vocals' : 'instrumental';
    [0, 1, 2].forEach(index => {
        const section = d.sections?.[index] || { name: ['Intro', 'Main', 'Outro'][index], direction: '' };
        musicElement(`section-${index}-name`).value = section.name;
        musicElement(`section-${index}-direction`).value = section.direction;
    });
    musicElement('applied-preset').textContent = `Using ${preset.name}`;
    musicRevise(true);
    musicStatus(`${preset.name} directions applied. Your description, lyrics and existing prompt are preserved.${musicAssistantState.built ? ' Rebuild when ready.' : ''}`);
}

function musicPreviewPreset() {
    const preset = musicAssistantState.presets.find(item => item.id === musicElement('preset').value);
    musicElement('preset-description').textContent = preset?.description || '';
    // Selecting a preset only previews it. Application is always explicit.
}

async function musicApiError(response, fallback) {
    if (typeof readApiError !== 'function') return fallback;
    const detail = await readApiError(response, fallback);
    if (typeof detail === 'string') return detail;
    if (Array.isArray(detail)) return detail.map(item => item.msg || fallback).join('; ');
    return fallback;
}

async function musicBuild(event) {
    if (event) event.preventDefault();
    const s = musicAssistantState;
    if (s.building || !s.presets.length || !musicElement('form').reportValidity()) return;
    const brief = musicReadBrief();
    if (!brief.description) {
        musicStatus('Describe the music you need before building a brief.', 'error');
        musicElement('description').focus();
        return;
    }
    const requestRevision = s.revision;
    const formRevision = s.formRevision;
    s.building = true;
    s.refineRequest++;
    s.refining = false;
    s.suggestion = null;
    musicElement('suggestions').hidden = true;
    musicStatus('Building your text brief locally…');
    musicUpdateControls();
    try {
        const response = await fetch('/api/music/brief', {
            method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(brief),
        });
        if (!response.ok) throw new Error(await musicApiError(response, 'Could not build the brief. Try again.'));
        const result = await response.json();
        if (requestRevision !== s.revision) return;
        if (typeof result.caption !== 'string' || !result.caption.trim() || !result.brief) {
            throw new Error('The brief response was incomplete. Your previous prompt is preserved.');
        }
        s.built = result;
        s.builtFormRevision = formRevision;
        s.revision++;
        s.appliedSuggestions = [];
        musicElement('caption').value = result.caption;
        const warnings = Array.isArray(result.warnings) ? result.warnings : [];
        musicElement('warnings').textContent = warnings.join(' ');
        musicElement('warnings').hidden = !warnings.length;
        musicStatus('Brief built locally. Review and edit the prompt before using it.', 'success');
        musicElement('caption').focus();
        musicElement('caption').setSelectionRange(0, 0);
        musicElement('caption').scrollTop = 0;
    } catch (error) {
        if (requestRevision === s.revision) musicStatus(error.message || 'Could not build the brief. Try again.', 'error');
    } finally {
        s.building = false;
        if (requestRevision !== s.revision && s.builtFormRevision !== s.formRevision) {
            musicStatus('Directions or prompt changed during the build. Build again to use your latest changes.', 'warning');
        }
        musicUpdateControls();
    }
}

async function musicRefine() {
    const s = musicAssistantState;
    if (!musicPermission() || s.refining || s.building || !s.built || s.builtFormRevision !== s.formRevision) return;
    const caption = musicElement('caption').value.trim();
    if (!caption) return;
    const revision = s.revision;
    const request = ++s.refineRequest;
    s.refining = true;
    s.suggestion = null;
    musicElement('suggestions').hidden = true;
    musicStatus('Asking your local Ollama model for suggestions…');
    musicUpdateControls();
    try {
        const response = await fetch('/api/music/refine', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ brief: s.built.brief, caption }),
        });
        if (!response.ok) throw new Error(await musicApiError(response, 'Local suggestions are unavailable. Your prompt is preserved.'));
        const result = await response.json();
        if (revision !== s.revision || request !== s.refineRequest || !musicPermission()) return;
        if (typeof result.suggestions !== 'string' || !result.suggestions.trim()) {
            throw new Error('The local model returned no suggestions. Your prompt is preserved.');
        }
        s.suggestion = { text: result.suggestions, model: result.model, engine: result.engine, revision };
        musicElement('suggestion-text').textContent = result.suggestions;
        musicElement('suggestion-model').textContent = `Local model: ${result.model || 'Ollama'}`;
        musicElement('suggestions').hidden = false;
        musicStatus('Suggestions are ready. Check for conflicts with your directions before appending.', 'warning');
    } catch (error) {
        if (revision === s.revision && request === s.refineRequest) {
            musicStatus(error.message || 'Local suggestions are unavailable. Your prompt is preserved.', 'error');
        }
    } finally {
        if (request === s.refineRequest) s.refining = false;
        musicUpdateControls();
    }
}

function musicAppendSuggestions() {
    const s = musicAssistantState;
    if (!s.suggestion || s.suggestion.revision !== s.revision || s.building) return;
    const suggestion = s.suggestion;
    const caption = `${musicElement('caption').value}\n\n${suggestion.text}`;
    if (caption.length > 16000) {
        musicStatus('Appending would exceed 16,000 characters. Shorten the prompt, then request suggestions again.', 'error');
        return;
    }
    musicElement('caption').value = caption;
    s.appliedSuggestions.push({ suggestions: suggestion.text, model: suggestion.model, engine: suggestion.engine });
    musicRevise(false);
    musicStatus('Suggestions appended. Review the combined prompt; you can edit every line.', 'success');
}

async function musicCopy() {
    const caption = musicElement('caption').value;
    if (!caption.trim()) return;
    try {
        await navigator.clipboard.writeText(caption);
        musicStatus('Prompt copied.', 'success');
    } catch (_) {
        musicElement('caption').focus();
        musicElement('caption').select();
        musicStatus('Clipboard access was unavailable. The prompt is selected; use your keyboard to copy it.', 'warning');
    }
}

function musicExportData() {
    const s = musicAssistantState;
    if (!s.built || s.builtFormRevision !== s.formRevision || !musicElement('caption').value.trim() || s.building) return null;
    return {
        schema_version: 1, kind: 'aemax-music-brief', text_only: true,
        caption: musicElement('caption').value,
        original_caption: s.built.caption,
        lyrics: s.built.lyrics,
        brief: s.built.brief,
        engine: s.built.engine,
        model: s.appliedSuggestions.at(-1)?.model || null,
        suggestions_applied: s.appliedSuggestions.length > 0,
        applied_suggestions: s.appliedSuggestions,
        caption_edited: musicElement('caption').value !== s.built.caption,
        warnings: s.built.warnings || [],
    };
}

function musicExport() {
    const payload = musicExportData();
    if (!payload) return;
    const url = URL.createObjectURL(new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' }));
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = 'aemax-music-brief.json';
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    musicStatus('JSON exported with your edited prompt, original brief and separate lyrics.', 'success');
}

function musicOpenSettings() {
    switchPanel('settings-panel', document.querySelector('[data-panel="settings-panel"]'));
    const control = document.getElementById('setting-ollama-editorial');
    control?.focus();
    control?.scrollIntoView({ block: 'center', behavior: 'auto' });
}

async function musicLoadPresets() {
    const initialFormRevision = musicAssistantState.formRevision;
    musicElement('retry').hidden = true;
    musicElement('preset').disabled = true;
    musicElement('apply-preset').disabled = true;
    try {
        const response = await fetch('/api/music/presets', { cache: 'no-store' });
        if (!response.ok) throw new Error(await musicApiError(response, 'Music presets could not be loaded.'));
        const result = await response.json();
        if (!Array.isArray(result.presets) || !result.presets.length) throw new Error('No music presets are available.');
        musicAssistantState.presets = result.presets;
        const select = musicElement('preset');
        select.replaceChildren();
        result.presets.forEach(preset => {
            const option = document.createElement('option');
            option.value = preset.id;
            option.textContent = preset.name;
            select.appendChild(option);
        });
        select.value = result.presets.find(preset => preset.id === 'podcast_intro')?.id || result.presets[0].id;
        musicPreviewPreset();
        // Never replace directions entered while the initial request was pending.
        if (initialFormRevision === 0 && musicAssistantState.formRevision === 0) {
            musicApplyPreset();
        } else {
            musicElement('applied-preset').textContent = 'Custom directions';
        }
        musicElement('preset').disabled = false;
        musicElement('apply-preset').disabled = false;
        musicStatus('Describe your music, then build a text brief. No model or audio file is needed.');
    } catch (error) {
        musicStatus(error.message || 'Music presets could not be loaded. Try again.', 'error');
        musicElement('retry').hidden = false;
    }
    musicUpdateControls();
}

function initMusicAssistant() {
    if (!musicElement('form') || musicAssistantState.initialized) return;
    musicAssistantState.initialized = true;
    musicElement('form').addEventListener('submit', musicBuild);
    musicElement('form').addEventListener('input', event => {
        if (event.target.id !== 'music-preset') musicRevise(true);
    });
    musicElement('preset').addEventListener('change', musicPreviewPreset);
    musicElement('apply-preset').addEventListener('click', musicApplyPreset);
    musicElement('caption').addEventListener('input', () => musicRevise(false));
    musicElement('refine').addEventListener('click', musicRefine);
    musicElement('append').addEventListener('click', musicAppendSuggestions);
    musicElement('copy').addEventListener('click', musicCopy);
    musicElement('export').addEventListener('click', musicExport);
    musicElement('retry').addEventListener('click', musicLoadPresets);
    musicElement('settings').addEventListener('click', musicOpenSettings);
    refreshMusicAssistantPrivacy();
    musicLoadPresets();
}
