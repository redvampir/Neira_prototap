import argparse
import sys
import unittest
from unittest import mock

from install_models import (
    DEFAULT_OLLAMA_API_URL,
    PERSONALITY_MODEL,
    REQUIRED_MODELS,
    ModelSpec,
    build_parser,
    ensure_ollama_cli,
    install_models,
    main,
    pull_model,
    select_models,
    warn_if_server_unavailable,
)


class EnsureOllamaCliTest(unittest.TestCase):
    def test_ollama_cli_found(self):
        with mock.patch("install_models.shutil.which", return_value="/usr/bin/ollama"):
            self.assertTrue(ensure_ollama_cli())

    def test_ollama_cli_not_found(self):
        with mock.patch("install_models.shutil.which", return_value=None), \
                mock.patch("builtins.print") as mock_print:
            self.assertFalse(ensure_ollama_cli())
            mock_print.assert_called_once()
            self.assertIn("не найдена", mock_print.call_args[0][0])


class WarnIfServerUnavailableTest(unittest.TestCase):
    def test_server_available_200(self):
        mock_resp = mock.MagicMock()
        mock_resp.status = 200
        mock_resp.__enter__ = mock.MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = mock.MagicMock(return_value=False)

        with mock.patch("install_models.urllib.request.urlopen", return_value=mock_resp), \
                mock.patch("builtins.print") as mock_print:
            warn_if_server_unavailable("http://localhost:11434/api/version")
            mock_print.assert_not_called()

    def test_server_non_200_status(self):
        mock_resp = mock.MagicMock()
        mock_resp.status = 500
        mock_resp.__enter__ = mock.MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = mock.MagicMock(return_value=False)

        with mock.patch("install_models.urllib.request.urlopen", return_value=mock_resp), \
                mock.patch("builtins.print") as mock_print:
            warn_if_server_unavailable("http://localhost:11434/api/version")
            mock_print.assert_called_once()
            self.assertIn("нестандартно", mock_print.call_args[0][0])

    def test_server_unavailable_url_error(self):
        import urllib.error
        with mock.patch(
            "install_models.urllib.request.urlopen",
            side_effect=urllib.error.URLError("Connection refused")
        ), mock.patch("builtins.print") as mock_print:
            warn_if_server_unavailable("http://localhost:11434/api/version")
            mock_print.assert_called_once()
            call_args = mock_print.call_args[0]
            self.assertIn("Не удалось подключиться", call_args[0])


class PullModelTest(unittest.TestCase):
    def test_pull_model_dry_run(self):
        model = ModelSpec(name="test-model", reason="тестовая модель")
        with mock.patch("builtins.print") as mock_print:
            result = pull_model(model, dry_run=True)
            self.assertTrue(result)
            mock_print.assert_called_once()
            self.assertIn("DRY-RUN", mock_print.call_args[0][0])

    def test_pull_model_success(self):
        model = ModelSpec(name="test-model", reason="тестовая модель")
        mock_result = mock.MagicMock()
        mock_result.returncode = 0

        with mock.patch("install_models.subprocess.run", return_value=mock_result), \
                mock.patch("builtins.print"):
            result = pull_model(model, dry_run=False)
            self.assertTrue(result)

    def test_pull_model_failure(self):
        model = ModelSpec(name="test-model", reason="тестовая модель")
        mock_result = mock.MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = "stdout output"
        mock_result.stderr = "stderr output"

        with mock.patch("install_models.subprocess.run", return_value=mock_result), \
                mock.patch("builtins.print") as mock_print:
            result = pull_model(model, dry_run=False)
            self.assertFalse(result)
            # Check that error message was printed
            print_calls = [str(call) for call in mock_print.call_args_list]
            error_printed = any("Не удалось скачать" in str(call) for call in print_calls)
            self.assertTrue(error_printed)

    def test_pull_model_command_not_found(self):
        model = ModelSpec(name="test-model", reason="тестовая модель")

        with mock.patch("install_models.subprocess.run", side_effect=FileNotFoundError), \
                mock.patch("builtins.print") as mock_print:
            result = pull_model(model, dry_run=False)
            self.assertFalse(result)
            # Check that error message was printed
            print_calls = [str(call) for call in mock_print.call_args_list]
            error_printed = any("не найдена" in str(call) for call in print_calls)
            self.assertTrue(error_printed)


class SelectModelsTest(unittest.TestCase):
    def test_select_default_models(self):
        args = argparse.Namespace(only=None, with_personality=False)
        models = select_models(args)
        self.assertEqual(len(models), len(REQUIRED_MODELS))
        self.assertEqual(models, REQUIRED_MODELS)

    def test_select_with_personality(self):
        args = argparse.Namespace(only=None, with_personality=True)
        models = select_models(args)
        self.assertEqual(len(models), len(REQUIRED_MODELS) + 1)
        self.assertIn(PERSONALITY_MODEL, models)

    def test_select_only_specific_models(self):
        args = argparse.Namespace(
            only=["qwen2.5-coder:7b", "mistral:7b-instruct"],
            with_personality=False
        )
        models = select_models(args)
        self.assertEqual(len(models), 2)
        self.assertEqual(models[0].name, "qwen2.5-coder:7b")
        self.assertEqual(models[1].name, "mistral:7b-instruct")

    def test_select_only_personality_model(self):
        args = argparse.Namespace(only=["neira-personality"], with_personality=False)
        models = select_models(args)
        self.assertEqual(len(models), 1)
        self.assertEqual(models[0], PERSONALITY_MODEL)


