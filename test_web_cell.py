import sys
import unittest
from unittest import mock


class _RequestsStub:
    __spec__ = mock.MagicMock()

    def __init__(self):
        self.post = mock.MagicMock()


sys.modules.setdefault("requests", _RequestsStub())
sys.modules.setdefault("numpy", type("_NumpyStub", (), {"__spec__": mock.MagicMock()})())

from web_cell import SearchResult, WebSearchCell


class WebCellFallbackTest(unittest.TestCase):
    def test_ddg_missing_returns_reason(self):
        cell = WebSearchCell()
        cell.ddgs = None  # Имитация отсутствия duckduckgo-search

        result = cell.search_and_summarize("test запрос")

        self.assertIn("причина: ddg_unavailable", result.content)
        self.assertEqual(result.metadata.get("reason_code"), "ddg_unavailable")
        self.assertIn("reason_detail", result.metadata)


class WebCellSearchAndSummarizeTest(unittest.TestCase):
    def setUp(self):
        self.cell = WebSearchCell()

    def test_search_and_summarize_success(self):
        self.cell.ddgs = mock.MagicMock()
        self.cell.ddgs.text.return_value = [
            {"title": "t1", "href": "https://a", "body": "b1"},
            {"title": "t2", "href": "https://b", "body": "b2"},
        ]

        mock_response = mock.MagicMock()
        mock_response.json.return_value = {"response": "Готовый ответ"}

        with mock.patch("web_cell.REQUESTS_AVAILABLE", True), \
                mock.patch("web_cell.requests.post", return_value=mock_response):
            result = self.cell.search_and_summarize("python")

        self.assertEqual(result.content, "Готовый ответ")
        self.assertEqual(result.metadata.get("sources"), ["https://a", "https://b"])
        self.assertEqual(result.metadata.get("results_count"), 2)

    def test_search_and_summarize_requests_error(self):
        self.cell.search = mock.MagicMock(return_value=(
            [SearchResult(title="t", url="https://a", snippet="s")],
            {}
        ))

        with mock.patch("web_cell.REQUESTS_AVAILABLE", True), \
                mock.patch("web_cell.requests.post", side_effect=Exception("boom")):
            result = self.cell.search_and_summarize("python")

        self.assertEqual(result.metadata.get("reason_code"), "requests_error")
        self.assertIn("boom", result.metadata.get("reason_detail", ""))


class WebCellLearnTopicTest(unittest.TestCase):
    def setUp(self):
        self.cell = WebSearchCell()
        self.cell.search = mock.MagicMock(return_value=(
            [SearchResult(title="Title", url="https://a", snippet="Snippet")],
            {}
        ))

    def test_learn_topic_parses_json(self):
        response_payload = {"response": '{"facts": [{"text": "f1", "importance": 0.9}]}'}
        mock_response = mock.MagicMock()
        mock_response.json.return_value = response_payload

        with mock.patch("web_cell.REQUESTS_AVAILABLE", True), \
                mock.patch("web_cell.requests.post", return_value=mock_response):
            facts, reason = self.cell.learn_topic("Тест")

        self.assertEqual(reason, {})
        self.assertEqual(len(facts), 1)
        fact = facts[0]
        self.assertEqual(fact.get("text"), "f1")
        self.assertEqual(fact.get("source"), "web")
        self.assertEqual(fact.get("category"), "learned")
        self.assertEqual(fact.get("topic"), "Тест")

    def test_learn_topic_parse_error(self):
        mock_response = mock.MagicMock()
        mock_response.json.return_value = {"response": "not json"}

        with mock.patch("web_cell.REQUESTS_AVAILABLE", True), \
                mock.patch("web_cell.requests.post", return_value=mock_response):
            facts, reason = self.cell.learn_topic("Тест")

        self.assertEqual(facts, [])
        self.assertEqual(reason.get("reason_code"), "parse_error")
        self.assertTrue(reason.get("reason_detail"))


if __name__ == "__main__":
    unittest.main()
