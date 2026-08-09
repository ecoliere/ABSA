# src/redis_client.py
import os
import logging
from redis.asyncio import Redis
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# ВСЕ параметры ТОЛЬКО из переменных окружения
REDIS_CONFIG = {
    "host": os.environ["REDIS_HOST"],
    "port": int(os.environ["REDIS_PORT"]),
    "db": int(os.environ["REDIS_DB"]),
    "password": os.getenv("REDIS_PASSWORD", None),   # может быть None (без пароля)
    "decode_responses": True,
    "socket_connect_timeout": int(os.getenv("REDIS_SOCKET_TIMEOUT", "30")),
    "socket_timeout": int(os.getenv("REDIS_SOCKET_TIMEOUT", "30")),
    "retry_on_timeout": True,
}

# Префикс для изоляции окружений (из .env, с fallback на 'dev')
ENV = os.getenv("ENV", "dev")
QUEUE_NAME = f"task_queue:{ENV}"

_redis_client: Redis | None = None


async def init_redis() -> Redis:
    """Инициализирует Redis клиент. Вызывается один раз при старте приложения."""
    global _redis_client
    try:
        _redis_client = Redis(
            host=REDIS_CONFIG["host"],
            port=REDIS_CONFIG["port"],
            db=REDIS_CONFIG["db"],
            password=REDIS_CONFIG["password"],
            decode_responses=REDIS_CONFIG["decode_responses"],
            socket_connect_timeout=REDIS_CONFIG["socket_connect_timeout"],
            socket_timeout=REDIS_CONFIG["socket_timeout"],
            retry_on_timeout=REDIS_CONFIG["retry_on_timeout"],
            health_check_interval=30,          # поддерживает соединение активным
        )
        # Проверяем соединение
        await _redis_client.ping()
        logger.info(f"✅ Redis подключён: {REDIS_CONFIG['host']}:{REDIS_CONFIG['port']}")
        return _redis_client
    except KeyError as e:
        raise RuntimeError(f"❌ Отсутствует переменная окружения: {e}. Проверьте .env файл.")
    except Exception as e:
        logger.error(f"❌ Ошибка подключения к Redis: {e}")
        raise


async def get_redis() -> Redis:
    """Возвращает клиент Redis. Предполагает, что init_redis уже вызван."""
    if _redis_client is None:
        raise RuntimeError("Redis не инициализирован. Вызовите init_redis() в lifespan.")
    return _redis_client


async def close_redis():
    """Закрывает соединение с Redis."""
    global _redis_client
    if _redis_client:
        await _redis_client.close()
        _redis_client = None
        logger.info("🛑 Redis соединение закрыто")