import io
import json
import os
import unittest
from unittest.mock import patch

from agent_eval.judge_providers import make_judge


class JudgeProviderTests(unittest.TestCase):
    def grade(self, provider, payload, environment):
        requests = []

        def request(url_request, timeout):
            requests.append(url_request)
            return io.BytesIO(json.dumps(payload).encode())

        with patch.dict(os.environ, environment, clear=True), patch("agent_eval.judge_providers.urlopen", request):
            judge = make_judge(provider, "test-model", "Grade the evidence.")
            result = judge({"final_response": "Found a record", "tool_calls": [{"tool": "lookup"}]})
        self.assertEqual(len(requests), 1)
        return requests[0], json.loads(requests[0].data), result

    def test_ollama_needs_no_key_and_normalizes_token_usage(self):
        request, body, result = self.grade("ollama", {
            "done": True, "done_reason": "stop", "message": {"content": '{"score": 0.8, "reason": "Supported"}'},
            "prompt_eval_count": 14, "eval_count": 5,
        }, {})
        self.assertEqual(request.full_url, "http://127.0.0.1:11434/api/chat")
        self.assertFalse(body["stream"])
        self.assertEqual(body["format"]["required"], ["score", "reason"])
        self.assertEqual(body["messages"][0]["content"], "Grade the evidence.")
        self.assertIsNone(request.get_header("Authorization"))
        self.assertEqual(result["usage"], {"input_tokens": 14, "output_tokens": 5})

    def test_anthropic_uses_messages_api_and_structured_grade(self):
        request, body, result = self.grade("anthropic", {
            "stop_reason": "end_turn", "content": [{"type": "text", "text": '{"score": 0.5, "reason": "Partial"}'}],
            "usage": {"input_tokens": 10, "output_tokens": 6},
        }, {"ANTHROPIC_API_KEY": "demo-key"})
        self.assertEqual(request.full_url, "https://api.anthropic.com/v1/messages")
        self.assertEqual(request.get_header("X-api-key"), "demo-key")
        self.assertEqual(body["system"], "Grade the evidence.")
        self.assertEqual(body["output_config"]["format"]["type"], "json_schema")
        self.assertEqual(result["score"], 0.5)
