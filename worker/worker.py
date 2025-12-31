import asyncio
import json
import logging
import os
import signal
from datetime import datetime
import redis.asyncio as redis
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# 1. Import the new processor function
from worker.processor import save_post_and_analysis

# Imports from backend
from backend.services.sentiment_analyzer import SentimentAnalyzer

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("SentimentWorker")

class SentimentWorker:
    """
    Consumes posts from Redis Stream and processes them through sentiment analysis.
    """

    def __init__(self, redis_url: str, db_url: str, stream_name: str, consumer_group: str):
        """
        Initialize worker with necessary dependencies.
        """
        self.redis_url = redis_url
        self.stream_name = stream_name
        self.consumer_group = consumer_group
        self.consumer_name = f"worker-{os.getpid()}"
        
        # Initialize Redis
        self.redis = redis.from_url(self.redis_url, decode_responses=True)
        
        # Initialize DB (Async)
        self.engine = create_async_engine(db_url, echo=False)
        self.SessionLocal = sessionmaker(
            self.engine, expire_on_commit=False, class_=AsyncSession
        )

        # Initialize Analyzers
        logger.info("🧠 Initializing AI Models...")
        self.analyzer = SentimentAnalyzer(model_type='local') 
        # Optional: Initialize external analyzer if needed
        # self.external_analyzer = SentimentAnalyzer(model_type='external')

        self.running = False
        self.stats = {"processed": 0, "errors": 0}

    async def setup_consumer_group(self):
        """Ensure the consumer group exists"""
        try:
            await self.redis.xgroup_create(
                self.stream_name, self.consumer_group, id='0', mkstream=True
            )
            logger.info(f"✅ Consumer group '{self.consumer_group}' created.")
        except redis.ResponseError as e:
            if "BUSYGROUP" in str(e):
                logger.info(f"ℹ️ Consumer group '{self.consumer_group}' already exists.")
            else:
                raise e

    async def process_message(self, message_id: str, message_data: dict) -> bool:
        """
        Process a single message from the stream.
        """
        # Create a new DB session for this transaction
        async with self.SessionLocal() as session:
            try:
                # 1. Extract & Parse Post Content
                if isinstance(message_data, str):
                    post_data = json.loads(message_data)
                else:
                    post_data = message_data 
                
                content = post_data.get('content', '')
                if not content:
                    logger.warning(f"⚠️ Empty content in message {message_id}")
                    # Ack bad messages to stop loop
                    await self.redis.xack(self.stream_name, self.consumer_group, message_id)
                    return False

                # 2. Run Sentiment & Emotion Analysis
                # (These run on CPU/GPU, not DB, so we do them before DB transaction logic)
                sentiment_result = await self.analyzer.analyze_sentiment(content)
                emotion_result = await self.analyzer.analyze_emotion(content)

                # 3. Save to Database (Using the imported processor function)
                # This handles the Upsert logic, Foreign Keys, and Commit
                await save_post_and_analysis(
                    session, 
                    post_data, 
                    sentiment_result, 
                    emotion_result
                )
                
                # 4. Acknowledge message (XACK)
                # We only ack if the DB save above succeeded (didn't raise exception)
                await self.redis.xack(self.stream_name, self.consumer_group, message_id)
                
                self.stats["processed"] += 1
                return True

            except Exception as e:
                logger.error(f"❌ Error processing message {message_id}: {e}")
                # Requirement: "If database save fails... DON'T acknowledge"
                # This allows Redis to re-deliver the message later (or claim by another worker)
                return False

    async def run(self, batch_size: int = 10, block_ms: int = 5000):
        """
        Main worker loop.
        """
        await self.setup_consumer_group()
        self.running = True
        logger.info(f"🚀 Worker started. Listening to stream: {self.stream_name}")

        while self.running:
            try:
                # Use XREADGROUP to consume
                streams = {self.stream_name: '>'} 
                messages = await self.redis.xreadgroup(
                    groupname=self.consumer_group,
                    consumername=self.consumer_name,
                    streams=streams,
                    count=batch_size,
                    block=block_ms
                )

                if not messages:
                    continue

                # Process batch concurrently
                for stream, msg_list in messages:
                    tasks = []
                    for message_id, message_data in msg_list:
                        tasks.append(self.process_message(message_id, message_data))
                    
                    if tasks:
                        await asyncio.gather(*tasks)

                # Log stats occasionally
                if self.stats["processed"] % 10 == 0 and self.stats["processed"] > 0:
                     logger.info(f"📊 Stats: {self.stats}")

            except redis.ConnectionError:
                logger.error("⚠️ Redis connection lost. Retrying in 5s...")
                await asyncio.sleep(5)
            except Exception as e:
                logger.error(f"❌ Unexpected error in worker loop: {e}")
                await asyncio.sleep(1)
        
        await self.redis.close()
        await self.engine.dispose()

# --- Entry Point ---
if __name__ == "__main__":
    # Load Config
    redis_host = os.getenv("REDIS_HOST", "localhost")
    redis_port = os.getenv("REDIS_PORT", "6379")
    redis_url = f"redis://{redis_host}:{redis_port}"
    
    # Patch database URL for async driver if needed
    db_url = os.getenv("DATABASE_URL", "").replace("postgresql://", "postgresql+asyncpg://")
    
    stream_name = os.getenv("REDIS_STREAM_NAME", "social_posts_stream")
    group_name = os.getenv("REDIS_CONSUMER_GROUP", "sentiment_workers")

    worker = SentimentWorker(redis_url, db_url, stream_name, group_name)
    
    # Graceful Shutdown Handler
    loop = asyncio.get_event_loop()
    
    def stop():
        worker.running = False
        print("Stopping worker...")

    loop.add_signal_handler(signal.SIGINT, stop)
    loop.add_signal_handler(signal.SIGTERM, stop)

    try:
        loop.run_until_complete(worker.run())
    except KeyboardInterrupt:
        pass