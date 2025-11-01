# Generated migration for multiple ISO standards support

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('certificates', '0027_add_uploaded_audit_fields'),
    ]

    operations = [
        # Создаем промежуточную модель для связи многие-ко-многим
        migrations.CreateModel(
            name='CertificateISOStandard',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('order', models.PositiveIntegerField(default=0, verbose_name='Порядок отображения')),
                ('certificate', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='certificate_standards', to='certificates.certificate')),
                ('iso_standard', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='certificates.isostandard', verbose_name='Стандарт ISO')),
            ],
            options={
                'verbose_name': 'Стандарт ISO сертификата',
                'verbose_name_plural': 'Стандарты ISO сертификата',
                'ordering': ['order'],
                'unique_together': {('certificate', 'iso_standard')},
            },
        ),
        # Добавляем поле ManyToMany в Certificate
        migrations.AddField(
            model_name='certificate',
            name='iso_standards',
            field=models.ManyToManyField(
                related_name='certificates',
                through='certificates.CertificateISOStandard',
                to='certificates.isostandard',
                verbose_name='Стандарты ISO'
            ),
        ),
        # Изменяем старое поле iso_standard на nullable для обратной совместимости
        migrations.AlterField(
            model_name='certificate',
            name='iso_standard',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to='certificates.isostandard',
                verbose_name='Стандарт ISO (устаревшее)'
            ),
        ),
    ]

