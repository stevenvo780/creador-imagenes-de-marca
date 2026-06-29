"""Configuración de pytest: agrega la raíz del repo a sys.path.

Permite que los tests bajo tests/ importen `eikon_core` al ejecutarse vía pytest
(el runner histórico se ejecuta como script y no necesita esto).
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
