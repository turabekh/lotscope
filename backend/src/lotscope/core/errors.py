class LotScopeError(Exception):
    default_message = "An unexpected error occurred."

    def __init__(self, message: str | None = None) -> None:
        self.message = message or self.default_message
        super().__init__(self.message)


class NotFoundError(LotScopeError):
    default_message = "The requested resource was not found."


class ValidationError(LotScopeError):
    default_message = "The request was invalid."


class UpstreamError(LotScopeError):
    default_message = "An upstream data source failed."


class ConfigurationError(LotScopeError):
    default_message = "The application is misconfigured."


class AuthError(LotScopeError):
    default_message = "Authentication failed."


class ForbiddenError(LotScopeError):
    default_message = "You do not have permission to perform this action."


class QuotaExceededError(LotScopeError):
    default_message = "You have reached your plan's usage limit."
