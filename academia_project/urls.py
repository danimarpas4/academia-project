from django.contrib import admin
from django.urls import path, include
from simulador import views as vistas_simulador 
# --- IMPORTACIONES PARA ARCHIVOS ESTÁTICOS ---
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # 1. Autenticación Estándar (Tu Login propio)
    # Mantenemos esto PRIMERO para que use tu diseño de 'registration/login.html'
    path('accounts/', include('django.contrib.auth.urls')),
    
    # 2. Autenticación con Google (Allauth)
    # Aquí es donde busca las rutas 'accounts/google/login/'
    path('accounts/', include('allauth.urls')),
    
    # MANTENEMOS TU RUTA DE REGISTRO
    path('registro/', vistas_simulador.registro, name='registro'),
    
    # RUTAS DE LA APP
    path('', include('simulador.urls')),
]

# --- SIRVE ARCHIVOS MEDIA EN MODO DEBUG ---
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)