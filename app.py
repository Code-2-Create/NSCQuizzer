from __future__ import annotations

import random
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from utils.cache import JSONCache, build_mcq_cache_key
from utils.chunking import build_chapter_chunks
from utils.evaluator import evaluate_quiz
from utils.mcq_generator import DEFAULT_MODEL, generate_mcqs
from utils.pdf_parser import extract_text_from_pdf, parse_syllabus_pdf
from utils.retriever import (
    build_pyq_subject_bank,
    extract_pyq_style_context,
    retrieve_chapter_context,
    retrieve_pyq_examples,
)

load_dotenv()

ROOT_DIR = Path(__file__).resolve().parent
SYLLABUS_PATH = ROOT_DIR / "Syllabus.pdf"
PYQ_PATH = ROOT_DIR / "SamplePYQs.pdf"
CACHE_FILE = ROOT_DIR / ".mcq_cache.json"

QUIZ_CACHE = JSONCache(CACHE_FILE)

FIXED_SUBJECTS = [
    "NAVAL ORIENTATION",
    "NAVAL COMMUNICATION",
    "NAVIGATION",
    "SEAMANSHIP",
    "WATERMANSHIP",
    "SHIP MODELLING",
    "FIRE FIGHTING AND DAMAGE CONTROL",
    "SWIMMING",
]

SUBJECT_KEYWORDS = {
    "NAVAL ORIENTATION": [
        "indian armed forces",
        "indian navy",
        "warships",
        "anti-submarine warfare",
        "surface warfare",
        "fleet operations",
        "naval aircraft",
        "submarines",
        "customs and traditions",
        "honours",
        "awards",
        "rank structure",
        "mode of entry",
    ],
    "NAVAL COMMUNICATION": [
        "naval communication",
        "semaphore",
        "phonetic alphabets",
        "radio telephony",
        "communication network",
        "cryptography",
        "line of sight",
        "los",
        "flag ",
        "hands call",
    ],
    "NAVIGATION": [
        "ship navigation",
        "chart work",
        "electronic aids",
        "tides",
        "astronavigation",
        "nautical chart",
        "course to steer",
        "compass",
        "magnetic meridian",
        "deviation",
        "bearing",
    ],
    "SEAMANSHIP": [
        "types of ropes",
        "bends and hitches",
        "shackles and blocks",
        "anchor and cable",
        "holding ground",
        "rope",
        "ropes",
        "splice",
        "splicing",
        "shackle",
        "block",
        "anchor",
        "cable",
        "fluke",
        "swivel",
        "knot",
        "hawser",
        "heaving line",
        "monkey fist",
        "hause pipe",
    ],
    "WATERMANSHIP": [
        "parts of boat",
        "rigging of sails",
        "enterprise class",
        "whaler sailing",
        "power boats",
        "boat",
        "oar",
        "bowman",
        "boat hook",
        "whaler",
        "sailing",
        "sail",
        "pulling",
        "hold water",
    ],
    "SHIP MODELLING": [
        "ship modelling",
        "ship models",
        "sail area",
        "tools",
        "remote-control models",
        "model",
        "models",
        "hull",
        "top view",
        "breadth of ship",
        "length and breadth",
    ],
    "FIRE FIGHTING AND DAMAGE CONTROL": [
        "fire fighting",
        "damage control",
        "flooding",
        "foam solution",
        "afff",
        "breathing apparatus",
        "leak",
        "red zone",
        "nbcdo",
    ],
    "SWIMMING": [
        "swimming",
    ],
}

IMPORTANT_TOPICS = {
    "NAVAL ORIENTATION": [
        "ranks",
        "equivalent ranks",
        "naval organisation at national level",
        "command level",
        "fleet level",
        "flotilla level",
        "ship level",
        "departments and heads in a ship",
        "establishments",
        "hospitals",
        "training institutes",
        "depots",
        "types of ships",
        "class and members",
    ],
    "NAVAL COMMUNICATION": [
        "semaphore",
        "combination meaning",
        "aaa for period",
        "flag meanings",
        "types of flags",
    ],
    "NAVIGATION": [
        "charts",
        "devices and instruments",
        "tides",
        "types of tides",
    ],
    "SEAMANSHIP": [
        "all important topics",
    ],
    "WATERMANSHIP": [
        "boat pulling",
    ],
    "SHIP MODELLING": [
        "types",
        "wood",
        "tools",
        "competitions",
    ],
    "FIRE FIGHTING AND DAMAGE CONTROL": [
        "all important topics",
    ],
    "SWIMMING": [
        "types",
        "characteristics",
        "frog paddle",
        "dolphin kicks",
    ],
}

