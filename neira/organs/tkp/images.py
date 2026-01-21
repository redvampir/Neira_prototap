"""
Цель: Извлечение изображений из PDF для вставки в ТКП.
Инварианты: Безопасные пути, не более лимита изображений.
Проверка: python -m py_compile neira/organs/tkp/images.py
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from neira.config import (
    TKP_IMAGE_DPI,
    TKP_IMAGE_MAX_COUNT,
    TKP_IMAGE_MODEL_PAGE_BONUS,
    TKP_IMAGE_MODEL_PAGE_WINDOW,
    TKP_IMAGE_DIGIT_RATIO_PENALTY,
    TKP_IMAGE_DIGIT_RATIO_THRESHOLD,
    TKP_IMAGE_DIGIT_WEIGHT,
    TKP_IMAGE_LETTER_WEIGHT,
    TKP_IMAGE_LENGTH_WEIGHT,
    TKP_IMAGE_OCR_DPI,
    TKP_IMAGE_OCR_MAX_PAGES,
    TKP_IMAGE_OCR_TIMEOUT_SECONDS,
    TKP_IMAGE_OCR_CROP_RATIO,
    TKP_IMAGE_RENDER_TIMEOUT_SECONDS,
    TKP_IMAGE_TEXT_KEYWORD_PENALTY,
    TKP_IMAGES_DIR,
    TKP_OCR_LANG,
    TKP_OCR_DIR,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TkpImageResult:
    image_paths: list[Path]
    warnings: list[str]


def select_model_images(
    catalog_path: Path,
    model_name: str,
    pages: Sequence[int],
    max_count: int | None = None,
) -> TkpImageResult:
    """
    Подобрать изображения для модели (общий вид).
    """
    warnings: list[str] = []
    pdf_path = _prefer_ocr_pdf(catalog_path)
    model_pages = _find_model_pages_by_image_ocr(pdf_path, model_name, pages)
    if not model_pages:
        model_pages = _find_model_pages(pdf_path, model_name)
    candidate_pages = _expand_pages(model_pages, TKP_IMAGE_MODEL_PAGE_WINDOW)
    if not candidate_pages:
        candidate_pages = list(pages)
    ranked_pages = _rank_pages_by_text(pdf_path, candidate_pages, set(model_pages))
    selected_pages = _select_pages(ranked_pages, max_count)
    if not selected_pages:
        selected_pages = [1]
        warnings.append("Не найдены страницы модели для изображений, взята 1-я.")

    image_dir = TKP_IMAGES_DIR / _safe_name(model_name)
    image_dir.mkdir(parents=True, exist_ok=True)

    image_paths: list[Path] = []
    for page in selected_pages:
        output_path = image_dir / f"{_safe_name(model_name)}_p{page:03d}.png"
        if output_path.exists():
            image_paths.append(output_path)
            continue
        rendered = _render_page_to_png(pdf_path, page, output_path)
        if rendered:
            image_paths.append(rendered)
        else:
            warnings.append(f"Не удалось извлечь изображение для стр. {page}.")

    return TkpImageResult(image_paths=image_paths, warnings=warnings)


def _select_pages(pages: Sequence[int], max_count: int | None) -> list[int]:
    if not pages:
        return []
    seen: set[int] = set()
    unique: list[int] = []
    for page in pages:
        if page in seen:
            continue
        seen.add(page)
        unique.append(page)
    limit = max_count or TKP_IMAGE_MAX_COUNT
    return unique[:limit]


def _prefer_ocr_pdf(catalog_path: Path) -> Path:
    ocr_path = TKP_OCR_DIR / f"{_safe_name(catalog_path.stem)}_ocr.pdf"
    return ocr_path if ocr_path.exists() else catalog_path


def _rank_pages_by_text(
    pdf_path: Path,
    pages: Sequence[int],
    model_pages: set[int],
) -> list[int]:
    if not pages:
        return []
    page_texts = _extract_page_texts(pdf_path, pages)
    scored = []
    for page in pages:
        text = page_texts.get(page, "")
        score = _score_page_text(text)
        if page in model_pages:
            score -= TKP_IMAGE_MODEL_PAGE_BONUS
        scored.append((score, page))
    return [page for _, page in sorted(scored, key=lambda item: (item[0], item[1]))]


def _expand_pages(pages: Sequence[int], window: int) -> list[int]:
    if not pages:
        return []
    expanded: list[int] = []
    for page in sorted(set(pages)):
        for offset in range(-window, window + 1):
            candidate = page + offset
            if candidate <= 0:
                continue
            expanded.append(candidate)
    return expanded


def _build_scan_order(preferred_pages: Sequence[int], total_pages: int) -> list[int]:
    order: list[int] = []
    seen: set[int] = set()
    expanded = _expand_pages(preferred_pages, TKP_IMAGE_MODEL_PAGE_WINDOW)
    if expanded:
        for page in expanded:
            if page <= 0 or page > total_pages:
                continue
            if page in seen:
                continue
            seen.add(page)
            order.append(page)
        return order
    for page in range(1, total_pages + 1):
        order.append(page)
    return order


def _extract_page_texts(pdf_path: Path, pages: Sequence[int]) -> dict[int, str]:
    try:
        import pypdf
    except ImportError:
        return {}
    texts: dict[int, str] = {}
    try:
        reader = pypdf.PdfReader(str(pdf_path))
    except (OSError, ValueError):
        return texts
    for page_index in pages:
        if page_index <= 0 or page_index > len(reader.pages):
            continue
        page = reader.pages[page_index - 1]
        texts[page_index] = page.extract_text() or ""
    return texts


def _score_page_text(text: str) -> float:
    if not text:
        return 0.0
    lowered = text.lower()
    keyword_penalty = 0.0
    for keyword in (
        "technical",
        "parameters",
        "specification",
        "specifications",
        "характерист",
        "параметр",
        "таблиц",
        "table",
    ):
        if keyword in lowered:
            keyword_penalty += TKP_IMAGE_TEXT_KEYWORD_PENALTY
    digits = sum(ch.isdigit() for ch in text)
    letters = sum(ch.isalpha() for ch in text)
    length = len(text)
    ratio_penalty = 0.0
    if length:
        digit_ratio = digits / length
        if digit_ratio > TKP_IMAGE_DIGIT_RATIO_THRESHOLD:
            ratio_penalty = TKP_IMAGE_DIGIT_RATIO_PENALTY
    return (
        keyword_penalty
        + ratio_penalty
        + digits * TKP_IMAGE_DIGIT_WEIGHT
        + letters * TKP_IMAGE_LETTER_WEIGHT
        + length * TKP_IMAGE_LENGTH_WEIGHT
    )


def _find_model_pages(pdf_path: Path, model_name: str) -> list[int]:
    if not model_name:
        return []
    try:
        import pypdf
    except ImportError:
        return []
    try:
        reader = pypdf.PdfReader(str(pdf_path))
    except (OSError, ValueError):
        return []
    normalized_model = _normalize_text(model_name)
    pages: list[int] = []
    for idx, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        if normalized_model and normalized_model in _normalize_text(text):
            pages.append(idx)
    return pages


def _find_model_pages_by_image_ocr(
    pdf_path: Path,
    model_name: str,
    preferred_pages: Sequence[int],
) -> list[int]:
    if not model_name:
        return []
    gs_path = _find_ghostscript()
    if not gs_path:
        return []
    tesseract_path = shutil.which("tesseract")
    if not tesseract_path:
        return []
    try:
        import pypdf
    except ImportError:
        return []
    try:
        reader = pypdf.PdfReader(str(pdf_path))
    except (OSError, ValueError):
        return []
    max_pages = min(len(reader.pages), TKP_IMAGE_OCR_MAX_PAGES)
    normalized_model = _normalize_text(model_name)
    if not normalized_model:
        return []
    scan_dir = TKP_IMAGES_DIR / "_scan" / _safe_name(model_name)
    scan_dir.mkdir(parents=True, exist_ok=True)
    matches: list[int] = []
    scanned = 0
    scan_order = _build_scan_order(preferred_pages, len(reader.pages))
    for page_index in scan_order:
        scanned += 1
        if scanned > max_pages:
            break
        image_path = scan_dir / f"scan_p{page_index:03d}.png"
        if not image_path.exists():
            rendered = _render_page_to_png(
                pdf_path,
                page_index,
                image_path,
                dpi=TKP_IMAGE_OCR_DPI,
            )
            if not rendered:
                continue
        text = _ocr_image_text(image_path, tesseract_path)
        if normalized_model in _normalize_text(text):
            matches.append(page_index)
            break
    return matches


def _ocr_image_text(image_path: Path, tesseract_path: str) -> str:
    ocr_path = image_path
    if TKP_IMAGE_OCR_CROP_RATIO:
        try:
            from PIL import Image
        except ImportError:
            Image = None
        if Image is not None:
            try:
                with Image.open(image_path) as img:
                    width, height = img.size
                    crop_height = max(1, int(height * TKP_IMAGE_OCR_CROP_RATIO))
                    cropped = img.crop((0, 0, width, crop_height))
                    ocr_path = image_path.with_suffix(".crop.png")
                    cropped.save(ocr_path)
            except OSError as exc:
                logger.warning("Не удалось подготовить изображение для OCR: %s", exc)
    args = [
        tesseract_path,
        str(ocr_path),
        "stdout",
        "-l",
        TKP_OCR_LANG,
        "--psm",
        "6",
    ]
    try:
        result = subprocess.run(
            args,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=TKP_IMAGE_OCR_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        logger.warning("OCR изображения не удался: %s", exc)
        return ""
    if result.returncode != 0:
        return ""
    return result.stdout or ""


def _normalize_text(text: str) -> str:
    if not text:
        return ""
    lowered = text.lower().translate(_OCR_CONFUSABLES)
    return "".join(ch for ch in lowered if ch.isalnum())


_OCR_CONFUSABLES = str.maketrans(
    {
        "а": "a",
        "в": "b",
        "е": "e",
        "к": "k",
        "м": "m",
        "н": "h",
        "о": "o",
        "р": "p",
        "с": "c",
        "т": "t",
        "у": "y",
        "х": "x",
        "А": "A",
        "В": "B",
        "Е": "E",
        "К": "K",
        "М": "M",
        "Н": "H",
        "О": "O",
        "Р": "P",
        "С": "C",
        "Т": "T",
        "У": "Y",
        "Х": "X",
    }
)


def _render_page_to_png(
    pdf_path: Path,
    page: int,
    output_path: Path,
    dpi: int | None = None,
) -> Path | None:
    gs_path = _find_ghostscript()
    if not gs_path:
        logger.warning("Ghostscript не найден, изображения не извлечены.")
        return None
    dpi = dpi or TKP_IMAGE_DPI
    args = [
        gs_path,
        "-dNOPAUSE",
        "-dBATCH",
        "-sDEVICE=png16m",
        f"-r{dpi}",
        f"-dFirstPage={page}",
        f"-dLastPage={page}",
        f"-sOutputFile={output_path}",
        str(pdf_path),
    ]
    try:
        result = subprocess.run(
            args,
            check=False,
            capture_output=True,
            text=True,
            timeout=TKP_IMAGE_RENDER_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        logger.warning("Ошибка рендера изображения: %s", exc)
        return None
    if result.returncode != 0:
        logger.warning("Ghostscript ошибка: %s", (result.stderr or "").strip())
        return None
    return output_path if output_path.exists() else None


def _find_ghostscript() -> str | None:
    return shutil.which("gswin64c") or shutil.which("gs")


def _safe_name(text: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in text)
    cleaned = cleaned.strip("_")
    return cleaned or "model"
