from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from estimator import views as estimator_views
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('admin/', admin.site.urls),

    path('login/', estimator_views.login_user, name='login'),
    path('register/', estimator_views.register_user, name='register'),
    path('logout/', estimator_views.logout_user, name='logout'),

    path('password_reset/', 
         auth_views.PasswordResetView.as_view(
             template_name='estimator/password_reset.html'
         ), 
         name='password_reset'),
    path('password_reset/done/', 
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

    path('', include('estimator.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)