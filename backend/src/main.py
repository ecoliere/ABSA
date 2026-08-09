import os
import sys
import asyncio
import logging
import hmac
import hashlib
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import aiohttp

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.database import (
    get_deep_analysis_data, init_db, create_session, save_analysis, update_session_status,
    get_session, get_processed_count,
    get_aspect_stats_by_session, get_reviews_by_session_paginated
)
from src.task_queue import enqueue_reviews_batch, get_stream_length, init_stream
from src.gigachat_service import gigachat
from src.clustering import aggregate_deep_analysis
from src.redis_client import init_redis, close_redis
from src.worker import start_workers, stop_workers
from src.embeddings import warmup_model
from src.schemas import (
    AnalyzeSingleResponse, TopicResponse, UploadFileResponse, ResultsResponse,
    AspectShortResponse, ReviewShortResponse, DeepAnalysisResponse,
    QueueStatusResponse, DLQResponse, ProcessingStatusResponse
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

MAX_CONCURRENT = 2
WORKER_COUNT = 2
llm_semaphore = asyncio.Semaphore(MAX_CONCURRENT)

# ---------- Защита доступа по URL-key ---------------------------
SECRET_KEY = os.environ["SECRET_KEY"]

def _generate_token(session_id: int) -> str:
    return hmac.new(SECRET_KEY.encode(), str(session_id).encode(), hashlib.sha256).hexdigest()[:16]

def _verify_token(session_id: int, token: str) -> bool:
    expected = _generate_token(session_id)
    return hmac.compare_digest(expected, token)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    await init_redis()
    await init_stream()
    await asyncio.to_thread(warmup_model)
    workers = await start_workers(WORKER_COUNT, MAX_CONCURRENT)
    logger.info(f"База данных готова, Redis готов, {WORKER_COUNT} воркеров запущены")
    yield
    await stop_workers(workers)
    await close_redis()
    logger.info("Приложение остановлено")

app = FastAPI(title="Анализатор отзывов", lifespan=lifespan)
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"message": "Анализатор отзывов работает", "status": "ok"}

@app.get("/health")
async def health():
    return {"status": "alive"}

@app.get("/queue/status", response_model=QueueStatusResponse)
async def queue_status():
    try:
        length = await get_stream_length()
        return QueueStatusResponse(
            queue_length=length,
            workers=WORKER_COUNT,
            max_concurrent=MAX_CONCURRENT
        )
    except Exception as e:
        logger.exception("Ошибка в /queue/status")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/queue/dlq", response_model=DLQResponse)
async def get_dlq():
    from src.task_queue import get_dlq_size, pop_from_dlq
    size = await get_dlq_size()
    samples = []
    for _ in range(min(10, size)):
        task = await pop_from_dlq()
        if task:
            samples.append(task)
    return DLQResponse(size=size, samples=samples)

@app.post("/analyze-single", response_model=AnalyzeSingleResponse)
async def analyze_single(request: Request):
    try:
        data = await request.json()
        text = data.get("text", "")
        if not text or not text.strip():
            raise HTTPException(status_code=400, detail="Текст отзыва не может быть пустым")
        async with aiohttp.ClientSession() as session:
            result = await gigachat.quick_analyze(text, session)

        aspects = result.get("topics", [])
        session_id = await asyncio.to_thread(create_session, "manual_input")
        token = _generate_token(session_id)

        if result.get("valid"):
            await asyncio.to_thread(save_analysis, session_id, text, aspects)
            await asyncio.to_thread(update_session_status, session_id, "completed", 1, 1)
            return AnalyzeSingleResponse(
                session_id=session_id,
                access_token=token,
                text=text,
                topics=[TopicResponse(**t) for t in aspects]
            )
        else:
            await asyncio.to_thread(save_analysis, session_id, text, [])
            await asyncio.to_thread(update_session_status, session_id, "failed", 1, 0)
            return AnalyzeSingleResponse(
                session_id=session_id,
                access_token=token,
                text=text,
                topics=[]
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Ошибка в /analyze-single")
        raise HTTPException(status_code=500, detail=str(e))

MAX_FILE_SIZE = 10 * 1024 * 1024

@app.post("/upload", response_model=UploadFileResponse)
async def upload_file(file: UploadFile = File(...)):
    try:
        if not file.filename.lower().endswith('.csv'):
            raise HTTPException(status_code=400, detail="Допустимы только CSV файлы")
        content = await file.read(MAX_FILE_SIZE + 1)
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(status_code=413, detail=f"Файл слишком большой (макс. {MAX_FILE_SIZE // (1024*1024)} MB)")
        upload_dir = Path("uploads")
        upload_dir.mkdir(exist_ok=True)
        file_path = upload_dir / file.filename
        file_path.write_bytes(content)

        try:
            import pandas as pd
            try:
                df = pd.read_csv(file_path, encoding='utf-8')
            except UnicodeDecodeError:
                df = pd.read_csv(file_path, encoding='cp1251')
            text_column = None
            for col in ['review', 'text', 'отзыв', 'review_text', 'Review', 'Text']:
                if col in df.columns:
                    text_column = col
                    break
            if not text_column:
                raise HTTPException(status_code=400, detail="CSV должен содержать колонку 'review' или 'text'")
            reviews = [str(r).strip() for r in df[text_column].dropna().tolist() if str(r).strip()]
            if not reviews:
                raise HTTPException(status_code=400, detail="Файл не содержит текстов отзывов")
            session_id = await asyncio.to_thread(create_session, file.filename)
            token = _generate_token(session_id)
            await asyncio.to_thread(update_session_status, session_id, 'processing', len(reviews), 0)
            await enqueue_reviews_batch(session_id, reviews)
            return UploadFileResponse(
                session_id=session_id,
                access_token=token,
                file_name=file.filename,
                message=f"Файл загружен, {len(reviews)} отзывов добавлено в очередь на обработку"
            )
        finally:
            file_path.unlink(missing_ok=True)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Ошибка в /upload")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/results/{session_id}/data", response_model=ResultsResponse)
