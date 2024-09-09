import aioredis
import logging
from utils.config import REDIS_URL
from aioredis.exceptions import RedisError
from collections import defaultdict

logger = logging.getLogger(__name__)

# Инициализация подключения к Redis
redis = aioredis.from_url(REDIS_URL)

# Локальный кеш для хранения данных при отказе Redis
local_thread_cache = defaultdict(dict)


# Логирование всего кеша
def log_local_cache():
    logger.info(
        f"Current state of local_thread_cache: {dict(local_thread_cache)}"
    )


# Очистка локального кеша для конкретного пользователя
def clear_local_cache(user_id):
    if user_id in local_thread_cache:
        del local_thread_cache[user_id]
        logger.info(f"Cleared local cache for user {user_id}")
    else:
        logger.info(f"No local cache found for user {user_id}")


# Функция для синхронизации данных из Redis в локальный кеш при первом сбое Redis
async def sync_redis_to_cache(user_id):
    try:
        # Попытка получить данные из Redis
        state = await redis.get(f"user_state:{user_id}")
        thread_id = await redis.get(f"thread_id:{user_id}")
        assistant_id = await redis.get(f"assistant_id:{user_id}")
        processed_messages = await redis.smembers(f"processed:{user_id}")

        # Если данные из Redis получены, сохраняем их в локальный кеш
        if state:
            local_thread_cache[user_id]["state"] = (
                state.decode("utf-8") if isinstance(state, bytes) else state
            )
        if thread_id:
            local_thread_cache[user_id]["thread_id"] = (
                thread_id.decode("utf-8")
                if isinstance(thread_id, bytes)
                else thread_id
            )
        if assistant_id:
            local_thread_cache[user_id]["assistant_id"] = (
                assistant_id.decode("utf-8")
                if isinstance(assistant_id, bytes)
                else assistant_id
            )
        if processed_messages:
            local_thread_cache[user_id]["processed_messages"] = set(
                processed_messages
            )

        logger.info(
            f"Data synchronized from Redis to cache for user {user_id}"
        )
        log_local_cache()

    except RedisError as e:
        logger.error(
            f"Failed to synchronize Redis to cache for user {user_id}: {e}"
        )


# Обертка для операций с Redis, синхронизация данных при успешных операциях
async def redis_operation_with_sync(func, *args, user_id=None, **kwargs):
    try:
        # Выполнение операции с Redis
        result = await func(*args, **kwargs)

        # Синхронизация данных в локальный кэш после успешной операции
        if user_id:
            await sync_redis_to_cache(user_id)
        return result
    except RedisError as e:
        logger.error(f"Redis Error during operation: {e}")
        if user_id:
            await sync_redis_to_cache(user_id)
        return None


# Функция для работы с состоянием пользователя
async def get_user_state(user_id):
    try:
        result = await redis_operation_with_sync(
            redis.get, f"user_state:{user_id}", user_id=user_id
        )
        if result:
            return result
        # Если в Redis нет данных, берем их из локального кэша
        return local_thread_cache.get(user_id, {}).get("state")
    except RedisError as e:
        logger.error(f"Redis Error in get_user_state for user {user_id}: {e}")
        return local_thread_cache.get(user_id, {}).get("state")


async def set_user_state(user_id, state):
    try:
        await redis_operation_with_sync(
            redis.set, f"user_state:{user_id}", state, user_id=user_id
        )
        local_thread_cache[user_id]["state"] = state
    except RedisError as e:
        logger.error(f"Redis Error in set_user_state for user {user_id}: {e}")
        local_thread_cache[user_id]["state"] = state


# Функции для работы с thread_id
async def get_thread_id(user_id):
    try:
        result = await redis_operation_with_sync(
            redis.get, f"thread_id:{user_id}", user_id=user_id
        )
        if result:
            return result
        # Если в Redis нет данных, берем их из локального кэша
        return local_thread_cache.get(user_id, {}).get("thread_id")
    except RedisError as e:
        logger.error(f"Redis Error in get_thread_id for user {user_id}: {e}")
        return local_thread_cache.get(user_id, {}).get("thread_id")


async def save_thread_id(user_id, thread_id):
    try:
        await redis_operation_with_sync(
            redis.set, f"thread_id:{user_id}", thread_id, user_id=user_id
        )
        local_thread_cache[user_id]["thread_id"] = thread_id
    except RedisError as e:
        logger.error(f"Redis Error in save_thread_id for user {user_id}: {e}")
        local_thread_cache[user_id]["thread_id"] = thread_id


# Функции для работы с assistant_id
async def get_assistant_id(user_id):
    try:
        result = await redis_operation_with_sync(
            redis.get, f"assistant_id:{user_id}", user_id=user_id
        )
        if result:
            return result
        # Если в Redis нет данных, берем их из локального кэша
        return local_thread_cache.get(user_id, {}).get("assistant_id")
    except RedisError as e:
        logger.error(
            f"Redis Error in get_assistant_id for user {user_id}: {e}"
        )
        return local_thread_cache.get(user_id, {}).get("assistant_id")


