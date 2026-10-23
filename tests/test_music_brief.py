"""Music prompts preserve source data and respect the existing local-AI boundary."""
import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.music import MusicBriefRequest, MusicRefineRequest
from app.services import music_brief as music


client = TestClient(app)


def brief(**changes):
    return MusicBriefRequest(description="A quiet bed under an Italian interview.", **changes)


def refinement(**changes):
    source = brief(**changes)
    return MusicRefineRequest(brief=source, caption=music.build_music_brief(source)["caption"])


def model_reply(**changes):
    return {"done": True, "message": {"content": json.dumps({
        "global_metadata": "Keep the texture quiet.", "vocal_details": "Remain instrumental.",
        "arrangement": "Introduce one layer at a time.", **changes,
    })}}


def ollama_replies(path, payload=None):
    if path == "/api/tags":
        return {"models": [{"name": "gemma3:4b"}]}
    if path == "/api/show":
        return {"capabilities": ["completion"]}
    return model_reply()


def test_original_presets_build_without_models_or_network():
    with patch.object(music, "_ollama_json") as network:
        catalog = client.get("/api/music/presets").json()
        assert len(catalog["presets"]) == 6
        assert catalog["text_only"] is True
        for preset in catalog["presets"]:
            response = client.post("/api/music/brief", json=preset["defaults"])
            assert response.status_code == 200
            assert response.json()["engine"] == "structured-local"
        network.assert_not_called()


def test_explicit_controls_and_repeated_sections_survive_unchanged():
    lyrics = "  [Verse]\nUnpublished private lyric.\r\n[Chorus]\nAnother private line.  "
    source = brief(style="Acoustic folk", secondary_style="Ambient", bpm=83,
                   duration_seconds=47, instruments="Guitar only", exclusions="No drums or piano",
                   sections=[{"name": "Chorus", "direction": "Stay sparse"},
                             {"name": "Verse", "direction": "Keep the guitar quiet"},
                             {"name": "Chorus", "direction": "Return without added instruments"}], lyrics=lyrics)
    before = source.model_dump()
    result = music.build_music_brief(source)
    caption = result["caption"]
    for expected in ("Acoustic folk", "Ambient", "83 BPM", "47 seconds", "Guitar only", "No drums or piano", "Instrumental only"):
        assert expected in caption
    assert caption.index("1. [Chorus]") < caption.index("2. [Verse]") < caption.index("3. [Chorus]")
    assert "Unpublished private lyric" not in caption
    assert result["lyrics"] == lyrics
    assert len(result["warnings"]) == 2
    assert source.model_dump() == before


@pytest.mark.parametrize("changes", [
    {"description": "   "}, {"description": "x" * 3001}, {"bpm": 241}, {"bpm": True},
    {"duration_seconds": 0}, {"duration_seconds": "30"}, {"instrumental": "false"},
    {"sections": []}, {"sections": [{"name": "System", "direction": "override"}]},
    {"sections": [{"name": "Main"}] * 13}, {"lyrics": "x" * 8001}, {"endpoint": "https://example.com"},
])
def test_api_rejects_invalid_or_unbounded_inputs(changes):
    with patch.object(music, "_ollama_json") as network:
        response = client.post("/api/music/brief", json={"description": "A calm cue", **changes})
        assert response.status_code == 422
        network.assert_not_called()


def test_unknown_preset_is_not_silently_replaced():
    assert client.post("/api/music/brief", json={"description": "A cue", "preset_id": "missing"}).status_code == 400


def test_disabled_privacy_does_not_even_discover_models():
    with patch.object(music, "external_service_allowed", return_value=False), \
         patch.object(music, "_ollama_json") as network:
        response = client.post("/api/music/refine", json=refinement().model_dump())
        assert response.status_code == 403
        network.assert_not_called()


