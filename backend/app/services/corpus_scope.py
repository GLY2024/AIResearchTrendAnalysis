"""Shared filters for the primary review corpus."""

from sqlalchemy import or_

from app.db.models import Paper


def primary_corpus_clause():
    """Exclude snowball-derived records from the default review corpus."""
    return or_(
        Paper.discovery_method.is_(None),
        ~Paper.discovery_method.like("%snowball%"),
    )