async def save_assistant_id(user_id, assistant_id):
    try:
        await redis_operation_with_sync(
            redis.set, f"assistant_id:{user_id}", assistant_id, user_id=user_id
        )
        local_thread_cache[user_id]["assistant_id"] = assistant_id
    except RedisError as e:
        logger.error(
            f"Redis Error in save_assistant_id for user {user_id}: {e}"
        )
        local_thread_cache[user_id]["assistant_id"] = assistant_id


async def mark_message_as_processed(user_id, message_id):
    # Приводим message_id к строковому типу, проверяя, что он не None
    if message_id is None:
        logger.error(f"message_id is None for user {user_id}")
        return

    message_id_str = (
        message_id.decode("utf-8")
        if isinstance(message_id, bytes)
        else message_id
    )
    logger.info(f"message_id_str {message_id_str} ")
    try:
        # Проверка, что message_id_str не является None
        if message_id_str is None:
            logger.error(f"message_id_str is None for user {user_id}")
            return

        # Добавляем сообщение в Redis
        await redis_operation_with_sync(
            redis.sadd, f"processed:{user_id}", message_id_str, user_id=user_id
        )
        logger.info(
            f"Marked message {message_id_str} as processed for user {user_id}"
        )

        # Добавляем сообщение в локальный кэш
        if "processed_messages" not in local_thread_cache[user_id]:
            local_thread_cache[user_id]["processed_messages"] = set()
        local_thread_cache[user_id]["processed_messages"].add(message_id_str)
        log_local_cache()
    except RedisError as e:
        logger.error(
            f"Redis Error in mark_message_as_processed for user {user_id}: {e}"
        )
        # Добавляем сообщение в локальный кэш, если произошла ошибка с Redis
        if "processed_messages" not in local_thread_cache[user_id]:
            local_thread_cache[user_id]["processed_messages"] = set()
        local_thread_cache[user_id]["processed_messages"].add(message_id_str)
        log_local_cache()


# Проверка, обработано ли сообщение
async def is_message_processed(user_id, message_id):
    if message_id is None:
        logger.error(f"message_id is None for user {user_id}")
        return False

    message_id_str = (
        message_id.decode("utf-8")
        if isinstance(message_id, bytes)
        else message_id
    )

    try:
        # Проверка в Redis
        is_processed = await redis.sismember(
            f"processed:{user_id}", message_id_str
        )
        if is_processed:
            return True
        else:
            # Проверка в локальном кэше
            processed_messages = local_thread_cache.get(user_id, {}).get(
                "processed_messages", set()
            )
            return message_id_str in processed_messages
    except RedisError as e:
        logger.error(
            f"Redis Error in is_message_processed for user {user_id}: {e}"
        )
        # Проверка в локальном кэше при ошибке Redis
        processed_messages = local_thread_cache.get(user_id, {}).get(
            "processed_messages", set()
        )
        return message_id_str in processed_messages


# Функции удаления данных
async def delete_processed_messages(user_id, message_ids):
    try:
        for message_id in message_ids:
            await redis_operation_with_sync(
                redis.delete, user_id, f"processed:{message_id}"
            )
        await redis_operation_with_sync(
            redis.delete, user_id, f"processed:{user_id}"
        )
        clear_local_cache(user_id)
        logger.info(f"Deleted processed messages for user {user_id}")
        log_local_cache()
    except RedisError as e:
        logger.error(
            f"Redis Error in delete_processed_messages for user {user_id}: {e}"
        )


async def delete_user_state(user_id):
    redis_result = await redis_operation_with_sync(
        redis.delete, f"user_state:{user_id}", user_id=user_id
    )
    if redis_result is None:
        local_thread_cache[user_id].pop("state", None)
        logger.info(f"Deleted user_state from local cache for user {user_id}")


async def delete_thread_id(user_id):
    redis_result = await redis_operation_with_sync(
        redis.delete, f"thread_id:{user_id}", user_id=user_id
    )
    if redis_result is None:
        local_thread_cache[user_id].pop("thread_id", None)


async def delete_assistant_id(user_id):
    redis_result = await redis_operation_with_sync(
        redis.delete, f"assistant_id:{user_id}", user_id=user_id
    )
    if redis_result is None:
        local_thread_cache[user_id].pop("assistant_id", None)


# Полная очистка состояния пользователя
async def clear_user_state(user_id, processed_message_ids):
    await delete_user_state(user_id)
    await delete_thread_id(user_id)
    await delete_assistant_id(user_id)
    await delete_processed_messages(user_id, processed_message_ids)