async def get_results_data(session_id: int, token: str, skip: int = 0, limit: int = 50):
    if not _verify_token(session_id, token):
        raise HTTPException(status_code=403, detail="Недействительный ключ доступа")
    limit = min(limit, 500)
    try:
        def fetch_data():
            session = get_session(session_id)
            if not session:
                return None, None, None, 0
            aspects_list = get_aspect_stats_by_session(session_id)
            reviews_list, total = get_reviews_by_session_paginated(session_id, limit, skip)
            return aspects_list, reviews_list, session, total

        aspects_list, reviews_list, session_info, total = await asyncio.to_thread(fetch_data)
        if aspects_list is None:
            raise HTTPException(status_code=404, detail="Сессия не найдена")
        return ResultsResponse(
            session_id=session_id,
            total_reviews=total,
            status=session_info.get("status", "unknown") if session_info else "unknown",
            skip=skip,
            limit=limit,
            aspects=[AspectShortResponse(**a) for a in aspects_list],
            reviews=[ReviewShortResponse(**r) for r in reviews_list]
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Ошибка в /results/data")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/processing/{session_id}/status", response_model=ProcessingStatusResponse)
async def get_processing_status(session_id: int, token: str):
    if not _verify_token(session_id, token):
        raise HTTPException(status_code=403, detail="Недействительный ключ доступа")
    try:
        def fetch_status():
            session = get_session(session_id)
            if not session:
                raise HTTPException(status_code=404, detail="Сессия не найдена")
            processed = get_processed_count(session_id)
            return session, processed
        session_info, processed = await asyncio.to_thread(fetch_status)
        return ProcessingStatusResponse(
            session_id=session_id,
            status=session_info.get("status", "unknown"),
            total_reviews=session_info.get("total_rows", 0),
            processed_reviews=processed
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Ошибка в /processing/status")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/deep/{session_id}/{aspect}", response_model=DeepAnalysisResponse)
async def deep_analysis(session_id: int, aspect: str, token: str, aspects: str = None):
    if not _verify_token(session_id, token):
        raise HTTPException(status_code=403, detail="Недействительный ключ доступа")
    from urllib.parse import unquote
    if aspects:
        target_aspects = [a.strip().lower() for a in unquote(aspects).split(',')]
    else:
        target_aspects = [aspect.lower()]
    data = await asyncio.to_thread(get_deep_analysis_data, session_id, target_aspects)
    if not data["praised"] and not data["criticized"]:
        return DeepAnalysisResponse(
            aspect=aspect,
            total_mentions=data["total_mentions"],
            total_reasons=0,
            average_score=0.0,
            praised_groups=[],
            criticized_groups=[],
            recommendation="Нет данных по данному аспекту."
        )
    aggregated = await asyncio.to_thread(aggregate_deep_analysis, data["praised"], data["criticized"])
    total_reasons = sum(g["total_frequency"] for g in aggregated["praised_groups"]) + \
                    sum(g["total_frequency"] for g in aggregated["criticized_groups"])
    avg_score = round((float(data["average_score"]) + 1) * 2.5, 1)
    recommendation = "Продолжайте в том же духе!"
    if aggregated["criticized_groups"]:
        top_group = aggregated["criticized_groups"][0]
        recommendation = f"Основная проблема — {top_group['name']}."
    return DeepAnalysisResponse(
        aspect=aspect,
        total_mentions=data["total_mentions"],
        total_reasons=total_reasons,
        average_score=avg_score,
        praised_groups=aggregated["praised_groups"],
        criticized_groups=aggregated["criticized_groups"],
        recommendation=recommendation
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.main:app", host="0.0.0.0", port=8081, reload=True)