from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import UserProfile

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Automatically create UserProfile when a new User is created"""
    if created:
        default_role = 'admin' if instance.is_staff else 'contractor'
        UserProfile.objects.get_or_create(user=instance, defaults={'role': default_role})

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """Ensure UserProfile is saved when User is saved"""
    try:
        instance.userprofile.save()
    except UserProfile.DoesNotExist:
        default_role = 'admin' if instance.is_staff else 'contractor'
        UserProfile.objects.create(user=instance, role=default_role)