# Data migration to move existing iso_standard data to new many-to-many relationship

from django.db import migrations


def migrate_iso_standards_forward(apps, schema_editor):
    """
    Миграция данных из старого поля iso_standard в новую связь many-to-many
    """
    Certificate = apps.get_model('certificates', 'Certificate')
    CertificateISOStandard = apps.get_model('certificates', 'CertificateISOStandard')
    
    for certificate in Certificate.objects.all():
        if certificate.iso_standard_id:
            # Создаем связь в промежуточной таблице
            CertificateISOStandard.objects.get_or_create(
                certificate=certificate,
                iso_standard_id=certificate.iso_standard_id,
                defaults={'order': 0}
            )
            print(f"Мигрирован сертификат {certificate.id}: {certificate.name}")


def migrate_iso_standards_backward(apps, schema_editor):
    """
    Обратная миграция - восстанавливаем первый стандарт в старое поле
    """
    Certificate = apps.get_model('certificates', 'Certificate')
    CertificateISOStandard = apps.get_model('certificates', 'CertificateISOStandard')
    
    for certificate in Certificate.objects.all():
        # Берем первый стандарт (с наименьшим order)
        first_cert_std = CertificateISOStandard.objects.filter(
            certificate=certificate
        ).order_by('order').first()
        
        if first_cert_std:
            certificate.iso_standard = first_cert_std.iso_standard
            certificate.save(update_fields=['iso_standard'])


class Migration(migrations.Migration):

    dependencies = [
        ('certificates', '0028_add_multiple_iso_standards'),
    ]

    operations = [
        migrations.RunPython(migrate_iso_standards_forward, migrate_iso_standards_backward),
    ]

