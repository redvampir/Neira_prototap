from __future__ import annotations

import argparse
import json
import logging
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from neira.config import TKP_OUTPUT_DIR, TKP_SAMPLES_DIR
from neira.organs.tkp.generator import (
    generate_tkp_document,
    _extract_catalog_info,
    _load_templates,
    _select_template,
)
from neira.organs.tkp.parser import _build_parsed_paths, load_or_parse_catalog

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TestResult:
    model_name: str
    output_path: Path
    catalog_path: Path
    template_id: str
    warnings: list[str]
    missing_values: int
    parameter_count: int
    tech_rows: int
    matched_rows: int


def _load_parsed_count(catalog_path: Path, model_name: str) -> int:
    json_path, _ = _build_parsed_paths(TKP_OUTPUT_DIR / "parsed", catalog_path, model_name)
    if not json_path.exists():
        return 0
    try:
        payload = json.loads(json_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return 0
    return len(payload.get("parameters", []))


def _run_case(model_name: str, force_parse: bool) -> TestResult:
    result = generate_tkp_document(model_name, force_parse=force_parse)
    warnings = list(result.warnings)
    parsed_param_count = _load_parsed_count(result.catalog_path, model_name)
    tech_rows: list = []
    matched_rows = 0
    template_id = result.template_id
    try:
        templates = _load_templates(TKP_SAMPLES_DIR)
        template = _select_template(templates, result.catalog_path, model_name)
        template_id = template.template_id
        parsed = load_or_parse_catalog(
            result.catalog_path,
            model_name,
            force_parse=False,
        ).parsed
        catalog_info = _extract_catalog_info(parsed=parsed, template=template)
        tech_rows = [row for row in template.tech_rows if not row.is_group]
        matched_rows = sum(1 for row in tech_rows if row.name in catalog_info.param_values)
    except (OSError, zipfile.BadZipFile, ValueError) as exc:
        warnings.append(f"template_load_failed: {exc}")
    return TestResult(
        model_name=model_name,
        output_path=result.output_path,
        catalog_path=result.catalog_path,
        template_id=template_id,
        warnings=warnings,
        missing_values=result.missing_values,
        parameter_count=parsed_param_count,
        tech_rows=len(tech_rows),
        matched_rows=matched_rows,
    )


def _write_report(results: list[TestResult]) -> Path:
    TKP_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    report_path = TKP_OUTPUT_DIR / f"tkp_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    lines = ["# TKP test report", ""]
    for item in results:
        coverage = (
            f"{item.matched_rows}/{item.tech_rows}"
            if item.tech_rows
            else "0/0"
        )
        lines.extend(
            [
                f"## Model: {item.model_name}",
                "",
                f"- output: {item.output_path}",
                f"- catalog: {item.catalog_path}",
                f"- template: {item.template_id}",
                f"- warnings: {', '.join(item.warnings) if item.warnings else 'none'}",
                f"- missing_values: {item.missing_values}",
                f"- parsed_parameters: {item.parameter_count}",
                f"- tech_coverage: {coverage}",
                "",
            ]
        )
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("models", nargs="*", default=["DVF 6500T", "DVF 8000", "DVF 8000T", "HT2"])
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    results = [_run_case(model, args.refresh) for model in args.models]
    report_path = _write_report(results)
    logger.info("Report: %s", report_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