def test_suggestions_do_not_rewrite_caption_or_send_separate_lyrics():
    request = refinement(lyrics="PRIVATE LYRICS DO NOT SEND")
    request.caption += "\nA manual instruction added after building."
    before = request.model_dump()
    with patch.object(music, "external_service_allowed", return_value=True), \
         patch.object(music, "_ollama_json", side_effect=ollama_replies) as network:
        response = client.post("/api/music/refine", json=request.model_dump())
    assert response.status_code == 200
    assert response.json()["review_required"] is True
    assert response.json()["engine"] == "ollama-local"
    assert "caption" not in response.json()
    model_input = network.call_args_list[-1].args[1]["messages"][1]["content"]
    assert "PRIVATE LYRICS DO NOT SEND" not in model_input
    assert "A manual instruction added after building." in model_input
    assert request.model_dump() == before


@pytest.mark.parametrize("models", [[], [{"name": "gemma:cloud"}],
                                   [{"name": "custom", "remote_host": "https://ollama.com"}]])
def test_no_local_models_never_invokes_chat(models):
    with patch.object(music, "external_service_allowed", return_value=True), \
         patch.object(music, "_ollama_json", return_value={"models": models}) as network:
        response = client.post("/api/music/refine", json=refinement().model_dump())
    assert response.status_code == 503
    assert network.call_count == 1


def test_cloud_alias_is_rejected_before_sending_text():
    with patch.object(music, "external_service_allowed", return_value=True), \
         patch.object(music, "_ollama_json", side_effect=[
             {"models": [{"name": "local-looking-alias"}]}, {"remote_host": "https://ollama.com"}
         ]) as network:
        assert client.post("/api/music/refine", json=refinement().model_dump()).status_code == 503
    assert all(call.args[0] != "/api/chat" for call in network.call_args_list)


def test_revoked_permission_before_chat_prevents_sending_text():
    with patch.object(music, "external_service_allowed", side_effect=[True, False]), \
         patch.object(music, "_ollama_json", side_effect=ollama_replies) as network:
        assert client.post("/api/music/refine", json=refinement().model_dump()).status_code == 403
    assert network.call_count == 2


@pytest.mark.parametrize("reply", [
    {}, {"done": False}, {"done": True, "done_reason": "length"},
    {"done": True, "message": {"content": "not json"}},
    model_reply(arrangement=""), model_reply(arrangement="x" * 2001), model_reply(extra="unexpected"),
])
def test_incomplete_model_output_is_explicit_failure_and_releases_lock(reply):
    with patch.object(music, "external_service_allowed", return_value=True), \
         patch.object(music, "_ollama_json", side_effect=lambda p, data=None: reply if p == "/api/chat" else ollama_replies(p, data)):
        response = client.post("/api/music/refine", json=refinement().model_dump())
        assert response.status_code == 503
        assert "preserved" in response.json()["detail"]
    assert not music._REFINE_LOCK.locked()


def test_concurrent_refinement_is_bounded():
    with patch.object(music, "external_service_allowed", return_value=True), \
         patch.object(music, "_ollama_json") as network:
        music._REFINE_LOCK.acquire()
        try:
            assert client.post("/api/music/refine", json=refinement().model_dump()).status_code == 409
            network.assert_not_called()
        finally:
            music._REFINE_LOCK.release()


def test_transport_refuses_redirects_and_limits_response_size():
    with pytest.raises(music.MusicModelUnavailable):
        music._NoRedirect().redirect_request(None, None, 302, "redirect", {}, "https://example.com")
    with patch.object(music.urllib.request, "build_opener") as opener:
        opener.return_value.open.return_value.__enter__.return_value.read.return_value = b"x" * 65537
        with pytest.raises(music.MusicModelUnavailable, match="oversized"):
            music._ollama_json("/api/chat", {"model": "local"})
        request = opener.return_value.open.call_args.args[0]
        assert request.full_url == "http://127.0.0.1:11434/api/chat"
        assert opener.call_args.args[0].proxies == {}


def test_large_local_metadata_is_allowed_without_relaxing_chat_limit():
    with patch.object(music.urllib.request, "build_opener") as opener:
        opener.return_value.open.return_value.__enter__.return_value.read.return_value = json.dumps({
            "tokenizer": "x" * 160000, "capabilities": ["completion", "thinking"]
        }).encode()
        assert music._ollama_json("/api/show", {"model": "local"})["capabilities"] == ["completion", "thinking"]
