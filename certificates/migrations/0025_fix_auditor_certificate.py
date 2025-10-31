# Generated manually - исправление переименования file3

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('certificates', '0024_remove_psd_fields_rename_file3'),
    ]

    operations = [
        # На случай если переименование не сработало, создаем поле заново
        # Эта операция безопасна - если поле уже существует, она будет пропущена
        migrations.AlterField(
            model_name='certificate',
            name='auditor_certificate',
            field=models.FileField(
                blank=True,
                null=True,
                upload_to='certificates/',
                verbose_name='Сертификат аудитора'
            ),
        ),
    ]


