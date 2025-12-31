import os
import logging
from transformers import pipeline
from groq import Groq

logger = logging.getLogger(__name__)

class SentimentEngine:
    """
    Handles both Local (Hugging Face) and External (Groq) sentiment analysis.
    """
    
    def __init__(self):
        self.device = -1 # CPU
        self.local_pipeline = None
        self.groq_client = None
        self._initialize_models()

    def _initialize_models(self):
        """Load local models and setup external API clients"""
        
        # 1. Setup Local Model (Hugging Face)
        try:
            model_name = os.getenv("HUGGINGFACE_MODEL", "distilbert-base-uncased-finetuned-sst-2-english")
            logger.info(f"📥 Loading local model: {model_name}...")
            
            # This downloads the model the first time it runs
            self.local_pipeline = pipeline(
                "sentiment-analysis",
                model=model_name,
                device=self.device
            )
            logger.info("✅ Local model loaded successfully.")
        except Exception as e:
            logger.error(f"❌ Failed to load local model: {e}")

        # 2. Setup External API (Groq)
        try:
            api_key = os.getenv("EXTERNAL_LLM_API_KEY")
            if api_key:
                self.groq_client = Groq(api_key=api_key)
                logger.info("✅ Groq client initialized.")
            else:
                logger.warning("⚠️ No EXTERNAL_LLM_API_KEY found. External analysis will be disabled.")
        except Exception as e:
            logger.error(f"❌ Failed to setup Groq client: {e}")

    def analyze_local(self, text: str):
        """
        Run sentiment analysis using the local Hugging Face model.
        Fast, free, runs on your hardware.
        """
        if not self.local_pipeline:
            return {"error": "Local model not available"}

        # Truncate text to 512 tokens to prevent model errors
        result = self.local_pipeline(text[:512])[0]
        
        # Normalize result (e.g., 'POSITIVE' -> 'positive')
        label = result['label'].lower()
        score = result['score']
        
        return {
            "model": "local_distilbert",
            "sentiment": label,
            "confidence": score,
            "emotion": "neutral" # Basic models don't detect emotion, only sentiment
        }

    def analyze_external(self, text: str):
        """
        Run sentiment analysis using Groq (LLaMA-3).
        Slower, costs money (if not free tier), but higher quality/emotion detection.
        """
        if not self.groq_client:
            return {"error": "External API not configured"}

        try:
            response = self.groq_client.chat.completions.create(
                messages=[
                    {
                        "role": "system",
                        "content": "Analyze the sentiment of the user's text. Return ONLY a JSON object with keys: 'sentiment' (positive/negative/neutral), 'confidence' (0.0-1.0), and 'emotion' (joy/anger/sadness/fear/surprise/neutral)."
                    },
                    {
                        "role": "user",
                        "content": text
                    }
                ],
                model="llama3-8b-8192",
                temperature=0, # Deterministic results
                response_format={"type": "json_object"}
            )
            
            # Parse the JSON response from the LLM
            import json
            result = json.loads(response.choices[0].message.content)
            result['model'] = "external_llama3"
            return result
            
        except Exception as e:
            logger.error(f"External API call failed: {e}")
            return {"error": str(e)}

# Simple test to verify it works when run directly
if __name__ == "__main__":
    engine = SentimentEngine()
    print("Local Test:", engine.analyze_local("I love this project!"))