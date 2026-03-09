"""Exception hierarchy for ARTA."""


class ARTAError(Exception):
    """Base exception."""
    pass


class AIServiceError(ARTAError):
    """AI provider errors."""
    pass


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
