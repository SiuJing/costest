from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.management import call_command
from django.db import transaction
from django.db.models import Sum, F, Q
from django.contrib.humanize.templatetags.humanize import intcomma
from estimator.models import Project, Forecast, InflationRate, ProjectItem, ActualItem, UserProfile
from django.contrib.auth.models import User
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordResetForm
from django.contrib.auth.tokens import default_token_generator
from django.template.loader import render_to_string
from django.core.mail import send_mail
from django.conf import settings
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from decimal import Decimal
from django.forms import modelform_factory
import pandas as pd
import decimal
import os
import json
import re
from io import BytesIO
from django.core.paginator import Paginator
from pathlib import Path

from .models import (
    UserProfile, Project, ProjectItem, MaterialPrice, Forecast, ActualItem, LabourRate
)
from .forms import ProjectUploadForm, ProjectEditForm
from .utils import qs_required, admin_or_qs_required


# ----------------------------------------------------------------------
# AUTH
# ----------------------------------------------------------------------
def register_user(request):
    if request.method == "POST":
        username = request.POST['username']
        email = request.POST.get('email', '')
        password = request.POST['password']
        role = request.POST['role']

        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already taken.")
            return redirect('register')
        if email and User.objects.filter(email=email).exists():
            messages.error(request, "Email already registered.")
            return redirect('register')

        user = User.objects.create_user(username=username, email=email, password=password)
        UserProfile.objects.create(user=user, role=role)
        messages.success(request, "Registration successful – please log in.")
        return redirect('login')
    return render(request, 'estimator/register.html')

def login_user(request):
    if request.method == "POST":
        user = authenticate(request, username=request.POST['username'], password=request.POST['password'])
        if user:
            login(request, user)
            return redirect('dashboard')
        messages.error(request, "Invalid credentials.")
    return render(request, 'estimator/login.html')

@login_required
def logout_user(request):
    logout(request)
    messages.info(request, "Logged out.")
    return redirect('login')

# ----------------------------------------------------------------------
# PROFILE
# ----------------------------------------------------------------------
@login_required
def profile(request):
    profile, created = UserProfile.objects.get_or_create(user=request.user)
    if created:
        if request.user.is_staff and not profile.role:
            profile.role = 'admin'
            profile.save()
    
    if request.method == 'POST':
        profile.phone = request.POST.get('phone', '')
        profile.company = request.POST.get('company', '')
        if 'avatar' in request.FILES:
            profile.avatar = request.FILES['avatar']
        profile.save()
        messages.success(request, "Profile updated.")
        return redirect('profile')
    return render(request, 'estimator/profile.html', {'profile': profile})


