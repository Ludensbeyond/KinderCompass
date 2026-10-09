"""Pure, offline Markdown selection and chunking for reviewed parent guidance.

No embeddings, generated files, or runtime retrieval are created here. Source
hashes pin review locators; unreviewed text never enters the returned corpus.
"""

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import urlparse

from SystemCode.src.backend.pipeline.general_knowledge_config import DEFAULT_VECTOR_PATH


@dataclass(frozen=True)
class ChunkingSettings:
    # Conservative planning estimate, not an embedding-model tokenizer.
    target_characters: int = 1800
    max_passage_characters: int = 5000
    version: str = "parent-guide-markdown-v1"

    def __post_init__(self):
        if not 1 <= self.target_characters <= self.max_passage_characters <= 5000:
            raise ValueError("Invalid parent-guide chunking bounds.")


@dataclass(frozen=True)
class MarkdownBlock:
    kind: str
    start_line: int
    end_line: int
    section_heading: str
    subsection_heading: str
    text: str


@dataclass(frozen=True)
class GuideChunk:
    chunk_id: str
    matrix_row: int
    mapping_id: str
    document_path: str
    document_title: str
    section_heading: str
    subsection_heading: str
    topic: str
    text: str
    embedding_text: str
    content_sha256: str
    evidence_scope: str
    evidence_category: str
    primary_source_id: str
    citation: dict
    source_links: tuple[str, ...]
    review_status: str
    required_qualifications: tuple[str, ...]
    policy_dates: dict
    document_checked_on: str
    source_verified_at: str
    indexed_at: None = None

    def to_dict(self) -> dict:
        """JSON-ready metadata; the later builder owns indexing timestamps."""
        return asdict(self)


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _cells(line: str) -> list[str]:
    return [cell.strip() for cell in re.split(r"(?<!\\)\|", line.strip().strip("|"))]


def _separator(line: str) -> bool:
    return bool(line.strip().startswith("|") and all(
        re.fullmatch(r":?-{3,}:?", cell) for cell in _cells(line)
    ))


def parse_markdown(markdown: str) -> tuple[MarkdownBlock, ...]:
    """Split sections/subsections first, retaining complete tables and lists."""
    lines = markdown.splitlines()
    blocks = []
    section = subsection = ""
    i = 0
    while i < len(lines):
        line = lines[i]
        heading = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
        if heading:
            level, title = len(heading[1]), heading[2]
            if level == 2:
                section, subsection = title, ""
            elif level >= 3:
                subsection = title
            i += 1
            continue
        if not line.strip():
            i += 1
            continue
        start = i
        if i + 1 < len(lines) and line.lstrip().startswith("|") and _separator(lines[i + 1]):
            kind = "table"
            i += 2
            while i < len(lines) and lines[i].lstrip().startswith("|"):
                i += 1
        else:
            kind = "list" if re.match(r"^\s*(?:[-*+] |\d+\. )", line) else "paragraph"
            i += 1
            while i < len(lines) and lines[i].strip() and not re.match(r"^#{1,6}\s", lines[i]):
                if i + 1 < len(lines) and _separator(lines[i + 1]):
                    break
                i += 1
        blocks.append(MarkdownBlock(kind, start + 1, i, section, subsection,
                                    "\n".join(lines[start:i])))
    return tuple(blocks)


def _sentences(text: str, indices: list[int]) -> str:
    # Reviewed guide uses numbered sentence locators. Avoid treating initials
    # such as M.Y World, decimals, or SPARK 2.0 as sentence boundaries.
    sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z])", text.strip())
    if not indices or len(set(indices)) != len(indices) or any(
        type(index) is not int or not 1 <= index <= len(sentences) for index in indices
    ):
        raise ValueError("Invalid reviewed sentence selection.")
    return " ".join(sentences[index - 1] for index in indices)


