"""Package shim for moved utility scripts.

This allows legacy imports like `import brain_integration` to continue
working by importing from `scripts.brain_integration`.
"""

# Expose commonly used script modules lazily
__all__ = []
