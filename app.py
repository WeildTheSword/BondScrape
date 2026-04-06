# app.py
#
# FastAPI control panel for BondScrape. Provides a web dashboard for managing the
# scraping and parsing workflow, including:
#   - Home dashboard showing production and sandbox issue counts
#   - Sandbox document selector (pick documents from production to test with)
#   - CLI command generator for parse and aggregate scripts
#   - Scraper launch API with SSE streaming for live progress
#
# Run with: uvicorn app:app --reload
# Templates are in templates/ (Jinja2).
# NOS static site served at /NOS/

import asyncio
import json
import subprocess
import sys
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# =========================
# PATH SETUP
# =========================
BASE_DIR = Path(__file__).resolve().parent

DATA_DIR = BASE_DIR / "prospectus_json"
PROCESSED_DIR = DATA_DIR / "scraper_output"

SANDBOX_DIR = DATA_DIR / "sandbox"
SANDBOX_PROCESSED_DIR = SANDBOX_DIR / "processed"
SANDBOX_PARSED_DIR = SANDBOX_DIR / "parsed"

TEMPLATE_DIR = BASE_DIR / "templates"

TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)
SANDBOX_PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
SANDBOX_PARSED_DIR.mkdir(parents=True, exist_ok=True)

# =========================
# APP INIT
# =========================
app = FastAPI(title="BondScrape Control Panel")
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))


# =========================
# UTILS
# =========================
def load_json(path: Path):
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def run_command(command: list[str], env: Optional[dict] = None) -> str:
    result = subprocess.run(
        command,
        cwd=str(BASE_DIR),
        capture_output=True,
        text=True,
        env=env,
    )

    output = [f"$ {' '.join(command)}"]

    if result.stdout:
        output.append(result.stdout)

    if result.stderr:
        output.append(result.stderr)

    output.append(f"\nExit code: {result.returncode}")
    return "\n".join(output)


def get_prod_issues_path() -> Path:
    return PROCESSED_DIR / "issues_master.json"


def get_sandbox_issues_path() -> Path:
    return SANDBOX_PROCESSED_DIR / "issues_master.json"


# =========================
# HOME DASHBOARD
# =========================
@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    prod = load_json(get_prod_issues_path()) or {"issue_count": 0}
    sandbox = load_json(get_sandbox_issues_path()) or {"issue_count": 0}

    return templates.TemplateResponse(
        name="dashboard.html",
        context={
            "request": request,
            "prod_issue_count": prod.get("issue_count", 0),
            "sandbox_issue_count": sandbox.get("issue_count", 0),
            "log_output": "",
        },
    )


# =========================
# SANDBOX SELECTOR PAGE
# =========================
@app.get("/sandbox/select", response_class=HTMLResponse)
def sandbox_select(request: Request):
    prod = load_json(get_prod_issues_path()) or {"issues": []}

    return templates.TemplateResponse(
        name="sandbox_selector.html",
        context={
            "request": request,
            "issues_json": json.dumps(prod.get("issues", [])),
        },
    )


# =========================
# BUILD SANDBOX
# =========================
@app.post("/sandbox/build-from-selection")
async def build_from_selection(request: Request):
    data = await request.json()

    selected_doc_ids = set(data.get("document_ids", []))
    source = load_json(get_prod_issues_path()) or {"issues": []}

    selected_issues = []

    for issue in source.get("issues", []):
        docs = [
            d for d in issue.get("documents", [])
            if d.get("document_id") in selected_doc_ids
        ]

        if not docs:
            continue

        new_issue = dict(issue)
        new_issue["documents"] = docs
        new_issue["document_count"] = len(docs)

        selected_issues.append(new_issue)

    sandbox = {
        "issue_count": len(selected_issues),
        "issues": selected_issues,
    }

    save_json(get_sandbox_issues_path(), sandbox)

    return JSONResponse({
        "status": "ok",
        "issue_count": len(selected_issues),
    })


# =========================
# CLI GENERATOR
# =========================
@app.post("/sandbox/generate-cli")
async def generate_cli(request: Request):
    data = await request.json()

    parse_cmd = ["python3", "parse_remote_pdfs.py"]

    if data.get("use_llm"):
        parse_cmd.append("--use-llm")
    if data.get("full_mode"):
        parse_cmd.append("--full")
    if data.get("retry_failed"):
        parse_cmd.append("--retry-failed")

    parse_cmd.extend([
        "--issues-path", str(get_sandbox_issues_path()),
        "--parsed-root", str(SANDBOX_PARSED_DIR),
    ])

    agg_cmd = [
        "python3",
        "POS/aggregate_issue_features.py",
        "--issues-path", str(get_sandbox_issues_path()),
        "--output", str(SANDBOX_PROCESSED_DIR / "issues_enriched.json"),
    ]

    return JSONResponse({
        "parse": " ".join(parse_cmd),
        "aggregate": " ".join(agg_cmd),
    })


