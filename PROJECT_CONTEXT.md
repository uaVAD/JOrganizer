# JOrganizer

**Версія:** 0.5.0
**Мова:** Python 3.10+ (білд на 3.10, спека цілить 3.13+)
**ОС:** Windows 10/11 (збірка PyInstaller, використовуються Win32 API)
**Тип:** Десктопний застосунок (PyQt6)

## Призначення

Повністю автоматизувати організацію медіафайлів для Jellyfin. Програма сканує папку завантажень, визначає тип контенту (фільм, серіал, аніме), перейменовує файли за правилами Jellyfin, переміщує у відповідну структуру папок та опціонально оновлює бібліотеку Jellyfin через API.

---

# Основна ідея

- **Що робить:** Сканування → Виявлення → Зіставлення → Перейменування → Переміщення → Оновлення Jellyfin
- **Для кого:** Користувачі Jellyfin (Plex-подібні системи), які хочуть автоматизувати імпорт медіа
- **Проблема:** Ручне перейменування та сортування медіафайлів — нудна робота. JOrganizer робить це за одну кнопку.
- **Девіз:** "Press one button and all downloaded media appears in Jellyfin correctly."

---

# Архітектура

## Загальна схема

```
main.py
  └── PyQt6 QApplication
        └── MainWindow (ui/main_window.py)
              ├── Scanner (core/scanner.py) — обхід файлової системи
              ├── MediaDetector (core/detector.py) — визначення типу медіа
              │     └── MetadataAPI (api/metadata.py) — TMDB API
              │     └── AniListAPI (api/anilist.py) — GraphQL API
              ├── Renamer (core/renamer.py) — генерація нових імен
              ├── Organizer (core/organizer.py) — генерація шляхів призначення
              ├── FolderAnalyzer (core/folder_analyzer.py) — аналіз структури папок
              │     ├── Scanner — повторне використання
              │     └── MediaDetector — повторне використання
              ├── OperationsManager (core/operations.py) — виконання/відкат операцій
              │     └── Database — збереження історії
              ├── DuplicateDetector (core/duplicates.py) — пошук дублікатів
              ├── AutoWatcher (monitoring/watcher.py) — фонове спостереження
              │     └── watchdog.Observer — потік ОС
              └── Database (database/__init__.py) — SQLite
```

## Головні модулі

