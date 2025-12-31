from sqlalchemy import Column, Integer, String, Text, Float, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base

# Table 1: social_media_posts
class SocialMediaPost(Base):
    __tablename__ = "social_media_posts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    # Requirement: String length 255, unique, indexed
    post_id = Column(String(255), unique=True, index=True, nullable=False)
    # Requirement: String length 50, indexed
    source = Column(String(50), index=True)
    content = Column(Text)
    author = Column(String(255))
    # Requirement: DateTime (when post was created on platform)
    created_at = Column(DateTime, index=True) # Indexed per "Required Indexes"
    ingested_at = Column(DateTime, server_default=func.now())

    # Relationship
    analysis = relationship("SentimentAnalysis", back_populates="post", uselist=False)

# Table 2: sentiment_analysis
class SentimentAnalysis(Base):
    __tablename__ = "sentiment_analysis"

    id = Column(Integer, primary_key=True, autoincrement=True)
    # Requirement: Foreign key referencing social_media_posts.post_id
    post_id = Column(String(255), ForeignKey("social_media_posts.post_id"))
    
    # Requirement: String length 100
    model_name = Column(String(100))
    # Requirement: String length 20 (positive, negative, neutral)
    sentiment_label = Column(String(20))
    confidence_score = Column(Float)
    # Requirement: String length 50, nullable
    emotion = Column(String(50), nullable=True)
    analyzed_at = Column(DateTime, server_default=func.now(), index=True)

    post = relationship("SocialMediaPost", back_populates="analysis")

# Table 3: sentiment_alerts
class SentimentAlert(Base):
    __tablename__ = "sentiment_alerts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    # Requirement: String length 50
    alert_type = Column(String(50))
    threshold_value = Column(Float)
    actual_value = Column(Float)
    window_start = Column(DateTime)
    window_end = Column(DateTime)
    post_count = Column(Integer)
    # Requirement: Indexed
    triggered_at = Column(DateTime, server_default=func.now(), index=True)
    # Requirement: JSON column for alert details
    details = Column(JSON)