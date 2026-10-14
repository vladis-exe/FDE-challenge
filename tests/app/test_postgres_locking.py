"""Per-conversation locking with concurrent workers. Postgres only: SQLite has no row locks.

Run with a Postgres DATABASE_URL, e.g.
    docker run -d --rm --name sazon-pg -e POSTGRES_PASSWORD=postgres \\
        -p 55432:5432 postgres:16-alpine
    DATABASE_URL=postgres://postgres:postgres@localhost:55432/sazon \\
        DJANGO_SETTINGS_MODULE=config.settings uv run pytest tests/app/test_postgres_locking.py
"""

import threading
import time

import pytest
from django.conf import settings
from django.db import connection

from apps.candidates.models import Candidate, Conversation
from apps.messaging import services

pytestmark = [
    pytest.mark.skipif(
        settings.DATABASES["default"]["ENGINE"] != "django.db.backends.postgresql",
        reason="needs Postgres row locks (select_for_update skip_locked)",
    ),
    pytest.mark.django_db(transaction=True),
]

TURN_SECONDS = 0.5


@pytest.fixture
def slow_engine(engine):
    """The fake engine, but each turn takes TURN_SECONDS and records when it ran."""
    turns: list[tuple[str, float, float]] = []
    lock = threading.Lock()
    handle = engine.handle_message

    def slow(state, message, *, ctx):
        started = time.monotonic()
        time.sleep(TURN_SECONDS)
        with lock:
            turns.append((state.conversation_id, started, time.monotonic()))
        return handle(state, message, ctx=ctx)

    engine.handle_message = slow
    return turns


def run_workers(count: int) -> list[bool]:
    results: list[bool] = []

    def worker():
        try:
            results.append(services.process_next_inbound())
        finally:
            connection.close()  # each thread has its own connection

    threads = [threading.Thread(target=worker) for _ in range(count)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    return results


def test_two_workers_take_different_conversations_in_parallel(slow_engine, channel):
    a = services.start_conversation(
        Candidate.objects.create(), Conversation.Channel.WEB, vacancy_id="driver"
    )
    b = services.start_conversation(
        Candidate.objects.create(), Conversation.Channel.WEB, vacancy_id="driver"
    )
    services.store_inbound(a, "a1")
    services.store_inbound(a, "a2")
    services.store_inbound(b, "b1")

    started = time.monotonic()
    assert run_workers(2) == [True, True]
    elapsed = time.monotonic() - started

    assert {conversation for conversation, _, _ in slow_engine} == {str(a.pk), str(b.pk)}
    assert elapsed < 2 * TURN_SECONDS  # in parallel, not one after the other
    # a's second message waited for a's first turn: still queued, in order.
    pending = a.messages.filter(direction="in", processed_at__isnull=True)
    assert [m.text for m in pending] == ["a2"]


def test_one_conversation_is_never_processed_by_two_workers_at_once(slow_engine, channel):
    a = services.start_conversation(
        Candidate.objects.create(), Conversation.Channel.WEB, vacancy_id="driver"
    )
    for text in ["uno", "dos", "tres"]:
        services.store_inbound(a, text)

    results = run_workers(3)

    # One worker holds a's lock; the others skip it and find nothing else to do.
    assert sorted(results) == [False, False, True]
    assert len(slow_engine) == 1
