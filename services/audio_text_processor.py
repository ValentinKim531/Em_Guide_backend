import base64
import io
import subprocess
import tempfile
from pydub import AudioSegment
import logging
from pydub.exceptions import CouldntDecodeError
from .yandex_service import recognize_speech

logger = logging.getLogger(__name__)


async def process_audio_and_text(message_data, user_language):
    text = None

    is_audio = "audio" in message_data and message_data["audio"]
    if is_audio:
        try:
            audio_content_encoded = message_data["audio"]
            audio_content = base64.b64decode(audio_content_encoded)
            logger.info("Successfully decoded base64 audio content.")

            # Сохранение аудиоданных в временный файл
            temp_input = tempfile.NamedTemporaryFile(
                delete=False, suffix=".aac"
            )
            with open(temp_input.name, "wb") as f:
                f.write(audio_content)
            logger.info(f"Saved AAC data to temporary file: {temp_input.name}")

            # Попытка конвертировать с помощью ffmpeg в формат WAV
            try:
                temp_output = tempfile.NamedTemporaryFile(
                    delete=False, suffix=".wav"
                )
                ffmpeg_command = [
                    "ffmpeg",
                    "-y",
                    "-i",
                    temp_input.name,
                    temp_output.name,
                ]
                subprocess.run(ffmpeg_command, check=True)
                logger.info(f"Successfully converted AAC to WAV using ffmpeg.")

                # Загрузка результата и обработка с помощью AudioSegment
                with open(temp_output.name, "rb") as f:
                    wav_data = f.read()
                audio = AudioSegment.from_file(
                    io.BytesIO(wav_data), format="wav"
                )
                logger.info("Successfully created AudioSegment from WAV data.")
            except subprocess.CalledProcessError as e:
                logger.error(f"ffmpeg failed to convert AAC to WAV: {e}")
                raise CouldntDecodeError(
                    "Failed to decode AAC file using ffmpeg"
                )

            # Конвертируем в OGG
            try:
                ogg_io = io.BytesIO()
                audio.export(ogg_io, format="ogg")
                ogg_io.seek(0)
                audio_content = ogg_io.read()
                logger.info("Successfully converted audio to OGG format.")
            except Exception as e:
                logger.error(f"Failed to convert audio to OGG format: {e}")
                raise

            # Получаем данные для транскрибации
            try:
                text = recognize_speech(
                    audio_content,
                    lang="kk-KK" if user_language == "kk" else "ru-RU",
                )
                logger.info(f"Speech recognition result: {text}")
            except Exception as e:
                logger.error(f"Speech recognition failed: {e}")
                text = None

        except Exception as e:
            logger.error(f"Error processing audio message: {e}")
            text = None
    else:
        text = message_data["text"]

    return text
