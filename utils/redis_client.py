import aioredis
from utils.config import REDIS_URL
import logging
import asyncio

logger = logging.getLogger(__name__)

redis = aioredis.from_url(REDIS_URL)


async def get_user_state(user_id):
    return await redis.get(f"user_state:{user_id}")


async def set_user_state(user_id, state):
    await redis.set(f"user_state:{user_id}", state)


async def get_thread_id(user_id):
    return await redis.get(f"thread_id:{user_id}")


async def save_thread_id(user_id, thread_id):
    await redis.set(f"thread_id:{user_id}", thread_id)


async def get_assistant_id(user_id):
    return await redis.get(f"assistant_id:{user_id}")


async def save_assistant_id(user_id, assistant_id):
    await redis.set(f"assistant_id:{user_id}", assistant_id)


def delete_user_state(user_id):
    return redis.delete(f"user_state:{user_id}")


def delete_thread_id(user_id):
    return redis.delete(f"thread_id:{user_id}")


def delete_assistant_id(user_id):
    return redis.delete(f"assistant_id:{user_id}")
