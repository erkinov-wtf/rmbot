from collections.abc import Callable

from asgiref.sync import sync_to_async


async def run_sync[**P, T](
    func: Callable[P, T],
    /,
    *args: P.args,
    thread_sensitive: bool = True,
    **kwargs: P.kwargs,
) -> T:
    """
    Execute a synchronous callable in a thread, returning the awaited result.

    thread_sensitive=True keeps calls for the same callable on the same thread
    (suitable for ORM access). Set False for CPU-bound pure Python functions.

    @param func: The synchronous function to execute.
    @param args: Positional arguments to pass to the function.
    @param thread_sensitive: Whether to keep calls for the same callable on the same thread.
    @param kwargs: Keyword arguments to pass to the function.
    @return: The result of the function execution.

    """
    return await sync_to_async(func, thread_sensitive=thread_sensitive)(*args, **kwargs)
