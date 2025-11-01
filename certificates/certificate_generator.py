"""
Модуль для автоматической генерации изображений сертификатов
"""
import os
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime
from django.conf import settings
from django.core.files.base import ContentFile
from io import BytesIO
import logging

logger = logging.getLogger(__name__)


def hex_to_rgb(hex_color):
    """Конвертирует hex цвет в RGB"""
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


def format_date(date_obj):
    """Форматирует дату в формат DD.MM.YYYY"""
    try:
        if isinstance(date_obj, str):
            date_obj = datetime.strptime(date_obj, '%Y-%m-%d').date()
        return date_obj.strftime('%d.%m.%Y')
    except Exception as e:
        logger.error(f"Ошибка форматирования даты: {e}")
        return str(date_obj)


def get_font(size, bold=False):
    """Получает шрифт Times New Roman или его аналог"""
    # Список путей к шрифтам для поиска (в порядке приоритета)
    font_paths = []
    
    if bold:
        font_paths = [
            # Пользовательские шрифты в проекте
            os.path.join(settings.BASE_DIR, 'static', 'fonts', 'LiberationSerif-Bold.ttf'),
            os.path.join(settings.BASE_DIR, 'static', 'fonts', 'timesbd.ttf'),
            # Windows
            "C:/Windows/Fonts/timesbd.ttf",
            "timesbd.ttf",
            # Linux системные шрифты
            "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSerif-Bold.ttf",
        ]
    else:
        font_paths = [
            # Пользовательские шрифты в проекте
            os.path.join(settings.BASE_DIR, 'static', 'fonts', 'LiberationSerif-Regular.ttf'),
            os.path.join(settings.BASE_DIR, 'static', 'fonts', 'times.ttf'),
            # Windows
            "C:/Windows/Fonts/times.ttf",
            "times.ttf",
            # Linux системные шрифты
            "/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSerif-Regular.ttf",
        ]
    
    # Пробуем загрузить шрифты по очереди
    for font_path in font_paths:
        try:
            font = ImageFont.truetype(font_path, size)
            logger.info(f"Успешно загружен шрифт: {font_path}")
            return font
        except Exception:
            continue
    
    # Если ничего не найдено, логируем ошибку
    logger.error(f"КРИТИЧНО: Не найден ни один подходящий шрифт! Размер: {size}, Bold: {bold}")
    logger.error("Пожалуйста, установите Liberation Serif или Times New Roman")
    logger.error("Для Linux: установите пакет fonts-liberation")
    logger.error("Для Windows: запустите copy_fonts_windows.bat")
    
    # Последняя надежда - дефолтный шрифт PIL (очень маленький и некрасивый)
    logger.warning("Используется дефолтный шрифт PIL - качество будет низким!")
    return ImageFont.load_default()


def draw_text_in_box(draw, text, x, y, width, height, font, color, align='center', valign='top'):
    """
    Рисует текст в заданной области с автоматическим переносом
    align: 'left', 'center', 'right'
    valign: 'top', 'center', 'bottom'
    
    Возвращает фактическую высоту отрисованного текста
    """
    # Разбиваем текст на строки
    lines = []
    words = text.split()
    current_line = ""
    
    for word in words:
        test_line = current_line + word + " "
        bbox = draw.textbbox((0, 0), test_line, font=font)
        text_width = bbox[2] - bbox[0]
        
        if text_width <= width:
            current_line = test_line
        else:
            if current_line:
                lines.append(current_line.strip())
                current_line = word + " "
            else:
                # Слово слишком длинное, но все равно добавляем
                lines.append(word)
                current_line = ""
    
    if current_line:
        lines.append(current_line.strip())
    
    # Вычисляем высоту текста
    line_height = font.size + 10  # Добавляем межстрочный интервал
    total_height = len(lines) * line_height
    
    # Определяем начальную позицию Y с учетом вертикального выравнивания
    if valign == 'center':
        start_y = y + (height - total_height) // 2
    elif valign == 'bottom':
        start_y = y + height - total_height
    else:  # top
        start_y = y
    
    # Рисуем каждую строку
    current_y = start_y
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        text_width = bbox[2] - bbox[0]
        
        if align == 'center':
            line_x = x + (width - text_width) // 2
        elif align == 'right':
            line_x = x + width - text_width
        else:  # left
            line_x = x
        
        draw.text((line_x, current_y), line, font=font, fill=color)
        current_y += line_height
    
    # Возвращаем фактическую высоту отрисованного текста
    return total_height


