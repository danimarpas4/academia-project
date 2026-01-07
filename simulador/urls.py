from django.urls import path
from . import views

urlpatterns = [
    # 1. PÁGINA PÚBLICA (La de los 4 cursos)
    # Al entrar a la web (ruta vacía), carga la vista 'inicio'
    path('', views.inicio, name='inicio'),

    # 2. PANEL PRIVADO (Dashboard)
    # Hemos movido la portada antigua a '/dashboard/'
    path('dashboard/', views.portada, name='portada'),
    
    # --- EL RESTO SE QUEDA IGUAL ---
    path('configurar-test/', views.configurar_test, name='configurar_test'),
    path('estadisticas/', views.estadisticas, name='estadisticas'),
    path('temario-descargas/', views.ver_temario, name='ver_temario'),
    path('temario/<int:tema_id>/mp3/', views.descargar_tema_mp3, name='descargar_tema_mp3'),
    path('perfil/', views.perfil, name='perfil'),
    
    # Lógica del examen
    path('examen/<int:tema_id>/', views.examen, name='examen'),
    path('resultado/<int:resultado_id>/', views.resultado, name='resultado'),
    
    # Pagos
    path('pagos/iniciar/', views.iniciar_pago, name='iniciar_pago'),
    path('pagos/exitoso/', views.pago_exitoso, name='pago_exitoso'),
    path('pagos/cancelado/', views.pago_cancelado, name='pago_cancelado'),
    
    # Rutas de autenticación (Login/Registro)
    # Asegúrate de tener estas si no las estás importando desde 'django.contrib.auth.urls'
    path('registro/', views.registro, name='registro'),
]