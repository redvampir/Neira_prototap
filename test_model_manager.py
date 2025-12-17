import unittest
from unittest import mock

import requests

from model_manager import ModelManager


class _FakeResponse:
    def __init__(self, status_code=200, json_data=None, text="", headers=None, json_error=None):
        self.status_code = status_code
        self._json_data = json_data or {}
        self.text = text
        self.headers = headers or {}
        self._json_error = json_error

    def json(self):
        if self._json_error:
            raise self._json_error
        return self._json_data


class ModelManagerGetLoadedModelsTest(unittest.TestCase):
    @mock.patch("model_manager.requests.get")
    def test_get_loaded_models_success(self, mock_get):
        mock_get.side_effect = [
            _FakeResponse(json_data={"models": []}),
            _FakeResponse(json_data={"models": [{"name": "m1"}, {"name": "m2"}]}),
        ]

        manager = ModelManager(verbose=False)
        manager.log = mock.MagicMock()

        loaded = manager.get_loaded_models()

        self.assertEqual(loaded, ["m1", "m2"])
        self.assertEqual(manager.last_loaded_models, ["m1", "m2"])
        manager.log.assert_not_called()

    @mock.patch("model_manager.requests.get")
    def test_get_loaded_models_server_error_keeps_previous(self, mock_get):
        mock_get.side_effect = [
            _FakeResponse(json_data={"models": []}),
            _FakeResponse(json_data={"models": [{"name": "ok"}]}),
            _FakeResponse(status_code=500, text="<html>error</html>"),
        ]

        manager = ModelManager(verbose=False)
        manager.log = mock.MagicMock()

        initial = manager.get_loaded_models()
        manager.log.reset_mock()
        fallback = manager.get_loaded_models()

        self.assertEqual(initial, ["ok"])
        self.assertEqual(fallback, ["ok"])
        self.assertEqual(manager.last_loaded_models, ["ok"])
        manager.log.assert_called_once()
        log_message = manager.log.call_args[0][0]
        self.assertIn("500", log_message)
        self.assertIn("error", log_message)

    @mock.patch("model_manager.requests.get")
    def test_get_loaded_models_invalid_json(self, mock_get):
        mock_get.side_effect = [
            _FakeResponse(json_data={"models": []}),
            _FakeResponse(json_data={"models": [{"name": "ok"}]}),
            _FakeResponse(status_code=200, text="<html>oops", json_error=ValueError("not json")),
        ]

        manager = ModelManager(verbose=False)
        manager.log = mock.MagicMock()

        manager.get_loaded_models()
        manager.log.reset_mock()
        fallback = manager.get_loaded_models()

        self.assertEqual(fallback, ["ok"])
        self.assertEqual(manager.last_loaded_models, ["ok"])
        manager.log.assert_called_once()
        self.assertIn("Ошибка разбора JSON", manager.log.call_args[0][0])

    @mock.patch("model_manager.requests.get")
    def test_get_loaded_models_network_error_uses_cache(self, mock_get):
        mock_get.side_effect = [
            _FakeResponse(json_data={"models": []}),
            _FakeResponse(json_data={"models": [{"name": "ok"}]}),
            requests.RequestException("timeout"),
        ]

        manager = ModelManager(verbose=False)
        manager.log = mock.MagicMock()

        manager.get_loaded_models()
        manager.log.reset_mock()
        fallback = manager.get_loaded_models()

        self.assertEqual(fallback, ["ok"])
        manager.log.assert_called_once()
        self.assertIn("Сетевая ошибка", manager.log.call_args[0][0])

    @mock.patch("model_manager.requests.get")
    def test_get_loaded_models_ignores_invalid_entries(self, mock_get):
        mock_get.side_effect = [
            _FakeResponse(json_data={"models": []}),
            _FakeResponse(json_data={"models": [
                {"name": "alpha"},
                {"name": ""},
                {"name": None},
                "broken",
                {"not_name": "beta"},
            ]}),
        ]

        manager = ModelManager(verbose=False)

        loaded = manager.get_loaded_models()

        self.assertEqual(loaded, ["alpha"])


if __name__ == "__main__":
    unittest.main()
