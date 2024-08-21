import asyncio
import subprocess
import tempfile
import io
import requests
import logging
from utils.config import YANDEX_OAUTH_TOKEN, YANDEX_FOLDER_ID

YANDEX_IAM_TOKEN = None
logger = logging.getLogger(__name__)


def get_iam_token():
    global YANDEX_IAM_TOKEN
    url = "https://iam.api.cloud.yandex.net/iam/v1/tokens"
    payload = {"yandexPassportOauthToken": YANDEX_OAUTH_TOKEN}
    response = requests.post(url, json=payload)
    response.raise_for_status()
    YANDEX_IAM_TOKEN = response.json()["iamToken"]
    logger.info(f"Received new IAM token: {YANDEX_IAM_TOKEN}")


async def refresh_iam_token():
    while True:
        await asyncio.sleep(6 * 3600)
        get_iam_token()
        logger.info("IAM token refreshed")


def recognize_speech(audio_content, lang="ru-RU"):
    try:
        if not YANDEX_IAM_TOKEN:
            get_iam_token()
        url = f"https://stt.api.cloud.yandex.net/speech/v1/stt:recognize?folderId={YANDEX_FOLDER_ID}&lang={lang}"
        headers = {"Authorization": f"Bearer {YANDEX_IAM_TOKEN}"}

        logger.info(
            f"Sending request to Yandex STT API with URL: {url} and headers: {headers}"
        )
        response = requests.post(url, headers=headers, data=audio_content)

        if response.status_code == 200:
            result = response.json().get("result")
            if not result:
                logger.info(
                    "Recognition result is empty. Asking user to repeat the question."
                )
                return None
            logger.info(f"Recognition result: {result}")
            return result
        else:
            error_message = f"Failed to recognize speech, status code: {response.status_code}, response text: {response.text}"
            logger.error(error_message)
            raise Exception(error_message)
    except Exception as e:
        logger.error(f"Error in recognize_speech: {e}")
        return None


def synthesize_speech(text, lang_code):
    try:
        logger.info(
            f"Starting synthesis for text: '{text[:100]}' with lang_code: '{lang_code}'"
        )
        voice_settings = {
            "ru": {"lang": "ru-RU", "voice": "jane", "emotion": "good"},
            "kk": {"lang": "kk-KK", "voice": "amira", "emotion": "neutral"},
        }
        settings = voice_settings.get(lang_code, voice_settings["ru"])
        url = "https://tts.api.cloud.yandex.net/speech/v1/tts:synthesize"
        headers = {"Authorization": f"Bearer {YANDEX_IAM_TOKEN}"}

        data = {
            "text": text,
            "lang": settings["lang"],
            "voice": settings["voice"],
            "emotion": settings["emotion"],
            "folderId": YANDEX_FOLDER_ID,
            "format": "mp3",
            "sampleRateHertz": 48000,
            "speed": "1.2",
        }
        response = requests.post(url, headers=headers, data=data, stream=True)
        if response.status_code == 200:
            logger.info(f"Audio response content: OK for text: '{text[:100]}'")

            # Конвертация в aac
            input_audio = io.BytesIO(response.content)
            temp_input = tempfile.NamedTemporaryFile(
                delete=False, suffix=".mp3"
            )
            temp_output = tempfile.NamedTemporaryFile(
                delete=False, suffix=".aac"
            )
            with open(temp_input.name, "wb") as f:
                f.write(input_audio.read())

            # Использование ffmpeg для конвертации
            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-i",
                    temp_input.name,
                    "-c:a",
                    "aac",
                    temp_output.name,
                ],
                check=True,
            )

            with open(temp_output.name, "rb") as f:
                return f.read()

        else:
            error_message = f"Failed to synthesize speech, status code: {response.status_code}, response text: {response.text[:200]}"
            logger.error(error_message)
            raise Exception(error_message)
    except Exception as e:
        logger.error(f"Exception in synthesize_speech: {e}")
        return None


def translate_text(text, source_lang="ru", target_lang="kk"):
    url = "https://translate.api.cloud.yandex.net/translate/v2/translate"
    headers = {
        "Authorization": f"Bearer {YANDEX_IAM_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "folder_id": YANDEX_FOLDER_ID,
        "texts": [text],
        "targetLanguageCode": target_lang,
        "sourceLanguageCode": source_lang,
    }

    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        translations = response.json().get("translations", [])
        if translations:
            return translations[0]["text"]
        else:
            logger.error("Translation not found in response")
            return "Перевод не найден."
    except requests.exceptions.RequestException as e:
        logger.error(f"Error during translation request: {e}")
        return "Ошибка при запросе перевода."
    except Exception as e:
        logger.error(f"Unexpected error during translation: {e}")
        return "Произошла неожиданная ошибка."
