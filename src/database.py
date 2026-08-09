import os
import json
import hashlib
import logging
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv
from pgvector.psycopg2 import register_vector

load_dotenv()
logger = logging.getLogger(__name__)

DB_CONFIG = {
    "host": os.environ["DB_HOST"],
    "port": int(os.environ["DB_PORT"]),
    "dbname": os.environ["DB_NAME"],
    "user": os.environ["DB_USER"],
    "password": os.environ["DB_PASSWORD"],
}

SEM_CACHE_THRESHOLD = 0.15

def get_db_connection():
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        register_vector(conn)
        return conn
    except KeyError as e:
        raise RuntimeError(f"Missing env: {e}")

def compute_review_hash(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        
        # 1. Сессии
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id BIGSERIAL PRIMARY KEY,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                file_name TEXT,
                total_rows INTEGER DEFAULT 0,
                processed_rows INTEGER DEFAULT 0,
                status TEXT DEFAULT 'processing'
            )
        """)
        
        # 2. Анализы (текст и hash, без UNIQUE)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS analyses (
                id BIGSERIAL PRIMARY KEY,
                session_id BIGINT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                review_text TEXT NOT NULL,
                review_hash TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        
        # 3. Нормализованные аспекты
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS review_aspects (
                id BIGSERIAL PRIMARY KEY,
                analysis_id BIGINT NOT NULL REFERENCES analyses(id) ON DELETE CASCADE,
                aspect_name TEXT NOT NULL,
                sentiment TEXT NOT NULL,
                weight REAL DEFAULT 0.5,
                praised_reasons JSONB DEFAULT '[]'::jsonb,
                criticized_reasons JSONB DEFAULT '[]'::jsonb,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        
        # 4. Семантический кэш
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS semantic_cache (
                review_hash TEXT PRIMARY KEY,
                embedding halfvec(768) NOT NULL,
                aspects JSONB NOT NULL,
                frequency INTEGER DEFAULT 1,
                last_accessed TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        
        # Индексы
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_analyses_session ON analyses(session_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_analyses_hash ON analyses(review_hash);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_review_aspects_analysis ON review_aspects(analysis_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_review_aspects_name ON review_aspects(aspect_name);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_review_aspects_sentiment ON review_aspects(sentiment);")
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_cache_embedding 
            ON semantic_cache USING hnsw (embedding halfvec_cosine_ops)
            WITH (m = 16, ef_construction = 200)
        """)
        
        conn.commit()
        logger.info("Нормализованная БД инициализирована")
    except Exception as e:
        conn.rollback()
        logger.error(f"Init DB error: {e}")
        raise
    finally:
        cursor.close()
        conn.close()

# ---------------------- СЕССИИ ----------------------
def create_session(file_name: str) -> int:
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO sessions (file_name, status) VALUES (%s, 'processing') RETURNING id", (file_name,))
        session_id = cursor.fetchone()[0]
        conn.commit()
        return session_id
    finally:
        cursor.close()
        conn.close()

def update_session_status(session_id: int, status: str, total_rows: int = None, processed_rows: int = None):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        updates = ["status = %s"]
        params = [status]
        if total_rows is not None:
            updates.append("total_rows = %s")
            params.append(total_rows)
        if processed_rows is not None:
            updates.append("processed_rows = %s")
            params.append(processed_rows)
        params.append(session_id)

        # Для перехода в 'completed' — добавляем условие, чтобы не менять уже завершённую сессию
        if status == 'completed':
            cursor.execute(
                f"UPDATE sessions SET {', '.join(updates)} WHERE id = %s AND status != 'completed'",
                params
            )
        else:
            cursor.execute(f"UPDATE sessions SET {', '.join(updates)} WHERE id = %s", params)

        conn.commit()
    finally:
        cursor.close()
        conn.close()

def get_session(session_id: int):
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cursor.execute("SELECT * FROM sessions WHERE id = %s", (session_id,))
        row = cursor.fetchone()
        if row is None:
            print(f"Сессия {session_id} не найдена в БД!")
        else:
            print(f"Сессия {session_id} существует")
        return dict(row) if row else None
    finally:
        cursor.close()
        conn.close()

def get_analyses_by_session(session_id: int) -> list[dict]:
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cursor.execute("SELECT id, review_text, created_at FROM analyses WHERE session_id = %s", (session_id,))
        rows = cursor.fetchall()
        result = []
        for row in rows:
            aid = row["id"]
            cursor.execute("""
                SELECT aspect_name, sentiment, weight, praised_reasons, criticized_reasons
                FROM review_aspects WHERE analysis_id = %s
            """, (aid,))
            aspects = cursor.fetchall()
            row_dict = dict(row)
            row_dict["aspects"] = [
                {
                    "name": a["aspect_name"],
                    "sentiment": a["sentiment"],
                    "weight": a["weight"],
                    "praised": a["praised_reasons"] if a["praised_reasons"] else [],
                    "criticized": a["criticized_reasons"] if a["criticized_reasons"] else [],
                }
                for a in aspects
            ]
            result.append(row_dict)
        return result
    finally:
        cursor.close()
        conn.close()

