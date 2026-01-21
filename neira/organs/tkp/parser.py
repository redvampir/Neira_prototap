"""
Цель: Конвертация PDF каталогов в JSON/MD для ТКП.
Инварианты: Сохраняем источники (страницы/строки), не выдумываем значения.
Риски: PDF шумит, таблицы распознаются неполно.
Проверка: python -m py_compile neira/organs/tkp/parser.py
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Sequence

from neira.config import (
    TKP_LIST_LIMIT,
    TKP_PARSED_DIR,
    TKP_PARSED_SCHEMA_VERSION,
    TKP_PARSE_FALLBACK_PAGES,
    TKP_PARSE_PAGE_WINDOW,
    TKP_SNIPPET_CHARS,
    TKP_VALUE_WINDOW_CHARS,
)

logger = logging.getLogger(__name__)

_UNIT_TOKENS = (
    "mm",
    "mm/min",
    "m/min",
    "kg",
    "kw",
    "kva",
    "nm",
    "rpm",
    "r/min",
    "bar",
    "hz",
    "v",
    "a",
    "s",
    "°",
    "l/min",
    "l",
    "db",
)
_NUMERIC_PATTERN = re.compile(r"[-+]?\\d[\\d\\s.,/x×-]*\\d|[-+]?\\d")


@dataclass(frozen=True)
class ParsedParameter:
    name: str
    value: str
    unit: str | None
    source_page: int | None
    source_text: str | None

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "value": self.value,
            "unit": self.unit,
            "source_page": self.source_page,
            "source_text": self.source_text,
        }


@dataclass(frozen=True)
class ParsedListItem:
    text: str
    source_page: int | None
    source_text: str | None

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "source_page": self.source_page,
            "source_text": self.source_text,
        }


@dataclass(frozen=True)
class ParsedCatalog:
    model_name: str
    catalog_path: str
    extracted_at: str
    schema_version: str
    pages_used: list[int]
    snippet: str | None
    main_units: list[str]
    standard_items: list[str]
    option_items: list[str]
    main_units_sources: list[ParsedListItem]
    standard_items_sources: list[ParsedListItem]
    option_items_sources: list[ParsedListItem]
    parameters: list[ParsedParameter]
    warnings: list[str]

    def to_dict(self) -> dict:
        return {
            "model_name": self.model_name,
            "catalog_path": self.catalog_path,
            "extracted_at": self.extracted_at,
            "schema_version": self.schema_version,
            "pages_used": self.pages_used,
            "snippet": self.snippet,
            "main_units": self.main_units,
            "standard_items": self.standard_items,
            "option_items": self.option_items,
            "main_units_sources": [item.to_dict() for item in self.main_units_sources],
            "standard_items_sources": [item.to_dict() for item in self.standard_items_sources],
            "option_items_sources": [item.to_dict() for item in self.option_items_sources],
            "parameters": [param.to_dict() for param in self.parameters],
            "warnings": self.warnings,
        }


@dataclass(frozen=True)
class ParsedCatalogResult:
    parsed: ParsedCatalog
    json_path: Path
    md_path: Path
    warnings: list[str]


@dataclass(frozen=True)
class PageContent:
    index: int
    text: str
    tables: list[list[list[str]]]


def load_or_parse_catalog(
    catalog_path: Path,
    model_name: str,
    output_dir: Path | None = None,
    force_parse: bool = False,
) -> ParsedCatalogResult:
    """
    Получить parsed-данные из кэша или пересоздать.
    """
    output_dir = output_dir or TKP_PARSED_DIR
    json_path, md_path = _build_parsed_paths(output_dir, catalog_path, model_name)
    warnings: list[str] = []

    if not force_parse:
        loaded = _load_parsed_catalog(json_path, catalog_path)
        if loaded:
            return ParsedCatalogResult(loaded, json_path, md_path, loaded.warnings)

    parsed = parse_catalog_to_files(catalog_path, model_name, json_path, md_path)
    warnings.extend(parsed.warnings)
    return ParsedCatalogResult(parsed, json_path, md_path, warnings)


def parse_catalog_to_files(
    catalog_path: Path,
    model_name: str,
    json_path: Path,
    md_path: Path,
) -> ParsedCatalog:
    """
    Извлечь данные из PDF и сохранить JSON/MD.
    """
    pages, warnings = _extract_pages(catalog_path)
    selected_pages, page_warnings = _select_pages_for_model(pages, model_name)
    warnings.extend(page_warnings)

    content = _parse_catalog_content(selected_pages, model_name)

    parsed = ParsedCatalog(
        model_name=model_name,
        catalog_path=str(catalog_path),
        extracted_at=datetime.now().isoformat(),
        schema_version=TKP_PARSED_SCHEMA_VERSION,
        pages_used=[page.index for page in selected_pages],
        snippet=content["snippet"],
        main_units=content["main_units"],
        standard_items=content["standard_items"],
        option_items=content["option_items"],
        main_units_sources=content["main_units_sources"],
        standard_items_sources=content["standard_sources"],
        option_items_sources=content["option_sources"],
        parameters=content["parameters"],
        warnings=warnings,
    )

    _write_json(parsed, json_path)
    _write_md(parsed, md_path)
    return parsed


def _parse_catalog_content(
    pages: Sequence[PageContent],
    model_name: str,
) -> dict[str, object]:
    combined_text = "\n".join(page.text for page in pages)
    lines = _collect_lines(combined_text)
    snippet = _extract_snippet(combined_text, model_name)

    main_units = _extract_main_units(lines)
    main_units_sources = _extract_lines_with_sources(
        pages,
        (
            "шпиндел",
            "револьвер",
            "патрон",
            "ось",
            "стол",
            "направляющ",
            "привод",
            "двигател",
            "система чпу",
            "spindle",
            "turret",
            "chuck",
            "axis",
            "table",
        ),
        TKP_LIST_LIMIT,
    )
    standard_sources = _extract_items_with_sources(
        pages, ("стандарт", "standard", "комплектац")
    )
    option_sources = _extract_items_with_sources(
        pages, ("опци", "optional", "option")
    )
    if main_units_sources:
        main_units = [item.text for item in main_units_sources]
    standard_items = [item.text for item in standard_sources]
    option_items = [item.text for item in option_sources]
    parameters = _extract_parameters(pages, model_name)

    return {
        "snippet": snippet,
        "main_units": main_units,
        "standard_items": standard_items,
        "option_items": option_items,
        "main_units_sources": main_units_sources,
        "standard_sources": standard_sources,
        "option_sources": option_sources,
        "parameters": parameters,
    }


def _build_parsed_paths(
    output_dir: Path,
    catalog_path: Path,
    model_name: str,
) -> tuple[Path, Path]:
    safe_model = _safe_name(model_name)
    catalog_dir = output_dir / _safe_name(catalog_path.stem)
    catalog_dir.mkdir(parents=True, exist_ok=True)
    json_path = catalog_dir / f"{safe_model}.json"
    md_path = catalog_dir / f"{safe_model}.md"
    return json_path, md_path


def _load_parsed_catalog(
    json_path: Path,
    catalog_path: Path,
) -> ParsedCatalog | None:
    if not json_path.exists():
        return None
    try:
        raw = json.loads(json_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if raw.get("schema_version") != TKP_PARSED_SCHEMA_VERSION:
        return None
    if raw.get("catalog_path") != str(catalog_path):
        return None
    return _catalog_from_dict(raw)


def _catalog_from_dict(payload: dict) -> ParsedCatalog:
    def _parse_list_items(items) -> list[ParsedListItem]:
        parsed_items: list[ParsedListItem] = []
        for item in items or []:
            if isinstance(item, dict):
                parsed_items.append(
                    ParsedListItem(
                        text=item.get("text", ""),
                        source_page=item.get("source_page"),
                        source_text=item.get("source_text"),
                    )
                )
            else:
                parsed_items.append(ParsedListItem(text=str(item), source_page=None, source_text=None))
        return parsed_items

    params = [
        ParsedParameter(
            name=item.get("name", ""),
            value=item.get("value", ""),
            unit=item.get("unit"),
            source_page=item.get("source_page"),
            source_text=item.get("source_text"),
        )
        for item in payload.get("parameters", [])
        if isinstance(item, dict)
    ]
    return ParsedCatalog(
        model_name=payload.get("model_name", ""),
        catalog_path=payload.get("catalog_path", ""),
        extracted_at=payload.get("extracted_at", ""),
        schema_version=payload.get("schema_version", ""),
        pages_used=list(payload.get("pages_used", [])),
        snippet=payload.get("snippet"),
        main_units=list(payload.get("main_units", [])),
        standard_items=list(payload.get("standard_items", [])),
        option_items=list(payload.get("option_items", [])),
        main_units_sources=_parse_list_items(payload.get("main_units_sources")),
        standard_items_sources=_parse_list_items(payload.get("standard_items_sources")),
        option_items_sources=_parse_list_items(payload.get("option_items_sources")),
        parameters=params,
        warnings=list(payload.get("warnings", [])),
    )


def _extract_pages(catalog_path: Path) -> tuple[list[PageContent], list[str]]:
    warnings: list[str] = []
    pages = _extract_pages_with_pdfplumber(catalog_path)
    if pages:
        return pages, warnings

    pages = _extract_pages_with_pypdf(catalog_path)
    warnings.append("pdfplumber недоступен, качество извлечения ниже.")
    return pages, warnings


def _extract_pages_with_pdfplumber(catalog_path: Path) -> list[PageContent]:
    try:
        import pdfplumber
    except ImportError:
        return []

    pages: list[PageContent] = []
    with pdfplumber.open(str(catalog_path)) as pdf:
        for idx, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            tables = page.extract_tables() or []
            pages.append(PageContent(idx, text, tables))
    return pages


def _extract_pages_with_pypdf(catalog_path: Path) -> list[PageContent]:
    try:
        import pypdf
    except ImportError as exc:
        raise RuntimeError("Для PDF нужен pypdf.") from exc

    pages: list[PageContent] = []
    reader = pypdf.PdfReader(str(catalog_path))
    for idx, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        pages.append(PageContent(idx, text, []))
    return pages


def _select_pages_for_model(
    pages: Sequence[PageContent],
    model_name: str,
) -> tuple[list[PageContent], list[str]]:
    warnings: list[str] = []
    normalized_model = _normalize_text(model_name)
    matched = [page for page in pages if normalized_model in _normalize_text(page.text)]

    if not matched:
        warnings.append("Модель не найдена на страницах каталога.")
        return list(pages[:TKP_PARSE_FALLBACK_PAGES]), warnings

    selected_indexes = _expand_page_window([page.index for page in matched])
    selected = [page for page in pages if page.index in selected_indexes]
    return selected, warnings


def _expand_page_window(indexes: Sequence[int]) -> set[int]:
    selected: set[int] = set()
    for index in indexes:
        for offset in range(-TKP_PARSE_PAGE_WINDOW, TKP_PARSE_PAGE_WINDOW + 1):
            selected.add(index + offset)
    return {idx for idx in selected if idx > 0}


def _collect_lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def _extract_snippet(text: str, model_name: str) -> str | None:
    lowered = text.lower()
    idx = lowered.find(model_name.lower())
    if idx == -1:
        return None
    start = max(0, idx - TKP_SNIPPET_CHARS // 3)
    end = min(len(text), idx + TKP_SNIPPET_CHARS)
    snippet = " ".join(text[start:end].split())
    sentences = re.split(r"(?<=[.!?])\\s+", snippet)
    selected = [s.strip() for s in sentences if s.strip()][:2]
    return " ".join(selected) if selected else snippet


def _extract_main_units(lines: Sequence[str]) -> list[str]:
    keywords = (
        "шпиндел",
        "револьвер",
        "патрон",
        "ось",
        "стол",
        "направляющ",
        "привод",
        "двигател",
        "система чпу",
        "spindle",
        "turret",
        "chuck",
        "axis",
        "table",
    )
    return _extract_lines_by_keywords(lines, keywords, TKP_LIST_LIMIT)


def _extract_items_with_sources(
    pages: Sequence[PageContent],
    keywords: Sequence[str],
) -> list[ParsedListItem]:
    items: list[ParsedListItem] = []
    seen: set[str] = set()
    for page in pages:
        for line in _collect_lines(page.text):
            lowered = line.lower()
            if not any(keyword in lowered for keyword in keywords):
                continue
            for item in _split_line_items(line):
                normalized = item.lower()
                if normalized in seen:
                    continue
                seen.add(normalized)
                items.append(
                    ParsedListItem(
                        text=item,
                        source_page=page.index,
                        source_text=line,
                    )
                )
                if len(items) >= TKP_LIST_LIMIT:
                    return items
    return items


def _extract_lines_by_keywords(
    lines: Sequence[str],
    keywords: Sequence[str],
    limit: int,
) -> list[str]:
    matched: list[str] = []
    seen: set[str] = set()
    for line in lines:
        lowered = line.lower()
        if not any(keyword in lowered for keyword in keywords):
            continue
        normalized = lowered.strip()
        if normalized in seen:
            continue
        seen.add(normalized)
        matched.append(line)
        if len(matched) >= limit:
            break
    return matched


def _extract_lines_with_sources(
    pages: Sequence[PageContent],
    keywords: Sequence[str],
    limit: int,
) -> list[ParsedListItem]:
    matched: list[ParsedListItem] = []
    seen: set[str] = set()
    for page in pages:
        for line in _collect_lines(page.text):
            lowered = line.lower()
            if not any(keyword in lowered for keyword in keywords):
                continue
            normalized = lowered.strip()
            if normalized in seen:
                continue
            seen.add(normalized)
            matched.append(
                ParsedListItem(
                    text=line,
                    source_page=page.index,
                    source_text=line,
                )
            )
            if len(matched) >= limit:
                return matched
    return matched


def _split_line_items(line: str) -> list[str]:
    if ":" in line:
        line = line.split(":", 1)[1]
    chunks = re.split(r"[;•·\\u2022]", line)
    items: list[str] = []
    for chunk in chunks:
        part = chunk.strip(" -\t")
        if part:
            items.append(part)
    return items or [line.strip()]


def _extract_parameters(
    pages: Sequence[PageContent],
    model_name: str,
) -> list[ParsedParameter]:
    parameters = []
    parameters.extend(_extract_parameters_from_tables(pages, model_name))
    parameters.extend(_extract_parameters_from_lines(pages, model_name))
    return _dedupe_parameters(parameters)


def _extract_parameters_from_tables(
    pages: Sequence[PageContent],
    model_name: str,
) -> list[ParsedParameter]:
    parameters: list[ParsedParameter] = []
    for page in pages:
        for table in page.tables:
            model_params = _parse_table_with_model(
                table,
                page.index,
                model_name,
            )
            if model_params:
                parameters.extend(model_params)
                continue
            for row in table:
                param = _parse_table_row(row, page.index, model_name)
                if param:
                    parameters.append(param)
    return parameters


def _parse_table_row(
    row: Sequence[str],
    page_index: int,
    model_name: str,
) -> ParsedParameter | None:
    cells = [_clean_cell(cell) for cell in row if cell and cell.strip()]
    if len(cells) < 2:
        return None

    if _is_header_row(cells):
        return None
    param_cell = _choose_param_cell(cells)
    value_cell = _choose_value_cell(cells, model_name, param_cell)
    if not param_cell or not value_cell:
        return None

    unit = _extract_unit(cells)
    return ParsedParameter(
        name=param_cell,
        value=value_cell,
        unit=unit,
        source_page=page_index,
        source_text=" | ".join(cells)[:TKP_VALUE_WINDOW_CHARS],
    )


def _choose_param_cell(cells: Sequence[str]) -> str | None:
    candidates = []
    for cell in cells:
        if _has_digits(cell):
            continue
        letters = _count_letters(cell)
        if letters:
            candidates.append((letters, cell))
    if not candidates:
        return None
    return max(candidates, key=lambda item: item[0])[1]


def _choose_value_cell(
    cells: Sequence[str],
    model_name: str,
    param_cell: str | None,
) -> str | None:
    candidates = [
        cell for cell in cells if _has_digits(cell) and cell != param_cell
    ]
    model_lower = model_name.lower()
    for cell in candidates:
        if model_lower in cell.lower():
            trimmed = _trim_after_model(cell, model_name)
            if trimmed:
                return trimmed
    if candidates:
        return max(candidates, key=len)

    fallback = [
        cell
        for cell in cells
        if cell != param_cell and _has_letters(cell)
    ]
    if fallback:
        return max(fallback, key=len)
    return None


def _extract_unit(cells: Sequence[str]) -> str | None:
    for cell in cells:
        lowered = cell.lower()
        for token in _UNIT_TOKENS:
            if token in lowered:
                return token
    return None


def _is_header_row(cells: Sequence[str]) -> bool:
    header = " ".join(cell.lower() for cell in cells if cell)
    return "парамет" in header or "parameter" in header or "ед." in header or "unit" in header


def _extract_parameters_from_lines(
    pages: Sequence[PageContent],
    model_name: str,
) -> list[ParsedParameter]:
    parameters: list[ParsedParameter] = []
    for page in pages:
        for line in _collect_lines(page.text):
            param = _parse_line(line, page.index, model_name)
            if param:
                parameters.append(param)
    return parameters


def _parse_line(
    line: str,
    page_index: int,
    model_name: str,
) -> ParsedParameter | None:
    if not _has_digits(line):
        return None
    unit = _extract_unit([line])
    if unit is None:
        return None
    value = _extract_value_from_line(line, model_name)
    if not value:
        return None
    name = _extract_name_from_line(line)
    if not name:
        return None
    return ParsedParameter(
        name=name,
        value=value,
        unit=unit,
        source_page=page_index,
        source_text=line[:TKP_VALUE_WINDOW_CHARS],
    )


def _extract_value_from_line(line: str, model_name: str) -> str | None:
    if model_name.lower() in line.lower():
        trimmed = _trim_after_model(line, model_name)
        match = _NUMERIC_PATTERN.search(trimmed or "")
        if match:
            return match.group(0).strip()
    match = _NUMERIC_PATTERN.search(line)
    return match.group(0).strip() if match else None


def _extract_name_from_line(line: str) -> str | None:
    parts = re.split(r"\\d", line, maxsplit=1)
    name = parts[0].strip(" :-")
    return name if len(name) > 2 else None


def _trim_after_model(text: str, model_name: str) -> str | None:
    idx = text.lower().find(model_name.lower())
    if idx == -1:
        return None
    return text[idx + len(model_name) :].strip()


def _dedupe_parameters(parameters: Sequence[ParsedParameter]) -> list[ParsedParameter]:
    indexed: dict[str, ParsedParameter] = {}
    for param in parameters:
        key = _normalize_text(param.name)
        if not key:
            continue
        existing = indexed.get(key)
        if existing is None or len(param.value) > len(existing.value):
            indexed[key] = param
    return list(indexed.values())


def _parse_table_with_model(
    table: Sequence[Sequence[str]],
    page_index: int,
    model_name: str,
) -> list[ParsedParameter]:
    model_column, header_index = _find_model_column(table, model_name)
    if model_column is None:
        return []

    unit_column = _find_unit_column(table, header_index)
    fallback_columns = _find_fallback_columns(table, header_index, model_name)
    parameters: list[ParsedParameter] = []
    context = _init_context(unit_column)

    for row in table[header_index + 1 :]:
        cells = [_clean_cell(cell) for cell in row if cell and str(cell).strip()]
        if not cells:
            continue
        if _is_header_row(cells):
            continue
        if len(row) <= model_column:
            continue
        value_cell = _clean_cell(row[model_column])
        if _is_missing_value(value_cell):
            value_cell = _first_fallback_value(row, fallback_columns)
        if _is_missing_value(value_cell):
            continue
        if unit_column is not None:
            context = _update_context(context, row, unit_column)
            param_cell = _build_param_name_from_context(context)
        else:
            param_cell = _pick_param_before_index(row, model_column)
        if not param_cell:
            continue
        unit = None
        if unit_column is not None and len(row) > unit_column:
            unit = _clean_cell(row[unit_column])
        if not unit:
            unit = _extract_unit([value_cell])
        parameters.append(
            ParsedParameter(
                name=param_cell,
                value=_extract_value_from_line(value_cell, model_name) or value_cell,
                unit=unit,
                source_page=page_index,
                source_text=" | ".join(_clean_cell(cell) for cell in row)[:TKP_VALUE_WINDOW_CHARS],
            )
        )
    return parameters


def _find_model_column(
    table: Sequence[Sequence[str]],
    model_name: str,
) -> tuple[int | None, int]:
    normalized_model = _normalize_text(model_name)
    header_index = 0
    best_index = None
    for idx, row in enumerate(table):
        cells = [_clean_cell(cell) for cell in row if cell and cell.strip()]
        if not cells:
            continue
        if any(normalized_model in _normalize_text(cell) for cell in cells):
            best_index = next(
                (
                    i
                    for i, cell in enumerate(row)
                    if normalized_model in _normalize_text(cell)
                ),
                None,
            )
            header_index = idx
            if _is_header_row(cells) or _row_has_models(cells):
                return best_index, header_index
    return best_index, header_index


def _row_has_models(cells: Sequence[str]) -> bool:
    hits = 0
    for cell in cells:
        if re.search(r"[A-Za-z]{1,4}\\s?\\d{2,4}", cell):
            hits += 1
    return hits >= 2


def _find_unit_column(
    table: Sequence[Sequence[str]],
    header_index: int,
) -> int | None:
    if header_index < 0 or header_index >= len(table):
        return None
    row = table[header_index]
    for idx, cell in enumerate(row):
        lowered = (cell or "").lower()
        if "ед" in lowered or "unit" in lowered:
            return idx
    return None


def _model_fallback_candidates(model_name: str) -> list[str]:
    normalized = re.sub(r"\s+", " ", model_name).strip()
    if not normalized:
        return []
    base = re.sub(r"([0-9])T(\\b|/)", r"\\1\\2", normalized)
    if base != normalized:
        return [base.strip()]
    return []


def _find_fallback_columns(
    table: Sequence[Sequence[str]],
    header_index: int,
    model_name: str,
) -> list[int]:
    if header_index < 0 or header_index >= len(table):
        return []
    header_row = table[header_index]
    fallback_candidates = _model_fallback_candidates(model_name)
    if not fallback_candidates:
        return []
    indices: list[int] = []
    seen: set[int] = set()
    for candidate in fallback_candidates:
        normalized_candidate = _normalize_text(candidate)
        if not normalized_candidate:
            continue
        for idx, cell in enumerate(header_row):
            if idx in seen:
                continue
            if normalized_candidate in _normalize_text(cell):
                indices.append(idx)
                seen.add(idx)
    return indices


def _is_missing_value(value: str) -> bool:
    if not value:
        return True
    normalized = value.strip().lower()
    return normalized in {"-", "—", "–", "n/a", "na"}


def _first_fallback_value(
    row: Sequence[str],
    fallback_columns: Sequence[int],
) -> str:
    for idx in fallback_columns:
        if idx >= len(row):
            continue
        cell = _clean_cell(row[idx])
        if not _is_missing_value(cell):
            return cell
    return ""


def _pick_param_before_index(
    row: Sequence[str],
    index: int,
) -> str | None:
    fallback: str | None = None
    for idx in range(min(index - 1, len(row) - 1), -1, -1):
        cell = _clean_cell(row[idx])
        if not cell or not _has_letters(cell):
            continue
        if not _has_digits(cell):
            return cell
        if fallback is None:
            fallback = cell
    return fallback


def _init_context(unit_column: int | None) -> list[str]:
    if unit_column is None:
        return []
    return ["" for _ in range(unit_column)]


def _update_context(
    context: list[str],
    row: Sequence[str],
    unit_column: int,
) -> list[str]:
    if unit_column <= 0:
        return context
    updated = list(context)
    highest = _highest_non_empty_index(row, unit_column)
    for idx in range(unit_column):
        cell = _clean_cell(row[idx]) if idx < len(row) else ""
        if cell:
            updated[idx] = cell
        elif highest is not None and idx > highest:
            updated[idx] = ""
    return updated


def _highest_non_empty_index(row: Sequence[str], limit: int) -> int | None:
    highest = None
    for idx in range(min(limit, len(row))):
        cell = _clean_cell(row[idx])
        if cell:
            highest = idx
    return highest


def _build_param_name_from_context(context: Sequence[str]) -> str | None:
    parts = [part for part in context if part]
    if not parts:
        return None
    return " ".join(parts)


def _clean_cell(cell: str) -> str:
    if not cell:
        return ""
    return " ".join(str(cell).replace("\n", " ").split())


def _normalize_text(text: str) -> str:
    if not text:
        return ""
    return re.sub(r"[^a-z0-9а-яё]+", "", str(text).lower())


def _safe_name(text: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "_", text).strip("_")
    return cleaned or "model"


def _count_letters(text: str) -> int:
    return sum(ch.isalpha() for ch in text)


def _has_letters(text: str) -> bool:
    return any(ch.isalpha() for ch in text)


def _has_digits(text: str) -> bool:
    return any(ch.isdigit() for ch in text)


def _write_json(parsed: ParsedCatalog, path: Path) -> None:
    data = parsed.to_dict()
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_md(parsed: ParsedCatalog, path: Path) -> None:
    lines: list[str] = []
    lines.append(f"# ТКП парсинг: {parsed.model_name}")
    lines.append("")
    lines.append(f"- Каталог: {parsed.catalog_path}")
    lines.append(f"- Страницы: {', '.join(str(i) for i in parsed.pages_used)}")
    if parsed.snippet:
        lines.append("")
        lines.append("## Сниппет")
        lines.append(parsed.snippet)
    lines.append("")
    lines.append("## Основные узлы")
    lines.extend(_render_list_with_sources(parsed.main_units_sources))
    lines.append("")
    lines.append("## Стандартная комплектация")
    lines.extend(_render_list_with_sources(parsed.standard_items_sources))
    lines.append("")
    lines.append("## Опции")
    lines.extend(_render_list_with_sources(parsed.option_items_sources))
    lines.append("")
    lines.append("## Параметры")
    lines.append("| Параметр | Значение | Ед. изм. | Стр. | Источник |")
    lines.append("| --- | --- | --- | --- | --- |")
    for param in parsed.parameters:
        lines.append(
            "| "
            + " | ".join(
                [
                    param.name or "-",
                    param.value or "-",
                    param.unit or "-",
                    str(param.source_page or "-"),
                    (param.source_text or "-").replace("|", "/"),
                ]
            )
            + " |"
        )
    path.write_text("\n".join(lines), encoding="utf-8")


def _render_list(items: Sequence[str]) -> list[str]:
    if not items:
        return ["- (нет данных)"]
    return [f"- {item}" for item in items]


def _render_list_with_sources(items: Sequence[ParsedListItem]) -> list[str]:
    if not items:
        return ["- (нет данных)"]
    lines = []
    for item in items:
        page = f"стр. {item.source_page}" if item.source_page else "стр. ?"
        lines.append(f"- {item.text} ({page})")
    return lines
