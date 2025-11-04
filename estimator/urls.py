from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('dashboard/', views.dashboard, name='dashboard'),  
    path('import-cidb/', views.import_cidb, name='import_cidb'),
    path('data-status/', views.data_status, name='data_status'),
    path('force-import/', views.force_import_data, name='force_import_data'),
    path('profile/', views.profile, name='profile'),
    path('upload/', views.upload_project, name='upload_project'),  # NEW: dedicated upload page
    path('upload-actual/<int:pk>/', views.upload_actual_cost, name='upload_actual_cost'),
    path('project/<int:pk>/', views.project_detail, name='project_detail'),
    path('project/<int:pk>/edit/', views.project_edit, name='project_edit'),
    path('project/<int:pk>/actuals/', views.edit_actuals, name='edit_actuals'),
    path('project/<int:pk>/adjust-inflation/', views.adjust_inflation, name='adjust_inflation'),
    path('project/<int:pk>/forecast/', views.run_forecast_view, name='run_forecast_view'),
    path('project/<int:pk>/view-forecast/', views.view_forecast, name='view_forecast'),
    path('debug-export/', views.debug_export_forecast, name='debug_export'),
    path('project/<int:pk>/generate-report/', views.generate_report, name='generate_report'),
    path('export-report/<int:project_id>/<str:format>/', views.export_report, name='export_single'),
    path('export-forecast/', views.export_forecast, name='export_forecast'),
    path('export-all/', views.export_all, name='export_all'),
    path('login/', views.login_user, name='login'),
    path('register/', views.register_user, name='register'),
    path('logout/', views.logout_user, name='logout'),
    path('forgot-password/', 
         auth_views.PasswordResetView.as_view(
             template_name='estimator/forgot_password.html'
         ), 
         name='forgot_password'),

    path('forgot-password/done/', 
         auth_views.PasswordResetDoneView.as_view(
             template_name='estimator/password_reset_done.html'
         ), 
         name='password_reset_done'),

    path('reset/<uidb64>/<token>/', 
         auth_views.PasswordResetConfirmView.as_view(
             template_name='estimator/password_reset_confirm.html'
         ), 
         name='password_reset_confirm'),

    path('reset/done/', 
         auth_views.PasswordResetCompleteView.as_view(
             template_name='estimator/password_reset_complete.html'
         ), 
         name='password_reset_complete'),
]
