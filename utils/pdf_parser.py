from __future__ import annotations

import re
import unicodedata
from math import ceil
from typing import Any

import fitz

EXPLICIT_CHAPTER_PATTERNS = (
    re.compile(r"^chapter\s*(?:no\.?|number)?\s*[-:]?\s*\d+\s*[:\-]?\s*.+", re.IGNORECASE),
    re.compile(r"^chapter\s+\d+\s*[:\-]?\s*.+", re.IGNORECASE),
)

SECTION_HEADING_PATTERNS = (
    re.compile(r"^\(code[-\s]?[a-z]+\)\s+.+", re.IGNORECASE),
    re.compile(r"^section index\s*:\s*.+", re.IGNORECASE),
)

NON_HEADING_PREFIXES = (
    "part ",
    "assessment",
    "teaching instructions",
    "conducting officer",
    "training aids",
    "time plan",
    "page no",
    "s no",
)


def clean_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text or "")
    normalized = normalized.replace("\xa0", " ")
    normalized = re.sub(r"[ \t]+", " ", normalized)
    normalized = re.sub(r"[•●▪■◦]", " ", normalized)
    normalized = re.sub(r"[^\w\s.,;:!?()/%+\-\"'&\[\]\n]", " ", normalized)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)

    cleaned_lines: list[str] = []
    for line in normalized.splitlines():
        stripped = re.sub(r"\s+", " ", line).strip(" -:\t")
        if not stripped:
            continue
        if re.fullmatch(r"[_=\-.]{3,}", stripped):
            continue
        cleaned_lines.append(stripped)
    return "\n".join(cleaned_lines).strip()


def extract_text_from_pdf(pdf_source: bytes | str, source_name: str = "PDF") -> dict[str, Any]:
    if isinstance(pdf_source, bytes):
        document = fitz.open(stream=pdf_source, filetype="pdf")
    else:
        document = fitz.open(pdf_source)

    page_texts: list[str] = []
    try:
        for page in document:
            page_texts.append(clean_text(page.get_text("text")))
    finally:
        document.close()

    full_text = "\n\n".join(page for page in page_texts if page).strip()
    if not full_text:
        raise ValueError(
            f"{source_name} appears empty or scanned as images only. "
            "Please upload a text-based PDF."
        )

    return {
        "page_texts": page_texts,
        "full_text": full_text,
        "page_count": len(page_texts),
    }


def is_probable_heading(line: str) -> bool:
    stripped = line.strip()
    words = stripped.split()
    if len(words) < 2 or len(words) > 10:
        return False

    lower_stripped = stripped.lower()
    if lower_stripped.startswith(NON_HEADING_PREFIXES):
        return False

    keyword_match = re.match(
        r"^(chapter|unit|module|topic|part|section)\s+[\w.-]+(?:\s*[:\-]\s*|\s+).+",
        lower_stripped,
    )
    numbered_match = re.match(r"^\d+(?:\.\d+)*[\).:-]?\s+[A-Z][A-Za-z0-9\s,&/\-]{2,}$", stripped)
    uppercase_match = stripped.isupper() and len(words) <= 6
    title_case_ratio = sum(word[:1].isupper() for word in words if word[:1].isalpha()) / max(
        sum(word[:1].isalpha() for word in words),
        1,
    )
    title_case_match = title_case_ratio >= 0.85 and len(words) <= 5 and len(stripped) <= 45

    if keyword_match or numbered_match or uppercase_match:
        return True

    if title_case_match and not stripped.endswith((".", "?", "!", ";")):
        return True
    return False


def normalize_heading_text(heading: str) -> str:
    heading = clean_text(heading)
    heading = re.sub(r"\s+", " ", heading).strip()
    if heading.isupper():
        heading = heading.title()
    return heading


def looks_like_explicit_heading(line: str) -> bool:
    return any(pattern.match(line) for pattern in EXPLICIT_CHAPTER_PATTERNS)


def looks_like_section_heading(line: str) -> bool:
    return any(pattern.match(line) for pattern in SECTION_HEADING_PATTERNS)


