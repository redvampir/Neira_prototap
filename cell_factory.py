"""Фабрика клеток и органы для управления экосистемой Neira."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from cells import Cell, MemoryCell
from model_manager import ModelManager


@dataclass
class CellBlueprint:
    """Чертёж клетки, знает как её создавать."""

    name: str
    builder: Callable[[MemoryCell, Optional[ModelManager]], Cell]
    description: str = ""
    metadata: Dict[str, str] = field(default_factory=dict)

    def create(self, memory: MemoryCell, model_manager: Optional[ModelManager]) -> Cell:
        cell = self.builder(memory, model_manager)
        cell.name = self.name
        return cell


@dataclass
class Organ:
    """Орган — набор взаимосвязанных клеток."""

    name: str
    cells: List[Cell]
    description: str = ""

    def get_cell_names(self) -> List[str]:
        return [cell.name for cell in self.cells]


class CellFactory:
    """Регистрация чертежей клеток, их создание и группировка."""

    def __init__(self, memory: MemoryCell, model_manager: Optional[ModelManager], verbose: bool = False):
        self.memory = memory
        self.model_manager = model_manager
        self.verbose = verbose
        self._blueprints: Dict[str, CellBlueprint] = {}
        self._active_cells: Dict[str, Cell] = {}
        self._organs: Dict[str, Organ] = {}

    def register_blueprint(self, blueprint: CellBlueprint) -> None:
        if blueprint.name in self._blueprints:
            raise ValueError(f"Чертёж с именем {blueprint.name} уже зарегистрирован")
        self._blueprints[blueprint.name] = blueprint
        if self.verbose:
            print(f"🧬 Зарегистрирован чертёж: {blueprint.name}")

    def create_cell(self, name: str) -> Cell:
        if name not in self._blueprints:
            raise KeyError(f"Чертёж '{name}' не найден")
        blueprint = self._blueprints[name]
        cell = blueprint.create(self.memory, self.model_manager)
        if hasattr(cell, "lora_key") and "lora" in blueprint.metadata:
            cell.lora_key = blueprint.metadata.get("lora")
            if self.model_manager:
                self.model_manager.activate_lora_for_cell(name, cell.lora_key)
        self._active_cells[name] = cell
        if self.verbose:
            print(f"🧩 Создана клетка: {name}")
        return cell

    def create_organ(self, name: str, cell_names: List[str], description: str = "") -> Organ:
        organ_cells: List[Cell] = []
        for cell_name in cell_names:
            if cell_name in self._active_cells:
                organ_cells.append(self._active_cells[cell_name])
            else:
                organ_cells.append(self.create_cell(cell_name))
        organ = Organ(name=name, cells=organ_cells, description=description)
        self._organs[name] = organ
        if self.verbose:
            print(f"🫀 Орган '{name}' собран из клеток: {', '.join(cell_names)}")
        return organ

    def train_new_blueprint(self, name: str, goal: str, example_query: str = "") -> CellBlueprint:
        trainer = Cell(self.memory, self.model_manager)
        trainer.system_prompt = (
            "Ты — архитектор клеток системы Neira. Создай новый чертёж клетки. "
            "Ответь строго JSON без пояснений."
        )
        prompt = (
            "Сформируй системный промпт для новой клетки. "
            "Учти цель: {goal}. Верни JSON вида "
            "{\"system_prompt\": str, \"use_code_model\": bool, \"description\": str}."
        ).format(goal=goal)
        if example_query:
            prompt += f" Пример запроса: {example_query}."

        raw_response = trainer.call_llm(prompt, with_memory=False, model_key="reason")
        spec = self._parse_blueprint_response(raw_response)

        blueprint = CellBlueprint(
            name=name,
            description=spec.get("description", goal),
            builder=lambda memory, manager: self._build_custom_cell(
                name=name,
                system_prompt=spec.get("system_prompt", trainer.system_prompt),
                use_code_model=bool(spec.get("use_code_model", False)),
                memory=memory,
                model_manager=manager,
            ),
            metadata={"source": "trained"},
        )
        self.register_blueprint(blueprint)
        return blueprint

    def _parse_blueprint_response(self, response: str) -> Dict[str, str]:
        cleaned = response.strip()
        cleaned = re.sub(r"```json|```", "", cleaned)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Не удалось распарсить ответ LLM: {exc}: {cleaned[:200]}")

    def _build_custom_cell(
        self,
        name: str,
        system_prompt: str,
        use_code_model: bool,
        memory: MemoryCell,
        model_manager: Optional[ModelManager],
    ) -> Cell:
        custom_cell = Cell(memory, model_manager)
        custom_cell.name = name
        custom_cell.system_prompt = system_prompt
        custom_cell.use_code_model = use_code_model
        return custom_cell

    def get_stats(self) -> Dict[str, object]:
        return {
            "blueprints": list(self._blueprints.keys()),
            "active_cells": list(self._active_cells.keys()),
            "organs": {name: organ.get_cell_names() for name, organ in self._organs.items()},
        }
