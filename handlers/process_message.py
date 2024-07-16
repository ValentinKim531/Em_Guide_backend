import json
import asyncio
import logging
from datetime import datetime
from supabase import create_client, Client
from websockets import connect, WebSocketException
from services.openai_service import get_new_thread_id
from utils import get_current_time_in_almaty_naive, redis_client
from utils.config import SUPABASE_URL, SUPABASE_KEY
from models import User, Message, Survey
from crud import Postgres
from utils.config import ASSISTANT2_ID, ASSISTANT_ID
import uuid

# Инициализация логирования
logging.basicConfig(level=logging.INFO)

# Настройка уровня логирования для SQLAlchemy
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

# Логирование
logger = logging.getLogger(__name__)

# Инициализация Supabase
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


async def send_to_gpt(
    content, thread_id=None, assistant_id=None, initial=False
):
    from services.openai_service import process_question

    if initial:
        content = "Здравствуйте"

        # Декодируем thread_id и assistant_id из байтовой строки в строку
        if isinstance(thread_id, bytes):
            thread_id = thread_id.decode("utf-8")
        if isinstance(assistant_id, bytes):
            assistant_id = assistant_id.decode("utf-8")

    logger.info(
        f"Sending content to GPT: {content} with thread_id: {thread_id} and assistant_id: {assistant_id}"
    )
    response_text, new_thread_id, full_response = await process_question(
        content, thread_id, assistant_id
    )
    logger.info(
        f"Received response from GPT: {response_text} with new_thread_id: {new_thread_id}"
    )
    return response_text, new_thread_id, full_response


async def subscribe_to_messages(db: Postgres):
    logger.info("Starting subscribe_to_messages loop.")
    while True:
        try:
            ws_url = (
                SUPABASE_URL.replace("https", "wss")
                + "/realtime/v1/websocket?apikey="
                + SUPABASE_KEY
            )
            logger.info(f"Connecting to {ws_url}")
            async with connect(
                ws_url,
                extra_headers={"Authorization": f"Bearer {SUPABASE_KEY}"},
            ) as websocket:
                logger.info("WebSocket connection established.")
                subscription_payload = {
                    "event": "phx_join",
                    "topic": "realtime:public:messages",
                    "payload": {},
                    "ref": 1,
                }
                await websocket.send(json.dumps(subscription_payload))
                logger.info("Subscribed to Supabase websocket.")
                while True:
                    result = await websocket.recv()
                    logger.info(f"Received message: {result}")
                    if result:
                        try:
                            message = json.loads(result)
                            if message.get("event") == "INSERT":
                                record = message["payload"]["record"]
                                if record["is_created_by_user"]:
                                    logger.info(
                                        f"Processing new message: {record}"
                                    )
                                    # Проверка, если сообщение уже обработано
                                    if not await redis_client.is_message_processed(
                                        record["id"]
                                    ):
                                        await process_message(record, db)
                                        await redis_client.mark_message_as_processed(
                                            record["user_id"], record["id"]
                                        )
                        except json.JSONDecodeError as e:
                            logger.error(f"Error decoding JSON: {e}")
                    await asyncio.sleep(1)
        except WebSocketException as e:
            logger.error(f"WebSocket connection error: {e}. Reconnecting...")
        except Exception as e:
            logger.error(f"Unexpected error: {e}. Reconnecting...")
        await asyncio.sleep(5)  # ждем перед переподключением


