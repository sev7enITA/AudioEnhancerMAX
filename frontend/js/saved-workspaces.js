(() => {
    const byId = id => document.getElementById(id);
    const endpoint = '/api/settings/workspaces';
    const form = byId('workspace-form');
    const controls = byId('workspace-form-controls');
    const name = byId('new-workspace-name');
    const order = byId('workspace-tool-order');
    const select = byId('workspace-module-select');
    const list = byId('saved-workspaces');
    const status = byId('workspace-settings-status');
    const formStatus = byId('workspace-form-status');
    const create = byId('create-workspace');
    const strip = byId('active-workspace-strip');
    const switcher = byId('active-workspace-switcher');
    const pins = byId('active-workspace-tools');
    const verifier = byId('credentials-inspector');
    const managerButton = document.querySelector('#workspace-dock [data-panel="workspaces-panel"]');

    const tools = new Map([
        ['upload-panel', {label: 'Clean up audio', icon: '/static/img/icons/workspace-import.svg'}],
        ['verify-content', {label: 'Verify C2PA', icon: '/static/img/icons/content-credentials.svg'}],
    ]);
    for (const id of ['presets', 'batch', 'stt', 'speech-editor', 'tts', 'music', 'diarize', 'smart', 'watermark', 'cluster']) {
        const key = `${id}-panel`;
        const nav = document.querySelector(`#desktop-tool-tray [data-panel="${key}"]`);
        const label = [...nav.childNodes].filter(node => node.nodeType === Node.TEXT_NODE)
            .map(node => node.textContent.trim()).filter(Boolean).join(' ');
        tools.set(key, {label, icon: nav.querySelector('img').getAttribute('src'), nav});
    }

    let workspaces = [];
    let activeName = null;
    let editing = null;
    let selected = [];
    let saving = false;
    const lastTool = new Map();

    function activeWorkspace() {
        return workspaces.find(workspace => workspace.name === activeName);
    }

    function button(label, action, accessibleLabel) {
        const control = document.createElement('button');
        control.type = 'button';
        control.className = 'btn btn-secondary';
        control.textContent = label;
        if (accessibleLabel) control.setAttribute('aria-label', accessibleLabel);
        control.addEventListener('click', action);
        return control;
    }

    function renderToolLabel(element, tool) {
        const {label, icon} = tools.get(tool);
        const image = document.createElement('img');
        image.src = icon;
        image.alt = '';
        const text = document.createElement('span');
        text.textContent = label;
        element.replaceChildren(image, text);
    }

    function available(tool) {
        if (tool === 'verify-content') return !verifier.hidden;
        const entry = tools.get(tool);
        return Boolean(entry && !entry.nav?.hidden && !entry.nav?.disabled &&
            byId(tool === 'speech-editor-panel' ? 'upload-panel' : tool));
    }

    function openTool(tool, trigger) {
        if (!available(tool)) return;
        if (tool === 'verify-content') {
            switchPanel('upload-panel');
            window.aemWorkspace.openVerifier(trigger);
        } else {
            if (tool === 'upload-panel' || tool === 'speech-editor-panel') verifier.open = false;
            switchPanel(tool, tools.get(tool).nav);
            if (tool === 'upload-panel') window.aemWorkspace.selectStage('clean');
            const main = byId('main-content');
            const heading = [...main.querySelectorAll('.panel.active h1, .panel.active .card-title')]
                .find(node => node.getClientRects().length) || main;
            heading.tabIndex = -1;
            heading.focus();
        }
        syncCurrentTool();
    }

    function revealPin(pin) {
        const {left, right} = pins.getBoundingClientRect();
        const tile = pin.getBoundingClientRect();
        const inset = 4;
        if (tile.left < left + inset) pins.scrollLeft += tile.left - left - inset;
        else if (tile.right > right - inset) pins.scrollLeft += tile.right - right + inset;
    }

    function syncCurrentTool() {
        const panel = document.querySelector('#main-content .panel.active')?.id;
        let tool = panel;
        if (panel === 'upload-panel') {
            if (verifier.open && available('verify-content')) {
                tool = 'verify-content';
            } else if (!byId('studio-session').hidden &&
                document.querySelector('[data-workspace-stage="review"][aria-current="step"]')) {
                tool = 'speech-editor-panel';
            }
        }

        for (const pin of pins.children) {
            if (pin.dataset.workspaceTool === tool) {
                if (!pin.hasAttribute('aria-current')) revealPin(pin);
                pin.setAttribute('aria-current', 'page');
            } else {
                pin.removeAttribute('aria-current');
            }
            if (pin.dataset.workspaceTool === 'verify-content') {
                pin.setAttribute('aria-expanded', String(tool === 'verify-content'));
            }
        }
        if (activeWorkspace()?.tools.includes(tool)) lastTool.set(activeName, tool);
    }

    function refreshVerifierPin() {
        const pin = pins.querySelector('[data-workspace-tool="verify-content"]');
        document.body.classList.toggle('workspace-verifier-pinned', Boolean(pin && available('verify-content')));
        if (pin) {
            pin.disabled = !available('verify-content');
            pin.title = pin.disabled ? 'Verify C2PA is unavailable in this build.' : 'Verify C2PA';
        }
    }

    function renderShell() {
        const workspace = activeWorkspace();
        switcher.replaceChildren(new Option('General', ''), ...workspaces.map(item => new Option(item.name, item.name)));
        switcher.value = workspace?.name ?? '';
        switcher.title = workspace ? `Switch workspace · ${workspace.name}` : 'Switch workspace · General';
        pins.replaceChildren(...(workspace?.tools || []).map(tool => {
            const pin = button('', () => openTool(tool, pin));
            pin.className = 'workspace-pin';
            pin.dataset.workspaceTool = tool;
            renderToolLabel(pin, tool);
            pin.disabled = !available(tool);
            if (tool === 'verify-content') pin.setAttribute('aria-controls', verifier.id);
            return pin;
        }));
        const generalSlot = byId('workspace-general-slot');
        generalSlot.hidden = Boolean(workspace) || !workspaces.length;
        const slot = workspace ? byId('workspace-strip-slot') : generalSlot;
        const control = byId('workspace-switcher-control');
        if (!slot.contains(control)) slot.append(control);
        strip.hidden = !workspace;
        refreshVerifierPin();
    }

    function resumeWorkspace(workspace) {
        const remembered = lastTool.get(workspace.name);
        const tool = [remembered, ...workspace.tools].find(candidate => workspace.tools.includes(candidate) && available(candidate));
        if (tool) {
            openTool(tool, pins.querySelector(`[data-workspace-tool="${tool}"]`));
        } else {
            switchPanel('upload-panel');
            byId('studio-welcome-title').focus();
            showToast('warning', 'The pinned tools are unavailable in this build.');
        }
    }

    async function activate(workspaceName) {
        if (saving) return;
        if (workspaceName !== activeName && !await persist(workspaces, workspaceName)) return;
        const workspace = activeWorkspace();
        if (workspace) resumeWorkspace(workspace);
        else (workspaces.length ? switcher : managerButton).focus();
    }

    function renderList() {
        list.replaceChildren();
        workspaces.forEach((workspace, index) => {
            const current = workspace.name === activeName;
            const item = document.createElement('article');
            item.className = 'workspace-saved-item';
            item.classList.toggle('workspace-saved-item-active', current);

            const header = document.createElement('header');
            const title = document.createElement('h3');
            title.textContent = workspace.name;
            header.append(title);
            if (current) {
                const badge = document.createElement('span');
                badge.className = 'workspace-active-badge';
                badge.textContent = 'Active';
                header.append(badge);
            }

            const modules = document.createElement('ul');
            modules.className = 'workspace-collection-modules';
            modules.setAttribute('aria-label', 'Pinned tools');
            for (const tool of workspace.tools) {
                const chip = document.createElement('li');
                renderToolLabel(chip, tool);
                modules.append(chip);
            }

            const action = current ? 'Resume' : 'Activate';
            const activateButton = button(action, () => activate(workspace.name), `${action} ${workspace.name}`);
            activateButton.className = current ? 'btn btn-secondary' : 'btn btn-primary';
            const edit = button('Edit', () => editWorkspace(index), `Edit ${workspace.name}`);
            const remove = button('Remove', async () => {
                if (saving || !window.confirm(`Remove the workspace “${workspace.name}”?`)) return;
                if (await persist(workspaces.filter(item => item !== workspace), current ? null : activeName)) {
                    lastTool.delete(workspace.name);
                    if (!form.hidden) form.hidden = true;
                    status.textContent = workspaces.length ? 'Workspace removed.' : 'Create a workspace to pin your tools.';
                    (create.disabled ? byId('workspaces-title') : create).focus();
                }
            }, `Remove ${workspace.name}`);

            const actions = document.createElement('div');
            actions.className = 'workspace-collection-actions';
            for (const control of [activateButton, edit, remove]) control.dataset.workspaceWrite = '';
            actions.append(activateButton, edit, remove);
            item.append(header, modules, actions);
            list.append(item);
        });
        setSaving(saving);
    }

    function renderSelection() {
        order.replaceChildren();
        selected.forEach((tool, index) => {
            const {label} = tools.get(tool);
            const row = document.createElement('li');
            const title = document.createElement('span');
            title.textContent = label;
            const move = (direction, text) => button(text, () => {
                const place = index + direction;
                [selected[index], selected[place]] = [selected[place], selected[index]];
                renderSelection();
                order.children[place].querySelector(direction < 0 ? '[data-down]' : '[data-up]').focus();
                formStatus.textContent = `${label} moved to position ${place + 1}.`;
            }, `Move ${label} ${text.toLowerCase()}`);
            const up = move(-1, 'Up');
            const down = move(1, 'Down');
            up.dataset.up = '';
            down.dataset.down = '';
            up.disabled = index === 0;
            down.disabled = index === selected.length - 1;
            row.append(title, up, down, button('Remove', () => {
                selected.splice(index, 1);
                renderSelection();
                select.focus();
                formStatus.textContent = `${label} removed.`;
            }, `Remove ${label}`));
            order.append(row);
        });
        select.replaceChildren(...[...tools].filter(([tool]) => !selected.includes(tool))
            .map(([tool, {label}]) => new Option(label, tool)));
        select.disabled = byId('workspace-add-module').disabled = !select.options.length;
    }

    function editWorkspace(index) {
        if (saving) return;
        editing = index;
        const workspace = workspaces[index];
        selected = [...(workspace?.tools || [])];
        name.value = workspace?.name || '';
        byId('workspace-form-title').textContent = workspace ? 'Edit workspace' : 'New workspace';
        formStatus.textContent = '';
        renderSelection();
        form.hidden = false;
        name.focus();
    }

    function setSaving(busy) {
        saving = controls.disabled = switcher.disabled = byId('edit-active-workspace').disabled = busy;
        create.disabled = busy || workspaces.length >= 12;
        list.querySelectorAll('[data-workspace-write]').forEach(control => {control.disabled = busy;});
    }

    async function persist(next, nextActive, errorStatus = status) {
        if (saving) return false;
        const trigger = document.activeElement;
        setSaving(true);
        try {
            const response = await fetch(endpoint, {
                method: 'PUT',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({workspaces: next, active_workspace: nextActive}),
            });
            if (!response.ok) {
                const {detail} = await response.json();
                throw new Error(typeof detail === 'string' ? detail : 'Could not save your workspaces.');
            }
            const saved = await response.json();
            workspaces = saved.workspaces;
            activeName = saved.active_workspace ?? null;
            renderList();
            renderShell();
            return true;
        } catch (error) {
            errorStatus.textContent = error.message;
            if (!byId('workspaces-panel').classList.contains('active')) showToast('error', error.message);
            return false;
        } finally {
            setSaving(false);
            if (document.activeElement === document.body && trigger?.getClientRects().length) trigger.focus();
        }
    }

    create.addEventListener('click', () => editWorkspace(null));
    byId('workspace-cancel').addEventListener('click', () => {
        form.hidden = true;
        (create.disabled ? byId('workspaces-title') : create).focus();
    });
    byId('workspace-add-module').addEventListener('click', () => {
        if (!select.value) return;
        const {label} = tools.get(select.value);
        selected.push(select.value);
        renderSelection();
        if (select.disabled) order.lastElementChild.querySelector('button:last-child').focus();
        formStatus.textContent = `${label} added.`;
    });
    form.addEventListener('submit', async event => {
        event.preventDefault();
        if (!selected.length) {
            formStatus.textContent = 'Add at least one tool.';
            select.focus();
            return;
        }
        const next = [...workspaces];
        const previous = workspaces[editing];
        const edited = {name: name.value.trim(), tools: [...selected]};
        next[editing ?? next.length] = edited;
        const renamedActive = previous?.name === activeName && edited.name !== activeName;
        if (await persist(next, renamedActive ? edited.name : activeName, formStatus)) {
            if (previous && previous.name !== edited.name) {
                if (lastTool.has(previous.name)) lastTool.set(edited.name, lastTool.get(previous.name));
                lastTool.delete(previous.name);
            }
            form.hidden = true;
            status.textContent = 'Workspace saved.';
            syncCurrentTool();
            (create.disabled ? byId('workspaces-title') : create).focus();
        }
    });

    switcher.addEventListener('change', () => {
        const nextActive = switcher.value || null;
        switcher.value = activeName ?? '';
        activate(nextActive);
    });
    byId('edit-active-workspace').addEventListener('click', () => {
        switchPanel('workspaces-panel');
        editWorkspace(workspaces.indexOf(activeWorkspace()));
    });
    pins.addEventListener('focusin', event => {
        if (event.target.parentElement === pins) revealPin(event.target);
    });
    document.addEventListener('aem:panel', syncCurrentTool);
    verifier.addEventListener('toggle', syncCurrentTool);
    new MutationObserver(() => {
        refreshVerifierPin();
        syncCurrentTool();
    }).observe(verifier, {attributes: true, attributeFilter: ['hidden']});
    const stageObserver = new MutationObserver(syncCurrentTool);
    for (const stage of document.querySelectorAll('[data-workspace-stage]')) {
        stageObserver.observe(stage, {attributes: true, attributeFilter: ['aria-current']});
    }
    stageObserver.observe(byId('studio-session'), {attributes: true, attributeFilter: ['hidden']});

    window.aemSavedWorkspaces = {
        commands() {
            const choices = workspaces.map(workspace => ({
                label: `Activate workspace ${workspace.name}`,
                keywords: `workspace: ${workspace.name}`,
                run: () => activate(workspace.name),
            }));
            if (activeName) choices.push({label: 'Switch to General workspace', keywords: 'workspace: General', run: () => activate(null)});
            return choices;
        },
    };

    fetch(endpoint, {cache: 'no-store'}).then(async response => {
        if (!response.ok) throw new Error('Could not load your workspaces.');
        const saved = await response.json();
        workspaces = saved.workspaces;
        activeName = saved.active_workspace ?? null;
        status.textContent = workspaces.length ? '' : 'Create a workspace to pin your tools.';
        renderList();
        renderShell();
        // Restore the shell without taking focus from first-run setup or an open project.
        syncCurrentTool();
    }).catch(() => {
        status.textContent = 'Could not load your workspaces. Reopen the app to try again.';
    });
})();
