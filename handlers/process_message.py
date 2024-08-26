import base64
import json
import logging
from datetime import datetime
from dateutil import parser
from supabase import create_client, Client
from handlers.meta import get_user_language, validate_json_format
from services.audio_text_processor import process_audio_and_text
from services.openai_service import get_new_thread_id, send_to_gpt
from services.yandex_service import (
    synthesize_speech,
    translate_text,
)
from utils import get_current_time_in_almaty_naive, redis_client
from utils.config import SUPABASE_URL, SUPABASE_KEY
from models import User, Message, Survey
from crud import Postgres
from utils.config import ASSISTANT2_ID, ASSISTANT_ID
from utils.redis_client import clear_user_state

# Инициализация логирования
logging.basicConfig(level=logging.INFO)

# Логирование
logger = logging.getLogger(__name__)

# Инициализация Supabase
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


async def process_message(record, user_language, db: Postgres):
    try:
        user_id = record["user_id"]
        content = record["content"]
        content_dict = json.loads(content)
        gpt_response_json = None
        created_at_str = None

        if not validate_json_format(json.dumps(content)):
            logger.error(f"Invalid JSON format: {content}")
            return {
                "status": "error",
                "error_type": "invalid_request",
                "error_message": "Invalid JSON format",
            }

        message_data = content_dict

        text = await process_audio_and_text(message_data, user_language)

        if user_language == "kk":
            try:
                text = translate_text(text, source_lang="kk", target_lang="ru")
                logger.info(f"Translation result: {text}")
            except Exception as e:
                logger.error(f"Translation failed: {e}")
                text = None

        if text is None:
            response_text = "К сожалению, я не смог распознать ваш голос. Пожалуйста, повторите свой запрос."
            message_id, gpt_response_json, created_at_str = (
                await save_response_to_db(user_id, response_text, db)
            )
            logger.info("Text is None, saved response to DB and returning.")
            return {
                "status": "success",
                "message_id": message_id,
                "gpt_response_json": gpt_response_json,
                "created_at_str": created_at_str,
            }

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
                return {
                    "status": "error",
                    "error_type": "server_error",
                    "error_message": "Initial response text is empty.",
                }

            message_id, gpt_response_json, created_at_str = (
                await save_response_to_db(user_id, response_text, db)
            )
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
                return {
                    "status": "error",
                    "error_type": "server_error",
                    "error_message": "Response text is empty.",
                }

            message_id, gpt_response_json, created_at_str = (
                await save_response_to_db(user_id, response_text, db)
            )
            logger.info("Message processing completed2.")
            await redis_client.set_user_state(
                str(user_id), "response_received"
            )

            await parse_and_save_json_response(
                user_id, full_response, db, assistant_id
            )
            logger.info(
                f"response_text in process message: {response_text[:200]}"
            )

        await redis_client.mark_message_as_processed(user_id, message_id)
        if await final_response_reached(full_response):
            await clear_user_state(user_id, [message_id])

        return {
            "status": "success",
            "message_id": message_id,
            "gpt_response_json": gpt_response_json,
            "created_at_str": created_at_str,
        }

    except Exception as e:
        logger.error(f"Error processing message: {e}")
        return {
            "status": "error",
            "error_type": "server_error",
            "error_message": "An internal server error occurred.",
        }


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


async def save_response_to_db(user_id, response_text, db):
    try:
        if response_text:
            logger.info(
                f"Response text before synthesis: {response_text[:100]}"
            )
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
                saved_message = await db.add_entity(
                    {
                        "user_id": str(user_id),
                        "content": gpt_response_json,
                        "is_created_by_user": False,
                    },
                    Message,
                )
                logger.info(f"Response saved to database: for user {user_id}")

                message_id = saved_message.id
                created_at = saved_message.created_at
                created_at_str = created_at.strftime("%Y-%m-%dT%H:%M:%SZ")
                logger.info(f"Message ID retrieved: {message_id}")

                return str(message_id), gpt_response_json, created_at_str
            else:
                logger.error(
                    f"Audio response is None for text: {response_text[:100]}"
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
                response_data["userid"] = str(user_id)
                logger.info(f"userid: {response_data['userid']}")
                logger.info(f"response_data: {response_data}")

                if isinstance(assistant_id, bytes):
                    assistant_id = assistant_id.decode("utf-8")

                if (
                    "birthdate" in response_data
                    and response_data["birthdate"] is not None
                ):
                    try:
                        birthdate_str = response_data["birthdate"].strip()
                        try:
                            birthdate = datetime.strptime(
                                birthdate_str, "%d.%m.%Y"
                            ).date()
                        except ValueError:
                            birthdate = parser.parse(birthdate_str).date()
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
                    user_exists = await db.get_entity_parameter(
                        User, {"userid": response_data["userid"]}, None
                    )
                    if user_exists:
                        for parameter, value in response_data.items():
                            if parameter != "userid" and value:
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
                            await db.add_entity(response_data, User)
                            logger.info(
                                f"New user {response_data['userid']} added to the database"
                            )
                        except Exception as e:
                            logger.error(
                                f"Error adding new user to database: {e}"
                            )
                else:
                    try:
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
