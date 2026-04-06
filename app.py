# app.py
#
# FastAPI control panel for BondScrape. Provides a web dashboard for managing the
# scraping and parsing workflow, including:
#   - Home dashboard showing production and sandbox issue counts
#   - Sandbox document selector (pick documents from production to test with)
#   - CLI command generator for parse and aggregate scripts
#
# Run with: uvicorn app:app --reload
# Templates are in templates/ (Jinja2).

import json
import subprocess
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
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