# src/gigachat_service.py
import os
import time
import json
import re
import asyncio
import logging
import aiohttp
from typing import Optional
from dotenv import load_dotenv
from src.database import get_cached_result, save_cached_result
from src.embeddings import get_embedding

load_dotenv()
logger = logging.getLogger(__name__)

AUTH_KEY = os.getenv("GIGACHAT_AUTH_KEY")
RQ_UID = os.getenv("GIGACHAT_RQUID")
TOKEN_URL = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
API_URL = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"


class GigaChatService:
    def __init__(self):
        self._access_token: Optional[str] = None
        self._token_expires_at: float = 0
        self._last_request_time: float = 0
        self._rate_limit_lock = asyncio.Lock()
        self._token_lock = asyncio.Lock()
        self.min_interval = 1.5
        self.max_retries = 3
        self.retry_base_delay = 2.0

    async def _get_token(self, session: aiohttp.ClientSession) -> str:
        if self._access_token and time.time() < self._token_expires_at - 60:
            return self._access_token

        async with self._token_lock:
            if self._access_token and time.time() < self._token_expires_at - 60:
                return self._access_token

            headers = {
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
                "RqUID": RQ_UID,
                "Authorization": f"Basic {AUTH_KEY}"
            }
            async with session.post(
                TOKEN_URL,
                data={"scope": "GIGACHAT_API_PERS"},
                headers=headers,
                ssl=False
            ) as resp:
                resp.raise_for_status()
                data = await resp.json()
                self._access_token = data["access_token"]
                self._token_expires_at = time.time() + data.get("expires_in", 1800)
                return self._access_token

    async def _wait_rate_limit(self):
        async with self._rate_limit_lock:
            now = time.time()
            wait = max(0.0, self.min_interval - (now - self._last_request_time))
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_request_time = time.time()

    @staticmethod
    def _normalize_sentiment(s: str) -> str:
        s = s.lower().strip()
        if "позитив" in s or "positive" in s:
            return "positive"
        if "негатив" in s or "negative" in s:
            return "negative"
        return "neutral"

    @staticmethod
    def _extract_json(text: str) -> dict:
        text = text.strip()
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            try:
                res = json.loads(match.group())
                if "topics" in res:
                    for t in res["topics"]:
                        if "sentiment" in t:
                            t["sentiment"] = GigaChatService._normalize_sentiment(t["sentiment"])
                        t.setdefault("praised", [])
                        t.setdefault("criticized", [])
                return res
            except json.JSONDecodeError:
                pass
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        try:
            res = json.loads(text.strip())
            if "topics" in res:
                for t in res["topics"]:
                    if "sentiment" in t:
                        t["sentiment"] = GigaChatService._normalize_sentiment(t["sentiment"])
                    t.setdefault("praised", [])
                    t.setdefault("criticized", [])
            return res
        except json.JSONDecodeError:
            logger.warning(f"Не удалось распарсить JSON: {text[:200]}")
            return {"topics": [], "error": "parse_failed"}

    @staticmethod
    def _build_quick_prompt(text: str) -> str:        
        return f"""
Ты — эксперт по анализу отзывов. Проанализируй отзыв и верни JSON строго в формате:
{{
  "topics": [
    {{
      "name": "название темы",
      "sentiment": "positive/negative/neutral",
      "weight": 0.0-1.0,
      "praised": ["конкретная причина1", "причина2"],
      "criticized": ["конкретная причина1", "причина2"]
    }}
  ]
}}

ПРАВИЛА:
1. name — одна конкретная тема (1–2 слова). постарайся дать название как можно более коротким.
   • Категорически запрещено перечислять разные сущности в одном аспекте: «цена и доставка», «сервис и поддержка» — это ошибка. Для каждой сущности создавай отдельный аспект.
   • Объединяй только точные синонимы или разные формулировки одной и той же темы: «быстрая доставка», «скорость доставки», «время доставки» → «доставка»; «вежливый персонал», «приветливые сотрудники» → «персонал».
2. sentiment — оценка автора к этой теме ("positive", "negative" или "neutral").
3. weight — значимость темы в отзыве (число от 0.0 до 1.0; 0.0=незначимо, 1.0=главная тема).
4. praised — список конкретных причин положительной оценки (формулировки из отзыва, 3–8 слов). Если положительных причин нет, возвращай [].
5. criticized — список конкретных причин отрицательной оценки (формулировки из отзыва, 3–8 слов). Если отрицательных причин нет, возвращай [].
6. Не придумывай темы, которых нет в отзыве. Каждый аспект должен относиться строго к одной сущности или действию, упомянутому в тексте.
7. Как аспекты выделяй только то, что действительно важно в контексте конкретного отзыва. Чтобы проверить себя сначала выдели для себя, на что дается отзыв, а затем выделяй аспекты.
8. Как причины выделяй только действительно значимые для аспекта фразы. 

ПРИМЕРЫ:

[IT/Софт]
Отзыв: "Приложение тормозит, постоянно вылетает, интерфейс красивый"
Ответ: {{
  "topics": [
    {{"name": "производительность", "sentiment": "negative", "weight": 0.9, "praised": [], "criticized": ["приложение тормозит", "вылетает"]}},
    {{"name": "дизайн", "sentiment": "positive", "weight": 0.4, "praised": ["красивый интерфейс"], "criticized": []}}
  ]
}}

[Клининг / Услуги]
Отзыв: "Девушка на телефоне нахамила, пришлось трижды уточнять цену. Уборку делали плохо, пыль осталась. Зато ковры почистили отлично."
Ответ: {{
  "topics": [
    {{"name": "обслуживание", "sentiment": "negative", "weight": 0.6, "praised": [], "criticized": ["нахамила по телефону", "трижды уточнял цену"]}},
    {{"name": "уборка", "sentiment": "negative", "weight": 0.8, "praised": [], "criticized": ["пыль осталась", "убрали плохо"]}},
    {{"name": "чистка", "sentiment": "positive", "weight": 0.5, "praised": ["ковры почистили отлично"], "criticized": []}}
  ]
}}

[Доставка/логистика]
Отзыв: "Курьер приехал через 3 часа, но вежливый и посылку не помяли"
Ответ: {{
  "topics": [
    {{"name": "доставка", "sentiment": "negative", "weight": 0.7, "praised": [], "criticized": ["опоздание на 3 часа"]}},
    {{"name": "сервис", "sentiment": "positive", "weight": 0.5, "praised": ["вежливый курьер", "целая посылка"], "criticized": []}}
  ]
}}

[Гостиничный бизнес]
Отзыв: "Номер чистый, просторный, но шумно с улицы"
Ответ: {{
  "topics": [
    {{"name": "комфорт номера", "sentiment": "positive", "weight": 0.6, "praised": ["чистый номер", "просторный"], "criticized": []}},
    {{"name": "шум", "sentiment": "negative", "weight": 0.4, "praised": [], "criticized": ["шумно с улицы"]}}
  ]
}}

[Ресторан / доставка еды]
Отзыв: "Пицца вкусная, но дорогая. Доставка опоздала на час."
Ответ: {{
  "topics": [
    {{"name": "качество еды", "sentiment": "positive", "weight": 0.6, "praised": ["вкусная пицца"], "criticized": []}},
    {{"name": "цена", "sentiment": "negative", "weight": 0.5, "praised": [], "criticized": ["дорогая"]}},
    {{"name": "доставка", "sentiment": "negative", "weight": 0.7, "praised": [], "criticized": ["опоздала на час"]}}
  ]
}}

ОТЗЫВ ДЛЯ АНАЛИЗА:
"{text}"
"""

    async def quick_analyze(self, text: str, session: aiohttp.ClientSession) -> dict:
        if not text or len(text.strip().split()) < 3:
            return {"topics": [], "valid": True}

        #1 проверка кэша
        emb = None
        try:
            emb = await asyncio.to_thread(get_embedding, text)
            cached = await asyncio.to_thread(get_cached_result, text, emb, 0.05)
            if cached:
                logger.info(f"Кэш: {text[:50]}...")
                cached["valid"] = True
                return cached
        except Exception as e:
            logger.warning(f"Ошибка кэша: {e}")

        #2 запрос к LLM с retry-циклом
        prompt = self._build_quick_prompt(text)
        result = None

        for attempt in range(self.max_retries):
            try:
                await self._wait_rate_limit()
                token = await self._get_token(session)

                async with session.post(
                    API_URL,
                    json={
                        "model": "GigaChat-2",
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.2
                    },
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json"
                    },
                    ssl=False
                ) as resp:
                    if resp.status == 429:
                        retry_after = float(
                            resp.headers.get("Retry-After", self.retry_base_delay * (2 ** attempt))
                        )
                        logger.warning(
                            f"429 Rate limit, attempt {attempt + 1}/{self.max_retries}, "
                            f"retry after {retry_after:.1f}s"
                        )
                        if attempt < self.max_retries - 1:
                            await asyncio.sleep(retry_after)
                            continue
                        raise Exception("Rate limit hit")

                    resp.raise_for_status()
                    data = await resp.json()
                    result = self._extract_json(data["choices"][0]["message"]["content"])
                    break

            except Exception as e:
                if attempt == self.max_retries - 1:
                    logger.error(f"Ошибка запроса к LLM после {self.max_retries} попыток: {e}")
                    return {"topics": [], "valid": False}
                wait = self.retry_base_delay * (2 ** attempt)
                logger.warning(
                    f"LLM request failed (attempt {attempt + 1}), retry in {wait:.1f}s: {e}"
                )
                await asyncio.sleep(wait)

        #3 проверка валидности результата
        if not result or not result.get("topics") or result.get("error") == "parse_failed":
            logger.warning(f"Пустой ответ или ошибка парсинга для: {text[:100]}...")
            result = {"topics": [], "valid": False}
        else:
            result["valid"] = True

        #4 сохранение в кэш (только валидные результаты)
        if emb is not None and result.get("valid"):
            try:
                await asyncio.to_thread(save_cached_result, text, emb, result)
                logger.info(f"Сохранено в кэш: {text[:50]}...")
            except Exception as e:
                logger.warning(f"Ошибка сохранения кэша: {e}")

        return result

gigachat = GigaChatService()