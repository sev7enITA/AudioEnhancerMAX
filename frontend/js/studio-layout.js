(() => {
    const studio = document.getElementById('project-studio');
    if (!studio) return;

    const phases = {
        record: ['assets'],
        edit: ['inspector'],
        mix: ['inspector'],
        export: ['export'],
    };
    const presetLabels = {record: 'Record', edit: 'Edit', mix: 'Mix', export: 'Export'};
    const panels = new Map([...studio.querySelectorAll('[data-studio-panel]')].map(panel => [
        panel.dataset.studioPanel, {panel, slot: document.createComment('panel dock'), floating: false},
    ]));
    const toggles = new Map([...studio.querySelectorAll('[data-studio-panel-toggle]')].map(input => [
        input.dataset.studioPanelToggle, input,
    ]));
    const phaseButtons = [...studio.querySelectorAll('[data-studio-phase]')];
    const aspectButtons = [...studio.querySelectorAll('[data-studio-aspect]')];
    const layer = document.getElementById('studio-floating-layer');
    const dockWidth = document.getElementById('studio-dock-width');
    const calm = document.getElementById('studio-calm');
    const enlargePreview = document.getElementById('studio-enlarge-preview');
    const project = document.getElementById('studio-active-project');
    const projectEmpty = document.getElementById('studio-project-empty');
    const layoutNote = document.getElementById('studio-layout-note');
    const mixControls = document.getElementById('studio-mix-controls');
    const view = document.getElementById('studio-view-menu');
    let visible = new Set(phases.edit);
    let floatingCount = 0;
    let frontPanel = null;

    function say(message) {
        layoutNote.textContent = message;
    }

    function preference(name) {
        try {
            return localStorage.getItem('aemStudio.' + name);
        } catch {
            return null;
        }
    }

    function savePreference(name, value) {
        try {
            localStorage.setItem('aemStudio.' + name, value);
        } catch {
            // The layout still works when storage is restricted.
        }
    }

    function refreshPanels() {
        let docked = false;
        for (const [name, data] of panels) {
            data.panel.hidden = !visible.has(name);
            toggles.get(name).checked = visible.has(name);
            if (!data.panel.hidden && !data.floating) docked = true;
        }
        studio.dataset.noDock = String(!docked);
    }

    function setPhase(phase, announce = true) {
        if (!Object.hasOwn(phases, phase)) return;
        studio.dataset.phase = phase;
        phaseButtons.forEach(button => {
            button.setAttribute('aria-pressed', String(button.dataset.studioPhase === phase));
        });
        visible = new Set(phases[phase]);
        mixControls.open = phase === 'mix';
        refreshPanels();
        savePreference('phase', phase);
        if (announce) say(presetLabels[phase] + ' layout.');
    }

    function setAspect(aspect) {
        if (aspect !== 'wide' && aspect !== 'tall') return;
        studio.dataset.aspect = aspect;
        aspectButtons.forEach(button => {
            button.setAttribute('aria-pressed', String(button.dataset.studioAspect === aspect));
        });
    }

    function setCalm(active, announce = true) {
        studio.dataset.calm = String(active);
        calm.setAttribute('aria-pressed', String(active));
        if (active) view.open = false;
        savePreference('calm', String(active));
        if (announce) say(active ? 'Calm mode. Extra panels hidden.' : 'Extra panels restored.');
    }

    function setPreviewEnlarged(enlarged) {
        studio.dataset.previewEnlarged = String(enlarged);
        enlargePreview.setAttribute('aria-pressed', String(enlarged));
        say(enlarged ? 'Video preview enlarged.' : 'Standard video preview.');
    }

    function setDockWidth(width) {
        const value = Math.round(Math.min(480, Math.max(260, Number(width) || 310)));
        dockWidth.value = value;
        studio.style.setProperty('--studio-dock-width', value + 'px');
        savePreference('dockWidth', String(value));
    }

    function positionPanel(panel, left, top) {
        const bounds = panel.getBoundingClientRect();
        const x = Math.min(Math.max(8, left), Math.max(8, window.innerWidth - bounds.width - 8));
        const y = Math.min(Math.max(8, top), Math.max(8, window.innerHeight - bounds.height - 8));
        panel.style.setProperty('--studio-panel-x', Math.round(x) + 'px');
        panel.style.setProperty('--studio-panel-y', Math.round(y) + 'px');
    }

    function raisePanel(data) {
        if (!data.floating || frontPanel === data.panel) return;
        frontPanel?.style.removeProperty('z-index');
        frontPanel = data.panel;
        frontPanel.style.zIndex = '920';
    }

    const floatingSize = new ResizeObserver(entries => {
        for (const {target: panel} of entries) {
            if (panel.hidden) continue;
            const {left, top} = panel.getBoundingClientRect();
            positionPanel(panel, left, top);
        }
    });

    function makeFloatingControls(data, label) {
        const header = data.panel.querySelector('header');
        const move = document.createElement('button');
        move.type = 'button';
        move.className = 'studio-button studio-dock-move';
        move.textContent = 'Move';
        move.title = 'Use arrow keys to move this panel';
        move.setAttribute('aria-label', 'Move ' + label + ' using arrow keys');
        move.hidden = true;
        header.insertBefore(move, data.button);
        move.addEventListener('keydown', event => {
            const step = event.shiftKey ? 36 : 12;
            const offsets = {ArrowLeft: [-step, 0], ArrowRight: [step, 0], ArrowUp: [0, -step], ArrowDown: [0, step]};
            if (!data.floating || !Object.hasOwn(offsets, event.key)) return;
            event.preventDefault();
            event.stopPropagation();
            const rect = data.panel.getBoundingClientRect();
            const [dx, dy] = offsets[event.key];
            positionPanel(data.panel, rect.left + dx, rect.top + dy);
        });

        const sizes = document.createElement('details');
        sizes.className = 'studio-float-size';
        sizes.hidden = true;
        const summary = document.createElement('summary');
        summary.textContent = 'Panel size';
        sizes.append(summary);
        for (const [axis, labelText, min, max, value] of [
            ['width', 'Width', 245, 620, 340],
            ['height', 'Height', 130, 620, 330],
        ]) {
            const key = document.createElement('label');
            key.className = 'studio-range';
            key.append(labelText);
            const input = document.createElement('input');
            input.type = 'range';
            input.min = min;
            input.max = max;
            input.step = 5;
            input.value = value;
            input.setAttribute('aria-label', label + ' panel ' + labelText.toLowerCase());
            input.addEventListener('input', () => {
                data.panel.style.setProperty('--studio-panel-' + axis, input.value + 'px');
            });
            key.append(input);
            sizes.append(key);
        }
        header.after(sizes);
        data.move = move;
        data.sizes = sizes;

        data.panel.addEventListener('focusin', () => raisePanel(data));
        data.panel.addEventListener('pointerdown', () => raisePanel(data));
        let drag = null;
        header.addEventListener('pointerdown', event => {
            if (!data.floating || event.button !== 0 || (event.target.closest('button') && !move.contains(event.target))) return;
            const rect = data.panel.getBoundingClientRect();
            drag = {id: event.pointerId, x: event.clientX - rect.left, y: event.clientY - rect.top};
            header.setPointerCapture(event.pointerId);
        });
        header.addEventListener('pointermove', event => {
            if (drag?.id === event.pointerId) positionPanel(data.panel, event.clientX - drag.x, event.clientY - drag.y);
        });
        for (const type of ['pointerup', 'pointercancel', 'lostpointercapture']) {
            header.addEventListener(type, () => { drag = null; });
        }
    }

    function setFloating(data, floating, announce = true) {
        if (data.floating === floating) return;
        data.floating = floating;
        data.panel.classList.toggle('is-floating', floating);
        if (floating) {
            layer.append(data.panel);
            const offset = (floatingCount++ % 4) * 24;
            positionPanel(data.panel, (window.innerWidth - 345) * .56 + offset, 160 + offset);
            floatingSize.observe(data.panel);
            raisePanel(data);
        } else {
            floatingSize.unobserve(data.panel);
            data.panel.style.removeProperty('z-index');
            if (frontPanel === data.panel) frontPanel = null;
            data.slot.after(data.panel);
        }
        data.move.hidden = data.sizes.hidden = !floating;
        data.button.textContent = floating ? 'Dock' : 'Detach';
        data.button.setAttribute('aria-label', (floating ? 'Dock ' : 'Detach ') + data.label);
        refreshPanels();
        if (announce) {
            data.button.focus();
            say(data.label + (floating ? ' detached. Use Move or Panel size to adjust it.' : ' docked.'));
        }
    }

    for (const [name, data] of panels) {
        data.panel.before(data.slot);
        data.button = data.panel.querySelector('[data-studio-detach]');
        data.label = data.panel.querySelector('h2').textContent;
        makeFloatingControls(data, data.label);
        data.button.addEventListener('click', () => setFloating(data, !data.floating));
        toggles.get(name).addEventListener('change', event => {
            if (event.target.checked) visible.add(name);
            else visible.delete(name);
            refreshPanels();
        });
    }

    phaseButtons.forEach(button => button.addEventListener('click', () => setPhase(button.dataset.studioPhase)));
    aspectButtons.forEach(button => button.addEventListener('click', () => {
        const aspect = button.dataset.studioAspect;
        setAspect(aspect);
        studio.dispatchEvent(new CustomEvent('studio:aspect', {bubbles: true, detail: {aspect}}));
        say(aspect === 'tall' ? 'Portrait preview.' : 'Landscape preview.');
    }));
    calm.addEventListener('click', () => setCalm(studio.dataset.calm !== 'true'));
    enlargePreview.addEventListener('click', () => setPreviewEnlarged(studio.dataset.previewEnlarged !== 'true'));
    studio.addEventListener('keydown', event => {
        if (event.key !== 'Escape' || document.getElementById('studio-video').hidden || studio.dataset.calm === 'true' ||
            studio.dataset.previewEnlarged !== 'true' ||
            !event.target.closest('.studio-preview-panel')) return;
        event.preventDefault();
        setPreviewEnlarged(false);
        enlargePreview.focus();
    });
    dockWidth.addEventListener('input', () => setDockWidth(dockWidth.value));
    document.getElementById('studio-restore-layout').addEventListener('click', () => {
        for (const data of panels.values()) setFloating(data, false, false);
        setDockWidth(310);
        setPhase(studio.dataset.phase);
    });
    document.addEventListener('pointerdown', event => {
        if (view.open && !view.contains(event.target)) view.open = false;
    });
    view.addEventListener('keydown', event => {
        if (event.key !== 'Escape' || !view.open) return;
        event.preventDefault();
        view.open = false;
        view.querySelector('summary').focus();
    });
    window.addEventListener('resize', () => {
        for (const data of panels.values()) {
            if (!data.floating || data.panel.hidden) continue;
            const rect = data.panel.getBoundingClientRect();
            positionPanel(data.panel, rect.left, rect.top);
        }
    });

    if (!navigator.mediaDevices?.getUserMedia || typeof window.MediaRecorder !== 'function') {
        const record = document.getElementById('studio-record-start');
        record.disabled = true;
        record.title = 'Microphone recording is unavailable in this runtime.';
        document.getElementById('studio-record-status').textContent = record.title;
    }

    document.querySelector('[data-panel="project-studio-panel"]')?.addEventListener('click', () => {
        document.getElementById('project-studio-title').focus();
    });

    const modal = document.getElementById('studio-new-dialog');
    const newProject = document.getElementById('studio-project-new');
    newProject.addEventListener('click', () => {
        if (modal.open) return;
        modal.showModal();
        document.getElementById('studio-project-name').focus();
    });
    document.getElementById('studio-new-cancel').addEventListener('click', () => modal.close());
    modal.addEventListener('close', () => newProject.focus());

    function updateProjectState() {
        projectEmpty.hidden = !project.disabled;
    }
    new MutationObserver(updateProjectState).observe(project, {attributes: true, attributeFilter: ['disabled']});
    updateProjectState();
    setDockWidth(preference('dockWidth'));
    setPhase(preference('phase') || 'edit', false);
    setCalm(preference('calm') === 'true', false);
    window.aemStudioLayout = {setAspect, setPhase};
})();