| Модуль | Файл | Відповідальність |
|--------|------|-------------------|
| **main** | `main.py` | Точка входу, створює QApplication та MainWindow |
| **UI** | `ui/main_window.py` | Весь графічний інтерфейс, обробка подій користувача |
| **Scanner** | `core/scanner.py` | Рекурсивне сканування папок для медіафайлів |
| **Detector** | `core/detector.py` | 3-рівневе визначення типу медіа (regex → API → користувач) |
| **Renamer** | `core/renamer.py` | Генерація імен файлів за правилами Jellyfin |
| **Organizer** | `core/organizer.py` | Генерація цільового шляху (структура папок) |
| **FolderAnalyzer** | `core/folder_analyzer.py` | Аналіз папок з медіа, угруповання, API-збагачення |
| **OperationsManager** | `core/operations.py` | Preview, execute, undo/redo операцій |
| **DuplicateDetector** | `core/duplicates.py` | Виявлення дублікатів (ім'я, розмір, хеш) |
| **MetadataAPI** | `api/metadata.py` | HTTP-клієнт для TMDB API |
| **AniListAPI** | `api/anilist.py` | GraphQL-клієнт для AniList API |
| **Database** | `database/__init__.py` | SQLite-обгортка (settings, operations, user_matches) |
| **AutoWatcher** | `monitoring/watcher.py` | watchdog-обгортка для стеження за папками |
| **Errors** | `core/errors.py` | Кастомні винятки (RetryableError, LockedFileError тощо) |
| **Settings** | `config/settings.py` | Глобальні константи: шляхи, кольори, TMDB-ключ |

## Зв'язки між модулями

```
main.py → config.settings (BASE_DIR, DB_PATH, COLORS)
main.py → ui.main_window.MainWindow

MainWindow → core.scanner.Scanner (тільки як залежність FolderAnalyzer)
MainWindow → core.detector.MediaDetector
MainWindow → core.renamer.Renamer
MainWindow → core.organizer.Organizer
MainWindow → core.operations.OperationsManager
MainWindow → core.folder_analyzer.FolderAnalyzer
MainWindow → database.Database
MainWindow → monitoring.watcher.AutoWatcher

FolderAnalyzer → Scanner
FolderAnalyzer → MediaDetector

MediaDetector → api.metadata.MetadataAPI (через asyncio.run)
FolderAnalyzer → api.metadata.MetadataAPI (через asyncio.run)
FolderAnalyzer → api.anilist.AniListAPI (через asyncio.run)

OperationsManager → database.Database
```

## Потік даних

1. Користувач вибирає **Source Folder** → викликається `FolderAnalyzer.analyze()`
2. `FolderAnalyzer` використовує `Scanner` для отримання `list[dict]` файлів
3. `FolderAnalyzer` групує файли по папках, для кожної папки:
   - Викликає `MediaDetector.detect(quick=True)` для кожного файла (regex)
   - Викликає `_detect_folder_type()` з API-запитами (TMDB → AniList)
4. Результат — деревоподібна структура: `{path, name, type, children: [{folder, files}]}`
5. Дані відображаються в `QTreeWidget`
6. Користувач вибирає файли → натискає **Dry Run** → `OperationsManager.preview()`
7. Preview використовує `Detector` (повний, з API) + `Renamer` + `Organizer`
8. Користувач натискає **Execute** → `OperationsManager.execute()` виконує `shutil.move`
9. Операція записується в SQLite (таблиця `operations`)
10. Кнопка **Undo** → `OperationsManager.undo()` виконує зворотний `shutil.move`

---

# Структура проєкту

## Папка: корінь (Jellyfin_Organizer/)

**Призначення:** Корінь проєкту, точка входу, збірка
**Основні файли:**
- `main.py` — точка входу
- `JOrganizer.spec` — конфіг PyInstaller
- `requirements.txt` — залежності
- `JO.ico` — іконка програми
- `JOrganizer_Extended_Spec.md` — технічна специфікація
- `data.db` — SQLite база даних (створюється при першому запуску)
- `.gitignore` — ігноровані файли

## Папка: config/

**Призначення:** Конфігурація програми
**Основні файли:**
- `__init__.py` — порожній
- `settings.py` — глобальні константи (BASE_DIR, DB_PATH, COLORS, TMDB_API_KEY)
- `init.json` — початкові налаштування (API-ключі, тема, шляхи)
**Як використовується:** Імпортується всіма модулями через `from config.settings import ...`
**Приховані дані:** `init.json` містить TMDB API-ключ (`d06e482dde8cfb088bde6c7befd93091`), інші ключі пусті.

## Папка: core/

**Призначення:** Основна бізнес-логіка
**Основні файли:**
- `scanner.py` — Scanner: рекурсивний обхід файлової системи
- `detector.py` — MediaDetector: 3 рівні визначення типу
- `renamer.py` — Renamer: генерація імен за типом
- `organizer.py` — Organizer: цільові шляхи
- `operations.py` — OperationsManager: preview/execute/undo
- `folder_analyzer.py` — FolderAnalyzer: аналіз папок з API-збагаченням
- `duplicates.py` — DuplicateDetector: пошук дублікатів
- `errors.py` — Кастомні винятки
- `__init__.py` — порожній

## Папка: ui/

**Призначення:** Графічний інтерфейс (PyQt6)
**Основні файли:**
- `main_window.py` — MainWindow (704 рядки, вся UI-логіка)
- `__init__.py` — додає корінь проєкту в sys.path

## Папка: api/

**Призначення:** Зовнішні API-клієнти
**Основні файли:**
- `__init__.py` — порожній
- `metadata.py` — MetadataAPI: TMDB (movie + TV пошук)
- `anilist.py` — AniListAPI: GraphQL-запити до AniList

## Папка: database/

**Призначення:** Робота з SQLite
**Основні файли:**
- `__init__.py` — Database: повноцінна обгортка (CRUD для operations, settings, user_matches)

## Папка: monitoring/

**Призначення:** Фонове спостереження за файловою системою
**Основні файли:**
- `watcher.py` — AutoWatcher + FileWatchHandler (watchdog)

## Папка: tests/

**Призначення:** Тести (pytest)
**Основні файли:**
- `conftest.py` — фікстури (temp_dir, organizer, renamer, detector, scanner)
- `test_renamer.py` — 7 тестів для Renamer
- `test_detector.py` — 7 тестів для MediaDetector
- `test_organizer.py` — 5 тестів для Organizer
- `test_scanner.py` — 6 тестів для Scanner
- `test_operations.py` — 7 тестів для OperationsManager
- `test_duplicates.py` — 7 тестів для DuplicateDetector
- `test_database.py` — 7 тестів для Database
- `__init__.py` — порожній

## Папки: build/, dist/

**Призначення:** Результати збірки PyInstaller
**Що містять:**
- `build/JOrganizer/` — проміжні файли збірки (toc, pyz, pkg)
- `dist/JOrganizer/` — готовий дистрибутив (JOrganizer.exe + DLL)
- Збірка виконана з `console=False` (windows-додаток)
- Іконка: `JO.ico`

## Папки: plugins/, assets/, logs/

**Призначення:** Зарезервовані для майбутніх функцій
**Стан:** Усі порожні

---

# Аналіз основних файлів

## main.py (25 рядків)

**Призначення:** Точка входу
**Що виконує:**
- Додає корінь проєкту в sys.path
- Імпортує BASE_DIR та DB_PATH з config.settings
- Створює QApplication → MainWindow → show() → app.exec()
**Залежності:** PyQt6.QtWidgets, ui.main_window, config.settings

## ui/main_window.py (704 рядки)

**Призначення:** Весь графічний інтерфейс
**Ключові класи:**
- `OperationThread(QThread)` — фоновий потік для виконання операцій (прогрес, лог, фініш, помилка)
- `MainWindow(QMainWindow)` — головне вікно
**Ключові методи MainWindow:**
- `_init_ui()` — створює 3-панельний інтерфейс (ліво/центр/право) через QSplitter
- `_create_left_panel()` — QTabWidget: Settings + Scan вкладки
- `_create_center_panel()` — QTreeWidget (файлова структура) + QProgressBar
- `_create_right_panel()` — QTextEdit (логи) + кнопки Dry Run/Execute/Undo
- `_scan_source()` — викликає FolderAnalyzer.analyze() + відображає дерево
- `_start_dry_run()` — викликає OperationsManager.preview() + діалог
- `_start_execution()` — запускає OperationThread
- `_undo_last()` — викликає OperationsManager.undo()
- `_start_auto_watch()` / `_stop_auto_watch()` — управління AutoWatcher
- `_load_settings()` / `_save_settings()` — через Database (SQLite), авто-збереження кожні 30 секунд
- `_apply_stylesheet()` — тема "Modern Dark" (кольори: фон #111827, акцент #7C3AED)
- `_on_watched_file()` — обробка нових файлів від Watcher (додає в дерево)
**Залежності:** Усі модулі core/, api/metadata.py (через detector), database, monitoring/watcher

## core/scanner.py (61 рядок)

**Призначення:** Рекурсивний обхід папок
**MEDIA_EXTENSIONS:** 17 розширень: .mkv, .mp4, .avi, .mov, .wmv, .flv, .webm, .m4v, .mpg, .mpeg, .ts, .rm, .rmvb, .3gp, .ogv, .m2ts, .vob
**Методи:**
- `scan(folder_path)` — обгортка для scan_folder
- `scan_folder(path, progress_callback)` — рекурсивний пошук, повертає `list[dict]`
- `_scan_directory(directory, callback)` — внутрішня рекурсія
- Пропускає приховані файли (починаються з `.` або `~`)
- Ігнорує PermissionError
**Залежності:** pathlib (немає зовнішніх)

## core/detector.py (190 рядків)

**Призначення:** 3-рівневе визначення типу медіа
**Рівні:**
1. **Regex** (`quick=True` використовує тільки цей) — TV-патерни (S01E05, 1x03, Season 02 Episode 15), Аніме-патерни (ключові слова), Фільми (рік), Якість (2160p/1080p/720p), Джерело (WEBRip/BluRay)
2. **API** (TMDB) — `asyncio.run(api_detector.search(filename))`
3. **Користувач** — повертає `{type:'unknown', level:3, method:'user_confirmation'}`
**Ключові патерни:**
- `TV_PATTERN` — S01E05, 1x03, season 2 episode 15
- `SEASON_ONLY` — S02, Season 2
- `ANIME_EPISODE` — цифри в кінці назви
- `ANIME_PATTERN` — 20+ відомих аніме-назв
- `QUALITY_PATTERN` — 2160p/1080p/720p/480p/4k/3d
- `SOURCE_PATTERN` — WEBRip/BluRay/WEB-DL/HDTV/DVDRip/HDRip/CAM/TS/R5/DVD/BD/REMUX/IMAX
**Залежності:** api.metadata.MetadataAPI, re, logging

## core/renamer.py (52 рядки)

**Призначення:** Генерація нових імен файлів
**Правила:**
- `movie`/`cartoon`: `Назва (2025).ext`
- `tv`/`anime` з season+episode: `Назва (2025) - S01E05.ext`
- `unknown`: зберігає оригінальне ім'я
**Методи:** `rename_movie()`, `rename_tv()`, `rename_anime()`, `generate_new_filename()`
**Залежності:** pathlib

## core/organizer.py (24 рядки)

**Призначення:** Генерація цільових шляхів
**Логіка:**
- Якщо є season: `{destination}/{title} ({year})/Season {season:02d}/{filename}`
- Якщо немає season: `{destination}/{title} ({year})/{filename}`
- Якщо немає year: `{destination}/{title}/{filename}`
**УВАГА:** Тести (`test_organizer.py`) очікують `organizer.categories['movie']`, але поточний код **не має** атрибута `categories`. Код і тести розсинхронізовані.

## core/operations.py (179 рядків)

**Призначення:** Управління операціями з файлами
**Ключові методи:**
- `set_pipeline(detector, renamer, organizer)` — встановлює компоненти
- `preview(files, destination)` — використовується UI (через detector+renamer+organizer)
- `dry_run(files, organizer, renamer, detector)` — використовується тестами (той самий функціонал, інша сигнатура)
- `execute(preview, force=False)` — виконує shutil.move, записує в БД
- `undo(operation_id=None)` — відкат операцій
- `_undo_operation(op)` — зворотний shutil.move
**Кодова проблема:** Методи `preview` і `dry_run` дублюють функціонал, але мають різні сигнатури.

## core/folder_analyzer.py (237 рядків)

**Призначення:** Повний аналіз структури папок
**Алгоритм:**
1. Сканує файли через Scanner
2. Групує по батьківській папці (SUB_FOLDER: Season/Saison/Temporada — вирівнює на рівень вище)
3. Для кожної папки:
   - Виявляє тип кожного файла (quick regex)
   - Визначає тип папки через TMDB → AniList → unknown
4. Будує деревоподібну структуру з категоріями
**Методи API:**
- `_try_tmdb()` — `asyncio.run(api.search(title, year))`
- `_try_anilist()` — `asyncio.run(api.search(title))`
**Залежності:** core.detector.MediaDetector, core.scanner.Scanner, api.metadata.MetadataAPI, api.anilist.AniListAPI

## core/duplicates.py (79 рядків)

**Призначення:** Виявлення дублікатів
**Методи:**
- `check_duplicates(files, destination)` — перевірка по імені, потім по розміру
- `compute_hash(filepath)` — SHA256 хеш
- `_resolve(file_info, mode)` — режими: replace/skip/keep_both/ask
**Режими:** зберігаються в `init.json` (`duplicate_mode`), стандартно — `ask`
**Проблема:** `check_duplicates` порівнює `(filename.lower(), destination)`, але `destination` це об'єкт Path, а `existing_files` це `set` з `(name.lower(), parent)` — порівняння з Path замість parent працює некоректно.

## api/metadata.py (89 рядків)

**Призначення:** Клієнт TMDB API
**Методи:**
- `search(title, year)` — асинхронний пошук в TMDB
- `_search_tmdb(title, year)` — шукає одночасно movie та TV, порівнює за популярністю
- Аніме-детекція: genre_id=16 + original_language='ja' (movie), genre_id=16 + origin_country='JP' (TV)
**Ендпоінти:** `api.themoviedb.org/3/search/movie`, `api.themoviedb.org/3/search/tv`
**Залежності:** aiohttp, config.settings.TMDB_API_KEY

## api/anilist.py (94 рядки)

**Призначення:** Клієнт AniList GraphQL API
**Методи:**
- `search(title)` — GraphQL-запит
- `_graphql_search(title)` — надсилає POST на `graphql.anilist.co`
- `_normalize(title)` — нормалізація для точного порівняння
**Важливо:** Повертає результат **тільки** якщо назва збігається точно (після нормалізації). Це захист від хибних спрацьовувань.
**Залежності:** aiohttp

## database/__init__.py (134 рядки)

**Призначення:** SQLite обгортка
**Таблиці:**
- `user_matches` — кеш підтверджених користувачем відповідностей (original_name, matched_name, media_type)
- `operations` — історія переміщень (old_path, new_path, timestamp)
- `settings` — налаштування (setting, value) з UNIQUE constraint
**Методи:** add/get/get_all/delete/clear для кожної таблиці
**Важливо:** `check_same_thread=False` — дозволяє доступ з різних потоків (QThread). При старті виконується `_init_tables()` з CREATE TABLE IF NOT EXISTS.

## monitoring/watcher.py (109 рядків)

**Призначення:** Фонове спостереження за папками
**Компоненти:**
- `FileWatchHandler(FileSystemEventHandler)` — обробник подій watchdog
- `AutoWatcher` — обгортка над Observer
**Логіка:**
- `on_created` / `on_modified` → `_handle_file` → перевірка чи файл стабільний (розмір не змінюється) → callback
- Фільтр по розширеннях медіа (той самий список, що в Scanner)
- Детекція "файл дописується": відстежує розмір у часі
**Залежності:** watchdog

## config/settings.py (24 рядки)

**Призначення:** Глобальні константи
**Вміст:**
- `BASE_DIR` — корінь проєкту (Path)
- `DB_PATH` — `BASE_DIR / "data.db"`
- `TMDB_API_KEY` — з `init.json` (завантажується при імпорті)
- `COLORS` — палітра теми (background #111827, panel #1F2937, accent #7C3AED, success #10B981, warning #F59E0B, error #EF4444)

## JOrganizer.spec (27 рядків)

**Призначення:** Конфігурація PyInstaller
**Параметри:**
- Вхідний файл: `main.py`
- Дані: `JO.ico`, `config/init.json`
- Приховані імпорти: `api`, `config`, `core`, `database`, `monitoring`, `ui`
- Виключено: `pytest`, `setuptools`, `wheel`
- Оптимізація: 1
- Console: False (Windows-додаток без консолі)
- UPX: True
- Іконка: `JO.ico`
- Ім'я: `JOrganizer`

---

# Залежності

## Runtime (requirements.txt)

| Бібліотека | Призначення | Де використовується |
|-----------|-------------|---------------------|
| **PyQt6 ≥6.6.0** | GUI фреймворк | ui/main_window.py — все вікно, діалоги, дерево |
| **requests ≥2.31.0** | HTTP-запити | Не використовується напряму, але вказана (можливо для майбутнього Jellyfin API) |
| **aiohttp ≥3.9.0** | Асинхронні HTTP-запити | api/metadata.py, api/anilist.py — TMDB та AniList API |
| **python-slugify ≥8.0.0** | Нормалізація імен | Не використовується в коді (імпорт відсутній) |
| **watchdog ≥3.0.0** | Файловий моніторинг | monitoring/watcher.py — AutoWatcher |

## Тестові (requirements.txt)

| Бібліотека | Призначення |
|-----------|-------------|
| **pytest ≥8.0.0** | Тестовий фреймворк |
| **pytest-qt ≥4.2.0** | Тестування PyQt6 інтерфейсу (не використовується в існуючих тестах) |

## Зовнішні API

| API | Тип | Ключ | Де використовується |
|-----|-----|------|---------------------|
| **TMDB** | REST (REST API) | `d06e482dde8cfb088bde6c7befd93091` (жорстко зашитий) | api/metadata.py, core/folder_analyzer.py |
| **AniList** | GraphQL | Не потрібен | api/anilist.py, core/folder_analyzer.py |
| **Jellyfin** | REST (заплановано) | Порожній в init.json | Не реалізовано |

## Приховані залежності

- **shutil** (stdlib) — `core/operations.py`, виконання переміщення файлів
- **sqlite3** (stdlib) — `database/__init__`
- **hashlib** (stdlib) — `core/duplicates.py`
- **asyncio** (stdlib) — `core/detector.py`, `core/folder_analyzer.py` (для запуску асинхронних API-запитів з синхронного коду)

---

# Логіка роботи

## 1. Запуск програми

1. `python main.py`
2. `main()` додає корінь в sys.path
3. Імпортує `BASE_DIR`, `DB_PATH` з `config.settings` (при цьому завантажується TMDB_API_KEY з init.json)
4. Створює `QApplication(sys.argv)`
5. Створює `MainWindow` → викликає `_init_ui()` → `_load_settings()` → `_apply_stylesheet()`
6. `_load_settings()` відновлює збережені папки з SQLite
7. Запускає QTimer на авто-збереження (кожні 30 секунд)
8. `window.show()`, `app.exec()`

## 2. Ініціалізація MainWindow

- Створює `Database(DB_PATH)` — підключається до SQLite, створює таблиці
- Створює `MediaDetector()` (в конструкторі створює `MetadataAPI()`)
- Створює `Renamer()`, `OperationsManager(db)`, `FolderAnalyzer()`, `AutoWatcher()`
- Будує інтерфейс: QSplitter з 3 панелями (ліво: вкладки Settings/Scan, центр: дерево файлів + прогрес, право: логи + кнопки)
- Завантажує збережені налаштування з БД

## 3. Сканування та аналіз

1. Користувач вибирає папку → натискає "Analyze Folder"
2. `_scan_source()` викликає `FolderAnalyzer.analyze(Path(folder), progress_callback)`
3. `FolderAnalyzer`:
   a. `Scanner.scan_folder()` — рекурсивний обхід, повертає `list[dict]` файлів
   b. `_group_by_parent()` — групує по батьківській папці (вирівнює SubFolder)
   c. Для кожної групи:
      - `_analyze_folder()` → `detector.detect(quick=True)` для кожного файла
      - `_detect_folder_type()` → TMDB → AniList → unknown
   d. Будує деревоподібну структуру
4. Результат відображається в `QTreeWidget` з кольоровим кодуванням

## 4. Прев'ю (Dry Run)

1. Користувач вибирає файли в дереві → натискає "Dry Run"
2. `_start_dry_run()` викликає `OperationsManager.preview()`
3. Для кожного файла: `detector.detect()` (повний, з API) → `renamer.generate_new_filename()` → `organizer.get_target_path()`
4. Показує діалогове вікно зі списком дій

## 5. Виконання

1. Користувач натискає "Execute"
2. `_start_execution()` створює `OperationThread(QThread)` і запускає його
3. `OperationThread.run()` викликає `OperationsManager.execute(preview)`
4. Для кожної операції:
   - Записує в БД (old_path, new_path, timestamp)
   - `target_path.parent.mkdir(parents=True, exist_ok=True)`
   - `shutil.move(original, target)`
5. Результати повертаються через сигнали: `progress`, `log`, `finished`, `error`

## 6. Відкат (Undo)

1. Користувач натискає "Undo Last"
2. `_undo_last()` викликає `OperationsManager.undo()`
3. `undo()` отримує всі операції з БД (зворотній порядок)
4. Для кожної: `shutil.move(new_path, old_path)`, видаляє запис з БД

## 7. Авто-спостереження (Auto Watch)

1. Користувач вибирає папку → "Start Watch"
2. `AutoWatcher.add_folder(watch_folder, callback)` — додає `FileWatchHandler` до `Observer`
3. `Observer.start()` — запускає фоновий потік
4. При створенні/зміні файла: перевіряє розширення → чекає стабілізації розміру → викликає callback
5. Callback (`_on_watched_file`) додає файл в дерево в UI

## 8. Завершення

1. `MainWindow.closeEvent()` → якщо watcher запущений, зупиняє
2. QApplication завершується

---

# UI

## Структура вікна

```
┌──────────────────────────────────────────────────────────────┐
│ QMainWindow (1200x800, мін)                                  │
│ ┌──────────┬────────────────────┬──────────────────────────┐ │
│ │ Ліво     │ Центр              │ Право                    │ │
│ │ [Tabs]   │ [Header]           │ [Logs] QTextEdit         │ │
│ │ Settings │ Folders: 0 Files:0 │ [Clear Logs]             │ │
│ │ Scan     │                    │                          │ │
│ │          │ [QTreeWidget]       │ [Dry Run]                │ │
│ │          │ Name │ Type        │ [Execute]                │ │
│ │          │                   │ [Undo Last]              │ │
│ │          │ [QProgressBar]     │                          │ │
│ ├──────────┴────────────────────┴──────────────────────────┤ │
│ │ [Status: Ready]                       [Memory: 0 MB]     │ │
│ └───────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
```

## Вкладка Settings (ліво)

- **Destination:** QLineEdit (тільки читання) + Browse
- **Watch Folder:** QLineEdit (тільки читання) + Browse
- **Auto Watch:** Status Label (Stopped/Running) + Start Watch / Stop Watch

## Вкладка Scan (ліво)

- **Source:** QLineEdit (тільки читання) + Browse
- **Analyze Folder** кнопка
- **Refresh** кнопка

## Центральна панель

- QTreeWidget (2 колонки: Name, Type)
  - Кольорове кодування типів: movie=#10B981, tv=#7C3AED, anime=#F59E0B, cartoon=#EC4899, unknown=#6B7280
  - ExtendedSelection (мультивибір)
  - AlternatingRowColors
- QProgressBar (прихований за замовчуванням)

## Права панель

- QTextEdit (логи, моноширинний шрифт Consolas 9pt)
- Кнопки: Dry Run → Execute → Undo Last

## Нижня панель (StatusBar)

- Текст статусу
- Memory (розмір вибраних файлів)

## Діалоги

- **Dry Run Preview:** QDialog з QTextEdit (список дій) + Close
- **Error/Warning:** QMessageBox.critical/warning
- **Browse:** QFileDialog.getExistingDirectory

## Кольорова тема

- Dark Modern: фон #111827, панелі #1F2937, акцент #7C3AED (фіолетовий)
- Всі елементи стилізовані через `_apply_stylesheet()`

---

# Робота з даними

## Дані

| Тип | Де зберігається | Формат |
|-----|-----------------|--------|
| Налаштування | SQLite (settings) | TEXT pairs |
| Історія операцій | SQLite (operations) | TEXT (old_path, new_path, timestamp) |
| Кеш відповідностей | SQLite (user_matches) | TEXT (original_name, matched_name, media_type) |
| Початкові налаштування | config/init.json | JSON |
| Медіафайли | Файлова система | Відеоформати |

## База даних (SQLite)

**Файл:** `data.db` (в корені проєкту)
**Таблиці:**
- `settings` — UNIQUE на `setting`, використовується `INSERT ... ON CONFLICT DO UPDATE`
- `operations` — історія для undo
- `user_matches` — кеш (наразі API не використовує, тільки CRUD методи є)
**check_same_thread=False** — дозволяє доступ з QThread

## Імпорт/Експорт

- Відсутній (всі налаштування зберігаються автоматично в SQLite)
- `init.json` — тільки початкове завантаження при старті

## API-клієнти

- **TMDB API Key:** жорстко зашитий в `init.json` (`d06e482dde8cfb088bde6c7befd93091`)
- **AniList:** без ключа (публічний GraphQL)
- **Jellyfin API:** не реалізований (ключ пустий в init.json)
- **TVDB/OMDb ключі:** пусті в init.json

## Логування

- `logging.basicConfig` (INFO рівень)
- Формат: `час - ім'я - рівень - повідомлення`
- Виводиться в консоль (якщо console=False в spec — не буде видно)
- UI дублює логи в `QTextEdit`

---

# Потенційні проблеми

## Критичні

1. **Розсинхронізація коду та тестів:**
   - `test_organizer.py` очікує `organizer.categories['movie']`, але `Organizer.__init__()` не створює `self.categories`. Всі тести `TestOrganizer` впадуть.
   - `test_operations.py` використовує `ops_manager.dry_run(files, organizer, renamer, detector)` (сигнатура з 4 параметрами після files), але UI використовує `preview(files, destination)`. Методи дублюють логіку з різними сигнатурами.

2. **Жорстко зашитий API-ключ:**
   - `config/init.json` містить `tmdb_api_key` у відкритому вигляді.
   - Ключ потрапляє в білд через `JOrganizer.spec` (рядок 11).
   - Будь-хто з доступом до exe може його витягнути.

3. **Потенційний баг в DuplicateDetector:**
   - `check_duplicates` порівнює `(filename.lower(), destination)` (де destination — це Path), хоча в `existing_files` зберігаються `(f.name.lower(), f.parent)`. Порівняння з destination замість parent — це логічна помилка.

## Баги

4. **TV_PATTERN неоднозначність:** `[xe]` в регулярному виразі (рядок 14, `core/detector.py`) — квадратні дужки означають "або 'x' або 'e'". Формат "S01X05" визнається як TV, що може бути неочікувано.

5. **Anime-детекція рівня 1:** Якщо файл має TV-паттерн (S01E01), він завжди визначається як `tv`, навіть якщо назва — відоме аніме. Це дизайн-рішення: "TV pattern wins over anime keyword at file level; TMDB corrects at folder level."

## Вузькі місця продуктивності

6. **Синхронний API-доступ через `asyncio.run()`:**
   - `detector._level2_api_lookup()` та `folder_analyzer._try_tmdb()`, `_try_anilist()` створюють новий event loop для кожного запиту.
   - Кожен виклик створює новий `aiohttp.ClientSession()`.
   - Блокує UI під час виконання.

7. **Відсутність кешування API-запитів:** Кожен виклик `detect()` з `quick=False` робить API-запит. При preview 100 файлів — 100 HTTP-запитів.

8. **`_detect_folder_type` робить 2-3 API-запити** на кожну папку (TMDB з year, TMDB без year, AniList). При 100 папках — до 300 запитів.

9. **Список медіа-розширень дублюється** в `scanner.py` та `watcher.py`.

## Слабкі місця

10. **Відсутність graceful shutdown:** При закритті вікна зупиняється тільки watcher, але не `OperationThread`.

11. **Небезпечний доступ до дерева в `_on_watched_file`:** Якщо дерево ще не заповнене, код може впасти.

12. **Відсутність валідації API-ключів:** Якщо TMDB_API_KEY порожній або невалідний, помилка ігнорується (except), програма просто працює без Level 2.

---

# Рекомендації

## Терміново

1. **Виправити `Organizer` — додати `categories`** або оновити тести, щоб вони відповідали поточному API.
2. **Видалити дублювання `preview`/`dry_run`** в `operations.py`. Залишити один метод з єдиною сигнатурою.
3. **Виправити `DuplicateDetector.check_duplicates`** — порівнювати `(filename.lower(), parent)` коректно.

## Продуктивність

4. **Додати кеш API-запитів** (in-memory dict або SQLite user_matches) для повторюваних назв.
5. **Оптимізувати `FolderAnalyzer`** — не робити API-запити для кожної папки окремо; групувати та дедуплікувати.
6. **Використовувати єдиний `aiohttp.ClientSession`** замість створення нового для кожного запиту.

## Безпека

7. **Винести API-ключі** з `init.json` в змінні оточення або `.env` файл.
8. **Не включати API-ключі в білд** — завантажувати при першому запуску.

## Архітектура

9. **Використовувати єдиний event loop** для всіх асинхронних операцій.
10. **Відокремити логіку обробки API-відповідей** від HTTP-клієнтів (SRP).
11. **Реалізувати plugin system** — папка `plugins/` порожня, але spec передбачає плагіни.
12. **Додати Jellyfin API-клієнт** — зараз це тільки в spec, код відсутній.

## Тестування

13. **Додати mock для API-запитів** в тестах (зараз `MediaDetector` створює реальний `MetadataAPI()`).
14. **Додати UI-тести** з `pytest-qt` (залежність вказана, але не використовується).
15. **Додати інтеграційні тести** для `FolderAnalyzer`.

## Код

16. **Використовувати константи для медіа-розширень** — список дублюється в `scanner.py` та `watcher.py`.
17. **Додати обробку сигналу `finished` в `OperationThread`** — при закритті вікна очікувати завершення потоку.

---

# Інструкція для майбутніх змін

## Як безпечно додавати нові функції

### Додавання нового API-клієнта
1. Створити файл в `api/` з класом-клієнтом (асинхронний, aiohttp)
2. Додати ключ в `config/init.json` (якщо потрібен)
3. Додати конфігурацію в `config/settings.py`
4. Використовувати через `asyncio.run()` в синхронному коді
5. Додати тести з mock-об'єктами

### Додавання нового типу медіа
1. Додати правила в `core/detector.py` (патерни)
2. Додати правила перейменування в `core/renamer.py`
3. Додати обробку шляху в `core/organizer.py`
4. Додати колір в `TYPE_COLORS` в `ui/main_window.py`
5. Додати тести для всіх трьох рівнів

### Додавання UI-компонента
1. Всі UI-компоненти додаються в `ui/main_window.py`
2. Використовувати існуючі стилі через `COLORS` з `config/settings.py`
3. Дотримуватись патерну: метод `_create_*_panel()` викликається з `_init_ui()`
4. Для фонових операцій — використовувати `OperationThread` (або `QThread`)
5. Додати метод `_save_settings()` якщо потрібно зберігати стан

### Додавання нової таблиці в БД
1. Додати `CREATE TABLE` в `database/__init__.py:_init_tables()`
2. Додати CRUD методи в `Database` клас
3. Використовувати `check_same_thread=False` (для доступу з QThread)

## Які файли змінювати

| Зміна | Файли |
|-------|-------|
| Новий API | `api/*.py`, `config/init.json`, `config/settings.py` |
| Новий тип медіа | `core/detector.py`, `core/renamer.py`, `core/organizer.py`, `ui/main_window.py` |
| Новий UI | `ui/main_window.py` (і тільки цей файл) |
| Нова БД-таблиця | `database/__init__.py` |
| Нова логіка | `core/*.py` |
| Новий моніторинг | `monitoring/watcher.py` |
| Нова зовнішня залежність | `requirements.txt` |
| Збірка | `JOrganizer.spec` |

## Що не варто ламати

1. **Формат `data.db`** — таблиці `operations` (для undo), `settings` (для стану вікна), `user_matches`
2. **Кольорову тему** — всі UI-компоненти покладаються на `COLORS` з `config/settings.py`
3. **Сигнатуру `main()`** — точка входу для PyInstaller
4. **Структуру `FolderAnalyzer.analyze()`** — результат використовується `_populate_tree()`
5. **Формат результату `MediaDetector.detect()`** — `dict` з `type`, `title`, `season`, `episode`, `year`, `confidence`
6. **Формат preview для execute** — список словників з `source`/`original` та `dest`/`target`

## Важливі залежності

- **`OperationsManager.preview` → `detector.detect(..., quick=False)`** — викликає API
- **`FolderAnalyzer.analyze` → `detector.detect(..., quick=True)`** — без API
- **`MainWindow.closeEvent`** → має зупиняти `AutoWatcher`
- **`Database(DB_PATH, check_same_thread=False)`** — потрібен для роботи з QThread
- **`MediaDetector.__init__`** → створює `MetadataAPI()` (важка ініціалізація)

---

# Короткий контекст для LLM

**JOrganizer** — десктопний застосунок на Python 3.10+ / PyQt6 для автоматичної організації медіафайлів під Jellyfin. Основна ідея: сканувати папку завантажень, визначати тип контенту (фільм, серіал, аніме, невідомо) через 3 рівні (регулярні вирази → API TMDB/AniList → підтвердження користувача), перейменовувати за правилами Jellyfin, переміщувати в правильну структуру папок і опціонально оновлювати бібліотеку Jellyfin.

**Архітектура:** Точка входу `main.py` створює `QApplication` та `MainWindow`. MainWindow містить 3 панелі (ліво — налаштування/сканування, центр — дерево файлів, право — логи/кнопки). Використовує `FolderAnalyzer` для аналізу папок (який включає `Scanner` та `MediaDetector`), `OperationsManager` для прев'ю/виконання/відкату операцій через `shutil.move` з історією в SQLite (`database/__init__.py`). Фонове спостереження за папками через `watchdog` (`monitoring/watcher.py`). API-клієнти: TMDB (REST) та AniList (GraphQL) через `aiohttp`. Збірка через PyInstaller в `dist/JOrganizer/`.

**Структура:** 16 файлів коду, 8 тест-файлів (pytest, 46 тестів). Ключові модулі: `core/scanner.py` (рекурсивний обхід), `core/detector.py` (3-рівнева детекція з regex + API), `core/renamer.py` (генерація імен), `core/organizer.py` (шляхи призначення), `core/operations.py` (керування файловими операціями), `core/folder_analyzer.py` (аналіз папок з TMDB/AniList), `core/duplicates.py` (SHA256 + ім'я + розмір), `database/__init__.py` (SQLite з 3 таблицями: settings, operations, user_matches). Дизайн: тільки темна тема (#111827 фон, #7C3AED акцент). Конфігурація: `config/settings.py` + `config/init.json` (там TMDB API-ключ `d06e482dde8cfb088bde6c7befd93091`). Білд: `JOrganizer.spec`.

**Відомі проблеми:** розсинхронізація тестів з кодом (`test_organizer.py` очікує `organizer.categories`, якого немає), дублювання `preview`/`dry_run` в operations.py, жорстко зашитий TMDB-ключ, неефективне використання `asyncio.run()` (новий event loop на кожен API-запит), відсутність кешування API-запитів, можливий баг в `DuplicateDetector.check_duplicates`. Jellyfin API-інтеграція не реалізована (init.json з пустими ключами). Папки `plugins/`, `assets/`, `logs/` порожні.