# ------------------------------------------------------------------
# DASHBOARD - FIXED WITH SAFE PROFILE ACCESS
# ------------------------------------------------------------------
@login_required
def dashboard(request):
    profile, created = UserProfile.objects.get_or_create(user=request.user)
    if created:
        if request.user.is_staff and not profile.role:
            profile.role = 'admin'
            profile.save()
    
    role = profile.role
    
    template_map = {
        'admin': 'estimator/dashboard_admin.html',
        'pm': 'estimator/dashboard_pm.html', 
        'qs': 'estimator/dashboard_user.html',
        'contractor': 'estimator/dashboard_user.html',
        'developer': 'estimator/dashboard_user.html',
    }
    
    print(f"DEBUG: User {request.user.username} has role: {role}")
    print(f"DEBUG: User is staff: {request.user.is_staff}")
    print(f"DEBUG: Template being used: {template_map.get(role, 'estimator/dashboard_user.html')}")

    project_filter = request.GET.get('project', 'all')

    if role in ['qs', 'contractor']:
        all_projects = Project.objects.filter(uploaded_by=profile).order_by('-upload_date')
    else:
        all_projects = Project.objects.all().order_by('-upload_date')

    display_projects = all_projects

    search = request.GET.get('q', '').strip()
    if search:
        display_projects = display_projects.filter(
            Q(name__icontains=search) | Q(estimate_items__description__icontains=search)
        ).distinct()

    est_total = Decimal('0')
    cidb_total = Decimal('0')
    actual_total = Decimal('0')
    total_variance = Decimal('0')
    total_projects = display_projects.count()

    chart_labels = ['Cost Comparison']
    chart_est = []
    chart_cidb = []
    chart_actual = []

    if project_filter == 'all':
        for project in display_projects:
            est_total += project.estimated_cost or Decimal('0')
            cidb_total += project.cidb_cost or Decimal('0')
            actual_total += project.actual_cost or Decimal('0')
        
        total_variance = est_total - cidb_total
        
        chart_est = [float(est_total)]
        chart_cidb = [float(cidb_total)]
        chart_actual = [float(actual_total)]
        
    else:
        try:
            selected_project = display_projects.get(pk=project_filter)
            est_total = selected_project.estimated_cost or Decimal('0')
            cidb_total = selected_project.cidb_cost or Decimal('0')
            actual_total = selected_project.actual_cost or Decimal('0')
            total_variance = est_total - cidb_total
            total_projects = 1

            chart_est = [float(est_total)]
            chart_cidb = [float(cidb_total)]
            chart_actual = [float(actual_total)]
            
        except Project.DoesNotExist:
            project_filter = 'all'
            return redirect('dashboard')

    chart_data = {
        'labels': chart_labels,
        'datasets': [
            {
                'label': 'Estimated Cost',
                'data': chart_est,
                'backgroundColor': '#17a2b8',  # Blue
            },
            {
                'label': 'CIDB Cost', 
                'data': chart_cidb,
                'backgroundColor': '#dc3545',  # Red
            },
            {
                'label': 'Actual Cost',
                'data': chart_actual, 
                'backgroundColor': '#198754',  # Green
            }
        ]
    }

    print(f"Chart data: {chart_data}")
    print(f"Estimated: {chart_est}, CIDB: {chart_cidb}, Actual: {chart_actual}")

    paginator = Paginator(display_projects, 5)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'profile': profile,
        'projects': page_obj,
        'page_obj': page_obj,
        'total_projects': total_projects,
        'est_total': est_total,
        'cidb_total': cidb_total,
        'actual_total': actual_total,
        'total_variance': total_variance,
        'forecast_total': Decimal('0'),
        'can_upload': role in ['qs', 'contractor'],
        'search': search,
        'chart_data': json.dumps(chart_data),
        'project_filter': project_filter,
    }

    if project_filter != 'all':
        context['selected_project'] = selected_project

    template_name = template_map.get(role, 'estimator/dashboard_user.html')
    return render(request, template_name, context)

# ----------------------------------------------------------------------
# CIDB IMPORT
# ----------------------------------------------------------------------
@login_required
def import_cidb(request):
    if request.user.userprofile.role != 'admin':
        messages.error(request, "Only admins can import CIDB data.")
        return redirect('dashboard')

    if request.method == 'POST':
        try:
            call_command('import_prices', '--auto')
            call_command('train_forecast')
            messages.success(request, "CIDB data imported and forecast updated.")
        except Exception as e:
            messages.error(request, f"Import failed: {e}")
        return redirect('dashboard')
    return render(request, 'estimator/import_cidb.html')


# ------------------------------------------------------------------
# CHECK DATA STATUS
# ------------------------------------------------------------------
@login_required
def data_status(request):
    """Show current data status and import new files"""
    material_count = MaterialPrice.objects.count()
    labour_count = LabourRate.objects.count()
    
    data_dir = Path('data')
    new_files = []
    if data_dir.exists():
        for file in data_dir.glob('*.xlsx'):
            new_files.append(file.name)
    
    material_quarters = MaterialPrice.objects.values('quarter', 'year').distinct().order_by('-year', '-quarter')
    labour_quarters = LabourRate.objects.values('quarter', 'year').distinct().order_by('-year', '-quarter')
    
    context = {
        'material_count': material_count,
        'labour_count': labour_count,
        'new_files': new_files,
        'material_quarters': material_quarters,
        'labour_quarters': labour_quarters,
        'total_quarters': material_quarters.count(),
    }
    return render(request, 'estimator/data_status.html', context)

