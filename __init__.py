# Auto-generated shim for backward compatibility
try:
    # Когда `prototype` импортируется как пакет (sys.path содержит parent), нужен относительный импорт.
    from .scripts import *  # type: ignore
except ImportError:
    # Когда запускаем из корня проекта (sys.path содержит `prototype/`), работает абсолютный импорт.
    from scripts import *  # type: ignore