def draw_iso_standards_column(draw, certificate, x, y, width, height, font, color, align='center', valign='top'):
    """
    Рисует несколько ISO стандартов столбиком (каждый с новой строки)
    
    Возвращает фактическую высоту отрисованного текста
    """
    iso_standards = certificate.get_all_iso_standards()
    
    # Если нет новых стандартов, используем старое поле для обратной совместимости
    if not iso_standards and certificate.iso_standard:
        iso_standards = [certificate.iso_standard]
    
    if not iso_standards:
        # Если совсем нет стандартов, используем iso_standard_name
        if certificate.iso_standard_name:
            return draw_text_in_box(draw, certificate.iso_standard_name, x, y, width, height, 
                                   font, color, align, valign)
        return 0
    
    # Получаем названия всех стандартов
    standard_names = [std.certificate_standard_name for std in iso_standards]
    
    # Объединяем в одну строку с переносами
    combined_text = '\n'.join(standard_names)
    
    # Разбиваем по переносам строк для корректной отрисовки
    lines = []
    for standard_name in standard_names:
        # Каждый стандарт может сам переноситься, если слишком длинный
        words = standard_name.split()
        current_line = ""
        
        for word in words:
            test_line = current_line + word + " "
            bbox = draw.textbbox((0, 0), test_line, font=font)
            text_width = bbox[2] - bbox[0]
            
            if text_width <= width:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line.strip())
                    current_line = word + " "
                else:
                    lines.append(word)
                    current_line = ""
        
        if current_line:
            lines.append(current_line.strip())
    
    # Вычисляем высоту текста
    line_height = font.size + 10  # Межстрочный интервал
    total_height = len(lines) * line_height
    
    # Определяем начальную позицию Y с учетом вертикального выравнивания
    if valign == 'center':
        start_y = y + (height - total_height) // 2
    elif valign == 'bottom':
        start_y = y + height - total_height
    else:  # top
        start_y = y
    
    # Рисуем каждую строку
    current_y = start_y
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        text_width = bbox[2] - bbox[0]
        
        if align == 'center':
            line_x = x + (width - text_width) // 2
        elif align == 'right':
            line_x = x + width - text_width
        else:  # left
            line_x = x
        
        draw.text((line_x, current_y), line, font=font, fill=color)
        current_y += line_height
    
    return total_height


def get_background_path(filename):
    """Получает путь к файлу фона"""
    return os.path.join(settings.BASE_DIR, 'templates', 'background', filename)


def generate_audit_certificate(certificate, auditor, with_signatures=False):
    """Генерирует сертификат аудитора"""
    try:
        # Открываем фоновое изображение
        bg_path = get_background_path('aud.png')
        if not os.path.exists(bg_path):
            logger.error(f"Не найден фон для аудита: {bg_path}")
            return None
            
        bg = Image.open(bg_path)
        draw = ImageDraw.Draw(bg)
        
        # 0. ФИО аудитора
        font = get_font(63, bold=True)
        color = hex_to_rgb('7f1b18')
        draw_text_in_box(draw, auditor.full_name.upper(), 340, 1738, 2012, 200, 
                         font, color, align='center', valign='top')
        
        # 1. Номер аудита
        font = get_font(63, bold=True)
        color = hex_to_rgb('8d8c8c')
        draw_text_in_box(draw, auditor.audit_number, 340, 864, 1200, 72, 
                         font, color, align='left', valign='top')
        
        # 2. ISO стандарты (может быть несколько, отображаются столбиком)
        font = get_font(63, bold=True)
        color = hex_to_rgb('000000')
        draw_iso_standards_column(draw, certificate, 340, 2051, 2012, 300, 
                                 font, color, align='center', valign='top')
        
        # 3. Дата (только дата начала, в правом поле)
        font = get_font(63, bold=False)
        color = hex_to_rgb('851814')
        start_date = format_date(certificate.start_date)
        draw_text_in_box(draw, start_date, 2007, 2740, 341, 72, 
                         font, color, align='center', valign='top')
        
        # 5. QR код
        if certificate.qr_code and os.path.exists(certificate.qr_code.path):
            qr = Image.open(certificate.qr_code.path)
            # Уменьшаем размер QR-кода в 1.5 раза
            new_size = (int(qr.width / 1.5), int(qr.height / 1.5))
            qr = qr.resize(new_size, Image.Resampling.LANCZOS)
            bg.paste(qr, (2053, 756), qr if qr.mode == 'RGBA' else None)
        
        # Добавляем подписи и печать, если требуется
        if with_signatures:
            # 1. Печать
            stamp_path = get_background_path('stamp.png')
            if os.path.exists(stamp_path):
                stamp = Image.open(stamp_path)
                bg.paste(stamp, (1614, 2669), stamp if stamp.mode == 'RGBA' else None)
            
            # 2. Подпись первая
            per_path = get_background_path('per.png')
            if os.path.exists(per_path):
                per = Image.open(per_path)
                bg.paste(per, (1705, 2930), per if per.mode == 'RGBA' else None)
            
            # 3. Подпись руководителя
            ruk_path = get_background_path('ruk.png')
            if os.path.exists(ruk_path):
                ruk = Image.open(ruk_path)
                bg.paste(ruk, (1709, 3087), ruk if ruk.mode == 'RGBA' else None)
        
        # Сохраняем результат в BytesIO
        buffer = BytesIO()
        bg.save(buffer, format='PNG')
        buffer.seek(0)
        
        logger.info(f"Аудит сгенерирован для {auditor.full_name} {'с подписями' if with_signatures else 'без подписей'}")
        return ContentFile(buffer.getvalue())
        
    except Exception as e:
        logger.error(f"Ошибка при генерации аудита: {e}", exc_info=True)
        return None


