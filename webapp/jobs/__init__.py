"""Sistema de workers in-process para renderizado combinatorio de Eikon.

Exporta las funciones públicas y la clase WorkerPool para integrar
con webapp/app.py y la API SSE de monitoreo de batches.
"""

from __future__ import annotations

from .worker import WorkerPool, enqueue_batch, get_worker, job_events, set_worker

__all__ = [
    "WorkerPool",
    "enqueue_batch",
    "get_worker",
    "job_events",
    "set_worker",
]