# ------------------------------------------------------------------
# FORCE IMPORT DATA
# ------------------------------------------------------------------
@login_required
def force_import_data(request):
    """Force import of all data files"""
    if request.user.userprofile.role != 'admin':
        messages.error(request, "Only admins can import data.")
        return redirect('dashboard')
    
    try:
        from django.core.management import call_command
        call_command('import_prices', '--auto', '--force')
        messages.success(request, "Data import completed successfully!")
    except Exception as e:
        messages.error(request, f"Import failed: {e}")
    
    return redirect('data_status')


# ----------------------------------------------------------------------
# PROJECT UPLOAD - NEW DEDICATED PAGE
# ----------------------------------------------------------------------
@login_required
def upload_project(request):
    if request.user.userprofile.role not in ['qs', 'contractor']:
        return redirect('dashboard')

    if request.method == 'POST':
        form = ProjectUploadForm(request.POST, request.FILES)
        if form.is_valid():
            project = form.save(commit=False)
            project.uploaded_by = request.user.userprofile
            
            if project.start_date and project.end_date:
                if project.end_date < project.start_date:
                    messages.error(request, "End date cannot be before start date.")
                    return render(request, 'estimator/upload_project.html', {'form': form})
                delta = project.end_date - project.start_date
                project.duration_days = max(delta.days, 0)
            
            project.save()

            try:
                df = pd.read_excel(request.FILES['file'])
                total_est = total_cidb = Decimal('0')
                
                for _, row in df.iterrows():
                    desc = str(row['Description']).strip()
                    section = str(row['Section']).strip()
                    qty = Decimal(str(row['Quantity']))
                    rate = Decimal(str(row['Rate (RM)']))
                    amount = Decimal(str(row['Amount (RM)']))

                    cidb = MaterialPrice.objects.filter(section=section, description__iexact=desc).order_by('-year', '-quarter').first()
                    cidb_rate = cidb.rate * project.inflation_multiplier if cidb else Decimal('0')
                    cidb_amount = qty * cidb_rate

                    ProjectItem.objects.create(
                        project=project, section=section, description=desc, quantity=qty, 
                        unit=str(row['Unit']).strip(), rate=rate, amount=amount, 
                        cidb_rate=cidb_rate, cidb_amount=cidb_amount
                    )
                    total_est += amount
                    if cidb_amount:
                        total_cidb += cidb_amount

                project.estimated_cost = total_est
                project.cidb_cost = total_cidb
                project.actual_cost = Decimal('0')
                project.save()
                
                messages.success(request, f"Project '{project.name}' uploaded successfully.")
                return redirect('project_detail', pk=project.pk)
                
            except Exception as e:
                project.delete()
                messages.error(request, f"Error processing Excel file: {e}")
                return redirect('upload_project')
    else:
        form = ProjectUploadForm()
    
    return render(request, 'estimator/upload_project.html', {'form': form})


# ------------------------------------------------------------------
# EDIT PROJECT DETAILS (duration, dates, notes)
# ------------------------------------------------------------------
@login_required
def project_edit(request, pk):
    project = get_object_or_404(Project, pk=pk)
    
    if request.user.userprofile != project.uploaded_by and request.user.userprofile.role not in ['admin', 'pm']:
        messages.error(request, "You can only edit your own projects.")
        return redirect('dashboard')

    if request.method == 'POST':
        form = ProjectEditForm(request.POST, request.FILES, instance=project)
        if form.is_valid():
            form.save()
            messages.success(request, "Project updated successfully.")
            return redirect('project_detail', pk=pk)
    else:
        form = ProjectEditForm(instance=project)

    return render(request, 'estimator/project_edit.html', {
        'form': form,
        'project': project
    })


# ----------------------------------------------------------------------
# ACTUAL COST UPLOAD
# ----------------------------------------------------------------------
@login_required
def upload_actual_cost(request, pk):
    project = get_object_or_404(Project, pk=pk)
    if request.user.userprofile.role not in ['pm', 'developer']:
        messages.error(request, "Only PM/Developer can upload actual cost.")
        return redirect('project_detail', pk=pk)

    if request.method == 'POST':
        file = request.FILES.get('file')
        if file:
            project.actual_file = file
            df = pd.read_excel(file)
            total = df['Amount (RM)'].sum()
            project.actual_cost = Decimal(str(total))
            project.save()
            messages.success(request, f"Actual cost: RM {total:,.2f}")
        return redirect('project_detail', pk=pk)
    return render(request, 'estimator/upload_actual.html', {'project': project})


