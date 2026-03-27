from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages


def requiere_premium(view_func):
    """
    Decorador que verifica si el usuario tiene suscripción premium.
    Si no la tiene, redirige a la página de Plan Premium.
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if request.user.is_authenticated:
            try:
                perfil = request.user.perfil
                if not perfil.es_premium:
                    messages.warning(
                        request, 
                        '¡Soldado! Esta funcionalidad requiere suscripción Premium.'
                    )
                    return redirect('plan_premium')
            except AttributeError:
                pass
        return view_func(request, *args, **kwargs)
    return wrapper


def requiere_curso_activo(curso_slug):
    """
    Decorador factory que verifica si el usuario tiene activo un curso específico.
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if request.user.is_authenticated:
                try:
                    perfil = request.user.perfil
                    curso_slugs = [c.nombre.lower().replace(' ', '-') for c in perfil.cursos_activos.all()]
                    if curso_slug.lower() not in curso_slugs and not perfil.es_premium:
                        messages.warning(
                            request, 
                            f'¡Soldado! Necesitas el curso {curso_slug} para acceder a este contenido.'
                        )
                        return redirect('plan_premium')
                except AttributeError:
                    pass
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator
