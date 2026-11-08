# iATLAAS Doc Parser

A document parsing platform and interactive side-by-side visualizer powered by [**doc2struct**](https://github.com/john-friedman/doc2struct). 

iATLAAS Doc Parser provides both a web UI and CLI utilities to ingest complex documents (HTML, PDF, and TXT) and transform them into structured, hierarchical JSON data with table matrices, preambles, footnotes, and document section classifications.

---

## ✨ Features

- **Split-View Web Interface**:
  - **Left Pane**: Original document viewer (native HTML sandboxed iframe or embedded PDF viewer) with a toggle for doc2struct's native layout visualizer.
  - **Right Pane**: Structured JSON explorer featuring:
    - **Cards & Tables View**: Visual cards with nesting depth badges, type tags (`TITLE`, `TABLE`, `TEXT`, `LIST`), and SEC Item labels.
    - **Interactive Data Grids**: Formatted `<table>` views displaying extracted matrix cells, column alignments, preambles, and footnotes.
    - **Search & Filters**: Real-time text search and category filter pills (`Tables`, `Titles`, `Text`, `SEC Items`).
    - **SEC Section Navigator**: Quick-jump dropdown to jump directly to SEC items (e.g., Item 1 Business, Item 1A Risk Factors, Item 7 MD&A, Item 8 Financial Statements).
    - **Interactive JSON Tree**: Collapsible/expandable nodes with syntax highlighting.
    - **Raw JSON & Export**: Copy to clipboard or export directly as a `.json` file.
- **Fast Parsing Engine**:
  - Leverages `doc2struct`'s SIMD-accelerated C parsing core and PCRE2 regex engine.
  - Ingests multi-megabyte SEC filings in ~100ms.
- **SEC Filing Presets**:
  - Built-in support for presets including `SEC:10-K`, `SEC:10-Q`, `SEC:8-K`, and default document rulesets.
- **CLI Utility**:
  - Standalone script (`parse_sec_filing.py`) for automated downloading, parsing, and exporting SEC EDGAR filings.

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

1. Click **"Load 10-K Sample"** to instantly test with FactSet's 2026 Form 10-K.
2. Drag and drop any `.html` or `.pdf` file into the upload zone.
3. Or click **"URL"** and paste any public SEC EDGAR filing URL.

---

## 🖥️ Command-Line Usage

To parse an SEC Form 10-K directly from the command line:

```bash
python parse_sec_filing.py --url "https://www.sec.gov/Archives/edgar/data/1013237/000162828026066391/fds-20260831.htm" --json-out output.json
```

### CLI Arguments:
- `--url`: Public URL of the filing (default: FactSet Research Systems 10-K).
- `--rules`: Preset ruleset to apply (default: `SEC:10-K`).
- `--json-out`: File path to save the full structured output.
- `--no-cache`: Force re-download instead of using local cached filing.

---

## 📁 Project Structure

```text
iATLAAS-Doc-Parser/
├── app.py                  # Flask web backend and REST API
├── parse_sec_filing.py     # Standalone CLI SEC filing parser
├── requirements.txt        # Python package dependencies
├── templates/
│   └── index.html          # Split-view web application interface
├── fds-20260831.htm        # Sample FactSet 2026 Form 10-K HTML
├── parsed_output.json      # Sample parsed structured output JSON
├── test_sample.pdf         # Sample PDF test document
└── README.md               # Documentation
```

---

## ⚙️ REST API Endpoints

- `GET /`: Serves the web UI.
- `GET /api/presets`: Lists available document presets (`SEC:10-K`, `SEC:10-Q`, etc.).
- `POST /api/parse`: Upload a file (`file`) or pass a URL (`url`) with optional `rules` to parse.
- `GET /api/load-sample`: Parses and returns the bundled FactSet 10-K sample.
- `GET /api/document/<doc_id>`: Streams the original document for native preview.
- `GET /api/visualize/<doc_id>`: Streams doc2struct's native layout visualizer HTML.

---

## 📄 License

MIT
