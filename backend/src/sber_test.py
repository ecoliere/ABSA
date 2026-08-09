import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

GIGACHAT_AUTH_KEY = os.getenv("GIGACHAT_AUTH_KEY")


def get_access_token() -> str:
    url = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
    
    payload = {'scope': 'GIGACHAT_API_PERS'}
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Accept': 'application/json',
        'RqUID': '019dd120-8522-7d5c-95a1-8c270abe8813',
        'Authorization': f'Basic {GIGACHAT_AUTH_KEY}'
    }
    
    response = requests.post(url, headers=headers, data=payload, verify=False)
    response.raise_for_status()
    
    return response.json()["access_token"]


def quick_analyze(text: str) -> dict:
    access_token = get_access_token()
    
    prompt = f"""
Ты — эксперт по анализу отзывов.
Проанализируй отзыв и верни JSON ровно в таком формате:
{{"topics": [{{"name": "тема", "sentiment": "positive/negative/neutral", "weight": 0.0-1.0}}]}}
Отзыв: "{text}"
"""
    
    url = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    body = {
        "model": "GigaChat-2",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2
    }
    
    response = requests.post(url, headers=headers, json=body, verify=False)
    
    # Добавь эти три строки для диагностики
    print("Статус:", response.status_code)
    print("Ответ:", response.text)
    
    content = response.json()["choices"][0]["message"]["content"]
    return json.loads(content)


if __name__ == "__main__":
    test_review = "Товар пришёл быстро, курьер был вежливый. Но упаковка была помята, цена приятная."
    result = quick_analyze(test_review)
    print(json.dumps(result, ensure_ascii=False, indent=2))