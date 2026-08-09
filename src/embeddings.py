# src/embeddings.py
import re
from sentence_transformers import SentenceTransformer
from functools import lru_cache

_model = None

def clean_text(text: str) -> str:
    """
    Минимальная очистка текста для LaBSE.
    - Не меняем регистр (модель cased)
    - Не удаляем стоп-слова, не лемматизируем
    - Убираем только откровенный мусор: HTML, URL, непечатные символы
    """
    # Удаляем HTML-теги
    text = re.sub(r'<[^>]+>', ' ', text)
    # Удаляем URL
    text = re.sub(r'https?://\S+|www\.\S+', '', text)
    # Удаляем непечатные символы (оставляем буквы, цифры, знаки препинания, пробелы)
    text = re.sub(r'[^\w\s\.,!?;:()-]', '', text)
    # Сжимаем множественные пробелы
    text = re.sub(r'\s+', ' ', text).strip()
    return text

@lru_cache(maxsize=10000)
def get_embedding(text: str) -> list[float]:
    """
    Возвращает эмбеддинг для короткого текста (причины).
    Используется модель sentence-transformers/LaBSE.
    """
    global _model
    if _model is None:
        _model = SentenceTransformer('cointegrated/LaBSE-en-ru')
    
    if not text or not text.strip():
        return [0.0] * 768
    
    cleaned = clean_text(text)
    if not cleaned:
        return [0.0] * 768
        
    embedding = _model.encode(cleaned, normalize_embeddings=True)
    return embedding.tolist()

def warmup_model():
    """
    Синхронная загрузка модели в память.
    Вызывается один раз при старте приложения.
    """
    global _model
    if _model is None:
        _model = SentenceTransformer('cointegrated/LaBSE-en-ru')
    # Опционально: прогнать пустую строку или короткий тест, чтобы инициализировать внутренние состояния
    _model.encode("test", normalize_embeddings=True)