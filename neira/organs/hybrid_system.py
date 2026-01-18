"""
Гибридная система органов Neira.

Объединяет UnifiedOrganSystem и ExecutableOrganRegistry в единый интерфейс.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple

from executable_organs import ExecutableOrgan, ExecutableOrganRegistry, get_organ_registry
from neira.brain.store import get_brain_store
from unified_organ_system import OrganDefinition, OrganStatus, UnifiedOrganSystem


@dataclass(frozen=True)
class HybridOrganEntry:
    """Единое представление органа из разных источников."""

    organ_id: str
    name: str
    description: str
    source: str
    status: str
    capabilities: List[str]
    triggers: List[str]


def _entry_from_unified(organ: OrganDefinition) -> HybridOrganEntry:
    return HybridOrganEntry(
        organ_id=organ.id,
        name=organ.name,
        description=organ.description,
        source="unified",
        status=organ.status.value,
        capabilities=list(organ.capabilities),
        triggers=list(organ.triggers),
    )


def _entry_from_executable(organ: ExecutableOrgan) -> HybridOrganEntry:
    capabilities = [cap.value for cap in getattr(organ, "capabilities", [])]
    return HybridOrganEntry(
        organ_id=organ.organ_id,
        name=organ.name,
        description=organ.description,
        source="executable",
        status="active",
        capabilities=capabilities,
        triggers=[],
    )


def _dedupe_by_name(entries: Iterable[HybridOrganEntry]) -> List[HybridOrganEntry]:
    unique: Dict[str, HybridOrganEntry] = {}
    for entry in entries:
        key = entry.name.lower()
        if key not in unique:
            unique[key] = entry
    return list(unique.values())


class HybridOrganSystem:
    """
    Гибридный интерфейс для органов Neira.
    """

    def __init__(
        self,
        unified: UnifiedOrganSystem | None = None,
        executable: ExecutableOrganRegistry | None = None,
    ):
        if unified is None:
            brain = get_brain_store()
            unified = UnifiedOrganSystem(brain=brain)
        self._unified = unified
        self._executable = executable or get_organ_registry()

    def list_organs(self, include_disabled: bool = False) -> List[HybridOrganEntry]:
        """
        Возвращает объединённый список органов.
        """
        unified_entries: List[HybridOrganEntry] = []
        for organ in self._unified.organs.values():
            if not include_disabled and organ.status != OrganStatus.ACTIVE:
                continue
            unified_entries.append(_entry_from_unified(organ))

        executable_entries = [
            _entry_from_executable(organ)
            for organ in self._executable.organs.values()
        ]
        merged = _dedupe_by_name([*unified_entries, *executable_entries])
        merged.sort(key=lambda item: item.name.lower())
        return merged

    def get_organ(self, organ_id_or_name: str) -> Optional[HybridOrganEntry]:
        """
        Ищет орган по id или имени.
        """
        key = organ_id_or_name.strip().lower()
        for organ in self._unified.organs.values():
            if organ.id.lower() == key or organ.name.lower() == key:
                return _entry_from_unified(organ)
        for organ in self._executable.organs.values():
            if organ.organ_id.lower() == key or organ.name.lower() == key:
                return _entry_from_executable(organ)
        return None

    def register_custom_organ(
        self,
        name: str,
        description: str,
        cell_type: str,
        triggers: List[str],
        code: str | None = None,
        created_by: str | None = None,
        require_approval: bool = True,
    ) -> Tuple[bool, str]:
        """
        Регистрирует пользовательский орган через UnifiedOrganSystem.
        """
        return self._unified.register_organ(
            name=name,
            description=description,
            cell_type=cell_type,
            triggers=triggers,
            code=code,
            created_by=created_by,
            require_approval=require_approval,
        )

    def register_executable_organ(self, organ: ExecutableOrgan) -> None:
        """Регистрирует исполняемый орган в локальном реестре."""
        self._executable.register(organ)

    def suggest_organs(self, user_input: str, max_items: int = 3) -> List[HybridOrganEntry]:
        """
        Возвращает кандидатов органов для пользовательского запроса.
        """
        suggestions: List[HybridOrganEntry] = []
        candidates = self._unified.get_organ_for_user_choice(user_input)
        for candidate in candidates[:max_items]:
            organ_id = candidate.get("id")
            if organ_id:
                entry = self.get_organ(organ_id)
                if entry:
                    suggestions.append(entry)

        executable_organ, score = self._executable.find_best_organ(user_input)
        if executable_organ and score >= 0.3:
            suggestions.append(_entry_from_executable(executable_organ))

        return _dedupe_by_name(suggestions)[:max_items]


_hybrid_system: HybridOrganSystem | None = None


def get_hybrid_organ_system() -> HybridOrganSystem:
    """Возвращает singleton гибридной системы органов."""
    global _hybrid_system
    if _hybrid_system is None:
        _hybrid_system = HybridOrganSystem()
    return _hybrid_system


__all__ = ["HybridOrganEntry", "HybridOrganSystem", "get_hybrid_organ_system"]
