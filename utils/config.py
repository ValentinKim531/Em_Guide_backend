import os
from dotenv import load_dotenv

load_dotenv()


SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

DATABASE_URL = os.getenv("DATABASE_URL")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ASSISTANT_ID = os.getenv("ASSISTANT_ID")
ASSISTANT2_ID = os.getenv("ASSISTANT2_ID")

REDIS_URL = os.getenv("REDIS_URL", default="")

YANDEX_OAUTH_TOKEN = os.getenv("YANDEX_OAUTH_TOKEN")
YANDEX_FOLDER_ID = os.getenv("YANDEX_FOLDER_ID")
