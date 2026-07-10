from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Lock


class SearchExecutorPool:
    """Thread-safe owner of executors shared by configured worker capacity."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._executors: dict[int, ThreadPoolExecutor] = {}

    def get(self, max_workers: int) -> ThreadPoolExecutor:
        if isinstance(max_workers, bool) or not isinstance(max_workers, int):
            raise TypeError("max_workers must be an integer")
        if max_workers <= 0:
            raise ValueError("max_workers must be greater than 0")

        with self._lock:
            executor = self._executors.get(max_workers)
            if executor is None:
                executor = ThreadPoolExecutor(max_workers=max_workers)
                self._executors[max_workers] = executor
            return executor

    def shutdown_all(
        self,
        wait: bool = True,
        cancel_futures: bool = True,
    ) -> None:
        """Detach and shut down every executor currently owned by this pool."""
        with self._lock:
            executors = tuple(self._executors.values())
            self._executors.clear()

        for executor in executors:
            executor.shutdown(wait=wait, cancel_futures=cancel_futures)


_DEFAULT_SEARCH_EXECUTOR_POOL = SearchExecutorPool()


def get_search_executor_pool() -> SearchExecutorPool:
    """Return the process-shared search executor pool."""
    return _DEFAULT_SEARCH_EXECUTOR_POOL
