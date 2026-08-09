# src/task_queue.py
import os
import json
import logging
from src.redis_client import get_redis

logger = logging.getLogger(__name__)

ENV = os.getenv("ENV", "dev")
STREAM_NAME = f"task_stream:{ENV}"
GROUP_NAME = "workers"
DLQ_NAME = f"task_dlq:{ENV}"
MAX_ATTEMPTS = int(os.getenv("MAX_TASK_ATTEMPTS", "3"))
PENDING_IDLE_MS = int(os.getenv("PENDING_IDLE_MS", "60000"))
CLAIM_BATCH_SIZE = 100
CLAIM_INTERVAL = int(os.getenv("CLAIM_INTERVAL", "30"))

ATTEMPTS_KEY = f"task_attempts:{ENV}"

async def init_stream() -> None:
    redis = await get_redis()
    try:
        await redis.xgroup_create(STREAM_NAME, GROUP_NAME, id='0', mkstream=True)
    except Exception as e:
        if 'BUSYGROUP' not in str(e):
            logger.warning(f"Init stream: {e}")

async def enqueue_reviews_batch(session_id: int, reviews: list[str]) -> int:
    if not reviews:
        return 0
    redis = await get_redis()
    pipe = redis.pipeline()
    for text in reviews:
        task = json.dumps({
            "session_id": session_id,
            "review_text": text,
        })
        pipe.xadd(STREAM_NAME, {"task": task})
    await pipe.execute()
    return len(reviews)

async def dequeue_task(consumer_name: str, timeout: int = 5) -> dict | None:
    redis = await get_redis()
    try:
        result = await redis.xreadgroup(
            GROUP_NAME, consumer_name,
            {STREAM_NAME: '>'},
            count=1,
            block=timeout * 1000
        )
        if result:
            stream_name, messages = result[0]
            msg_id, data = messages[0]
            raw_task = data.get(b'task', data.get('task'))
            if isinstance(raw_task, bytes):
                raw_task = raw_task.decode()
            task = json.loads(raw_task)
            return {"task": task, "msg_id": msg_id}
        return None
    except TimeoutError:
        # Таймаут – нет сообщений
        return None
    except Exception as e:
        logger.error(f"Ошибка dequeue_task: {e}")
        raise

async def ack_task(msg_id: str) -> None:
    redis = await get_redis()
    await redis.xack(STREAM_NAME, GROUP_NAME, msg_id)
    await redis.hdel(ATTEMPTS_KEY, msg_id)

async def _get_attempts(msg_id: str) -> int:
    redis = await get_redis()
    val = await redis.hget(ATTEMPTS_KEY, msg_id)
    return int(val) if val else 0

async def _increment_attempts(msg_id: str) -> int:
    redis = await get_redis()
    return await redis.hincrby(ATTEMPTS_KEY, msg_id, 1)

async def _delete_attempts(msg_id: str) -> None:
    redis = await get_redis()
    await redis.hdel(ATTEMPTS_KEY, msg_id)

async def push_to_dlq(task: dict) -> None:
    redis = await get_redis()
    await redis.rpush(DLQ_NAME, json.dumps(task))

async def claim_pending_tasks(consumer_name: str) -> None:
    redis = await get_redis()
    pending = await redis.xpending_range(STREAM_NAME, GROUP_NAME, '-', '+', CLAIM_BATCH_SIZE)
    for entry in pending:
        msg_id = entry['message_id']
        if not msg_id:
            continue
        if entry['time_since_delivered'] >= PENDING_IDLE_MS:
            try:
                # Исправлено: передаём список [msg_id]
                claimed = await redis.xclaim(STREAM_NAME, GROUP_NAME, consumer_name,
                                             PENDING_IDLE_MS, [msg_id])
            except Exception as e:
                logger.error(f"XCLAIM error for {msg_id}: {e}")
                continue
            if not claimed:
                continue
            attempts = await _increment_attempts(msg_id)
            if attempts >= MAX_ATTEMPTS:
                raw = await redis.xrange(STREAM_NAME, msg_id, msg_id)
                if raw:
                    task_data = raw[0][1].get(b'task', raw[0][1].get('task'))
                    if isinstance(task_data, bytes):
                        task_data = task_data.decode()
                    task = json.loads(task_data)
                    await push_to_dlq(task)
                await redis.xack(STREAM_NAME, GROUP_NAME, msg_id)
                await _delete_attempts(msg_id)
                logger.warning(f"Задача {msg_id} отправлена в DLQ после {attempts} попыток")
            else:
                logger.info(f"Задача {msg_id} переподвешена, попытка {attempts}")

# ------------------- Мониторинг -------------------
async def get_stream_length() -> int:
    redis = await get_redis()
    info = await redis.xinfo_stream(STREAM_NAME)
    return info.get('length', 0)

async def get_pending_count() -> int:
    redis = await get_redis()
    info = await redis.xpending(STREAM_NAME, GROUP_NAME)
    return info.get('pending', 0)

async def get_dlq_size() -> int:
    redis = await get_redis()
    return await redis.llen(DLQ_NAME)

async def pop_from_dlq() -> dict | None:
    redis = await get_redis()
    task_json = await redis.lpop(DLQ_NAME)
    if task_json:
        return json.loads(task_json)
    return None