# ----------------------------------------------------------------------
# EDIT ACTUALS
# ----------------------------------------------------------------------
@login_required
@qs_required
def edit_actuals(request, pk):
    project = get_object_or_404(Project, pk=pk)
    items = ProjectItem.objects.filter(project=project)

    actuals_qs = ActualItem.objects.filter(project_item__project=project)
    actuals_dict = {a.project_item_id: a for a in actuals_qs}

    if request.method == 'POST':
        for item in items:
            qty_key = f'item_{item.id}_qty'
            rate_key = f'item_{item.id}_rate'
            qty_str = request.POST.get(qty_key, '').strip()
            rate_str = request.POST.get(rate_key, '').strip()

            try:
                qty = Decimal(qty_str) if qty_str else None
                rate = Decimal(rate_str) if rate_str else None
            except decimal.InvalidOperation:
                messages.error(request, f"Invalid number for item {item.description}.")
                continue

            ActualItem.objects.update_or_create(
                project_item=item,
                defaults={
                    'quantity_actual': qty,
                    'rate_actual': rate,
                }
            )

        total = Decimal('0')
        for actual in ActualItem.objects.filter(project_item__project=project):
            actual.save()  
            total += actual.amount_actual or 0

        project.actual_cost = total
        project.save()

        messages.success(request, "Actual costs updated.")
        return redirect('project_detail', pk=pk)

    context = {
        'project': project,
        'items': items,
        'actuals_dict': actuals_dict,  
    }
    return render(request, 'estimator/edit_actuals.html', context)


# ----------------------------------------------------------------------
# PROJECT DETAIL - UPDATED WITH INFLATION
# ----------------------------------------------------------------------
@login_required
def project_detail(request, pk):
    project = get_object_or_404(Project, pk=pk)
    items = ProjectItem.objects.filter(project=project).order_by('section')

    inflation = InflationRate.objects.filter(project=project, applied=True).first()

    if request.method == 'POST':
        if 'apply_inflation' in request.POST:
            rate = Decimal(request.POST['inflation_rate'])
            InflationRate.objects.filter(project=project).delete()
            InflationRate.objects.create(project=project, rate=rate, applied=True,
                                         applied_at=timezone.now())
            total_est = Decimal('0')
            for item in items:
                if item.original_rate:  
                    new_rate = item.original_rate * (1 + rate/100)
                else:
                    new_rate = item.rate * (1 + rate/100)
                    item.original_rate = item.rate  
                
                item.rate = new_rate
                item.amount = item.quantity * new_rate
                item.save()
                total_est += item.amount
            
            project.estimated_cost = total_est
            project.save()
            
            messages.success(request, f"Inflation of {rate}% applied successfully.")
            return redirect('project_detail', pk=pk)

        if 'revert_inflation' in request.POST:
            InflationRate.objects.filter(project=project).delete()
            total_est = Decimal('0')
            for item in items:
                if item.original_rate:
                    item.rate = item.original_rate
                    item.amount = item.quantity * item.rate
                    item.save()
                    total_est += item.amount
            
            project.estimated_cost = total_est
            project.save()
            
            messages.success(request, "Inflation reverted successfully.")
            return redirect('project_detail', pk=pk)

    breakdown = []
    total_est = total_cidb = total_variance = decimal.Decimal('0')
    original_total_est = decimal.Decimal('0')

    for itm in items:
        est = decimal.Decimal(itm.quantity) * decimal.Decimal(itm.rate)
        original_est = decimal.Decimal(itm.quantity) * decimal.Decimal(itm.original_rate or itm.rate)
        cidb = decimal.Decimal(itm.quantity) * decimal.Decimal(itm.cidb_rate or 0)
        var = est - cidb

        try:
            actual = itm.actual
        except ActualItem.DoesNotExist:
            actual = None

        breakdown.append({
            'item': itm,
            'est_cost': est,
            'original_est_cost': original_est,
            'cidb_cost': cidb,
            'variance': var,
            'actual': actual,
        })

        total_est += est
        original_total_est += original_est
        total_cidb += cidb
        total_variance += var

    actual_total = project.actual_cost or decimal.Decimal('0')

    breakdown_chart_data = {
        'labels': ['Costs'],
        'datasets': [
            {'label': 'Estimated Cost (Original)', 'data': [float(original_total_est)], 'backgroundColor': '#17a2b8'},
            {'label': 'CIDB Cost', 'data': [float(total_cidb)], 'backgroundColor': '#dc3545'},
        ]
    }

    inflation_chart_data = {
        'labels': ['Costs'],
        'datasets': [
            {'label': 'Estimated Cost (Inflated)', 'data': [float(total_est)], 'backgroundColor': '#17a2b8'},
            {'label': 'CIDB Cost', 'data': [float(total_cidb)], 'backgroundColor': '#dc3545'},
        ]
    }

    actuals_chart_data = {
        'labels': ['Costs'],
        'datasets': [
            {'label': 'Estimated Cost (Inflated)', 'data': [float(total_est)], 'backgroundColor': '#17a2b8'},
            {'label': 'Actual Cost', 'data': [float(actual_total)], 'backgroundColor': '#198754'},
        ]
    }

    context = {
        'project': project,
        'breakdown': breakdown,
        'total_est': total_est,
        'original_total_est': original_total_est,
        'total_cidb': total_cidb,
        'total_variance': total_variance,
        'actual_total': actual_total,
        'inflation_rate': inflation.rate if inflation else None,
        'inflation_applied': inflation.applied_at if inflation else None,
        'inflation_applied_at': inflation.applied_at if inflation else None,
        'breakdown_chart_data': json.dumps(breakdown_chart_data),
        'inflation_chart_data': json.dumps(inflation_chart_data),
        'actuals_chart_data': json.dumps(actuals_chart_data),
    }
    return render(request, 'estimator/project_detail.html', context)

