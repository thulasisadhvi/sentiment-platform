import os
import json
import asyncio
import httpx
import logging
import torch
from transformers import pipeline

# Configure logging
logger = logging.getLogger(__name__)

class SentimentAnalyzer:
    """
    Unified interface for sentiment analysis using multiple model backends.
    """
    
    def __init__(self, model_type: str = 'local', model_name: str = None):
        self.model_type = model_type
        # Auto-detect GPU
        self.device = 0 if torch.cuda.is_available() else -1
        logger.info(f"🚀 Sentiment Analyzer running on device: {'GPU (cuda)' if self.device == 0 else 'CPU'}")
        
        # Load Configuration
        self.hf_token = os.getenv("HF_TOKEN")
        self.ext_api_key = os.getenv("EXTERNAL_LLM_API_KEY")
        self.ext_model = os.getenv("EXTERNAL_LLM_MODEL", "llama-3.1-8b-instant")
        self.ext_endpoint = "https://api.groq.com/openai/v1/chat/completions"

        if self.model_type == 'local':
            # UPDATED: Using Twitter RoBERTa which handles Neutral natively
            sent_model = model_name or os.getenv("HUGGINGFACE_MODEL", "cardiffnlp/twitter-roberta-base-sentiment-latest")
            logger.info(f"📥 Loading Local Sentiment Model: {sent_model}...")
            self.sentiment_pipeline = pipeline(
                "text-classification",
                model=sent_model,
                device=self.device,
                top_k=None 
            )
            
            emo_model = os.getenv("EMOTION_MODEL", "j-hartmann/emotion-english-distilroberta-base")
            logger.info(f"📥 Loading Local Emotion Model: {emo_model}...")
            self.emotion_pipeline = pipeline(
                "text-classification",
                model=emo_model,
                device=self.device,
                top_k=1
            )
            logger.info("✅ Local models loaded.")
            
        elif self.model_type == 'external':
            if not self.ext_api_key:
                logger.warning("⚠️ No API Key found for external model.")
            else:
                logger.info(f"✅ External client configured for {self.ext_endpoint}")

    async def analyze_sentiment(self, text: str) -> dict:
        if not text or not text.strip():
            return {'sentiment_label': 'neutral', 'confidence_score': 0.0, 'model_name': 'none'}

        if self.model_type == 'local':
            try:
                truncated_text = text[:512]
                
                # Run model in thread (Non-blocking)
                results = await asyncio.to_thread(self.sentiment_pipeline, truncated_text)
                results = results[0]
                
                # Normalize results (Find highest score)
                top_result = max(results, key=lambda x: x['score'])
                raw_label = top_result['label'].lower()
                score = round(float(top_result['score']), 4)
                
                # --- UPDATED LOGIC FOR ROBERTA ---
                # This model supports 'neutral', 'positive', and 'negative' directly.
                # We do NOT need the threshold gatekeeper anymore.
                
                final_label = 'neutral' # Default fallback
                
                if 'positive' in raw_label:
                    final_label = 'positive'
                elif 'negative' in raw_label:
                    final_label = 'negative'
                elif 'neutral' in raw_label:
                    final_label = 'neutral'
                else:
                    # Handle raw ID mappings if the model returns LABEL_0, etc.
                    # For RoBERTa: 0=Negative, 1=Neutral, 2=Positive
                    if raw_label == 'label_0':
                        final_label = 'negative'
                    elif raw_label == 'label_1':
                        final_label = 'neutral'
                    elif raw_label == 'label_2':
                        final_label = 'positive'

                return {
                    'sentiment_label': final_label,
                    'confidence_score': score,
                    'model_name': self.sentiment_pipeline.model.name_or_path
                }
            except Exception as e:
                logger.error(f"Local sentiment error: {e}")
                return {'sentiment_label': 'error', 'confidence_score': 0.0, 'model_name': 'local_error'}

        elif self.model_type == 'external':
            return await self._call_external_api(text, task="sentiment")

    async def analyze_emotion(self, text: str) -> dict:
        if not text or len(text.strip()) < 5:
             return {'emotion': 'neutral', 'confidence_score': 0.5, 'model_name': 'rule_based_short_text'}

        if self.model_type == 'local':
            try:
                results = await asyncio.to_thread(self.emotion_pipeline, text[:512])
                results = results[0]
                
                if isinstance(results, list): top = results[0]
                else: top = results
                
                return {
                    'emotion': top['label'],
                    'confidence_score': round(float(top['score']), 4),
                    'model_name': self.emotion_pipeline.model.name_or_path
                }
            except Exception as e:
                logger.error(f"Local emotion error: {e}")
                return {'emotion': 'neutral', 'confidence_score': 0.0, 'model_name': 'local_error'}
                
        elif self.model_type == 'external':
            return await self._call_external_api(text, task="emotion")

    async def batch_analyze(self, texts: list[str]) -> list[dict]:
        if not texts: return []
        tasks = [self.analyze_sentiment(text) for text in texts]
        return await asyncio.gather(*tasks)

    async def _call_external_api(self, text: str, task: str) -> dict:
        if task == "sentiment":
            system_prompt = "You are a sentiment analyzer. Return JSON ONLY: {\"sentiment_label\": \"positive\"|\"negative\"|\"neutral\", \"confidence_score\": 0.0-1.0}"
        else:
            system_prompt = "You are an emotion detector. Return JSON ONLY: {\"emotion\": \"joy\"|\"sadness\"|\"anger\"|\"fear\"|\"surprise\"|\"neutral\", \"confidence_score\": 0.0-1.0}"

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.ext_endpoint,
                    headers={"Authorization": f"Bearer {self.ext_api_key}"},
                    json={
                        "model": self.ext_model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": text}
                        ],
                        "temperature": 0.1,
                        "response_format": {"type": "json_object"}
                    }
                )
                if response.status_code != 200:
                    return {'sentiment_label': 'error', 'confidence_score': 0.0, 'model_name': 'api_error'}
                data = response.json()
                content = json.loads(data['choices'][0]['message']['content'])
                content['model_name'] = self.ext_model
                return content
        except Exception as e:
            logger.error(f"External API exception: {e}")
            return {'sentiment_label': 'error', 'confidence_score': 0.0, 'model_name': 'connection_error'}