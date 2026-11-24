def evaluate(expected, run):
    phrases = expected.get("answer_contains")
    answer = run.get("final_response")
    if not isinstance(phrases, list) or not phrases or not all(isinstance(phrase, str) and phrase.strip() for phrase in phrases):
        raise ValueError("answer_contains must list the required answer phrases")
    if not isinstance(answer, str):
        raise ValueError("A captured final response is required")
    normalized = answer.casefold()
    missing = [phrase for phrase in phrases if phrase.casefold() not in normalized]
    return {
        "status": "fail" if missing else "pass",
        "reason": "Response omitted expected phrases" if missing else "Response includes the expected phrases",
        "details": {"missing_phrases": missing},
    }