def generate_main_certificate(certificate, with_signatures=False):
    """Генерирует основной сертификат"""
    try:
        # Открываем фоновое изображение
        bg_path = get_background_path('sert.png')
        if not os.path.exists(bg_path):
            logger.error(f"Не найден фон для сертификата: {bg_path}")
            return None
            
        bg = Image.open(bg_path)
        draw = ImageDraw.Draw(bg)
        
        # 0. Название организации
        font = get_font(63, bold=True)
        color = hex_to_rgb('000000')
        y1 = 1463
        name_height = draw_text_in_box(draw, certificate.name, 340, y1, 2012, 300, 
                         font, color, align='center', valign='top')
        
        # 1. Номер сертификата
        font = get_font(63, bold=True)
        color = hex_to_rgb('8d8c8c')
        draw_text_in_box(draw, certificate.full_certificate_number, 340, 864, 1200, 72, 
                         font, color, align='left', valign='top')
        
        # 2. УНП/ИНН
        font = get_font(43, bold=False)
        color = hex_to_rgb('000000')
        y2 = y1 + name_height + 15  # Вычисляем от фактической высоты названия + отступ
        identifier_text = certificate.display_identifier_label + ' ' + certificate.display_identifier
        identifier_height = draw_text_in_box(draw, identifier_text, 340, y2, 2012, 300, 
                         font, color, align='center', valign='top')
        
        # 3. Адрес
        y3 = y2 + identifier_height + 10  # Вычисляем от фактической высоты идентификатора + отступ
        draw_text_in_box(draw, certificate.address, 340, y3, 2012, 300, 
                         font, color, align='center', valign='top')
        
        # 4. ISO стандарты (может быть несколько, отображаются столбиком)
        font = get_font(63, bold=True)
        draw_iso_standards_column(draw, certificate, 340, 2320, 2012, 300, 
                                 font, color, align='center', valign='top')
        
        # 5. Дата начала
        font = get_font(63, bold=False)
        color = hex_to_rgb('851814')
        start_date = format_date(certificate.start_date)
        draw_text_in_box(draw, start_date, 1380, 2740, 341, 72, 
                         font, color, align='center', valign='top')
        
        # 6. Дата окончания
        expiry_date = format_date(certificate.expiry_date)
        draw_text_in_box(draw, expiry_date, 2007, 2740, 341, 72, 
                         font, color, align='center', valign='top')
        
        # 7. QR код
        if certificate.qr_code and os.path.exists(certificate.qr_code.path):
            qr = Image.open(certificate.qr_code.path)
            # Уменьшаем размер QR-кода в 1.5 раза
            new_size = (int(qr.width / 1.5), int(qr.height / 1.5))
            qr = qr.resize(new_size, Image.Resampling.LANCZOS)
            bg.paste(qr, (2053, 756), qr if qr.mode == 'RGBA' else None)
        
        # 10. Текст того, что удостоверяет сертификат
        font = get_font(43, bold=False)
        color = hex_to_rgb('000000')
        draw_text_in_box(draw, certificate.quality_management_system, 340, 1900, 2012, 350, 
                         font, color, align='center', valign='center')
        
        # Добавляем подписи и печать, если требуется
        if with_signatures:
            # 1. Печать
            stamp_path = get_background_path('stamp.png')
            if os.path.exists(stamp_path):
                stamp = Image.open(stamp_path)
                bg.paste(stamp, (1614, 2669), stamp if stamp.mode == 'RGBA' else None)
            
            # 2. Подпись первая
            per_path = get_background_path('per.png')
            if os.path.exists(per_path):
                per = Image.open(per_path)
                bg.paste(per, (1705, 2930), per if per.mode == 'RGBA' else None)
            
            # 3. Подпись руководителя
            ruk_path = get_background_path('ruk.png')
            if os.path.exists(ruk_path):
                ruk = Image.open(ruk_path)
                bg.paste(ruk, (1709, 3087), ruk if ruk.mode == 'RGBA' else None)
        
        # Сохраняем результат в BytesIO
        buffer = BytesIO()
        bg.save(buffer, format='PNG')
        buffer.seek(0)
        
        logger.info(f"Сертификат сгенерирован для {certificate.name} {'с подписями' if with_signatures else 'без подписей'}")
        return ContentFile(buffer.getvalue())
        
    except Exception as e:
        logger.error(f"Ошибка при генерации сертификата: {e}", exc_info=True)
        return None


