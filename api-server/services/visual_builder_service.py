"""
services/visual_builder_service.py — Plan E1 business logic.

Every AI call goes through `llm_stub` so this works without any external
provider. Public functions are async and accept an AsyncSession so they
can be called from FastAPI routes without ceremony.
"""
from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.visual_builder import (
    VisualBuild,
    VisualBuildAsset,
    VisualBuildHistory,
    VisualBuildReview,
    VisualBuildStatus,
)
from services.llm_stub import (
    LLMConfig,
    generate_bullets,
    generate_text,
    seo_score,
)
from services.llm_stub import (
    translate as llm_translate,
)

CFG = LLMConfig()


# ─────────────────────────────── Description ────────────────────────────────

async def generate_description(
    session: AsyncSession,
    *,
    store_id: int,
    product_name: str,
    category: str | None = None,
    tone: str = "premium",
    actor_id: int | None = None,
) -> VisualBuild:
    prompt = f"{product_name} | category={category or 'general'} | tone={tone}"
    short = generate_text(prompt, max_chars=140)
    long_text = generate_text(prompt + " long", max_chars=900)
    bullets = generate_bullets(prompt, n=4)

    build = VisualBuild(
        store_id=store_id,
        locale_default="fr",
        description_short=short,
        description_long=long_text,
        bullets=bullets,
        status=VisualBuildStatus.DRAFT,
        model_version=CFG.model,
        created_by=actor_id,
        translations={},
        glossary={},
    )
    session.add(build)
    await session.flush()
    await _record_history(session, store_id, build.id, actor_id, "generate_description",
                          before=None, after={"short": short, "long": long_text, "bullets": bullets})
    return build


# ─────────────────────────────── Photos (AI enhancement stub) ───────────────

async def enhance_photos(
    session: AsyncSession,
    *,
    build_id: int,
    store_id: int,
    image_urls: list[str],
    backgrounds: list[str] | None = None,
    actor_id: int | None = None,
) -> list[VisualBuildAsset]:
    """Pretend to call the vision model; in stub mode we just copy URLs through
    with deterministic alt-text generation."""
    out: list[VisualBuildAsset] = []
    for idx, url in enumerate(image_urls):
        alt = generate_text(f"alt for {url}", max_chars=110)
        asset = VisualBuildAsset(
            build_id=build_id,
            kind="enhanced" if idx > 0 else "photo",
            url=url,
            alt_text=alt,
            order=idx,
            is_primary=(idx == 0),
            ai_metadata={
                "background": backgrounds[idx] if backgrounds and idx < len(backgrounds) else None,
                "model": CFG.model,
                "processed_at": datetime.now(UTC).isoformat(),
            },
        )
        session.add(asset)
        out.append(asset)
    await session.flush()
    await _record_history(session, store_id, build_id, actor_id, "enhance_photos",
                          before=None, after={"assets": [a.url for a in out]})
    return out


# ─────────────────────────────── SEO ───────────────────────────────────────

async def generate_seo(
    session: AsyncSession,
    *,
    build: VisualBuild,
    target_locale: str = "fr",
    keywords: list[str] | None = None,
    actor_id: int | None = None,
) -> VisualBuild:
    keywords = keywords or []
    prompt = f"seo for {build.description_short or ''}"
    title = generate_text(prompt + " title", max_chars=70)
    meta = generate_text(prompt + " meta", max_chars=170)
    og = {"title": title, "description": meta, "image": None}
    score = seo_score(title, meta, keywords)

    build.seo_title = title
    build.seo_meta = meta
    build.seo_keywords = keywords
    build.seo_og = og
    build.seo_score = score
    await session.flush()
    await _record_history(session, build.store_id, build.id, actor_id, "generate_seo",
                          before=None, after={"title": title, "meta": meta, "score": score,
                                              "keywords": keywords})
    return build


# ─────────────────────────────── Traductions ───────────────────────────────

