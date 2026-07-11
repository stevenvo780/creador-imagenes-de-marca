"""Configuración de pytest: agrega la raíz del repo a sys.path.

Permite que los tests bajo tests/ importen `eikon_core` al ejecutarse vía pytest
(el runner histórico se ejecuta como script y no necesita esto).

También setea env vars seguras para tests antes de que webapp/* sea importado.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Setear env vars seguras para tests ANTES de cualquier import de webapp
# (para que Settings las lea en default_factory al instanciar)
os.environ.setdefault("EIKON_WEBAPP_SECRET", "test-jwt-secret-" + "a" * 50)  # 66 chars >= 32
os.environ.setdefault("EIKON_WEBAPP_COOKIE_SECURE", "0")  # OK para tests locales

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
