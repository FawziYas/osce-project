"""
Management command: create_admin

Creates an admin examiner account interactively or via flags.
"""
from django.core.management.base import BaseCommand
from core.models import Examiner


class Command(BaseCommand):
    help = 'Create an admin examiner account'

    def add_arguments(self, parser):
        parser.add_argument('--username', type=str, default='admin')
        parser.add_argument('--email', type=str, default='admin@osce.local')
        parser.add_argument('--password', type=str, default=None)
        parser.add_argument('--full-name', type=str, default='System Administrator')

    def handle(self, *args, **options):
        username = options['username']
        email = options['email']
        password = options['password']
        full_name = options['full_name']

        if Examiner.objects.filter(username=username).exists():
            self.stdout.write(self.style.WARNING(f'User "{username}" already exists.'))
            return

        if not password:
            import getpass
            password = getpass.getpass('Password: ')
            confirm = getpass.getpass('Confirm password: ')
            if password != confirm:
                self.stdout.write(self.style.ERROR('Passwords do not match.'))
                return

        user = Examiner.objects.create_superuser(
            username=username,
            email=email,
            password=password,
            full_name=full_name,
        )
        self.stdout.write(self.style.SUCCESS(
            f'Admin account created: {user.username} ({user.email})'
        ))
