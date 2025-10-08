"""
Circuit breaker pattern implementation for resilient service calls.
"""

import time
import asyncio
from enum import Enum
from typing import Dict, Any, Optional, Callable, Awaitable
import sys
import os

# Add shared directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from shared.logging import get_logger


class CircuitBreakerState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, requests blocked
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitBreaker:
    """Circuit breaker implementation."""

    def __init__(self,
                 failure_threshold: int = 5,
                 recovery_timeout: float = 60.0,
                 expected_exception: type = Exception,
                 name: str = "default"):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self.name = name
        self.logger = get_logger(f"circuit_breaker.{name}")

        self._state = CircuitBreakerState.CLOSED
        self._failure_count = 0
        self._last_failure_time = 0.0
        self._success_count = 0

    def _can_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt a reset."""
        return (time.time() - self._last_failure_time) >= self.recovery_timeout

    def _should_attempt_call(self) -> bool:
        """Determine if a call should be attempted based on current state."""
        if self._state == CircuitBreakerState.CLOSED:
            return True
        elif self._state == CircuitBreakerState.OPEN:
            if self._can_attempt_reset():
                self._state = CircuitBreakerState.HALF_OPEN
                self.logger.info("Circuit breaker transitioning to half-open")
                return True
            return False
        elif self._state == CircuitBreakerState.HALF_OPEN:
            return True
        return False

    async def call(self, func: Callable[..., Awaitable[Any]], *args, **kwargs) -> Any:
        """Execute function with circuit breaker protection."""
        if not self._should_attempt_call():
            raise CircuitBreakerOpenException(
                f"Circuit breaker '{self.name}' is OPEN - blocking call"
            )

        try:
            result = await func(*args, **kwargs)

            # Success - reset counters and state
            if self._state == CircuitBreakerState.HALF_OPEN:
                self._state = CircuitBreakerState.CLOSED
                self._failure_count = 0
                self._success_count += 1
                self.logger.info("Circuit breaker reset to CLOSED after successful call")

            return result

        except self.expected_exception as e:
            self._record_failure()
            raise
        except Exception as e:
            # Unexpected exception - still count as failure
            self._record_failure()
            raise

    def _record_failure(self):
        """Record a failure and update state."""
        self._failure_count += 1
        self._last_failure_time = time.time()
        self._success_count = 0

        if self._failure_count >= self.failure_threshold:
            self._state = CircuitBreakerState.OPEN
            self.logger.warning(
                "Circuit breaker opened due to failures",
                failure_count=self._failure_count,
                threshold=self.failure_threshold
            )

    def get_state(self) -> Dict[str, Any]:
        """Get current circuit breaker state."""
        return {
            "name": self.name,
            "state": self._state.value,
            "failure_count": self._failure_count,
            "success_count": self._success_count,
            "last_failure_time": self._last_failure_time,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout": self.recovery_timeout
        }

    def is_open(self) -> bool:
        """Check if circuit breaker is in OPEN state."""
        return self._state == CircuitBreakerState.OPEN


class CircuitBreakerOpenException(Exception):
    """Exception raised when circuit breaker is open."""
    pass


class CircuitBreakerManager:
    """Manager for multiple circuit breakers."""

    def __init__(self):
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.logger = get_logger("circuit_breaker_manager")

    def get_circuit_breaker(self,
                           name: str,
                           failure_threshold: int = 5,
                           recovery_timeout: float = 60.0,
                           expected_exception: type = Exception) -> CircuitBreaker:
        """Get or create a circuit breaker."""
        if name not in self.circuit_breakers:
            self.circuit_breakers[name] = CircuitBreaker(
                failure_threshold=failure_threshold,
                recovery_timeout=recovery_timeout,
                expected_exception=expected_exception,
                name=name
            )
            self.logger.info("Created circuit breaker", name=name)

        return self.circuit_breakers[name]

    def get_all_states(self) -> Dict[str, Dict[str, Any]]:
        """Get states of all circuit breakers."""
        return {
            name: cb.get_state()
            for name, cb in self.circuit_breakers.items()
        }


# Global circuit breaker manager instance
circuit_breaker_manager = CircuitBreakerManager()


def get_circuit_breaker(name: str, **kwargs) -> CircuitBreaker:
    """Get a circuit breaker from the global manager."""
    return circuit_breaker_manager.get_circuit_breaker(name, **kwargs)