# ----------------------------------------------------------------------
# ADJUST INFLATION (legacy - kept for compatibility)
# ----------------------------------------------------------------------
@login_required
@admin_or_qs_required
def adjust_inflation(request, pk):
    project = get_object_or_404(Project, pk=pk)

    if request.method == 'POST':
        try:
            factor = decimal.Decimal(request.POST.get('factor', '1.0'))
            if factor <= 0:
                raise ValueError
        except (ValueError, decimal.InvalidOperation):
            messages.error(request, "Invalid inflation factor.")
            return redirect('project_detail', pk=pk)

        ProjectItem.objects.filter(project=project).update(
            rate=F('rate') * factor,
            amount=F('amount') * factor
        )
        agg = ProjectItem.objects.filter(project=project)\
                                 .aggregate(est=Sum('amount'), cidb=Sum('cidb_amount'))
        project.estimated_cost = agg['est'] or decimal.Decimal('0')
        project.cidb_cost = agg['cidb'] or decimal.Decimal('0')
        project.save()

        messages.success(request, f"Inflation factor {factor} applied.")
        return redirect('project_detail', pk=pk)

    return render(request, 'estimator/adjust_inflation.html', {'project': project})

# ------------------------------------------------------------------
# RUN FORECAST (ML)
# ------------------------------------------------------------------
@login_required
@qs_required
def run_forecast_view(request, pk):
    try:
        from estimator.ml_forecast import run_forecast
        forecast_count = run_forecast(pk)
        messages.success(request, f"Forecast generated successfully! Created {forecast_count} predictions.")
        return redirect('view_forecast', pk=pk)
    except Exception as e:
        messages.error(request, f"Forecast failed: {e}")
        return redirect('project_detail', pk=pk)

