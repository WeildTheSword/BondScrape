# pip install playwright
# playwright install

import re
import json
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

from playwright.sync_api import sync_playwright

# =========================
# CONFIG
# =========================
START_URL = "https://www.i-dealprospectus.com/Public"
DOWNLOAD_ROOT = Path("downloads_all_issues")
HEADLESS = False
WAIT_FOR_MANUAL_LOGIN = True

# Set to True if you want to start from an already filtered page and just scrape
# whatever is visible through pagination.
USE_EXISTING_FILTERS = True


# =========================
# HELPERS
# =========================
def slugify(text: str) -> str:
    text = re.sub(r"[^\w\s\-&,()]+", "", text)
    text = re.sub(r"\s+", "_", text.strip())
    return text[:180] if text else "unknown_issue"


def safe_doc_type(doc_type: str) -> str:
    cleaned = re.sub(r"[^\w\s\-&]+", "", doc_type).strip()
    cleaned = re.sub(r"\s+", "_", cleaned)
    return cleaned if cleaned else "UnknownDocType"


def unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    parent = path.parent
    i = 2
    while True:
        candidate = parent / f"{stem}_{i}{suffix}"
        if not candidate.exists():
            return candidate
        i += 1


def normalize_url(base_url: str, maybe_relative: str | None) -> str | None:
    if not maybe_relative:
        return None
    return urljoin(base_url, maybe_relative)


def looks_like_pdf(url: str | None) -> bool:
    if not url:
        return False
    lower = url.lower()
    return ".pdf" in lower or "pdf" in lower


def get_table_rows(page):
    selectors = [
        "table tbody tr",
        "tbody tr",
        "[role='rowgroup'] [role='row']",
    ]
    for sel in selectors:
        loc = page.locator(sel)
        try:
            if loc.count() > 0:
                return loc
        except Exception:
            pass
    raise RuntimeError("Could not find table rows. Inspect the DOM and update selectors.")


def parse_row(row):
    """
    Expected visible columns from screenshot:
    0 Date
    1 Issue
    2 Manager/FA
    3 Par Amt ($)
    4 Doc Type
    5 Type
    6 Size (MB)
    """
    cell_selectors = ["td", "[role='cell']"]
    cells = None

    for sel in cell_selectors:
        loc = row.locator(sel)
        try:
            if loc.count() >= 6:
                cells = loc
                break
        except Exception:
            pass

    if cells is None:
        raise RuntimeError("Could not parse row cells.")

    date_text = cells.nth(0).inner_text().strip()
    issue_cell = cells.nth(1)
    manager_text = cells.nth(2).inner_text().strip()
    par_amt_text = cells.nth(3).inner_text().strip()
    doc_type_text = cells.nth(4).inner_text().strip()
    issue_type_text = cells.nth(5).inner_text().strip()
    size_text = cells.nth(6).inner_text().strip() if cells.count() > 6 else ""

    link = issue_cell.locator("a").first
    issue_text = link.inner_text().strip() if link.count() > 0 else issue_cell.inner_text().strip()
    href = link.get_attribute("href") if link.count() > 0 else None

    return {
        "date": date_text,
        "issue": issue_text,
        "manager_fa": manager_text,
        "par_amt": par_amt_text,
        "doc_type": doc_type_text,
        "type": issue_type_text,
        "size_mb": size_text,
        "href": href,
    }


def next_page(page) -> bool:
    selectors = [
        "button[aria-label='Next page']",
        "a[aria-label='Next page']",
        "button:has-text('Next')",
        "a:has-text('Next')",
    ]

    for sel in selectors:
        btn = page.locator(sel).first
        try:
            if btn.count() > 0 and btn.is_visible() and btn.is_enabled():
                btn.click()
                page.wait_for_load_state("networkidle")
                time.sleep(1)
                return True
        except Exception:
            pass

    return False


def collect_all_rows(page):
    """
    Walk every paginated table page and collect row metadata.
    Does not download yet.
    """
    all_rows = []
    seen_signatures = set()
    page_index = 1

    while True:
        rows = get_table_rows(page)
        row_count = rows.count()

        for i in range(row_count):
            row = rows.nth(i)
            try:
                parsed = parse_row(row)
            except Exception:
                continue

            signature = (
                parsed["date"],
                parsed["issue"],
                parsed["doc_type"],
                parsed["href"],
            )

            if signature in seen_signatures:
                continue

            seen_signatures.add(signature)
            parsed["page_seen"] = page_index
            all_rows.append(parsed)

        moved = next_page(page)
        if not moved:
            break

        page_index += 1

    return all_rows


