import asyncio
from datetime import datetime

import websockets
import json
import requests
from crud import Postgres
from models import Message
from services.database import async_session
from handlers.process_message import process_message
import logging

db = Postgres(async_session)
logger = logging.getLogger(__name__)


def verify_token_with_auth_server(token):
    url = "https://backoffice.daribar.com/api/v1/users"
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(url, headers=headers)
    print(response)
    if response.status_code == 200:
        return response.json()  # Информация о пользователе
    else:
        return None  # Токен не валиден


async def handle_connection(websocket, path):
    async for message in websocket:
        try:
            print(f"Received message: {message}")
            data = json.loads(message)

            token = data.get("user_id")
            logger.info(f"token: {token}")
            user_data = verify_token_with_auth_server(token)
            logger.info(f"user_data: {user_data}")

            if not user_data:
                await websocket.send(
                    json.dumps(
                        {"token_validation": False, "error": "Invalid token"}
                    )
                )
                continue

            phone_number = user_data["result"]["phone"]
            content = data.get("content")
            created_at = datetime.utcnow()

            message_data = {
                "user_id": phone_number,
                "content": content,
                "created_at": created_at,
                "is_created_by_user": True,
            }

            await db.add_entity(message_data, Message)

            response_text = await process_message(message_data, db)

            response = {
                "content": {"text": response_text},
                "is_created_by_user": False,
                "token_validation": True,
            }
            logger.info(f"response text: {response_text}")
            await websocket.send(json.dumps(response, ensure_ascii=False))
        except Exception as e:
            logger.error(f"Error handling message: {e}")
            await websocket.send(
                json.dumps(
                    {
                        "token_validation": False,
                        "error": "Error processing message",
                    }
                )
            )


async def main():
    server = await websockets.serve(handle_connection, "0.0.0.0", 8081)
    print("Server started on ws://0.0.0.0:8081")
    await server.wait_closed()


if __name__ == "__main__":
    asyncio.run(main())
