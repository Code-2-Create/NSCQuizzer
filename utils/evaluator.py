from __future__ import annotations

from typing import Any


def evaluate_quiz(
    questions: list[dict[str, Any]],
    user_answers: list[str | None],
) -> dict[str, Any]:
    question_reviews: list[dict[str, Any]] = []
    incorrect_questions: list[dict[str, Any]] = []
    score = 0

    for index, question in enumerate(questions):
        user_answer = user_answers[index] if index < len(user_answers) else None
        correct_answer = question["correct_answer"]
        is_correct = user_answer == correct_answer
        if is_correct:
            score += 1
        else:
            incorrect_questions.append(question)

        question_reviews.append(
            {
                "question": question["question"],
                "user_answer": user_answer,
                "correct_answer": correct_answer,
                "explanation": question.get("explanation", ""),
                "is_correct": is_correct,
            }
        )

    total_questions = len(questions)
    percentage = (score / total_questions * 100) if total_questions else 0.0

    return {
        "score": score,
        "total_questions": total_questions,
        "correct_count": score,
        "incorrect_count": total_questions - score,
        "percentage": percentage,
        "question_reviews": question_reviews,
        "incorrect_questions": incorrect_questions,
    }
