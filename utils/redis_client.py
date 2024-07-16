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


async def is_message_processed(message_id):
    return await redis.exists(f"processed:{message_id}")


async def mark_message_as_processed(user_id, message_id):
    await redis.sadd(f"processed:{user_id}", message_id)
    logger.info(f"Marked message {message_id} as processed for user {user_id}")


async def get_processed_messages(user_id):
    return await redis.smembers(f"processed:{user_id}")


async def delete_processed_messages(user_id, message_ids):
    try:
        for message_id in message_ids:
            result = await redis.delete(f"processed:{message_id}")
            if result == 1:
                logger.info(f"Deleted processed message with id: {message_id}")
            else:
                logger.warning(
                    f"Failed to delete processed message with id: {message_id}"
                )
        # Удаляем сам набор
        result = await redis.delete(f"processed:{user_id}")
        if result == 1:
            logger.info(f"Deleted processed message set for user {user_id}")
        else:
            logger.warning(
                f"Failed to delete processed message set for user {user_id}"
            )
    except Exception as e:
        logger.error(
            f"Error deleting processed messages for user {user_id}: {e}"
        )
