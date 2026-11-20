(() => {
    const dock = document.getElementById('workspace-dock');
    const toggle = document.getElementById('dock-tools');
    const tray = document.getElementById('desktop-tool-tray');
    const command = document.getElementById('command-search-button');
    const commandDialog = document.getElementById('command-search-dialog');
    const headerContext = document.getElementById('studio-header-context');
    const headerProject = document.getElementById('studio-header-project');
    const headerTransport = document.getElementById('studio-header-transport');
    const studioProject = document.getElementById('studio-active-project');
    const studioName = document.getElementById('studio-active-name');
    const play = document.getElementById('studio-play');
    const verify = document.getElementById('home-verify-content');
    const verifyQuickAction = tray.querySelector('[data-dock-action="verify"]');
    const transcribe = tray.querySelector('[data-panel="stt-panel"]');
    const transcribeQuickAction = tray.querySelector('[data-dock-action="transcribe"]');
    let paletteFromTray = false;

    function openTray(open, restoreFocus = false) {
        tray.hidden = !open;
        toggle.setAttribute('aria-expanded', String(open));
        if (!open && restoreFocus) toggle.focus();
    }

    function focusPanel(panelId) {
        const panel = document.getElementById(panelId);
        const heading = panel.querySelector('h1, .panel-header h2, .card-title') || panel;
        heading.tabIndex = -1;
        heading.focus({preventScroll:true});
    }

    function refreshHeader() {
        const inStudio = document.getElementById('project-studio-panel').classList.contains('active');
        headerContext.hidden = !inStudio;
        headerProject.textContent = studioName.textContent;
        headerTransport.hidden = !inStudio || studioProject.disabled;
    }

    headerTransport.append(play.closest('.studio-transport-buttons'), document.getElementById('studio-time'));
    const editorObserver = new MutationObserver(refreshHeader);
    editorObserver.observe(studioName, {childList: true, subtree: true});
    editorObserver.observe(studioProject, {attributes:true, attributeFilter:['disabled']});
    refreshHeader();

    toggle.addEventListener('click', () => openTray(tray.hidden));
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
        if (detail.changed) window.scrollTo(0, 0);
    });
    dock.querySelectorAll('.sidebar-nav-item[data-panel]').forEach(item => {
        item.addEventListener('click', () => focusPanel(document.querySelector('main > .panel.active').id));
    });
    document.getElementById('desktop-build').addEventListener('click', () => {
        switchPanel('about-panel');
        focusPanel('about-panel');
    });

    command.addEventListener('click', () => {
        paletteFromTray = true;
        openTray(false);
    });
    commandDialog.addEventListener('close', () => {
        if (paletteFromTray && (document.activeElement === document.body || document.activeElement === command)) {
            toggle.focus();
        }
        paletteFromTray = false;
    });
    function syncQuickActions() {
        verifyQuickAction.hidden = verify.hidden;
        transcribeQuickAction.hidden = transcribe.hidden || transcribe.style.display === 'none';
    }
    const quickObserver = new MutationObserver(syncQuickActions);
    quickObserver.observe(verify, {attributes:true, attributeFilter:['hidden']});
    quickObserver.observe(transcribe, {attributes:true, attributeFilter:['hidden','style']});
    syncQuickActions();

    transcribeQuickAction.addEventListener('click', () => transcribe.click());
    verifyQuickAction.addEventListener('click', () => {
        switchPanel('upload-panel');
        window.aemWorkspace.openVerifier();
    });
    tray.querySelector('[data-dock-action="clean"]').addEventListener('click', () => {
        switchPanel('upload-panel');
        if (document.getElementById('studio-session').hidden) {
            document.getElementById('upload-zone').focus({preventScroll:true});
            document.getElementById('file-input').click();
        } else {
            window.aemWorkspace.selectStage('clean', true);
        }
    });
})();
