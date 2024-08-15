import json
import logging

from models import User

# Инициализация логирования
logging.basicConfig(level=logging.INFO)

# Логирование
logger = logging.getLogger(__name__)


async def get_user_language(user_id, message_language, db):
    try:
        if message_language:
            await db.update_entity_parameter(
                user_id, "language", message_language, User
            )
            return message_language
        else:
            user_language = await db.get_entity_parameter(
                User, {"userid": str(user_id)}, "language"
            )
            return user_language or "ru"
    except Exception as e:
        logger.error(f"Error getting user language for user_id {user_id}: {e}")
        return "ru"


def validate_json_format(content):
    try:
        json.loads(content)
        return True
    except json.JSONDecodeError as e:
        logger.error(f"JSON format error: {e}")
        return False
