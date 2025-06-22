import redis
import json
import logging
from dotenv import load_dotenv
import os

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

load_dotenv()

redis_client = redis.Redis(host=os.getenv("REDIS_HOST", "redis"), port=int(os.getenv("REDIS_PORT", 6379)), decode_responses=True)

def get_cached_response(query: str) -> str:
    try:
        cached = redis_client.get(query)
        if cached:
            logger.info(f"Cache hit for query: {query}")
            return cached
        return None
    except redis.RedisError as e:
        logger.error(f"Error accessing Redis cache: {str(e)}")
        return None

def cache_response(query: str, response: str):
    try:
        redis_client.setex(query, 3600, response)
        logger.info(f"Cached response for query: {query}")
    except redis.RedisError as e:
        logger.error(f"Error caching response: {str(e)}")