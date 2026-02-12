from django.urls import path
from . import views

urlpatterns = [
    # 1. PÁGINA PÚBLICA
    path('', views.inicio, name='inicio'),

    # 2. PANEL PRIVADO (Dashboard y Perfil)
    path('dashboard/', views.portada, name='portada'),
    path('perfil/', views.perfil, name='perfil'),
    path('temario-descargas/', views.ver_temario, name='ver_temario'),
    path('temario/<int:tema_id>/mp3/', views.descargar_tema_mp3, name='descargar_tema_mp3'),
    
    # ⚠️ ESTA ES LA QUE TE FALTABA (Por eso el error amarillo)
    path('estadisticas/', views.estadisticas, name='estadisticas'),

    # 3. ZONA DE TEST (Nuevo sistema)
    path('configurar/', views.configurar_test, name='configurar_test'),
    path('examen/', views.examen, name='examen'),
    path('resultado/<int:resultado_id>/', views.resultado, name='resultado'),

    # 4. PAGOS Y USUARIOS
    path('pagos/iniciar/', views.iniciar_pago, name='iniciar_pago'),
    path('pagos/exitoso/', views.pago_exitoso, name='pago_exitoso'),
    path('pagos/cancelado/', views.pago_cancelado, name='pago_cancelado'),
    path('registro/', views.registro, name='registro'),
]