# =========================
# SCRAPER LAUNCH API
# =========================
scraper_process: Optional[asyncio.subprocess.Process] = None
scraper_running = False


@app.get("/api/scraper/status")
def scraper_status():
    """Check if scraper is currently running and if data exists."""
    raw_path = PROCESSED_DIR / "scrape_output_raw.json"
    issues_path = PROCESSED_DIR / "issues_master.json"

    raw_exists = raw_path.exists()
    issues_exists = issues_path.exists()

    raw_count = 0
    issue_count = 0
    if raw_exists:
        try:
            raw_count = len(json.loads(raw_path.read_text()))
        except Exception:
            pass
    if issues_exists:
        try:
            data = json.loads(issues_path.read_text())
            issue_count = data.get("issue_count", len(data.get("issues", [])))
        except Exception:
            pass

    return JSONResponse({
        "running": scraper_running,
        "raw_exists": raw_exists,
        "raw_count": raw_count,
        "issues_exists": issues_exists,
        "issue_count": issue_count,
    })


@app.get("/api/scraper/launch")
async def launch_scraper():
    """Launch the scraper as a subprocess, streaming stdout/stderr as SSE."""
    global scraper_process, scraper_running

    if scraper_running:
        return JSONResponse({"error": "Scraper is already running"}, status_code=409)

    async def stream():
        global scraper_process, scraper_running
        scraper_running = True

        try:
            yield f"data: {json.dumps({'type': 'status', 'msg': 'Launching scraper...'})}\n\n"

            scraper_process = await asyncio.create_subprocess_exec(
                sys.executable, "iprospectus_scraper/scraper_linkpull.py",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=str(BASE_DIR),
            )

            async for line in scraper_process.stdout:
                text = line.decode("utf-8", errors="replace").rstrip()
                if text:
                    yield f"data: {json.dumps({'type': 'log', 'msg': text})}\n\n"

            exit_code = await scraper_process.wait()

            if exit_code == 0:
                yield f"data: {json.dumps({'type': 'status', 'msg': 'Scraper finished successfully.'})}\n\n"
                yield f"data: {json.dumps({'type': 'done', 'success': True, 'exit_code': exit_code})}\n\n"
            else:
                yield f"data: {json.dumps({'type': 'status', 'msg': f'Scraper exited with code {exit_code}'})}\n\n"
                yield f"data: {json.dumps({'type': 'done', 'success': False, 'exit_code': exit_code})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'msg': str(e)})}\n\n"
            yield f"data: {json.dumps({'type': 'done', 'success': False, 'exit_code': -1})}\n\n"
        finally:
            scraper_running = False
            scraper_process = None

    return StreamingResponse(stream(), media_type="text/event-stream")


@app.get("/api/scraper/build-index")
async def build_index():
    """Run build_issue_index.py to group raw rows into issues, streaming progress."""
    async def stream():
        try:
            yield f"data: {json.dumps({'type': 'status', 'msg': 'Building issue index...'})}\n\n"

            proc = await asyncio.create_subprocess_exec(
                sys.executable, "iprospectus_scraper/build_issue_index.py",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=str(BASE_DIR),
            )

            async for line in proc.stdout:
                text = line.decode("utf-8", errors="replace").rstrip()
                if text:
                    yield f"data: {json.dumps({'type': 'log', 'msg': text})}\n\n"

            exit_code = await proc.wait()

            if exit_code == 0:
                yield f"data: {json.dumps({'type': 'status', 'msg': 'Index built successfully.'})}\n\n"
                yield f"data: {json.dumps({'type': 'done', 'success': True, 'exit_code': exit_code})}\n\n"
            else:
                yield f"data: {json.dumps({'type': 'done', 'success': False, 'exit_code': exit_code})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'msg': str(e)})}\n\n"
            yield f"data: {json.dumps({'type': 'done', 'success': False, 'exit_code': -1})}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")


@app.post("/api/scraper/stop")
async def stop_scraper():
    """Kill a running scraper process."""
    global scraper_process, scraper_running
    if scraper_process and scraper_running:
        try:
            scraper_process.terminate()
            await asyncio.sleep(1)
            if scraper_process.returncode is None:
                scraper_process.kill()
        except Exception:
            pass
        scraper_running = False
        return JSONResponse({"status": "stopped"})
    return JSONResponse({"status": "not_running"})


# =========================
# STATIC FILE SERVING
# =========================
# Mount NOS site and data directories so everything works from one server
app.mount("/prospectus_json", StaticFiles(directory=str(DATA_DIR)), name="data")
app.mount("/NOS", StaticFiles(directory=str(BASE_DIR / "NOS"), html=True), name="nos")