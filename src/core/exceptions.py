class PolymarketBotError(Exception):
    pass


class PolymarketAPIError(PolymarketBotError):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class RateLimitError(PolymarketAPIError):
    pass


class AuthError(PolymarketAPIError):
    pass


class InsufficientCapitalError(PolymarketBotError):
    pass


class CircuitBreakerError(PolymarketBotError):
    def __init__(self, breaker_type: str):
        super().__init__(f"Circuit breaker active: {breaker_type}")
        self.breaker_type = breaker_type


class KillswitchError(PolymarketBotError):
    pass


class InvalidWalletTransitionError(PolymarketBotError):
    def __init__(self, from_status: str, to_status: str):
        super().__init__(f"Invalid wallet transition: {from_status} → {to_status}")


class InvalidPositionTransitionError(PolymarketBotError):
    def __init__(self, from_status: str, to_status: str):
        super().__init__(f"Invalid position transition: {from_status} → {to_status}")


class OrderUnfillableError(PolymarketBotError):
    pass


class ConfigValidationError(PolymarketBotError):
    pass


class DBSchemaError(PolymarketBotError):
    pass


class ReconciliationError(PolymarketBotError):
    pass
