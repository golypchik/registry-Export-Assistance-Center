# Generated manually - добавление полей для ручной загрузки аудиторских сертификатов

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('certificates', '0026_add_uploaded_certificate_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='auditor',
            name='uploaded_audit',
            field=models.ImageField(
                blank=True,
                null=True,
                upload_to='uploaded_audits/',
                verbose_name='Загруженный аудит (без подписей)',
            ),
        ),
        migrations.AddField(
            model_name='auditor',
            name='uploaded_audit_signed',
            field=models.ImageField(
                blank=True,
                null=True,
                upload_to='uploaded_audits/',
                verbose_name='Загруженный аудит (с подписями)',
            ),
        ),
    ]