class BuildParserTest(unittest.TestCase):
    def test_parser_defaults(self):
        parser = build_parser()
        args = parser.parse_args([])
        self.assertFalse(args.with_personality)
        self.assertIsNone(args.only)
        self.assertFalse(args.dry_run)
        self.assertEqual(args.server_url, DEFAULT_OLLAMA_API_URL)

    def test_parser_with_personality_flag(self):
        parser = build_parser()
        args = parser.parse_args(["--with-personality"])
        self.assertTrue(args.with_personality)

    def test_parser_dry_run_flag(self):
        parser = build_parser()
        args = parser.parse_args(["--dry-run"])
        self.assertTrue(args.dry_run)

    def test_parser_only_flag(self):
        parser = build_parser()
        args = parser.parse_args(["--only", "qwen2.5-coder:7b", "mistral:7b-instruct"])
        self.assertEqual(args.only, ["qwen2.5-coder:7b", "mistral:7b-instruct"])

    def test_parser_server_url_flag(self):
        parser = build_parser()
        args = parser.parse_args(["--server-url", "http://example.com:11434/api/version"])
        self.assertEqual(args.server_url, "http://example.com:11434/api/version")


class InstallModelsTest(unittest.TestCase):
    def test_install_all_success(self):
        models = [
            ModelSpec(name="model1", reason="test"),
            ModelSpec(name="model2", reason="test"),
        ]

        with mock.patch("install_models.pull_model", return_value=True), \
                mock.patch("builtins.print") as mock_print:
            result = install_models(models, dry_run=False)
            self.assertEqual(result, 0)
            # Check success message was printed
            print_calls = [str(call) for call in mock_print.call_args_list]
            success_printed = any("Все выбранные модели" in str(call) for call in print_calls)
            self.assertTrue(success_printed)

    def test_install_partial_failure(self):
        models = [
            ModelSpec(name="model1", reason="test"),
            ModelSpec(name="model2", reason="test"),
        ]

        with mock.patch("install_models.pull_model", side_effect=[True, False]), \
                mock.patch("builtins.print") as mock_print:
            result = install_models(models, dry_run=False)
            self.assertEqual(result, 1)
            # Check failure message was printed
            print_calls = [str(call) for call in mock_print.call_args_list]
            failure_printed = any("Некоторые модели не удалось" in str(call) for call in print_calls)
            self.assertTrue(failure_printed)


class MainTest(unittest.TestCase):
    def test_main_empty_models(self):
        with mock.patch("install_models.select_models", return_value=[]), \
                mock.patch("builtins.print") as mock_print:
            result = main([])
            self.assertEqual(result, 0)
            mock_print.assert_called_once()
            self.assertIn("Нечего скачивать", mock_print.call_args[0][0])

    def test_main_dry_run(self):
        models = [ModelSpec(name="test-model", reason="test")]
        with mock.patch("install_models.select_models", return_value=models), \
                mock.patch("install_models.install_models", return_value=0) as mock_install, \
                mock.patch("install_models.ensure_ollama_cli") as mock_ensure, \
                mock.patch("install_models.warn_if_server_unavailable") as mock_warn:
            result = main(["--dry-run"])
            self.assertEqual(result, 0)
            mock_install.assert_called_once_with(models, dry_run=True)
            mock_ensure.assert_not_called()
            mock_warn.assert_not_called()

    def test_main_ollama_not_found(self):
        models = [ModelSpec(name="test-model", reason="test")]
        with mock.patch("install_models.select_models", return_value=models), \
                mock.patch("install_models.ensure_ollama_cli", return_value=False), \
                mock.patch("install_models.install_models") as mock_install:
            result = main([])
            self.assertEqual(result, 1)
            mock_install.assert_not_called()

    def test_main_success_with_server_check(self):
        models = [ModelSpec(name="test-model", reason="test")]
        with mock.patch("install_models.select_models", return_value=models), \
                mock.patch("install_models.ensure_ollama_cli", return_value=True), \
                mock.patch("install_models.warn_if_server_unavailable") as mock_warn, \
                mock.patch("install_models.install_models", return_value=0) as mock_install:
            result = main([])
            self.assertEqual(result, 0)
            mock_warn.assert_called_once_with(api_url=DEFAULT_OLLAMA_API_URL)
            mock_install.assert_called_once_with(models, dry_run=False)

    def test_main_custom_server_url(self):
        models = [ModelSpec(name="test-model", reason="test")]
        custom_url = "http://custom:11434/api/version"
        with mock.patch("install_models.select_models", return_value=models), \
                mock.patch("install_models.ensure_ollama_cli", return_value=True), \
                mock.patch("install_models.warn_if_server_unavailable") as mock_warn, \
                mock.patch("install_models.install_models", return_value=0):
            result = main(["--server-url", custom_url])
            self.assertEqual(result, 0)
            mock_warn.assert_called_once_with(api_url=custom_url)


if __name__ == "__main__":
    unittest.main()
