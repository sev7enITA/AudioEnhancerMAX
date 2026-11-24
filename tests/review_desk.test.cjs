const assert = require("node:assert/strict");
const { createHash, webcrypto } = require("node:crypto");
const { test } = require("node:test");

globalThis.crypto ??= webcrypto;
require("../frontend/review-desk/engine.js");
const desk = globalThis.reviewDesk;

test("checks SRT timing, overlap and readability and keeps text inert", () => {
    const value = "\uFEFF1\r\n00:00:00,000 --> 00:00:02,000\r\n<i>Title</i>\r\n\r\n"
        + "2\r\n00:00:01,000 --> 00:00:01,200\r\nA very fast subtitle that is longer than forty-two characters.\r\n\r\n"
        + "3\r\n00:00:09,000 --> 00:00:02,000\r\nWrong direction";
    const parsed = desk.parseCaptions(value);
    assert.equal(parsed.format, "SRT");
    assert.equal(parsed.cues[0].text, "Title");
    assert.deepEqual(parsed.issues.map(issue => issue.code), ["overlap", "reading-speed", "long-cue", "invalid-cue"]);
});

test("parses WebVTT and keeps clip subtitles aligned to WAV time zero", () => {
    const parsed = desk.parseCaptions("WEBVTT\n\nNOTE comment\nThis is not a cue.\n\n"
        + "opening\n00:01.000 --> 00:04.000 line:0\nHello\n\n01:01.000 --> 01:04.000\nNext section");
    assert.equal(parsed.issues.length, 0);
    assert.deepEqual(desk.suggestChapters(parsed.cues), [
        { start: 1000, title: "Hello" }, { start: 61000, title: "Next section" },
    ]);
    assert.equal(desk.clipCaptions(parsed.cues, 2000, 3500), "1\n00:00:00,000 --> 00:00:01,500\nHello\n");
    assert.throws(() => desk.clipCaptions(parsed.cues, -1, 3500));
    assert.throws(() => desk.parseCaptions("bad\n\n".repeat(1501)), /1,500 cues/);
});

test("cuts PCM frames without resampling and rejects truncated inputs", () => {
    const samples = new Int16Array(8000).map((_, index) => index);
    const wav = new ArrayBuffer(44 + samples.byteLength);
    const header = new DataView(wav);
    for (const [index, value] of [[0, 0x52494646], [8, 0x57415645], [12, 0x666d7420], [36, 0x64617461]]) {
        header.setUint32(index, value);
    }
    header.setUint32(4, wav.byteLength - 8, true);
    header.setUint32(16, 16, true);
    header.setUint16(20, 1, true);
    header.setUint16(22, 1, true);
    header.setUint32(24, 8000, true);
    header.setUint32(28, 16000, true);
    header.setUint16(32, 2, true);
    header.setUint16(34, 16, true);
    header.setUint32(40, samples.byteLength, true);
    new Int16Array(wav, 44).set(samples);
    const output = desk.clipWave(wav, 250, 750);
    assert.equal(output.byteLength, 8044);
    assert.equal(new Int16Array(output, 44)[0], 2000);
    assert.equal(new Int16Array(output, 44).at(-1), 5999);
    assert.throws(() => desk.clipWave(wav.slice(0, 50), 250, 750), /incomplete/);
    assert.throws(() => desk.clipWave(wav, 250, 1750), /fit/);
});

test("publishing evidence can be independently recomputed", async () => {
    const content = { title: "Intervista à Roma", chapters: [{ start: 500, title: "Introduzione" }] };
    const pack = await desk.publishingPack(content);
    assert.equal(pack.format, "audioenhancer.review-pack.v1");
    assert.equal(pack.digest.content, createHash("sha256").update(JSON.stringify(content)).digest("hex"));
});