def click_and_capture_pdf(page, row_href: str | None, save_path: Path) -> str:
    """
    Strategy:
    1. Direct GET if href is already a PDF-ish URL
    2. Open link in a new page and inspect iframe/embed/object
    3. Trigger browser download if applicable
    """
    base = page.url
    full_url = normalize_url(base, row_href)

    if looks_like_pdf(full_url):
        response = page.context.request.get(full_url)
        if response.ok:
            save_path.write_bytes(response.body())
            return full_url

    # Open a temporary page for doc landing pages / viewers
    temp = page.context.new_page()
    try:
        if full_url:
            temp.goto(full_url, wait_until="domcontentloaded", timeout=30000)
            temp.wait_for_load_state("networkidle", timeout=15000)
            candidate_url = temp.url

            if looks_like_pdf(candidate_url):
                response = page.context.request.get(candidate_url)
                if response.ok:
                    save_path.write_bytes(response.body())
                    return candidate_url

            # inspect iframe/embed/object for PDF src
            for selector, attr in [("iframe", "src"), ("embed", "src"), ("object", "data")]:
                elems = temp.locator(selector)
                count = elems.count()
                for i in range(count):
                    val = elems.nth(i).get_attribute(attr)
                    candidate = normalize_url(temp.url, val)
                    if looks_like_pdf(candidate):
                        response = page.context.request.get(candidate)
                        if response.ok:
                            save_path.write_bytes(response.body())
                            return candidate

            # last fallback: click first obvious PDF-ish link on landing page
            anchors = temp.locator("a")
            count = anchors.count()
            for i in range(count):
                href = anchors.nth(i).get_attribute("href")
                candidate = normalize_url(temp.url, href)
                if looks_like_pdf(candidate):
                    response = page.context.request.get(candidate)
                    if response.ok:
                        save_path.write_bytes(response.body())
                        return candidate

        raise RuntimeError("No downloadable PDF found for row.")
    finally:
        temp.close()


def download_grouped_documents(page, grouped_rows):
    """
    Downloads all collected rows, grouped by issue.
    """
    DOWNLOAD_ROOT.mkdir(parents=True, exist_ok=True)

    all_manifests = {}

    for issue, docs in grouped_rows.items():
        issue_dir = DOWNLOAD_ROOT / slugify(issue)
        issue_dir.mkdir(parents=True, exist_ok=True)

        manifest = []
        doc_types_in_order = []

        for idx, doc in enumerate(docs, start=1):
            doc_type = doc["doc_type"] or "UnknownDocType"
            doc_types_in_order.append(doc_type)

            file_name = f"{idx:02d}_{safe_doc_type(doc_type)}.pdf"
            save_path = unique_path(issue_dir / file_name)

            try:
                pdf_url = click_and_capture_pdf(page, doc["href"], save_path)
                status = "downloaded"
            except Exception as e:
                pdf_url = None
                status = f"failed: {str(e)}"

            manifest.append({
                "date": doc["date"],
                "issue": doc["issue"],
                "manager_fa": doc["manager_fa"],
                "par_amt": doc["par_amt"],
                "doc_type": doc["doc_type"],
                "type": doc["type"],
                "size_mb": doc["size_mb"],
                "source_href": doc["href"],
                "resolved_pdf_url": pdf_url,
                "file_name": save_path.name if pdf_url else None,
                "status": status,
            })

            time.sleep(0.75)

        concatenated_doc_types = " | ".join(doc_types_in_order)

        (issue_dir / "doc_types.txt").write_text(
            f"Issue: {issue}\n"
            f"Concatenated Doc Types: {concatenated_doc_types}\n"
            f"Document Count: {len(docs)}\n",
            encoding="utf-8"
        )

        (issue_dir / "manifest.json").write_text(
            json.dumps({
                "issue": issue,
                "concatenated_doc_types": concatenated_doc_types,
                "documents": manifest,
            }, indent=2),
            encoding="utf-8"
        )

        all_manifests[issue] = {
            "issue_dir": str(issue_dir),
            "document_count": len(docs),
            "concatenated_doc_types": concatenated_doc_types,
        }

    (DOWNLOAD_ROOT / "summary.json").write_text(
        json.dumps(all_manifests, indent=2),
        encoding="utf-8"
    )


def group_by_issue(rows):
    grouped = {}
    for row in rows:
        issue = row["issue"]
        grouped.setdefault(issue, []).append(row)
    return grouped


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS)
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()

        page.goto(START_URL, wait_until="domcontentloaded")

        if WAIT_FOR_MANUAL_LOGIN:
            input(
                "\nLog in, apply any filters you want, make sure the table is visible, then press ENTER...\n"
            )

        page.wait_for_load_state("networkidle")
        time.sleep(2)

        all_rows = collect_all_rows(page)
        print(f"Collected {len(all_rows)} rows total.")

        grouped = group_by_issue(all_rows)
        print(f"Found {len(grouped)} unique issues.")

        download_grouped_documents(page, grouped)

        print(f"Finished. Output written to: {DOWNLOAD_ROOT.resolve()}")

        browser.close()


if __name__ == "__main__":
    main()