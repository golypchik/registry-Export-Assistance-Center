@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ============================================
echo Git: Добавление изменений
echo ============================================

git add certificates/models.py
git add certificates/admin.py
git add certificates/forms.py
git add certificates/certificate_generator.py
git add certificates/views.py
git add certificates/templates/certificates/certificate_detail.html
git add certificates/templates/certificates/search_results.html
git add certificates/templates/certificates/admin/manage_inspections.html
git add certificates/templates/certificates/admin/certificate_list.html
git add certificates/templates/certificates/audit_template.html
git add certificates/templates/certificates/certificate_template.html
git add certificates/migrations/0028_add_multiple_iso_standards.py
git add certificates/migrations/0029_migrate_iso_standard_data.py

echo.
echo ============================================
echo Git: Коммит изменений
echo ============================================

git commit -m "feat: множественные ISO стандарты и улучшения генерации сертификатов

Множественные ISO стандарты:
- Создана промежуточная модель CertificateISOStandard для связи многие-ко-многим
- Добавлено поле iso_standards (ManyToManyField) в модель Certificate
- Обновлены методы модели для работы с несколькими стандартами
- Добавлен inline в админке для управления несколькими стандартами ISO
- Обновлен генератор для отображения стандартов столбиком на фото
- Все стандарты отображаются каждый с новой строки
- Обновлены шаблоны для корректного отображения
- Созданы миграции БД с автоматическим переносом данных
- Сохранена обратная совместимость

Оптимизация генерации (исправлены таймауты):
- ОТКЛЮЧЕНА автоматическая регенерация при каждом сохранении (предотвращает таймауты)
- Регенерация только при изменении ISO стандартов или через кнопки
- Переход с PNG на JPEG (качество 95%) для ВСЕХ генерируемых изображений
- Значительно ускорена генерация сертификатов
- Исправлена ошибка 'AttributeError: _idat object has no attribute fileno'
- НЕ перезаписываются загруженные пользователем файлы (uploaded_*)

Управление регенерацией:
- Admin action 'Регенерировать сертификаты' - выбор нескольких сертификатов и массовая регенерация
- Admin action 'Регенерировать QR-коды' - массовая регенерация QR-кодов
- Добавлена отдельная секция 'QR-код' в админке с большой кнопкой перегенерации
- Кнопка 'Скачать QR-код' с иконкой
- Кнопка 'Перегенерировать QR-код' с подтверждением и индикатором загрузки
- Улучшенный дизайн с выделением и иконками
- Детальная статистика по результатам регенерации (успех/ошибки/пропуски)

Изменения интерфейса:
- Поле 'Система менеджмента качества' переименовано в 'Настоящий сертификат удостоверяет'
- Убран префикс 'Система менеджмента подтверждает' на сертификатах
- Добавлено предупреждение о ручной регенерации сертификатов
- Теперь выводится только текст из поля БД"

echo.
echo ============================================
echo Git: Push изменений
echo ============================================

git push

echo.
echo ============================================
echo Готово!
echo ============================================
pause

