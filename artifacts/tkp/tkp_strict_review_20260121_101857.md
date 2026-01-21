# TKP strict test report
timestamp: 2026-01-21T10:18:57.131983

## Model: DVF 6500T

- status: error
- error: 'NoneType' object has no attribute 'lower'

## Model: HT2

- status: ok
- docx: F:\Нейронки\prototype\artifacts\tkp\TKP_HT2_20260121_102035.docx
- catalog: F:\Нейронки\prototype\training_data\tkp\catalogs\1_ECATALOG_OF_HT_CT_ADVANCED_TYPE_CNC_TURNING_CENTER_DRC_MACHINERY.pdf
- template: ht
- parsed_json: F:\Нейронки\prototype\artifacts\tkp\parsed\1_ECATALOG_OF_HT_CT_ADVANCED_TYPE_CNC_TURNING_CENTER_DRC_MACHINERY\HT2.json
- parsed_md: F:\Нейронки\prototype\artifacts\tkp\parsed\1_ECATALOG_OF_HT_CT_ADVANCED_TYPE_CNC_TURNING_CENTER_DRC_MACHINERY\HT2.md
- trace_json: artifacts\tkp\trace\ht2_trace.json
- warnings:
  - Модель не найдена на страницах каталога.
- tech_coverage: 0/36 (0%)
- main_units_count: 0
- standard_items_count: 0
- option_items_count: 0

### Strict review
- Ошибка: Тех. параметры заполнены менее чем на 60%.
- Ошибка: Пустой раздел основных узлов (нет данных).
- Ошибка: Пустая стандартная комплектация.
- Ошибка: Пустые опции.
- Ошибка: Есть предупреждения при выборе каталога/страниц.

### Missing (top 12)
- Головка шпинделя
- Макс.скорость шпинделя
- Мощность шпинделя
- Макс. крутящий момент
- Диаметр патрона
- Диаметр отверстия шпинделя
- Макс. диаметр стержня
- Смазка подшипника шпинделя
- Смазка направляющей
- Максимальное вращение над станиной
- Максимальное вращение над суппортом
- Максимальный диаметр обработки

### Source trace (top 10)
