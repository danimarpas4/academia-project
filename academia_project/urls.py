from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

# Índice principal del proyecto
urlpatterns = [
    # Panel de administración de Django
    path('admin/', admin.site.urls),
    
    # Delegamos TODAS las rutas a la app simulador
    path('', include('simulador.urls')),
    
    # Sistema de autenticación de Django (login, logout, etc.)
    path('accounts/', include('django.contrib.auth.urls')),
    
    # django-allauth (social login)
    path('accounts/', include('allauth.urls')),
]

# Configuración para servir archivos multimedia (PDFs, Audios) en desarrollo local
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)