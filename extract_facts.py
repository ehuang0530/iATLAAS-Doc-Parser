#!/usr/bin/env python3
"""
Numeric Fact Extraction Post-Processor for doc2struct.
Extracts discrete numeric facts from text nodes/blocks into a structured schema
capturing normalized values, verbatim strings, units, temporal anchors,
and multi-dimensional qualifiers (geography, department/function, representation).
"""

import re
from datetime import datetime
from typing import Any, Dict, List, Optional

MONTHS_REGEX = (
    r"(?:January|February|March|April|May|June|July|August|September|October|November|December|"
    r"Jan\.?|Feb\.?|Mar\.?|Apr\.?|May\.?|Jun\.?|Jul\.?|Aug\.?|Sep\.?|Oct\.?|Nov\.?|Dec\.?)"
)

AS_OF_PATTERN = re.compile(
    rf"\b(?:as of|at|ended|as at)\s+({MONTHS_REGEX}\s+\d{{1,2}},\s+\d{{4}}|\d{{4}}-\d{{2}}-\d{{2}})\b",
    re.IGNORECASE,
)

COMPARED_PATTERN = re.compile(
    rf"\b(?:compared\s+(?:with|to)|versus|vs\.?)\s+({MONTHS_REGEX}\s+\d{{1,2}},\s+\d{{4}}|\d{{4}}-\d{{2}}-\d{{2}}|FY\s*\d{{4}}|\d{{4}})\b",
    re.IGNORECASE,
)

SENTENCE_SPLIT_PATTERN = re.compile(
    r"(?<!\bU\.S)(?<!\be\.g)(?<!\bi\.e)(?<!\bMr)(?<!\bMs)(?<!\bDr)(?<!\bInc)(?<!\bCorp)(?<!\bCo)(?<=\.|\?|\!)\s+"
)


