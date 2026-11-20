"""Same-origin Studio requests and bounded background work."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import logging
import mimetypes
from pathlib import Path
import threading
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import Field

from app.config import UPLOAD_DIR
from app.services import project_studio as studio
from app.services.artifact_store import atomic_json

LOG = logging.getLogger(__name__)
router = APIRouter(prefix="/api/studio")
executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="studio")
jobs: dict[str, dict] = {}
jobs_lock = threading.Lock()


def require_local(request: Request):
    from app.main import _require_local_credentials_request
    _require_local_credentials_request(request, "Studio projects")


def operation(call, *args):
    try:
        return call(*args)
    except studio.StaleStudioProject as error:
        raise HTTPException(409, str(error)) from error
    except FileNotFoundError as error:
        raise HTTPException(404, str(error)) from error
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    except OSError as error:
        LOG.exception("Studio storage operation failed")
        raise HTTPException(503, "Studio storage is unavailable. Check the available disk space.") from error


class ProjectCreate(studio.StudioModel):
    name: str = Field(min_length=1, max_length=80)


class ProjectSave(studio.StudioModel):
    revision: int = Field(ge=1)
    label: str = Field(min_length=1, max_length=100)
    document: studio.StudioDocument


class RestoreRequest(studio.StudioModel):
    revision: int = Field(ge=1)
    target: int = Field(ge=1)


class WorkspaceSource(studio.StudioModel):
    file_id: studio.IDENTITY
    name: str = Field(min_length=1, max_length=160)


class StudioJob(studio.StudioModel):
    revision: int = Field(ge=1)
    kind: Literal["preview", "render", "consolidate", "transcribe", "silences", "subtitles", "isolate"]
    format: Literal["wav", "flac"] = "wav"
    asset_id: studio.IDENTITY | None = None


@router.get("/projects")
def projects(request: Request):
    require_local(request)
    return {"projects": operation(studio.list_projects), "isolation_available": studio.isolation_repository() is not None}


@router.post("/projects")
def create(request: Request, body: ProjectCreate):
    require_local(request)
    return operation(studio.create_project, body.name)


@router.post("/projects/from-package")
def reopen(request: Request, file: UploadFile = File(...)):
    require_local(request)
    return operation(studio.reopen_portable, file.file)


@router.get("/projects/{project_id}")
def load(request: Request, project_id: studio.IDENTITY):
    require_local(request)
    return operation(studio.get_project, project_id)


@router.get("/projects/{project_id}/availability")
def availability(request: Request, project_id: studio.IDENTITY):
    require_local(request)
    project = operation(studio.get_project, project_id)
    return {item["id"]: item["available"] for item in project["assets"]}


@router.put("/projects/{project_id}")
def save(request: Request, project_id: studio.IDENTITY, body: ProjectSave):
    require_local(request)
    return operation(studio.save_project, project_id, body.revision, body.document, body.label)


@router.post("/projects/{project_id}/restore")
def restore(request: Request, project_id: studio.IDENTITY, body: RestoreRequest):
    require_local(request)
    return operation(studio.restore_project, project_id, body.revision, body.target)


@router.post("/projects/{project_id}/assets")
def upload(request: Request, project_id: studio.IDENTITY, file: UploadFile = File(...)):
    require_local(request)
    return operation(studio.import_asset, project_id, file.filename, file.file)


@router.post("/projects/{project_id}/assets/from-workspace")
def from_workspace(request: Request, project_id: studio.IDENTITY, body: WorkspaceSource):
    require_local(request)
    suffix = Path(body.name).suffix.lower()
    if suffix not in studio.MEDIA_EXTENSIONS:
        raise HTTPException(422, "Open a supported file in Home first.")
    source = UPLOAD_DIR / (body.file_id + suffix)
    if not source.is_file():
        raise HTTPException(404, "The original selected in Home is unavailable.")
    with source.open("rb") as stream:
        return operation(studio.import_asset, project_id, body.name, stream)


@router.post("/projects/{project_id}/assets/{asset_id}/relink")
def relink(request: Request, project_id: studio.IDENTITY, asset_id: studio.IDENTITY, file: UploadFile = File(...)):
    require_local(request)
    return operation(studio.import_asset, project_id, file.filename, file.file, asset_id)


@router.get("/projects/{project_id}/assets/{asset_id}/media")
def media(request: Request, project_id: studio.IDENTITY, asset_id: studio.IDENTITY, original: bool = False):
    require_local(request)
    item = operation(studio.read_asset, project_id, asset_id)
    first, canonical = operation(studio.available_paths, project_id, item)
    path = first if original else canonical
    mimetype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    if original and not item["video"]:
        return FileResponse(path, media_type=mimetype, filename=item["name"])
    return FileResponse(path, media_type=mimetype, headers={"X-Content-Type-Options": "nosniff"})


@router.get("/projects/{project_id}/assets/{asset_id}/transcript")
def transcript(request: Request, project_id: studio.IDENTITY, asset_id: studio.IDENTITY):
    require_local(request)
    return operation(studio.read_transcript, project_id, asset_id)


def job_info(project_id: str, identity: str) -> dict:
    with jobs_lock:
        job = jobs.get(identity)
        if job is None or job["project_id"] != project_id:
            raise HTTPException(404, "Studio job not found.")
        return dict(job)


def execute_job(identity: str, project: dict, body: StudioJob):
    project_id = project["id"]
    root = studio.project_path(project_id) / "output"

    def update(progress):
        with jobs_lock:
            # Limit updates to meaningful progress increments.
            jobs[identity]["progress"] = round(min(progress, 0.98), 2)

    try:
        if body.kind in {"preview", "render", "consolidate"}:
            extension = {"preview": "wav", "consolidate": "zip"}.get(body.kind, body.format)
            destination = root / f"{identity}.{extension}"
            if body.kind == "consolidate":
                outcome = studio.consolidate(project, destination, update)
            else:
                outcome = studio.render_audio(project, destination, extension, update)
            url = f"/api/studio/projects/{project_id}/jobs/{identity}/file"
            outcome.update(url=url, extension=extension)
            if body.kind == "render":
                asset_hashes = {item["id"]: item["sha256"] for item in project["assets"]}
                document = {field: project[field] for field in studio.StudioDocument.model_fields}
                atomic_json(root / f"{identity}.json", {
                    "schema_version": 1, "project_id": project_id, "revision": project["revision"],
                    "output_sha256": outcome["sha256"], "document": document,
                    "source_sha256": {key: asset_hashes[key] for key in
                                      dict.fromkeys(clip["asset_id"] for clip in project["clips"])},
                })
                outcome["report_url"] = f"{url}?report=true"
        elif body.kind == "silences":
            outcome = studio.detect_silences(project_id, body.asset_id, update)
        elif body.kind == "isolate":
            outcome = studio.isolate_voice(project_id, body.asset_id, update)
        elif body.kind == "subtitles":
            outcome = studio.studio_subtitles(project, body.asset_id, update)
        else:
            outcome = studio.studio_transcript(project_id, body.asset_id, update)
    except (ValueError, FileNotFoundError) as error:
        with jobs_lock:
            jobs[identity].update(status="error", error=str(error))
    except Exception:
        LOG.exception("Studio job %s failed", identity)
        with jobs_lock:
            jobs[identity].update(status="error", error="Studio could not finish this job. Check the local app log.")
    else:
        with jobs_lock:
            jobs[identity].update(status="complete", progress=1, result=outcome)


@router.post("/projects/{project_id}/jobs", status_code=202)
def start_job(request: Request, project_id: studio.IDENTITY, body: StudioJob):
    require_local(request)
    project = operation(studio.get_project, project_id, body.revision)
    if body.kind in {"transcribe", "silences", "subtitles", "isolate"}:
        if body.asset_id is None:
            raise HTTPException(422, "Select a clip first.")
        operation(studio.read_asset, project_id, body.asset_id)
    identity = uuid4().hex
    with jobs_lock:
        if sum(job["status"] == "running" for job in jobs.values()) >= 2:
            raise HTTPException(429, "Studio is busy. Try again after a job completes.")
        for stale in list(jobs)[:-64]:
            if jobs[stale]["status"] != "running":
                del jobs[stale]
        jobs[identity] = {"id": identity, "project_id": project_id, "kind": body.kind,
                          "status": "running", "progress": 0, "revision": body.revision}
    executor.submit(execute_job, identity, project, body)
    return job_info(project_id, identity)


@router.get("/projects/{project_id}/jobs/{identity}")
def status(request: Request, project_id: studio.IDENTITY, identity: studio.IDENTITY):
    require_local(request)
    return job_info(project_id, identity)


@router.get("/projects/{project_id}/jobs/{identity}/file")
def file(request: Request, project_id: studio.IDENTITY, identity: studio.IDENTITY, report: bool = False):
    require_local(request)
    info = job_info(project_id, identity)
    result = info.get("result", {})
    extension = result.get("extension")
    if info["status"] != "complete" or not extension or (report and not result.get("report_url")):
        raise HTTPException(404, "Studio output is unavailable.")
    if report:
        extension = "json"
    path = studio.project_path(project_id) / "output" / f"{identity}.{extension}"
    if not path.is_file():
        raise HTTPException(404, "The exported file was removed.")
    filename = None if info["kind"] == "preview" else f"AudioEnhancerMAX-Project-r{info['revision']}.{extension}"
    mimetype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return FileResponse(path, media_type=mimetype, filename=filename, headers={"X-Content-Type-Options": "nosniff"})
