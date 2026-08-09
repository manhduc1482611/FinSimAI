"""Endpoint nội bộ nhận nội dung giả lập do AI Engine sinh (news + social posts).

- Xác thực bằng ``X-Internal-Api-Key`` (cấu hình ``INTERNAL_API_KEY``) — không
  phải JWT của người dùng, AI Engine không có tài khoản.
- Normalise: symbol → ``company_id`` (thị trường chính, contest NULL),
  category tiếng Anh của ai_engine → tiếng Việt, ``has_deception`` → ``is_trap``.
- Dedupe: bỏ bài trùng title (news) / trùng content + persona (social) trong
  cửa sổ lookback, để cron của ai_engine chạy lặp lại không nhân đôi nội dung.
"""

import logging
import uuid as uuid_lib
from datetime import datetime, timedelta, timezone

from core.dependencies import get_db, require_internal_api_key
from fastapi import APIRouter, Depends, status
from models.company import Company
from models.news import News
from models.social import SocialPost
from schemas.ai_sync import (
    AiContentBatch,
    AiContentSyncResponse,
    AiNewsItem,
    AiSocialPostItem,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/ai/content",
    tags=["ai-sync"],
    dependencies=[Depends(require_internal_api_key)],
)

_CATEGORY_MAP = {
    "macro_domestic": "vĩ mô",
    "macro_international": "vĩ mô",
    "market_report": "thị trường",
    "company": "doanh nghiệp",
    "industry": "phân tích",
}

_DEDUPE_LOOKBACK_DAYS = 7


def _map_category(category: str) -> str:
    mapped = _CATEGORY_MAP.get(category.strip().lower())
    return mapped or (category.strip() or "vĩ mô")


async def _company_by_symbol(db: AsyncSession, symbol: str | None) -> uuid_lib.UUID | None:
    if not symbol:
        return None
    row = await db.execute(
        select(Company.id).where(
            Company.symbol == symbol,
            Company.contest_id.is_(None),
        )
    )
    return row.scalar_one_or_none()


async def _news_title_exists(db: AsyncSession, title: str) -> bool:
    since = datetime.now(timezone.utc) - timedelta(days=_DEDUPE_LOOKBACK_DAYS)
    row = await db.execute(
        select(News.id)
        .where(News.title == title, News.simulated_at >= since)
        .limit(1)
    )
    return row.scalar_one_or_none() is not None


async def _social_post_exists(db: AsyncSession, content: str) -> bool:
    since = datetime.now(timezone.utc) - timedelta(days=_DEDUPE_LOOKBACK_DAYS)
    row = await db.execute(
        select(SocialPost.id)
        .where(SocialPost.content == content, SocialPost.simulated_at >= since)
        .limit(1)
    )
    return row.scalar_one_or_none() is not None


@router.post(
    "",
    response_model=AiContentSyncResponse,
    status_code=status.HTTP_201_CREATED,
)
async def ingest_ai_content(
    body: AiContentBatch,
    db: AsyncSession = Depends(get_db),
) -> AiContentSyncResponse:
    now = datetime.now(timezone.utc)

    inserted_news = 0
    skipped_news = 0
    for item in body.articles:
        if await _news_title_exists(db, item.title):
            skipped_news += 1
            continue
        company_id = await _company_by_symbol(db, item.company_symbol)
        news = News(
            title=item.title,
            summary=item.summary,
            content=item.content,
            source=item.source,
            category=_map_category(item.category),
            sentiment=item.sentiment,
            impact_score=item.impact_score,
            company_id=company_id,
            is_ai_generated=True,
            simulated_at=item.simulated_at or now,
        )
        db.add(news)
        inserted_news += 1

    inserted_social = 0
    skipped_social = 0
    for item in body.social_posts:
        if await _social_post_exists(db, item.content):
            skipped_social += 1
            continue
        company_id = await _company_by_symbol(db, item.company_symbol)
        post = SocialPost(
            author_name=item.author_name,
            author_avatar=item.author_avatar,
            persona_type=item.persona_type,
            content=item.content,
            sentiment=item.sentiment,
            is_trap=item.has_deception,
            virality_score=item.virality_score,
            likes_count=0,
            shares_count=0,
            comments_count=0,
            company_id=company_id,
            simulated_at=item.simulated_at or now,
        )
        db.add(post)
        inserted_social += 1

    await db.commit()
    logger.info(
        "Ingested AI content: %d news (skipped %d), %d social posts (skipped %d)",
        inserted_news,
        skipped_news,
        inserted_social,
        skipped_social,
    )
    return AiContentSyncResponse(
        inserted_news=inserted_news,
        inserted_social_posts=inserted_social,
        skipped_news=skipped_news,
        skipped_social_posts=skipped_social,
    )
