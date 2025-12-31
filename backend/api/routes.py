import os
import json
import redis
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session
from sqlalchemy import desc, func, text

# Make sure these paths match your actual folder structure
from backend.models.database import get_db
from backend.models.models import SocialMediaPost, SentimentAnalysis

from fastapi import WebSocket, WebSocketDisconnect
from backend.models.database import SessionLocal
from backend.api.websocket_manager import manager

router = APIRouter()

# Initialize Redis client for the backend
redis_pool = redis.ConnectionPool(
    host=os.getenv("REDIS_HOST", "redis"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    decode_responses=True
)
redis_client = redis.Redis(connection_pool=redis_pool)

@router.websocket("/ws/sentiment")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time sentiment updates.
   
    """
    await manager.connect(websocket)
    
    # 1. Send Initial Connection Confirmation (Type 1)
    await websocket.send_json({
        "type": "connected",
        "message": "Connected to sentiment stream",
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    })

    last_metrics_update = datetime.utcnow()
    # Start tracking from the latest post to avoid re-sending old history
    # We use a new DB session for the setup
    with SessionLocal() as db:
        last_post_id = db.query(func.max(SocialMediaPost.id)).scalar() or 0

    try:
        while True:
            # 2. Check for New Posts (Type 2)
            # We poll the DB every 1 second for new data
            with SessionLocal() as db:
                # Get any posts newer than what we've seen
                new_posts = db.query(SocialMediaPost).join(SentimentAnalysis)\
                              .filter(SocialMediaPost.id > last_post_id)\
                              .order_by(SocialMediaPost.id.asc())\
                              .all()

                for post in new_posts:
                    analysis = post.analysis
                    post_data = {
                        "type": "new_post",
                        "data": {
                            "post_id": post.post_id,
                            "content": post.content[:100] + "..." if len(post.content) > 100 else post.content,
                            "source": post.source,
                            "sentiment_label": analysis.sentiment_label,
                            "confidence_score": analysis.confidence_score,
                            "emotion": analysis.emotion,
                            "timestamp": post.created_at.isoformat()
                        }
                    }
                    await websocket.send_json(post_data)
                    last_post_id = post.id # Update tracker
            
            # 3. Check for Metrics Update (Type 3) - Every 30 seconds
            now = datetime.utcnow()
            if (now - last_metrics_update).total_seconds() >= 30:
                with SessionLocal() as db:
                    metrics_data = {
                        "type": "metrics_update",
                        "data": {
                            "last_minute": _get_metrics(db, 1), # Helper function
                            "last_hour": _get_metrics(db, 60),
                            "last_24_hours": _get_metrics(db, 1440)
                        },
                        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
                    }
                    await websocket.send_json(metrics_data)
                    last_metrics_update = now

            # Sleep to prevent blocking the thread
            await asyncio.sleep(1)

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        print(f"WebSocket Error: {e}")
        manager.disconnect(websocket)

def _get_metrics(db: Session, minutes: int):
    """Helper to calculate metrics for a specific time window"""
    time_threshold = datetime.utcnow() - timedelta(minutes=minutes)
    
    results = db.query(
        SentimentAnalysis.sentiment_label,
        func.count(SentimentAnalysis.id)
    ).join(SocialMediaPost)\
     .filter(SocialMediaPost.created_at >= time_threshold)\
     .group_by(SentimentAnalysis.sentiment_label).all()
     
    counts = {label: count for label, count in results}
    total = sum(counts.values())
    
    return {
        "positive": counts.get("positive", 0),
        "negative": counts.get("negative", 0),
        "neutral": counts.get("neutral", 0),
        "total": total
    }
@router.get("/sentiment/distribution")
async def get_sentiment_distribution(
    hours: int = Query(24, ge=1, le=168),
    source: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """
    Get current sentiment distribution for dashboard.
   
    """
    
    # 1. Check Redis Cache
    cache_key = f"dist:{hours}:{source or 'all'}"
    cached_data = redis_client.get(cache_key)
    
    if cached_data:
        data = json.loads(cached_data)
        data["cached"] = True
        return data

    # 2. Calculate Time Threshold
    time_threshold = datetime.utcnow() - timedelta(hours=hours)

    # 3. Build Base Query
    base_query = db.query(SentimentAnalysis).join(SocialMediaPost)\
                   .filter(SocialMediaPost.created_at >= time_threshold)
    
    if source:
        base_query = base_query.filter(SocialMediaPost.source == source)

    # 4. Count Sentiments
    sentiment_results = base_query.with_entities(
        SentimentAnalysis.sentiment_label,
        func.count(SentimentAnalysis.id)
    ).group_by(SentimentAnalysis.sentiment_label).all()
    
    dist_counts = {label: count for label, count in sentiment_results}
    distribution = {
        "positive": dist_counts.get("positive", 0),
        "negative": dist_counts.get("negative", 0),
        "neutral": dist_counts.get("neutral", 0)
    }

    # 5. Count Top 5 Emotions
    emotion_results = base_query.with_entities(
        SentimentAnalysis.emotion,
        func.count(SentimentAnalysis.id)
    ).filter(SentimentAnalysis.emotion.isnot(None))\
     .group_by(SentimentAnalysis.emotion)\
     .order_by(func.count(SentimentAnalysis.id).desc())\
     .limit(5).all()
     
    top_emotions = {emotion: count for emotion, count in emotion_results}

    # 6. Calculate Totals and Percentages
    total = sum(distribution.values())
    
    percentages = {}
    if total > 0:
        percentages = {
            k: round((v / total) * 100, 2) for k, v in distribution.items()
        }
    else:
        percentages = {"positive": 0.0, "negative": 0.0, "neutral": 0.0}

    # 7. Construct Response
    response_data = {
        "timeframe_hours": hours,
        "source": source,
        "distribution": distribution,
        "total": total,
        "percentages": percentages,
        "top_emotions": top_emotions,
        "cached": False,
        "cached_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    }

    # 8. Save to Redis (60s TTL)
    redis_client.setex(cache_key, 60, json.dumps(response_data))

    return response_data


@router.get("/sentiment/aggregate")
async def get_sentiment_aggregate(
    period: str = Query(..., regex="^(minute|hour|day)$"),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    source: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """
    Get sentiment counts aggregated by time period.
   
    """
    
    if not end_date:
        end_date = datetime.utcnow()
    if not start_date:
        start_date = end_date - timedelta(hours=24)

    cache_key = f"agg:{period}:{start_date.isoformat()}:{end_date.isoformat()}:{source}"
    cached_data = redis_client.get(cache_key)
    if cached_data:
        return json.loads(cached_data)

    time_bucket = func.date_trunc(period, SocialMediaPost.created_at).label('timestamp')
    
    query = db.query(
        time_bucket,
        SentimentAnalysis.sentiment_label,
        func.count(SentimentAnalysis.id).label('count'),
        func.avg(SentimentAnalysis.confidence_score).label('avg_conf')
    ).join(SocialMediaPost)

    query = query.filter(SocialMediaPost.created_at >= start_date)
    query = query.filter(SocialMediaPost.created_at <= end_date)
    
    if source:
        query = query.filter(SocialMediaPost.source == source)

    results = query.group_by(time_bucket, SentimentAnalysis.sentiment_label)\
                   .order_by(time_bucket)\
                   .all()

    grouped_data = {}
    summary = {
        "total_posts": 0,
        "positive_total": 0,
        "negative_total": 0,
        "neutral_total": 0
    }

    for ts, label, count, avg_conf in results:
        ts_str = ts.isoformat()
        
        if ts_str not in grouped_data:
            grouped_data[ts_str] = {
                "timestamp": ts_str,
                "positive_count": 0,
                "negative_count": 0,
                "neutral_count": 0,
                "total_count": 0,
                "confidence_sum": 0.0
            }
        
        bucket = grouped_data[ts_str]
        bucket[f"{label}_count"] = count
        bucket["total_count"] += count
        bucket["confidence_sum"] += (avg_conf * count)

        summary["total_posts"] += count
        summary[f"{label}_total"] += count

    final_data_list = []
    
    for bucket in grouped_data.values():
        total = bucket["total_count"]
        if total > 0:
            bucket["positive_percentage"] = round((bucket["positive_count"] / total) * 100, 2)
            bucket["negative_percentage"] = round((bucket["negative_count"] / total) * 100, 2)
            bucket["neutral_percentage"] = round((bucket["neutral_count"] / total) * 100, 2)
            bucket["average_confidence"] = round(bucket["confidence_sum"] / total, 2)
        else:
            bucket["positive_percentage"] = 0
            bucket["negative_percentage"] = 0
            bucket["neutral_percentage"] = 0
            bucket["average_confidence"] = 0
        
        del bucket["confidence_sum"]
        final_data_list.append(bucket)

    response_payload = {
        "period": period,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "data": final_data_list,
        "summary": summary
    }

    redis_client.setex(cache_key, 60, json.dumps(response_payload))
    return response_payload


@router.get("/posts")
async def get_posts(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    source: Optional[str] = Query(None),
    sentiment: Optional[str] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    db: Session = Depends(get_db)
):
    """
    Retrieve posts with filtering and pagination.
   
    """
    
    query = db.query(SocialMediaPost).join(SentimentAnalysis)

    if source:
        query = query.filter(SocialMediaPost.source == source)
    if sentiment:
        query = query.filter(SentimentAnalysis.sentiment_label == sentiment)
    if start_date:
        query = query.filter(SocialMediaPost.created_at >= start_date)
    if end_date:
        query = query.filter(SocialMediaPost.created_at <= end_date)

    total_count = query.count()

    posts = query.order_by(desc(SocialMediaPost.created_at))\
                 .offset(offset)\
                 .limit(limit)\
                 .all()

    formatted_posts = []
    for post in posts:
        analysis_data = post.analysis
        
        formatted_posts.append({
            "post_id": post.post_id,
            "source": post.source,
            "content": post.content,
            "author": post.author,
            "created_at": post.created_at.isoformat() if post.created_at else None,
            "sentiment": {
                "label": analysis_data.sentiment_label if analysis_data else None,
                "confidence": analysis_data.confidence_score if analysis_data else 0.0,
                "emotion": analysis_data.emotion if analysis_data else None,
                "model_name": analysis_data.model_name if analysis_data else "unknown"
            }
        })

    return {
        "posts": formatted_posts,
        "total": total_count,
        "limit": limit,
        "offset": offset,
        "filters": {
            "source": source,
            "sentiment": sentiment,
            "start_date": start_date,
            "end_date": end_date
        }
    }


@router.get("/health")
def health_check(response: Response, db: Session = Depends(get_db)):
    """
    Check system health and connectivity.
   
    """
    services_status = {
        "database": "disconnected",
        "redis": "disconnected"
    }
    
    # 1. Ping Database
    try:
        db.execute(text("SELECT 1"))
        services_status["database"] = "connected"
    except Exception as e:
        print(f"Database Check Failed: {e}")

    # 2. Ping Redis
    try:
        redis_client.ping()
        services_status["redis"] = "connected"
    except Exception as e:
        print(f"Redis Check Failed: {e}")

    # Determine overall status
    is_healthy = (
        services_status["database"] == "connected" and 
        services_status["redis"] == "connected"
    )
    
    # Set HTTP Status Code
    if not is_healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        overall_status = "unhealthy" if services_status["database"] == "disconnected" else "degraded"
    else:
        response.status_code = status.HTTP_200_OK
        overall_status = "healthy"

    # 3. Collect Statistics
    stats = {
        "total_posts": 0,
        "total_analyses": 0,
        "recent_posts_1h": 0
    }

    if services_status["database"] == "connected":
        try:
            stats["total_posts"] = db.query(SocialMediaPost).count()
            stats["total_analyses"] = db.query(SentimentAnalysis).count()
            one_hour_ago = datetime.utcnow() - timedelta(hours=1)
            stats["recent_posts_1h"] = db.query(SocialMediaPost).filter(
                SocialMediaPost.created_at >= one_hour_ago
            ).count()
        except Exception as e:
            print(f"Stats Collection Failed: {e}")

    return {
        "status": overall_status,
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "services": services_status,
        "stats": stats
    }