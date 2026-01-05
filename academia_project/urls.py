from django.contrib import admin
from django.urls import path, include
from simulador import views as vistas_simulador # Importamos las vistas para usar el registro

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # Rutas de autenticación (Login/Logout automáticos de Django)
    path('accounts/', include('django.contrib.auth.urls')),
    
    # Ruta para registrarse (la crearemos nosotros ahora)
    path('registro/', vistas_simulador.registro, name='registro'),
    
    path('', include('simulador.urls')),
]