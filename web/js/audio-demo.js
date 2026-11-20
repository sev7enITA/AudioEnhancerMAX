/* One native audio element keeps A/B playback exclusive and keyboard accessible. */
(() => {
    'use strict';
    const root = document.getElementById('audio-demo');
    if (!root) return;
    const audio = root.querySelector('audio[data-demo-player]');
    const title = root.querySelector('[data-demo-now]');
    const status = root.querySelector('[data-demo-status]');
    const retry = root.querySelector('[data-demo-retry]');
    const examples = [...root.querySelectorAll('[data-demo-example]')];
    const versions = [...root.querySelectorAll('[data-demo-version]')];
    const links = [...root.querySelectorAll('[data-demo-download]')];
    const labels = {hiss: 'Background hiss', hum: 'Electrical hum', rumble: 'Low-frequency rumble'};
    let example = 'hiss';
    let version = 'before';
    let sequence = 0;
    let desiredTime = 0;
    let resume = false;
    let loading = false;
    let cancelLoad = () => {};

    const path = (side) => `audio/demos/${example}-${side}.wav`;
    const updateLabels = () => {
        examples.forEach(button => button.setAttribute('aria-pressed', String(button.dataset.demoExample === example)));
        versions.forEach(button => button.setAttribute('aria-pressed', String(button.dataset.demoVersion === version)));
        title.textContent = `${labels[example]} · ${version === 'before' ? 'Before' : 'After'}`;
        audio.setAttribute('aria-label', `${labels[example]}, ${version}`);
        links.forEach(link => { link.href = path(link.dataset.demoDownload); });
    };
    const fail = () => {
        loading = false;
        resume = false;
        audio.pause();
        status.textContent = 'This sample could not play. Retry, or download the WAV files below.';
        retry.hidden = false;
        root.removeAttribute('aria-busy');
    };
    const load = ({reset = false} = {}) => {
        const token = ++sequence;
        cancelLoad();
        if (!loading) {
            desiredTime = reset ? 0 : audio.currentTime;
            resume = !audio.paused && !audio.ended;
        } else if (reset) {
            desiredTime = 0;
        }
        audio.pause();
        loading = true;
        retry.hidden = true;
        root.setAttribute('aria-busy', 'true');
        status.textContent = 'Loading sample…';
        updateLabels();
        const ready = async () => {
            if (token !== sequence) return;
            loading = false;
            root.removeAttribute('aria-busy');
            const duration = Number.isFinite(audio.duration) ? audio.duration : 0;
            const position = Math.min(desiredTime, Math.max(0, duration - 0.025));
            const canSeek = position === 0 || Array.from({length: audio.seekable.length}, (_, i) => i)
                .some(i => audio.seekable.start(i) <= position && audio.seekable.end(i) >= position);
            audio.currentTime = canSeek ? position : 0;
            status.textContent = `${version === 'before' ? 'Before' : 'After'} ready. ${reset ? 'New example starts at the beginning.' : canSeek ? 'Playback position preserved.' : 'Seeking is unavailable in this browser. Starting from the beginning.'}`;
            if (resume) {
                try { await audio.play(); }
                catch (_) {
                    if (token === sequence) status.textContent = 'Sample ready. Press Play to continue.';
                }
            }
            if (token === sequence) resume = false;
        };
        const error = () => { if (token === sequence) fail(); };
        audio.addEventListener('loadedmetadata', ready, {once: true});
        audio.addEventListener('error', error, {once: true});
        cancelLoad = () => {
            audio.removeEventListener('loadedmetadata', ready);
            audio.removeEventListener('error', error);
        };
        audio.src = path(version);
        audio.load();
    };

    examples.forEach(button => button.addEventListener('click', () => {
        if (button.dataset.demoExample === example) return;
        example = button.dataset.demoExample;
        load({reset: true});
    }));
    versions.forEach(button => button.addEventListener('click', () => {
        if (button.dataset.demoVersion === version) return;
        version = button.dataset.demoVersion;
        load();
    }));
    retry.addEventListener('click', () => load());
    audio.addEventListener('error', fail);
    // Also coordinate any native audio controls elsewhere on the page.
    document.addEventListener('play', event => {
        if (!(event.target instanceof HTMLMediaElement)) return;
        document.querySelectorAll('audio, video').forEach(other => {
            if (other !== event.target) other.pause();
        });
    }, true);
    root.querySelectorAll('[data-demo-enhanced]').forEach(element => { element.hidden = false; });
    updateLabels();
})();
