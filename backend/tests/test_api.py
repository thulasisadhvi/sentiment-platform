import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient
from backend.main import app
from backend.models.database import get_db
from datetime import datetime

# Setup DB Mocking
mock_db = MagicMock()
mock_query = MagicMock()

# Configure Chainability
mock_db.query.return_value = mock_query
mock_query.join.return_value = mock_query
mock_query.filter.return_value = mock_query
mock_query.group_by.return_value = mock_query
mock_query.order_by.return_value = mock_query
mock_query.limit.return_value = mock_query
mock_query.offset.return_value = mock_query

def override_get_db():
    try:
        yield mock_db
    finally:
        pass

app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)

def test_health_check():
    mock_db.execute.return_value = True
    response = client.get("/api/health")
    assert response.status_code == 200

def test_get_posts_all_filters():
    # Mock data
    mock_post = MagicMock()
    mock_post.as_dict.return_value = {"id": 1, "content": "test"}
    mock_query.all.return_value = [mock_post]
    mock_query.scalars.return_value.all.return_value = [mock_post]
    mock_query.count.return_value = 1
    mock_query.scalar_one.return_value = 1

    # 1. Test Basic
    client.get("/api/posts")
    
    # 2. Test Source Filter
    client.get("/api/posts?source=twitter")
    
    # 3. Test Sentiment Filter
    client.get("/api/posts?sentiment=positive")
    
    # 4. Test Date Filter
    client.get("/api/posts?start_date=2025-01-01T00:00:00&end_date=2025-01-02T00:00:00")
    
    assert mock_query.filter.called

def test_distribution_endpoint():
    mock_row = MagicMock()
    mock_row.sentiment_label = "positive"
    mock_row.count = 10
    mock_query.all.return_value = [mock_row]
    
    # Test with source filter
    response = client.get("/api/sentiment/distribution?source=reddit&hours=24")
    assert response.status_code == 200

def test_aggregation_endpoint():
    fake_dt = datetime(2025, 1, 1, 12, 0, 0)
    mock_row = (fake_dt, "positive", 10, 0.9)
    mock_query.all.return_value = [mock_row]
    
    # Test with all params
    response = client.get("/api/sentiment/aggregate?period=day&source=twitter")
    assert response.status_code == 200
