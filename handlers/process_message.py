import base64
import json
import logging
from datetime import datetime
from supabase import create_client, Client
from handlers.meta import get_user_language, validate_json_format
from services.openai_service import get_new_thread_id, send_to_gpt
from services.statistics_service import generate_statistics_file
from services.yandex_service import (
    recognize_speech,
    synthesize_speech,
    translate_text,
)
from utils import get_current_time_in_almaty_naive, redis_client
from utils.config import SUPABASE_URL, SUPABASE_KEY
from models import User, Message, Survey
from crud import Postgres
from utils.config import ASSISTANT2_ID, ASSISTANT_ID
import uuid

from utils.redis_client import clear_user_state

# Инициализация логирования
logging.basicConfig(level=logging.INFO)

# Логирование
logger = logging.getLogger(__name__)

# Инициализация Supabase
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


async def process_message(record, db: Postgres):
    try:
        user_id = record["user_id"]
        content = record["content"]
        message_id = record["user_id"]

        logger.info(
            f"Processing message for user_id: {user_id}, content: {content}"
        )

        if not validate_json_format(content):
            logger.error(f"Invalid JSON format: {content}")
            return

        message_data = json.loads(content)
        logger.info(f"Decoded message data: {message_data}")

        message_language = message_data.get("language")

        if "menu" in message_data and message_data["menu"] == "statistics":
            statistics_json, excel_file_path = await generate_statistics_file(
                user_id, db
            )
            response = {
                "menu": "statistics",
                "statisticsFile": statistics_json,
                "excelFilePath": excel_file_path,
            }
            await save_response_to_db(user_id, json.dumps(response), db)
            logger.info(f"Statistics sent for user {user_id}")
            return response

        user_language = await get_user_language(user_id, message_language, db)

        is_audio = "audio" in message_data
        if is_audio:
            audio_content_encoded = message_data["audio"]
            audio_content = base64.b64decode(audio_content_encoded)
            text = recognize_speech(
                audio_content,
                lang="kk-KK" if user_language == "kk" else "ru-RU",
            )
            if user_language == "kk" and text:
                text = translate_text(text, source_lang="kk", target_lang="ru")
        else:
            text = message_data["text"]
            if user_language == "kk":
                text = translate_text(text, source_lang="kk", target_lang="ru")

        if text is None:
            response_text = "К сожалению, я не смог распознать ваш голос. Пожалуйста, повторите свой запрос."
            await save_response_to_db(user_id, response_text, db)
            logger.info("Text is None, saved response to DB and returning.")
            return response_text

        user_state = await redis_client.get_user_state(str(user_id))
        logger.info(f"Retrieved state {user_state} for user_id {user_id}")

        if user_state is None:
            logger.info(f"Checking if user {user_id} exists in the database")
            user = await db.get_entity_parameter(
                User, {"userid": str(user_id)}, None
            )
            if not user:
                new_user_data = {
                    "userid": str(user_id),
                    "language": user_language,
                    "created_at": get_current_time_in_almaty_naive(),
                    "updated_at": get_current_time_in_almaty_naive(),
                }
                await db.add_entity(new_user_data, User)
                logger.info(f"New user {user_id} registered in the database")

            assistant_id = ASSISTANT2_ID if not user else ASSISTANT_ID

            new_thread_id = await get_new_thread_id()
            await redis_client.save_thread_id(str(user_id), new_thread_id)
            await redis_client.save_assistant_id(str(user_id), assistant_id)
            logger.info(
                f"Generated and saved new thread_id {new_thread_id} for user {user_id}"
            )

            logger.info(f"Sending initial message to GPT for user {user_id}")
            response_text, new_thread_id, full_response = await send_to_gpt(
                "Здравствуйте", new_thread_id, assistant_id
            )

            if user_language == "kk":
                response_text = translate_text(
                    response_text, source_lang="ru", target_lang="kk"
                )

            if not response_text:
                logger.error("Initial response text is empty.")
                return

            await save_response_to_db(user_id, response_text, db, is_audio)
            logger.info("Message processing completed1.")
            await redis_client.set_user_state(
                str(user_id), "awaiting_response"
            )

        else:
            logger.info(
                f"User {user_id} sent a message, forwarding content to GPT."
            )
            thread_id = await redis_client.get_thread_id(user_id)
            assistant_id = await redis_client.get_assistant_id(user_id)
            response_text, new_thread_id, full_response = await send_to_gpt(
                text, thread_id, assistant_id
            )
            await redis_client.save_thread_id(str(user_id), new_thread_id)

            if user_language == "kk":
                response_text = translate_text(
                    response_text, source_lang="ru", target_lang="kk"
                )

            if not response_text:
                logger.error("Response text is empty.")
                return

            await save_response_to_db(user_id, response_text, db, is_audio)
            logger.info("Message processing completed2.")
            await redis_client.set_user_state(
                str(user_id), "response_received"
            )

            if is_audio:
                audio_response = synthesize_speech(
                    response_text, user_language
                )
                if audio_response:
                    await save_response_to_db(user_id, audio_response, db)
                else:
                    logger.error("Audio response is empty.")

            await parse_and_save_json_response(
                user_id, full_response, db, assistant_id
            )
            logger.info(f"response_text in process message : {response_text}")

        await redis_client.mark_message_as_processed(user_id, message_id)
        if await final_response_reached(full_response):
            await clear_user_state(user_id, [message_id])

        return response_text

    except Exception as e:
        logger.error(f"Error processing message: {e}")


