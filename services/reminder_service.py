import logging
from datetime import datetime

from crud import Postgres
from models import User

logger = logging.getLogger(__name__)


async def change_reminder_time(user_id: str, reminder_time: str, db: Postgres):
    try:
        reminder_time_obj = datetime.strptime(reminder_time, "%H:%M").time()
        # Обновление времени напоминания в базе данных
        await db.update_entity_parameter(
            entity_id=user_id,
            parameter="reminder_time",
            value=reminder_time_obj,
            model_class=User,
        )
        logger.info(f"Reminder time updated successfully for user {user_id}")
        return str(reminder_time_obj)
    except Exception as e:
        logger.error(f"Error updating reminder time: {e}")
        return f"Failed to update reminder time: {e}"