async def translate_content(
    session: AsyncSession,
    *,
    build: VisualBuild,
    target_locales: list[str],
    glossary: dict | None = None,
    actor_id: int | None = None,
) -> VisualBuild:
    glossary = glossary or {}
    translations = dict(build.translations or {})
    for locale in target_locales:
        existing = translations.get(locale, {})
        existing["description_short"] = llm_translate(build.description_short or "", locale, glossary)
        existing["description_long"] = llm_translate(build.description_long or "", locale, glossary)
        existing["seo_title"] = llm_translate(build.seo_title or "", locale, glossary)
        existing["seo_meta"] = llm_translate(build.seo_meta or "", locale, glossary)
        existing["bullets"] = [
            llm_translate(b, locale, glossary) for b in (build.bullets or [])
        ]
        translations[locale] = existing
    build.translations = translations
    build.glossary = glossary
    await session.flush()
    await _record_history(session, build.store_id, build.id, actor_id, "translate_content",
                          before=None, after={"locales": target_locales})
    return build


# ─────────────────────────────── Validation humaine ────────────────────────

async def submit_for_review(
    session: AsyncSession, *, build: VisualBuild, actor_id: int | None
) -> VisualBuild:
    build.status = VisualBuildStatus.PENDING_REVIEW
    await session.flush()
    await _record_history(session, build.store_id, build.id, actor_id,
                          "submit_for_review", None, {"status": build.status.value})
    return build


async def review_build(
    session: AsyncSession,
    *,
    build: VisualBuild,
    reviewer_id: int,
    decision: str,
    comments: str | None,
) -> VisualBuild:
    if decision not in {"approve", "reject", "changes_requested"}:
        raise ValueError(f"Invalid decision: {decision}")
    new_status = {
        "approve": VisualBuildStatus.APPROVED,
        "reject": VisualBuildStatus.REJECTED,
        "changes_requested": VisualBuildStatus.CHANGES_REQUESTED,
    }[decision]
    preview_before = {
        "status": build.status.value,
        "description_short": build.description_short,
        "seo_title": build.seo_title,
    }
    build.status = new_status
    review = VisualBuildReview(
        build_id=build.id,
        reviewer_id=reviewer_id,
        decision=decision,
        comments=comments,
        diff={"before": preview_before, "after": {"status": new_status.value}},
    )
    session.add(review)
    await session.flush()
    await _record_history(session, build.store_id, build.id, reviewer_id,
                          f"review:{decision}", preview_before, {"status": new_status.value})
    return build


async def publish(
    session: AsyncSession, *, build: VisualBuild, actor_id: int | None
) -> VisualBuild:
    if build.status not in {VisualBuildStatus.APPROVED, VisualBuildStatus.PENDING_REVIEW}:
        # Allow direct publish after approval only.
        from fastapi import HTTPException
        raise HTTPException(status_code=409, detail="Build must be approved before publish")
    build.status = VisualBuildStatus.PUBLISHED
    await session.flush()
    await _record_history(session, build.store_id, build.id, actor_id,
                          "publish", None, {"status": build.status.value})
    return build


# ─────────────────────────────── Historique ────────────────────────────────

async def list_history(
    session: AsyncSession, *, store_id: int, build_id: int, limit: int = 100
) -> list[VisualBuildHistory]:
    res = await session.execute(
        select(VisualBuildHistory)
        .where(VisualBuildHistory.store_id == store_id,
               VisualBuildHistory.build_id == build_id)
        .order_by(VisualBuildHistory.created_at.desc())
        .limit(limit)
    )
    return list(res.scalars().all())


async def _record_history(
    session: AsyncSession,
    store_id: int,
    build_id: int,
    actor_id: int | None,
    action: str,
    before: dict | None,
    after: dict | None,
) -> None:
    row = VisualBuildHistory(
        store_id=store_id,
        build_id=build_id,
        actor_id=actor_id,
        action=action,
        before=before or {},
        after=after or {},
        model_version=CFG.model,
    )
    session.add(row)
    await session.flush()
