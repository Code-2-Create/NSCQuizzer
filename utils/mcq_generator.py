from __future__ import annotations

import json
import os
import re
from typing import Any

from dotenv import load_dotenv
from groq import Groq

load_dotenv()

DEFAULT_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

DIFFICULTY_PROFILES = {
    "Easy": {
        "exact_ratio": 0.5,
        "temperature": 0.1,
        "instructions": [
            "Use direct recall and foundational facts from the selected topics.",
            "Prefer straightforward stems with one clearly correct answer.",
            "Use simpler distractors that are still relevant but less deceptive.",
            "Avoid multi-step reasoning and avoid combining multiple concepts in one question.",
        ],
    },
    "Medium": {
        "exact_ratio": 0.35,
        "temperature": 0.2,
        "instructions": [
            "Test conceptual understanding, distinctions between related ideas, and applied recall.",
            "Use distractors from the same subtopic so all four options feel believable.",
            "Prefer questions that require identifying the best match, not just repeating a definition.",
            "Include some exact PYQ-style stems, but ensure the rest are fresh and not repetitive.",
        ],
    },
    "Hard": {
        "exact_ratio": 0.15,
        "temperature": 0.3,
        "instructions": [
            "Avoid simple definition-only questions unless the distractors are very close and confusing.",
            "Prefer inference, comparison, multi-clue recall, or application within the selected topic.",
            "Use closely related distractors from the same concept family with similar length and tone.",
            "Do not make the correct option obvious by wording, specificity, or length.",
        ],
    },
}

GENERIC_QUESTION_PATTERNS = [
    r"^who\s+is\s+",
    r"^which\s+(?:navy|state|country|city|day|exercise|ship|vessel|mountain|river)\b",
    r"^.*\bis\s+the\s+.*\sof\s+which\b",
    r"^.*\bbelongs\s+to\s+which\b",
]

SPECIFICITY_PREFERRED_PATTERNS = [
    r"\bterm\b",
    r"\bdifference\b",
    r"\bpurpose\b",
    r"\bfunction\b",
    r"\brole\b",
    r"\bprinciple\b",
    r"\bused\s+for\b",
    r"\brefers\s+to\b",
    r"\bcalled\b",
    r"\bwhich\s+of\s+the\s+following\b",
]


def get_groq_client() -> Groq:
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is missing. Add it to your environment or .env file.")
    if api_key.lower().startswith("xai-"):
        raise RuntimeError(
            "GROQ_API_KEY appears to be an xAI key, not a Groq key. "
            "Please provide a valid Groq API key."
        )
    return Groq(api_key=api_key)


def get_difficulty_profile(difficulty: str) -> dict[str, Any]:
    return DIFFICULTY_PROFILES.get(difficulty, DIFFICULTY_PROFILES["Medium"])


def is_generic_question(question: str) -> bool:
    normalized = " ".join(question.lower().split())
    if normalized.startswith("expand ") or "full form" in normalized or "stands for" in normalized:
        return False
    if len(normalized.split()) < 7:
        return True
    return any(re.search(pattern, normalized) for pattern in GENERIC_QUESTION_PATTERNS)


def looks_specific_enough(question: str) -> bool:
    normalized = " ".join(question.lower().split())
    if any(re.search(pattern, normalized) for pattern in SPECIFICITY_PREFERRED_PATTERNS):
        return True
    return len(normalized.split()) >= 10


def has_balanced_options(options: list[str]) -> bool:
    option_lengths = [len(option.split()) for option in options]
    return max(option_lengths) - min(option_lengths) <= 8


def normalize_question(question: str) -> str:
    question = re.sub(r"^\d+[\).:-]?\s*", "", question.strip())
    return " ".join(question.lower().split())


