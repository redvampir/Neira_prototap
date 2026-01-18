# NEIRA — Technical Specification v2.0 (MVP)

Минимальная реализация слоёв:
- `organism/` — живое ядро (Zustand store + чистые функции)
- `manifestation/` — визуальная проекция (Canvas + DOM)
- `ritual/` — ритуалы (первый запуск / «рождение»)

## Запуск (чек‑лист)

- [ ] `cd neira-app`
- [ ] `npm install`
- [ ] `npm run dev`
- [ ] открыть `http://localhost:3000`

## Проверка (чек‑лист)

- [ ] `cd neira-app`
- [ ] `npm run check` (быстрая проверка чистых функций и стора)
- [ ] `npm run build` (проверка сборки)

## Поведение по спецификации (кратко)

- Чёрный экран ~1 сек → первый «удар» (изменение `heart.resonance`)
- Сердце пульсирует с частотой `1 + resonance` Гц
- Цвет зависит от режима (`reflective | active | uncertain`)
- Дыхание деформирует сцену по ритму (`legato | staccato | syncopated`)
- «Глаз» следует за курсором, внимание падает к краям
- В `memory.events` сохраняются последние 100 взаимодействий

## Edge cases (учтено)

- Невалидные значения (NaN/undefined) не ломают стор и вычисления
- Отсутствие размеров viewport → внимание = 0
- Высокая частота pointer‑events → троттлинг через `requestAnimationFrame` в `manifestation/Eye.js`
