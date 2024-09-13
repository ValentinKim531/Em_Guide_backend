import logging
import pandas as pd
from io import BytesIO
import json
import aiofiles
from crud import Postgres
from models import Survey


logger = logging.getLogger(__name__)


async def generate_statistics_file(user_id, db: Postgres):
    try:
        logger.info(f"Fetching statistics for user_id: {user_id}")

        user_records = await db.get_entities_parameter(
            Survey, {"userid": user_id}
        )

        if not user_records:
            logger.info(f"No records found for user {user_id}")
            return None

        # Логируем количество найденных записей
        logger.info(f"Found {len(user_records)} records for user {user_id}")

        data = [
            {
                "Номер": str(record.survey_id),
                "Дата создания": record.created_at.strftime("%Y-%m-%d %H:%M"),
                "Дата обновления": record.updated_at.strftime(
                    "%Y-%m-%d %H:%M"
                ),
                "Головная боль сегодня": record.headache_today,
                "Принимали ли медикаменты": record.medicament_today,
                "Интенсивность боли": record.pain_intensity,
                "Область боли": record.pain_area,
                "Детали области": record.area_detail,
                "Тип боли": record.pain_type,
                "Комментарии": record.comments,
            }
            for record in user_records
        ]

        df = pd.DataFrame(data)
        statistics_json = df.to_json(orient="records", force_ascii=False)

        # Логируем сгенерированные данные
        logger.info(f"Generated statistics: {statistics_json}")

        excel_file_path = await save_json_to_excel(statistics_json)
        return statistics_json
    except Exception as e:
        logger.error(
            f"Error generating statistics file for user {user_id}: {e}"
        )
        return None


async def save_json_to_excel(json_data):
    try:
        df = pd.read_json(BytesIO(json_data.encode("utf-8")))

        excel_file_path = "statistics_output.xlsx"
        df.to_excel(excel_file_path, index=False)

        return excel_file_path
    except Exception as e:
        logger.error(f"Error saving JSON to Excel: {e}")
        return None