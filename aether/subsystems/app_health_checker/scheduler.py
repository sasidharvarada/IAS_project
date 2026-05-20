"""
scheduler.py

Background scheduler for periodic app health checks.
"""

from __future__ import annotations

import logging
import threading
from typing import Callable, Dict, Iterable

from .models import AppHealthRecord, ProbeResult
from .prober import AppHealthProber

logger = logging.getLogger("aether.app_health_checker.scheduler")


class HealthCheckScheduler:
    def __init__(
        self,
        registry: Dict[str, AppHealthRecord],
        prober: AppHealthProber,
        on_probe: Callable[[AppHealthRecord, ProbeResult], None] | None = None,
        interval_seconds: int = 30,
    ):
        self.registry = registry
        self.prober = prober
        self.interval_seconds = max(1, interval_seconds)
        self.on_probe = on_probe

        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info("App health scheduler started (interval=%ss)", self.interval_seconds)

    def stop(self) -> None:
        if not self._thread:
            return

        self._stop_event.set()
        self._thread.join(timeout=2.0)
        logger.info("App health scheduler stopped")

    def run_once(self) -> list[ProbeResult]:
        results: list[ProbeResult] = []
        for record in self._records_snapshot():
            probe = self.prober.probe(record)
            record.apply_probe(probe)
            results.append(probe)

            if self.on_probe:
                self.on_probe(record, probe)

        return results

    def _records_snapshot(self) -> Iterable[AppHealthRecord]:
        return list(self.registry.values())

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                self.run_once()
            except Exception as exc:  # pragma: no cover
                logger.exception("App health check loop error: %s", exc)

            self._stop_event.wait(self.interval_seconds)
