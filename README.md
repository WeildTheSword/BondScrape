# Prospectus Scraper + Issue Browser

This project scrapes municipal bond document listings from the Prospectus website, consolidates the documents by issue, and provides a browser UI for exploring the results.

The workflow consists of three stages:

1. Scrape document metadata from the website
2. Consolidate the scraped rows into issue-level JSON
3. Launch a local UI to browse the results

---

# Project Folder Structure

Your project should look like this:

```
BondScrape/
│
├── scraper_linkpull.py
├── build_issue_index.py
├── index.html
├── README.md
│
├── prospectus_json/
│   ├── rows_raw.json
│   └── processed/
│       ├── issues_grouped.json
│       └── documents_flat.json
│
└── .venv/
```

If the `processed` folder does not exist yet, create it once:

```
mkdir -p prospectus_json/processed
```

---

# 1. Navigate to the Project Folder

Open a terminal and move into the project directory.

Example:

```
cd ~/Desktop/BondScrape
```

---

# 2. Activate the Python Virtual Environment

Activate the environment used by the scraper.

```
python3 -m venv .venv
source .venv/bin/activate
```

Your terminal should now look like:

```
(.venv) username@machine %
```

---

# 3. Install Dependencies (First Time Only)

Install Playwright:

```
pip install playwright
```

Install browser binaries:

```
python3 -m playwright install
```

You only need to run this once.

---

# 4. Run the Scraper

Run the scraper script:

```
python3 scraper_linkpull.py
```

What happens:

1. A browser window opens
2. Log into the site manually
3. Apply any filters if needed
4. Press ENTER in the terminal when ready

The scraper will:

- load document batches
- scrape every row
- resolve document links
- save the results

Output file created:

```
prospectus_json/rows_raw.json
```

---

# 5. Build the Consolidated Dataset

Process the raw rows into issue-grouped JSON.

```
python3 build_issue_index.py
```

This script:

- reads `rows_raw.json`
- groups documents by issue
- prepares datasets for the UI

Output files created:

```
prospectus_json/processed/issues_grouped.json
prospectus_json/processed/documents_flat.json
```

---

# 6. Launch the UI

Start a local web server:

```
python3 -m http.server 8000
```

Terminal should show:

```
Serving HTTP on 0.0.0.0 port 8000
```

---

# 7. Open the Browser Interface

Open your browser and go to:

```
http://localhost:8000
```

The UI will load:

- the consolidated issue dataset
- expandable issue cards
- document links
- search and filters

---

# Issue Card Colors

Issues are automatically color-coded by issue date.

| Status | Color |
|------|------|
| Issue date has passed | Light Red |
| Issue date upcoming or today | Light Blue |

The earliest document date associated with an issue is used as the issue date.

---

# Normal Workflow

After initial setup, your normal workflow will be:

```
cd bond_ui_project
source .venv/bin/activate

python3 scraper_linkpull.py
python3 build_issue_index.py

python3 -m http.server 8000
```

Then open:

```
http://localhost:8000
```

---

# When to Run Each Script

| Task | Command |
|------|--------|
| Scrape fresh site data | `python3 scraper_linkpull.py` |
| Rebuild UI dataset | `python3 build_issue_index.py` |
| Launch UI | `python3 -m http.server 8000` |

---

# Stopping the Server

Press:

```
CTRL + C
```

in the terminal running the server.










---

# Quick Run Commands

```
cd BondScrape
source .venv/bin/activate

python3 scraper_linkpull.py
python3 build_issue_index.py

python3 -m http.server 8000
```

Open in browser:

```
http://localhost:8000
```

