(() => {
    const byId = id => document.getElementById(id);
    const form = byId('workspace-form');
    const controls = byId('workspace-form-controls');
    const name = byId('new-workspace-name');
    const order = byId('workspace-tool-order');
    const select = byId('workspace-module-select');
    const list = byId('saved-workspaces');
    const status = byId('workspace-settings-status');
    const formStatus = byId('workspace-form-status');
    const create = byId('create-workspace');
    const tools = new Map([
        ['upload-panel', 'Open and clean up audio'],
        ['verify-content', 'Verify content'],
        ...[...document.querySelectorAll('.studio-tools [data-panel]')].map(button => [
            button.dataset.panel,
            [...button.childNodes].filter(node => node.nodeType === Node.TEXT_NODE).map(node => node.textContent).join(' ').trim(),
        ]),
    ]);
    let workspaces = [];
    let editing = null;
    let selected = [];
    let saving = false;

    function button(label, action, accessibleLabel) {
        const control = document.createElement('button');
        control.type = 'button';
        control.className = 'btn btn-secondary';
        control.textContent = label;
        if (accessibleLabel) control.setAttribute('aria-label', accessibleLabel);
        control.addEventListener('click', action);
        return control;
    }

    function openTool(tool) {
        const panel = tool === 'verify-content' ? 'upload-panel' : tool;
        switchPanel(panel);
        if (tool === 'verify-content') {
            const verifier = byId('credentials-inspector');
            if (verifier.hidden) {
                switchPanel('workspaces-panel');
                status.textContent = 'Verify Content is unavailable in this build.';
                return;
            }
            verifier.open = true;
            verifier.querySelector('summary').focus();
            return;
        }
        const main = byId('main-content');
        const heading = [...main.querySelectorAll('.panel.active h1, .panel.active .card-title')]
            .find(node => node.getClientRects().length) || main;
        heading.tabIndex = -1;
        heading.focus();
    }

    function renderList() {
        list.replaceChildren();
        create.disabled = saving || workspaces.length >= 12;
        workspaces.forEach((workspace, index) => {
            const item = document.createElement('article');
            item.className = 'workspace-saved-item';
            const title = document.createElement('h3');
            title.textContent = workspace.name;
            const modules = document.createElement('ol');
            modules.className = 'workspace-collection-modules';
            for (const tool of workspace.tools) {
                const row = document.createElement('li');
                row.append(button(tools.get(tool) || tool, () => openTool(tool)));
                modules.append(row);
            }
            const edit = button('Edit', () => editWorkspace(index), `Edit ${workspace.name}`);
            const remove = button('Remove', () => {
                if (!saving && window.confirm(`Remove the workspace “${workspace.name}”?`)) {
                    persist(workspaces.filter((_, position) => position !== index));
                }
            }, `Remove ${workspace.name}`);
            edit.disabled = remove.disabled = saving;
            const actions = document.createElement('div');
            actions.className = 'workspace-collection-actions';
            actions.append(edit, remove);
            item.append(title, modules, actions);
            list.append(item);
        });
    }

    function renderSelection() {
        order.replaceChildren();
        selected.forEach((tool, index) => {
            const label = tools.get(tool) || tool;
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
            .map(([tool, label]) => new Option(label, tool)));
        select.disabled = byId('workspace-add-module').disabled = !select.options.length;
    }

    function editWorkspace(index) {
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

    async function persist(next) {
        if (saving) return;
        saving = controls.disabled = true;
        renderList();
        try {
            const response = await fetch('/api/settings/workspaces', {
                method: 'PUT',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({workspaces: next}),
            });
            if (!response.ok) {
                const {detail} = await response.json();
                throw new Error(typeof detail === 'string' ? detail : 'Could not save your workspaces.');
            }
            workspaces = (await response.json()).workspaces;
            form.hidden = true;
            status.textContent = 'Workspaces saved.';
        } catch (error) {
            (form.hidden ? status : formStatus).textContent = error.message;
        } finally {
            saving = controls.disabled = false;
            renderList();
            if (form.hidden) (create.disabled ? byId('workspaces-title') : create).focus();
        }
    }

    byId('home-workspaces').addEventListener('click', () => {
        switchPanel('workspaces-panel');
        byId('workspaces-title').focus();
    });
    create.addEventListener('click', () => editWorkspace(null));
    byId('workspace-cancel').addEventListener('click', () => {
        form.hidden = true;
        (create.disabled ? byId('workspaces-title') : create).focus();
    });
    byId('workspace-add-module').addEventListener('click', () => {
        if (!select.value) return;
        const label = tools.get(select.value);
        selected.push(select.value);
        renderSelection();
        if (select.disabled) order.lastElementChild.querySelector('button:last-child').focus();
        formStatus.textContent = `${label} added.`;
    });
    form.addEventListener('submit', event => {
        event.preventDefault();
        if (!selected.length) {
            formStatus.textContent = 'Add at least one tool.';
            select.focus();
            return;
        }
        const next = [...workspaces];
        next[editing ?? next.length] = {name: name.value.trim(), tools: selected};
        persist(next);
    });

    fetch('/api/settings/workspaces', {cache: 'no-store'}).then(async response => {
        if (!response.ok) throw new Error('Could not load your workspaces.');
        workspaces = (await response.json()).workspaces;
        status.textContent = workspaces.length ? '' : 'Create a workspace and add the tools you use most often.';
        renderList();
    }).catch(() => {
        status.textContent = 'Could not load your workspaces. Reopen the app to try again.';
    });
})();
