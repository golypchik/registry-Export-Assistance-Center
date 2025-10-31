from django.core.management.base import BaseCommand
from certificates.models import Certificate
from certificates.admin import CertificateAdmin
from django.contrib import admin


class Command(BaseCommand):
    help = 'Отладка админки Certificate'

    def handle(self, *args, **options):
        self.stdout.write("=" * 80)
        self.stdout.write("ДИАГНОСТИКА АДМИНКИ CERTIFICATE")
        self.stdout.write("=" * 80)
        
        # 1. Проверка модели
        self.stdout.write("\n1. ПРОВЕРКА МОДЕЛИ:")
        self.stdout.write("-" * 80)
        
        model_fields = [f.name for f in Certificate._meta.get_fields()]
        self.stdout.write(f"Всего полей в модели: {len(model_fields)}")
        
        check_fields = ['file1', 'file2', 'auditor_certificate', 'file3']
        for fname in check_fields:
            exists = fname in model_fields
            symbol = "✓" if exists else "✗"
            self.stdout.write(f"  {symbol} {fname}")
            if exists:
                field = Certificate._meta.get_field(fname)
                self.stdout.write(f"      Тип: {field.get_internal_type()}")
                self.stdout.write(f"      Verbose: {getattr(field, 'verbose_name', 'N/A')}")
        
        # 2. Проверка AdminForm
        self.stdout.write("\n2. ПРОВЕРКА ADMIN FORM:")
        self.stdout.write("-" * 80)
        
        admin_instance = CertificateAdmin(Certificate, admin.site)
        form_class = admin_instance.form
        
        self.stdout.write(f"Form class: {form_class.__name__}")
        
        # Создаем экземпляр формы
        form = form_class()
        form_fields = list(form.fields.keys())
        
        self.stdout.write(f"Всего полей в форме: {len(form_fields)}")
        
        for fname in check_fields:
            exists = fname in form_fields
            symbol = "✓" if exists else "✗"
            self.stdout.write(f"  {symbol} {fname} в форме")
        
        # 3. Проверка fieldsets
        self.stdout.write("\n3. ПРОВЕРКА FIELDSETS:")
        self.stdout.write("-" * 80)
        
        fieldsets = admin_instance.get_fieldsets(None)
        all_fieldset_fields = []
        
        for name, data in fieldsets:
            fields = data.get('fields', ())
            self.stdout.write(f"\nСекция: {name}")
            for field in fields:
                if isinstance(field, (list, tuple)):
                    for f in field:
                        all_fieldset_fields.append(f)
                        self.stdout.write(f"  - {f}")
                else:
                    all_fieldset_fields.append(field)
                    self.stdout.write(f"  - {field}")
        
        self.stdout.write("\nПроверка наличия полей в fieldsets:")
        for fname in check_fields:
            exists = fname in all_fieldset_fields
            symbol = "✓" if exists else "✗"
            self.stdout.write(f"  {symbol} {fname}")
        
        # 4. Проверка readonly_fields
        self.stdout.write("\n4. ПРОВЕРКА READONLY FIELDS:")
        self.stdout.write("-" * 80)
        
        readonly = admin_instance.get_readonly_fields(None)
        self.stdout.write(f"Readonly fields: {readonly}")
        
        for fname in check_fields:
            is_readonly = fname in readonly
            symbol = "⚠" if is_readonly else "✓"
            self.stdout.write(f"  {symbol} {fname} {'(READONLY!)' if is_readonly else ''}")
        
        # 5. Проверка exclude
        self.stdout.write("\n5. ПРОВЕРКА EXCLUDE:")
        self.stdout.write("-" * 80)
        
        exclude = getattr(admin_instance, 'exclude', None) or ()
        self.stdout.write(f"Excluded fields: {exclude}")
        
        for fname in check_fields:
            is_excluded = fname in exclude
            symbol = "✗" if is_excluded else "✓"
            self.stdout.write(f"  {symbol} {fname} {'(EXCLUDED!)' if is_excluded else ''}")
        
        # 6. Проверка базы данных
        self.stdout.write("\n6. ПРОВЕРКА БАЗЫ ДАННЫХ:")
        self.stdout.write("-" * 80)
        
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("PRAGMA table_info(certificates_certificate)")
            columns = cursor.fetchall()
            db_fields = [col[1] for col in columns]
            
            self.stdout.write(f"Всего столбцов в БД: {len(db_fields)}")
            
            for fname in check_fields:
                exists = fname in db_fields
                symbol = "✓" if exists else "✗"
                self.stdout.write(f"  {symbol} {fname} {'в БД' if exists else 'НЕТ В БД!'}")
        
        # 7. Итоговая диагностика
        self.stdout.write("\n" + "=" * 80)
        self.stdout.write("ИТОГИ:")
        self.stdout.write("=" * 80)
        
        auditor_cert_in_model = 'auditor_certificate' in model_fields
        auditor_cert_in_form = 'auditor_certificate' in form_fields
        auditor_cert_in_fieldsets = 'auditor_certificate' in all_fieldset_fields
        auditor_cert_in_db = 'auditor_certificate' in db_fields
        auditor_cert_readonly = 'auditor_certificate' in readonly
        auditor_cert_excluded = 'auditor_certificate' in exclude
        
        self.stdout.write(f"\nПоле 'auditor_certificate':")
        self.stdout.write(f"  ✓ В модели: {auditor_cert_in_model}")
        self.stdout.write(f"  ✓ В БД: {auditor_cert_in_db}")
        self.stdout.write(f"  ✓ В форме: {auditor_cert_in_form}")
        self.stdout.write(f"  ✓ В fieldsets: {auditor_cert_in_fieldsets}")
        self.stdout.write(f"  ✗ Readonly: {auditor_cert_readonly}")
        self.stdout.write(f"  ✗ Excluded: {auditor_cert_excluded}")
        
        if not auditor_cert_in_db:
            self.stdout.write("\n⚠️ ПРОБЛЕМА: Поле отсутствует в БД! Выполните миграцию:")
            self.stdout.write("  python manage.py migrate certificates")
        elif auditor_cert_excluded:
            self.stdout.write("\n⚠️ ПРОБЛЕМА: Поле в exclude! Уберите из exclude в admin.py")
        elif auditor_cert_readonly and not auditor_cert_in_fieldsets:
            self.stdout.write("\n⚠️ ПРОБЛЕМА: Поле readonly но не в fieldsets!")
        elif not auditor_cert_in_form:
            self.stdout.write("\n⚠️ ПРОБЛЕМА: Поле отсутствует в форме!")
        elif not auditor_cert_in_fieldsets:
            self.stdout.write("\n⚠️ ПРОБЛЕМА: Поле отсутствует в fieldsets!")
        else:
            self.stdout.write("\n✅ Все проверки пройдены! Поле должно отображаться.")
            self.stdout.write("\nЕсли поле все еще не видно:")
            self.stdout.write("  1. Очистите кэш браузера (Ctrl+Shift+Del)")
            self.stdout.write("  2. Перезапустите сервер")
            self.stdout.write("  3. Обновите страницу с Ctrl+F5")