async def process_message(record, db: Postgres):
    try:
        logger.info(f"Processing message: {record}")
        user_id = record["user_id"]
        content = record["content"]
        message_id = record["id"]

        # Проверка состояния пользователя
        user_state = await redis_client.get_user_state(str(user_id))
        logger.info(f"Retrieved state {user_state} for user_id {user_id}")

        assistant_id = await redis_client.get_assistant_id(str(user_id))
        if assistant_id is None:
            assistant_id = ASSISTANT_ID

        if user_state is None:
            # Проверка существования пользователя в базе данных
            logger.info(f"Checking if user {user_id} exists in the database")
            user = await db.get_entity_parameter(
                User, {"userid": str(user_id)}, None
            )
            if user:
                logger.info(f"User {user_id} found: {user}")
            else:
                logger.info(f"User {user_id} not found, registering new user.")

                new_user_data = {
                    "userid": uuid.UUID(user_id),
                    "created_at": get_current_time_in_almaty_naive(),
                    "updated_at": get_current_time_in_almaty_naive(),
                }
                await db.add_entity(new_user_data, User)
                logger.info(f"New user {user_id} registered in the database")
                assistant_id = ASSISTANT2_ID

            # Создание нового thread_id для диалога
            new_thread_id = await get_new_thread_id()
            await redis_client.save_thread_id(str(user_id), new_thread_id)
            await redis_client.save_assistant_id(str(user_id), assistant_id)
            logger.info(
                f"Generated and saved new thread_id {new_thread_id} for user {user_id}"
            )

            # Отправка сообщения в GPT для новой регистрации или ежедневного опроса
            logger.info(f"Sending initial message to GPT for user {user_id}")
            response_text, new_thread_id, full_response = await send_to_gpt(
                "Здравствуйте", new_thread_id, assistant_id
            )

            # Сохранение ответа GPT в базу данных в формате JSON
            gpt_response_json = json.dumps(
                {"text": response_text}, ensure_ascii=False
            )
            logger.info(
                f"Saving GPT response to the database for user {user_id}"
            )
            await db.add_entity(
                {
                    "user_id": uuid.UUID(user_id),
                    "content": gpt_response_json,
                    "is_created_by_user": False,
                },
                Message,
            )
            logger.info(
                f"Response saved to database: {gpt_response_json} for user {user_id}"
            )
            logger.info("Message processing completed.")
            await redis_client.set_user_state(
                str(user_id), "awaiting_response"
            )

        else:
            # Если состояние уже существует, то обрабатываем сообщение от пользователя
            logger.info(
                f"User {user_id} sent a message, forwarding content to GPT."
            )
            thread_id = await redis_client.get_thread_id(user_id)
            response_text, new_thread_id, full_response = await send_to_gpt(
                content, thread_id, assistant_id
            )
            await redis_client.save_thread_id(str(user_id), new_thread_id)

            # Сохранение ответа GPT в базу данных
            gpt_response_json = json.dumps(
                {"text": response_text}, ensure_ascii=False
            )
            logger.info(
                f"Saving GPT response to the database for user {user_id}"
            )
            await db.add_entity(
                {
                    "user_id": uuid.UUID(user_id),
                    "content": gpt_response_json,
                    "is_created_by_user": False,
                },
                Message,
            )
            logger.info(
                f"Response saved to database: {gpt_response_json} for user {user_id}"
            )
            logger.info("Message processing completed.")
            await redis_client.set_user_state(
                str(user_id), "response_received"
            )

            # Парсинг JSON ответа и сохранение в соответствующие таблицы
            final_response_json = None
            for msg in full_response.data:
                if "json" in msg.content[0].text.value:
                    final_response_json = msg.content[0].text.value

            if final_response_json:
                try:
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

                        # Добавляем userid в данные ответа
                        response_data["userid"] = uuid.UUID(user_id)
                        logger.info(f"userid: {response_data['userid']}")
                        logger.info(f"response_data: {response_data}")

                        if isinstance(assistant_id, bytes):
                            assistant_id = assistant_id.decode("utf-8")

                        if (
                            "birthdate" in response_data
                            and response_data["birthdate"] is not None
                        ):
                            try:
                                birthdate_str = response_data["birthdate"]
                                birthdate = datetime.strptime(
                                    birthdate_str, "%d %B %Y"
                                ).date()
                                response_data["birthdate"] = birthdate
                            except ValueError as e:
                                logger.error(f"Error parsing birthdate: {e}")

                        # Преобразование времени напоминания в объект time
                        if (
                            "reminder_time" in response_data
                            and response_data["reminder_time"] is not None
                        ):
                            try:
                                reminder_time_str = response_data[
                                    "reminder_time"
                                ]
                                reminder_time = datetime.strptime(
                                    reminder_time_str, "%H:%M"
                                ).time()
                                response_data["reminder_time"] = reminder_time
                                logger.info(
                                    f"Converted reminder_time: {reminder_time}"
                                )
                            except ValueError as e:
                                logger.error(
                                    f"Error parsing reminder_time: {e}"
                                )

                        if assistant_id == ASSISTANT2_ID:
                            # Сохранение данных регистрации в таблицу users
                            for parameter, value in response_data.items():

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
                                if response_data["pain_intensity"]:
                                    response_data["pain_intensity"] = int(
                                        response_data["pain_intensity"]
                                    )
                                else:
                                    response_data["pain_intensity"] = 0
                                logger.info(
                                    f"pain_intensity: {response_data['pain_intensity']}"
                                )

                                response_data["userid"] = uuid.UUID(user_id)
                                response_data["created_at"] = (
                                    get_current_time_in_almaty_naive()
                                )
                                response_data["updated_at"] = (
                                    get_current_time_in_almaty_naive()
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

                finally:

                    await redis_client.mark_message_as_processed(
                        user_id, message_id
                    )
                    await asyncio.sleep(2)
                    processed_message_ids = (
                        await redis_client.get_processed_messages(user_id)
                    )
                    await clear_user_state(user_id, processed_message_ids)
                    logger.info(
                        f"User state and thread information cleared for user {user_id}"
                    )

    except Exception as e:
        logger.error(f"Error processing message: {e}")


async def clear_user_state(user_id, processed_message_ids):
    await redis_client.delete_user_state(user_id)
    await redis_client.delete_thread_id(user_id)
    await redis_client.delete_assistant_id(user_id)
    await redis_client.delete_processed_messages(
        user_id, processed_message_ids
    )
    logger.info(
        f"User state and thread information cleared for user {user_id}"
    )
