import asyncio
import logging
from openai import AsyncOpenAI
from collections import defaultdict
from services.yandex_service import translate_text
from utils.config import OPENAI_API_KEY

client = AsyncOpenAI(api_key=OPENAI_API_KEY)
logger = logging.getLogger(__name__)

# Словарь для хранения очередей запросов для каждого треда
thread_queues = defaultdict(asyncio.Queue)


async def get_new_thread_id():
    try:
        thread = await client.beta.threads.create()
        return thread.id
    except Exception as e:
        logger.error(f"Error getting new thread ID: {e}")
        return None


async def process_queue(thread_id):
    while not thread_queues[thread_id].empty():
        task = await thread_queues[thread_id].get()
        try:
            result = await task()
            thread_queues[thread_id].task_done()
            return result
        except Exception as e:
            logger.error(f"Error processing task in queue: {e}")
            thread_queues[thread_id].task_done()


async def queue_task(thread_id, task):
    await thread_queues[thread_id].put(task)
    return await process_queue(thread_id)


async def process_question(question, thread_id=None, assistant_id=None):
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
        logger.info(f"Run created with ID: {run.id} and status: {run.status}")

        while run.status in ["queued", "in_progress", "cancelling"]:
            await asyncio.sleep(1)
            run = await client.beta.threads.runs.retrieve(
                thread_id=thread_id, run_id=run.id
            )
            logger.info(f"Run status updated to: {run.status}")

        if run.status == "completed":
            messages = await client.beta.threads.messages.list(
                thread_id=thread_id
            )
            logger.info(f"Retrieved messages: {messages.data}")

            if not messages.data:
                logger.error("No messages were retrieved.")
                return (
                    "Не удалось получить ответ от ассистента1.",
                    thread_id,
                    messages,
                )

            assistant_messages = [
                msg.content[0].text.value.split("```json")[0]
                for msg in messages.data
                if msg.role == "assistant"
            ]
            if assistant_messages:
                return assistant_messages[0], thread_id, messages
            else:
                logger.error("Assistant messages list is empty.")
                return (
                    "Не удалось получить ответ от ассистента1.",
                    thread_id,
                    messages,
                )
        else:
            logger.error(f"Run status is not completed: {run.status}")
            return "Не удалось получить ответ от ассистента2.", thread_id, run
    except Exception as e:
        logger.error(f"Error in process_question: {e}")
        return "Произошла ошибка при обработке вопроса.", thread_id, None


async def send_to_gpt(
    content, thread_id=None, assistant_id=None, target_language="ru"
):
    if isinstance(thread_id, bytes):
        thread_id = thread_id.decode("utf-8")
    if isinstance(assistant_id, bytes):
        assistant_id = assistant_id.decode("utf-8")

    async def task():
        try:
            response_text, new_thread_id, full_response = (
                await process_question(content, thread_id, assistant_id)
            )

            if (
                response_text is None
                or new_thread_id is None
                or full_response is None
            ):
                logger.error("One of the returned values is None")
                return (
                    "Произошла ошибка при отправке запроса в GPT.",
                    None,
                    None,
                )

            if target_language == "kk":
                response_text = translate_text(
                    response_text, source_lang="ru", target_lang="kk"
                )

            logger.info(
                f"Received response from GPT: {response_text} with new_thread_id: {new_thread_id} and full_response: {full_response}"
            )
            return response_text, new_thread_id, full_response
        except Exception as e:
            logger.error(f"Error in send_to_gpt: {e}")
            return "Произошла ошибка при отправке запроса в GPT.", None, None

    return await queue_task(thread_id, task)