def _selected_lines(selection: dict, lines: list[str]) -> dict[int, str]:
    ranges = selection["line_ranges"]
    if not ranges or any(not 1 <= start <= end <= len(lines) for start, end in ranges):
        raise ValueError("Invalid reviewed line selection.")
    raw = "\n\n".join("\n".join(lines[start - 1:end]) for start, end in ranges)
    if _hash(raw) != selection["content_sha256"]:
        raise ValueError("Reviewed passage hash mismatch.")
    selected = {number: lines[number - 1] for start, end in ranges
                for number in range(start, end + 1)}
    if "sentence_selection" in selection:
        nonblank = [number for number, line in selected.items() if line.strip()]
        if len(nonblank) != 1:
            raise ValueError("Sentence selection requires one reviewed line.")
        number = nonblank[0]
        selected[number] = _sentences(selected[number], selection["sentence_selection"])
    for number, indices in selection.get("sentence_selection_by_line", {}).items():
        number = int(number)
        if number not in selected:
            raise ValueError("Sentence selection outside reviewed range.")
        selected[number] = _sentences(selected[number], indices)
    return selected


def _render_table(block: MarkdownBlock, selected: dict[int, str], columns: list[int] | None) -> str:
    lines = block.text.splitlines()
    width = len(_cells(lines[0]))
    columns = list(range(width)) if columns is None else columns
    if not columns or len(set(columns)) != len(columns) or any(
        type(column) is not int or not 0 <= column < width for column in columns
    ):
        raise ValueError("Invalid reviewed table column selection.")
    rows = [line for number, line in selected.items()
            if block.start_line + 2 <= number <= block.end_line]
    if not rows:
        raise ValueError("Reviewed table selection has no rows.")
    rendered = []
    for line in (lines[0], lines[1], *rows):
        cells = _cells(line)
        if len(cells) != width:
            raise ValueError("Inconsistent Markdown table columns.")
        rendered.append("| " + " | ".join(cells[column] for column in columns) + " |")
    return "\n".join(rendered)


def _passages(parts: list[tuple[str, str]], prefix: str, settings: ChunkingSettings) -> list[str]:
    """Keep reviewed prose/qualifications atomic; split tables by complete rows.

    Repeating the mapping's prose on every table group keeps explanatory notes
    and exceptions attached. Oversized prose or single rows require a new
    reviewed selection rather than silently dropping a qualification.
    """
    prose = "\n\n".join(text for kind, text in parts if kind != "table")
    tables = [text for kind, text in parts if kind == "table"]
    whole = "\n\n".join(text for _, text in parts)
    available = settings.max_passage_characters - len(prefix)
    target = min(settings.target_characters, available)
    if len(whole) <= target or not tables:
        if len(whole) > available:
            raise ValueError("Reviewed prose exceeds passage bound; review a smaller selection.")
        return [whole]
    passages = []
    for table in tables:
        header, separator, *rows = table.splitlines()
        group = []

        def render(group):
            return "\n\n".join(part for part in ("\n".join([header, separator, *group]), prose) if part)

        for row in rows:
            if group and len(render([*group, row])) > target:
                passages.append(render(group))
                group = []
            group.append(row)
            if len(render(group)) > available:
                raise ValueError("Table row and qualifications exceed passage bound.")
        if group:
            passages.append(render(group))
    return passages


