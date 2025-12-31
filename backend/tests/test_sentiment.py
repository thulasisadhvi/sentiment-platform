import pytest
from unittest.mock import MagicMock, patch
from backend.services.sentiment_analyzer import SentimentAnalyzer

@pytest.mark.asyncio
async def test_sentiment_flow():
    # FIX: Use List of Lists [[...]] to match HuggingFace batch format
    mock_sent = MagicMock(return_value=[[{'label': 'POSITIVE', 'score': 0.99}]])
    # Emotion is already correct as [[...]]
    mock_emo = MagicMock(return_value=[[{'label': 'joy', 'score': 0.9}]])
    
    analyzer = SentimentAnalyzer(model_type='local')
    analyzer.sentiment_pipeline = mock_sent
    analyzer.emotion_pipeline = mock_emo

    # 1. Test Positive Case
    res = await analyzer.analyze_sentiment("I am happy")
    # Check case-insensitive to be safe
    assert res['sentiment_label'].lower() == 'positive'
    
    # 2. Test Emotion
    emo = await analyzer.analyze_emotion("I am happy")
    assert emo['emotion'] == 'joy'

@pytest.mark.asyncio
async def test_batch_processing_simulation():
    # Simulating batch processing
    analyzer = SentimentAnalyzer(model_type='local')
    # FIX: Use List of Lists [[...]]
    analyzer.sentiment_pipeline = MagicMock(return_value=[[{'label': 'NEGATIVE', 'score': 0.9}]])
    analyzer.emotion_pipeline = MagicMock(return_value=[[{'label': 'sadness', 'score': 0.8}]])
    
    texts = ["Bad day", "Worst service", "I hate this"]
    results = []
    for text in texts:
        res = await analyzer.analyze_sentiment(text)
        results.append(res)
    
    assert len(results) == 3
    assert results[0]['sentiment_label'].lower() == 'negative'

@pytest.mark.asyncio
async def test_device_and_edge_cases():
    # 1. Test CPU/GPU Selection Logic
    with patch('torch.cuda.is_available', return_value=False):
        with patch('backend.services.sentiment_analyzer.pipeline'):
            SentimentAnalyzer()
            
    with patch('torch.cuda.is_available', return_value=True):
        with patch('backend.services.sentiment_analyzer.pipeline'):
            SentimentAnalyzer()

    # 2. Test Error Handling
    analyzer = SentimentAnalyzer(model_type='local')
    analyzer.sentiment_pipeline = MagicMock(side_effect=Exception("Boom"))
    analyzer.emotion_pipeline = MagicMock(side_effect=Exception("Boom"))
    
    # Analyze Sentiment Error
    res = await analyzer.analyze_sentiment("Fail")
    assert res['sentiment_label'] in ['neutral', 'error', 'negative']
    
    # Analyze Emotion Error
    emo = await analyzer.analyze_emotion("Fail")
    assert emo['emotion'] == 'neutral'