# ------------------------------------------------------------------
# VIEW FORECAST RESULTS
# ------------------------------------------------------------------
@login_required
def view_forecast(request, pk):
    project = get_object_or_404(Project, pk=pk)
    
    linear_forecasts = Forecast.objects.filter(project=project, model_type='linear').order_by('material_description')
    rf_forecasts = Forecast.objects.filter(project=project, model_type='random_forest').order_by('material_description')
    
    total_quarters = MaterialPrice.objects.values('quarter', 'year').distinct().count()
    project_items = ProjectItem.objects.filter(project=project)
    
    forecast_analysis = []
    for item in project_items:
        material_historical_count = MaterialPrice.objects.filter(
            description__icontains=item.description
        ).count()
        
        labour_historical_count = LabourRate.objects.filter(
            description__icontains=item.description
        ).count()
        
        total_historical_records = material_historical_count + labour_historical_count
        
        forecast_analysis.append({
            'material': item.description,
            'section': item.section,
            'material_records': material_historical_count,
            'labour_records': labour_historical_count,
            'historical_records': total_historical_records,
            'can_forecast': total_historical_records >= 2,
            'data_source': 'Material' if material_historical_count > labour_historical_count else 'Labour',
            'status': '✅ Ready' if total_historical_records >= 2 else '❌ Need more data'
        })
    
    linear_forecast_data = []
    rf_forecast_data = []
    
    for forecast in linear_forecasts:
        current_material = MaterialPrice.objects.filter(
            description__iexact=forecast.material_description.replace('MATERIAL: ', '').replace('LABOUR: ', '')
        ).order_by('-year', '-quarter').first()
        
        current_labour = LabourRate.objects.filter(
            description__iexact=forecast.material_description.replace('MATERIAL: ', '').replace('LABOUR: ', '')
        ).order_by('-year', '-quarter').first()
        
        if current_material:
            current_rate = current_material.rate
            current_quarter = f"{current_material.quarter} {current_material.year}"
            data_source = 'Material'
        elif current_labour:
            current_rate = current_labour.rate
            current_quarter = f"{current_labour.quarter} {current_labour.year}"
            data_source = 'Labour'
        else:
            current_rate = None
            change = None
            current_quarter = "N/A"
            data_source = "Unknown"
            
        if current_rate:
            change = ((forecast.forecasted_price - current_rate) / current_rate) * 100
        else:
            change = None
            
        linear_forecast_data.append({
            'material': forecast.material_description,
            'model_type': forecast.get_model_type_display(),
            'current_quarter': current_quarter,
            'current_price': current_rate,
            'forecast_quarter': f"{forecast.quarter} {forecast.year}",
            'forecast_price': forecast.forecasted_price,
            'change_percent': change,
            'data_source': data_source,
        })
    
    for forecast in rf_forecasts:
        current_material = MaterialPrice.objects.filter(
            description__iexact=forecast.material_description.replace('MATERIAL: ', '').replace('LABOUR: ', '')
        ).order_by('-year', '-quarter').first()
        
        current_labour = LabourRate.objects.filter(
            description__iexact=forecast.material_description.replace('MATERIAL: ', '').replace('LABOUR: ', '')
        ).order_by('-year', '-quarter').first()
        
        if current_material:
            current_rate = current_material.rate
            current_quarter = f"{current_material.quarter} {current_material.year}"
            data_source = 'Material'
        elif current_labour:
            current_rate = current_labour.rate
            current_quarter = f"{current_labour.quarter} {current_labour.year}"
            data_source = 'Labour'
        else:
            current_rate = None
            change = None
            current_quarter = "N/A"
            data_source = "Unknown"
            
        if current_rate:
            change = ((forecast.forecasted_price - current_rate) / current_rate) * 100
        else:
            change = None
            
        rf_forecast_data.append({
            'material': forecast.material_description,
            'model_type': forecast.get_model_type_display(),
            'current_quarter': current_quarter,
            'current_price': current_rate,
            'forecast_quarter': f"{forecast.quarter} {forecast.year}",
            'forecast_price': forecast.forecasted_price,
            'change_percent': change,
            'data_source': data_source,
        })
    
    context = {
        'project': project,
        'linear_forecast_data': linear_forecast_data,
        'rf_forecast_data': rf_forecast_data,
        'linear_count': linear_forecasts.count(),
        'rf_count': rf_forecasts.count(),
        'total_quarters': total_quarters,
        'forecast_analysis': forecast_analysis,
        'has_sufficient_data': total_quarters >= 2,
    }
    return render(request, 'estimator/view_forecast.html', context)