def generate_permission_certificate(certificate, with_signatures=False):
    """Генерирует разрешение"""
    try:
        # Открываем фоновое изображение
        bg_path = get_background_path('soot.png')
        if not os.path.exists(bg_path):
            logger.error(f"Не найден фон для разрешения: {bg_path}")
            return None
            
        bg = Image.open(bg_path)
        draw = ImageDraw.Draw(bg)
        
        # 0. Название организации
        font = get_font(63, bold=True)
        color = hex_to_rgb('000000')
        y1 = 1600
        name_height = draw_text_in_box(draw, certificate.name, 340, y1, 2012, 300, 
                         font, color, align='center', valign='top')
        
        # 2. УНП/ИНН
        font = get_font(43, bold=False)
        y2 = y1 + name_height + 15  # Вычисляем от фактической высоты названия + отступ
        identifier_text = certificate.display_identifier_label + ' ' + certificate.display_identifier
        identifier_height = draw_text_in_box(draw, identifier_text, 340, y2, 2012, 300, 
                         font, color, align='center', valign='top')
        
        # 3. Адрес
        y3 = y2 + identifier_height + 10  # Вычисляем от фактической высоты идентификатора + отступ
        draw_text_in_box(draw, certificate.address, 340, y3, 2012, 300, 
                         font, color, align='center', valign='top')
        
        # 7. QR код
        if certificate.qr_code and os.path.exists(certificate.qr_code.path):
            qr = Image.open(certificate.qr_code.path)
            # Уменьшаем размер QR-кода в 1.5 раза
            new_size = (int(qr.width / 1.5), int(qr.height / 1.5))
            qr = qr.resize(new_size, Image.Resampling.LANCZOS)
            bg.paste(qr, (2053, 756), qr if qr.mode == 'RGBA' else None)
        
        # 10. Текст разрешения
        font = get_font(43, bold=False)
        permission_text = f"использование знака соответствия системы менеджмента на период действия сертификата {certificate.full_certificate_number}"
        draw_text_in_box(draw, permission_text, 300, 2060, 2092, 350, 
                         font, color, align='center', valign='top')
        
        # Добавляем подписи и печать, если требуется
        if with_signatures:
            # 1. Печать
            stamp_path = get_background_path('stamp.png')
            if os.path.exists(stamp_path):
                stamp = Image.open(stamp_path)
                bg.paste(stamp, (1614, 2669), stamp if stamp.mode == 'RGBA' else None)
            
            # 2. Подпись первая
            per_path = get_background_path('per.png')
            if os.path.exists(per_path):
                per = Image.open(per_path)
                bg.paste(per, (1705, 2930), per if per.mode == 'RGBA' else None)
        
        # Сохраняем результат в BytesIO
        buffer = BytesIO()
        bg.save(buffer, format='PNG')
        buffer.seek(0)
        
        logger.info(f"Разрешение сгенерировано для {certificate.name} {'с подписями' if with_signatures else 'без подписей'}")
        return ContentFile(buffer.getvalue())
        
    except Exception as e:
        logger.error(f"Ошибка при генерации разрешения: {e}", exc_info=True)
        return None


