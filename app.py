#!/usr/bin/env python3
"""
doc2struct Web UI Backend
Provides an interactive split-view interface to upload/view original documents (PDF/HTML)
and inspect doc2struct structured JSON output with readability controls and
table stitching recovery.
"""

import gzip
import json
import os
import time
import urllib.request
import uuid
from collections import Counter
from pathlib import Path
from flask import Flask, request, jsonify, send_file, render_template

try:
    import doc2struct
    from doc2struct.visualizer import visualize_standardized_text
except ImportError:
    print("Error: doc2struct not found. Make sure you activate your venv or install doc2struct.")
    raise

from stitch_tables import auto_stitch_document
from extract_facts import postprocess_extracted_facts

BASE_DIR = Path(__file__).resolve().parent
TEMP_DOCS_DIR = BASE_DIR / "temp_docs"
SAMPLES_DIR = BASE_DIR / "samples"
TEMP_DOCS_DIR.mkdir(exist_ok=True)
SAMPLES_DIR.mkdir(exist_ok=True)

app = Flask(__name__, template_folder="templates", static_folder="static")
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024  # 100 MB max upload

# Store metadata for loaded documents
DOC_STORE = {}


@app.after_request
def add_cache_headers(response):
    """Ensure browsers always get the latest scripts and templates without caching."""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


def detect_file_type(content: bytes, filename: str = "") -> str:
    """Detect whether file is PDF, HTML, JSON, or TXT."""
    lower_fn = filename.lower()
    if lower_fn.endswith(".pdf") or content[:5] == b"%PDF-":
        return "pdf"
    if lower_fn.endswith((".htm", ".html")) or b"<html" in content[:2000].lower() or b"<!doctype" in content[:2000].lower():
        return "html"
    if lower_fn.endswith(".json") or (content.strip()[:1] in (b"[", b"{") and content.strip()[-1:] in (b"]", b"}")):
        try:
            json.loads(content.decode("utf-8", errors="replace"))
            return "json"
        except Exception:
            pass
    return "text"


def process_with_doc2struct(content: bytes, file_type: str, rules: str = None) -> list:
    """Run doc2struct on bytes."""
    rule_arg = None if (not rules or rules.strip().lower() in ("none", "default", "")) else rules.strip()
    
    if file_type == "pdf":
        return doc2struct.parse_pdf(content, rules=rule_arg)
    elif file_type == "html":
        return doc2struct.parse_html(content, rules=rule_arg)
    else:
        return doc2struct.parse_text(content, rules=rule_arg)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/presets", methods=["GET"])
def get_presets():
    """Return available rule presets."""
    try:
        namespaces = doc2struct.list_namespaces()
        sec_types = doc2struct.list_document_types("SEC")
        presets = ["None (Default)", "SEC:10-K", "SEC:10-Q", "SEC:8-K"]
        for dt in sec_types:
            preset_name = f"SEC:{dt}"
            if preset_name not in presets:
                presets.append(preset_name)
        return jsonify({"namespaces": namespaces, "presets": presets})
    except Exception as e:
        return jsonify({"namespaces": ["SEC"], "presets": ["None (Default)", "SEC:10-K", "SEC:10-Q", "SEC:8-K"]})


@app.route("/api/visualizer/<doc_id>", methods=["GET"])
@app.route("/api/visualize/<doc_id>", methods=["GET"])
def get_visualizer(doc_id):
    """Generate and serve doc2struct HTML visualizer."""
    doc_info = DOC_STORE.get(doc_id)
    if not doc_info or "elements" not in doc_info:
        return jsonify({"error": "Visualizer data not found. Process a document first."}), 404
    vis_path = TEMP_DOCS_DIR / f"{doc_id}_vis.html"
    try:
        visualize_standardized_text(doc_info["elements"], filename=str(vis_path), open_browser=False)
        return send_file(vis_path, mimetype="text/html; charset=utf-8")
    except Exception as e:
        return jsonify({"error": f"Failed to generate visualizer: {str(e)}"}), 500