# ---------------------- АНАЛИЗЫ (СОХРАНЕНИЕ) ----------------------
def save_analysis(session_id: int, review_text: str, aspects: list[dict]) -> int:
    review_hash = compute_review_hash(review_text)
    logger.info(f"Saving analysis: session={session_id}, hash={review_hash[:8]}..., aspects={len(aspects)}")
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO analyses (session_id, review_text, review_hash)
            VALUES (%s, %s, %s)
            RETURNING id
        """, (session_id, review_text, review_hash))
        analysis_id = cursor.fetchone()[0]
        logger.info(f"New analysis created, id={analysis_id}")

        for a in aspects:
            cursor.execute("""
                INSERT INTO review_aspects (analysis_id, aspect_name, sentiment, weight, praised_reasons, criticized_reasons)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                analysis_id,
                a.get("name"),
                a.get("sentiment", "neutral"),
                a.get("weight", 0.5),
                json.dumps(a.get("praised", [])),
                json.dumps(a.get("criticized", []))
            ))
        conn.commit()
        logger.info(f"Successfully saved {len(aspects)} aspects for analysis {analysis_id}")
        return analysis_id
    except Exception as e:
        logger.error(f"Error in save_analysis: {e}", exc_info=True)
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()

# ---------------------- ЗАПРОСЫ ДЛЯ ГЛУБОКОГО АНАЛИЗА ----------------------
def get_deep_analysis_data(session_id: int, aspect_names: list[str]) -> dict:
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT 
                COUNT(DISTINCT ra.analysis_id) AS total_mentions,
                COALESCE(AVG(
                    CASE ra.sentiment 
                        WHEN 'positive' THEN 1 
                        WHEN 'negative' THEN -1 
                        ELSE 0 
                    END
                ), 0) AS avg_sentiment
            FROM review_aspects ra
            JOIN analyses a ON ra.analysis_id = a.id
            WHERE a.session_id = %s AND ra.aspect_name = ANY(%s)
        """, (session_id, aspect_names))
        row = cursor.fetchone()
        total = row[0] or 0
        avg_sentiment = row[1] or 0.0

        cursor.execute("""
            SELECT jsonb_array_elements_text(ra.praised_reasons) AS reason
            FROM review_aspects ra
            JOIN analyses a ON ra.analysis_id = a.id
            WHERE a.session_id = %s 
              AND ra.aspect_name = ANY(%s)
              AND ra.praised_reasons IS NOT NULL 
              AND jsonb_array_length(ra.praised_reasons) > 0
        """, (session_id, aspect_names))
        praised = [r[0] for r in cursor.fetchall() if r[0] and r[0].strip()]

        cursor.execute("""
            SELECT jsonb_array_elements_text(ra.criticized_reasons) AS reason
            FROM review_aspects ra
            JOIN analyses a ON ra.analysis_id = a.id
            WHERE a.session_id = %s 
              AND ra.aspect_name = ANY(%s)
              AND ra.criticized_reasons IS NOT NULL 
              AND jsonb_array_length(ra.criticized_reasons) > 0
        """, (session_id, aspect_names))
        criticized = [r[0] for r in cursor.fetchall() if r[0] and r[0].strip()]

        return {
            "total_mentions": total,
            "average_score": avg_sentiment,
            "praised": praised,
            "criticized": criticized
        }
    finally:
        cursor.close()
        conn.close()

def get_processed_count(session_id: int) -> int:
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT COUNT(*) FROM analyses WHERE session_id = %s", (session_id,))
        return cursor.fetchone()[0]
    finally:
        cursor.close()
        conn.close()

# ---------------------- ПАГИНАЦИЯ ----------------------
def get_aspect_stats_by_session(session_id: int) -> list[dict]:
    """Агрегирует аспекты по всей сессии (лёгкий запрос, без пагинации)."""
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cursor.execute("""
            SELECT 
                ra.aspect_name,
                COUNT(*) as total,
                SUM(CASE WHEN ra.sentiment = 'positive' THEN 1 ELSE 0 END) as positive_count,
                SUM(CASE WHEN ra.sentiment = 'negative' THEN 1 ELSE 0 END) as negative_count,
                SUM(CASE WHEN ra.sentiment = 'neutral' THEN 1 ELSE 0 END) as neutral_count
            FROM review_aspects ra
            JOIN analyses a ON ra.analysis_id = a.id
            WHERE a.session_id = %s
            GROUP BY ra.aspect_name
        """, (session_id,))
        rows = cursor.fetchall()
        result = []
        for row in rows:
            total = row["total"]
            if total == 0:
                continue
            sentiment_score = round((row["positive_count"] - row["negative_count"]) / total, 2)
            avg_score = round((sentiment_score + 1) * 2.5, 1)
            result.append({
                "name": row["aspect_name"],
                "total": total,
                "positivity": round(row["positive_count"] / total * 100, 1),
                "negativity": round(row["negative_count"] / total * 100, 1),
                "positive_count": row["positive_count"],
                "neutral_count": row["neutral_count"],
                "negative_count": row["negative_count"],
                "sentiment_score": sentiment_score,
                "average_score": avg_score
            })
        result.sort(key=lambda x: x["total"], reverse=True)
        return result
    finally:
        cursor.close()
        conn.close()


def get_reviews_by_session_paginated(session_id: int, limit: int, offset: int) -> tuple[list[dict], int]:
    """Возвращает страницу отзывов + общее количество для сессии."""
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cursor.execute("SELECT COUNT(*) as total_count FROM analyses WHERE session_id = %s", (session_id,))
        total_row = cursor.fetchone()
        total = total_row["total_count"] if total_row else 0

        cursor.execute("""
            SELECT id, review_text FROM analyses 
            WHERE session_id = %s 
            ORDER BY id 
            LIMIT %s OFFSET %s
        """, (session_id, limit, offset))
        rows = cursor.fetchall()
        if not rows:
            return [], total

        ids = [r["id"] for r in rows]
        cursor.execute("""
            SELECT analysis_id, aspect_name, sentiment 
            FROM review_aspects 
            WHERE analysis_id = ANY(%s)
        """, (ids,))
        asp_rows = cursor.fetchall()
        asp_map = {}
        for r in asp_rows:
            asp_map.setdefault(r["analysis_id"], []).append(f"{r['aspect_name']}({r['sentiment']})")

        reviews_list = []
        for idx, row in enumerate(rows, 1):
            text = row["review_text"]
            reviews_list.append({
                "id": offset + idx,  #сквозная нумерация вместо 1..N на каждой странице
                "text": text[:200] + "..." if len(text) > 200 else text,
                "topics": ", ".join(asp_map.get(row["id"], [])),
                "full_text": text
            })
        return reviews_list, total
    finally:
        cursor.close()
        conn.close()

# ---------------------- КЭШ ----------------------
def get_cached_result(review_text: str, embedding: list[float], threshold: float = SEM_CACHE_THRESHOLD) -> dict | None:
    review_hash = compute_review_hash(review_text)
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT aspects FROM semantic_cache WHERE review_hash = %s", (review_hash,))
        row = cursor.fetchone()
        if row:
            cursor.execute("UPDATE semantic_cache SET frequency = frequency + 1, last_accessed = NOW() WHERE review_hash = %s", (review_hash,))
            conn.commit()
            return row[0]
        cursor.execute("""
            SELECT review_hash, aspects, (embedding <=> %s::halfvec) AS distance
            FROM semantic_cache
            ORDER BY distance
            LIMIT 1
        """, (embedding,))
        row = cursor.fetchone()
        if row and row[2] is not None and row[2] < threshold:
            cursor.execute("UPDATE semantic_cache SET frequency = frequency + 1, last_accessed = NOW() WHERE review_hash = %s", (row[0],))
            conn.commit()
            return row[1]
        return None
    finally:
        cursor.close()
        conn.close()

def save_cached_result(review_text: str, embedding: list[float], aspects: dict):
    review_hash = compute_review_hash(review_text)
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO semantic_cache (review_hash, embedding, aspects)
            VALUES (%s, %s::halfvec, %s)
            ON CONFLICT (review_hash) DO UPDATE
            SET aspects = EXCLUDED.aspects, embedding = EXCLUDED.embedding,
                frequency = semantic_cache.frequency + 1, last_accessed = NOW()
        """, (review_hash, embedding, json.dumps(aspects, ensure_ascii=False)))
        conn.commit()
    finally:
        cursor.close()
        conn.close()

def get_cache_stats() -> dict:
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cursor.execute("SELECT COUNT(*) as total_entries, SUM(frequency) as total_hits, AVG(frequency) as avg_hits, MAX(last_accessed) as last_use FROM semantic_cache")
        return dict(cursor.fetchone())
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    init_db()