def generate_all_certificates(certificate):
    """
    Генерирует все 6 изображений для сертификата:
    - Основной сертификат (с подписями и без)
    - Разрешение (с подписями и без)
    - Аудит для каждого аудитора (с подписями и без)
    
    НЕ перезаписывает uploaded файлы (загруженные пользователем вручную)
    """
    logger.info(f"Начало генерации сертификатов для {certificate.name} (ID: {certificate.id})")
    
    # 1. Генерируем основной сертификат без подписей (только если нет uploaded версии)
    if not certificate.uploaded_certificate:
        cert_file = generate_main_certificate(certificate, with_signatures=False)
        if cert_file:
            filename = f'certificate_{certificate.id}.png'
            certificate.generated_certificate.save(filename, cert_file, save=False)
            logger.info(f"Сохранен сертификат без подписей: {filename}")
        else:
            logger.error("Не удалось сгенерировать сертификат без подписей")
    else:
        logger.info(f"Пропуск генерации сертификата без подписей - используется uploaded версия")
    
    # 2. Генерируем основной сертификат с подписями (только если нет uploaded версии)
    if not certificate.uploaded_certificate_signed:
        cert_signed_file = generate_main_certificate(certificate, with_signatures=True)
        if cert_signed_file:
            filename = f'certificate_{certificate.id}_signed.png'
            certificate.generated_certificate_signed.save(filename, cert_signed_file, save=False)
            logger.info(f"Сохранен сертификат с подписями: {filename}")
        else:
            logger.error("Не удалось сгенерировать сертификат с подписями")
    else:
        logger.info(f"Пропуск генерации сертификата с подписями - используется uploaded версия")
    
    # 3. Генерируем разрешение без подписей (только если нет uploaded версии)
    if not certificate.uploaded_permission:
        perm_file = generate_permission_certificate(certificate, with_signatures=False)
        if perm_file:
            filename = f'permission_{certificate.id}.png'
            certificate.generated_permission.save(filename, perm_file, save=False)
            logger.info(f"Сохранено разрешение без подписей: {filename}")
        else:
            logger.error("Не удалось сгенерировать разрешение без подписей")
    else:
        logger.info(f"Пропуск генерации разрешения без подписей - используется uploaded версия")
    
    # 4. Генерируем разрешение с подписями (только если нет uploaded версии)
    if not certificate.uploaded_permission_signed:
        perm_signed_file = generate_permission_certificate(certificate, with_signatures=True)
        if perm_signed_file:
            filename = f'permission_{certificate.id}_signed.png'
            certificate.generated_permission_signed.save(filename, perm_signed_file, save=False)
            logger.info(f"Сохранено разрешение с подписями: {filename}")
        else:
            logger.error("Не удалось сгенерировать разрешение с подписями")
    else:
        logger.info(f"Пропуск генерации разрешения с подписями - используется uploaded версия")
    
    # 5. Генерируем аудиты для каждого аудитора (только если нет uploaded версий)
    for auditor in certificate.auditors.all():
        # Аудит без подписей (только если нет uploaded версии)
        if not auditor.uploaded_audit:
            audit_file = generate_audit_certificate(certificate, auditor, with_signatures=False)
            if audit_file:
                filename = f'audit_{auditor.id}.png'
                auditor.generated_audit.save(filename, audit_file, save=False)
                auditor.save(update_fields=['generated_audit'])
                logger.info(f"Сохранен аудит без подписей для {auditor.full_name}: {filename}")
        else:
            logger.info(f"Пропуск генерации аудита без подписей для {auditor.full_name} - используется uploaded версия")
        
        # Аудит с подписями (только если нет uploaded версии)
        if not auditor.uploaded_audit_signed:
            audit_signed_file = generate_audit_certificate(certificate, auditor, with_signatures=True)
            if audit_signed_file:
                filename = f'audit_{auditor.id}_signed.png'
                auditor.generated_audit_signed.save(filename, audit_signed_file, save=False)
                auditor.save(update_fields=['generated_audit_signed'])
                logger.info(f"Сохранен аудит с подписями для {auditor.full_name}: {filename}")
        else:
            logger.info(f"Пропуск генерации аудита с подписями для {auditor.full_name} - используется uploaded версия")
    
    # Проверяем что поля установлены перед сохранением
    logger.info(f"Проверка полей перед сохранением:")
    logger.info(f"  generated_certificate: {bool(certificate.generated_certificate)}")
    logger.info(f"  generated_certificate_signed: {bool(certificate.generated_certificate_signed)}")
    logger.info(f"  generated_permission: {bool(certificate.generated_permission)}")
    logger.info(f"  generated_permission_signed: {bool(certificate.generated_permission_signed)}")
    
    # Сохраняем сертификат с обновленными полями
    try:
        certificate.save(update_fields=['generated_certificate', 'generated_certificate_signed', 
                                        'generated_permission', 'generated_permission_signed'])
        logger.info("Сертификат успешно сохранен в базу данных")
    except Exception as e:
        logger.error(f"Ошибка при сохранении сертификата: {e}", exc_info=True)
        return False
    
    logger.info(f"Завершена генерация сертификатов для {certificate.name}")
    return True