def is_index_page(page_text: str) -> bool:
    lines = [line.strip().lower() for line in page_text.splitlines() if line.strip()]
    first_lines = lines[:20]
    if any("index" in line for line in first_lines):
        return True
    page_range_count = len(re.findall(r"\b\d+\s*-\s*\d+\b", page_text))
    return page_range_count >= 4


def find_heading_in_lines(lines: list[str], allow_section_headings: bool = False) -> str | None:
    for index, raw_line in enumerate(lines[:20]):
        line = raw_line.strip()
        if looks_like_explicit_heading(line) or (
            allow_section_headings and looks_like_section_heading(line)
        ):
            return normalize_heading_text(line)
    return None


def split_text_into_sections(text: str, target_words: int = 1800) -> dict[str, str]:
    words = text.split()
    if not words:
        return {}

    section_count = max(1, ceil(len(words) / target_words))
    sections: dict[str, str] = {}
    for index in range(section_count):
        start = index * target_words
        end = min((index + 1) * target_words, len(words))
        chunk_words = words[start:end]
        sections[f"Section {index + 1}"] = " ".join(chunk_words)
    return sections


def detect_chapters_from_pages(page_texts: list[str]) -> tuple[dict[str, str], str] | None:
    for allow_section_headings, mode in (
        (False, "explicit_chapter_detection"),
        (True, "section_heading_detection"),
    ):
        chapters: dict[str, list[str]] = {}
        current_heading: str | None = None

        for page_text in page_texts:
            if not page_text.strip():
                continue
            if is_index_page(page_text):
                continue
            lines = [line.strip() for line in page_text.splitlines() if line.strip()]
            page_heading = find_heading_in_lines(lines, allow_section_headings=allow_section_headings)
            if page_heading:
                current_heading = page_heading
                chapters.setdefault(current_heading, [])
            if current_heading:
                chapters.setdefault(current_heading, []).append(page_text)

        cleaned_chapters = {
            title: clean_text("\n\n".join(content))
            for title, content in chapters.items()
            if clean_text("\n\n".join(content))
        }
        if len(cleaned_chapters) >= 2:
            return cleaned_chapters, mode
    return None


def detect_chapters(full_text: str) -> tuple[dict[str, str], str]:
    lines = [line.strip() for line in full_text.splitlines() if line.strip()]
    chapters: dict[str, list[str]] = {}
    current_heading = "Overview"

    for line in lines:
        if is_probable_heading(line):
            candidate_heading = re.sub(r"\s+", " ", line).strip()
            if candidate_heading in chapters:
                suffix = 2
                while f"{candidate_heading} ({suffix})" in chapters:
                    suffix += 1
                candidate_heading = f"{candidate_heading} ({suffix})"
            current_heading = candidate_heading
            chapters.setdefault(current_heading, [])
            continue

        chapters.setdefault(current_heading, []).append(line)

    cleaned_chapters = {
        title: clean_text("\n".join(content))
        for title, content in chapters.items()
        if clean_text("\n".join(content))
    }

    if len(cleaned_chapters) >= 2:
        return cleaned_chapters, "heading_detection"

    fallback_sections = split_text_into_sections(full_text)
    return fallback_sections, "manual_section_split"


def parse_syllabus_pdf(
    pdf_source: bytes | str,
    source_name: str = "Syllabus PDF",
) -> tuple[dict[str, str], dict[str, Any]]:
    extracted = extract_text_from_pdf(pdf_source, source_name)
    page_based_detection = detect_chapters_from_pages(extracted["page_texts"])
    if page_based_detection:
        chapters, chapter_mode = page_based_detection
    else:
        chapters, chapter_mode = detect_chapters(extracted["full_text"])
    if not chapters:
        raise ValueError(f"No usable content was found in {source_name}.")

    metadata = {
        "source_name": source_name,
        "page_count": extracted["page_count"],
        "chapter_mode": chapter_mode,
    }
    return chapters, metadata
