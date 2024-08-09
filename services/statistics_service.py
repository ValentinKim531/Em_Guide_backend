import pandas as pd
from io import BytesIO
import json
import aiofiles
from crud import Postgres
from models import Survey


async def generate_statistics_file(user_id, db: Postgres):
    # Получение записей опросов пользователя из базы данных
    user_records = await db.get_entities_parameter(Survey, {"userid": user_id})

    # Подготовка данных для DataFrame
    data = [
        {
            "Номер": record.survey_id,
            "Дата создания": record.created_at.strftime("%Y-%m-%d %H:%M"),
            "Дата обновления": record.updated_at.strftime("%Y-%м-%d %H:%M"),
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

    # Создание DataFrame
    df = pd.DataFrame(data)

    # Преобразование DataFrame в JSON
    statistics_json = df.to_json(orient="records", force_ascii=False)

    # Сохранение JSON как Excel файл
    excel_file_path = await save_json_to_excel(statistics_json)

    return statistics_json, excel_file_path


async def save_json_to_excel(json_data):
    # Преобразование JSON строки в DataFrame
    df = pd.read_json(BytesIO(json_data.encode("utf-8")))

    # Сохранение DataFrame в Excel файл
    excel_file_path = "statistics_output.xlsx"
    df.to_excel(excel_file_path, index=False)

    return excel_file_path
