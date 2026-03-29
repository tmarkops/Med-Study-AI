"""
FastAPI server for med-study-ai.

Routes:
  GET  /                          → student notes page
  GET  /admin                     → admin page
  GET  /api/notes                 → list available generated notes (nested by semester/block/ape)
  GET  /download/{path}           → download a .docx file
  POST /api/ingest                → upload + ingest a PDF (admin)
  POST /api/generate              → upload objectives file + generate notes (admin)
  GET  /api/jobs/{job_id}         → poll generation job status

Output folder structure:
  outputs/{semester}/{block}/APE_{number}_{name}/{filename}.docx
"""

import os
import sys
import uuid
import threading
import re
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends, status
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from dotenv import load_dotenv
import secrets

load_dotenv()

# Add app/ to path so we can import from it
sys.path.insert(0, str(Path(__file__).parent / "app"))

from ingest import ingest
from objectives import parse_objectives
from notes import generate_notes_from_objectives
from export import save_as_docx

app = FastAPI()

OUTPUTS_DIR = Path(__file__).parent / "outputs"
OUTPUTS_DIR.mkdir(exist_ok=True)

STATIC_DIR = Path(__file__).parent / "static"

# In-memory job store
jobs: dict[str, dict] = {}

# --- Auth ---

security = HTTPBasic()
ADMIN_USER = os.environ.get("ADMIN_USER", "admin")
ADMIN_PASS = os.environ.get("ADMIN_PASS", "changeme")


def require_admin(credentials: HTTPBasicCredentials = Depends(security)):
    ok = secrets.compare_digest(credentials.username, ADMIN_USER) and \
         secrets.compare_digest(credentials.password, ADMIN_PASS)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


def _safe_slug(text: str) -> str:
    """Convert user input to a safe folder/filename segment."""
    return re.sub(r"[^\w\-]", "_", text.strip()).strip("_")


# --- Static pages ---

@app.get("/", response_class=HTMLResponse)
def student_page():
    return (STATIC_DIR / "index.html").read_text(encoding="utf-8")


@app.get("/admin", response_class=HTMLResponse)
def admin_page():
    return (STATIC_DIR / "admin.html").read_text(encoding="utf-8")


# --- Notes listing ---

@app.get("/api/notes")
def list_notes():
    """
    Return all .docx files under outputs/, each annotated with semester/block/ape
    parsed from the folder structure: {semester}/{block}/APE_{number}_{name}/file.docx
    """
    results = []
    for f in sorted(OUTPUTS_DIR.rglob("*.docx"), key=lambda x: x.stat().st_mtime, reverse=True):
        rel = f.relative_to(OUTPUTS_DIR)
        parts = rel.parts  # e.g. ("S1", "GI", "APE_1_Digestion", "notes.docx")

        semester = parts[0] if len(parts) > 1 else None
        block = parts[1] if len(parts) > 2 else None
        ape_folder = parts[2] if len(parts) > 3 else None

        ape_number = None
        ape_name = None
        if ape_folder:
            m = re.match(r"APE_(\d+)_(.*)", ape_folder)
            if m:
                ape_number = int(m.group(1))
                ape_name = m.group(2).replace("_", " ")

        results.append({
            "path": str(rel).replace("\\", "/"),   # URL-safe relative path
            "filename": f.name,
            "semester": semester,
            "block": block,
            "ape_number": ape_number,
            "ape_name": ape_name,
            "size_kb": round(f.stat().st_size / 1024, 1),
            "modified": f.stat().st_mtime,
        })
    return results


# --- Download ---

@app.get("/download/{file_path:path}")
def download_notes(file_path: str):
    # Reject path traversal
    if ".." in file_path:
        raise HTTPException(status_code=400, detail="Invalid path")
    path = OUTPUTS_DIR / file_path
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(
        path=str(path),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=path.name,
    )


# --- Ingest PDF (admin) ---

@app.post("/api/ingest")
def ingest_pdf(
    file: UploadFile = File(...),
    block: str = Form("general"),
    source_type: str = Form("textbook"),
    language: str = Form("FR"),
    title: Optional[str] = Form(None),
    _user: str = Depends(require_admin),
):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    tmp_path = Path(f"/tmp/{uuid.uuid4()}_{file.filename}")
    try:
        tmp_path.write_bytes(file.file.read())
        metadata = {
            "block": block,
            "source_type": source_type,
            "language": language,
            "title": title or Path(file.filename).stem,
        }
        ingest(str(tmp_path), metadata=metadata)
    finally:
        tmp_path.unlink(missing_ok=True)

    return {"status": "ok", "message": f"'{file.filename}' ingested successfully."}


# --- Generate notes (admin) ---

def _run_generation(job_id: str, objectives_path: Path, output_path: Path, params: dict):
    try:
        jobs[job_id]["status"] = "running"
        objectives = parse_objectives(objectives_path)
        notes_md = generate_notes_from_objectives(
            objectives=objectives,
            block=params.get("block") or None,
            source_type=params.get("source_type") or None,
            language=params["language"],
            style=params["style"],
            rerank=True,
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        save_as_docx(notes_md, output_path)
        jobs[job_id]["status"] = "done"
        jobs[job_id]["path"] = str(output_path.relative_to(OUTPUTS_DIR)).replace("\\", "/")
        jobs[job_id]["filename"] = output_path.name
    except Exception as e:
        jobs[job_id]["status"] = "error"
        jobs[job_id]["error"] = str(e)
    finally:
        objectives_path.unlink(missing_ok=True)


@app.post("/api/generate")
def generate(
    file: UploadFile = File(...),
    output_name: str = Form(...),
    semester: str = Form(...),
    block: str = Form(...),
    ape_number: int = Form(...),
    ape_name: str = Form(...),
    source_type: Optional[str] = Form(""),
    language: str = Form("FR"),
    style: str = Form("detailed"),
    _user: str = Depends(require_admin),
):
    suffix = Path(file.filename).suffix.lower()
    if suffix not in (".pdf", ".docx", ".txt"):
        raise HTTPException(status_code=400, detail="Objectives file must be .pdf, .docx, or .txt")

    safe_semester = _safe_slug(semester)
    safe_block = _safe_slug(block)
    safe_ape_name = _safe_slug(ape_name)
    ape_folder = f"APE_{ape_number}_{safe_ape_name}"

    safe_filename = _safe_slug(output_name)
    if not safe_filename:
        raise HTTPException(status_code=400, detail="Invalid output name")
    if not safe_filename.endswith(".docx"):
        safe_filename += ".docx"

    output_path = OUTPUTS_DIR / safe_semester / safe_block / ape_folder / safe_filename

    tmp_objectives = Path(f"/tmp/{uuid.uuid4()}{suffix}")
    tmp_objectives.write_bytes(file.file.read())

    job_id = str(uuid.uuid4())
    jobs[job_id] = {"status": "pending", "path": None, "filename": None, "error": None}

    params = {"block": block, "source_type": source_type, "language": language, "style": style}
    t = threading.Thread(target=_run_generation, args=(job_id, tmp_objectives, output_path, params), daemon=True)
    t.start()

    return {"job_id": job_id}


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


# --- Mount static files ---
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
