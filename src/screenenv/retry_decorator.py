import functools
import time
from typing import Any, Callable, TypeVar, cast

from screenenv.logger import get_logger

T = TypeVar("T")

logger = get_logger(__name__)


def retry(
    retry_times: int = 10, retry_interval: float = 5.0, break_on_timeout: bool = True
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    A decorator that implements retry logic for functions that make HTTP requests.

    Args:
        retry_times: Number of times to retry the operation
        retry_interval: Time to wait between retries in seconds
        break_on_timeout: Whether to break retries on timeout exceptions

    Returns:
        A decorated function that implements retry logic
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            for attempt in range(retry_times):
                try:
                    result = func(*args, **kwargs)
                    return result
                except Exception as e:
                    if isinstance(e, TimeoutError) and break_on_timeout:
                        logger.error(f"Timeout occurred: {e}")
                        break

                    if attempt < retry_times - 1:
                        logger.error(f"Attempt {attempt + 1} failed: {e}")
                        logger.info(f"Retrying {func.__name__}...")
                        time.sleep(retry_interval)
                    else:
                        logger.error(
                            f"All {retry_times} attempts failed for {func.__name__}"
                        )
                        raise

            raise Exception(
                f"Failed to execute {func.__name__} after {retry_times} attempts"
            )

        return cast(Callable[..., T], wrapper)

    return decorator
