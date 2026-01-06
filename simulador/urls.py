from django.urls import path
from . import views

urlpatterns = [
    # Panel Principal (El menú con las 3 opciones)
    path('', views.portada, name='portada'),
    
    # Opción 1: Generador (Lo haremos funcional en el siguiente paso)
    path('configurar-test/', views.configurar_test, name='configurar_test'),
    
    # Opción 2: Estadísticas (Placeholder por ahora)
    path('estadisticas/', views.estadisticas, name='estadisticas'),

    # Opción 3: Temario (Solo descargas)
    path('temario-descargas/', views.ver_temario, name='ver_temario'),
    
    path('perfil/', views.perfil, name='perfil'),

    # La lógica del examen (se mantiene)
    path('examen/<int:tema_id>/', views.examen, name='examen'),
    path('resultado/<int:resultado_id>/', views.resultado, name='resultado'),
    path('pagos/iniciar/', views.iniciar_pago, name='iniciar_pago'),
    path('pagos/exitoso/', views.pago_exitoso, name='pago_exitoso'),
    path('pagos/cancelado/', views.pago_cancelado, name='pago_cancelado'),
]