(() => {
    "use strict";
    const tool = globalThis.reviewDesk;
    const byId = id => document.getElementById(id);
    const on = (id, type, callback) => byId(id).addEventListener(type, callback);
    const status = (id, text) => { byId(id).textContent = text; };
    const errors = {
        "invalid-cue": "invalid timing or empty cue", "out-of-order": "cue starts out of order",
        overlap: "overlaps an earlier cue", "reading-speed": "over 20 characters per second",
        "long-cue": "over 42 characters per line or more than two lines", "no-cues": "no usable cues",
    };
    let captions;
    let chapters = [];
    let pair = [];
    let decision;
    let active = -1;
    let clipSource;
    let lastClip;
    let captionRead = 0;
    let audioRead = 0;
    let clipRead = 0;
    const heard = new Set();
    const pendingSources = new Set();
    const busy = new Set();
    const player = byId("listener");

    async function fingerprint(file, max) {
        if (!file.size || file.size > max) throw new Error(`Choose a non-empty file up to ${max / 1024} KiB.`);
        const bytes = await file.arrayBuffer();
        return { bytes, identity: { name: file.name, bytes: file.size, sha256: await tool.sha256(bytes) } };
    }

    function save(name, data, type) {
        const bytes = typeof data === "string" ? new TextEncoder().encode(data) : new Uint8Array(data);
        if (bytes.length > tool.EXPORT_BYTES) throw new Error("This export exceeds 8 MiB.");
        const ios = window.webkit?.messageHandlers?.reviewExport;
        const android = window.ReviewExport;
        if (ios || android) {
            let binary = "";
            for (let start = 0; start < bytes.length; start += 8192) {
                binary += String.fromCharCode(...bytes.subarray(start, start + 8192));
            }
            const encoded = btoa(binary);
            if (ios) ios.postMessage({ name, data: encoded });
            else android.save(name, encoded);
            return;
        }
        const url = URL.createObjectURL(new Blob([bytes], { type }));
        const link = document.createElement("a");
        link.download = name;
        link.href = url;
        // A connected anchor is required by WebKit.
        link.hidden = true;
        document.body.append(link);
        link.click();
        link.remove();
        setTimeout(() => URL.revokeObjectURL(url), 30_000);
    }

    async function run(button, message, operation) {
        if (busy.has(button.id)) return;
        busy.add(button.id);
        button.disabled = true;
        try { await operation(); }
        catch (error) { status(message, error.message || "The operation failed."); }
        finally {
            busy.delete(button.id);
            button.disabled = false;
            updateExports();
        }
    }

    function updateExports() {
        byId("export-clip").disabled = busy.has("export-clip") || !captions?.cues.length;
        byId("export-wav").disabled = busy.has("export-wav") || !clipSource;
        byId("export-chapters").disabled = busy.has("export-chapters") || !chapters.length;
        byId("export-pack").disabled = busy.has("export-pack") || pendingSources.size > 0;
    }

    on("captions", "change", async event => {
        const file = event.target.files[0];
        if (!file) return;
        const revision = ++captionRead;
        pendingSources.add("captions");
        captions = undefined;
        lastClip = undefined;
        byId("suggest").disabled = true;
        byId("issues").replaceChildren();
        updateExports();
        status("caption-status", "Checking file…");
        try {
            const { bytes, identity } = await fingerprint(file, tool.CAPTION_BYTES);
            const result = tool.parseCaptions(new TextDecoder("utf-8", { fatal: true }).decode(bytes));
            if (revision !== captionRead) return;
            captions = { ...result, input: identity };
            byId("suggest").disabled = !result.cues.length;
            if (result.duration) byId("clip-out").value = Math.min(result.duration / 1000, 30);
            const first = result.issues.slice(0, 30);
            for (const issue of first) {
                const item = document.createElement("li");
                item.textContent = (issue.cue ? `Cue ${issue.cue} · ` : "") + errors[issue.code];
                byId("issues").append(item);
            }
            status("caption-status", `${result.format} · ${result.cues.length} cues · ${result.issues.length} flags${first.length < result.issues.length ? " (first 30 shown)" : ""}`);
        } catch (error) {
            if (revision === captionRead) status("caption-status", error.message);
        } finally {
            if (revision === captionRead) pendingSources.delete("captions");
            updateExports();
        }
    });

    function field(label, props, changed) {
        const wrapper = document.createElement("label");
        wrapper.textContent = label;
        const input = Object.assign(document.createElement("input"), props);
        input.addEventListener("input", () => changed(input));
        wrapper.append(input);
        return wrapper;
    }

    function renderChapters() {
        const rows = chapters.map((chapter, index) => {
            const row = document.createElement("div");
            row.className = "chapter-row";
            const remove = document.createElement("button");
            remove.textContent = "Remove";
            remove.setAttribute("aria-label", `Remove chapter ${index + 1}`);
            remove.onclick = () => { chapters.splice(index, 1); renderChapters(); byId("add-chapter").focus(); };
            row.append(
                field(`Chapter ${index + 1} time (seconds)`, { type: "number", min: 0, max: 86400, step: .001, value: chapter.start / 1000 },
                    input => { chapter.start = Math.round(input.valueAsNumber * 1000); }),
                field(`Chapter ${index + 1} title`, { type: "text", maxLength: 160, value: chapter.title },
                    input => { chapter.title = input.value; }),
                remove,
            );
            return row;
        });
        byId("chapter-list").replaceChildren(...rows);
        updateExports();
        byId("add-chapter").disabled = chapters.length >= 80;
    }

    function reviewedChapters() {
        const list = chapters.map(({ start, title }) => ({ start, title: title.trim() })).sort((a, b) => a.start - b.start);
        if (list.some((item, index) => !item.title || !Number.isInteger(item.start) || item.start < 0
            || item.start > 86_400_000 || (index > 0 && item.start === list[index - 1].start))) {
            throw new Error("Give each chapter a title and a distinct start time.");
        }
        return list;
    }

    on("suggest", "click", () => {
        const suggested = tool.suggestChapters(captions.cues);
        chapters = chapters.concat(suggested.filter(item => !chapters.some(chapter => chapter.start === item.start))).slice(0, 80);
        renderChapters();
    });
    on("add-chapter", "click", () => {
        chapters.push({ start: 0, title: "" });
        renderChapters();
        byId("chapter-list").lastElementChild.querySelector('input[type="text"]').focus();
    });
    on("export-chapters", "click", event => run(event.currentTarget, "chapter-status", () => {
        const text = reviewedChapters().map(item => `${tool.timestamp(item.start)} ${item.title}`).join("\n");
        save("aemax-chapters.txt", text + "\n", "text/plain");
        status("chapter-status", "Chapter list prepared.");
    }));

    function clipRange() {
        const start = Math.round(byId("clip-in").valueAsNumber * 1000);
        const end = Math.round(byId("clip-out").valueAsNumber * 1000);
        if (!Number.isInteger(start) || !Number.isInteger(end) || start < 0 || end <= start || end > 86_400_000) {
            throw new Error("Enter a valid in and out range in seconds.");
        }
        return { start, end };
    }

    on("clip-audio", "change", async event => {
        const file = event.target.files[0];
        if (!file) return;
        const revision = ++clipRead;
        pendingSources.add("clip");
        clipSource = undefined;
        lastClip = undefined;
        updateExports();
        status("clip-status", "Reading WAV…");
        try {
            const source = await fingerprint(file, tool.AUDIO_BYTES);
            if (revision !== clipRead) return;
            clipSource = source;
            status("clip-status", "WAV ready. Use the same range for WAV and SRT.");
        } catch (error) {
            if (revision === clipRead) status("clip-status", error.message);
        } finally {
            if (revision === clipRead) pendingSources.delete("clip");
            updateExports();
        }
    });
    on("clip-in", "input", () => { lastClip = undefined; });
    on("clip-out", "input", () => { lastClip = undefined; });
    for (const [id, ext, mime] of [["export-clip", "srt", "text/plain"], ["export-wav", "wav", "audio/wav"]]) {
        on(id, "click", event => run(event.currentTarget, "clip-status", async () => {
            const range = clipRange();
            const source = ext === "srt" ? captions : clipSource;
            if (!source) throw new Error("Choose a source first.");
            const data = ext === "srt" ? tool.clipCaptions(source.cues, range.start, range.end)
                : tool.clipWave(source.bytes, range.start, range.end);
            if (!data.length && !data.byteLength) throw new Error("No captions intersect this range.");
            const digest = await tool.sha256(typeof data === "string" ? new TextEncoder().encode(data) : data);
            const currentRange = clipRange();
            if (source !== (ext === "srt" ? captions : clipSource)
                || currentRange.start !== range.start || currentRange.end !== range.end) {
                throw new Error("The source or range changed. Export the current selection.");
            }
            const sameRange = lastClip?.start === range.start && lastClip.end === range.end;
            save(`aemax-clip.${ext}`, data, mime);
            lastClip = { ...(sameRange ? lastClip : {}), ...range,
                [ext]: { sha256: digest, source: ext === "wav" ? source.identity : source.input } };
            status("clip-status", `${ext.toUpperCase()} prepared for ${tool.timestamp(range.start)} to ${tool.timestamp(range.end)}.`);
        }));
    }

    function updateListen() {
        for (const id of ["play-a", "play-b", "stop"]) byId(id).disabled = pair.length !== 2;
        for (const id of ["pick-a", "pick-b", "pick-tie"]) byId(id).disabled = heard.size !== 2 || !!decision;
        for (const [index, id] of ["play-a", "play-b"].entries()) {
            byId(id).setAttribute("aria-pressed", String(index === active && !player.paused));
        }
    }

    function resetAudio() {
        player.pause();
        player.removeAttribute("src");
        player.load();
        for (const entry of pair) URL.revokeObjectURL(entry.url);
        pair = [];
        active = -1;
        decision = undefined;
        heard.clear();
        byId("reveal").hidden = true;
        status("reveal", "");
        updateListen();
    }

    on("listen-files", "change", async event => {
        const files = [...event.target.files];
        event.target.value = "";
        const revision = ++audioRead;
        resetAudio();
        if (files.length !== 2) {
            pendingSources.delete("listening");
            updateExports();
            status("listen-status", "Choose exactly two audio files.");
            return;
        }
        pendingSources.add("listening");
        updateExports();
        status("listen-status", "Preparing anonymous versions…");
        try {
            const validated = [];
            for (const file of files) validated.push((await fingerprint(file, tool.AUDIO_BYTES)).identity);
            if (revision !== audioRead) return;
            const first = crypto.getRandomValues(new Uint8Array(1))[0] & 1;
            pair = [first, first ^ 1].map(index => ({ ...validated[index], url: URL.createObjectURL(files[index]) }));
            status("listen-status", "Both versions are ready. Play A and B to unlock the decision.");
            updateListen();
        } catch (error) {
            if (revision === audioRead) status("listen-status", error.message);
        } finally {
            if (revision === audioRead) pendingSources.delete("listening");
            updateExports();
        }
    });

    for (const [index, id] of ["play-a", "play-b"].entries()) on(id, "click", async () => {
        if (pair.length !== 2) return;
        const revision = audioRead;
        active = index;
        player.src = pair[index].url;
        try { await player.play(); }
        catch (_) {
            if (revision === audioRead && active === index) status("listen-status", "This audio format could not be played here. Try PCM WAV.");
        }
        updateListen();
    });
    on("stop", "click", () => { player.pause(); updateListen(); });
    for (const event of ["play", "pause", "ended"]) player.addEventListener(event, updateListen);
    for (const event of ["timeupdate", "ended"]) player.addEventListener(event, () => {
        if (active >= 0 && player.currentTime >= Math.min(0.25, player.duration) && Number.isFinite(player.duration)) {
            heard.add(active);
            updateListen();
        }
    });
    for (const [index, id] of ["pick-a", "pick-b", "pick-tie"].entries()) on(id, "click", () => {
        if (heard.size !== 2 || decision) return;
        const versions = pair.map(({ name, bytes, sha256 }) => ({ name, bytes, sha256 }));
        decision = { preference: ["A", "B", "tie"][index], A: versions[0], B: versions[1] };
        byId("reveal").hidden = false;
        status("reveal", `A · ${decision.A.name}\nB · ${decision.B.name}\n${index === 2 ? "No preference recorded." : `Preferred ${decision.preference}.`}`);
        status("listen-status", "Decision saved for the publishing pack.");
        updateListen();
    });

    function packContent() {
        if (pendingSources.size) throw new Error("Wait for the selected files to finish loading.");
        const title = byId("publish-name").value.trim();
        if (!title) { byId("publish-name").focus(); throw new Error("Enter a title for the publishing pack."); }
        return {
            title, notes: byId("publish-notes").value.trim(), captions: captions || null,
            chapters: reviewedChapters(), clip: lastClip || null, listening: decision || null,
        };
    }

    on("export-pack", "click", event => run(event.currentTarget, "export-status", async () => {
        const content = packContent();
        const revisions = [captionRead, clipRead, audioRead].join(":");
        const pack = await tool.publishingPack(content);
        if (revisions !== [captionRead, clipRead, audioRead].join(":")
            || JSON.stringify(content) !== JSON.stringify(packContent())) {
            throw new Error("The review changed. Export the current publishing pack.");
        }
        save("aemax-review-pack.json", JSON.stringify(pack, null, 2) + "\n", "application/json");
        status("export-status", `Pack prepared · SHA-256 ${pack.digest.content}`);
    }));
})();