def build_messages(
    syllabus_context: str,
    pyq_style_text: str,
    exact_pyq_questions: list[str],
    allowed_topics: list[str],
    topic_guidance: dict[str, list[str]],
    excluded_questions: list[str],
    num_questions: int,
    requested_generation_count: int,
    difficulty: str,
) -> list[dict[str, str]]:
    difficulty_profile = get_difficulty_profile(difficulty)
    exact_target = (
        max(1, round(requested_generation_count * difficulty_profile["exact_ratio"]))
        if exact_pyq_questions
        else 0
    )
    abbreviation_target = max(1, round(requested_generation_count / 5))
    exact_pyq_block = "\n".join(f"- {question}" for question in exact_pyq_questions) or "None"
    excluded_block = "\n".join(f"- {question}" for question in excluded_questions) or "None"
    allowed_topics_block = ", ".join(allowed_topics)
    topic_guidance_block = "\n".join(
        f"- {topic}: {', '.join(subtopics)}"
        for topic, subtopics in topic_guidance.items()
        if subtopics
    ) or "None"
    difficulty_instruction_block = "\n".join(
        f"- {instruction}" for instruction in difficulty_profile["instructions"]
    )

    system_prompt = (
        "You are an expert exam-setter. Generate factually correct MCQs using ONLY the syllabus "
        "content provided. Every question must stay strictly within the allowed topics. Use the "
        "selected PYQ stems to imitate style and, when asked, preserve those stems exactly while "
        "converting them into 4-option MCQs. Do not use facts from outside the syllabus context. "
        "Avoid repeating ideas or previously used questions. Keep questions clear, exam-oriented, "
        "and appropriate for the requested difficulty. Output a JSON array only, with no markdown "
        "fences or extra text. Each item must contain exactly these keys: question, options, "
        "correct_answer, explanation. options must contain exactly 4 distinct answer choices. "
        "correct_answer must match one item from options exactly. Prefer specific concept-based "
        "questions over generic one-fact identification questions."
    )

    user_prompt = f"""
Generate exactly {requested_generation_count} MCQs.

Difficulty: {difficulty}
Allowed topics: {allowed_topics_block}

Difficulty-specific behaviour:
{difficulty_instruction_block}

Rules:
1. Use only the syllabus context for factual content.
2. Keep every question strictly inside the allowed topics listed above. Do not mix in any other topic.
3. If a draft question falls outside the allowed topics, discard it and replace it before answering.
4. Use exactly {exact_target} questions from the Exact PYQ stems list below by preserving the stem wording as closely as possible, then convert them into 4-option MCQs.
5. For the remaining questions, create fresh questions inspired by the PYQ style but not copied from previous or exact PYQ stems.
6. Do not reuse or closely paraphrase anything from the Excluded questions list.
7. Make options plausible and non-repetitive.
8. Prioritize the important subtopics listed below when selecting question coverage.
9. For Medium and Hard difficulty, prefer confusing-but-fair distractors drawn from the same subtopic.
10. Include exactly {abbreviation_target} abbreviation/full-form questions. These can ask for expansions, meanings of signal groups, short forms, or matching abbreviations to full forms, but only if supported by the syllabus context or selected PYQ stems.
11. Spread abbreviation/full-form questions across the selected topics where possible instead of clustering them all in one area.
12. Avoid broad generic identification questions such as "X is the vessel of which navy?" or trivia-style prompts about names, places, or people unless that fact is a core syllabus concept.
13. Prefer specific conceptual stems such as terms, functions, distinctions, mechanisms, classifications, meanings, and roles within the selected topics.
14. Across all chapters, make the options belong to the same concept family as the correct answer.
15. Make the difficulty level meaningfully distinct from the other difficulty modes.
16. Keep each explanation under 35 words.
17. Return valid JSON only.

Expected JSON schema:
[
  {{
    "question": "string",
    "options": ["option 1", "option 2", "option 3", "option 4"],
    "correct_answer": "must exactly equal one option string",
    "explanation": "short explanation"
  }}
]

Syllabus context:
{syllabus_context}

PYQ style examples:
{pyq_style_text or "No PYQ style examples provided."}

Exact PYQ stems for selected topics:
{exact_pyq_block}

Important subtopics to prioritize:
{topic_guidance_block}

Excluded questions:
{excluded_block}
""".strip()

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def extract_json_array(raw_text: str) -> list[dict[str, Any]]:
    raw_text = raw_text.strip()
    if raw_text.startswith("```"):
        raw_text = re.sub(r"^```(?:json)?\s*", "", raw_text)
        raw_text = re.sub(r"\s*```$", "", raw_text)

    match = re.search(r"\[\s*{.*}\s*\]", raw_text, flags=re.DOTALL)
    json_payload = match.group(0) if match else raw_text
    parsed = json.loads(json_payload)

    if not isinstance(parsed, list):
        raise ValueError("Model output was not a JSON array.")
    return parsed


