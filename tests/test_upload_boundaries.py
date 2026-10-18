"""Bounded ingest and event-loop responsiveness, with synthetic local audio."""
import asyncio
import io
import threading

import httpx
import numpy as np
import pytest
import soundfile as sf
from fastapi import HTTPException, UploadFile
from fastapi.testclient import TestClient

from app import main
from app.utils import audio_io
from app.services import runtime_settings


@pytest.fixture
def uploads(tmp_path, monkeypatch):
    directory = tmp_path / 'uploads'
    directory.mkdir()
    for module in (main, audio_io):
        monkeypatch.setattr(module, 'UPLOAD_DIR', directory)
    monkeypatch.setattr(runtime_settings, 'RUNTIME_SETTINGS_FILE', tmp_path / 'privacy.json')
    return directory


def audio_bytes(fmt='WAV'):
    buffer = io.BytesIO()
    sf.write(buffer, np.zeros(8000, dtype=np.float32), 16000, format=fmt)
    return buffer.getvalue()


def test_oversized_ingest_stops_reading_and_removes_partial_files(uploads, monkeypatch):
    class BoundedReader(io.BytesIO):
        def read(self, size=-1):
            assert 0 < size <= 1024 * 1024, 'Ingest must not read the entire upload'
            return super().read(size)
    reader = BoundedReader(b'x' * (3 * 1024 * 1024))
    monkeypatch.setattr(main, 'MAX_FILE_SIZE_MB', 1)
    with pytest.raises(HTTPException) as error:
        main.upload_file(UploadFile(filename='large.wav', file=reader))
    assert error.value.status_code == 400
    assert reader.tell() == 2 * 1024 * 1024
    assert list(uploads.iterdir()) == []


def test_valid_upload_keeps_response_and_original_audio(uploads):
    content = audio_bytes()
    response = TestClient(main.app).post('/api/upload', files={'file': ('sample.wav', content, 'audio/wav')})
    assert response.status_code == 200, response.text
    result = response.json()
    assert result['size_bytes'] == len(content)
    assert result['duration_seconds'] == .5
    assert (uploads / (result['file_id'] + '.wav')).read_bytes() == content
    assert result['waveform_data']


def test_failure_after_conversion_removes_both_uploaded_and_converted_audio(uploads, monkeypatch):
    def fail(*args, **kwargs):
        assert len(list(uploads.iterdir())) == 2  # Input FLAC and generated WAV exist.
        raise RuntimeError('waveform interrupted')
    monkeypatch.setattr(main, 'generate_waveform_data', fail)
    response = TestClient(main.app).post('/api/upload', files={'file': ('sample.flac', audio_bytes('FLAC'))})
    assert response.status_code == 500
    assert list(uploads.iterdir()) == []


def test_slow_decode_does_not_block_privacy_api(uploads, monkeypatch):
    entered = threading.Event()
    release = threading.Event()
    original_load = main.load_audio
    def held_decode(*args, **kwargs):
        entered.set()
        assert release.wait(5), 'The control request must finish while decoding is still active'
        return original_load(*args, **kwargs)
    monkeypatch.setattr(main, 'load_audio', held_decode)

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url='http://test') as client:
            upload = asyncio.create_task(client.post('/api/upload', files={'file': ('sample.wav', audio_bytes())}))
            try:
                assert await asyncio.to_thread(entered.wait, 3)
                assert not upload.done()
                response = await asyncio.wait_for(client.get('/api/settings/privacy'), 1)
                assert response.status_code == 200
                assert not upload.done()
            finally:
                release.set()
                completed = await upload
            assert completed.status_code == 200
    asyncio.run(exercise())
