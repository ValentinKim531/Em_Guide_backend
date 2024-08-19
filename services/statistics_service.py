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
        user_records = await db.get_entities_parameter(
            Survey, {"userid": user_id}
        )

        data = [
            {
                "Номер": record.survey_id,
                "Дата создания": record.created_at.strftime("%Y-%m-%d %H:%M"),
                "Дата обновления": record.updated_at.strftime(
                    "%Y-%m-%d %H:%М"
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

        excel_file_path = await save_json_to_excel(statistics_json)

        return statistics_json
    except Exception as e:
        logger.error(
            f"Error generating statistics file for user {user_id}: {e}"
        )
        return None, None


async def save_json_to_excel(json_data):
    try:
        df = pd.read_json(BytesIO(json_data.encode("utf-8")))

        excel_file_path = "statistics_output.xlsx"
        df.to_excel(excel_file_path, index=False)

        return excel_file_path
    except Exception as e:
        logger.error(f"Error saving JSON to Excel: {e}")
        return None
