import asyncio
import json
import logging
import os
import random
import uuid
import signal
from datetime import datetime, timezone
import redis.asyncio as redis
from faker import Faker
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

class DataIngester:
    """
    Publishes simulated social media posts to Redis Stream
    """
    
    def __init__(self, redis_client, stream_name: str, posts_per_minute: int = 60):
        """
        Initialize the ingester
        
        Args:
            redis_client: Redis connection instance
            stream_name: Name of the Redis stream to publish to
            posts_per_minute: Rate of post generation (default: 60)
        """
        self.redis = redis_client
        self.stream_name = stream_name
        self.posts_per_minute = posts_per_minute
        self.sleep_interval = 60.0 / float(posts_per_minute)
        self.fake = Faker()
        self.running = False
        
        # - Post Generation Strategy
        self.products = ["iPhone 16", "Tesla Model 3", "ChatGPT", "Netflix", "Amazon Prime", "Google Pixel", "Spotify"]
        
        self.positive_templates = [
            "I absolutely love {product}!", 
            "This is amazing!", 
            "{product} exceeded my expectations!",
            "Can't believe how good {product} is.",
            "Best purchase ever: {product}."
        ]
        
        self.negative_templates = [
            "Very disappointed with {product}", 
            "Terrible experience", 
            "Would not recommend {product}",
            "{product} is a total waste of money.",
            "Worst customer service from {product}."
        ]
        
        self.neutral_templates = [
            "Just tried {product}", 
            "Received {product} today", 
            "Using {product} for the first time",
            "Thoughts on {product}?",
            "Thinking about buying {product}."
        ]

    def generate_post(self) -> dict:
        """
        Generate a single realistic post with varied sentiment
        
        Must return dict with exact keys: post_id, source, content, author, created_at
        """
        # - Random Selection Logic
        rand_val = random.random()
        product = random.choice(self.products)
        
        # 40% Positive, 30% Neutral, 30% Negative
        if rand_val < 0.4:
            template = random.choice(self.positive_templates)
        elif rand_val < 0.7:
            template = random.choice(self.negative_templates)
        else:
            template = random.choice(self.neutral_templates)
            
        content = template.format(product=product)
        
        return {
            'post_id': f"post_{uuid.uuid4().hex[:10]}",
            'source': random.choice(['twitter', 'reddit', 'facebook', 'instagram']),
            'content': content,
            'author': self.fake.user_name(),
            # - ISO 8601 with 'Z'
            'created_at': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        }

    async def publish_post(self, post_data: dict) -> bool:
        """
        Publish a single post to Redis Stream
        """
        try:
            # - XADD command
            await self.redis.xadd(
                self.stream_name,
                post_data,
                maxlen=1000 # Keep stream size manageable
            )
            return True
        except redis.RedisError as e:
            # - Handle Redis connection failures
            logger.error(f"Failed to publish to Redis: {e}")
            return False

    async def start(self, duration_seconds: int = None):
        """
        Start continuous post generation and publishing
        """
        self.running = True
        start_time = datetime.now()
        posts_generated = 0
        
        logger.info(f"🚀 Starting Ingester: {self.posts_per_minute} posts/min to stream '{self.stream_name}'")

        try:
            while self.running:
                # Check duration if set
                if duration_seconds and (datetime.now() - start_time).seconds >= duration_seconds:
                    logger.info("Duration limit reached.")
                    break

                # Generate and Publish
                post = self.generate_post()
                success = await self.publish_post(post)
                
                if success:
                    posts_generated += 1
                    logger.info(f"Published [{posts_generated}]: {post['content'][:50]}...")
                
                # - Rate limiting sleep
                await asyncio.sleep(self.sleep_interval)
                
        except asyncio.CancelledError:
            logger.info("Ingester task cancelled.")
        finally:
            self.running = False
            logger.info(f"🛑 Ingester stopped. Total posts: {posts_generated}")

# --- Entry Point ---
async def main():
    # Get config from env
    redis_host = os.getenv('REDIS_HOST', 'localhost')
    redis_port = int(os.getenv('REDIS_PORT', 6379))
    stream_name = os.getenv('REDIS_STREAM_NAME', 'social_posts_stream')
    
    # Initialize Redis Client
    r = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)
    
    # Initialize Ingester
    ingester = DataIngester(
        redis_client=r, 
        stream_name=stream_name, 
        posts_per_minute=60
    )
    
    # Handle graceful shutdown
    loop = asyncio.get_running_loop()
    stop_signal = asyncio.Event()
    
    def signal_handler():
        print("\nShutdown signal received...")
        stop_signal.set()
        ingester.running = False

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, signal_handler)

    # Run ingester until signal
    ingester_task = asyncio.create_task(ingester.start())
    
    await stop_signal.wait()
    await ingester_task
    await r.close()

if __name__ == "__main__":
    asyncio.run(main())