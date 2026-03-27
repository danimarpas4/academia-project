import django
from django.core.management.base import BaseCommand
from django.conf import settings

django.setup()

from allauth.socialaccount.models import SocialApp, SocialAccount
from django.contrib.sites.models import Site


class Command(BaseCommand):
    help = 'Configura automáticamente la SocialApp de Google en la base de datos'

    def handle(self, *args, **options):
        client_id = getattr(settings, 'GOOGLE_CLIENT_ID', None)
        client_secret = getattr(settings, 'GOOGLE_CLIENT_SECRET', None)
        
        if not client_id or not client_secret:
            self.stderr.write(
                self.style.ERROR(
                    'Error: GOOGLE_CLIENT_ID y GOOGLE_CLIENT_SECRET deben estar definidos en settings o .env'
                )
            )
            return

        site = Site.objects.get_current()
        
        social_app, created = SocialApp.objects.update_or_create(
            provider='google',
            defaults={
                'name': 'Google',
                'client_id': client_id,
                'secret': client_secret,
                'key': '',
            }
        )
        
        social_app.sites.add(site)
        
        if created:
            self.stdout.write(
                self.style.SUCCESS(f'SocialApp de Google creada correctamente')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f'SocialApp de Google actualizada correctamente')
            )
        
        self.stdout.write(f'  Provider: {social_app.provider}')
        self.stdout.write(f'  Client ID: {client_id[:20]}...')
        self.stdout.write(f'  Sites: {[s.domain for s in social_app.sites.all()]}')