st.set_page_config(page_title="NSC Quizzer", layout="centered")


@st.cache_data(show_spinner=False)
def load_content() -> tuple[dict[str, list[str]], str, dict[str, list[str]]]:
    if not SYLLABUS_PATH.exists():
        raise FileNotFoundError("Syllabus.pdf was not found in the project root.")
    if not PYQ_PATH.exists():
        raise FileNotFoundError("SamplePYQs.pdf was not found in the project root.")

    chapter_texts, _ = parse_syllabus_pdf(SYLLABUS_PATH.read_bytes(), SYLLABUS_PATH.name)
    syllabus_full_text = extract_text_from_pdf(SYLLABUS_PATH.read_bytes(), SYLLABUS_PATH.name)["full_text"]
    pyq_text = extract_text_from_pdf(PYQ_PATH.read_bytes(), PYQ_PATH.name)["full_text"]

    fixed_subject_texts = build_fixed_subject_texts(chapter_texts, syllabus_full_text)
    fixed_subject_chunks = build_chapter_chunks(fixed_subject_texts)
    pyq_style_text = extract_pyq_style_context(pyq_text)
    pyq_subject_bank = build_pyq_subject_bank(pyq_text, build_subject_focus_terms())
    return fixed_subject_chunks, pyq_style_text, pyq_subject_bank


def build_fixed_subject_texts(
    chapter_texts: dict[str, str],
    syllabus_full_text: str,
) -> dict[str, str]:
    normalized_chapters = {
        chapter_name: {
            "title": chapter_name.lower(),
            "content": f"{chapter_name}\n{text}",
            "content_lower": text.lower(),
        }
        for chapter_name, text in chapter_texts.items()
    }
    fixed_subject_texts: dict[str, str] = {}

    for subject in FIXED_SUBJECTS:
        subject_keywords = SUBJECT_KEYWORDS[subject]
        matched_sections = [
            chapter_data["content"]
            for chapter_data in normalized_chapters.values()
            if any(keyword in chapter_data["title"] for keyword in subject_keywords)
        ]

        if not matched_sections:
            for chapter_data in normalized_chapters.values():
                if any(keyword in chapter_data["content_lower"] for keyword in subject_keywords):
                    matched_sections.append(chapter_data["content"])

        if matched_sections:
            fixed_subject_texts[subject] = "\n\n".join(matched_sections)
            continue

        fallback_text = extract_subject_fallback_text(syllabus_full_text, subject_keywords)
        if fallback_text:
            fixed_subject_texts[subject] = fallback_text

    missing_subjects = [subject for subject in FIXED_SUBJECTS if subject not in fixed_subject_texts]
    if missing_subjects:
        raise ValueError(
            "Unable to map these fixed subjects from the syllabus: "
            + ", ".join(missing_subjects)
        )

    return fixed_subject_texts


def extract_subject_fallback_text(syllabus_full_text: str, keywords: list[str]) -> str:
    lines = [line.strip() for line in syllabus_full_text.splitlines() if line.strip()]
    matched_lines: list[str] = []

    for index, line in enumerate(lines):
        lower_line = line.lower()
        if any(keyword in lower_line for keyword in keywords):
            start = max(index - 2, 0)
            end = min(index + 5, len(lines))
            matched_lines.extend(lines[start:end])

    deduped_lines: list[str] = []
    seen = set()
    for line in matched_lines:
        normalized = line.lower()
        if normalized in seen:
            continue
        seen.add(normalized)
        deduped_lines.append(line)

    return "\n".join(deduped_lines)


def build_subject_focus_terms() -> dict[str, list[str]]:
    focus_terms: dict[str, list[str]] = {}
    for subject in FIXED_SUBJECTS:
        merged_terms = SUBJECT_KEYWORDS.get(subject, []) + IMPORTANT_TOPICS.get(subject, [])
        normalized_terms: list[str] = []
        seen = set()
        for term in merged_terms:
            normalized = term.strip().lower()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            normalized_terms.append(normalized)
        focus_terms[subject] = normalized_terms
    return focus_terms


