"""Add the failed webpage identity-gate rationale to Report 2."""

from docx import Document


DOC = r"ProjectReport/KinderCompass_Report_2.docx"


def set_text(paragraph, text: str) -> None:
    if paragraph.runs:
        paragraph.runs[0].text = text
        for run in paragraph.runs[1:]:
            run.text = ""
    else:
        paragraph.add_run(text)


document = Document(DOC)

prefix = "Webpage RAG readiness in web_rag_readiness.json"
replacement = (
    "Webpage RAG readiness in web_rag_readiness.json scored retrieval accuracy "
    "0.9016, school isolation 1.0, and fetch success 0.8611. Identity accuracy "
    "was 0.90 (approximately 27 of 30 assessed identity cases) against a 0.95 "
    "gate, so the JSON snapshot records production_ready=false. This gate checks "
    "whether an indexed webpage is correctly verified as belonging to the intended "
    "school, branch, or operator scope. It is safety-critical because a well-grounded "
    "answer from the wrong centre's page would still misattribute evidence. The audit "
    "uses an all-gates-must-pass rule; therefore, passing retrieval and answer-quality "
    "gates cannot compensate for the failed identity gate. Deterministic webpage "
    "answers scored 0.7073 against a 0.90 gate; the LLM-plus-fallback path scored "
    "0.9024 and passed that gate. These report figures treat the JSON output as "
    "canonical; the separately generated Markdown readiness summary is not used "
    "because it does not describe the same snapshot."
)

for paragraph in document.paragraphs:
    if paragraph.text.strip().startswith(prefix):
        set_text(paragraph, replacement)
        break
else:
    raise ValueError("Webpage RAG readiness paragraph not found")

table = next(
    table
    for table in document.tables
    if table.rows and table.rows[0].cells[0].text.strip() == "Evaluation Metric"
)
row = next(
    row
    for row in table.rows
    if row.cells[0].text.strip().startswith("Webpage identity accuracy")
)
set_text(
    row.cells[2].paragraphs[0],
    "Identity verification ensures evidence belongs to the intended school, branch, "
    "or operator scope. Because readiness requires every gate to pass, retrieval and "
    "answer accuracy cannot override this failure; the conflicting Markdown summary "
    "is excluded.",
)

document.save(DOC)
print(f"Updated {DOC}")
