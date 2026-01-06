from django.contrib import admin
from django.urls import path, include
from simulador import views as vistas_simulador 
# --- AÑADE ESTAS DOS IMPORTACIONES NUEVAS ---
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    
    path('accounts/', include('django.contrib.auth.urls')),
    
    # MANTENEMOS TU RUTA DE REGISTRO
    path('registro/', vistas_simulador.registro, name='registro'),
    
    path('', include('simulador.urls')),
]

# --- AÑADE ESTO AL FINAL DEL ARCHIVO ---
# Esto permite que Django "sirva" los archivos PDF en tu ordenador
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)