from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from estimator.models import UserProfile

class Command(BaseCommand):
    help = 'Create UserProfile for users that dont have one'

    def handle(self, *args, **options):
        users_without_profiles = User.objects.filter(userprofile__isnull=True)
        count = 0
        
        for user in users_without_profiles:
            default_role = 'admin' if user.is_staff else 'contractor'
            UserProfile.objects.create(user=user, role=default_role)
            count += 1
            self.stdout.write(f"Created UserProfile for {user.username} (role: {default_role})")
        
        self.stdout.write(
            self.style.SUCCESS(f'Successfully created {count} UserProfile(s) for users without profiles')
        )