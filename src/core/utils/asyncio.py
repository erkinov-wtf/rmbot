from typing import Callable, TypeVar

from asgiref.sync import sync_to_async

T = TypeVar("T")


async def run_sync(func: Callable[..., T], /, *args, thread_sensitive: bool = True, **kwargs) -> T:
    """
    Execute a synchronous callable in a thread, returning the awaited result.

    thread_sensitive=True keeps calls for the same callable on the same thread
    (suitable for ORM access). Set False for CPU-bound pure Python functions.
    """
    return await sync_to_async(func, thread_sensitive=thread_sensitive)(*args, **kwargs)
