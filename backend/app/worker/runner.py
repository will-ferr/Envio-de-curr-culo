"""Processo worker: consome a fila, agenda a varredura de fontes e escuta o Telegram.

python -m app.worker
"""

import logging
import signal
import threading
import time

from app.ai.base import AIError
from app.config import get_settings
from app.db import session_factory
from app.errors import AppError
from app.services import notify, queue, settings
from app.worker.handlers import HANDLERS

log = logging.getLogger("worker")


class Worker:
    def __init__(self) -> None:
        self.stop = threading.Event()
        self.cfg = get_settings()
        self._last_schedule = 0.0

    def run_once(self) -> bool:
        """Processa uma tarefa, se houver. Retorna True se processou."""
        Session = session_factory()
        with Session() as db:
            task = queue.claim(db)
            if task is None:
                return False
            handler = HANDLERS.get(task.kind)
            log.info("tarefa iniciada", extra={"task_id": task.id, "kind": task.kind, "attempt": task.attempts})
            started = time.monotonic()
            try:
                if handler is None:
                    raise AppError(f"Tipo de tarefa desconhecido: {task.kind}")
                result = handler(db, task.payload)
                queue.complete(db, task, result)
                log.info(
                    "tarefa concluída",
                    extra={
                        "task_id": task.id,
                        "kind": task.kind,
                        "duration_ms": round((time.monotonic() - started) * 1000),
                    },
                )
            except AIError as exc:
                db.rollback()
                queue.fail(db, task, f"{exc.code}: {exc.message}", retryable=exc.retryable)
                log.warning("tarefa falhou (IA)", extra={"task_id": task.id, "error": exc.code})
            except AppError as exc:
                db.rollback()
                queue.fail(db, task, f"{exc.code}: {exc.message}", retryable=exc.status >= 500)
                log.warning("tarefa falhou", extra={"task_id": task.id, "error": exc.code})
            except Exception as exc:
                db.rollback()
                queue.fail(db, task, f"INTERNAL: {exc!r}")
                log.exception("erro inesperado na tarefa", extra={"task_id": task.id})
            return True

    def schedule(self) -> None:
        """A cada N minutos, agenda a varredura de RSS/IMAP (sem duplicar se já houver uma pendente)."""
        now = time.monotonic()
        if now - self._last_schedule < self.cfg.sources_interval_minutes * 60:
            return
        self._last_schedule = now
        with session_factory()() as db:
            queue.recover_stale(db)
            queue.enqueue(db, "poll_sources", {}, dedupe=True, max_attempts=1)
            db.commit()

    def telegram_loop(self) -> None:
        """Long polling do bot. Reconfigurações (token novo) são lidas a cada ciclo."""
        offset: int | None = None
        while not self.stop.is_set():
            with session_factory()() as db:
                tg = notify.client(db)
                if tg is None:
                    self.stop.wait(15)
                    continue
                try:
                    stored = settings.get(db, "telegram.offset")
                    offset = int(stored) if stored is not None else offset
                    for update in tg.get_updates(offset, timeout=25):
                        offset = update["update_id"] + 1
                        notify.handle_update(db, update, tg)
                        settings.set_value(db, "telegram.offset", offset)
                        db.commit()
                except AppError as exc:
                    log.warning("telegram indisponível", extra={"error": exc.message})
                    self.stop.wait(30)
                except Exception:
                    log.exception("erro no loop do telegram")
                    self.stop.wait(30)
                finally:
                    tg.close()

    def run(self) -> None:
        signal.signal(signal.SIGTERM, lambda *_: self.stop.set())
        signal.signal(signal.SIGINT, lambda *_: self.stop.set())
        threading.Thread(target=self.telegram_loop, name="telegram", daemon=True).start()
        log.info("worker iniciado", extra={"poll_seconds": self.cfg.worker_poll_seconds})
        while not self.stop.is_set():
            try:
                self.schedule()
                if not self.run_once():
                    self.stop.wait(self.cfg.worker_poll_seconds)
            except Exception:
                log.exception("falha no ciclo do worker")
                self.stop.wait(5)
        log.info("worker encerrado")


def main() -> None:
    from app.logging_setup import configure_logging

    configure_logging(get_settings().log_level)
    Worker().run()
