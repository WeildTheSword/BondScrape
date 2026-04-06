# scraper_linkpull.py
#
# Scrapes document metadata from i-dealprospectus.com. Uses Playwright to load
# the public document table, iterates through batches via the "Load Documents"
# button, and extracts row-level metadata (issue name, date, doc type, par amount,
# manager/FA, and document link). Outputs prospectus_json/scraper_output/scrape_output_raw.json.
#
# This script collects metadata and links only — it does not download PDFs.
# Supports headless mode and optional manual login for authenticated sessions.
#
# Dependencies: pip install playwright && python3 -m playwright install

import re
import json
import time
from pathlib import Path
from urllib.parse import urljoin

from playwright.sync_api import sync_playwright

# =========================
# CONFIG
# =========================
START_URL = "https://www.i-dealprospectus.com/Public"
OUTPUT_ROOT = Path("prospectus_json/scraper_output")
HEADLESS = True
WAIT_FOR_MANUAL_LOGIN = False

# Set to True if you want to start from an already filtered page and just scrape
# whatever is visible through batch loading.
USE_EXISTING_FILTERS = True


# =========================
# HELPERS
# =========================

'''
SLUGIFY

Convert an issue name into a safe identifier ("slug") that can be used
in filenames, folder names, URLs, or JSON keys.

Steps:
1. Remove characters that are not safe for paths or URLs.
   Allowed characters are letters, numbers, whitespace, hyphens,
   ampersands, commas, and parentheses.

2. Replace any sequence of whitespace characters with a single underscore
   so the string becomes easier to use in filenames or URLs.

3. Limit the length to 180 characters to prevent filesystem path issues.

4. If the resulting string is empty, return "unknown_issue" as a fallback.

Example:
"Wake (County of), NC General Obligation Bonds, Series 2026A&B"
->
"Wake_(County_of),_NC_General_Obligation_Bonds,_Series_2026A&B"
'''
def slugify(text: str) -> str:
    text = re.sub(r"[^\w\s\-&,()]+", "", text)
    text = re.sub(r"\s+", "_", text.strip())
    return text[:180] if text else "unknown_issue"


'''
NORMALIZE_URL

Ensure that a link extracted from the page becomes a full absolute URL.

Many websites use relative links such as:
    /Document/View/12345

This function combines the base page URL with that relative path
so that it becomes a valid absolute link.

Steps:
1. If the extracted link is empty, return None.
2. Otherwise combine the base URL with the relative path using urljoin.
'''
def normalize_url(base_url: str, maybe_relative: str | None) -> str | None:
    if not maybe_relative:
        return None
    return urljoin(base_url, maybe_relative)


'''
LOOKS_LIKE_PDF

Determine whether a URL likely points to a PDF document.

This is used before opening a page to avoid unnecessary navigation.

Steps:
1. If the URL is empty, return False.
2. Convert the URL to lowercase.
3. Check if ".pdf" or "pdf" appears in the URL string.

Returns:
True if the link likely references a PDF.
'''
def looks_like_pdf(url: str | None) -> bool:
    if not url:
        return False
    lower = url.lower()
    return ".pdf" in lower or "pdf" in lower


'''
GET_TABLE_ROWS

Locate the table rows containing bond documents.

Different web frameworks render tables differently, so several
CSS selectors are attempted.

Selectors checked:
- Standard HTML tables
- tbody rows
- role-based table layouts

Steps:
1. Try each selector in order.
2. If rows are found, return them.
3. If none match, raise an error.

This ensures the scraper fails loudly if the site layout changes.
'''
def get_table_rows(page):
    selectors = [
        "table tbody tr",
        "tbody tr",
        "[role='rowgroup'] [role='row']",
    ]

    for sel in selectors:
        print(f"Trying row selector: {sel}")
        loc = page.locator(sel)
        try:
            count = loc.count()
            if count > 0:
                print(f"Found {count} rows using selector: {sel}")
                return loc
        except Exception as e:
            print(f"Selector failed: {sel} -> {e}")

    raise RuntimeError("Could not find table rows. Inspect the DOM and update selectors.")


