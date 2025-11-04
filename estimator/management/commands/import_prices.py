# estimator/management/commands/import_prices.py
from django.core.management.base import BaseCommand
from estimator.models import MaterialPrice, LabourRate
import pandas as pd
import os
import re
from pathlib import Path

class Command(BaseCommand):
    help = "Import material and labour prices from Excel files"

    def add_arguments(self, parser):
        parser.add_argument('--materials', type=str, help='Path to Excel file for material prices')
        parser.add_argument('--labour', type=str, help='Path to Excel file for labour rates')
        parser.add_argument('--auto', action='store_true', help='Automatically import all Excel files from /data folder')
        parser.add_argument('--force', action='store_true', help='Force re-import of all files')

    def handle(self, *args, **options):
        base_dir = Path('data')
        
        if not base_dir.exists():
            self.stdout.write(self.style.ERROR("Data directory not found!"))
            return

        if options['auto']:
            self.import_all(base_dir, options.get('force', False))
        else:
            if options['materials']:
                self.import_materials(options['materials'])
            if options['labour']:
                self.import_labour(options['labour'])

    def import_all(self, folder, force=False):
        """Detect and import all Excel files in data/"""
        imported_count = 0
        
        for file in os.listdir(folder):
            if file.endswith('.xlsx') or file.endswith('.xls'):
                file_path = folder / file
                
                # Check if we've already imported this file (by checking if any records exist for this quarter/year)
                if not force and self.file_already_imported(file_path):
                    self.stdout.write(f"⏭️  Skipping already imported: {file}")
                    continue
                    
                if re.search(r'Materials', file, re.IGNORECASE):
                    self.stdout.write(f"📘 Importing Material file: {file}")
                    count = self.import_materials(file_path)
                    imported_count += count
                elif re.search(r'Labour', file, re.IGNORECASE):
                    self.stdout.write(f"🧱 Importing Labour file: {file}")
                    count = self.import_labour(file_path)
                    imported_count += count
                else:
                    self.stdout.write(self.style.WARNING(f"⚠️  Skipping unknown file: {file}"))
        
        if imported_count > 0:
            self.stdout.write(self.style.SUCCESS(f"✅ Imported {imported_count} new files"))
        else:
            self.stdout.write("ℹ️  No new files to import")

    def file_already_imported(self, file_path):
        """Check if a file has already been imported by looking at its content"""
        try:
            df = pd.read_excel(file_path)
            if 'Quarter' in df.columns and 'Year' in df.columns:
                quarter = df['Quarter'].iloc[0]
                year = df['Year'].iloc[0]
                
                # Check if we have any records for this quarter/year
                material_exists = MaterialPrice.objects.filter(quarter=quarter, year=year).exists()
                labour_exists = LabourRate.objects.filter(quarter=quarter, year=year).exists()
                
                return material_exists or labour_exists
        except Exception as e:
            self.stdout.write(f"⚠️  Error checking file {file_path}: {e}")
        
        return False

    def import_materials(self, filepath):
        try:
            df = pd.read_excel(filepath)
            count = 0
            for _, row in df.iterrows():
                obj, created = MaterialPrice.objects.update_or_create(
                    quarter=row['Quarter'],
                    year=int(row['Year']),
                    section=row['Section'],
                    sn=int(row['S/N']),
                    description=row['Description'],
                    defaults={
                        'rate': float(row['Rate (RM)']),
                        'unit': row['Unit'],
                        'remarks': row.get('Remarks', '')
                    }
                )
                if created:
                    count += 1
            self.stdout.write(self.style.SUCCESS(f"✅ Imported {count} new MaterialPrice records from {filepath.name}"))
            return 1  # File was processed
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Error importing {filepath}: {e}"))
            return 0

    def import_labour(self, filepath):
        try:
            df = pd.read_excel(filepath)
            count = 0
            for _, row in df.iterrows():
                obj, created = LabourRate.objects.update_or_create(
                    quarter=row['Quarter'],
                    year=int(row['Year']),
                    section=row['Section'],
                    sn=int(row['S/N']),
                    description=row['Description'],
                    defaults={
                        'rate': float(row['Rate (RM)']),
                        'unit': row['Unit'],
                        'remarks': row.get('Remarks', '')
                    }
                )
                if created:
                    count += 1
            self.stdout.write(self.style.SUCCESS(f"✅ Imported {count} new LabourRate records from {filepath.name}"))
            return 1  # File was processed
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Error importing {filepath}: {e}"))
            return 0