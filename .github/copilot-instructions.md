# GitHub Copilot Instructions for Neira Project

> These instructions are automatically loaded by GitHub Copilot.
> See AGENTS.md for full documentation.

## 🚫 CRITICAL RULES (violations will break the build)

### 1. File Location
```
❌ NEVER create Python files in project root
✅ Use: neira/, scripts/, tests/
```

### 2. Before Creating Any File
```
❌ NEVER create file without checking if similar exists
✅ First search: "class ClassName" or "def function_name"
```

### 3. Code Quality
```
❌ NEVER: bare except:, except Exception: without logging
❌ NEVER: functions > 60 lines
❌ NEVER: nesting > 4 levels
❌ NEVER: hardcoded numbers (use neira/config.py)
```

## ✅ File Placement Guide

| Type | Path |
|------|------|
| Core logic | `neira/core/`, `neira/brain/`, `neira/organs/` |
| Utilities | `neira/utils/` |
| Constants | `neira/config.py` |
| CLI scripts | `scripts/` |
| Tests | `tests/unit/` or `tests/integration/` |

## ✅ Code Patterns

```python
# ✅ CORRECT exception handling
except (ValueError, KeyError) as e:
    logger.warning(f"Description: {e}")

# ✅ CORRECT imports
from neira.config import MEMORY_MAX_LONG_TERM

# ✅ CORRECT type hints
def process(text: str, max_len: int = 100) -> str:
    """Brief description."""
```

## ⚠️ Pre-commit Checklist

Before suggesting any code:
1. Is file in correct location (not root)?
2. Does similar file/function already exist?
3. Are all exceptions specific (not bare)?
4. Are functions under 60 lines?
5. Are magic numbers in config.py?

## 📁 Project Structure

```
neira/           # Main package
├── core/        # Cell, Memory, LLM
├── brain/       # Cortex, Organs
├── utils/       # Utilities
└── config.py    # All constants

scripts/         # CLI utilities
tests/           # Tests only
docs/            # Documentation
```

## 🔒 Security Rules

```python
# ❌ NEVER
exec(user_input)
eval(user_input)
subprocess.run(f"cmd {user_input}", shell=True)

# ✅ Safe alternative
subprocess.run(["cmd", sanitized_arg], shell=False)
```

## Language

- Code identifiers: English
- Comments/docstrings: Russian
- User-facing logs: Russian
