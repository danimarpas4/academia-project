from django.urls import path
from . import views

# Archivo de configuración de rutas para la aplicación simulador
urlpatterns = [
    # 1. PÁGINAS PÚBLICAS Y ACCESO
    path('', views.landing, name='inicio'),
    path('registro/', views.registro, name='registro'),
    path('signup/<str:curso_slug>/', views.signup_course, name='signup_course'),

    # 2. PANEL PRIVADO (Dashboard, Perfil y Estadísticas)
    path('dashboard/', views.portada, name='portada'),
    path('perfil/', views.perfil, name='perfil'),
    path('estadisticas/', views.estadisticas, name='estadisticas'),
    path('escalafon/', views.escalafon, name='escalafon'),
    path('referidos/', views.mis_referidos, name='mis_referidos'),
    path('perfil-referidos/', views.perfil_referidos, name='perfil_referidos'),
    path('plan-premium/', views.plan_premium, name='plan_premium'),

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

    # 5. PASARELA DE PAGOS (Redsys)
    path('pagos/iniciar/', views.iniciar_pago, name='iniciar_pago'),
    path('pagos/procesar/<str:curso_slug>/', views.procesar_pago, name='procesar_pago'),
    path('pagos/exitoso/', views.pago_exitoso, name='pago_exitoso'),
    path('pagos/cancelado/', views.pago_cancelado, name='pago_cancelado'),
    path('api/redsys/webhook/', views.redsys_webhook, name='redsys_webhook'),

    # 6. INSTRUCTOR IA
    path('instructor-ia/', views.chat_ia, name='chat_ia'),
    
    # Red de seguridad: alias de compatibilidad para evitar el error NoReverseMatch 
    # en cualquier HTML (como portada.html o temario.html) que aún use el código antiguo.
    path('instructor-ia/ask/', views.chat_ia, name='ask_ia_instructor'),
    path('sincronizar/', views.sincronizar_bd, name='sincronizar'),
]