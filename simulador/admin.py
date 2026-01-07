from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import Curso, Tema, Pregunta, Opcion, Perfil, Resultado

# 1. Configuración para ver el Perfil DENTRO del Usuario
class PerfilInline(admin.StackedInline):
    model = Perfil
    can_delete = False
    verbose_name_plural = 'Perfil del Alumno'
    filter_horizontal = ('cursos_activos',) # ¡Esto hace que aparezca el selector de cursos!

# Creamos un nuevo administrador de Usuarios que incluye el Perfil
class UserAdmin(BaseUserAdmin):
    inlines = [PerfilInline]

# Desregistramos el Usuario original y registramos el nuestro vitaminado
admin.site.unregister(User)
admin.site.register(User, UserAdmin)

# 2. Resto de modelos
class CursoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'precio')

class TemaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'curso')
    list_filter = ('curso',)

class OpcionInline(admin.TabularInline):
    model = Opcion
    extra = 4

class PreguntaAdmin(admin.ModelAdmin):
    inlines = [OpcionInline]
    list_display = ('enunciado', 'tema')
    list_filter = ('tema',)

class ResultadoAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'tema', 'nota', 'fecha')

# Registro
admin.site.register(Curso, CursoAdmin)
admin.site.register(Tema, TemaAdmin)
admin.site.register(Pregunta, PreguntaAdmin)
admin.site.register(Resultado, ResultadoAdmin)
# Ya no hace falta registrar Perfil suelto porque sale dentro de Usuario