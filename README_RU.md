# Реестр Центра содействия экспорту

Django-приложение для управления сертификатами экспортного центра.

## ✅ Проект настроен и готов к работе!

### 🔐 Данные для входа в админ-панель:

- **URL:** http://127.0.0.1:8000/admin/
- **Username:** `admin`
- **Email:** `admin@example.com`
- **Password:** `admin123`

⚠️ **ВАЖНО:** Смените пароль после первого входа!

## 🚀 Запуск проекта

### 1. Установка зависимостей (если еще не установлены):

```bash
pip install -r requirements.txt
```

### 2. Запуск сервера разработки:

```bash
python manage.py runserver
```

Проект будет доступен по адресу: http://127.0.0.1:8000/

### 3. Доступ к админ-панели:

http://127.0.0.1:8000/admin/

## 📋 Основные команды

### Создать нового суперпользователя:
```bash
python manage.py createsuperuser
```

### Выполнить миграции:
```bash
python manage.py migrate
```

### Собрать статические файлы:
```bash
python manage.py collectstatic
```

### Обновить статусы сертификатов:
```bash
python manage.py update_certificate_statuses
```

### Импортировать ISO стандарты:
```bash
python manage.py import_iso_standards
```

## 🛠 Технологии

- **Django 4.2.23** - веб-фреймворк
- **Celery** - фоновые задачи
- **SQLite/PostgreSQL** - база данных
- **ReportLab** - генерация PDF
- **Pillow** - обработка изображений
- **QR Code** - генерация QR-кодов

## 📂 Структура проекта

- `cert_checker/` - основное приложение Django
- `certificates/` - модуль управления сертификатами
- `templates/` - HTML-шаблоны
- `static_collected/` - статические файлы
- `email/` - шаблоны email-уведомлений

## 🔧 Настройка для продакшена

1. Создайте файл `.env` с настройками:
```env
SECRET_KEY=your-secret-key-here
DEBUG=False
DATABASE_URL=postgres://user:password@localhost:5432/dbname
```

2. Настройте PostgreSQL базу данных

3. Запустите с помощью gunicorn:
```bash
gunicorn cert_checker.wsgi:application
```

## 📝 Лицензия

Проект разработан для Центра содействия экспорту.

