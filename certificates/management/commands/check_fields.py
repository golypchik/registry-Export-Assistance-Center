from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = 'Проверка полей в таблице certificates_certificate'

    def handle(self, *args, **options):
        with connection.cursor() as cursor:
            cursor.execute("PRAGMA table_info(certificates_certificate)")
            columns = cursor.fetchall()
            
            self.stdout.write("Столбцы таблицы certificates_certificate:")
            self.stdout.write("-" * 80)
            for col in columns:
                self.stdout.write(f"Name: {col[1]}, Type: {col[2]}")
            
            field_names = [col[1] for col in columns]
            self.stdout.write("\n" + "=" * 80)
            self.stdout.write("Проверка полей:")
            self.stdout.write("=" * 80)
            
            fields_to_check = ['file1', 'file2', 'auditor_certificate', 'file3', 'file1_psd', 'file2_psd']
            for field in fields_to_check:
                status = "✓ ЕСТЬ" if field in field_names else "✗ НЕТ"
                self.stdout.write(f"{status}: {field}")


