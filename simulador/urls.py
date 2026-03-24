from django.urls import path
from . import views

# Archivo de configuración de rutas para la aplicación simulador
urlpatterns = [
    # 1. PÁGINAS PÚBLICAS Y ACCESO
    path('', views.landing, name='landing'),
    path('registro/', views.registro, name='registro'),

    # 2. PANEL PRIVADO (Dashboard, Perfil y Estadísticas)
    path('dashboard/', views.portada, name='portada'),
    path('perfil/', views.perfil, name='perfil'),
    path('estadisticas/', views.estadisticas, name='estadisticas'),

    # 3. TEMARIO Y DESCARGAS (Gestión de MP3 y PDF)
    path('temario-descargas/', views.ver_temario, name='ver_temario'),
    path('temario/<int:tema_id>/mp3/', views.descargar_tema_mp3, name='descargar_tema_mp3'),
    path('temario-cabo/', views.ver_temario, {'curso_slug': 'cabo'}, name='temario_cabo'),
    path('temario-cabo-primero/', views.ver_temario, {'curso_slug': 'cabo-primero'}, name='temario_cabo_primero'),
    path('temario-permanencia/', views.ver_temario, {'curso_slug': 'permanencia'}, name='temario_permanencia'),

    # 4. SISTEMA DE TEST (Configuración, Generación y Resultados)
    path('configurar/', views.configurar_test, name='configurar_test'),
    path('generar-test/', views.generar_test, name='generar_test'),
    path('examen/', views.examen, name='examen'),
    path('examen/<int:examen_id>/', views.ver_examen, name='ver_examen'),
    path('resultado/<int:resultado_id>/', views.resultado, name='resultado'),

    # 5. PASARELA DE PAGOS (Stripe u otros)
    path('pagos/iniciar/', views.iniciar_pago, name='iniciar_pago'),
    path('pagos/exitoso/', views.pago_exitoso, name='pago_exitoso'),
    path('pagos/cancelado/', views.pago_cancelado, name='pago_cancelado'),

    # 6. INSTRUCTOR IA
    path('instructor-ia/ask/', views.ask_ia_instructor, name='ask_ia_instructor'),
]
