"""Legacy snowball agent.

This implementation is retained for future work, but the current release
does not expose or execute snowball expansion in the user workflow.
"""

import json
import logging
import re
from collections import Counter

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.events import event_bus
from app.db.models import Paper, SearchPlan, SnowballCandidate, SnowballRun
from app.services.ai_service import ai_service
from app.services.paper_service import _normalize_title, paper_service
from app.sources.base import UnifiedPaper
from app.sources.registry import source_registry

logger = logging.getLogger(__name__)

DEFAULT_SNOWBALL_CONFIG = {
    "enabled": False,
    "approval_required": True,
    "approval_mode": "batch",  # batch, all
    "decision_mode": "manual_review",  # manual_review, all, high_confidence
    "max_hops": 1,
    "directions": ["forward"],
    "min_citation_threshold": 10,
    "max_seed_papers": 5,
    "per_seed_limit": 25,
    "max_candidates": 150,
    "verification_mode": "stable_identifier",  # none, stable_identifier, cross_source
    "ai_filter": {
        "enabled": True,
        "min_score": 0.55,
        "auto_import_score": 0.8,
    },
}


class SnowballAgent:
    """Performs staged forward/backward citation expansion."""

    def normalize_config(self, raw: dict | None) -> dict:
        raw = raw or {}
        ai_filter = raw.get("ai_filter") or {}
        merged = {
            **DEFAULT_SNOWBALL_CONFIG,
            **{k: v for k, v in raw.items() if k != "ai_filter"},
        }
        merged["directions"] = list(raw.get("directions") or DEFAULT_SNOWBALL_CONFIG["directions"])
        merged["ai_filter"] = {
            **DEFAULT_SNOWBALL_CONFIG["ai_filter"],
            **ai_filter,
        }
        merged["max_hops"] = max(1, int(merged["max_hops"]))
        merged["max_seed_papers"] = max(1, int(merged["max_seed_papers"]))
        merged["per_seed_limit"] = max(5, int(merged["per_seed_limit"]))
        merged["max_candidates"] = max(10, int(merged["max_candidates"]))
        merged["min_citation_threshold"] = max(0, int(merged["min_citation_threshold"]))
        merged["approval_required"] = bool(merged.get("approval_required", True))
        merged["enabled"] = bool(merged.get("enabled", False))
        return merged

    async def create_proposal(self, db: AsyncSession, plan: SearchPlan) -> SnowballRun | None:
        """Create a proposal after the main search finishes."""
        config = self.normalize_config(plan.plan_data.get("snowball_config"))
        if not config.get("enabled"):
            return None

        seeds = await self._get_seed_papers(db, plan.session_id, config["max_seed_papers"])
        if not seeds:
            await event_bus.emit("snowball_proposed", {
                "plan_id": plan.id,
                "status": "unavailable",
                "message": "Snowball is enabled, but no eligible OpenAlex seed papers were found.",
            }, session_id=str(plan.session_id))
            return None

        proposal_summary = {
            "topic": plan.plan_data.get("topic", ""),
            "decision_mode": config["decision_mode"],
            "approval_mode": config["approval_mode"],
            "verification_mode": config["verification_mode"],
            "estimated_candidate_budget": (
                len(seeds) * config["per_seed_limit"] * len(config["directions"]) * config["max_hops"]
            ),
            "seed_papers": [
                {
                    "paper_id": paper.id,
                    "title": paper.title,
                    "year": paper.year,
                    "citation_count": paper.citation_count,
                }
                for paper in seeds
            ],
        }

        run = SnowballRun(
            session_id=plan.session_id,
            plan_id=plan.id,
            status="proposed",
            config=config,
            proposal_summary=proposal_summary,
            stats={},
        )
        db.add(run)
        await db.commit()
        await db.refresh(run)

        await event_bus.emit("snowball_proposed", {
            "run_id": run.id,
            "plan_id": plan.id,
            "status": run.status,
            "config": run.config,
            "proposal_summary": run.proposal_summary,
        }, session_id=str(plan.session_id))
        return run

    async def apply_action(
        self,
        db: AsyncSession,
        run: SnowballRun,
        action: str,
        config_updates: dict | None = None,
        candidate_ids: list[int] | None = None,
    ) -> SnowballRun:
        """Apply a snowball decision."""
        if config_updates:
            run.config = self.normalize_config({**(run.config or {}), **config_updates})
            await db.commit()
            await db.refresh(run)

        if action == "reject":
            run.status = "rejected"
            await db.commit()
            await event_bus.emit("snowball_rejected", {
                "run_id": run.id,
                "plan_id": run.plan_id,
            }, session_id=str(run.session_id))
            return run

        if action in {"prepare_review", "approve_all", "approve_high_confidence"}:
            run = await self.stage_candidates(db, run)
            if action == "prepare_review":
                return run
            if action == "approve_all":
                await self.import_candidates(db, run)
                return run
            if action == "approve_high_confidence":
                threshold = float(run.config.get("ai_filter", {}).get("auto_import_score", 0.8))
                await self.import_candidates(db, run, min_score=threshold)
                return run

        if action == "approve_selected":
            await self.import_candidates(db, run, candidate_ids=candidate_ids or [])
            return run

        if action == "reject_selected":
            if candidate_ids:
                result = await db.execute(
                    select(SnowballCandidate).where(
                        SnowballCandidate.run_id == run.id,
                        SnowballCandidate.id.in_(candidate_ids),
                    )
                )
                for candidate in result.scalars().all():
                    candidate.status = "rejected"
                await db.commit()
            await event_bus.emit("snowball_review_updated", {
                "run_id": run.id,
                "status": run.status,
            }, session_id=str(run.session_id))
            return run

        raise ValueError(f"Unsupported snowball action: {action}")

    async def stage_candidates(self, db: AsyncSession, run: SnowballRun) -> SnowballRun:
        """Collect, dedupe, score, verify, and stage snowball candidates."""
        run.status = "running"
        run.stats = {}
        await db.commit()

        await event_bus.emit("snowball_progress", {
            "run_id": run.id,
            "plan_id": run.plan_id,
            "step": "collecting",
            "progress": 0.1,
        }, session_id=str(run.session_id))

        await db.execute(delete(SnowballCandidate).where(SnowballCandidate.run_id == run.id))
        await db.commit()

        config = self.normalize_config(run.config)
        seeds = await self._get_seed_papers(db, run.session_id, config["max_seed_papers"])
        staged = await self._collect_candidates(db, run, seeds, config)

        await event_bus.emit("snowball_progress", {
            "run_id": run.id,
            "plan_id": run.plan_id,
            "step": "screening",
            "progress": 0.45,
            "candidate_count": len(staged),
        }, session_id=str(run.session_id))

        plan = await db.get(SearchPlan, run.plan_id)
        topic = plan.plan_data.get("topic", "") if plan else ""

        scored = await self._score_candidates(topic, plan.plan_data if plan else {}, staged, config)

        await event_bus.emit("snowball_progress", {
            "run_id": run.id,
            "plan_id": run.plan_id,
            "step": "verifying",
            "progress": 0.7,
            "candidate_count": len(scored),
        }, session_id=str(run.session_id))

        for record in scored:
            verification_status, verification_sources = await self._verify_candidate(record["paper"], config)
            candidate = SnowballCandidate(
                run_id=run.id,
                seed_paper_id=record["seed_paper_id"],
                direction=record["direction"],
                hop=record["hop"],
                title=record["paper"].title,
                abstract=record["paper"].abstract,
                authors=record["paper"].authors,
                journal=record["paper"].journal,
                year=record["paper"].year,
                publication_date=record["paper"].publication_date,
                doi=record["paper"].doi,
                arxiv_id=record["paper"].arxiv_id,
                openalex_id=record["paper"].openalex_id,
                scopus_id=record["paper"].scopus_id,
                url=record["paper"].url,
                pdf_url=record["paper"].pdf_url,
                citation_count=record["paper"].citation_count,
                reference_count=record["paper"].reference_count,
                keywords=record["paper"].keywords,
                fields=record["paper"].fields,
                paper_type=record["paper"].paper_type,
                source_name=record["paper"].source_name or "openalex",
                relevance_score=record["score"],
                relevance_reason=record["reason"],
                verification_status=verification_status,
                verification_sources=verification_sources,
                duplicate_reason="",
                status="pending",
            )
            db.add(candidate)

        stats = await self._compute_stats(db, run.id, config)
        run.status = "awaiting_review"
        run.stats = stats
        await db.commit()
        await db.refresh(run)

        await event_bus.emit("snowball_review_ready", {
            "run_id": run.id,
            "plan_id": run.plan_id,
            "status": run.status,
            "stats": run.stats,
            "config": run.config,
        }, session_id=str(run.session_id))
        return run

    async def import_candidates(
        self,
        db: AsyncSession,
        run: SnowballRun,
        min_score: float | None = None,
        candidate_ids: list[int] | None = None,
    ) -> int:
        """Import approved snowball candidates into the paper library."""
        stmt = select(SnowballCandidate).where(SnowballCandidate.run_id == run.id)
        if candidate_ids:
            stmt = stmt.where(SnowballCandidate.id.in_(candidate_ids))
        else:
            stmt = stmt.where(SnowballCandidate.status == "pending")
        result = await db.execute(stmt)
        candidates = result.scalars().all()

        config = self.normalize_config(run.config)
        min_threshold = float(min_score if min_score is not None else config["ai_filter"]["min_score"])

        importable: list[UnifiedPaper] = []
        imported_candidate_ids: list[int] = []
        for candidate in candidates:
            if candidate.status == "rejected":
                continue
            if candidate.relevance_score is not None and candidate.relevance_score < min_threshold:
                continue
            if config["verification_mode"] != "none" and candidate.verification_status == "failed":
                continue

            importable.append(self._candidate_to_unified(candidate))
            imported_candidate_ids.append(candidate.id)

        saved = await paper_service.save_papers(
            db,
            run.session_id,
            importable,
            discovery_method="snowball",
        )

        if imported_candidate_ids:
            imported_result = await db.execute(
                select(SnowballCandidate).where(SnowballCandidate.id.in_(imported_candidate_ids))
            )
            for candidate in imported_result.scalars().all():
                candidate.status = "imported"

        if candidate_ids:
            remaining_stmt = select(SnowballCandidate).where(
                SnowballCandidate.run_id == run.id,
                SnowballCandidate.status == "pending",
            )
            remaining = (await db.execute(remaining_stmt)).scalars().all()
            run.status = "awaiting_review" if remaining else "completed"
        else:
            run.status = "completed"

        run.stats = {
            **(run.stats or {}),
            "imported_count": (run.stats or {}).get("imported_count", 0) + saved,
        }
        await db.commit()
        await db.refresh(run)

        await event_bus.emit("snowball_complete", {
            "run_id": run.id,
            "plan_id": run.plan_id,
            "imported_count": saved,
            "status": run.status,
        }, session_id=str(run.session_id))
        return saved

    async def _collect_candidates(
        self,
        db: AsyncSession,
        run: SnowballRun,
        seeds: list[Paper],
        config: dict,
    ) -> list[dict]:
        source = source_registry.get("openalex")
        if not source:
            raise RuntimeError("OpenAlex source is required for snowball.")

        staged: dict[str, dict] = {}
        max_candidates = config["max_candidates"]
        current_level = [
            {"seed_paper_id": paper.id, "openalex_id": paper.openalex_id, "title": paper.title}
            for paper in seeds
            if paper.openalex_id
        ]

        visited_openalex_ids = {paper.openalex_id for paper in seeds if paper.openalex_id}

        for hop in range(1, config["max_hops"] + 1):
            next_level: list[dict] = []
            for current in current_level:
                for direction in config["directions"]:
                    related = await self._fetch_related(
                        source,
                        current["openalex_id"],
                        direction,
                        config["per_seed_limit"],
                        config["min_citation_threshold"],
                    )
                    for unified in related:
                        key = self._candidate_key(unified)
                        if not key or key in staged:
                            continue
                        if await paper_service._is_duplicate(db, run.session_id, unified):
                            continue
                        staged[key] = {
                            "seed_paper_id": current["seed_paper_id"],
                            "direction": direction,
                            "hop": hop,
                            "paper": unified,
                        }
                        if unified.openalex_id and unified.openalex_id not in visited_openalex_ids:
                            visited_openalex_ids.add(unified.openalex_id)
                            next_level.append({
                                "seed_paper_id": current["seed_paper_id"],
                                "openalex_id": unified.openalex_id,
                                "title": unified.title,
                            })
                        if len(staged) >= max_candidates:
                            break
                    if len(staged) >= max_candidates:
                        break
                if len(staged) >= max_candidates:
                    break
            if len(staged) >= max_candidates or not next_level:
                break
            current_level = next_level

        return list(staged.values())

    async def _fetch_related(
        self,
        source,
        openalex_id: str,
        direction: str,
        per_seed_limit: int,
        min_citation_threshold: int,
    ) -> list[UnifiedPaper]:
        if direction == "forward":
            related = await source.get_citations(openalex_id)
            related = [paper for paper in related if paper.citation_count >= min_citation_threshold]
        else:
            related = await source.get_references(openalex_id)
        related.sort(key=lambda paper: paper.citation_count, reverse=True)
        return related[:per_seed_limit]

    async def _get_seed_papers(self, db: AsyncSession, session_id: int, limit: int) -> list[Paper]:
        result = await db.execute(
            select(Paper)
            .where(Paper.session_id == session_id)
            .where(Paper.discovery_method == "search")
            .where(Paper.is_included == True)
            .where(Paper.openalex_id.is_not(None))
            .order_by(Paper.citation_count.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def _score_candidates(
        self,
        topic: str,
        plan_data: dict,
        candidates: list[dict],
        config: dict,
    ) -> list[dict]:
        heuristic_scores = [self._heuristic_score(topic, plan_data, candidate["paper"]) for candidate in candidates]
        for candidate, (score, reason) in zip(candidates, heuristic_scores):
            candidate["score"] = score
            candidate["reason"] = reason

        if not config.get("ai_filter", {}).get("enabled", True) or not candidates:
            return candidates

        batch_size = 8
        for start in range(0, len(candidates), batch_size):
            batch = candidates[start:start + batch_size]
            try:
                ai_scores = await self._ai_score_batch(topic, plan_data, batch)
            except Exception as exc:
                logger.warning(f"Snowball AI scoring failed, falling back to heuristic: {exc}")
                continue

            for index, candidate in enumerate(batch):
                ai_score = ai_scores.get(index)
                if not ai_score:
                    continue
                candidate["score"] = max(candidate["score"], ai_score["score"])
                candidate["reason"] = ai_score["reason"]

        return candidates

    async def _ai_score_batch(self, topic: str, plan_data: dict, batch: list[dict]) -> dict[int, dict]:
        inclusion = plan_data.get("inclusion_criteria") or []
        exclusion = plan_data.get("exclusion_criteria") or []
        payload = [
            {
                "index": index,
                "title": candidate["paper"].title,
                "abstract": candidate["paper"].abstract[:1000],
                "keywords": candidate["paper"].keywords[:8],
                "year": candidate["paper"].year,
            }
            for index, candidate in enumerate(batch)
        ]
        messages = [
            {
                "role": "system",
                "content": (
                    "You are screening candidate snowball papers for a literature review. "
                    "Return JSON only. For each candidate, assign a relevance score from 0 to 1 "
                    "and a one-sentence reason. Focus on topical fit to the stated research topic. "
                    "Reject papers that drift into adjacent but different fields."
                ),
            },
            {
                "role": "user",
                "content": json.dumps({
                    "topic": topic,
                    "description": plan_data.get("description", ""),
                    "inclusion_criteria": inclusion,
                    "exclusion_criteria": exclusion,
                    "candidates": payload,
                }, ensure_ascii=False),
            },
        ]

        response = await ai_service.chat(messages, role="analyst", temperature=0.1, max_tokens=1200)
        parsed = self._extract_json(response)
        if not isinstance(parsed, list):
            raise ValueError("Snowball AI scoring did not return a list.")

        scores: dict[int, dict] = {}
        for item in parsed:
            try:
                scores[int(item["index"])] = {
                    "score": max(0.0, min(1.0, float(item["score"]))),
                    "reason": str(item.get("reason", "")).strip()[:240],
                }
            except (KeyError, ValueError, TypeError):
                continue
        return scores

    def _heuristic_score(self, topic: str, plan_data: dict, paper: UnifiedPaper) -> tuple[float, str]:
        topic_terms = self._tokenize(" ".join([
            topic,
            plan_data.get("description", ""),
            " ".join(plan_data.get("inclusion_criteria") or []),
        ]))
        haystack = self._tokenize(" ".join([
            paper.title,
            paper.abstract[:1500],
            " ".join(paper.keywords or []),
            " ".join(paper.fields or []),
        ]))
        if not topic_terms:
            return 0.5, "No topic terms were available, so the heuristic score is neutral."

        overlap = len(topic_terms & haystack)
        score = min(1.0, overlap / max(4, len(topic_terms) * 0.35))
        if overlap >= 5:
            return round(max(score, 0.85), 3), "High lexical overlap with the session topic and criteria."
        if overlap >= 3:
            return round(max(score, 0.68), 3), "Moderate lexical overlap with the current session topic."
        if overlap >= 2:
            return round(max(score, 0.5), 3), "Limited overlap; candidate may be adjacent rather than central."
        return round(score, 3), "Low topical overlap with the current session topic."

    async def _verify_candidate(self, paper: UnifiedPaper, config: dict) -> tuple[str, list[str]]:
        mode = config.get("verification_mode", "stable_identifier")
        if mode == "none":
            return "verified", ["none"]

        sources: list[str] = []
        if paper.openalex_id:
            sources.append("openalex")
        if mode == "stable_identifier":
            if paper.doi or paper.openalex_id or paper.arxiv_id or paper.scopus_id:
                return "verified", sources or ["identifier"]
            return "failed", []

        if paper.scopus_id:
            sources.append("scopus")
        if paper.arxiv_id:
            sources.append("arxiv")

        if paper.doi:
            scopus = source_registry.get("scopus")
            if scopus and await scopus.is_available():
                try:
                    verified = await scopus.get_paper_by_id(paper.doi)
                    if verified:
                        sources.append("scopus")
                except Exception as exc:
                    logger.debug(f"Snowball Scopus verification failed for DOI {paper.doi}: {exc}")

        unique_sources = sorted(set(sources))
        return ("verified" if len(unique_sources) >= 2 else "failed"), unique_sources

    async def _compute_stats(self, db: AsyncSession, run_id: int, config: dict) -> dict:
        result = await db.execute(
            select(SnowballCandidate).where(SnowballCandidate.run_id == run_id)
        )
        candidates = result.scalars().all()

        threshold = float(config["ai_filter"]["auto_import_score"])
        direction_counts = Counter(candidate.direction for candidate in candidates)
        verified_count = sum(1 for candidate in candidates if candidate.verification_status == "verified")
        high_confidence_count = sum(
            1 for candidate in candidates
            if (candidate.relevance_score or 0) >= threshold
        )

        return {
            "candidate_count": len(candidates),
            "verified_count": verified_count,
            "high_confidence_count": high_confidence_count,
            "direction_counts": dict(direction_counts),
        }

    def _candidate_to_unified(self, candidate: SnowballCandidate) -> UnifiedPaper:
        return UnifiedPaper(
            title=candidate.title,
            abstract=candidate.abstract or "",
            authors=candidate.authors or [],
            journal=candidate.journal or "",
            year=candidate.year,
            publication_date=candidate.publication_date or "",
            doi=candidate.doi or "",
            arxiv_id=candidate.arxiv_id or "",
            openalex_id=candidate.openalex_id or "",
            scopus_id=candidate.scopus_id or "",
            url=candidate.url or "",
            pdf_url=candidate.pdf_url or "",
            citation_count=candidate.citation_count or 0,
            reference_count=candidate.reference_count or 0,
            keywords=candidate.keywords or [],
            fields=candidate.fields or [],
            paper_type=candidate.paper_type or "",
            source_name=candidate.source_name or "openalex",
        )

    @staticmethod
    def _candidate_key(paper: UnifiedPaper) -> str:
        if paper.doi:
            return f"doi:{paper.doi.lower()}"
        if paper.openalex_id:
            return f"openalex:{paper.openalex_id}"
        if paper.arxiv_id:
            return f"arxiv:{paper.arxiv_id}"
        if paper.scopus_id:
            return f"scopus:{paper.scopus_id}"
        if paper.title:
            return f"title:{_normalize_title(paper.title)}:{paper.year or 0}"
        return ""

    @staticmethod
    def _tokenize(text: str) -> set[str]:
        tokens = {
            token
            for token in re.split(r"[^a-zA-Z0-9\u4e00-\u9fff]+", text.lower())
            if len(token) >= 3
        }
        stopwords = {
            "and", "the", "for", "with", "from", "into", "under", "study", "using",
            "analysis", "research", "based", "review", "this", "that", "field",
        }
        return {token for token in tokens if token not in stopwords}

    @staticmethod
    def _extract_json(text: str):
        text = text.strip()
        if "```json" in text:
            text = text.split("```json", 1)[1].split("```", 1)[0].strip()
        elif "```" in text:
            text = text.split("```", 1)[1].split("```", 1)[0].strip()
        return json.loads(text)


snowball_agent = SnowballAgent()
