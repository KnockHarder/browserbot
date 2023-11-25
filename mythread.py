import asyncio
import random
import time
from concurrent.futures import ThreadPoolExecutor, Future
from typing import TypeVar, Coroutine, Optional, Callable, Any, Iterable

T = TypeVar('T')

_EXECUTOR: Optional[ThreadPoolExecutor] = None


def shutdown_executor():
    if _EXECUTOR:
        _EXECUTOR.shutdown()


def submit(func: Callable) -> Future:
    global _EXECUTOR
    if not _EXECUTOR:
        _EXECUTOR = ThreadPoolExecutor(thread_name_prefix='my-thread')
    return _EXECUTOR.submit(func)


class AsyncResult:
    def __init__(self, cor: Coroutine[Any, Any, T]):
        self.coroutine = cor

    @classmethod
    def wait_done(cls, cor: Coroutine[Any, Any, T]):
        AsyncResult(cor).wait()

    @classmethod
    def wait_all_done(cls, cor_list: Iterable[Coroutine]):
        for cor in cor_list:
            AsyncResult.wait_done(cor)

    @classmethod
    def get_result(cls, cor: Coroutine[Any, Any, T]) -> T:
        return AsyncResult(cor).get()

    def get(self) -> T:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            future = submit(lambda: asyncio.run(self.coroutine))
            while not future.done():
                time.sleep(.01)
            return future.result()
        else:
            return loop.run_until_complete(self.coroutine)

    def wait(self):
        self.get()

    def __await__(self):
        return self.coroutine.__await__()


def main():
    async def async_random_value():
        await asyncio.sleep(.1)
        return random.Random().random()

    def sync_value():
        return AsyncResult(async_random_value()).get()

    async def loop_all():
        for i in range(1000):
            print(sync_value())
            await asyncio.sleep(.1)

    asyncio.get_event_loop().run_until_complete(loop_all())


if __name__ == '__main__':
    main()
