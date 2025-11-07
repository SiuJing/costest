from django.contrib import admin
from django.urls import path
from django.shortcuts import render, redirect
from django.contrib import messages
from django.core.management import call_command
from django.db import models
import tempfile
import os
from .models import (
    MaterialPrice, LabourRate, UserProfile, Project, ProjectItem,
    Forecast, Report, ActualItem, InflationRate
)
from django.contrib.auth.models import User

@admin.action(description='Import CIDB data from selected files')
def import_cidb_data(modeladmin, request, queryset):
    """Admin action to import CIDB data"""
    try:
        call_command('import_prices', '--auto')
        call_command('train_forecast')
        messages.success(request, "CIDB data imported and forecast models updated successfully!")
    except Exception as e:
        messages.error(request, f"Import failed: {str(e)}")

class CIDBUpload(models.Model):
    """Dummy model for CIDB upload interface"""
    class Meta:
        verbose_name = "CIDB Data Upload"
        verbose_name_plural = "CIDB Data Upload"
        app_label = 'estimator'

    def __str__(self):
        return "CIDB Data Upload"

class CIDBUploadAdmin(admin.ModelAdmin):
    """Custom admin for CIDB data upload"""
    list_display = ('description',)
    
    def description(self, obj):
        return "Upload CIDB Excel Files"
    description.short_description = "Action"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('upload-cidb/', self.admin_site.admin_view(self.upload_cidb_view), name='upload_cidb'),
        ]
        return custom_urls + urls

    def upload_cidb_view(self, request):
        """Handle CIDB file uploads"""
        if request.method == 'POST':
            files = request.FILES.getlist('cidb_files')
            
            if not files:
                messages.error(request, "Please select at least one file to upload.")
                return redirect('admin:upload_cidb')
            
            success_count = 0
            error_files = []
            
            for file in files:
                try:
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp_file:
                        for chunk in file.chunks():
                            tmp_file.write(chunk)
                        tmp_path = tmp_file.name
                    
                    from django.core.management import call_command
                    call_command('import_prices', file=tmp_path)
                    success_count += 1
                    
                    os.unlink(tmp_path)
                    
                except Exception as e:
                    error_files.append(f"{file.name} - {str(e)}")
                    try:
                        os.unlink(tmp_path)
                    except:
                        pass
            
            if success_count > 0:
                messages.success(request, f"Successfully imported {success_count} file(s).")
            
            if error_files:
                messages.error(request, f"Failed to import: {', '.join(error_files)}")
            
            try:
                call_command('train_forecast')
                messages.info(request, "Forecast models updated with new data.")
            except Exception as e:
                messages.warning(request, f"Forecast training failed: {str(e)}")
            
            return redirect('admin:upload_cidb')
        
        material_count = MaterialPrice.objects.count()
        labour_count = LabourRate.objects.count()
        material_quarters = MaterialPrice.objects.values('quarter', 'year').distinct().count()
        labour_quarters = LabourRate.objects.values('quarter', 'year').distinct().count()
        
        context = {
            **self.admin_site.each_context(request),
            'title': 'Upload CIDB Data',
            'material_count': material_count,
            'labour_count': labour_count,
            'material_quarters': material_quarters,
            'labour_quarters': labour_quarters,
            'opts': self.model._meta,
        }
        return render(request, 'admin/upload_cidb.html', context)

    def changelist_view(self, request, extra_context=None):
        """Redirect to upload view when accessing the changelist"""
        return redirect('admin:upload_cidb')

    def has_add_permission(self, request):
        """Prevent adding new instances of the dummy model"""
        return False

    def has_change_permission(self, request, obj=None):
        """Prevent changing instances of the dummy model"""
        return False

    def has_delete_permission(self, request, obj=None):
        """Prevent deleting instances of the dummy model"""
        return False

class CustomUserAdmin(admin.ModelAdmin):
    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if not hasattr(obj, 'userprofile'):
            UserProfile.objects.create(user=obj, role='admin' if obj.is_staff else 'contractor')

@admin.register(MaterialPrice)
class MaterialPriceAdmin(admin.ModelAdmin):
    list_display = ('quarter', 'year', 'section', 'sn', 'description', 'rate', 'unit')
    search_fields = ('section', 'description')
    list_filter = ('quarter', 'year', 'section')
    list_per_page = 20
    actions = [import_cidb_data]

@admin.register(LabourRate)
class LabourRateAdmin(admin.ModelAdmin):
    list_display = ('quarter', 'year', 'section', 'sn', 'description', 'rate', 'unit')
    search_fields = ('section', 'description')
    list_filter = ('quarter', 'year', 'section')
    list_per_page = 20
    actions = [import_cidb_data]

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'company', 'phone')
    list_filter = ('role',)
    search_fields = ('user__username', 'company')

@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('name', 'uploaded_by', 'upload_date', 'estimated_cost', 'cidb_cost', 'actual_cost')
    list_filter = ('upload_date', 'uploaded_by')
    search_fields = ('name', 'uploaded_by__user__username')
    readonly_fields = ('upload_date',)
    list_per_page = 20

@admin.register(ProjectItem)
class ProjectItemAdmin(admin.ModelAdmin):
    list_display = ('project', 'section', 'description', 'quantity', 'rate', 'amount')
    search_fields = ('description', 'project__name')
    list_filter = ('section',)
    list_per_page = 30

@admin.register(Forecast)
class ForecastAdmin(admin.ModelAdmin):
    list_display = ('material_description', 'model_type', 'quarter', 'year', 'forecasted_price', 'project')
    list_filter = ('model_type', 'quarter', 'year', 'project')
    search_fields = ('material_description',)
    list_per_page = 20

@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ('project', 'generated_by', 'generated_at', 'report_type')
    list_filter = ('report_type', 'generated_at')
    readonly_fields = ('generated_at',)

@admin.register(ActualItem)
class ActualItemAdmin(admin.ModelAdmin):
    list_display = ('project_item', 'quantity_actual', 'rate_actual', 'amount_actual')
    search_fields = ('project_item__description',)

@admin.register(InflationRate)
class InflationRateAdmin(admin.ModelAdmin):
    list_display = ('project', 'rate', 'applied', 'applied_at')
    list_filter = ('applied', 'applied_at')

admin.site.register(CIDBUpload, CIDBUploadAdmin)

admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)

admin.site.site_header = "CostEst Pro Administration"
admin.site.site_title = "CostEst Pro"
admin.site.index_title = "Dashboard"