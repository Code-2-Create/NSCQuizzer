from __future__ import annotations

import re


def split_into_chunks(
    text: str,
    min_words: int = 300,
    max_words: int = 500,
    overlap_words: int = 60,
) -> list[str]:
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []

    words = text.split()
    if len(words) <= max_words:
        return [" ".join(words)]

    chunks: list[str] = []
    start = 0
    while start < len(words):
        end = min(start + max_words, len(words))
        if end < len(words) and end - start >= min_words:
            search_start = start + min_words
            search_end = min(start + max_words, len(words))
            best_break = end
            for index in range(search_end - 1, search_start - 1, -1):
                if re.search(r"[.!?]$", words[index]):
                    best_break = index + 1
                    break
            end = best_break

        chunk_words = words[start:end]
        if chunk_words:
            chunks.append(" ".join(chunk_words))
        if end >= len(words):
            break
        start = max(end - overlap_words, start + 1)

    return chunks


def build_chapter_chunks(
    chapter_texts: dict[str, str],
    min_words: int = 300,
    max_words: int = 500,
) -> dict[str, list[str]]:
    chapter_chunks: dict[str, list[str]] = {}
    for chapter_name, chapter_text in chapter_texts.items():
        chapter_chunks[chapter_name] = split_into_chunks(
            chapter_text,
            min_words=min_words,
            max_words=max_words,
        )
    return chapter_chunks
