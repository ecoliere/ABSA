================================================================================
        ИНСТРУКЦИЯ ПО ЗАПУСКУ "АНАЛИЗАТОР ОТЗЫВОВ"
================================================================================

1. СИСТЕМНЫЕ ТРЕБОВАНИЯ
================================================================================

Минимум:                    Рекомендуется:
------------------------    ------------------------
Windows 10 / Linux / macOS  Windows 11 / Ubuntu 22.04
RAM 4 GB                    RAM 8 GB
Диск 10 GB свободно          Диск 20 GB SSD
Docker Desktop 4.20+         Последняя версия
Интернет 5 Мбит/с            Интернет 20 Мбит/с

ВНИМАНИЕ: Первый запуск качает ~2 GB (образы + модель LaBSE)


2. УСТАНОВКА DOCKER
================================================================================

--- Windows ---
1. Скачай Docker Desktop: https://www.docker.com/products/docker-desktop/
2. Установи и перезагрузи компьютер
3. В настройках включи WSL 2 (если спросит)
4. Проверь в PowerShell:
   docker --version
   docker compose version

--- Linux (Ubuntu/Debian) ---
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
newgrp docker
docker --version
docker compose version

--- macOS ---
1. Скачай Docker Desktop для Mac
2. Установи и запусти
3. Проверь:
   docker --version
   docker compose version


3. РАСПАКОВКА ПРОЕКТА
================================================================================

Скопируй папку diploma/ в удобное место:

Windows:    C:\Users\Имя\diploma\
Linux/Mac:  ~/diploma/

Структура должна быть:
diploma/
├── docker-compose.yml
├── .env
├── vkr-aspect-analysis/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── src/
│       ├── main.py
│       ├── database.py
│       ├── redis_client.py
│       ├── gigachat_service.py
│       ├── clustering.py
│       ├── embeddings.py
│       ├── task_queue.py
│       ├── worker.py
│       └── schemas.py
└── front/
    ├── Dockerfile
    ├── nginx.conf
    ├── package.json
    └── src/
        ├── main.tsx
        ├── App.tsx
        ├── routes.tsx
        ├── api/
        │   └── client.ts
        └── components/
            ├── HomePage.tsx
            ├── ProcessingPage.tsx
            ├── ResultsPage.tsx
            ├── DeepAnalysisPage.tsx
            ├── MergeAspectModal.tsx
            └── AspectChart.tsx


4. НАСТРОЙКА ПЕРЕМЕННЫХ ОКРУЖЕНИЯ
================================================================================

Открой файл .env в корне папки diploma/ и заполни:

SECRET_KEY=your-super-secret-key-here-min-32-chars-long-12345
GIGACHAT_AUTH_KEY=your-gigachat-auth-key-here
GIGACHAT_RQUID=your-gigachat-rquid-here

Как получить ключи GigaChat:
1. Зарегистрируйся на https://developers.sber.ru/
2. Создай проект и получь Client ID / Client Secret
3. Заполни GIGACHAT_AUTH_KEY и GIGACHAT_RQUID

ВНИМАНИЕ: Не меняй DB_HOST, REDIS_HOST, пароли — они настроены для Docker.


5. ЗАПУСК ПРИЛОЖЕНИЯ
================================================================================

Открой терминал и перейди в папку проекта:

Windows (PowerShell):
    cd C:\Users\Имя\diploma

Linux/macOS:
    cd ~/diploma

Запусти сборку и старт:
    docker compose up --build -d

ПЕРВЫЙ ЗАПУСК ЗАНИМАЕТ 10-20 МИНУТ
(скачиваются образы Python, Node.js, модель LaBSE ~1.5 GB)
Подожди, не прерывай!


6. ПРОВЕРКА ЗАПУСКА
================================================================================

Проверь статус контейнеров:
    docker ps

Должно быть 4 контейнера в статусе Up:
    analyzer-db       (порт 5432)
    redis             (порт 6379)
    diploma-backend   (порт 8081)
    diploma-frontend  (порт 3000)

Проверь API бэкенда:
    curl http://localhost:8081/health

Должен вернуть: {"status": "alive"}


7. ОТКРЫТИЕ ПРИЛОЖЕНИЯ
================================================================================

Открой браузер:
    http://localhost:3000

Должна открыться главная страница с загрузкой CSV и ручным вводом.


8. ОСТАНОВКА ПРИЛОЖЕНИЯ
================================================================================

Остановить (данные сохранятся):
    docker compose down

Полная очистка (удалить ВСЕ данные):
    docker compose down -v
    ВНИМАНИЕ: Это удалит базу данных и кэш модели!


9. ОБНОВЛЕНИЕ ПОСЛЕ ИЗМЕНЕНИЯ КОДА
================================================================================

Если изменил код бэкенда или фронтенда:
    docker compose up --build -d


10. ПРОСМОТР ЛОГОВ
================================================================================

Бэкенд:
    docker compose logs -f backend

Фронтенд:
    docker compose logs -f frontend

База данных:
    docker compose logs -f analyzer-db

Все контейнеры:
    docker compose logs -f


12. РЕШЕНИЕ ПРОБЛЕМ
================================================================================

Проблема                           | Решение
-----------------------------------|------------------------------------------
docker: command not found          | Установи Docker (см. шаг 2)
port 5432 already in use           | Останови локальный PostgreSQL или смени порт
port 3000 already in use           | Смени порт на 3001:80 в docker-compose.yml
It works! на localhost             | У нас порт 3000, открывай http://localhost:3000
Бэкенд падает: vector not found    | Подожди 30 сек, перезапусти: docker compose restart backend
Долгий первый запрос               | Нормально, модель кэшируется. Подожди 1-2 мин
Ошибка 502 от nginx                | Бэкенд ещё стартует. Подожди и обнови страницу


13. КОМАНДЫ ШПАРГАЛКА
================================================================================

Запуск:                    docker compose up --build -d
Остановка:                 docker compose down
Перезапуск бэкенда:        docker compose restart backend
Логи бэкенда:              docker compose logs -f backend
Логи фронтенда:            docker compose logs -f frontend
Войти в бэкенд:            docker exec -it diploma-backend bash
Войти в базу:              docker exec -it analyzer-db psql -U postgres -d analyzer
Список контейнеров:        docker ps
Ресурсы контейнеров:       docker stats


================================================================================
                    УСПЕШНОГО ЗАПУСКА!
================================================================================