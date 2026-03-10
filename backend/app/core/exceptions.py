"""Exception hierarchy for ARTA."""


class ARTAError(Exception):
    """Base exception."""
    pass


class AIServiceError(ARTAError):
    """AI provider errors."""

    def __init__(
        self,
        message: str,
        *,
        error_code: str = "",
        status_code: int | None = None,
        retryable: bool | None = None,
    ):
        super().__init__(message)
        self.error_code = error_code
        self.status_code = status_code
        self.retryable = retryable


class DataSourceError(ARTAError):
    """Data source fetch errors."""
    pass


class SearchError(ARTAError):
    """Search execution errors."""
    pass


class AnalysisError(ARTAError):
    """Analysis computation errors."""
    pass


class ExportError(ARTAError):
    """Export/Zotero errors."""
    pass


class ConfigError(ARTAError):
    """Configuration errors."""
    pass