'''
PARSE_ROW

Extract the relevant information from a single table row.

Expected column structure:

0  Date
1  Issue
2  Manager / Financial Advisor
3  Par Amount
4  Document Type
5  Sale Type
6  File Size

Steps:
1. Locate the table cells.
2. Extract text from each column.
3. Locate the clickable link associated with the issue.
4. Return a dictionary representing the row.

This structured dictionary becomes the main data object used
throughout the scraper.
'''
def parse_row(row):
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


'''
NEXT_PAGE

Advance the table by clicking the site's "Load Documents ..." button.

This site does not appear to use normal pagination.
Instead, it loads the next group of documents into the same table.

Strategy:
1. Count how many rows are currently visible.
2. Look for a visible "Load Documents" button.
3. Click it.
4. Wait until the table contains more rows than before.
5. Return True if a new batch was loaded.

If no load button is present, return False.
'''
def next_page(page) -> bool:
    print("\nChecking for 'Load Documents' button...")

    rows = get_table_rows(page)
    old_count = rows.count()
    print(f"Current visible row count before loading more: {old_count}")

    load_more_selectors = [
        "button:has-text('Load Documents')",
        "text=Load Documents",
    ]

    for sel in load_more_selectors:
        btn = page.locator(sel).first

        try:
            if btn.count() > 0 and btn.is_visible():
                print(f"Found load button using selector: {sel}")
                print("Clicking button to load next document batch...")

                btn.click()

                print("Waiting for new rows to appear...")
                page.wait_for_function(
                    f"""
                    () => {{
                        const rows = document.querySelectorAll('table tbody tr, tbody tr, [role="rowgroup"] [role="row"]');
                        return rows.length > {old_count};
                    }}
                    """,
                    timeout=15000
                )

                time.sleep(1)

                new_rows = get_table_rows(page)
                new_count = new_rows.count()
                print(f"Next batch loaded successfully. New visible row count: {new_count}")
                return True

        except Exception as e:
            print(f"Error while attempting to load next batch with selector {sel}: {e}")

    print("No additional document batches detected.")
    return False


'''
COLLECT_ALL_ROWS

Iterate through every visible batch of the table and collect row metadata.

Steps:
1. Read all rows currently visible.
2. Parse each row into structured metadata.
3. Avoid duplicates using a signature set.
4. Print whether each row succeeded, failed, or was skipped as a duplicate.
5. Click the "Load Documents" button to append the next batch.
6. Continue until no more batches are available.

Returns:
A list of dictionaries representing every unique document row.
'''

def collect_all_rows(page):
    print("\nStarting row scraping loop...")

    all_rows = []
    seen_signatures = set()

    batch_number = 1
    success_row_number = 1
    last_processed_visible_count = 0

    while True:
        print(f"\n--- Processing batch {batch_number} ---")

        rows = get_table_rows(page)
        row_count = rows.count()

        print(f"Rows currently visible after batch {batch_number}: {row_count}")
        print(f"Previously processed visible rows: {last_processed_visible_count}")

        new_rows_this_batch = 0

        # only process rows that were newly appended
        start_index = last_processed_visible_count
        end_index = row_count

        print(f"Processing only new visible rows: {start_index + 1} to {end_index}")

        for i in range(start_index, end_index):
            row = rows.nth(i)

            try:
                print(f"Attempting to parse visible row {i + 1} in batch {batch_number}...")

                parsed = parse_row(row)

                signature = (
                    parsed["date"],
                    parsed["issue"],
                    parsed["doc_type"],
                    parsed["href"],
                )

                if signature in seen_signatures:
                    print(f"Visible row {i + 1} skipped (duplicate already seen).")
                    continue

                seen_signatures.add(signature)

                parsed["batch"] = batch_number
                parsed["visible_row_index"] = i + 1
                parsed["success_row_number"] = success_row_number

                all_rows.append(parsed)
                new_rows_this_batch += 1

                print(
                    f"Row {success_row_number} successfully scraped "
                    f"(batch {batch_number}, visible row {i + 1}) -> "
                    f"Issue: {parsed['issue']} | Doc Type: {parsed['doc_type']}"
                )

                success_row_number += 1

            except Exception as e:
                print(
                    f"Visible row {i + 1} failed to scrape "
                    f"(batch {batch_number}) -> {e}"
                )

        print(f"New unique rows added from batch {batch_number}: {new_rows_this_batch}")
        print(f"Running total rows collected: {len(all_rows)}")

        # update how many visible rows we've already processed
        last_processed_visible_count = row_count

        print("\nAttempting to load next batch...")
        moved = next_page(page)

        if not moved:
            print("No further batches available. Ending scraping loop.")
            break

        batch_number += 1

    return all_rows


