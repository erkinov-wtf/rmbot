from collections.abc import Callable
from typing import Any

try:
    from drf_spectacular.utils import extend_schema as _extend_schema
except ModuleNotFoundError:

    def extend_schema(*args: Any, **kwargs: Any) -> Callable[[Any], Any]:
        """
        Fallback no-op decorator when drf-spectacular is unavailable in the env.
        """

        def decorator(target: Any) -> Any:
            return target

        return decorator

else:
    extend_schema = _extend_schema
