(() => {
    const byId = id => document.getElementById(id);
    const dock = byId('workspace-dock');
    const toggle = byId('dock-tools');
    const tray = byId('desktop-tool-tray');
    const context = byId('dock-context');
    const command = byId('command-search-button');
    const commandDialog = byId('command-search-dialog');
    const main = byId('main-content');
    const headerContext = byId('studio-header-context');
    const headerProject = byId('studio-header-project');
    const headerTransport = byId('studio-header-transport');
    const studio = byId('project-studio');
    const studioProject = byId('studio-active-project');
    const studioName = byId('studio-active-name');
    const studioClip = byId('studio-clip-fields');
    const studioInspector = studio.querySelector('[data-studio-panel="inspector"]');
    const studioMix = byId('studio-mix-controls');
    const workspaceForm = byId('workspace-form');
    const play = byId('studio-play');
    const session = byId('studio-session');
    const verifier = byId('credentials-inspector');
    const reviewWorkflow = byId('review-workflow');
    const hasSource = () => !session.hidden;
    const hasRevision = () => !reviewWorkflow.querySelector('[data-workspace-stage="export"]').disabled;
    const action = (selector, label, icon, options = {}) => ({
        target: document.querySelector(selector), label, icon, ...options,
    });
    const step = (id, label, icon) => action(`[data-workspace-stage="${id}"]`, label, icon);
    const phase = (id, label, icon) => action(`[data-studio-phase="${id}"]`, label, icon);

    const openAudio = action('#upload-zone', 'Open media', 'workspace-import', {panel: 'upload-panel'});
    const openAnother = action('#open-another-source', 'Open another', 'workspace-import', {panel: 'upload-panel', when: hasSource});
    const newProject = action('#studio-project-new', 'New project', 'workspace-capsule', {panel: 'project-studio-panel'});
    const openBundle = action('#studio-project-bundle', 'Open project ZIP', 'package', {panel: 'project-studio-panel'});
    const findTool = action('#command-search-button', 'Find a tool', 'search');
    const workspaceActions = [
        action('#create-workspace', 'New workspace', 'workspace-capsule'),
        action('#workspace-add-module', 'Add tool', 'advanced', {when: () => !workspaceForm.hidden}),
        action('#workspace-form button[type="submit"]', 'Save workspace', 'save', {when: () => !workspaceForm.hidden}),
    ];
    const history = action('#workspace-history-button', 'Actions history', 'activity-history');
    const toReview = step('review', 'Listen & edit', 'workspace-compare');
    const toExport = step('export', 'Export options', 'workspace-export');
    const uploadActions = {
        empty: [openBundle, findTool],
        verify: [
            action('#credentials-file', 'Choose file', 'workspace-import'),
            action('#credentials-inspector > summary', 'Close verifier', 'cross', {focusBeforeClick: true}),
            action('#media-verification-download', 'Download report', 'workspace-report', {
                when: () => !byId('media-verification-evidence').hidden,
            }),
        ],
        clean: [action('#btn-process', 'Process audio', 'workspace-clean'), toReview, history],
        review: [action('#btn-play', 'Play / pause', 'play'), history, toExport],
        export: [
            action('#download-current-format', 'Download audio', 'workspace-export'),
            action('#btn-quality-report', 'Processing report', 'workspace-report', {when: () => hasRevision()}),
            toReview,
        ],
    };
    const importMedia = action('#studio-import', 'Import media', 'workspace-import');
    const edit = phase('edit', 'Edit clips', 'workspace-cut');
    const studioActions = {
        empty: [newProject, action('#studio-welcome-import', 'Import media', 'workspace-import'), openBundle],
        record: [
            action('#studio-record-start', 'Record mic', 'studio-mic', {when: () => byId('studio-record-stop').hidden}),
            action('#studio-record-stop', 'Stop recording', 'stop', {when: () => !byId('studio-record-stop').hidden}),
            importMedia,
            edit,
        ],
        edit: [
            action('#studio-add-track', 'Add track', 'workspace-capsule'),
            action('#studio-split', 'Split clip', 'workspace-cut', {when: () => !studioClip.hidden}),
            action('#studio-undo', 'Undo', 'repeat'),
            phase('export', 'Export mix', 'workspace-export'),
        ],
        mix: [
            action('#studio-clip-gain', 'Clip gain', 'volume', {
                focus: true,
                when: () => !studioClip.hidden && !studioInspector.hidden && studioMix.open && studio.dataset.calm !== 'true',
            }),
            action('#studio-undo', 'Undo', 'repeat'),
            edit,
        ],
        export: [
            action('#studio-export', 'Render audio', 'workspace-export'),
            action('#studio-consolidate', 'Consolidate project', 'package'),
            edit,
        ],
    };
    const tools = {
        'batch-panel': [
            action('#batch-file-input', 'Choose files', 'workspace-import'),
            action('#btn-batch-process', 'Process all', 'workspace-clean'),
        ],
        'stt-panel': [
            action('#stt-open-audio', 'Open audio', 'workspace-import'),
            action('#btn-transcribe', 'Transcribe', 'workspace-transcribe'),
            action('#btn-download-transcript', 'Download transcript', 'download'),
        ],
        'tts-panel': [action('#btn-generate-speech', 'Generate speech', 'tts')],
        'music-panel': [
            action('#music-build', 'Build brief', 'music'),
            action('#music-export', 'Export JSON', 'download'),
        ],
        'diarize-panel': [action('#btn-diarize', 'Find speakers', 'speakers')],
        'smart-panel': [action('#btn-smart-analyze', 'Analyze recording', 'smart-ai')],
        'watermark-panel': [
            action('#btn-watermark', 'Embed watermark', 'audio-watermark'),
            action('#btn-detect-watermark', 'Detect watermark', 'search'),
        ],
        'cluster-panel': [
            action('#companion-controls [data-action="find-phones"]', 'Find nearby phones', 'workspace-device'),
            action('#companion-controls [data-action="start"]', 'Make discoverable', 'desktop-node'),
        ],
        'presets-panel': [openAudio, openAnother],
        'about-panel': [action('#about-panel .about-section-heading .about-text-link', 'Release notes', 'file-report')],
        'settings-panel': [
            action('#local-model-refresh', 'Check local model', 'refresh'),
            action('#btn-save-privacy', 'Save privacy settings', 'lock'),
        ],
    };
    const canOpenFromTool = new Set(['diarize-panel', 'smart-panel', 'watermark-panel']);
    let paletteFromTray = false;
    let renderKey = '';

    function openTray(open, restoreFocus = false) {
        tray.hidden = !open;
        toggle.setAttribute('aria-expanded', String(open));
        if (!open && restoreFocus) toggle.focus();
    }

    function focusPanel(panelId) {
        const panel = byId(panelId);
        const heading = panel.querySelector('h1, .panel-header h2, .card-title') || panel;
        heading.tabIndex = -1;
        heading.focus({preventScroll: true});
    }

    function refreshHeader() {
        const inStudio = byId('project-studio-panel').classList.contains('active');
        headerContext.hidden = !inStudio;
        if (headerProject.textContent !== studioName.textContent) headerProject.textContent = studioName.textContent;
        headerTransport.hidden = !inStudio || studioProject.disabled;
    }

    function currentActions(panel) {
        if (panel === 'upload-panel') {
            if (!verifier.hidden && verifier.open) return uploadActions.verify;
            if (!hasSource()) return uploadActions.empty;
            const step = reviewWorkflow.querySelector('[aria-current="step"]').dataset.workspaceStage;
            return uploadActions[step];
        }
        if (panel === 'project-studio-panel') return studioActions[studioProject.disabled ? 'empty' : studio.dataset.phase];
        if (panel === 'workspaces-panel') return workspaceActions;
        if (!hasSource() && canOpenFromTool.has(panel)) return [openAudio];
        return tools[panel] || [];
    }

    function isDisabled(target) {
        return target.matches(':disabled, [aria-disabled="true"]');
    }

    function launch({target, panel, focus, focusBeforeClick}) {
        if (isDisabled(target)) return;
        if (panel && !byId(panel).classList.contains('active')) {
            switchPanel(panel);
            // Focus the destination before invoking its command or opening its modal.
            focusPanel(panel);
        }
        if (focus || focusBeforeClick) target.focus({preventScroll: true});
        if (!focus) target.click();
    }

    function refreshContext() {
        const panel = main.querySelector(':scope > .panel.active');
        if (!panel) return;
        const actions = currentActions(panel.id).filter(item =>
            item.target && !item.target.hidden && item.target.style.display !== 'none' && (!item.when || item.when()));
        const key = JSON.stringify([panel.id, ...actions.map(({target, label}) => [label, isDisabled(target), target.getAttribute('aria-pressed')])]);
        if (key === renderKey) return;
        renderKey = key;
        const focusedLabel = context.contains(document.activeElement) && document.activeElement.textContent;
        const buttons = actions.map(item => {
            const button = document.createElement('button');
            button.type = 'button';
            button.className = 'dock-context-action';
            button.disabled = isDisabled(item.target);
            const pressed = item.target.getAttribute('aria-pressed');
            if (pressed !== null) button.setAttribute('aria-pressed', pressed);
            const icon = document.createElement('span');
            icon.className = 'dock-icon';
            const img = document.createElement('img');
            img.src = `/static/img/icons/${item.icon}.svg`;
            img.alt = '';
            icon.append(img);
            const label = document.createElement('span');
            label.textContent = item.label;
            button.append(icon, label);
            button.addEventListener('click', () => launch(item));
            return button;
        });
        context.replaceChildren(...buttons);
        context.hidden = !buttons.length;
        dock.style.setProperty('--dock-actions', buttons.length);
        dock.style.setProperty('--dock-action-share', `${buttons.length}fr`);
        if (focusedLabel) {
            const next = buttons.find(button => !button.disabled && button.textContent === focusedLabel)
                || buttons.find(button => !button.disabled) || toggle;
            next.focus({preventScroll: true});
        }
    }

    headerTransport.append(play.closest('.studio-transport-buttons'), byId('studio-time'));
    new MutationObserver(refreshHeader).observe(studioName, {childList: true, subtree: true});
    const observer = new MutationObserver(() => {
        refreshHeader();
        refreshContext();
    });
    const actionGroups = [...Object.values(uploadActions), ...Object.values(studioActions), workspaceActions, ...Object.values(tools)];
    for (const target of new Set(actionGroups.flatMap(group => group.map(({target}) => target)).filter(Boolean))) {
        observer.observe(target, {attributes: true, attributeFilter: ['disabled', 'aria-disabled', 'aria-pressed', 'hidden', 'style']});
    }
    for (const [target, attributes] of [
        [studio, ['data-phase', 'data-calm']],
        [studioProject, ['disabled']],
        [session, ['hidden']],
        [verifier, ['hidden', 'open']],
        [studioClip, ['hidden']],
        [studioInspector, ['hidden']],
        [studioMix, ['open']],
        [workspaceForm, ['hidden']],
        [byId('media-verification-evidence'), ['hidden']],
        ...[...reviewWorkflow.querySelectorAll('button')].map(button => [button, ['aria-current', 'disabled']]),
    ]) {
        observer.observe(target, {attributes: true, attributeFilter: attributes});
    }
    refreshHeader();
    refreshContext();

    toggle.addEventListener('click', () => {
        openTray(tray.hidden);
        if (!tray.hidden) command.focus({preventScroll: true});
    });
    toggle.addEventListener('keydown', event => {
        if (event.key !== 'ArrowUp') return;
        event.preventDefault();
        openTray(true);
        command.focus();
    });
    document.addEventListener('pointerdown', event => {
        if (!tray.hidden && !dock.contains(event.target)) openTray(false);
    });
    document.addEventListener('keydown', event => {
        if (event.key !== 'Escape' || tray.hidden || commandDialog.open || event.defaultPrevented) return;
        event.preventDefault();
        openTray(false, true);
    });

    document.addEventListener('aem:panel', ({detail}) => {
        toggle.classList.toggle('is-current', tray.contains(detail.navItem));
        openTray(false);
        refreshHeader();
        refreshContext();
        if (detail.changed) main.scrollTop = 0;
    });
    dock.querySelectorAll('.sidebar-nav-item[data-panel]').forEach(item => {
        item.addEventListener('click', () => {
            if (item.dataset.panel === 'upload-panel' && verifier.open) verifier.open = false;
            focusPanel(main.querySelector(':scope > .panel.active').id);
        });
    });
    byId('desktop-build').addEventListener('click', () => {
        switchPanel('about-panel');
        focusPanel('about-panel');
    });

    command.addEventListener('click', () => {
        paletteFromTray = !tray.hidden;
        openTray(false);
    });
    commandDialog.addEventListener('close', () => {
        if (paletteFromTray && (document.activeElement === document.body || document.activeElement === command)) {
            toggle.focus();
        }
        paletteFromTray = false;
    });
})();
