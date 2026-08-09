import os
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("GROQ_API_KEY")

if api_key:
    print(f"✅ API-ключ загружен: {api_key[:8]}...{api_key[-4:]}")
    print(f"Длина ключа: {len(api_key)} символов")
else:
    print("❌ API-ключ не найден. Проверьте файл .env")