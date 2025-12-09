# Small-automated-Agent_Assignment-Synapx-

1. Problem

The goal is to build a lightweight agent that:

- Extracts key fields from FNOL (First Notice of Loss) documents.
- Identifies missing or inconsistent fields.
- Classifies the claim and routes it to the correct workflow.
- Provides a short explanation for the routing decision.

The routing rules are implemented exactly as defined in the assignment brief. :contentReference[oaicite:6]{index=6}  

2. Approach

2.1 Tools & Stack

- Language: **Python 3.10+**
- Libraries:
  - `pdfplumber` – extract text from PDF FNOL documents
  - `re` – regex-based field extraction
  - `dataclasses` / `json` – structure and serialize outputs

2.2 Extraction

1. The PDF is parsed page by page using `pdfplumber`.
2. Regex patterns are applied to the full text to extract:
   - Policy information
   - Incident details
   - Involved parties (limited in this demo)
   - Asset details (automobile)
   - Estimate-related fields

The patterns are tuned to the **ACORD Automobile Loss Notice** layout. :contentReference[oaicite:7]{index=7} 

2.3 Validation & Missing Fields

A fixed list of mandatory fields is defined in `MANDATORY_FIELDS`.  
Any field not captured or empty is added to `missingFields` in the JSON output.

2.4 Routing Logic

The agent implements the following rules:

- If **any mandatory field is missing** → `Manual review`
- If description contains `fraud`, `inconsistent`, or `staged` → `Investigation Flag`
- If claim type contains the word `injury` → `Specialist Queue`
- If estimated damage `< 25,000` → `Fast-track`
- Otherwise → `Standard Queue`

The chosen route and a human-readable explanation are stored in `recommendedRoute` and `reasoning`.

2.5 Output Format

The agent outputs JSON in this shape:

```json
{
  "extractedFields": { "...": "..." },
  "missingFields": ["..."],
  "recommendedRoute": "Fast-track | Manual review | Investigation Flag | Specialist Queue | Standard Queue",
  "reasoning": "Short explanation..."
}