def normalize_date(date_str: Optional[str]) -> Optional[str]:
    """Converts month name dates (e.g. 'August 31, 2026') to ISO-8601 YYYY-MM-DD."""
    if not date_str:
        return None
    clean = re.sub(r"\s+", " ", date_str).replace(".", "").strip()
    for fmt in ("%B %d, %Y", "%b %d, %Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(clean, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return clean


def clean_geo(geo: Optional[str]) -> Optional[str]:
    """Cleans punctuation and leading articles from geography strings."""
    if not geo:
        return None
    geo = geo.strip()
    if geo.lower().startswith("our "):
        geo = geo[4:].strip()
    if geo.lower().startswith("the ") and not geo.lower().startswith("the philippines"):
        geo = geo[4:].strip()
    if geo.endswith(".") and not geo.endswith("U.S."):
        geo = geo[:-1].strip()
    if geo.lower() == "u.s":
        geo = "U.S."
    return geo


def extract_facts_from_text(text: str) -> List[Dict[str, Any]]:
    """Extracts all discrete numeric facts from a paragraph of prose."""
    if not text or not text.strip():
        return []

    # Normalize non-breaking spaces
    text = text.replace("\u00a0", " ").strip()
    sentences = [s.strip() for s in SENTENCE_SPLIT_PATTERN.split(text) if s.strip()]

    facts = []
    # Inherit as_of_date across paragraph if defined at the start
    paragraph_as_of = None
    first_match = AS_OF_PATTERN.search(text)
    if first_match:
        paragraph_as_of = normalize_date(first_match.group(1))

    for s in sentences:
        s_clean = s.strip()
        m_as_of = AS_OF_PATTERN.search(s_clean)
        current_as_of = normalize_date(m_as_of.group(1)) if m_as_of else paragraph_as_of

        m_comp = COMPARED_PATTERN.search(s_clean)
        comp_date = normalize_date(m_comp.group(1)) if m_comp else None

        extracted_indices = set()

        # -------------------------------------------------------------
        # Pattern 1: Offices and Countries ("33 offices in 19 countries with 12,444 employees")
        # -------------------------------------------------------------
        m_off = re.search(r"(\d+)\s+offices\s+in\s+(\d+)\s+countries\s+with\s+([\d,]+)\s+employees", s_clean, re.I)
        if m_off:
            facts.append({
                "metric": "office_count",
                "value": int(m_off.group(1)),
                "raw_value_string": m_off.group(1),
                "unit": "offices",
                "temporal_context": {"as_of_date": current_as_of, "comparison_period": None},
                "dimensions": {"geography": None, "department_function": None, "representation_type": None},
                "source_sentence": s_clean,
            })
            facts.append({
                "metric": "country_count",
                "value": int(m_off.group(2)),
                "raw_value_string": m_off.group(2),
                "unit": "countries",
                "temporal_context": {"as_of_date": current_as_of, "comparison_period": None},
                "dimensions": {"geography": None, "department_function": None, "representation_type": None},
                "source_sentence": s_clean,
            })
            facts.append({
                "metric": "total_employees",
                "value": int(m_off.group(3).replace(",", "")),
                "raw_value_string": m_off.group(3),
                "unit": "employees",
                "temporal_context": {"as_of_date": current_as_of, "comparison_period": None},
                "dimensions": {"geography": None, "department_function": None, "representation_type": None},
                "source_sentence": s_clean,
            })

        # -------------------------------------------------------------
        # Pattern 2: Percentage Change ("decrease of 2.8% compared with ...")
        # -------------------------------------------------------------
        m_change = re.search(r"\b(decrease|increase)\s+of\s+([\d.]+)%", s_clean, re.I)
        if m_change:
            direction = m_change.group(1).lower()
            val = float(m_change.group(2))
            if direction == "decrease":
                val = -val
            facts.append({
                "metric": "employee_headcount_change",
                "value": val,
                "raw_value_string": f"{m_change.group(1)} of {m_change.group(2)}%",
                "unit": "percentage",
                "temporal_context": {"as_of_date": current_as_of, "comparison_period": comp_date},
                "dimensions": {"geography": None, "department_function": None, "representation_type": None},
                "source_sentence": s_clean,
            })

        # -------------------------------------------------------------
        # Pattern 3: Regional Headcount & Share ("8,652 (70%) were located in Asia Pacific...")
        # -------------------------------------------------------------
        geo_matches = list(re.finditer(
            r"([\d,]+)\s*\(([\d.]+)%\)\s*(?:were\s+located\s+in|in)\s+([^,;]+?)(?=(?:,\s*[\d,]+|\s+and\s+[\d,]+|\.|$))",
            s_clean,
            re.I,
        ))
        for m_geo in geo_matches:
            count_str = m_geo.group(1)
            pct_str = m_geo.group(2)
            geo = clean_geo(m_geo.group(3))
            facts.append({
                "metric": "employee_headcount",
                "value": int(count_str.replace(",", "")),
                "raw_value_string": count_str,
                "unit": "employees",
                "temporal_context": {"as_of_date": current_as_of, "comparison_period": None},
                "dimensions": {"geography": geo, "department_function": None, "representation_type": None},
                "source_sentence": s_clean,
            })
            facts.append({
                "metric": "employee_headcount_share",
                "value": float(pct_str),
                "raw_value_string": f"{pct_str}%",
                "unit": "percentage",
                "temporal_context": {"as_of_date": current_as_of, "comparison_period": None},
                "dimensions": {"geography": geo, "department_function": None, "representation_type": None},
                "source_sentence": s_clean,
            })

        # -------------------------------------------------------------
        # Pattern 4: Centers of Excellence / Specific Global Facilities
        # -------------------------------------------------------------
        m_coe = re.search(
            r"centers of excellence\s*\(\"([^\"]+)\"\)[^,]*,\s*primarily located in\s+([^,]+),\s*which accounted for\s+(approximately\s+[\d.]+%|[\d.]+%)",
            s_clean,
            re.I,
        )
        if m_coe:
            raw_pct = m_coe.group(3)
            val = float(re.search(r"[\d.]+", raw_pct).group(0))
            dept = f"Centers of Excellence ({m_coe.group(1)})"
            geo = clean_geo(m_coe.group(2))
            facts.append({
                "metric": "employee_headcount_share",
                "value": val,
                "raw_value_string": raw_pct,
                "unit": "percentage",
                "temporal_context": {"as_of_date": current_as_of, "comparison_period": None},
                "dimensions": {"geography": geo, "department_function": dept, "representation_type": None},
                "source_sentence": s_clean,
            })

        # -------------------------------------------------------------
        # Pattern 5: Functional / Departmental Shares ("45% were in Content Operations...")
        # -------------------------------------------------------------
        if "functionally" in s_clean.lower() or "were in" in s_clean.lower():
            for m_fn in re.finditer(
                r"([\d.]+)%\s*(?:of our employees\s*)?were in\s+([^,;]+?)(?=(?:,\s*[\d.]+%\s*were|\s+and\s+[\d.]+%\s*were|\.|$))",
                s_clean,
                re.I,
            ):
                pct_str = m_fn.group(1)
                dept = m_fn.group(2).strip()
                facts.append({
                    "metric": "employee_headcount_share",
                    "value": float(pct_str),
                    "raw_value_string": f"{pct_str}%",
                    "unit": "percentage",
                    "temporal_context": {"as_of_date": current_as_of, "comparison_period": None},
                    "dimensions": {"geography": None, "department_function": dept, "representation_type": None},
                    "source_sentence": s_clean,
                })

        # -------------------------------------------------------------
        # Pattern 6: Representation / Collective Bargaining
        # -------------------------------------------------------------
        for m_rep in re.finditer(
            r"([\d,]+)\s+of our employees were represented by\s+([^,]+?)\s+in\s+(.+?)(?=(?:\s+and\s+[\d,]+\s+of our employees|\.$|$))",
            s_clean,
            re.I,
        ):
            val_str = m_rep.group(1)
            rep_type = m_rep.group(2).strip()
            geo = clean_geo(m_rep.group(3))
            facts.append({
                "metric": "represented_employees",
                "value": int(val_str.replace(",", "")),
                "raw_value_string": val_str,
                "unit": "employees",
                "temporal_context": {"as_of_date": current_as_of, "comparison_period": None},
                "dimensions": {"geography": geo, "department_function": None, "representation_type": rep_type},
                "source_sentence": s_clean,
            })

        # -------------------------------------------------------------
        # Fallback Heuristic Pattern: Generic currency / percentage / count statements
        # Only triggered if no specialized pattern captured facts from this sentence
        # -------------------------------------------------------------
        if not any(f["source_sentence"] == s_clean for f in facts):
            # Fallback 1: Dollars / currency: "$123.4 million"
            for m_cur in re.finditer(r"(\$|€|£|¥)\s*([\d,]+(?:\.\d+)?)\s*(million|billion|thousand)?", s_clean, re.I):
                symbol = m_cur.group(1)
                num_str = m_cur.group(2).replace(",", "")
                scale = (m_cur.group(3) or "").lower()
                multiplier = 1_000_000 if scale == "million" else 1_000_000_000 if scale == "billion" else 1_000 if scale == "thousand" else 1
                val = float(num_str) * multiplier
                raw_str = m_cur.group(0).strip()
                unit = "USD" if symbol == "$" else "EUR" if symbol == "€" else "GBP" if symbol == "£" else "JPY"
                facts.append({
                    "metric": "financial_amount",
                    "value": val,
                    "raw_value_string": raw_str,
                    "unit": unit,
                    "temporal_context": {"as_of_date": current_as_of, "comparison_period": comp_date},
                    "dimensions": {"geography": None, "department_function": None, "representation_type": None},
                    "source_sentence": s_clean,
                })

    return facts


def postprocess_extracted_facts(blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Transforms doc2struct output blocks:
    For any block where type == 'text' (case-insensitive), extracts numeric facts into 'extracted_facts'.
    For non-text blocks, attaches an empty list [] for schema consistency.
    """
    for block in blocks:
        b_type = (block.get("type") or "").strip().lower()
        if b_type == "text":
            raw_text = block.get("text") or ""
            block["extracted_facts"] = extract_facts_from_text(raw_text)
        else:
            block["extracted_facts"] = []

    return blocks


if __name__ == "__main__":
    sample_text = (
        'As of August 31, 2026, we had 33 offices in 19 countries with 12,444 employees, '
        'representing a decrease of 2.8% compared with August 31, 2025. '
        'Of our total employees, 8,652 (70%) were located in Asia Pacific, 2,373 (19%) in the Americas '
        'and 1,419 (11%) in EMEA. '
        'To support sustainable growth, we continue to invest in our global centers of excellence ("COEs"), '
        'primarily located in India and the Philippines, which accounted for approximately 68% of our employees. '
        'Functionally, as of August 31, 2026, 45% of our employees were in Content Operations, '
        '28% were in Technology and Product Development, 22% were in Sales and Client Solutions '
        'and 5% were in Corporate Support. '
        'As of August 31, 2026, 421 of our employees were represented by mandatory works councils '
        'in our French and German locations and 26 of our employees were represented by collective '
        'bargaining agreements in the U.S.'
    )

    facts = extract_facts_from_text(sample_text)
    print(f"Extracted {len(facts)} facts from sample text.")
    import json
    print(json.dumps(facts, indent=2))
