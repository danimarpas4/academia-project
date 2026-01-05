from django.urls import path
from . import views

urlpatterns = [
    # 1. LA NUEVA RAÍZ (El Hall de cursos)
    path('', views.landing, name='landing'),

    # 2. EL CURSO DE CABO (Antes era la raíz, ahora le llamamos 'temario_cabo')
    # Nota: Le he cambiado el name de 'portada' a 'temario_cabo' para ser más claros
    path('curso-cabo/', views.portada, name='temario_cabo'),

    # ... Resto de rutas (examen, resultados, perfil, login) se quedan igual ...
    path('examen/<int:tema_id>/', views.examen, name='examen'),
    path('perfil/', views.perfil, name='perfil'),
    path('pagar/', views.iniciar_pago, name='iniciar_pago'),
    path('gracias/', views.pago_exitoso, name='pago_exitoso'),
    path('cancelado/', views.pago_cancelado, name='pago_cancelado'),
    # etc...
]