def normalize_correct_answer(correct_answer: str, options: list[str]) -> str | None:
    if correct_answer in options:
        return correct_answer

    normalized = correct_answer.strip().upper()
    letter_map = {"A": 0, "B": 1, "C": 2, "D": 3}
    if normalized in letter_map and len(options) == 4:
        return options[letter_map[normalized]]

    for option in options:
        if option.strip().lower() == correct_answer.strip().lower():
            return option
    return None


def collect_valid_mcqs(
    raw_mcqs: list[dict[str, Any]],
    excluded_questions: list[str] | None = None,
    strict: bool = True,
) -> list[dict[str, Any]]:
    validated: list[dict[str, Any]] = []
    seen_questions: set[str] = set()
    excluded_normalized = {
        normalize_question(question)
        for question in (excluded_questions or [])
        if question.strip()
    }

    for item in raw_mcqs:
        if not isinstance(item, dict):
            continue

        question = re.sub(r"^\d+[\).:-]?\s*", "", str(item.get("question", "")).strip())
        options = item.get("options", [])
        correct_answer = str(item.get("correct_answer", "")).strip()
        explanation = str(item.get("explanation", "")).strip()
        normalized_question = normalize_question(question)

        if not question or normalized_question in seen_questions or normalized_question in excluded_normalized:
            continue
        if strict and is_generic_question(question):
            continue
        if strict and not looks_specific_enough(question):
            continue
        if not isinstance(options, list):
            continue

        clean_options = [str(option).strip() for option in options if str(option).strip()]
        if len(clean_options) != 4 or len(set(clean_options)) != 4:
            continue
        if strict and not has_balanced_options(clean_options):
            continue

        normalized_answer = normalize_correct_answer(correct_answer, clean_options)
        if not normalized_answer:
            continue

        seen_questions.add(normalized_question)
        validated.append(
            {
                "question": question,
                "options": clean_options,
                "correct_answer": normalized_answer,
                "explanation": explanation,
            }
        )
    return validated


def validate_mcqs(
    raw_mcqs: list[dict[str, Any]],
    required_count: int,
    excluded_questions: list[str] | None = None,
    strict: bool = True,
) -> list[dict[str, Any]]:
    validated = collect_valid_mcqs(
        raw_mcqs,
        excluded_questions=excluded_questions,
        strict=strict,
    )
    if len(validated) < required_count:
        raise ValueError("The model returned fewer valid MCQs than requested.")
    return validated[:required_count]


def generate_mcqs(
    syllabus_chunks: list[str],
    pyq_style_text: str,
    exact_pyq_questions: list[str],
    allowed_topics: list[str],
    topic_guidance: dict[str, list[str]],
    num_questions: int,
    difficulty: str,
    excluded_questions: list[str] | None = None,
    model_name: str = DEFAULT_MODEL,
) -> list[dict[str, Any]]:
    client = get_groq_client()
    syllabus_context = "\n\n".join(syllabus_chunks)
    excluded_questions = excluded_questions or []
    difficulty_profile = get_difficulty_profile(difficulty)
    requested_generation_count = min(num_questions + max(4, num_questions // 2), num_questions * 2)
    aggregated_raw_mcqs: list[dict[str, Any]] = []

    last_error = "Unknown error"
    for _ in range(3):
        try:
            response = client.chat.completions.create(
                model=model_name,
                temperature=difficulty_profile["temperature"],
                messages=build_messages(
                    syllabus_context=syllabus_context,
                    pyq_style_text=pyq_style_text,
                    exact_pyq_questions=exact_pyq_questions,
                    allowed_topics=allowed_topics,
                    topic_guidance=topic_guidance,
                    excluded_questions=excluded_questions[:40],
                    num_questions=num_questions,
                    requested_generation_count=requested_generation_count,
                    difficulty=difficulty,
                ),
            )
            raw_content = response.choices[0].message.content or ""
            parsed = extract_json_array(raw_content)
            aggregated_raw_mcqs.extend(parsed)
            strict_validated = collect_valid_mcqs(
                aggregated_raw_mcqs,
                excluded_questions=excluded_questions,
                strict=True,
            )
            if len(strict_validated) >= num_questions:
                return strict_validated[:num_questions]
        except Exception as exc:
            last_error = str(exc)

    relaxed_validated = collect_valid_mcqs(
        aggregated_raw_mcqs,
        excluded_questions=excluded_questions,
        strict=False,
    )
    if len(relaxed_validated) >= num_questions:
        return relaxed_validated[:num_questions]

    raise RuntimeError(f"Unable to generate valid MCQs from Groq. {last_error}")
