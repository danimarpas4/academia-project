class CourseAccessMiddleware:
    COURSE_PROTECTED_PATHS = {
        'cabo': ['/temario-cabo/', '/configurar/', '/examen/'],
        'cabo-primero': ['/temario-cabo-primero/'],
    }

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.user.is_authenticated:
            return self.get_response(request)

        path = request.path
        
        for curso_slug, protected_paths in self.COURSE_PROTECTED_PATHS.items():
            for protected_path in protected_paths:
                if path.startswith(protected_path):
                    if not self.user_has_course_access(request.user, curso_slug):
                        from django.contrib import messages
                        from django.shortcuts import redirect
                        messages.warning(
                            request, 
                            f"No tienes acceso al curso {curso_slug.replace('-', ' ').title()}. "
                            f"Completa tu inscripción para desbloquear este contenido."
                        )
                        return redirect('iniciar_pago')
                    break

        return self.get_response(request)

    def user_has_course_access(self, user, curso_slug):
        from simulador.models import Perfil, Curso
        
        try:
            perfil = user.perfil
            curso_mapping = {
                'cabo': 'Ascenso a Cabo',
                'cabo-primero': 'Cabo Primero',
            }
            curso_nombre = curso_mapping.get(curso_slug)
            if curso_nombre:
                return perfil.cursos_activos.filter(nombre=curso_nombre).exists()
        except Perfil.DoesNotExist:
            pass
        return False
