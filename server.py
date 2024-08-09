import asyncio
import websockets
import json
from crud import Postgres
from sqlalchemy.ext.asyncio import AsyncSession
from models import Message
from services.database import async_session
from handlers.process_message import process_message, save_response_to_db
import uuid
import logging

db = Postgres(async_session)
logger = logging.getLogger(__name__)


async def handle_connection(websocket, path):
    async for message in websocket:
        try:
            print(f"Received message: {message}")
            data = json.loads(message)

            # Сохранение сообщения в базу данных
            user_id = data.get("user_id")
            content = data.get("content")
            created_at = data.get("created_at")

            message_data = {
                "user_id": str(user_id),
                "content": content,
                "created_at": created_at,
                "is_created_by_user": True,
            }

            await db.add_entity(message_data, Message)

            # Обработка сообщения
            response_text = await process_message(message_data, db)

            # Отправка ответа клиенту
            response = {"text": response_text, "is_created_by_user": False}
            logger.info(f"response text: {response_text}")
            await websocket.send(json.dumps(response, ensure_ascii=False))
        except Exception as e:
            logger.error(f"Error handling message: {e}")
            await websocket.send(
                json.dumps({"error": "Error processing message"})
            )


async def main():
    server = await websockets.serve(handle_connection, "0.0.0.0", 8081)
    print("Server started on ws://0.0.0.0:8081")
    await server.wait_closed()


if __name__ == "__main__":
    asyncio.run(main())
