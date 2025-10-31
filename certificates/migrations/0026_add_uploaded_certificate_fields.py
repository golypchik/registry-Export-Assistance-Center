# Generated manually - добавление полей для ручной загрузки сертификатов

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('certificates', '0025_fix_auditor_certificate'),
    ]

    operations = [
        migrations.AddField(
            model_name='certificate',
            name='uploaded_certificate',
            field=models.ImageField(
                blank=True,
                null=True,
                upload_to='uploaded_certificates/',
                verbose_name='Загруженный сертификат (без подписей)',
            ),
        ),
        migrations.AddField(
            model_name='certificate',
            name='uploaded_certificate_signed',
            field=models.ImageField(
                blank=True,
                null=True,
                upload_to='uploaded_certificates/',
                verbose_name='Загруженный сертификат (с подписями)',
            ),
        ),
        migrations.AddField(
            model_name='certificate',
            name='uploaded_permission',
            field=models.ImageField(
                blank=True,
                null=True,
                upload_to='uploaded_permissions/',
                verbose_name='Загруженное разрешение (без подписей)',
            ),
        ),
        migrations.AddField(
            model_name='certificate',
            name='uploaded_permission_signed',
            field=models.ImageField(
                blank=True,
                null=True,
                upload_to='uploaded_permissions/',
                verbose_name='Загруженное разрешение (с подписями)',
            ),
        ),
    ]

