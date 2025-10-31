"""
Скрипт для регенерации QR-кодов с новым логотипом
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cert_checker.settings')
django.setup()

from certificates.models import Certificate

def regenerate_qr_codes():
    """Регенерирует QR-коды для всех сертификатов"""
    certificates = Certificate.objects.all()
    total = certificates.count()
    
    print(f"Найдено сертификатов: {total}")
    print("Начинаю регенерацию QR-кодов...")
    
    success_count = 0
    error_count = 0
    
    for i, cert in enumerate(certificates, 1):
        try:
            # Удаляем старый QR-код
            if cert.qr_code:
                old_path = cert.qr_code.path
                if os.path.exists(old_path):
                    os.remove(old_path)
                cert.qr_code = None
            
            # Генерируем новый QR-код с новым логотипом
            if cert._generate_qr_code():
                cert.save(update_fields=['qr_code'])
                success_count += 1
                print(f"[{i}/{total}] ✓ QR-код сгенерирован для: {cert.name}")
            else:
                error_count += 1
                print(f"[{i}/{total}] ✗ Ошибка генерации для: {cert.name}")
                
        except Exception as e:
            error_count += 1
            print(f"[{i}/{total}] ✗ Ошибка для {cert.name}: {e}")
    
    print("\n" + "="*60)
    print(f"Регенерация завершена!")
    print(f"Успешно: {success_count}")
    print(f"Ошибок: {error_count}")
    print("="*60)

if __name__ == "__main__":
    regenerate_qr_codes()