def build_topic_guidance(selected_chapters: list[str]) -> dict[str, list[str]]:
    return {
        chapter: IMPORTANT_TOPICS.get(chapter, [])
        for chapter in selected_chapters
    }


def init_session_state() -> None:
    defaults = {
        "page": "home",
        "questions": [],
        "quiz_answers": [],
        "current_question_index": 0,
        "result": None,
        "selected_chapters": FIXED_SUBJECTS.copy(),
        "question_count": 10,
        "difficulty": "Medium",
        "quiz_notice": "",
        "question_history": {},
        "quiz_variant_counts": {},
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def clear_answer_widgets() -> None:
    for index in range(len(st.session_state.get("questions", []))):
        st.session_state.pop(f"answer_{index}", None)


def normalize_question_text(question_text: str) -> str:
    return " ".join(question_text.lower().split())


def build_history_key(selected_chapters: list[str], difficulty: str) -> str:
    return f"{'|'.join(sorted(selected_chapters))}::{difficulty}"


def build_variant_key(
    selected_chapters: list[str],
    difficulty: str,
    question_count: int,
) -> str:
    return f"{'|'.join(sorted(selected_chapters))}::{difficulty}::{question_count}"


def get_question_history(selected_chapters: list[str], difficulty: str) -> list[str]:
    history_key = build_history_key(selected_chapters, difficulty)
    return st.session_state["question_history"].get(history_key, [])


def get_cross_difficulty_history(selected_chapters: list[str]) -> list[str]:
    combined_history: list[str] = []
    seen: set[str] = set()

    for difficulty in ("Easy", "Medium", "Hard"):
        for question in get_question_history(selected_chapters, difficulty):
            normalized = normalize_question_text(question)
            if normalized in seen:
                continue
            seen.add(normalized)
            combined_history.append(question)

    return combined_history


def shuffled_items(items: list[str], seed: int) -> list[str]:
    shuffled = list(items)
    random.Random(seed).shuffle(shuffled)
    return shuffled


def store_question_history(
    selected_chapters: list[str],
    difficulty: str,
    questions: list[dict[str, object]],
) -> None:
    history_key = build_history_key(selected_chapters, difficulty)
    existing_history = st.session_state["question_history"].get(history_key, [])
    existing_normalized = {normalize_question_text(question) for question in existing_history}

    for question in questions:
        question_text = str(question["question"]).strip()
        normalized = normalize_question_text(question_text)
        if normalized in existing_normalized:
            continue
        existing_history.append(question_text)
        existing_normalized.add(normalized)

    st.session_state["question_history"][history_key] = existing_history[-120:]


def filter_new_questions(
    questions: list[dict[str, object]],
    selected_chapters: list[str],
    difficulty: str,
) -> list[dict[str, object]]:
    seen_history = {
        normalize_question_text(question)
        for question in get_cross_difficulty_history(selected_chapters)
    }
    fresh_questions: list[dict[str, object]] = []
    seen_batch: set[str] = set()

    for question in questions:
        normalized = normalize_question_text(str(question["question"]))
        if normalized in seen_history or normalized in seen_batch:
            continue
        seen_batch.add(normalized)
        fresh_questions.append(question)

    return fresh_questions


def start_quiz(questions: list[dict[str, str]], selected_chapters: list[str], difficulty: str) -> None:
    clear_answer_widgets()
    store_question_history(selected_chapters, difficulty, questions)
    st.session_state["questions"] = questions
    st.session_state["quiz_answers"] = [None] * len(questions)
    st.session_state["current_question_index"] = 0
    st.session_state["result"] = None
    st.session_state["selected_chapters"] = selected_chapters
    st.session_state["difficulty"] = difficulty
    st.session_state["page"] = "quiz"
    st.session_state["quiz_notice"] = ""


def reset_to_home() -> None:
    clear_answer_widgets()
    st.session_state["page"] = "home"
    st.session_state["questions"] = []
    st.session_state["quiz_answers"] = []
    st.session_state["current_question_index"] = 0
    st.session_state["result"] = None
    st.session_state["quiz_notice"] = ""


def sync_answers_from_widgets() -> None:
    for index in range(len(st.session_state.get("questions", []))):
        widget_key = f"answer_{index}"
        if widget_key in st.session_state:
            st.session_state["quiz_answers"][index] = st.session_state[widget_key]


def finalize_quiz() -> None:
    sync_answers_from_widgets()
    st.session_state["result"] = evaluate_quiz(
        st.session_state["questions"],
        st.session_state["quiz_answers"],
    )
    st.session_state["page"] = "result"


def render_home_page() -> None:
    st.title("NSC Quizzer")
    st.caption("choose the topics you want to practice")

    try:
        fixed_subject_chunks, pyq_style_text, pyq_subject_bank = load_content()
    except Exception as exc:
        st.error(str(exc))
        return

    selected_chapters = st.multiselect(
        "Chapter name",
        FIXED_SUBJECTS,
        default=st.session_state["selected_chapters"],
    )
    question_count = st.slider(
        "Number of questions",
        min_value=5,
        max_value=50,
        step=5,
        value=st.session_state["question_count"],
    )
    difficulty = st.selectbox(
        "Difficulty",
        ["Easy", "Medium", "Hard"],
        index=["Easy", "Medium", "Hard"].index(st.session_state["difficulty"]),
    )

    if st.button("Start Quiz", type="primary", use_container_width=True):
        if not selected_chapters:
            st.error("Select at least one chapter before starting the quiz.")
            return

        st.session_state["selected_chapters"] = selected_chapters
        st.session_state["question_count"] = question_count
        st.session_state["difficulty"] = difficulty

        try:
            topic_guidance = build_topic_guidance(selected_chapters)
            base_syllabus_chunks = retrieve_chapter_context(
                fixed_subject_chunks,
                selected_chapters,
                priority_terms=topic_guidance,
            )
            base_exact_pyq_questions = retrieve_pyq_examples(
                pyq_subject_bank,
                selected_chapters,
                per_topic_limit=max(4, question_count // max(len(selected_chapters), 1)),
                total_limit=max(question_count, 12),
            )
            excluded_questions = get_cross_difficulty_history(selected_chapters)
            variant_key = build_variant_key(selected_chapters, difficulty, question_count)
            next_variant = st.session_state["quiz_variant_counts"].get(variant_key, 0)

            with st.spinner("Generating quiz..."):
                questions: list[dict[str, object]] = []

                for variant_offset in range(4):
                    variant_index = next_variant + variant_offset
                    shuffled_syllabus_chunks = shuffled_items(base_syllabus_chunks, variant_index)
                    shuffled_exact_pyq_questions = shuffled_items(base_exact_pyq_questions, variant_index)
                    selected_pyq_style_text = (
                        "\n".join(
                            shuffled_exact_pyq_questions[: min(len(shuffled_exact_pyq_questions), 12)]
                        )
                        if shuffled_exact_pyq_questions
                        else pyq_style_text
                    )
                    cache_key = build_mcq_cache_key(
                        chapters=selected_chapters,
                        difficulty=difficulty,
                        count=question_count,
                        syllabus_context="\n\n".join(shuffled_syllabus_chunks),
                        pyq_context=selected_pyq_style_text,
                        model_name=DEFAULT_MODEL,
                        variant_tag=f"variant:{variant_index}",
                    )

                    cached_questions = QUIZ_CACHE.get(cache_key) or []
                    questions = filter_new_questions(cached_questions, selected_chapters, difficulty)
                    if len(questions) >= question_count:
                        st.session_state["quiz_variant_counts"][variant_key] = variant_index + 1
                        break

                    generated_questions = generate_mcqs(
                        syllabus_chunks=shuffled_syllabus_chunks,
                        pyq_style_text=selected_pyq_style_text,
                        exact_pyq_questions=shuffled_exact_pyq_questions[
                            : max(1, question_count // 2) + 4
                        ],
                        allowed_topics=selected_chapters,
                        topic_guidance=topic_guidance,
                        num_questions=question_count,
                        difficulty=difficulty,
                        excluded_questions=excluded_questions,
                    )
                    filtered_generated_questions = filter_new_questions(
                        generated_questions,
                        selected_chapters,
                        difficulty,
                    )
                    QUIZ_CACHE.set(cache_key, filtered_generated_questions)
                    questions = filtered_generated_questions
                    st.session_state["quiz_variant_counts"][variant_key] = variant_index + 1
                    if len(questions) >= question_count:
                        break

                if len(questions) < question_count:
                    raise ValueError(
                        "Not enough fresh questions were available for this topic selection. "
                        "Try changing the difficulty, question count, or selected chapters."
                    )

            start_quiz(questions, selected_chapters, difficulty)
            st.rerun()
        except Exception as exc:
            st.error(f"Quiz generation failed: {exc}")


def render_quiz_page() -> None:
    questions = st.session_state.get("questions", [])
    if not questions:
        reset_to_home()
        st.rerun()
        return

    total_questions = len(questions)
    current_index = st.session_state["current_question_index"]
    question = questions[current_index]
    options = question["options"]
    selected_option = st.session_state["quiz_answers"][current_index]
    option_labels = {
        option: f"{chr(65 + index)}. {option}"
        for index, option in enumerate(options)
    }

    st.title("Quiz")
    if st.session_state["quiz_notice"]:
        st.info(st.session_state["quiz_notice"])
    st.progress((current_index + 1) / total_questions)
    st.caption(f"Question {current_index + 1} of {total_questions}")
    st.markdown(f"### {question['question']}")

    first_row = st.columns(2)
    second_row = st.columns(2)
    button_columns = first_row + second_row

    for index, option in enumerate(options):
        with button_columns[index]:
            if st.button(
                option_labels[option],
                key=f"option_{current_index}_{index}",
                type="primary" if selected_option == option else "secondary",
                use_container_width=True,
            ):
                st.session_state["quiz_answers"][current_index] = option
                st.rerun()

    previous_col, next_col, submit_col = st.columns(3)

    with previous_col:
        if st.button("Previous", disabled=current_index == 0, use_container_width=True):
            sync_answers_from_widgets()
            st.session_state["current_question_index"] -= 1
            st.rerun()

    with next_col:
        label = "Finish" if current_index == total_questions - 1 else "Next"
        if st.button(label, type="primary", use_container_width=True):
            sync_answers_from_widgets()
            if st.session_state["quiz_answers"][current_index] is None:
                st.warning("Select an answer before moving ahead.")
            elif current_index == total_questions - 1:
                finalize_quiz()
                st.rerun()
            else:
                st.session_state["current_question_index"] += 1
                st.rerun()

    with submit_col:
        if st.button("Submit Quiz", use_container_width=True):
            finalize_quiz()
            st.rerun()


def render_result_page() -> None:
    result = st.session_state.get("result")
    if not result:
        reset_to_home()
        st.rerun()
        return

    st.title("Results")

    score_col, accuracy_col, incorrect_col = st.columns(3)
    score_col.metric("Score", f"{result['score']}/{result['total_questions']}")
    accuracy_col.metric("Accuracy", f"{result['percentage']:.1f}%")
    incorrect_col.metric("Incorrect", result["incorrect_count"])

    st.write(f"Chapters: {', '.join(st.session_state['selected_chapters'])}")
    st.write(f"Difficulty: {st.session_state['difficulty']}")

    retry_col, home_col = st.columns(2)
    with retry_col:
        if st.button(
            "Retry Incorrect Questions",
            disabled=not result["incorrect_questions"],
            use_container_width=True,
        ):
            start_quiz(
                result["incorrect_questions"],
                st.session_state["selected_chapters"],
                st.session_state["difficulty"],
            )
            st.session_state["quiz_notice"] = "Retry mode is active."
            st.rerun()

    with home_col:
        if st.button("Start New Quiz", use_container_width=True):
            reset_to_home()
            st.rerun()

    for index, review in enumerate(result["question_reviews"], start=1):
        status = "Correct" if review["is_correct"] else "Incorrect"
        with st.expander(f"Q{index}. {status}", expanded=not review["is_correct"]):
            st.write(review["question"])
            st.write(f"Your answer: {review['user_answer'] or 'Not answered'}")
            st.write(f"Correct answer: {review['correct_answer']}")
            if review["explanation"]:
                st.write(f"Explanation: {review['explanation']}")


def main() -> None:
    init_session_state()

    if st.session_state["page"] == "quiz":
        render_quiz_page()
    elif st.session_state["page"] == "result":
        render_result_page()
    else:
        render_home_page()


if __name__ == "__main__":
    main()
