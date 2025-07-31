import pandas as pd
from django.core.management.base import BaseCommand, CommandError
from certificates.models import ISOStandard
import os

class Command(BaseCommand):
    help = 'Import ISO standards from Excel file'

    def add_arguments(self, parser):
        parser.add_argument('excel_file', type=str, help='Path to Excel file with ISO standards')

    def handle(self, *args, **options):
        excel_file = options['excel_file']
        
        if not os.path.exists(excel_file):
            raise CommandError(f'File "{excel_file}" does not exist.')

        try:
            # Чтение Excel-файла
            df = pd.read_excel(excel_file, header=0)
            
            # Проверка наличия необходимых столбцов
            required_columns = ['Стандарт ИСО', 'Расшифровка стандарта', 'Нумерация в сертификате', 'Наименование стандарта в сертификате']
            for column in required_columns:
                if column not in df.columns:
                    self.stdout.write(self.style.ERROR(f'В файле отсутствует столбец "{column}"'))
                    self.stdout.write(f'Доступные столбцы: {list(df.columns)}')
                    return
            
            # Счетчики для статистики
            created_count = 0
            updated_count = 0
            error_count = 0
            
            # Обработка строк до первой пустой ячейки в столбце "Стандарт ИСО"
            for index, row in df.iterrows():
                if pd.isna(row['Стандарт ИСО']) or str(row['Стандарт ИСО']).strip() == '':
                    break
                
                try:
                    standard_name = str(row['Стандарт ИСО']).strip()
                    description = str(row['Расшифровка стандарта']).strip() if not pd.isna(row['Расшифровка стандарта']) else ''
                    certificate_number_prefix = str(row['Нумерация в сертификате']).strip() if not pd.isna(row['Нумерация в сертификате']) else ''
                    certificate_standard_name = str(row['Наименование стандарта в сертификате']).strip() if not pd.isna(row['Наименование стандарта в сертификате']) else ''
                    
                    # Проверка наличия стандарта в базе данных
                    standard, created = ISOStandard.objects.update_or_create(
                        standard_name=standard_name,
                        defaults={
                            'description': description,
                            'certificate_number_prefix': certificate_number_prefix,
                            'certificate_standard_name': certificate_standard_name
                        }
                    )
                    
                    if created:
                        created_count += 1
                        self.stdout.write(
                            self.style.SUCCESS(f'Создан: {standard_name}')
                        )
                    else:
                        updated_count += 1
                        self.stdout.write(
                            self.style.WARNING(f'Обновлен: {standard_name}')
                        )
                        
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'Ошибка при обработке строки {index + 2}: {str(e)}'))
                    error_count += 1
            
            # Вывод статистики
            self.stdout.write(
                self.style.SUCCESS(
                    f'Импорт завершен. Создано: {created_count}, обновлено: {updated_count}, ошибок: {error_count}'
                )
            )
            
        except Exception as e:
            raise CommandError(f'Ошибка при чтении файла: {str(e)}')