
from django import template
from django.urls import reverse
from django.conf import settings
import qrcode
import base64
from io import BytesIO
import logging
import os
from PIL import Image

logger = logging.getLogger(__name__)
register = template.Library()

def create_qr_with_logo_base64(data, logo_path=None, transparent_bg=True):
    """Создает QR-код с логотипом и возвращает в формате base64"""
    try:
        # Создание QR-кода
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_H,  # Высокий уровень коррекции для логотипа
            box_size=10,
            border=4,
        )
        qr.add_data(data)
        qr.make(fit=True)
        
        # Создание изображения QR-кода
        if transparent_bg:
            qr_img = qr.make_image(fill_color="black", back_color=None)
            qr_img = qr_img.convert("RGBA")
            # Делаем белый фон прозрачным
            datas = qr_img.getdata()
            newData = []
            for item in datas:
                if item[0] == 255 and item[1] == 255 and item[2] == 255:  # белый цвет
                    newData.append((255, 255, 255, 0))  # прозрачный
                else:
                    newData.append(item)
            qr_img.putdata(newData)
        else:
            qr_img = qr.make_image(fill_color="black", back_color="white")
            qr_img = qr_img.convert("RGBA")
        
        # Добавление логотипа если указан путь
        if logo_path and os.path.exists(logo_path):
            try:
                logo = Image.open(logo_path)
                logo = logo.convert("RGBA")
                
                # Размер логотипа (не более 30% от размера QR-кода)
                qr_width, qr_height = qr_img.size
                logo_size = min(qr_width, qr_height) // 4
                logo = logo.resize((logo_size, logo_size), Image.Resampling.LANCZOS)
                
                # Создание белого фона для логотипа
                logo_bg = Image.new('RGBA', (logo_size + 20, logo_size + 20), (255, 255, 255, 255))
                logo_bg.paste(logo, (10, 10), logo)
                
                # Позиционирование в центре
                logo_pos = ((qr_width - logo_bg.size[0]) // 2, (qr_height - logo_bg.size[1]) // 2)
                qr_img.paste(logo_bg, logo_pos, logo_bg)
                
            except Exception as e:
                logger.error(f"Не удалось добавить логотип: {str(e)}")

        # Конвертация в base64
        buffer = BytesIO()
        qr_img.save(buffer, format="PNG")
        img_str = base64.b64encode(buffer.getvalue()).decode()
        
        return f"data:image/png;base64,{img_str}"
        
    except Exception as e:
        logger.error(f"Ошибка при создании QR-кода с логотипом: {str(e)}")
        return None

@register.simple_tag
def qr_code_url(certificate_id):
    """Генерирует QR-код с URL сертификата в формате base64"""
    try:
        url = settings.SITE_URL + reverse('certificate_detail', args=[certificate_id])
        logo_path = os.path.join(settings.BASE_DIR, 'certificates', 'static', 'certificates', 'img', 'company_logo.png')
        
        # Попытка создать QR-код с логотипом
        qr_data = create_qr_with_logo_base64(url, logo_path, transparent_bg=True)
        if qr_data:
            return qr_data
        
        # Fallback к обычному QR-коду
        qr = qrcode.QRCode(
            version=1, 
            box_size=10, 
            border=5,
            error_correction=qrcode.constants.ERROR_CORRECT_L
        )
        qr.add_data(url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        img_str = base64.b64encode(buffer.getvalue()).decode()
        
        return f"data:image/png;base64,{img_str}"
    
    except Exception as e:
        logger.error(f"Error generating QR code for certificate {certificate_id}: {str(e)}")
        return ""

@register.simple_tag
def audit_qr_code_url(certificate_id, auditor_id):
    """Генерирует QR-код с URL аудита в формате base64"""
    try:
        url = settings.SITE_URL + reverse('audit_detail', args=[certificate_id, auditor_id])
        logo_path = os.path.join(settings.BASE_DIR, 'certificates', 'static', 'certificates', 'img', 'company_logo.png')
        
        # Попытка создать QR-код с логотипом
        qr_data = create_qr_with_logo_base64(url, logo_path, transparent_bg=True)
        if qr_data:
            return qr_data
        
        # Fallback к обычному QR-коду
        qr = qrcode.QRCode(
            version=1, 
            box_size=10, 
            border=5,
            error_correction=qrcode.constants.ERROR_CORRECT_L
        )
        qr.add_data(url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        img_str = base64.b64encode(buffer.getvalue()).decode()
        
        return f"data:image/png;base64,{img_str}"
    
    except Exception as e:
        logger.error(f"Error generating audit QR code for certificate {certificate_id}, auditor {auditor_id}: {str(e)}")
        return ""

@register.simple_tag
def permission_qr_code_url(certificate_id):
    """Генерирует QR-код с URL разрешения в формате base64"""
    try:
        url = settings.SITE_URL + reverse('permission_detail', args=[certificate_id])
        logo_path = os.path.join(settings.BASE_DIR, 'certificates', 'static', 'certificates', 'img', 'company_logo.png')
        
        # Попытка создать QR-код с логотипом
        qr_data = create_qr_with_logo_base64(url, logo_path, transparent_bg=True)
        if qr_data:
            return qr_data
        
        # Fallback к обычному QR-коду
        qr = qrcode.QRCode(
            version=1, 
            box_size=10, 
            border=5,
            error_correction=qrcode.constants.ERROR_CORRECT_L
        )
        qr.add_data(url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        img_str = base64.b64encode(buffer.getvalue()).decode()
        
        return f"data:image/png;base64,{img_str}"
    
    except Exception as e:
        logger.error(f"Error generating permission QR code for certificate {certificate_id}: {str(e)}")
        return ""

@register.simple_tag
def custom_qr_code(data, size=10, border=5):
    """Генерирует QR-код для произвольных данных"""
    try:
        qr = qrcode.QRCode(
            version=1, 
            box_size=size, 
            border=border,
            error_correction=qrcode.constants.ERROR_CORRECT_L
        )
        qr.add_data(data)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        img_str = base64.b64encode(buffer.getvalue()).decode()
        
        return f"data:image/png;base64,{img_str}"
    
    except Exception as e:
        logger.error(f"Error generating custom QR code for data: {str(e)}")
        return ""

@register.filter
def qr_code_img_tag(certificate_id, css_class=""):
    """Возвращает готовый HTML тег img с QR-кодом"""
    try:
        qr_data = qr_code_url(certificate_id)
        if qr_data:
            return f'<img src="{qr_data}" class="{css_class}" alt="QR код сертификата">'
        return ""
    except Exception as e:
        logger.error(f"Error generating QR code img tag: {str(e)}")
        return ""