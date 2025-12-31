import os
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.models import SocialMediaPost, SentimentAnalysis, SentimentAlert

logger = logging.getLogger(__name__)

class AlertService:
    """
    Monitors sentiment metrics and triggers alerts on anomalies.
   
    """
    
    def __init__(self, db_session_maker, redis_client=None):
        """
        Initialize with configuration from environment variables.
        """
        self.db_session_maker = db_session_maker
        self.redis = redis_client # Optional, for caching alert state if needed
        
        # Load Configuration
        self.threshold_ratio = float(os.getenv("ALERT_NEGATIVE_RATIO_THRESHOLD", "2.0"))
        self.window_minutes = int(os.getenv("ALERT_WINDOW_MINUTES", "5"))
        self.min_posts = int(os.getenv("ALERT_MIN_POSTS", "10"))

    async def check_thresholds(self) -> Optional[dict]:
        """
        Check if current sentiment metrics exceed alert thresholds.
        """
        now = datetime.utcnow()
        window_start = now - timedelta(minutes=self.window_minutes)
        
        async with self.db_session_maker() as session:
            try:
                # 1. Count sentiments in the last N minutes
                #
                stmt = select(
                    SentimentAnalysis.sentiment_label,
                    func.count(SentimentAnalysis.id)
                ).join(SocialMediaPost)\
                 .filter(SocialMediaPost.created_at >= window_start)\
                 .group_by(SentimentAnalysis.sentiment_label)
                
                result = await session.execute(stmt)
                counts = {row[0]: row[1] for row in result.all()}
                
                pos_count = counts.get("positive", 0)
                neg_count = counts.get("negative", 0)
                neu_count = counts.get("neutral", 0)
                total_posts = pos_count + neg_count + neu_count

                # 2. Minimum Data Check
                if total_posts < self.min_posts:
                    return None

                # 3. Calculate Ratio
                # Avoid division by zero
                if pos_count == 0:
                    ratio = float('inf') if neg_count > 0 else 0.0
                else:
                    ratio = neg_count / pos_count

                # 4. Threshold Check
                if ratio > self.threshold_ratio:
                    logger.warning(f"🚨 ALERT TRIGGERED: Ratio {ratio:.2f} exceeds {self.threshold_ratio}")
                    return {
                        "alert_triggered": True,
                        "alert_type": "high_negative_ratio",
                        "threshold": self.threshold_ratio,
                        "actual_value": round(ratio, 2), # Matches actual_ratio in doc
                        "window_start": window_start,
                        "window_end": now,
                        "post_count": total_posts,
                        "metrics": {
                            "positive_count": pos_count,
                            "negative_count": neg_count,
                            "neutral_count": neu_count,
                            "total_count": total_posts
                        },
                        "timestamp": now.isoformat()
                    }
                
                return None

            except Exception as e:
                logger.error(f"Error checking thresholds: {e}")
                return None

    async def save_alert(self, alert_data: dict) -> int:
        """
        Save alert to database.
        """
        async with self.db_session_maker() as session:
            try:
                # Map dict to SQLAlchemy Model
                # - Table 3
                new_alert = SentimentAlert(
                    alert_type=alert_data["alert_type"],
                    threshold_value=alert_data["threshold"],
                    actual_value=alert_data["actual_value"],
                    window_start=alert_data["window_start"],
                    window_end=alert_data["window_end"],
                    post_count=alert_data["post_count"],
                    details=alert_data["metrics"], # Saving metrics JSON into details column
                    triggered_at=datetime.fromisoformat(alert_data["timestamp"])
                )
                
                session.add(new_alert)
                await session.commit()
                await session.refresh(new_alert)
                
                logger.info(f"✅ Alert saved to DB with ID: {new_alert.id}")
                return new_alert.id
                
            except Exception as e:
                logger.error(f"Failed to save alert: {e}")
                await session.rollback()
                return -1

    async def run_monitoring_loop(self, check_interval_seconds: int = 60):
        """
        Continuously monitor and trigger alerts.
        """
        logger.info(f"👀 Alert Monitoring started. Checking every {check_interval_seconds}s...")
        
        while True:
            try:
                # 1. Check
                alert = await self.check_thresholds()
                
                # 2. Save if triggered
                if alert:
                    await self.save_alert(alert)
                
                # 3. Sleep
                await asyncio.sleep(check_interval_seconds)
                
            except asyncio.CancelledError:
                logger.info("Monitoring loop cancelled")
                break
            except Exception as e:
                logger.error(f"Unexpected error in monitoring loop: {e}")
                await asyncio.sleep(check_interval_seconds)