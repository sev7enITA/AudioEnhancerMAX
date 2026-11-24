(() => {
"use strict";
/* Local caption analysis and portable review evidence. */
const CAPTION_BYTES = 512 * 1024;
const AUDIO_BYTES = 32 * 1024 * 1024;
const EXPORT_BYTES = 8 * 1024 * 1024;
const MAX_CUES = 1500;

function milliseconds(value, vtt) {
    const match = /^(?:(\d{2,}):)?([0-5]\d):([0-5]\d)([,.])(\d{3})$/.exec(value);
    if (!match || (vtt ? match[4] !== "." : !match[1] || match[4] !== ",")) return null;
    const result = ((Number(match[1] || 0) * 60 + Number(match[2])) * 60 + Number(match[3])) * 1000 + Number(match[5]);
    return Number.isSafeInteger(result) && result <= 86_400_000 ? result : null;
}

function timestamp(value, decimal = ".") {
    const pad = (part, length = 2) => String(part).padStart(length, "0");
    return [
        pad(Math.floor(value / 3_600_000)),
        pad(Math.floor(value / 60_000) % 60),
        pad(Math.floor(value / 1000) % 60),
    ].join(":") + decimal + pad(value % 1000, 3);
}

function parseCaptions(text) {
    const source = text.replace(/^\uFEFF/, "").replace(/\r\n?/g, "\n").trim();
    const vtt = /^WEBVTT(?:[ \t][^\n]*|)(?:\n|$)/.test(source);
    const blocks = source.split(/\n[ \t]*\n+/);
    if (vtt) blocks.shift();
    if (blocks.length > MAX_CUES) throw new Error("Choose captions with at most 1,500 cues.");

    const cues = [];
    const issues = [];
    let previousStart = -1;
    let latestEnd = -1;
    for (const [index, block] of blocks.entries()) {
        if (vtt && /^(NOTE(?:[ \t]|$)|STYLE\s*$|REGION\s*$)/.test(block.split("\n", 1)[0])) continue;
        const rows = block.split("\n");
        const offset = rows[0].includes("-->") ? 0 : 1;
        const timing = /^([^\s]+)[ \t]+-->[ \t]+([^\s]+)(?:[ \t]+.*)?$/.exec(rows[offset] || "");
        const start = timing && milliseconds(timing[1], vtt);
        const end = timing && milliseconds(timing[2], vtt);
        const lines = rows.slice(offset + 1).map(line => line.trim()).filter(Boolean);
        const number = index + 1;
        if (start === null || end === null || end <= start || !lines.length) {
            issues.push({ cue: number, code: "invalid-cue", severity: "error" });
            continue;
        }
        if (start < previousStart) issues.push({ cue: number, code: "out-of-order", severity: "error" });
        if (start < latestEnd) issues.push({ cue: number, code: "overlap", severity: "warning" });
        const visible = lines.map(line => line.replace(/<[^>]{1,100}>/g, ""));
        const characters = [...visible.join(" ")].length;
        if (characters * 1000 > (end - start) * 20) issues.push({ cue: number, code: "reading-speed", severity: "warning" });
        if (visible.length > 2 || visible.some(line => [...line].length > 42)) {
            issues.push({ cue: number, code: "long-cue", severity: "warning" });
        }
        cues.push({ number, start, end, text: visible.join("\n") });
        previousStart = start;
        latestEnd = Math.max(latestEnd, end);
    }
    if (!cues.length && !issues.length) issues.push({ cue: 0, code: "no-cues", severity: "error" });
    return { format: vtt ? "WebVTT" : "SRT", cues, issues, duration: Math.max(0, latestEnd) };
}

function suggestChapters(cues, interval = 60_000) {
    const sorted = cues.slice().sort((a, b) => a.start - b.start);
    const result = [];
    for (const cue of sorted) {
        if (result.length && cue.start - result.at(-1).start < interval) continue;
        result.push({ start: cue.start, title: [...cue.text.replace(/\s+/g, " ")].slice(0, 80).join("") });
        if (result.length === 80) break;
    }
    return result;
}

function clipCaptions(cues, start, end) {
    if (!Number.isInteger(start) || start < 0 || end <= start || !Number.isInteger(end)) {
        throw new Error("Enter a valid start and end time in seconds.");
    }
    const excerpt = cues
        .filter(cue => cue.start < end && cue.end > start)
        .sort((a, b) => a.start - b.start);
    return excerpt.map((cue, index) => {
        const first = timestamp(Math.max(cue.start, start) - start, ",");
        const last = timestamp(Math.min(cue.end, end) - start, ",");
        return `${index + 1}\n${first} --> ${last}\n${cue.text}\n`;
    }).join("\n");
}

async function sha256(bytes) {
    if (!globalThis.crypto?.subtle) throw new Error("SHA-256 requires a local secure context on this device.");
    const result = await globalThis.crypto.subtle.digest("SHA-256", bytes);
    return Array.from(new Uint8Array(result), byte => byte.toString(16).padStart(2, "0")).join("");
}

async function publishingPack(content) {
    const encoded = new TextEncoder().encode(JSON.stringify(content));
    return { format: "audioenhancer.review-pack.v1", digest: { algorithm: "SHA-256", content: await sha256(encoded) }, content };
}

function clipWave(bytes, start, end) {
    const view = new DataView(bytes);
    const fourCC = (offset, tag) => view.getUint32(offset) === tag;
    if (view.byteLength < 44 || !fourCC(0, 0x52494646) || !fourCC(8, 0x57415645)) {
        throw new Error("Choose an uncompressed PCM WAV for the audio clip.");
    }
    const limit = view.getUint32(4, true) + 8;
    if (limit > view.byteLength || limit < 44) throw new Error("The WAV is incomplete.");
    let format;
    let data;
    for (let offset = 12; offset + 8 <= limit;) {
        const size = view.getUint32(offset + 4, true);
        const body = offset + 8;
        if (body + size > limit) throw new Error("The WAV is incomplete.");
        if (fourCC(offset, 0x666d7420) && size >= 16 && !format) {
            format = {
                codec: view.getUint16(body, true), channels: view.getUint16(body + 2, true),
                rate: view.getUint32(body + 4, true), block: view.getUint16(body + 12, true),
                bits: view.getUint16(body + 14, true),
            };
        }
        if (fourCC(offset, 0x64617461) && !data) data = { body, size };
        offset = body + size + (size & 1);
    }
    if (!data || !format || format.codec !== 1 || ![1, 2].includes(format.channels)
        || ![8, 16, 24, 32].includes(format.bits) || format.rate < 8000 || format.rate > 192000
        || format.block !== format.channels * format.bits / 8 || data.size % format.block) {
        throw new Error("Use a mono or stereo PCM WAV with 8–192 kHz sample rate.");
    }
    const first = Math.round(start * format.rate / 1000) * format.block;
    const last = Math.round(end * format.rate / 1000) * format.block;
    if (first < 0 || last <= first || last > data.size) throw new Error("The clip must fit inside the selected WAV.");
    const length = last - first;
    const padding = length & 1;
    if (44 + length + padding > EXPORT_BYTES) throw new Error("Shorten the range to a WAV under 8 MiB.");
    const result = new ArrayBuffer(44 + length + padding);
    const header = new DataView(result);
    header.setUint32(0, 0x52494646);
    header.setUint32(4, 36 + length + padding, true);
    header.setUint32(8, 0x57415645);
    header.setUint32(12, 0x666d7420);
    header.setUint32(16, 16, true);
    header.setUint16(20, 1, true);
    header.setUint16(22, format.channels, true);
    header.setUint32(24, format.rate, true);
    header.setUint32(28, format.rate * format.block, true);
    header.setUint16(32, format.block, true);
    header.setUint16(34, format.bits, true);
    header.setUint32(36, 0x64617461);
    header.setUint32(40, length, true);
    new Uint8Array(result, 44, length).set(new Uint8Array(bytes, data.body + first, length));
    return result;
}

globalThis.reviewDesk = Object.freeze({ CAPTION_BYTES, AUDIO_BYTES, EXPORT_BYTES, timestamp, parseCaptions, suggestChapters, clipCaptions, sha256, publishingPack, clipWave });
})();