async def final_response_reached(full_response):
    """
    Определяет, является ли текущий ответ финальным, основываясь на содержании полного ответа от GPT.
    """
    try:
        # Проход по всем сообщениям в полном ответе
        for msg in full_response.data:
            for content in msg.content:
                text = content.text.value if hasattr(content, "text") else ""

                # Проверка на наличие JSON с маркером окончания
                if "json" in text:
                    return True
        return False
    except Exception as e:
        logger.error(f"Error determining final response: {e}")
        return False


async def save_response_to_db(user_id, response_text, db, is_audio=False):
    try:
        if response_text:
            logger.info(f"Response text before synthesis: {response_text}")
            audio_response = synthesize_speech(response_text, "ru")
            if audio_response:
                audio_response_encoded = base64.b64encode(
                    audio_response
                ).decode("utf-8")
                gpt_response_json = json.dumps(
                    {"text": response_text, "audio": audio_response_encoded},
                    ensure_ascii=False,
                )

                logger.info(
                    f"Saving GPT response to the database for user {user_id}"
                )
                await db.add_entity(
                    {
                        "user_id": str(
                            user_id
                        ),  # Преобразование UUID в строку
                        "content": gpt_response_json,
                        "is_created_by_user": False,
                    },
                    Message,
                )
                logger.info(f"Response saved to database: for user {user_id}")
            else:
                logger.error(
                    f"Audio response is None for text: {response_text}"
                )
        else:
            logger.error("Response text is empty, cannot save to database.")
    except Exception as e:
        logger.error(f"Error in save_response_to_db: {e}")


async def parse_and_save_json_response(
    user_id, full_response, db, assistant_id
):
    try:
        final_response_json = None
        for msg in full_response.data:
            for content in msg.content:
                text = content.text.value if hasattr(content, "text") else ""
                if "json" in text:
                    final_response_json = text
                    break
            if final_response_json:
                break

        if final_response_json:
            logger.info(
                f"Extracting JSON from response: {final_response_json}"
            )
            json_start = final_response_json.find("```json")
            json_end = final_response_json.rfind("```")
            if json_start != -1 and json_end != -1:
                response_data_str = final_response_json[
                    json_start + len("```json") : json_end
                ].strip()
                response_data = json.loads(response_data_str)

                response_data["userid"] = uuid.UUID(user_id)
                logger.info(f"userid: {response_data['userid']}")
                logger.info(f"response_data: {response_data}")

                if isinstance(assistant_id, bytes):
                    assistant_id = assistant_id.decode("utf-8")

                if "birthdate" in response_data and response_data["birthdate"]:
                    try:
                        birthdate_str = response_data["birthdate"]
                        birthdate = datetime.strptime(
                            birthdate_str, "%d %B %Y"
                        ).date()
                        response_data["birthdate"] = birthdate
                    except ValueError as e:
                        logger.error(f"Error parsing birthdate: {e}")

                if (
                    "reminder_time" in response_data
                    and response_data["reminder_time"]
                ):
                    try:
                        reminder_time_str = response_data["reminder_time"]
                        reminder_time = datetime.strptime(
                            reminder_time_str, "%H:%M"
                        ).time()
                        response_data["reminder_time"] = reminder_time
                        logger.info(
                            f"Converted reminder_time: {reminder_time}"
                        )
                    except ValueError as e:
                        logger.error(f"Error parsing reminder_time: {e}")

                # Updating user data in the database
                if assistant_id == ASSISTANT2_ID:
                    for parameter, value in response_data.items():
                        if parameter != "userid":
                            try:
                                logger.info(
                                    f"Updating {parameter} with value {value} for user {response_data['userid']}"
                                )
                                await db.update_entity_parameter(
                                    entity_id=response_data["userid"],
                                    parameter=parameter,
                                    value=value,
                                    model_class=User,
                                )
                                logger.info(
                                    f"Updated {parameter} successfully"
                                )
                            except Exception as e:
                                logger.error(
                                    f"Error updating {parameter}: {e}"
                                )
                else:
                    try:
                        response_data["created_at"] = (
                            get_current_time_in_almaty_naive()
                        )
                        response_data["updated_at"] = (
                            get_current_time_in_almaty_naive()
                        )
                        if response_data["pain_intensity"] is not None:
                            response_data["pain_intensity"] = int(
                                response_data["pain_intensity"]
                            )
                        else:
                            response_data["pain_intensity"] = 0
                            logger.info(
                                f"pain_intensity: {response_data['pain_intensity']}"
                            )
                        await db.add_entity(response_data, Survey)
                        logger.info(
                            f"Survey response saved for user {user_id}"
                        )
                    except Exception as e:
                        logger.error(
                            f"Error adding or updating response to database: {e}"
                        )
    except Exception as e:
        logger.error(f"Error saving response to database: {e}")
