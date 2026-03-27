from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.conf import settings


class SocialAccountAdapter(DefaultSocialAccountAdapter):
    def pre_social_login(self, request, sociallogin):
        email = sociallogin.account.extra_data.get('email')
        if email:
            sociallogin.email_addresses = [
                addr for addr in sociallogin.email_addresses
                if addr.email.lower() == email.lower()
            ]

    def save_user(self, request, sociallogin, form=None):
        user = super().save_user(request, sociallogin, form)
        
        curso_seleccionado = request.session.pop('curso_seleccionado', None)
        if curso_seleccionado:
            request.session['curso_a_pagar'] = curso_seleccionado
        
        return user
