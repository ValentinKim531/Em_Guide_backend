import asyncio
from datetime import datetime
import httpx
import websockets
import json
from crud import Postgres
from handlers.meta import get_user_language
from models import Message
from services.audio_text_processor import process_audio_and_text
from services.database import async_session
from handlers.process_message import process_message
import logging
import ftfy
from services.history_service import generate_chat_history
from services.language_service import change_language
from services.reminder_service import change_reminder_time
from services.statistics_service import generate_statistics_file

db = Postgres(async_session)
logger = logging.getLogger(__name__)


async def verify_token_with_auth_server(token):
    try:
        url = "https://backoffice.daribar.com/api/v1/users"
        headers = {"Authorization": f"Bearer {token}"}
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers)
            if response.status_code == 200:
                return response.json()  # Информация о пользователе
            else:
                return None
    except Exception as e:
        logger.error(f"Error verifying token: {e}")
        return None


async def handle_command(action, user_id, db, data=None):
    if action == "fetch_history":
        try:
            chat_history = await generate_chat_history(user_id, db)
            if not chat_history:
                return {
                    "type": "response",
                    "status": "error",
                    "action": "fetch_history",
                    "error": "no_history",
                    "message": "No message history available.",
                }
            return {
                "type": "response",
                "status": "success",
                "action": "fetch_history",
                "data": {"messages": chat_history},
            }
        except Exception as e:
            logger.error(f"Error generating chat history: {e}")
            return {
                "type": "response",
                "status": "error",
                "action": "fetch_history",
                "error": "server_error",
                "message": "An internal server error occurred. Please try again later.",
            }
    elif action == "export_stats":
        try:
            stats = await generate_statistics_file(user_id, db)
            if not stats:
                return {
                    "type": "response",
                    "status": "error",
                    "action": "export_stats",
                    "error": "no_stats",
                    "message": "No stats available.",
                }
            return {
                "type": "response",
                "status": "success",
                "action": "export_stats",
                "data": {"file_json": stats},
            }
        except Exception as e:
            logger.error(f"Error generating export stats: {e}")
            return {
                "type": "response",
                "status": "error",
                "action": "export_stats",
                "error": "server_error",
                "message": "An internal server error occurred. Please try again later.",
            }
    elif action == "change_reminder_time":
        try:
            reminder_time = data.get("data", {}).get("reminder_time")
            if not reminder_time:
                return {
                    "type": "response",
                    "status": "error",
                    "action": "change_reminder_time",
                    "error": "no_reminder_time",
                    "message": "No reminder_time pointed.",
                }
            response = await change_reminder_time(user_id, reminder_time, db)
            return {
                "type": "response",
                "status": "success",
                "action": "change_reminder_time",
                "data": {"reminder_time": response},
            }
        except Exception as e:
            logger.error(f"Error updating reminder time: {e}")
            return {
                "type": "response",
                "status": "error",
                "action": "change_reminder_time",
                "error": "server_error",
                "message": "An internal server error occurred. Please try again later.",
            }

    elif action == "change_language":
        try:
            language = data.get("data", {}).get("language")
            if not language:
                return {
                    "type": "response",
                    "status": "error",
                    "action": "change_language",
                    "error": "no_change_language",
                    "message": "No language pointed.",
                }
            response = await change_language(user_id, language, db)
            return {
                "type": "response",
                "status": "success",
                "action": "change_language",
                "data": {"language": response},
            }
        except Exception as e:
            logger.error(f"Error updating language: {e}")
            return {
                "type": "response",
                "status": "error",
                "action": "change_language",
                "error": "server_error",
                "message": "An internal server error occurred. Please try again later.",
            }

    return {
        "type": "response",
        "status": "error",
        "error": "invalid_request",
        "message": "The request format is invalid. Please check the data and try again.",
    }


