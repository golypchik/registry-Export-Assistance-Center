# Шрифты для генерации сертификатов

## Автоматическая установка (для Render/Linux)

Шрифты Liberation Serif будут установлены автоматически через `build.sh`.

## Ручное добавление шрифтов (опционально)

Если хотите использовать шрифты Times New Roman, поместите файлы в эту директорию:

- `LiberationSerif-Regular.ttf` - обычный шрифт
- `LiberationSerif-Bold.ttf` - жирный шрифт

### Скачать Liberation Serif (свободная замена Times New Roman):

https://github.com/liberationfonts/liberation-fonts/releases

### Скачать Times New Roman (если есть лицензия):

Скопируйте из Windows:
- `C:\Windows\Fonts\times.ttf` → `times.ttf`
- `C:\Windows\Fonts\timesbd.ttf` → `timesbd.ttf`

## Приоритет поиска шрифтов

1. Шрифты в `static/fonts/`
2. Системные шрифты Liberation Serif (Linux)
3. Системные шрифты DejaVu Serif (Linux)
4. Windows шрифты Times New Roman
5. Резервный вариант - системный serif шрифт

