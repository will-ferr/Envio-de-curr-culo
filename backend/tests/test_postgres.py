"""Comportamentos que só existem no PostgreSQL (rodam com TEST_DATABASE_URL apontando para ele)."""

import os
import threading

import pytest
from sqlalchemy import text

from app import db as db_module
from app.models import Task
from app.services import queue

pytestmark = pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL", "").startswith("postgresql"),
    reason="exige TEST_DATABASE_URL de PostgreSQL",
)


def test_concurrent_workers_never_claim_the_same_task():
    Session = db_module.session_factory()
    with Session() as s:
        for i in range(20):
            queue.enqueue(s, "x", {"i": i})
        s.commit()

    claimed: list[int] = []
    lock = threading.Lock()
    barrier = threading.Barrier(4)

    def worker():
        barrier.wait()
        with Session() as s:
            while (t := queue.claim(s)) is not None:
                with lock:
                    claimed.append(t.id)

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(claimed) == 20
    assert len(set(claimed)) == 20  # nenhuma tarefa processada duas vezes


def test_check_constraints_are_enforced(db):
    with pytest.raises(Exception, match="ck_tasks_status"):
        db.execute(
            text(
                "INSERT INTO tasks (kind, payload, status, attempts, max_attempts, run_after, created_at, "
                "updated_at) VALUES ('x', '{}', 'invalido', 0, 1, now(), now(), now())"
            )
        )
        db.flush()
    db.rollback()
    assert db.query(Task).count() == 0
