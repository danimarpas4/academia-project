from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import Curso, Tema, Pregunta, Opcion, Perfil, Resultado, HistorialDescuento, DocumentoContexto

# 1. Configuración para ver el Perfil DENTRO del Usuario
class PerfilInline(admin.StackedInline):
    model = Perfil
    can_delete = False
    verbose_name_plural = 'Perfil del Alumno'
    filter_horizontal = ('cursos_activos',)
    fk_name = 'usuario'

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

class HistorialDescuentoAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'fecha', 'motivo', 'cuantia', 'saldo_resultante')
    list_filter = ('motivo', 'fecha')
    search_fields = ('usuario__username',)

class DocumentoContextoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'curso', 'tipo', 'fecha_subida', 'activo')
    list_filter = ('curso', 'tipo', 'activo')
    search_fields = ('nombre', 'contenido_texto')
    readonly_fields = ('contenido_texto', 'fecha_subida')
    
    actions = ['extraer_texto_pdfs']

    @admin.action(description='Extraer texto de PDFs seleccionados')
    def extraer_texto_pdfs(self, request, queryset):
        for doc in queryset:
            if doc.archivo and not doc.contenido_texto:
                doc.extraer_texto_pdf()
                self.message_user(request, f'Texto extraído de: {doc.nombre}')
            else:
                self.message_user(request, f'{doc.nombre} ya tiene texto o no tiene PDF')

# Registro
admin.site.register(Curso, CursoAdmin)
admin.site.register(Tema, TemaAdmin)
admin.site.register(Pregunta, PreguntaAdmin)
admin.site.register(Resultado, ResultadoAdmin)
admin.site.register(HistorialDescuento, HistorialDescuentoAdmin)
admin.site.register(DocumentoContexto, DocumentoContextoAdmin)
# Ya no hace falta registrar Perfil suelto porque sale dentro de Usuario