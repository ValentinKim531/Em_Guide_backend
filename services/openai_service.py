import asyncio
import logging
from openai import AsyncOpenAI

from utils.config import OPENAI_API_KEY

client = AsyncOpenAI(api_key=OPENAI_API_KEY)
logger = logging.getLogger(__name__)


async def get_new_thread_id():
    thread = await client.beta.threads.create()
    return thread.id


async def process_question(question, thread_id=None, assistant_id=None):
    # Декодируем thread_id и assistant_id из байтовой строки в строку
    if isinstance(thread_id, bytes):
        thread_id = thread_id.decode("utf-8")
    if isinstance(assistant_id, bytes):
        assistant_id = assistant_id.decode("utf-8")

    logger.info(
        f"Processing question with GPT-4, question: {question}, thread_id: {thread_id}, assistant_id: {assistant_id}"
    )
    try:
        logger.info("Processing question with GPT-4")
        if not thread_id:
            thread = await client.beta.threads.create()
            thread_id = thread.id
            logger.info(f"New thread created with ID: {thread_id}")

        await client.beta.threads.messages.create(
            thread_id=thread_id, role="user", content=question
        )
        run = await client.beta.threads.runs.create(
            thread_id=thread_id, assistant_id=assistant_id
        )

        while run.status in ["queued", "in_progress", "cancelling"]:
            await asyncio.sleep(1)
            run = await client.beta.threads.runs.retrieve(
                thread_id=thread_id, run_id=run.id
            )

        if run.status == "completed":
            messages = await client.beta.threads.messages.list(
                thread_id=thread_id
            )
            assistant_messages = [
                msg.content[0].text.value.split("```json")[0]
                for msg in messages.data
                if msg.role == "assistant"
            ]
            if assistant_messages:
                return assistant_messages[0], thread_id, messages
            else:
                return (
                    "Не удалось получить ответ от ассистента.",
                    thread_id,
                    messages,
                )
        else:
            return "Не удалось получить ответ от ассистента.", thread_id, run
    except Exception as e:
        logger.error(f"Error in process_question: {e}")
        return "Произошла ошибка при обработке вопроса.", thread_id, None
