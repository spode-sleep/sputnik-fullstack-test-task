## Тестовое задание на позицию Fullstack разработчика (Python + React)

**Вводные:**
1. Здесь представлен MVP проект файлообменника. Он позволяет загружать файлы, проверяет их на подозрительный контент и отправляет алерты;
2. Репозиторий содержит в себе бэкенд и фронтенд части;
3. В обоих частях присутствуют баги, неоптимизированный код, неудачные архитектурные решения.

**Задачи:**
1. Проведите рефакторинг бэкенда, не ломая бизнес-логики: предложите свое видение архитектуры и реализуйте его;
2. (Дополнительно) На бэкенде есть возможность неочевидной оптимизации - выполните ее;
3. (Дополнительно) Разбейте логику фронтенда на слои;

**Отчёт о рефакторинге**

**Бэкенд**

**1. Архитектура: разбивка монолита на модули**

Проблема:
Весь код жил в плоских файлах без разделения ответственности:
- `service.py` совмещал конфигурацию БД, инициализацию engine, репозиторный доступ к данным и бизнес-логику.
- `tasks.py` дублировал `engine` и `async_session_maker` из `service.py`, создавая два независимых пула соединений к одной БД.
- `create_alert()` был объявлен в `service.py`.

Решение:
Новая структура:

```
src/
  core/
    config.py          # DB URL, STORAGE_DIR, REDIS_URL, engine, session_maker
  files/
    repository.py      # CRUD к таблице files (только работа с сессией)
    service.py         # Бизнес-логика: валидация, запись файла на диск, HTTP-ошибки
  alerts/
    repository.py      # CRUD к таблице alerts
    service.py         # list_alerts, create_alert
  models.py            # SQLAlchemy модели (без изменений)
  schemas.py           # Pydantic схемы (без изменений)
  tasks.py             # Celery-задачи
  app.py               # FastAPI роуты
```

Основная идея в том, что репозиторий знает только о сессии и SQL, сервис знает о бизнес-правилах и HTTP-ошибках, роут знает только о HTTP-запросе/ответе.

---

**2. Баг: гонка условий в event loop (tasks.py)**

Проблема:
Оригинальный код хранил один глобальный `_worker_loop` и переиспользовал его между задачами. При параллельном выполнении двух задач в одном воркере-потоке второй вызов `run_until_complete` падал с `RuntimeError: This event loop is already running`. При завершении первой задачи loop мог оказаться закрытым для второй.

Решение:
Каждая задача создаёт свой event loop через `asyncio.run()`. `asyncio.run()` гарантирует создание нового loop, его корректное завершение и закрытие — без глобального состояния.

---

**3. Оптимизация: объединение scan + metadata в одну задачу (одна сессия)**

Проблема:
Оригинальная цепочка из трёх задач выполняла три отдельных `session.get(StoredFile, file_id)`:

```
scan_file_for_threats(file_id)   -> session.get -> commit -> закрыть сессию
    .delay()
extract_file_metadata(file_id)   -> session.get -> commit -> закрыть сессию
    .delay()
send_file_alert(file_id)         -> session.get -> создать Alert -> commit
```

Итого: 3 round-trip к БД, 3 открытия сессии, плюс overhead диспетчеризации двух промежуточных задач через Redis.

Решение:
Scan и extraction объединены в одну задачу `process_file` с одной сессией:

```
process_file(file_id)    -> session.get -> scan -> metadata -> commit -> закрыть сессию
    .delay()
send_file_alert(file_id) -> session.get -> создать Alert -> commit
```

Итого: 2 round-trip к БД, 2 открытия сессии. `send_file_alert` остаётся отдельной задачей — алерт логически отделён от обработки файла. Дополнительно, логика scan и metadata вынесена в чистые функции `_scan_reasons()` и `_extract_metadata()`, которые не зависят от сессии и легко тестируются изолированно.

---

**4. Баг: processing_status не обновлялся до коммита в scan-задаче**

Проблема:
В `_scan_file_for_threats` строка `file_item.processing_status = "processing"` выставлялась, но коммит происходил только в конце, после выставления `scan_status`. Если задача падала посередине, статус в БД оставался `"uploaded"`, не давая понять, что обработка началась.

Решение:
Статус `"processing"` выставляется сразу в начале, остальные поля — по факту завершения, всё в одном `await session.commit()`.

---

**Фронтенд**

**Разбивка монолитного page.tsx на слои**

Проблема:
Единственный файл `page.tsx` (примерно 300 строк) содержал всё: типы данных, утилиты форматирования, прямые вызовы `fetch`, управление состоянием и JSX-разметку трёх разных UI-блоков.

Решение:
Четыре слоя с чёткими границами ответственности:

```
src/
  types/
    index.ts              # FileItem, AlertItem
  utils/
    format.ts             # formatDate, formatSize, getLevelVariant, getProcessingVariant
  api/
    client.ts             # fetchFiles, fetchAlerts, uploadFile, getDownloadUrl
  hooks/
    useFilesData.ts       # весь state + loadData, submitFile
  components/
    FilesTable.tsx
    AlertsTable.tsx
    FileUploadModal.tsx
  app/
    page.tsx              # только composition (~70 строк)
```

Дополнительно:
- Кнопка "Сохранить" в модалке задизейблена, если поля не заполнены.
- Локальное состояние формы (`title`, `selectedFile`) живёт внутри `FileUploadModal` и сбрасывается при закрытии.
- `handleResponse<T>` в `api/client.ts` убирает дублирование проверки `res.ok`, которое раньше было в каждом вызове `fetch`.

