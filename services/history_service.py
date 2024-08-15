import json
import logging

from crud import Postgres
from models import Message


# Логирование
logger = logging.getLogger(__name__)


async def generate_chat_history(user_id, db: Postgres):
    try:
        user_messages = await db.get_entities_parameter(
            Message, {"user_id": user_id}
        )
        data = [
            {
                "id": str(record.id),
                "content": json.loads(record.content),
                "created_at": record.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                "is_created_by_user": record.is_created_by_user,
            }
            for record in user_messages
        ]
        logger.info(f"user_messages: {data}")
        return data
    except Exception as e:
        logger.error(f"Error generating chat history: {e}")
        return {"error": "Error generating chat history"}
