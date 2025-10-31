# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('certificates', '0023_add_generated_images'),
    ]

    operations = [
        # Удаляем PSD поля из Certificate
        migrations.RemoveField(
            model_name='certificate',
            name='file1_psd',
        ),
        migrations.RemoveField(
            model_name='certificate',
            name='file2_psd',
        ),
        migrations.RemoveField(
            model_name='certificate',
            name='clear_file1_psd',
        ),
        migrations.RemoveField(
            model_name='certificate',
            name='clear_file2_psd',
        ),
        migrations.RemoveField(
            model_name='certificate',
            name='clear_file3',
        ),
        
        # Переименовываем file3 в auditor_certificate
        migrations.RenameField(
            model_name='certificate',
            old_name='file3',
            new_name='auditor_certificate',
        ),
        
        # Добавляем поле для очистки auditor_certificate
        migrations.AddField(
            model_name='certificate',
            name='clear_auditor_certificate',
            field=models.BooleanField(default=False),
        ),
        
        # Удаляем PSD поле из Auditor
        migrations.RemoveField(
            model_name='auditor',
            name='audit_file_psd',
        ),
    ]


