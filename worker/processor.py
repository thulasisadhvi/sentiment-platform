import logging
from datetime import datetime, timezone # <--- Ensure timezone is imported
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.models.models import SocialMediaPost, SentimentAnalysis

logger = logging.getLogger(__name__)

async def save_post_and_analysis(
    db_session: AsyncSession,
    post_data: dict,
    sentiment_result: dict,
    emotion_result: dict
) -> tuple[int, int]:
    """
    Save post and analysis results to database with upsert logic.
    """
    try:
        # 1. Check if post already exists
        stmt = select(SocialMediaPost).filter_by(post_id=post_data['post_id'])
        result = await db_session.execute(stmt)
        post = result.scalar_one_or_none()

        if post:
            logger.info(f"🔄 Updating existing post: {post_data['post_id']}")
            post.ingested_at = datetime.utcnow()
        else:
            # --- TIMEZONE FIX START ---
            # Parse the ISO string (handling the 'Z' if present)
            try:
                dt_str = post_data['created_at'].replace('Z', '+00:00')
                dt_aware = datetime.fromisoformat(dt_str)
            except ValueError:
                # Fallback if format is different
                dt_aware = datetime.utcnow().replace(tzinfo=timezone.utc)

            # Convert to UTC and strip timezone info to make it "offset-naive"
            # This makes it compatible with PostgreSQL's TIMESTAMP WITHOUT TIME ZONE
            dt_naive = dt_aware.astimezone(timezone.utc).replace(tzinfo=None)
            # --- TIMEZONE FIX END ---

            post = SocialMediaPost(
                post_id=post_data['post_id'],
                source=post_data['source'],
                content=post_data['content'],
                author=post_data['author'],
                created_at=dt_naive  # <--- Use the fixed naive datetime
            )
            db_session.add(post)

        await db_session.flush()

        # 2. Create Analysis Record
        analysis = SentimentAnalysis(
            post_id=post.post_id,
            model_name=sentiment_result.get('model_name', 'unknown'),
            sentiment_label=sentiment_result.get('sentiment_label', 'neutral'),
            confidence_score=sentiment_result.get('confidence_score', 0.0),
            emotion=emotion_result.get('emotion', 'neutral')
        )
        db_session.add(analysis)

        await db_session.commit()
        await db_session.refresh(post)
        await db_session.refresh(analysis)

        return post.id, analysis.id

    except Exception as e:
        logger.error(f"❌ Database save failed: {e}")
        await db_session.rollback()
        # Don't re-raise, just log it so the worker keeps processing other messages
        return None, None