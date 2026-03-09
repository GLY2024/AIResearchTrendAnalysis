"""Source registry for managing data source plugins."""

import logging

from app.sources.base import BaseDataSource

logger = logging.getLogger(__name__)


class SourceRegistry:
    """Registry for data source plugins."""

    def __init__(self):
        self._sources: dict[str, BaseDataSource] = {}

    def register(self, source: BaseDataSource):
        self._sources[source.name] = source
        logger.info(f"Registered data source: {source.name}")

    def get(self, name: str) -> BaseDataSource | None:
        return self._sources.get(name)

    def list_sources(self) -> list[str]:
        return list(self._sources.keys())

    async def get_available(self) -> list[BaseDataSource]:
        available = []
        for source in self._sources.values():
            if await source.is_available():
                available.append(source)
        return available

    async def status(self) -> dict[str, bool]:
        return {
            name: await source.is_available()
            for name, source in self._sources.items()
        }


source_registry = SourceRegistry()
