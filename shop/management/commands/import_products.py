import openpyxl
from django.core.management.base import BaseCommand
from shop.models import Category, Product


class Command(BaseCommand):
    help = 'Import products from Excel file'

    def add_arguments(self, parser):
        parser.add_argument('excel_path', type=str, help='Path to the Excel file')

    def handle(self, *args, **kwargs):
        excel_path = kwargs['excel_path']
        wb = openpyxl.load_workbook(excel_path)
        sheet = wb.active
        count = 0

        for row in sheet.iter_rows(min_row=2, values_only=True):
            category_name, product_name, price = row[0], row[1], row[2]
            if not category_name or not product_name or price is None:
                continue
            category, created = Category.objects.get_or_create(name=str(category_name).strip())
            Product.objects.create(
                category=category,
                name=str(product_name).strip(),
                price=price
            )
            count += 1

        self.stdout.write(self.style.SUCCESS(f'Successfully imported {count} products'))

     