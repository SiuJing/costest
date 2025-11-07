from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from decimal import Decimal
from django.utils import timezone
from django.core.files.uploadedfile import InMemoryUploadedFile
from PIL import Image
import io
import decimal


class MaterialPrice(models.Model):
    quarter = models.CharField(max_length=10)
    year = models.IntegerField()
    section = models.CharField(max_length=100)
    sn = models.IntegerField()
    description = models.CharField(max_length=255, blank=True, null=True)
    rate = models.DecimalField(max_digits=10, decimal_places=2)
    unit = models.CharField(max_length=20)
    remarks = models.TextField(blank=True, null=True)

    class Meta:
        unique_together = ('quarter', 'year', 'section', 'sn', 'description')

    def __str__(self):
        return f"{self.section} - {self.description} ({self.quarter} {self.year})"

    @staticmethod
    def next_quarter():
        latest = MaterialPrice.objects.order_by('-year', '-quarter').first()
        if not latest:
            return 'Q1', 2025
        q, y = latest.quarter, latest.year
        if q == 'Q4':
            return 'Q1', y + 1
        return f"Q{int(q[1:]) + 1}", y


class LabourRate(models.Model):
    quarter = models.CharField(max_length=10)
    year = models.IntegerField()
    section = models.CharField(max_length=100)
    sn = models.IntegerField()
    description = models.CharField(max_length=255, blank=True, null=True)
    rate = models.DecimalField(max_digits=10, decimal_places=2)
    unit = models.CharField(max_length=20)
    remarks = models.TextField(blank=True, null=True)

    class Meta:
        unique_together = ('quarter', 'year', 'section', 'sn', 'description')

    def __str__(self):
        return f"{self.section} - {self.description} ({self.quarter} {self.year})"

    @staticmethod
    def next_quarter():
        latest = LabourRate.objects.order_by('-year', '-quarter').first()
        if not latest:
            return 'Q1', 2025
        q, y = latest.quarter, latest.year
        if q == 'Q4':
            return 'Q1', y + 1
        return f"Q{int(q[1:]) + 1}", y
    

class UserProfile(models.Model):
    ROLE_CHOICES = [
        ('admin', 'Admin'),
        ('contractor', 'Contractor'),
        ('qs', 'Quantity Surveyor'),
        ('pm', 'Project Manager'),
        ('developer', 'Developer'),
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='contractor')
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    phone = models.CharField(max_length=15, blank=True)
    company = models.CharField(max_length=100, blank=True)

    def save(self, *args, **kwargs):
        if self.avatar:
            img = Image.open(self.avatar)
            if img.height > 300 or img.width > 300:
                img.thumbnail((300, 300))
                buffer = io.BytesIO()
                img.save(buffer, format='WEBP')
                self.avatar = InMemoryUploadedFile(
                    buffer, None, f"{self.user.username}.webp", 'image/webp',
                    buffer.tell(), None
                )
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user.username} ({self.role})"


class Project(models.Model):
    name = models.CharField(max_length=255)
    uploaded_by = models.ForeignKey('UserProfile', on_delete=models.CASCADE)
    upload_date = models.DateTimeField(auto_now_add=True)
    file = models.FileField(upload_to='projects/')
    
    duration_months = models.IntegerField(null=True, blank=True, help_text="Project duration in months")
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    duration_days = models.PositiveIntegerField(null=True, blank=True, help_text="Auto-filled from start/end")
    notes = models.TextField(blank=True)
    details = models.TextField(blank=True)
    person_in_charge = models.CharField(max_length=100, blank=True)

    estimated_cost = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    cidb_cost = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    actual_cost = models.DecimalField(max_digits=15, decimal_places=2, default=0, blank=True, null=True)
    
    inflation_quarter = models.CharField(max_length=10, blank=True, null=True)
    inflation_year = models.IntegerField(blank=True, null=True)
    inflation_multiplier = models.DecimalField(max_digits=5, decimal_places=3, default=Decimal('1.000'))

    def save(self, *args, **kwargs):
        if self.start_date and self.end_date:
            delta = self.end_date - self.start_date
            self.duration_days = max(delta.days, 0)  
        super().save(*args, **kwargs)

    def variance_est_cidb(self):
        return round(self.estimated_cost - self.cidb_cost, 2)

    def variance_actual_est(self):
        if self.actual_cost:
            return round(self.actual_cost - self.estimated_cost, 2)
        return None

    def profitability(self):
        if self.actual_cost and self.estimated_cost:
            return round((self.estimated_cost - self.actual_cost) / self.estimated_cost * 100, 2)
        return None
    
    def variance(self):
        return round(self.estimated_cost - self.cidb_cost, 2)

    def __str__(self):
        return f"{self.name} ({self.uploaded_by.user.username})"


class ProjectItem(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='estimate_items')
    section = models.CharField(max_length=100)
    description = models.CharField(max_length=255)
    quantity = models.DecimalField(max_digits=12, decimal_places=3, validators=[MinValueValidator(0)])
    unit = models.CharField(max_length=20)
    rate = models.DecimalField(max_digits=10, decimal_places=2)
    original_rate = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)  
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    cidb_rate = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    cidb_amount = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)

    def save(self, *args, **kwargs):
        if self.cidb_amount is None:
            self.cidb_amount = Decimal('0')
        if self.amount is None:
            self.amount = Decimal('0')
        if not self.original_rate and self.rate:
            self.original_rate = self.rate
        super().save(*args, **kwargs)
            
    class Meta:
        unique_together = ('project', 'section', 'description')

    def __str__(self):
        return f"{self.section} – {self.description}"


class ActualItem(models.Model):
    project_item = models.OneToOneField(ProjectItem, on_delete=models.CASCADE, related_name='actual')
    quantity_actual = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    rate_actual = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    amount_actual = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)

    def save(self, *args, **kwargs):
        qty = self.quantity_actual if self.quantity_actual is not None else self.project_item.quantity
        rate = self.rate_actual if self.rate_actual is not None else self.project_item.rate
        self.amount_actual = round(qty * rate, 2)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Actual: {self.project_item}"


class Forecast(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, null=True, blank=True)  # ADD THIS FIELD
    material_description = models.CharField(max_length=255)
    model_type = models.CharField(max_length=50, choices=[
        ('linear', 'Linear Regression'),
        ('random_forest', 'Random Forest'),
    ])
    quarter = models.CharField(max_length=10)
    year = models.IntegerField()
    forecasted_price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.material_description} - {self.model_type} ({self.quarter} {self.year})"


class InflationRate(models.Model):  
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    rate = models.DecimalField(max_digits=5, decimal_places=2)   
    applied = models.BooleanField(default=False)
    applied_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.project.name} - {self.rate}%"


class Report(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    generated_by = models.ForeignKey(UserProfile, on_delete=models.SET_NULL, null=True)
    generated_at = models.DateTimeField(auto_now_add=True)
    file_path = models.CharField(max_length=255)
    report_type = models.CharField(max_length=50, choices=[('pdf', 'PDF'), ('excel', 'Excel')])

    def __str__(self):
        return f"{self.project.name} ({self.report_type})"