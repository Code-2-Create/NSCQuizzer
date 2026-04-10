from __future__ import annotations

import re


def _word_count(text: str) -> int:
    return len(text.split())


def _normalize_terms(priority_terms: dict[str, list[str]] | None, chapter: str) -> list[str]:
    if not priority_terms:
        return []
    return [term.strip().lower() for term in priority_terms.get(chapter, []) if term.strip()]


def _chunk_priority_score(chunk: str, priority_terms: list[str]) -> int:
    if not priority_terms:
        return 0
    lowered_chunk = chunk.lower()
    return sum(lowered_chunk.count(term) for term in priority_terms)


def retrieve_chapter_context(
    chapter_chunks: dict[str, list[str]],
    selected_chapters: list[str],
    priority_terms: dict[str, list[str]] | None = None,
    max_words: int = 1800,
) -> list[str]:
    if not selected_chapters:
        raise ValueError("No chapters selected for retrieval.")

    missing_chapters = [chapter for chapter in selected_chapters if chapter not in chapter_chunks]
    if missing_chapters:
        raise ValueError(f"Selected chapters not found: {', '.join(missing_chapters)}")

    combined_chunks: list[str] = []
    prioritized_chunks = {
        chapter: sorted(
            chapter_chunks[chapter],
            key=lambda chunk: (_chunk_priority_score(chunk, _normalize_terms(priority_terms, chapter)), len(chunk)),
            reverse=True,
        )
        for chapter in selected_chapters
    }
    per_chapter_indices = {chapter: 0 for chapter in selected_chapters}
    total_words = 0

    while total_words < max_words:
        progress_made = False
        for chapter in selected_chapters:
            chapter_list = prioritized_chunks[chapter]
            chunk_index = per_chapter_indices[chapter]
            if chunk_index >= len(chapter_list):
                continue

            chunk = chapter_list[chunk_index]
            chunk_words = _word_count(chunk)
            if combined_chunks and total_words + chunk_words > max_words:
                continue

            combined_chunks.append(f"[{chapter}]\n{chunk}")
            total_words += chunk_words
            per_chapter_indices[chapter] += 1
            progress_made = True

            if total_words >= max_words:
                break

        if not progress_made:
            break

    if not combined_chunks:
        raise ValueError("No content could be retrieved for the selected chapters.")

    return combined_chunks


def extract_pyq_style_context(
    pyq_text: str,
    max_words: int = 700,
    max_blocks: int = 8,
) -> str:
    if not pyq_text.strip():
        return ""

    normalized = re.sub(r"\n{2,}", "\n\n", pyq_text).strip()
    split_pattern = r"(?=(?:^|\n)\s*(?:Q(?:uestion)?\s*)?\d+\s*[\).:-])"
    candidate_blocks = [block.strip() for block in re.split(split_pattern, normalized) if block.strip()]

    filtered_blocks = [
        block
        for block in candidate_blocks
        if "?" in block or re.search(r"\b[A-D][\).]\s", block)
    ]

    if not filtered_blocks:
        paragraphs = [part.strip() for part in normalized.split("\n\n") if part.strip()]
        filtered_blocks = paragraphs[:max_blocks]

    selected_blocks: list[str] = []
    total_words = 0
    for block in filtered_blocks[: max_blocks * 2]:
        words = _word_count(block)
        if selected_blocks and total_words + words > max_words:
            break
        selected_blocks.append(block)
        total_words += words
        if len(selected_blocks) >= max_blocks or total_words >= max_words:
            break

    return "\n\n".join(selected_blocks)


def extract_pyq_question_lines(pyq_text: str) -> list[str]:
    if not pyq_text.strip():
        return []

    question_lines: list[str] = []
    seen: set[str] = set()
    current_parts: list[str] = []

    def add_question(candidate: str) -> None:
        normalized_candidate = re.sub(r"\s+", " ", candidate).strip()
        if not normalized_candidate:
            return
        if re.search(r"\s\d+\.\s", normalized_candidate):
            return
        if len(normalized_candidate.split()) < 5 or len(normalized_candidate.split()) > 35:
            return

        normalized = normalized_candidate.lower()
        if normalized in seen:
            return
        seen.add(normalized)
        question_lines.append(normalized_candidate)

    for raw_line in pyq_text.splitlines():
        line = re.sub(r"\s+", " ", raw_line).strip()
        if not line:
            continue

        if re.match(r"^\d+\.\s+", line):
            if current_parts:
                add_question(" ".join(current_parts))
            current_parts = [re.sub(r"^\d+\.\s*", "", line).strip()]
            continue

        if current_parts and not re.fullmatch(r"\d+", line):
            current_parts.append(line)

    if current_parts:
        add_question(" ".join(current_parts))

    return question_lines


def build_pyq_subject_bank(
    pyq_text: str,
    subject_keywords: dict[str, list[str]],
) -> dict[str, list[str]]:
    question_lines = extract_pyq_question_lines(pyq_text)
    subject_bank: dict[str, list[str]] = {subject: [] for subject in subject_keywords}

    for line in question_lines:
        normalized_line = line.lower()
        for subject, keywords in subject_keywords.items():
            if any(keyword in normalized_line for keyword in keywords):
                subject_bank[subject].append(line)

    return subject_bank


def retrieve_pyq_examples(
    pyq_subject_bank: dict[str, list[str]],
    selected_chapters: list[str],
    per_topic_limit: int = 12,
    total_limit: int = 40,
) -> list[str]:
    selected_examples: list[str] = []
    seen: set[str] = set()

    for chapter in selected_chapters:
        for line in pyq_subject_bank.get(chapter, [])[:per_topic_limit]:
            normalized = line.lower()
            if normalized in seen:
                continue
            seen.add(normalized)
            selected_examples.append(line)
            if len(selected_examples) >= total_limit:
                return selected_examples

    return selected_examples
