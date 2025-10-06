"""
Retry mechanism for resilient operations.
"""

import asyncio
import random
import time
from typing import Dict, Any, Optional, Callable, Awaitable, Type
import sys
import os

# Add shared directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from shared.logging import get_logger


class RetryConfig:
    """Configuration for retry behavior."""

    def __init__(self,
                 max_attempts: int = 3,
                 base_delay: float = 1.0,
                 max_delay: float = 60.0,
                 exponential_base: float = 2.0,
                 jitter: bool = True,
                 backoff_strategy: str = "exponential"):
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
        self.backoff_strategy = backoff_strategy


class RetryError(Exception):
    """Exception raised when all retry attempts are exhausted."""
    def __init__(self, message: str, last_exception: Exception, attempts: int):
        super().__init__(message)
        self.last_exception = last_exception
        self.attempts = attempts


def retry_on_exception(exceptions: tuple = (Exception,),
                      config: Optional[RetryConfig] = None) -> Callable:
    """Decorator for retrying async functions on exceptions."""

    if config is None:
        config = RetryConfig()

    def decorator(func: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
        async def wrapper(*args, **kwargs) -> Any:
            logger = get_logger(f"retry.{func.__name__}")

            last_exception = None

            for attempt in range(1, config.max_attempts + 1):
                try:
                    logger.debug(
                        "Retry attempt",
                        attempt=attempt,
                        max_attempts=config.max_attempts,
                        function=func.__name__
                    )

                    result = await func(*args, **kwargs)

                    if attempt > 1:
                        logger.info(
                            "Retry succeeded",
                            attempt=attempt,
                            function=func.__name__
                        )

                    return result

                except exceptions as e:
                    last_exception = e

                    if attempt == config.max_attempts:
                        logger.error(
                            "All retry attempts exhausted",
                            attempt=attempt,
                            max_attempts=config.max_attempts,
                            function=func.__name__,
                            error=str(e)
                        )
                        raise RetryError(
                            f"Function {func.__name__} failed after {config.max_attempts} attempts",
                            last_exception=e,
                            attempts=config.max_attempts
                        )

                    # Calculate delay
                    delay = _calculate_delay(attempt, config)

                    logger.warning(
                        "Retry attempt failed, waiting before next attempt",
                        attempt=attempt,
                        delay=delay,
                        function=func.__name__,
                        error=str(e)
                    )

                    await asyncio.sleep(delay)

            # This should never be reached, but just in case
            raise RetryError(
                f"Unexpected error in retry wrapper for {func.__name__}",
                last_exception=last_exception or Exception("Unknown error"),
                attempts=config.max_attempts
            )

        return wrapper

    return decorator


def _calculate_delay(attempt: int, config: RetryConfig) -> float:
    """Calculate delay between retry attempts."""
    if config.backoff_strategy == "exponential":
        delay = config.base_delay * (config.exponential_base ** (attempt - 1))
    elif config.backoff_strategy == "linear":
        delay = config.base_delay * attempt
    elif config.backoff_strategy == "fixed":
        delay = config.base_delay
    else:
        delay = config.base_delay

    # Apply max delay cap
    delay = min(delay, config.max_delay)

    # Add jitter if enabled
    if config.jitter:
        jitter_amount = delay * 0.1  # 10% jitter
        jitter = random.uniform(-jitter_amount, jitter_amount)
        delay += jitter

    return max(0.0, delay)


class RetryManager:
    """Manager for retry configurations and statistics."""

    def __init__(self):
        self.configs: Dict[str, RetryConfig] = {}
        self.stats: Dict[str, Dict[str, int]] = {}
        self.logger = get_logger("retry_manager")

    def set_config(self, name: str, config: RetryConfig):
        """Set retry configuration for a function."""
        self.configs[name] = config
        self.stats[name] = {"attempts": 0, "successes": 0, "failures": 0}
        self.logger.info("Set retry config", name=name, config=config.__dict__)

    def get_config(self, name: str) -> Optional[RetryConfig]:
        """Get retry configuration."""
        return self.configs.get(name)

    def record_attempt(self, name: str):
        """Record a retry attempt."""
        if name in self.stats:
            self.stats[name]["attempts"] += 1

    def record_success(self, name: str):
        """Record a successful retry."""
        if name in self.stats:
            self.stats[name]["successes"] += 1

    def record_failure(self, name: str):
        """Record a failed retry."""
        if name in self.stats:
            self.stats[name]["failures"] += 1

    def get_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get retry statistics."""
        return {
            name: {
                **stats,
                "success_rate": stats["successes"] / max(1, stats["attempts"])
            }
            for name, stats in self.stats.items()
        }


# Global retry manager
retry_manager = RetryManager()


def retry_with_config(name: str, exceptions: tuple = (Exception,)) -> Callable:
    """Create a retry decorator with a specific configuration."""

    def decorator(func: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
        config = retry_manager.get_config(name)
        if config is None:
            config = RetryConfig()

        return retry_on_exception(exceptions, config)(func)

    return decorator