'''
RESOLVE_PDF_URL

Determine the final PDF link associated with a document row.

Many sites use intermediate viewer pages before the actual PDF.

Strategy:
1. If the extracted link already appears to be a PDF, return it.
2. Otherwise open the landing page in a temporary tab.
3. Inspect embedded viewers (iframe, embed, object).
4. Search anchor tags for a PDF link.

Returns:
The resolved PDF URL if found.
'''
def resolve_pdf_url(page, row_href: str | None) -> str | None:
    print(f"Resolving PDF URL for href: {row_href}")

    base = page.url
    full_url = normalize_url(base, row_href)

    if looks_like_pdf(full_url):
        print(f"Direct PDF URL detected: {full_url}")
        return full_url

    temp = page.context.new_page()
    try:
        if full_url:
            print(f"Opening temporary page to inspect link target: {full_url}")
            temp.goto(full_url, wait_until="domcontentloaded", timeout=30000)
            temp.wait_for_load_state("networkidle", timeout=15000)

            candidate_url = temp.url
            if looks_like_pdf(candidate_url):
                print(f"Resolved PDF from landing page URL: {candidate_url}")
                return candidate_url

            for selector, attr in [("iframe", "src"), ("embed", "src"), ("object", "data")]:
                print(f"Inspecting embedded viewer selector: {selector}")
                elems = temp.locator(selector)
                count = elems.count()
                for i in range(count):
                    val = elems.nth(i).get_attribute(attr)
                    candidate = normalize_url(temp.url, val)
                    if looks_like_pdf(candidate):
                        print(f"Resolved PDF from embedded viewer: {candidate}")
                        return candidate

            print("Inspecting anchor tags for PDF links...")
            anchors = temp.locator("a")
            count = anchors.count()
            for i in range(count):
                href = anchors.nth(i).get_attribute("href")
                candidate = normalize_url(temp.url, href)
                if looks_like_pdf(candidate):
                    print(f"Resolved PDF from anchor tag: {candidate}")
                    return candidate

        print("No PDF URL could be resolved.")
        return None

    finally:
        temp.close()


def main():
    print("\nStarting scraper...")
    print("Launching browser...")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS)

        print("Creating browser context...")
        context = browser.new_context()

        print("Opening new page...")
        page = context.new_page()

        print(f"Navigating to: {START_URL}")
        page.goto(START_URL, wait_until="domcontentloaded")

        if WAIT_FOR_MANUAL_LOGIN:
            input(
                "\nWaiting for manual login.\n"
                "Log in, apply filters if needed, then press ENTER to begin scraping...\n"
            ) 
        STATE_PATH = OUTPUT_ROOT / "playwright_storage_state.json"
        OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
        context.storage_state(path=str(STATE_PATH))
        print(f"Saved Playwright session state to: {STATE_PATH}")

        print("Waiting for page network activity to settle...")
        page.wait_for_load_state("networkidle")
        time.sleep(2)

        print("\nBeginning row collection process...")
        all_rows = collect_all_rows(page)

        print(f"\nScraping complete.")
        print(f"Total unique rows collected: {len(all_rows)}")

        print("Creating output directory if needed...")
        OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

        output_file = OUTPUT_ROOT / "scrape_output_raw.json"
        print(f"Writing output JSON to: {output_file}")

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(all_rows, f, indent=2)

        print("JSON successfully written.")
        print(f"Saved JSON to {output_file.resolve()}")

        print("Closing browser...")
        browser.close()

        print("\nScraper finished successfully.")


if __name__ == "__main__":
    main()