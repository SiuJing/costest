from django.contrib import admin
from .models import (
    MaterialPrice, LabourRate, UserProfile, Project, ProjectItem,
    Forecast, Report, ActualItem, InflationRate
)

@admin.register(MaterialPrice)
class MaterialPriceAdmin(admin.ModelAdmin):
    list_display = ('quarter', 'year', 'section', 'sn', 'description', 'rate', 'unit')
    search_fields = ('section', 'description')
    list_filter = ('quarter', 'year', 'section')
    list_per_page = 20

@admin.register(LabourRate)
class LabourRateAdmin(admin.ModelAdmin):
    list_display = ('quarter', 'year', 'section', 'sn', 'description', 'rate', 'unit')
    search_fields = ('section', 'description')
    list_filter = ('quarter', 'year', 'section')
    list_per_page = 20

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

# Customize admin site
admin.site.site_header = "CostEst Pro Administration"
admin.site.site_title = "CostEst Pro"
admin.site.index_title = "Dashboard"