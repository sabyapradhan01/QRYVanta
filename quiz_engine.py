"""Pure logic for QRYVANTA's offline quiz and exam-practice bank."""
from __future__ import annotations
import random
from copy import deepcopy

DIFFICULTIES = ("Easy", "Medium", "Hard")


def available_questions(bank, difficulty="All"):
    if difficulty == "All":
        return list(bank)
    return [item for item in bank if item.get("difficulty") == difficulty]


def build_attempt(bank, count, difficulty="All", rng=None):
    """Build a randomized attempt, with no repeated question IDs or options.

    Each item preserves its canonical answer string while independently
    shuffling question order and each question's option order.
    """
    rng = rng or random.SystemRandom()
    pool = available_questions(bank, difficulty)
    if not pool:
        raise ValueError("No questions are available for this difficulty.")
    if int(count) < 1 or int(count) > len(pool):
        raise ValueError(f"Choose between 1 and {len(pool)} questions for {difficulty}.")
    chosen = rng.sample(pool, k=int(count))
    attempt = []
    seen_ids = set()
    for original in chosen:
        question = deepcopy(original)
        qid = question.get("id")
        if qid in seen_ids:
            raise ValueError(f"Duplicate question ID in bank: {qid}")
        seen_ids.add(qid)
        options = list(question["options"])
        if len(options) < 2 or question["answer"] not in options:
            raise ValueError(f"Invalid answer/options for question {qid}.")
        if len(options) != len(set(options)):
            raise ValueError(f"Repeated option text for question {qid}.")
        rng.shuffle(options)
        question["options"] = options
        question["attempt_number"] = len(attempt) + 1
        attempt.append(question)
    return attempt


def validate_answer(question, selected_answer):
    """Return (is_correct, exact_feedback, explanation)."""
    if selected_answer is not None and selected_answer == question.get("answer"):
        return True, "Yes, you have correctly answered the question.", question.get("explanation", "")
    return False, "Yet to answer correctly.", question.get("explanation", "")


def summarize_attempt(questions, responses):
    """Summarize responses keyed by question ID; unanswered are incorrect."""
    total = len(questions)
    correct = 0
    attempted = 0
    by_topic = {}
    for q in questions:
        selected = responses.get(q["id"])
        is_correct = selected == q.get("answer") and selected is not None
        if selected is not None:
            attempted += 1
        if is_correct:
            correct += 1
        topic = q.get("topic", "General")
        slot = by_topic.setdefault(topic, {"correct": 0, "total": 0})
        slot["total"] += 1
        slot["correct"] += int(is_correct)
    return {
        "total": total,
        "attempted": attempted,
        "correct": correct,
        "incorrect_or_unanswered": total - correct,
        "percentage": round((correct / total) * 100, 1) if total else 0.0,
        "by_topic": by_topic,
    }