# ----------------------------------------------------------------------
# EXPORT FORECAST TO EXCEL
# ----------------------------------------------------------------------
@login_required
def export_forecast(request):
    profile = request.user.userprofile
    
    if profile.role in ['qs', 'contractor']:
        projects = Project.objects.filter(uploaded_by=profile)
        linear_forecasts = Forecast.objects.filter(project__in=projects, model_type='linear')
        rf_forecasts = Forecast.objects.filter(project__in=projects, model_type='random_forest')
    elif profile.role in ['pm', 'developer', 'admin']:
        linear_forecasts = Forecast.objects.filter(model_type='linear')
        rf_forecasts = Forecast.objects.filter(model_type='random_forest')
    else:
        messages.error(request, "Access denied.")
        return redirect('dashboard')

    if not linear_forecasts.exists() and not rf_forecasts.exists():
        messages.warning(request, "No forecast data available to export.")
        return redirect('dashboard')

    buffer = BytesIO()
    
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        linear_data = []
        for f in linear_forecasts:
            linear_data.append({
                'Project': f.project.name if f.project else 'N/A',
                'Material/Labour': f.material_description,
                'Model': f.get_model_type_display(),
                'Quarter': f.quarter,
                'Year': f.year,
                'Forecasted Price (RM)': f.forecasted_price,
            })
        
        if linear_data:
            linear_df = pd.DataFrame(linear_data)
            linear_df.to_excel(writer, sheet_name='Linear_Regression', index=False)
        
        rf_data = []
        for f in rf_forecasts:
            rf_data.append({
                'Project': f.project.name if f.project else 'N/A',
                'Material/Labour': f.material_description,
                'Model': f.get_model_type_display(),
                'Quarter': f.quarter,
                'Year': f.year,
                'Forecasted Price (RM)': f.forecasted_price,
            })
        
        if rf_data:
            rf_df = pd.DataFrame(rf_data)
            rf_df.to_excel(writer, sheet_name='Random_Forest', index=False)
    
    response = HttpResponse(buffer.getvalue(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="forecast_data.xlsx"'
    return response


@login_required
def debug_export_forecast(request):
    """Temporary debug view to check forecast data"""
    profile = request.user.userprofile
    forecasts = Forecast.objects.all()
    
    context = {
        'user_role': profile.role,
        'total_forecasts': forecasts.count(),
        'forecasts_list': list(forecasts.values('project__name', 'material_description', 'model_type')[:10])
    }
    return JsonResponse(context)


# ----------------------------------------------------------------------
# EXPORT ALL PROJECTS TO EXCEL (FIXED)
# ----------------------------------------------------------------------
@login_required
def export_all(request):
    format_type = request.GET.get('type', 'excel')
    if format_type != 'excel':
        messages.error(request, "Only Excel export supported for all projects.")
        return redirect('dashboard')

    profile = request.user.userprofile
    role = profile.role
    if role in ['qs', 'contractor']:
        projects = Project.objects.filter(uploaded_by=profile)
    else:
        projects = Project.objects.all()

    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        for project in projects:
            items = project.estimate_items.all()
            data = [
                {
                    'Section': i.section,
                    'Description': i.description,
                    'Qty': i.quantity,
                    'Unit': i.unit,
                    'Rate (RM)': i.rate,
                    'Amount (RM)': i.amount,
                    'CIDB Rate': i.cidb_rate or '',
                    'CIDB Amount': i.cidb_amount or '',
                    'Variance': (i.amount - (i.cidb_amount or 0)) if i.cidb_amount else ''
                } for i in items
            ]
            df = pd.DataFrame(data)
            
            sheet_name = re.sub(r'[\\/*?:[\]]', '', project.name)
            sheet_name = sheet_name[:31]  
            
            if not sheet_name.strip():
                sheet_name = f"Project_{project.pk}"
                
            df.to_excel(writer, sheet_name=sheet_name, index=False)

    response = HttpResponse(buffer.getvalue(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="all_projects.xlsx"'
    return response

# ----------------------------------------------------------------------
# REPORTS - FIXED PDF FORMATTING
# ----------------------------------------------------------------------
@login_required
def generate_report(request, pk):
    format_type = request.GET.get('type', 'pdf')
    return redirect('export_single', project_id=pk, format=format_type)

@login_required
def export_report(request, project_id, format):
    project = get_object_or_404(Project, pk=project_id)
    items = project.estimate_items.all()

    if format == 'excel':
        data = [{'Section': i.section, 'Description': i.description, 'Qty': i.quantity, 'Unit': i.unit,
                 'Rate (RM)': i.rate, 'Amount (RM)': i.amount, 'CIDB Rate': i.cidb_rate or '',
                 'CIDB Amount': i.cidb_amount or '', 'Variance': (i.amount - (i.cidb_amount or 0)) if i.cidb_amount else ''} for i in items]
        df = pd.DataFrame(data)
        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename="{project.name}_report.xlsx"'
        df.to_excel(response, index=False)
        return response

    elif format == 'pdf':
        from reportlab.lib.pagesizes import letter, landscape
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib import colors
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont

        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{project.name}_report.pdf"'
        
        doc = SimpleDocTemplate(response, pagesize=landscape(letter))
        elements = []
        styles = getSampleStyleSheet()
        
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=16,
            spaceAfter=30,
            alignment=1,  
        )
        
        elements.append(Paragraph(f"Project Report: {project.name}", title_style))
        elements.append(Spacer(1, 0.2*inch))
        
        summary_data = [
            [Paragraph(f"<b>Estimated Cost:</b> RM {project.estimated_cost:,.2f}", styles['Normal']),
             Paragraph(f"<b>CIDB Benchmark:</b> RM {project.cidb_cost:,.2f}", styles['Normal'])],
            [Paragraph(f"<b>Variance:</b> RM {project.variance():,.2f}", styles['Normal']),
             Paragraph(f"<b>Upload Date:</b> {project.upload_date.strftime('%d/%m/%Y')}", styles['Normal'])]
        ]
        
        if project.actual_cost:
            summary_data.append([
                Paragraph(f"<b>Actual Cost:</b> RM {project.actual_cost:,.2f}", styles['Normal']),
                Paragraph(f"<b>Profitability:</b> {project.profitability()}%", styles['Normal'])
            ])
        
        summary_table = Table(summary_data, colWidths=[3.5*inch, 3.5*inch])
        summary_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
            ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ]))
        elements.append(summary_table)
        elements.append(Spacer(1, 0.3*inch))
        
        table_data = [['Section', 'Description', 'Qty', 'Unit', 'Rate (RM)', 'Amount (RM)', 
                      'CIDB Rate', 'CIDB Amount', 'Variance']]
        
        for i in items:
            section_text = i.section[:15] + '...' if len(i.section) > 15 else i.section
            desc_text = i.description[:20] + '...' if len(i.description) > 20 else i.description
            
            table_data.append([
                section_text,
                desc_text,
                f"{i.quantity:,.3f}",
                i.unit,
                f"{i.rate:,.2f}",
                f"{i.amount:,.2f}",
                f"{i.cidb_rate:,.2f}" if i.cidb_rate else '-',
                f"{i.cidb_amount:,.2f}" if i.cidb_amount else '-',
                f"{(i.amount - (i.cidb_amount or 0)):,.2f}" if i.cidb_amount else '-',
            ])
        
        col_widths = [0.8*inch, 1.5*inch, 0.5*inch, 0.5*inch, 0.7*inch, 0.8*inch, 0.7*inch, 0.8*inch, 0.7*inch]
        t = Table(table_data, colWidths=col_widths, repeatRows=1)
        
        t.setStyle(TableStyle([
            # Header
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c3e50')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 7),  
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            
            # Data rows
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 6),  
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f8f9fa')),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
            ('ALIGN', (0, 1), (-1, -1), 'CENTER'),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
            
            # Grid and text wrapping
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dee2e6')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('WORDWRAP', (0, 0), (-1, -1), True),  
        ]))
        
        elements.append(t)
        doc.build(elements)
        return response

    messages.error(request, "Unsupported format")
    return redirect('dashboard')
