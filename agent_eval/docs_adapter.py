from time import perf_counter
from uuid import uuid4


def capture_docs(suite):
    if not isinstance(suite, dict) or not isinstance(suite.get("cases"), list):
        raise ValueError("The mock docs adapter requires a suite with cases")
    documents = suite.get("documents")
    if not isinstance(documents, dict) or not all(isinstance(text, str) for text in documents.values()):
        raise ValueError("The mock docs adapter requires a documents mapping")

    requests = []
    for case in suite["cases"]:
        request = case.get("capture") if isinstance(case, dict) else None
        if (not isinstance(request, dict) or not isinstance(request.get("document_id"), str)
                or not request["document_id"].strip() or type(request.get("simulate_timeout", False)) is not bool):
            raise ValueError("Each mock docs case needs a capture document_id and an optional simulate_timeout boolean")
        requests.append(request)
    return {**suite, "cases": [
        {**case, "run": run_docs(documents, request, case.get("prompt"))}
        for case, request in zip(suite["cases"], requests)
    ]}


def run_docs(documents, request, prompt):
    calls = []
    start = perf_counter()

    def lookup_doc(document_id):
        if request.get("simulate_timeout"):
            result = {"status": "timeout"}
        elif document_id not in documents:
            result = {"status": "missing"}
        else:
            result = {"status": "success", "text": documents[document_id]}
        calls.append({"tool": "lookup_doc", "arguments": {"id": document_id}, "result": result})
        return result

    found = lookup_doc(request["document_id"])
    if found["status"] == "success":
        answer = found["text"]
    elif found["status"] == "missing":
        answer = "The requested document was unavailable."
    else:
        answer = "The document lookup timed out."
    return {
        "id": str(uuid4()), "agent_version": "mock-docs-v1", "prompt": prompt, "final_response": answer,
        "tool_calls": calls, "stop_reason": found["status"],
        "telemetry": {"tool_calls": len(calls), "elapsed_ms": round((perf_counter() - start) * 1000),
                      "model_calls": 0, "retries": 0},
    }
