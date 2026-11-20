"""Fila de tarefas sobre o PostgreSQL.

Evita um Redis só para isso: com `FOR UPDATE SKIP LOCKED`, vários workers podem
consumir a mesma tabela sem pegar a mesma tarefa.
"""

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import utcnow
from app.models import Task


def enqueue(
    db: Session, kind: str, payload: dict | None = None, *, max_attempts: int = 3, dedupe: bool = False
) -> Task:
    """Cria uma tarefa. Com `dedupe`, reaproveita uma pendente idêntica (ex.: varredura periódica)."""
    payload = payload or {}
    if dedupe:
        existing = db.scalars(select(Task).where(Task.kind == kind, Task.status.in_(("pending", "running")))).all()
        for t in existing:
            if t.payload == payload:
                return t
    task = Task(kind=kind, payload=payload, max_attempts=max_attempts)
    db.add(task)
    db.flush()
    return task


def claim(db: Session) -> Task | None:
    """Pega a próxima tarefa disponível e marca como em execução (na mesma transação)."""
    task = db.scalars(
        select(Task)
        .where(Task.status == "pending", Task.run_after <= utcnow())
        .order_by(Task.id)
        .limit(1)
        .with_for_update(skip_locked=True)
    ).first()
    if task is None:
        return None
    task.status = "running"
    task.attempts += 1
    db.commit()
    return task


def complete(db: Session, task: Task, result: dict | None = None) -> None:
    task.status = "done"
    task.result = result or {}
    task.last_error = None
    db.commit()


def fail(db: Session, task: Task, error: str, *, retryable: bool = True) -> None:
    """Reagenda com backoff exponencial (30s, 2min, 8min...) até esgotar as tentativas."""
    task.last_error = error[:2000]
    if retryable and task.attempts < task.max_attempts:
        task.status = "pending"
        task.run_after = utcnow() + timedelta(seconds=30 * 4 ** (task.attempts - 1))
    else:
        task.status = "failed"
    db.commit()


def recover_stale(db: Session, older_than: timedelta = timedelta(minutes=15)) -> int:
    """Devolve à fila tarefas 'running' de um worker que morreu no meio."""
    stale = db.scalars(select(Task).where(Task.status == "running", Task.updated_at < utcnow() - older_than)).all()
    for t in stale:
        t.status = "pending"
    db.commit()
    return len(stale)
