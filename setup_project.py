#!/usr/bin/env python
"""Скрипт для первоначальной настройки проекта"""
import os
import sys
import subprocess

# Получаем путь к директории проекта
project_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(project_dir)

print("=" * 60)
print("НАСТРОЙКА ПРОЕКТА")
print("=" * 60)

# 1. Выполняем миграции
print("\n1. Выполнение миграций базы данных...")
try:
    subprocess.run([sys.executable, 'manage.py', 'migrate'], check=True)
    print("✓ Миграции выполнены успешно")
except subprocess.CalledProcessError as e:
    print(f"✗ Ошибка при выполнении миграций: {e}")
    sys.exit(1)

# 2. Создаем суперпользователя
print("\n2. Создание суперпользователя...")
try:
    subprocess.run([sys.executable, 'create_superuser.py'], check=True)
    print("✓ Суперпользователь создан")
except subprocess.CalledProcessError as e:
    print(f"✗ Ошибка при создании суперпользователя: {e}")
    sys.exit(1)

print("\n" + "=" * 60)
print("НАСТРОЙКА ЗАВЕРШЕНА!")
print("=" * 60)
print("\nДанные для входа:")
print("  Username: admin")
print("  Email: admin@example.com")
print("  Password: admin123")
print("\nДля запуска проекта используйте:")
print("  python manage.py runserver")
print("=" * 60)

