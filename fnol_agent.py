import re
import json
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional
from pathlib import Path

import pdfplumber


MANDATORY_FIELDS = [
    "Policy Number",
    "Policyholder Name",
    "Date of Loss",
    "Time of Loss",
    "Location",
    "Description",
    "Claim Type",
    "Estimated Damage",
    "Asset Type",
    "Initial Estimate",
    "Attachments"
]

# Simple regex patterns tuned to the ACORD Automobile Loss Notice form
# (labels appear on pages 1–2 of your PDF). :contentReference[oaicite:0]{index=0}
FIELD_PATTERNS = {
    "Policy Number": r"POLICY NUMBER\s*([\w\-\/]+)",
    "Policyholder Name": r"NAME OF INSURED.*?\n([A-Z0-9 ,.'\-]+)",
    "Date of Loss": r"DATE OF LOSS AND TIME\s*([\d\/\-]+)",
    "Time of Loss": r"DATE OF LOSS AND TIME\s*[\d\/\-]+\s*([APM0-9: ]+)",
    "Location": r"LOCATION OF LOSS\s*\n(.+)",
    "Description": r"DESCRIPTION OF ACCIDENT.*?\n(.+)",
    # In this template, you may encode claim type via "LINE OF BUSINESS"
    "Claim Type": r"LINE OF BUSINESS\s*([A-Z0-9 ,.'\-]+)",
    # Damage / estimate fields appear at bottom of page 1 & 2. :contentReference[oaicite:1]{index=1}
    "Estimated Damage": r"ESTIMATE AMOUNT[: ]*\$?([\d,\.]+)",
    "Asset Type": r"AUTOMOBILE LOSS NOTICE",  # from form title → "Automobile"
}


@dataclass
class AgentOutput:
    extractedFields: Dict[str, Optional[str]]
    missingFields: List[str]
    recommendedRoute: str
    reasoning: str


def extract_text_from_pdf(pdf_path: str) -> str:
    """Extract raw text from all pages of a PDF."""
    text_parts = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text_parts.append(page.extract_text() or "")
    return "\n".join(text_parts)


def extract_fields(text: str) -> Dict[str, Optional[str]]:
    """Use regex patterns plus some heuristics to get field values."""
    fields: Dict[str, Optional[str]] = {k: None for k in MANDATORY_FIELDS}

    # 1. Regex-based extraction
    for field, pattern in FIELD_PATTERNS.items():
        match = re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
        if match:
            value = match.group(1).strip()
            # Special handling for asset type (we just know it's automobile)
            if field == "Asset Type":
                value = "Automobile"
            fields[field] = value

    # 2. Asset type fallback from title
    if fields.get("Asset Type") is None and "AUTOMOBILE LOSS NOTICE" in text.upper():
        fields["Asset Type"] = "Automobile"

    # 3. Placeholder values for fields that are not explicitly present in this form
    # Attachments & Initial Estimate could come from outside system / UI.
    # For now, we leave them as None and let routing handle missing.
    return fields


def parse_amount(amount_str: Optional[str]) -> Optional[float]:
    """Convert a currency-like string to float; None if not parseable."""
    if not amount_str:
        return None
    cleaned = re.sub(r"[^\d\.]", "", amount_str)
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def apply_routing_rules(fields: Dict[str, Optional[str]],
                        missing: List[str]) -> (str, str):
    """
    Implements routing from the assignment brief: :contentReference[oaicite:2]{index=2}

    - If any mandatory field is missing → Manual review
    - If description has 'fraud', 'inconsistent', 'staged' → Investigation Flag
    - If claim type = injury → Specialist Queue
    - If estimated damage < 25,000 → Fast-track
    """
    description = (fields.get("Description") or "").lower()
    claim_type = (fields.get("Claim Type") or "").lower()
    estimate_val = parse_amount(fields.get("Estimated Damage"))

    # 1. Missing mandatory fields ⇒ Manual review (highest priority)
    if missing:
        reason = (
            "One or more mandatory fields are missing: " +
            ", ".join(missing)
        )
        return "Manual review", reason

    # 2. Suspicious keywords ⇒ Investigation Flag
    suspicious_words = ["fraud", "inconsistent", "staged"]
    if any(word in description for word in suspicious_words):
        return (
            "Investigation Flag",
            "Description contains potential fraud-related keywords."
        )

    # 3. Injury claims ⇒ Specialist Queue
    if "injury" in claim_type:
        return (
            "Specialist Queue",
            "Claim type is injury, so it is routed to the specialist queue."
        )

    # 4. Fast-track if estimate < 25k
    if estimate_val is not None and estimate_val < 25000:
        return (
            "Fast-track",
            f"Estimated damage ({estimate_val}) is less than 25,000."
        )

    # 5. Fallback
    return (
        "Standard Queue",
        "All mandatory fields present, no special conditions matched."
    )


def find_missing_fields(fields: Dict[str, Optional[str]]) -> List[str]:
    return [name for name in MANDATORY_FIELDS if not fields.get(name)]


def process_pdf(pdf_path: str) -> AgentOutput:
    text = extract_text_from_pdf(pdf_path)
    fields = extract_fields(text)
    missing = find_missing_fields(fields)
    route, reasoning = apply_routing_rules(fields, missing)
    return AgentOutput(
        extractedFields=fields,
        missingFields=missing,
        recommendedRoute=route,
        reasoning=reasoning
    )


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Autonomous Insurance Claims Processing Agent"
    )
    parser.add_argument(
        "pdf_path",
        help="Path to FNOL / ACORD PDF"
    )
    parser.add_argument(
        "-o", "--output",
        help="Output JSON file (optional)",
        default=None
    )

    args = parser.parse_args()
    pdf_path = Path(args.pdf_path)

    if not pdf_path.exists():
        raise SystemExit(f"File not found: {pdf_path}")

    result = process_pdf(str(pdf_path))
    json_result = json.dumps(asdict(result), indent=2)
    print(json_result)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(json_result)
        print(f"\nJSON written to {args.output}")


if __name__ == "__main__":
    main()
