from __future__ import annotations

from threading import Event, Lock, Thread

import pytest

from research_engine.search_executor import SearchExecutor
from research_engine.search_executor_pool import SearchExecutorPool
from research_engine.search_models import (
    ExecutionPolicy,
    ProviderRequest,
    ProviderStatus,
)


class FunctionProvider:
    def __init__(self, search):
        self.search = search


def request(provider_id, search, ordinal=0):
    return ProviderRequest(
        provider_id=provider_id,
        original_query="topic",
        planned_query="topic",
        max_results=20,
        from_year=None,
        until_year=None,
        ordinal=ordinal,
        provider=FunctionProvider(search),
    )


def test_get_validates_worker_count():
    pool = SearchExecutorPool()

    with pytest.raises(TypeError):
        pool.get(True)
    with pytest.raises(TypeError):
        pool.get(1.5)
    with pytest.raises(ValueError):
        pool.get(0)


def test_search_executors_and_repeated_searches_reuse_executor():
    pool = SearchExecutorPool()
    first = SearchExecutor(max_workers=2, executor_pool=pool)
    second = SearchExecutor(max_workers=2, executor_pool=pool)

    try:
        shared = pool.get(2)
        first.execute((request("first", lambda **kwargs: {"results": []}),))
        second.execute((request("second", lambda **kwargs: {"results": []}),))
        first.execute((request("third", lambda **kwargs: {"results": []}),))

        assert pool.get(2) is shared
    finally:
        pool.shutdown_all()


def test_different_worker_counts_and_injected_pools_are_independent():
    first_pool = SearchExecutorPool()
    second_pool = SearchExecutorPool()

    try:
        assert first_pool.get(2) is not first_pool.get(3)
        assert first_pool.get(2) is not second_pool.get(2)
    finally:
        first_pool.shutdown_all()
        second_pool.shutdown_all()


def test_simultaneous_searches_share_global_worker_capacity():
    pool = SearchExecutorPool()
    release = Event()
    capacity_reached = Event()
    lock = Lock()
    active = 0
    peak = 0

    def blocked(**kwargs):
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
            if active == 2:
                capacity_reached.set()
        assert release.wait(timeout=2)
        with lock:
            active -= 1
        return {"results": []}

    executors = (
        SearchExecutor(max_workers=2, executor_pool=pool),
        SearchExecutor(max_workers=2, executor_pool=pool),
    )
    threads = [
        Thread(target=executor.execute, args=((
            request(f"{index}-a", blocked, 0),
            request(f"{index}-b", blocked, 1),
        ),))
        for index, executor in enumerate(executors)
    ]

    try:
        for thread in threads:
            thread.start()
        assert capacity_reached.wait(timeout=1)
        with lock:
            assert active == peak == 2
    finally:
        release.set()
        for thread in threads:
            thread.join(timeout=2)
        pool.shutdown_all()

    assert all(not thread.is_alive() for thread in threads)
    assert peak == 2


def test_shutdown_all_covers_all_executors_is_idempotent_and_allows_recreation():
    pool = SearchExecutorPool()
    first = pool.get(1)
    second = pool.get(2)

    pool.shutdown_all()
    pool.shutdown_all()

    with pytest.raises(RuntimeError):
        first.submit(lambda: None)
    with pytest.raises(RuntimeError):
        second.submit(lambda: None)

    replacement = pool.get(1)
    try:
        assert replacement is not first
        assert replacement.submit(lambda: "fresh").result(timeout=1) == "fresh"
    finally:
        pool.shutdown_all()


def test_timed_out_running_task_keeps_shared_executor_and_cancels_queued_task():
    pool = SearchExecutorPool()
    started = Event()
    release = Event()
    queued_called = Event()

    def blocked(**kwargs):
        started.set()
        assert release.wait(timeout=2)
        return {"results": []}

    def queued(**kwargs):
        queued_called.set()
        return {"results": []}

    executor = SearchExecutor(
        ExecutionPolicy(default_provider_timeout=0.02, max_workers=1),
        executor_pool=pool,
    )
    shared = pool.get(1)

    try:
        outcomes = executor.execute((
            request("running", blocked, 0),
            request("queued", queued, 1),
        ))

        assert started.is_set()
        assert not queued_called.is_set()
        assert pool.get(1) is shared
        assert [outcome.status for outcome in outcomes] == [
            ProviderStatus.TIMED_OUT,
            ProviderStatus.TIMED_OUT,
        ]
    finally:
        release.set()
        pool.shutdown_all()
