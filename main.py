import logging
import asyncio
from fastapi import FastAPI, BackgroundTasks, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from handlers.process_message import process_message, subscribe_to_messages
from crud import Postgres
from services.database import async_session

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()


async def get_db() -> AsyncSession:
    async with async_session() as session:
        yield session


db = Postgres(async_session)


class Message(BaseModel):
    user_id: str
    content: str
    created_at: str


@app.on_event("startup")
async def startup_event():
    logger.info("Supabase startup_event.")
    asyncio.ensure_future(subscribe_to_messages(db))


@app.post("/messages/")
async def create_message(
    message: Message,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db),
):
    db_instance = Postgres(session)
    background_tasks.add_task(process_message, message.dict(), db_instance)
    return {"message": "Message received"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
