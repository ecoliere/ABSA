# src/worker.py
import asyncio
import time
import logging
import aiohttp
import redis.exceptions
from src.task_queue import (
    init_stream, dequeue_task, ack_task, claim_pending_tasks,
    CLAIM_INTERVAL
)
from src.gigachat_service import gigachat
from src.database import (
    save_analysis, get_processed_count, update_session_status, get_session
)
from src.redis_client import init_redis

logger = logging.getLogger(__name__)

_shutdown_requested = False
_llm_semaphore = None

async def _process_single_task(task: dict, session: aiohttp.ClientSession) -> tuple[bool, dict]:
    for attempt in range(3):
        try:
            result = await gigachat.quick_analyze(task["review_text"], session)
            if result.get("valid", True):
                return True, result
            return False, result
        except Exception as e:
            logger.warning(f"Сетевая ошибка (попытка {attempt+1}/3): {e}")
            if attempt < 2:
                await asyncio.sleep(2 ** attempt)
            else:
                return False, {"topics": [], "valid": False}
    return False, {"topics": [], "valid": False}

async def queue_worker(worker_id: int):
    consumer_name = f"worker_{worker_id}"
    await init_stream()
    async with aiohttp.ClientSession() as session:
        last_claim = time.time()
        while not _shutdown_requested:
            try:
                msg = await dequeue_task(consumer_name, timeout=5)
                if msg:
                    task = msg["task"]
                    async with _llm_semaphore:
                        success, result = await _process_single_task(task, session)
                    if success:
                        aspects = result.get("topics", [])
                        logger.info(f"Worker {worker_id}: saving analysis for session {task['session_id']}")
                        analysis_id = await asyncio.to_thread(save_analysis, task["session_id"], task["review_text"], aspects)
                        logger.info(f"Worker {worker_id}: analysis saved, id={analysis_id}")
                        
                        processed = await asyncio.to_thread(get_processed_count, task["session_id"])
                        await asyncio.to_thread(update_session_status, task["session_id"], "processing", processed_rows=processed)
                        logger.info(f"Worker {worker_id}: processed rows now {processed}")
                        
                        session_info = await asyncio.to_thread(get_session, task["session_id"])
                        if session_info and session_info.get("total_rows", 0) == processed:
                            await asyncio.to_thread(update_session_status, task["session_id"], "completed")
                        await ack_task(msg["msg_id"])
                        total = session_info.get("total_rows", "?") if session_info else "?"
                        logger.info(f"✅ Задача обработана: сессия {task['session_id']}, {processed}/{total}")
                    else:
                        logger.warning(f"⚠️ Неудачная обработка задачи, будет повторена")
                if time.time() - last_claim > CLAIM_INTERVAL:
                    await claim_pending_tasks(consumer_name)
                    last_claim = time.time()
            except asyncio.CancelledError:
                break
            except (redis.exceptions.TimeoutError, redis.exceptions.ConnectionError, OSError) as e:
                logger.error(f"Redis ошибка в воркере {worker_id}: {e}. Переподключаемся...")
                try:
                    await init_redis()
                except Exception as reconnect_error:
                    logger.error(f"Не удалось переподключить Redis: {reconnect_error}")
                await asyncio.sleep(2)
                continue
            except Exception as e:
                logger.error(f"Ошибка в воркере {worker_id}: {e}", exc_info=True)
                await asyncio.sleep(1)

async def start_workers(count: int, max_concurrent: int):
    global _llm_semaphore
    _llm_semaphore = asyncio.Semaphore(max_concurrent)
    workers = [asyncio.create_task(queue_worker(i)) for i in range(count)]
    return workers

async def stop_workers(workers: list):
    global _shutdown_requested
    _shutdown_requested = True
    done, pending = await asyncio.wait(workers, timeout=30, return_when=asyncio.ALL_COMPLETED)
    for p in pending:
        p.cancel()
    await asyncio.gather(*pending, return_exceptions=True)
    logger.info("Все воркеры остановлены")