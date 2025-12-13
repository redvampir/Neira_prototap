import unittest
from web_cell import WebSearchCell


class WebCellFallbackTest(unittest.TestCase):
    def test_ddg_missing_returns_reason(self):
        cell = WebSearchCell()
        cell.ddgs = None  # Имитация отсутствия duckduckgo-search

        result = cell.search_and_summarize("test запрос")

        self.assertIn("причина: ddg_unavailable", result.content)
        self.assertEqual(result.metadata.get("reason_code"), "ddg_unavailable")
        self.assertIn("reason_detail", result.metadata)


if __name__ == "__main__":
    unittest.main()
