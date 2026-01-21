# TKP strict test report
timestamp: 2026-01-21T10:54:53.819172

## Model: DVF 6500T

- status: ok
- docx: F:\Нейронки\prototype\artifacts\tkp\TKP_DVF_6500T_20260121_105640.docx
- catalog: F:\Нейронки\prototype\training_data\tkp\catalogs\DVF 6500-8000-8000T.pdf
- template: dvf
- parsed_json: F:\Нейронки\prototype\artifacts\tkp\parsed\DVF_6500-8000-8000T\DVF_6500T.json
- parsed_md: F:\Нейронки\prototype\artifacts\tkp\parsed\DVF_6500-8000-8000T\DVF_6500T.md
- trace_json: artifacts\tkp\trace\dvf_6500t_trace.json
- warnings: none
- tech_coverage: 4/21 (19%)
- main_units_count: 8
- standard_items_count: 8
- option_items_count: 8

### Strict review
- Ошибка: Тех. параметры заполнены менее чем на 60%.

### Missing (top 12)
- Максимальная нагрузка на стол
- Угол наклона оси
- Угол поворота
- Вращение стола
- Перемещение по осям X
- Перемещение по осям Y
- Перемещение по осям Z
- Тип конического отверстия
- Скорость
- Siemens One / Fanuc 31iB5 Plus
- Быстрый ход по оси X
- Быстрый ход по оси Y

### Source trace (top 10)
- Размер рабочего стола: ø650 X 600 (ø25.6 X 23.6) a | page 6 | Table size | mm (inch) | ø650 X 600 (ø25.6 X 23.6)
- Зона обработки: 60 {120} ea | page 30 |  | Tool capacity |  | ea | 40 {60, 90, 120} | 60 {120} | 40 {60, 120} | 60 {120} | 40 {60} | 40 {60}
- Мощность: 22 / 18.5 kW (29.5 hp/24.8 hp) kw | page 5 |  | Max. spindle power (S6 25%/Cont.) | 22 / 18.5 kW {22/18.5 kW} (29.5 hp/24.8 hp {29.5 hp/24.8 hp}) | 22 / 18.5 kW (29.5 hp/24.8 hp) | 35 / 25 kW (46.9 hp/33.5 hp )
- Крутящий момент: 2100 (1563.6) a | page 7 | Torque (rotating axis) | N·m (ft-lbs) | 2100 (1563.6)