async def handle_connection(websocket, path):
    async for message in websocket:
        try:
            data = json.loads(message)
            logger.info(f"data: {data}")
            token = data.get("token")
            user_data = await verify_token_with_auth_server(token)
            if not user_data:
                response = {
                    "type": "response",
                    "status": "error",
                    "error": "invalid_token",
                    "message": "Invalid or expired JWT token. Please re-authenticate.",
                }
                await websocket.send(json.dumps(response, ensure_ascii=False))
                continue

            user_id = user_data["result"]["phone"]
            message_type = data.get("type")
            action = data.get("action")

            try:
                content_dict = data.get("data", {}).get("content", {})
                logger.info(f"Original content dictionary: {content_dict}")

                # Если content является строкой, попробуем распарсить как JSON
                if isinstance(content_dict, str):
                    try:
                        content_dict = json.loads(content_dict)
                        logger.info(
                            "Content was a string and has been successfully parsed into a dictionary."
                        )
                    except json.JSONDecodeError as e:
                        logger.warning(
                            f"Failed to parse content string as JSON: {e}"
                        )

                # Декодирование поля 'text' с помощью ftfy
                if "text" in content_dict:
                    fixed_text = ftfy.fix_text(content_dict["text"])
                    content_dict["text"] = fixed_text
                    logger.info(f"Fixed text with ftfy: {fixed_text}")

                # Преобразование обратно в JSON, если необходимо
                content = content_dict
                logger.info(f"Decoded message data: {content}")

            except Exception as e:
                logger.error(f"Error decoding: {e}")
                response = {
                    "type": "response",
                    "status": "error",
                    "action": "message",
                    "error": "invalid_request",
                    "message": f"Error decoding the content string: {e}",
                }
                await websocket.send(json.dumps(response, ensure_ascii=False))
                continue

            if message_type == "command":
                response = await handle_command(action, user_id, db, data)
                await websocket.send(json.dumps(response, ensure_ascii=False))
            elif message_type == "system":
                response = await handle_command(action, user_id, db)
                await websocket.send(json.dumps(response, ensure_ascii=False))
            elif message_type == "message":

                is_created_by_user = data.get("data").get("is_created_by_user")
                front_id = data.get("data").get("front_id")

                user_language = await get_user_language(
                    user_id, content.get("language"), db
                )
                text = await process_audio_and_text(content, user_language)
                content["text"] = text

                message_data = {
                    "user_id": user_id,
                    "content": json.dumps(content, ensure_ascii=False),
                    "is_created_by_user": is_created_by_user,
                    "front_id": front_id,
                }
                try:
                    saved_message = await db.add_entity(message_data, Message)

                    if saved_message:
                        logger.info(f"saved_messaage: {saved_message}")

                        response_from_bot_user = {
                            "type": "response",
                            "status": "success",
                            "action": "message",
                            "data": {
                                "id": str(saved_message.id),
                                "created_at": saved_message.created_at.strftime(
                                    "%Y-%m-%dT%H:%M:%SZ"
                                ),
                                "content": saved_message.content,
                                "is_created_by_user": True,
                                "front_id": saved_message.front_id,
                            },
                        }

                        try:
                            log_message = json.dumps(
                                response_from_bot_user, ensure_ascii=False
                            )
                            shortened_log_message = (
                                f"{log_message[:300]}...{log_message[-200:]}"
                            )
                            logger.info(
                                f"Sending response to user (success confirmation): {shortened_log_message}"
                            )
                            await websocket.send(
                                json.dumps(
                                    response_from_bot_user, ensure_ascii=False
                                )
                            )
                        except Exception as e:
                            logger.error(
                                f"Failed to send JSON response (user confirmation): {e}"
                            )
                            response_error = {
                                "type": "response",
                                "status": "error",
                                "error": "json_serialization_error",
                                "message": f"Error serializing response to JSON: {str(e)}",
                            }
                            await websocket.send(
                                json.dumps(response_error, ensure_ascii=False)
                            )

                    message_id, gpt_response_json, created_at_str = (
                        await process_message(message_data, user_language, db)
                    )
                    response_from_bot = {
                        "type": "message",
                        "data": {
                            "id": message_id,
                            "created_at": created_at_str,
                            "content": gpt_response_json,
                            "is_created_by_user": False,
                        },
                    }

                    try:
                        log_message = json.dumps(
                            response_from_bot, ensure_ascii=False
                        )
                        shortened_log_message = (
                            f"{log_message[:300]}...{log_message[-200:]}"
                        )
                        logger.info(
                            f"Sending response from assistant: {shortened_log_message}"
                        )
                        await websocket.send(
                            json.dumps(response_from_bot, ensure_ascii=False)
                        )
                    except Exception as e:
                        logger.error(
                            f"Failed to send JSON response (assistant response): {e}"
                        )
                        response_error = {
                            "type": "response",
                            "status": "error",
                            "error": "json_serialization_error",
                            "message": f"Error serializing response to JSON: {str(e)}",
                        }
                        await websocket.send(
                            json.dumps(response_error, ensure_ascii=False)
                        )
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
                    response = {
                        "type": "response",
                        "status": "error",
                        "error": "server_error",
                        "message": str(e),
                    }
                    await websocket.send(
                        json.dumps(response, ensure_ascii=False)
                    )
        except Exception as e:
            logger.error(f"Error handling connection: {e}")
            await websocket.send(
                json.dumps(
                    {
                        "type": "response",
                        "status": "error",
                        "error": "server_error",
                        "message": f"Error processing message: {str(e)}",
                    },
                    ensure_ascii=False,
                )
            )


async def main():
    try:
        server = await websockets.serve(handle_connection, "0.0.0.0", 8081)
        print("Server started on ws://0.0.0.0:8081")
        await server.wait_closed()
    except Exception as e:
        logger.error(f"Error starting websocket server: {e}")


if __name__ == "__main__":
    asyncio.run(main())