@app.route("/api/document/<path:doc_id>", methods=["GET"])
def get_document(doc_id):
    """Serve the original document or associated images for iframe embedding."""
    # Check if doc_id is an image requested by an HTML document
    lower_id = doc_id.lower()
    if lower_id.endswith((".jpg", ".jpeg", ".png", ".gif", ".svg")):
        img_path = TEMP_DOCS_DIR / doc_id
        if img_path.exists():
            return send_file(img_path)
        # Attempt fallback to EDGAR for SEC images
        edgar_url = f"https://www.sec.gov/Archives/edgar/data/1013237/000162828026066391/{doc_id}"
        try:
            req = urllib.request.Request(edgar_url, headers={"User-Agent": "SampleResearchApp/1.0 (contact@example.com)"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = resp.read()
                img_path.write_bytes(data)
                return send_file(img_path)
        except Exception:
            return jsonify({"error": "Image not found"}), 404

    doc_info = DOC_STORE.get(doc_id)
    if not doc_info:
        for p in TEMP_DOCS_DIR.glob(f"{doc_id}.*"):
            ext = p.suffix.lower()
            mimetype = "application/pdf" if ext == ".pdf" else "application/json; charset=utf-8" if ext == ".json" else "text/html; charset=utf-8" if ext in (".htm", ".html") else "text/plain"
            return send_file(p, mimetype=mimetype)
        return jsonify({"error": "Document not found"}), 404

    file_path = doc_info["path"]
    ft = doc_info["file_type"]
    mimetype = "application/pdf" if ft == "pdf" else "application/json; charset=utf-8" if ft == "json" else "text/html; charset=utf-8" if ft == "html" else "text/plain"
    return send_file(file_path, mimetype=mimetype, as_attachment=False)


@app.route("/api/parse", methods=["POST"])
def parse_document():
    """Upload and process a document with automatic table stitching."""
    rules = request.form.get("rules", "SEC:10-K")
    doc_bytes = None
    filename = "document"

    if "file" in request.files and request.files["file"].filename != "":
        uploaded = request.files["file"]
        filename = uploaded.filename
        doc_bytes = uploaded.read()

    elif request.form.get("url"):
        url = request.form.get("url").strip()
        filename = url.split("/")[-1] or "document.htm"
        headers = {
            "User-Agent": "ResearchAssistant/1.0 (sec-research@example.com)",
            "Accept-Encoding": "gzip, deflate"
        }
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read()
                if resp.info().get("Content-Encoding") == "gzip":
                    doc_bytes = gzip.decompress(raw)
                else:
                    doc_bytes = raw
        except Exception as e:
            return jsonify({"error": f"Failed to fetch URL: {str(e)}"}), 400

    if not doc_bytes:
        return jsonify({"error": "No file uploaded or URL provided"}), 400

    file_type = detect_file_type(doc_bytes, filename)
    doc_id = str(uuid.uuid4())[:8]

    ext = ".pdf" if file_type == "pdf" else ".html" if file_type == "html" else ".json" if file_type == "json" else ".txt"
    file_path = TEMP_DOCS_DIR / f"{doc_id}{ext}"
    file_path.write_bytes(doc_bytes)

    DOC_STORE[doc_id] = {
        "doc_id": doc_id,
        "filename": filename,
        "file_type": file_type,
        "path": file_path,
        "size": len(doc_bytes)
    }

    start_time = time.perf_counter()
    try:
        if file_type == "json":
            raw_elements = json.loads(doc_bytes.decode("utf-8", errors="replace"))
            if not isinstance(raw_elements, list):
                raw_elements = [raw_elements]
        else:
            raw_elements = process_with_doc2struct(doc_bytes, file_type, rules)
    except Exception as e:
        return jsonify({"error": f"doc2struct parsing failed: {str(e)}"}), 500

    # Post-processing Step 1: Numeric Fact Extraction for text nodes
    raw_elements = postprocess_extracted_facts(raw_elements)

    # Post-processing Step 2: Table Stitching & Recovery
    elements, stitch_meta = auto_stitch_document(raw_elements, filename)
    elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)

    DOC_STORE[doc_id]["elements"] = elements

    counts = dict(Counter(e.get("type", "unknown") for e in elements))
    sec_items = [
        {
            "id": e.get("id"),
            "level": e.get("level"),
            "standardized_title": e.get("standardized_title"),
            "text": e.get("text")
        }
        for e in elements if e.get("class") == "item"
    ]
    total_facts = sum(len(e.get("extracted_facts", [])) for e in elements if (e.get("type") or "").lower() == "text")

    return jsonify({
        "status": "success",
        "doc_id": doc_id,
        "filename": filename,
        "file_type": file_type,
        "file_size": len(doc_bytes),
        "rules": rules,
        "view_url": f"/api/document/{doc_id}",
        "elapsed_ms": elapsed_ms,
        "total_elements": len(elements),
        "type_counts": counts,
        "sec_items": sec_items,
        "total_extracted_facts": total_facts,
        "stitched": stitch_meta.get("stitched", False),
        "stitched_count": stitch_meta.get("count", 0),
        "flagged_count": stitch_meta.get("flagged", 0),
        "stitched_tables": stitch_meta.get("stitched_tables", []),
        "data": elements
    })


@app.route("/api/load-sample", methods=["GET", "POST"])
def load_sample():
    """Load sample documents with table stitching."""
    sample_key = request.args.get("sample", "fds").lower()

    if sample_key == "hitachi":
        sample_path = SAMPLES_DIR / "Hitachi Construction Machinery Group_human-capital-report2025-EN.pdf"
        file_type = "pdf"
        filename = "Hitachi_Construction_Machinery_Group_human-capital-report2025-EN.pdf"
        doc_id = "sample_hitachi"
        rules = "None"
    elif sample_key == "toyota":
        sample_path = SAMPLES_DIR / "Toyota_Tsusho_human_capital_report_en_2025.pdf"
        file_type = "pdf"
        filename = "Toyota_Tsusho_human_capital_report_en_2025.pdf"
        doc_id = "sample_toyota"
        rules = "None"
    elif sample_key in ("tw", "taiwan"):
        sample_path = SAMPLES_DIR / "TWSampleESGReport.pdf"
        file_type = "pdf"
        filename = "TWSampleESGReport.pdf"
        doc_id = "sample_tw"
        rules = "None"
    else:  # fds
        sample_path = BASE_DIR / "fds-20260831.htm"
        file_type = "html"
        filename = "fds-20260831.htm (FactSet 10-K)"
        doc_id = "sample_fds_10k"
        rules = "SEC:10-K"

    if not sample_path.exists():
        return jsonify({"error": f"Sample file not found: {sample_path.name}"}), 404

    doc_bytes = sample_path.read_bytes()
    ext = ".pdf" if file_type == "pdf" else ".html"
    dest_path = TEMP_DOCS_DIR / f"{doc_id}{ext}"
    dest_path.write_bytes(doc_bytes)

    DOC_STORE[doc_id] = {
        "doc_id": doc_id,
        "filename": filename,
        "file_type": file_type,
        "path": dest_path,
        "size": len(doc_bytes)
    }

    start_time = time.perf_counter()
    if file_type == "pdf":
        raw_elements = doc2struct.parse_pdf(doc_bytes)
    else:
        raw_elements = doc2struct.parse_html(doc_bytes, rules=rules)

    # Post-processing Step 1: Numeric Fact Extraction for text nodes
    raw_elements = postprocess_extracted_facts(raw_elements)

    # Post-processing Step 2: Table Stitching & Recovery
    elements, stitch_meta = auto_stitch_document(raw_elements, filename)
    elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
    DOC_STORE[doc_id]["elements"] = elements

    counts = dict(Counter(e.get("type", "unknown") for e in elements))
    sec_items = [
        {
            "id": e.get("id"),
            "level": e.get("level"),
            "standardized_title": e.get("standardized_title"),
            "text": e.get("text")
        }
        for e in elements if e.get("class") == "item"
    ]
    total_facts = sum(len(e.get("extracted_facts", [])) for e in elements if (e.get("type") or "").lower() == "text")

    return jsonify({
        "status": "success",
        "doc_id": doc_id,
        "filename": filename,
        "file_type": file_type,
        "file_size": len(doc_bytes),
        "rules": rules,
        "view_url": f"/api/document/{doc_id}",
        "elapsed_ms": elapsed_ms,
        "total_elements": len(elements),
        "type_counts": counts,
        "sec_items": sec_items,
        "total_extracted_facts": total_facts,
        "stitched": stitch_meta.get("stitched", False),
        "stitched_count": stitch_meta.get("count", 0),
        "flagged_count": stitch_meta.get("flagged", 0),
        "stitched_tables": stitch_meta.get("stitched_tables", []),
        "data": elements
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    print(f"Starting doc2struct Web UI on http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)
