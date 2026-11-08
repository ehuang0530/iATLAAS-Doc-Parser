# iATLAAS Doc Parser

A document parsing platform and interactive side-by-side visualizer powered by [**doc2struct**](https://github.com/john-friedman/doc2struct) and enhanced with a **Table Stitching & Recovery Engine**.

iATLAAS Doc Parser provides both a web UI and CLI utilities to ingest complex documents (HTML, PDF, and TXT) and transform them into structured, hierarchical JSON data with clean 2D table matrices, preambles, footnotes, and document section classifications.

---

## ✨ Features

- **Split-View Web Interface**:
  - **Left Pane**: Original document viewer (native HTML sandboxed iframe or embedded PDF viewer) with a toggle for doc2struct's native layout visualizer.
  - **Right Pane**: Structured JSON explorer featuring:
    - **Cards & Tables View**: Visual cards with nesting depth badges, type tags (`TITLE`, `TABLE`, `TEXT`, `LIST`), and SEC Item labels.
    - **Table Stitching & Recovery Engine**:
      - Automatically detects fragmented tables in PDFs misclassified as text/list/title blocks.
      - Reconstructs rectangular 2D matrices with explicit `Entity Scope` / `Group` columns.
      - Repeats vertically merged labels and targets (e.g., `"Below previous year's figures"`, `"Statutory or over"`).
      - Preserves dashes (`"-"`, `"—"`) and units (`"%"`, `"hours/year"`, `"Million Yen"`, `"Cases"`).
      - Highlights stitched tables with `✨ Stitched Table Matrix` badges and surfaces `⚠️ Needs Visual Check` alerts for interleaved multi-column layouts.
      - Dedicated `✨ Stitched Tables` filter pill to view only reconstructed tables in one click.
    - **Search & Filters**: Real-time text search and category filter pills (`Tables`, `Stitched Tables`, `Titles`, `Text`, `SEC Items`).
    - **SEC Section Navigator**: Quick-jump dropdown to jump directly to SEC items (e.g., Item 1 Business, Item 1A Risk Factors, Item 7 MD&A, Item 8 Financial Statements).
    - **Interactive JSON Tree**: Collapsible/expandable nodes with syntax highlighting.
    - **Raw JSON & Export**: Copy to clipboard or export directly as a `.json` file.
- **Fast Parsing Engine**:
  - Leverages `doc2struct`'s SIMD-accelerated C parsing core and PCRE2 regex engine.
  - Ingests multi-megabyte SEC filings and sustainability reports in milliseconds.
- **Sample Documents Included**:
  - **Hitachi Construction Machinery Group Human Capital Report 2025** (PDF with 6 stitched tables)
  - **Toyota Tsusho Human Capital Report 2025** (PDF with 4 multi-page master metrics tables)
  - **Taiwan Sample ESG Report** (PDF with 4 stitched HR & turnover tables)
  - **FactSet Form 10-K** (SEC HTML)

---

## 🚀 Quick Start

### 1. Prerequisites
- Python 3.10 or higher
- macOS, Linux, or Windows

### 2. Setup Virtual Environment & Install Dependencies

```bash
# Clone the repository
git clone https://github.com/ehuang0530/iATLAAS-Doc-Parser.git
cd iATLAAS-Doc-Parser

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install required packages
pip install -r requirements.txt
```

### 3. Launch the Web Interface

```bash
python app.py
```

Open your browser to:
```
http://localhost:5050
```

1. Select any sample from the **Sample** dropdown (Hitachi, Toyota Tsusho, Taiwan ESG, or FactSet 10-K) and click **Load**.
2. Or drag and drop any `.html` or `.pdf` file into the upload zone.
3. Or click **"URL"** and paste any public SEC EDGAR filing URL.

---

## 🧩 Table Stitching & Recovery Workflow

When parsing complex PDFs with multi-column layouts, table rows may be split into fragmented text blocks or misclassified as titles. Use `stitch_tables.py` to detect and reconstruct them:

### Step 1: Detect Fragmented Table Clusters
```bash
python stitch_tables.py detect --input parsed_doc.json --output suspect_tables.json
```

### Step 2: Reconstruct 2D Table Matrices
Inspect candidates in `suspect_tables.json` and author rectangular matrices in `stitched_tables.json` following the standard schema:
```json
[
  {
    "cluster_id": "cluster_410_414",
    "preceding_title": "Total number of employees",
    "table_title": "Age Distribution",
    "block_ids": [410, 412, 414],
    "matrix": [
      ["Entity Scope", "Category", "Unit", "2022FY", "2023FY", "2024FY", "Target (2025FY)"],
      ["Global consolidated", "60 years old and above", "People", "1,228", "1,313", "1,247", "-"],
      ["Hitachi Construction Machinery (standalone)", "Under 30 years old", "People", "1,154", "1,300", "1,223", "-"]
    ],
    "needs_visual_check": true,
    "visual_check_reason": "Reading order scrambled across multi-column layout on Page 22."
  }
]
```

### Step 3: Apply Stitched Tables to Document JSON
```bash
python stitch_tables.py apply --input parsed_doc.json --stitched stitched_tables.json --output parsed_doc_stitched.json
```

---

## 🖥️ Command-Line Usage

To parse an SEC Form 10-K directly from the command line:

```bash
python parse_sec_filing.py --url "https://www.sec.gov/Archives/edgar/data/1013237/000162828026066391/fds-20260831.htm" --json-out output.json
```

---

## 📁 Project Structure

```text
iATLAAS-Doc-Parser/
├── app.py                      # Flask web backend and REST API (auto table stitching)
├── stitch_tables.py            # Table detection and matrix reconstruction CLI & engine
├── stitched_tables.json        # Hitachi reconstructed table matrices
├── stitched_tables_toyota.json # Toyota Tsusho reconstructed metrics matrices
├── stitched_tables_tw.json     # Taiwan ESG reconstructed metrics matrices
├── parse_sec_filing.py         # Standalone CLI SEC filing parser
├── requirements.txt            # Python dependencies
├── templates/
│   └── index.html              # Split-view web application interface
├── samples/                    # Test report PDFs (Hitachi, Toyota, Taiwan ESG)
├── fds-20260831.htm            # Sample FactSet 2026 Form 10-K HTML
├── parsed_doc_stitched.json    # Hitachi patched doc2struct JSON
├── parsed_toyota_stitched.json # Toyota patched doc2struct JSON
├── parsed_tw_stitched.json     # Taiwan ESG patched doc2struct JSON
└── README.md                   # Documentation
```