def chunk_parent_guide(markdown: str, provenance: dict,
                       settings: ChunkingSettings = ChunkingSettings()) -> tuple[GuideChunk, ...]:
    """Return every eligible mapping, with one approved primary citation each."""
    if provenance["schema_version"] != 1 or _hash(markdown) != provenance["document_sha256"]:
        raise ValueError("Parent-guide source or schema mismatch.")
    lines = markdown.splitlines()
    blocks = parse_markdown(markdown)
    title_match = re.search(r"^#\s+(.+)$", markdown, re.MULTILINE)
    if not title_match:
        raise ValueError("Parent-guide title missing.")
    title = title_match[1]
    sources = {source["source_id"]: source for source in provenance["sources"]}
    sections = {section["section"]: section for section in provenance["sections"]}
    chunks = []
    seen_mappings = set()
    for mapping in provenance["approved_mappings"]:
        if not mapping["runtime_eligible"] or mapping["review_status"] != "verified":
            continue
        mapping_id = mapping["mapping_id"]
        if not mapping_id or mapping_id in seen_mappings:
            raise ValueError("Missing or duplicate reviewed mapping ID.")
        seen_mappings.add(mapping_id)
        source = sources[mapping["primary_source_id"]]
        url = source["resolved_url"]
        if (urlparse(url).scheme != "https" or not urlparse(url).netloc
                or source["fetch_status"] != "content_available" or source["http_status"] != 200
                or not source["source_verified_at"]
                or source["source_verified_at"] != mapping["source_verified_at"]
                or mapping["evidence_scope"] != "general"):
            raise ValueError("Invalid reviewed primary citation.")
        selected = _selected_lines(mapping, lines)
        parts = []
        contexts = set()
        for block in blocks:
            intersecting = {number: text for number, text in selected.items()
                            if block.start_line <= number <= block.end_line and text.strip()}
            if not intersecting:
                continue
            contexts.add((block.section_heading, block.subsection_heading))
            text = (_render_table(block, intersecting, mapping.get("table_columns"))
                    if block.kind == "table" else "\n".join(intersecting.values()))
            parts.append((block.kind, text))
        if len(contexts) != 1 or not parts:
            raise ValueError("Reviewed selection crosses heading boundaries or is empty.")
        section, subsection = contexts.pop()
        if section != sections[mapping["section"]]["heading"]:
            raise ValueError("Reviewed section does not match Markdown heading.")
        for context in mapping.get("context_selections", []):
            extra = _selected_lines(context, lines)
            parts.append(("paragraph", "\n".join(extra.values())))
        prefix = "\n".join(part for part in (title, section, subsection) if part) + "\n\n"
        for text in _passages(parts, prefix, settings):
            embedding_text = prefix + text
            content_hash = _hash(embedding_text)
            chunk_id = _hash(mapping_id + "\n" + content_hash)
            chunks.append(GuideChunk(
                chunk_id=chunk_id, matrix_row=len(chunks), mapping_id=mapping_id,
                document_path=provenance["document_path"], document_title=title,
                section_heading=section, subsection_heading=subsection, topic=section,
                text=text, embedding_text=embedding_text, content_sha256=content_hash,
                evidence_scope="general", evidence_category=mapping["evidence_category"],
                primary_source_id=source["source_id"],
                citation={"url": url, "retrieved_at": source["source_verified_at"]},
                source_links=tuple(sources[source_id]["url"] for source_id in
                                   sections[mapping["section"]]["source_ids"]),
                review_status=mapping["review_status"],
                required_qualifications=tuple(mapping["required_qualifications"]),
                policy_dates=dict(mapping["policy_dates"]),
                document_checked_on=provenance["document_checked_on"],
                source_verified_at=source["source_verified_at"],
            ))
    if len({chunk.chunk_id for chunk in chunks}) != len(chunks):
        raise ValueError("Duplicate parent-guide chunk ID.")
    return tuple(chunks)


def load_parent_guide_chunks(provenance_path: Path = DEFAULT_VECTOR_PATH / "sources.json",
                           settings: ChunkingSettings = ChunkingSettings()) -> tuple[GuideChunk, ...]:
    """Convenience reader for offline callers; performs no writes or API calls."""
    provenance_path = Path(provenance_path)
    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    document = provenance_path.parent.parent / provenance["document_path"]
    # Decode bytes directly so reviewed CRLF/source hashes cannot be normalised.
    return chunk_parent_guide(document.read_bytes().decode("utf-8"), provenance, settings)
