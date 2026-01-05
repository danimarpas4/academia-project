from django.contrib import admin
from .models import Tema, Pregunta, Opcion

class OpcionInline(admin.TabularInline):
    model = Opcion
    extra = 4

class PreguntaAdmin(admin.ModelAdmin):
    inlines = [OpcionInline]
    list_display = ('enunciado', 'tema')

admin.site.register(Tema)
admin.site.register(Pregunta, PreguntaAdmin)