(() => {
    const home = document.getElementById('upload-panel');
    const list = document.getElementById('studio-recent-projects');
    const status = document.getElementById('studio-home-status');
    const sample = document.getElementById('open-workspace-sample');
    const retry = document.getElementById('studio-recent-retry');
    const transcribe = document.querySelector('#desktop-tool-tray [data-panel="stt-panel"]');
    const transcribeButton = document.getElementById('studio-home-transcribe');
    const dateFormat = new Intl.DateTimeFormat(undefined, {dateStyle: 'medium'});
    let requestId = 0;
    let opening = false;

    function showStatus(message) {
        status.textContent = message;
        status.hidden = !message;
    }

    async function openInStudio(action, message, trigger) {
        if (opening) return;
        opening = true;
        showStatus(message);
        try {
            await action();
            if (home.classList.contains('active')) {
                switchPanel('project-studio-panel');
                document.getElementById('project-studio-title').focus();
            }
            showStatus('');
        } catch (error) {
            showStatus(error.message || 'The project could not be opened.');
            if (home.classList.contains('active')) trigger.focus({preventScroll: true});
        } finally {
            opening = false;
        }
    }

    function projectRow(project) {
        const item = document.createElement('li');
        const button = document.createElement('button');
        button.type = 'button';
        const name = document.createElement('strong');
        name.textContent = project.name;
        name.title = project.name;
        const detail = document.createElement('span');
        const updated = new Date(project.updated);
        detail.textContent = Number.isFinite(updated.getTime())
            ? dateFormat.format(updated) : `Revision ${project.revision}`;
        button.append(name, detail);
        button.addEventListener('click', () =>
            openInStudio(() => window.aemStudioProjects.open(project.id), 'Opening project…', button));
        item.append(button);
        return item;
    }

    async function refresh() {
        if (opening) return;
        const request = ++requestId;
        sample.hidden = true;
        retry.hidden = true;
        showStatus('Loading projects…');
        try {
            const response = await fetch('/api/studio/projects', {cache: 'no-store'});
            if (!response.ok) throw new Error('Projects could not be loaded.');
            const {projects} = await response.json();
            if (!Array.isArray(projects)) throw new Error('Projects could not be loaded.');
            if (request !== requestId || opening) return;
            list.replaceChildren(...projects.slice(0, 6).map(projectRow));
            sample.hidden = projects.length > 0;
            showStatus(projects.length ? '' : 'No projects yet.');
        } catch {
            if (request !== requestId || opening) return;
            list.replaceChildren();
            showStatus('Projects could not be loaded.');
            retry.hidden = false;
        }
    }

    sample.addEventListener('click', () =>
        openInStudio(() => window.aemStudioProjects.openSample(), 'Opening the sample project…', sample));
    retry.addEventListener('click', refresh);
    document.getElementById('studio-home-new-project').addEventListener('click', () => {
        switchPanel('project-studio-panel');
        document.getElementById('studio-project-new').click();
    });
    transcribeButton.addEventListener('click', () => {
        transcribe.click();
        document.getElementById('stt-title').tabIndex = -1;
        document.getElementById('stt-title').focus({preventScroll:true});
    });
    function syncTranscribeAvailability() {
        transcribeButton.hidden = transcribe.hidden || transcribe.disabled;
    }
    new MutationObserver(syncTranscribeAvailability).observe(transcribe, {
        attributes:true, attributeFilter:['hidden', 'disabled'],
    });
    syncTranscribeAvailability();
    document.addEventListener('aem:panel', ({detail}) => {
        if (detail.panel === home.id && !document.getElementById('studio-welcome').hidden) refresh();
    });
    document.getElementById('close-studio-source').addEventListener('click', () => {
        if (!document.getElementById('studio-welcome').hidden) refresh();
    });
    refresh();
})();
