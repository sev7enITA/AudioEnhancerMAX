"""Exercise the real HTTP audio boundary with generated, non-private fixtures."""
import hashlib
import io
import json
import zipfile

import numpy as np
import pytest
import soundfile as sf
from fastapi.testclient import TestClient

from app import main
from app.services import artifact_store, delivery_compliance, processing_report, project_bundle
from app.services import processing_checkpoint as checkpoints
from app.services import smart_mode, enhancement, runtime_settings
from app.services import speech_editor
from app.utils import audio_io


@pytest.fixture
def api(tmp_path, monkeypatch):
    uploads = tmp_path / 'uploads'
    outputs = tmp_path / 'outputs'
    uploads.mkdir()
    outputs.mkdir()
    for module in (main, audio_io):
        monkeypatch.setattr(module, 'UPLOAD_DIR', uploads)
    for module in (main, audio_io, artifact_store, delivery_compliance, processing_report, speech_editor):
        monkeypatch.setattr(module, 'OUTPUT_DIR', outputs)
    monkeypatch.setattr(smart_mode, 'get_dynamic_parameters', lambda *args: {})
    monkeypatch.setattr(runtime_settings, 'external_service_allowed', lambda *args: False)
    monkeypatch.setattr(project_bundle, 'PROJECTS_DIR', tmp_path / 'projects')
    monkeypatch.setattr(runtime_settings, 'RUNTIME_SETTINGS_FILE', tmp_path / 'privacy.json')
    main._PROCESSING_FILES.clear()
    sr = 48000
    t = np.arange(sr * 2) / sr
    source = (0.08 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    sf.write(uploads / 'fixture.wav', source, sr, subtype='FLOAT')
    return TestClient(main.app), uploads, outputs


def process(client, **options):
    response = client.post('/api/process', json={'file_id': 'fixture', 'options': options})
    assert response.status_code == 200, response.text
    return response.json()


def test_reprocessing_invalidates_conversion_and_binds_compliance_to_download(api):
    client, _, outputs = api
    first = process(client, normalize=True, target_loudness_lufs=-16)
    old_export = client.get('/api/download/fixture?format=mp3&revision=' + first['revision'])
    assert old_export.status_code == 200
    second = process(client, normalize=True, target_loudness_lufs=-23)
    assert second['revision'] != first['revision']
    assert client.get('/api/download/fixture?format=mp3&revision=' + first['revision']).status_code == 409
    exported = client.get('/api/download/fixture?format=mp3&revision=' + second['revision'])
    assert exported.content != old_export.content
    assert exported.headers['x-audio-revision'] == second['revision']
    measured = client.get('/api/compliance/fixture', params={'format': 'mp3', 'revision': second['revision'], 'target_id': 'broadcast-r128'}).json()
    assert measured['format'] == 'mp3'
    assert measured['revision'] == second['revision']
    assert measured['artifact_sha256'] == hashlib.sha256(exported.content).hexdigest()
    assert abs(measured['measurements']['integrated_loudness_lufs'] + 23) < 0.5
    assert (outputs / first['output_url'].split('/')[-1]).exists()
    assert client.get('/api/reports/fixture?revision=' + first['revision']).status_code == 409


def test_changed_primary_format_never_selects_old_wav(api):
    client, _, _ = api
    process(client, normalize=True, target_loudness_lufs=-16)
    current = process(client, normalize=True, target_loudness_lufs=-23, output_format='flac')
    streamed = client.get('/api/audio/fixture?version=processed&revision=' + current['revision'])
    assert streamed.headers['content-type'].startswith('audio/flac')
    assert streamed.headers['x-audio-revision'] == current['revision']


def test_missing_processed_output_does_not_return_original(api):
    client, _, _ = api
    assert client.get('/api/audio/fixture?version=processed').status_code == 404
    assert client.get('/api/download/fixture').status_code == 404
    assert client.get('/api/audio/fixture').status_code == 200


def test_conversion_preserves_stereo_channels(api):
    client, _, _ = api
    t = np.arange(48000) / 48000
    stereo = np.column_stack([0.1*np.sin(2*np.pi*440*t), 0.05*np.sin(2*np.pi*880*t)])
    artifact = artifact_store.publish_audio('stereo', stereo, 48000, 'wav')
    response = client.get('/api/download/stereo?format=flac&revision=' + artifact['revision'])
    decoded, sr = sf.read(io.BytesIO(response.content))
    assert decoded.shape == stereo.shape and sr == 48000
    assert np.max(np.abs(decoded-stereo)) < 2**-22  # PCM_24 quantization, not a perceptual-quality gate.


def test_resume_matches_clean_run_and_tuning_sees_original(api, monkeypatch):
    client, _, outputs = api
    expected = process(client, auto_eq=True, normalize=True)
    reference, _ = sf.read(outputs / expected['output_url'].split('/')[-1])
    normalize = enhancement.normalize_volume
    tuning_inputs = []
    monkeypatch.setattr(smart_mode, 'get_dynamic_parameters', lambda audio, *args: tuning_inputs.append(audio.copy()) or {})
    def fail(*args):
        raise RuntimeError('simulated interruption')
    monkeypatch.setattr(enhancement, 'normalize_volume', fail)
    failed = client.post('/api/process', json={'file_id': 'fixture', 'options': {'auto_eq': True, 'normalize': True}})
    assert failed.status_code == 500
    monkeypatch.setattr(enhancement, 'normalize_volume', normalize)
    def forbidden(*args):
        raise AssertionError('Auto EQ should be restored from the verified checkpoint')
    monkeypatch.setattr(enhancement, 'apply_auto_eq', forbidden)
    resumed = process(client, auto_eq=True, normalize=True)
    actual, _ = sf.read(outputs / resumed['output_url'].split('/')[-1])
    assert resumed['checkpoint']['resumed_steps'] == ['auto_eq']
    np.testing.assert_array_equal(tuning_inputs[0], tuning_inputs[1])
    # This deterministic fixture has an observed zero repeatability baseline.
    np.testing.assert_array_equal(actual, reference)


@pytest.mark.parametrize('change', ['option', 'source', 'build', 'corrupt'])
def test_incompatible_or_corrupt_checkpoint_recomputes(api, monkeypatch, change):
    client, uploads, outputs = api
    normalize = enhancement.normalize_volume
    eq = enhancement.apply_auto_eq
    def fail(*args):
        raise RuntimeError('simulated interruption')
    monkeypatch.setattr(enhancement, 'normalize_volume', fail)
    client.post('/api/process', json={'file_id': 'fixture', 'options': {'auto_eq': True, 'normalize': True}})
    monkeypatch.setattr(enhancement, 'normalize_volume', normalize)
    opts = {'auto_eq': True, 'normalize': True}
    if change == 'option':
        opts['target_loudness_lufs'] = -23
    if change == 'source':
        sf.write(uploads / 'fixture.wav', np.ones(96000)*0.01, 48000, subtype='FLOAT')
    if change == 'build':
        monkeypatch.setattr(main, 'APP_BUILD', 'changed-build')
    if change == 'corrupt':
        meta = json.loads((outputs / 'fixture_checkpoints/meta.json').read_text())
        (outputs / 'fixture_checkpoints' / meta['audio_file']).write_bytes(b'broken')
    calls = []
    monkeypatch.setattr(enhancement, 'apply_auto_eq', lambda *args: calls.append(True) or eq(*args))
    result = process(client, **opts)
    assert calls == [True]
    assert result['checkpoint']['resumed_steps'] == []


def test_repeatability_baseline_three_runs(api):
    client, _, outputs = api
    runs = [process(client, normalize=True) for _ in range(3)]
    samples = [sf.read(outputs / run['output_url'].split('/')[-1])[0] for run in runs]
    assert len({run['revision'] for run in runs}) == 3
    assert max(float(np.max(np.abs(samples[0]-item))) for item in samples[1:]) == 0


def test_speech_edit_compliance_and_capsule_match_selected_result(api):
    client, _, _ = api
    process(client, normalize=True)
    edit = artifact_store.publish_audio('fixture', np.zeros(48000, dtype=np.float32), 48000, 'wav', 'speech_edit')
    review = client.post('/api/reviews/fixture/blind-ab', json={
        'selected_version': 'processed', 'blind_slot': 'B', 'output_version': 'speech_edit', 'revision': edit['revision']})
    assert review.status_code == 200
    assert review.json()['output_sha256'] == edit['exports']['wav']['sha256']
    capsule = client.post('/api/projects/fixture/export', json={
        'output_version': 'speech_edit', 'revision': edit['revision'], 'format': 'flac'})
    assert capsule.status_code == 200, capsule.text
    with zipfile.ZipFile(io.BytesIO(capsule.content)) as archive:
        names = archive.namelist()
        audio = next(name for name in names if name.endswith('.flac'))
        evidence = next(name for name in names if name.endswith('.compliance.json'))
        measured = json.loads(archive.read(evidence))
        assert hashlib.sha256(archive.read(audio)).hexdigest() == measured['artifact_sha256']
        assert measured['revision'] == edit['revision']
        assert measured['measurements']['integrated_loudness_lufs'] is None
        assert not any('/original/' in name for name in names)


def test_concurrent_job_is_rejected(api):
    client, _, _ = api
    main._PROCESSING_FILES.add('fixture')
    try:
        response = client.post('/api/process', json={'file_id': 'fixture', 'options': {'normalize': True}})
        assert response.status_code == 409
    finally:
        main._PROCESSING_FILES.clear()


def test_checkpoint_preserves_float_precision_and_rejects_legacy(tmp_path):
    audio = np.array([0.123456789123, -0.765432109876], dtype=np.float64)
    checkpoints.save_checkpoint(tmp_path, 'identity', audio, 48000, ['auto_eq'])
    restored = checkpoints.load_checkpoint(tmp_path, 'identity', ['auto_eq', 'normalize'])
    np.testing.assert_array_equal(restored[0], audio)
    assert restored[0].dtype == audio.dtype
    (tmp_path / 'meta.json').write_text(json.dumps({'completed_steps': ['auto_eq'], 'last_step': 'auto_eq'}))
    assert checkpoints.load_checkpoint(tmp_path, 'identity', ['auto_eq']) is None


def test_capsule_keeps_the_rendered_edl_and_transcript_after_later_edits(api):
    client, uploads, outputs = api
    source = uploads / 'fixture.wav'
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    audio, sr = sf.read(source)
    edl = speech_editor.build_speech_edl(file_id='fixture', audio=audio, sr=sr,
        transcription={'text': 'Original text', 'language': 'en', 'segments': []})
    edl = speech_editor.add_manual_speech_edit(edl, {'start': .2, 'end': .4,
        'action': 'mute', 'decision': 'apply', 'text': 'manual'}, expected_revision=edl['revision'])
    rendered = client.post('/api/speech-editor/fixture/render', json={'revision': edl['revision'], 'output_format': 'wav'})
    assert rendered.status_code == 200, rendered.text
    result = rendered.json()
    candidate = next(item for item in edl['candidates'] if item['detector'] == 'manual-transcript-selection')
    changed = client.patch('/api/speech-editor/fixture', json={'revision': edl['revision'],
        'decisions': [{'candidate_id': candidate['id'], 'decision': 'keep'}]})
    assert changed.status_code == 200
    (outputs / 'fixture_transcript.json').write_text('{"text":"A later transcription"}')
    capsule = client.post('/api/projects/fixture/export', json={'output_version': 'speech_edit',
        'revision': result['revision'], 'format': 'flac'})
    assert capsule.status_code == 200, capsule.text
    with zipfile.ZipFile(io.BytesIO(capsule.content)) as archive:
        manifest = json.loads(archive.read('manifest.json'))
        records = {}
        for item in manifest['artifacts']:
            if not item['included_in_capsule']:
                continue
            data = archive.read('artifacts/' + item['role'] + '/' + item['name'])
            assert hashlib.sha256(data).hexdigest() == item['sha256']
            if item['name'].endswith('.json'):
                records[item['role']] = json.loads(data)
    assert records['speech-edl'] == edl
    assert records['speech-edl']['revision'] != changed.json()['revision']
    assert records['processing-report']['speech_edits']['edl_snapshot'] == edl
    assert records['transcript']['text'] == 'Original text'
    assert records['transcript']['artifact_revision'] == result['revision']
    assert manifest['execution_boundary'] == 'local'
    assert manifest['artifact_revision'] == result['revision']
    assert manifest['evidence_warnings'] == []
    assert hashlib.sha256(source.read_bytes()).hexdigest() == source_hash


@pytest.mark.parametrize('report_contents', [None, '{', '[]', '{"privacy":{"processing_location":"local"}}'])
def test_missing_invalid_or_unbound_report_never_claims_local_execution(api, report_contents):
    client, _, outputs = api
    artifact = artifact_store.publish_audio('fixture', np.zeros(48000), 48000, 'wav', 'speech_edit')
    master = outputs / artifact['exports']['wav']['name']
    if report_contents is not None:
        master.with_suffix('.report.json').write_text(report_contents)
    speech_editor.speech_edl_path('fixture').write_text('{"revision":42}')
    (outputs / 'fixture_transcript.json').write_text('{"text":"current draft"}')
    response = client.post('/api/projects/fixture/export', json={'output_version': 'speech_edit'})
    assert response.status_code == 200
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        manifest = json.loads(archive.read('manifest.json'))
    assert manifest['execution_boundary'] == 'unknown'
    assert manifest['evidence_warnings']
    assert not {'speech-edl', 'transcript'} & {item['role'] for item in manifest['artifacts']}


def test_capsule_compliance_bytes_match_saved_report_with_non_ascii_text(api, monkeypatch):
    client, _, outputs = api
    artifact_store.publish_audio('fixture', np.zeros(48000), 48000, 'wav')
    analyze = delivery_compliance.analyze_delivery
    def localized(*args, **kwargs):
        return {**analyze(*args, **kwargs), 'interpretation': 'Verifica della qualità'}
    monkeypatch.setattr(delivery_compliance, 'analyze_delivery', localized)
    response = client.post('/api/projects/fixture/export', json={})
    assert response.status_code == 200, response.text
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        manifest = json.loads(archive.read('manifest.json'))
        entry = next(item for item in manifest['artifacts'] if item['role'] == 'delivery-compliance')
        archived = archive.read('artifacts/delivery-compliance/' + entry['name'])
    assert archived == (outputs / entry['name']).read_bytes()
    assert hashlib.sha256(archived).hexdigest() == entry['sha256']
