from django.contrib.auth.models import User
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver

# 1. NUEVO MODELO: CURSO
class Curso(models.Model):
    nombre = models.CharField(max_length=100) # Ej: "Ascenso a Cabo", "Permanencia"
    descripcion = models.TextField(blank=True)
    precio = models.DecimalField(max_digits=6, decimal_places=2, default=0.00)
    
    def __str__(self):
        return self.nombre

class Tema(models.Model):
    # Un tema pertenece a un Curso (ej: "Legislación" pertenece a "Cabo")
    curso = models.ForeignKey(Curso, on_delete=models.CASCADE, related_name='temas', null=True, blank=True)
    nombre = models.CharField(max_length=200)
    archivo_pdf = models.FileField(upload_to='temarios/', blank=True, null=True)
    
    # NUEVO CAMPO: Aquí subirás los MP3 que creas con tu script en Python
    archivo_audio = models.FileField(
        upload_to='temas_audio/', 
        blank=True, 
        null=True, 
        help_text="Sube aquí el archivo MP3 generado (ej: '01_Reales_Ordenanzas.mp3')"
    )

    # Este lo dejamos por compatibilidad, pero ya no es urgente rellenarlo
    contenido_texto = models.TextField(blank=True, null=True, help_text="Texto del tema (Opcional si ya subes el audio)")

    def __str__(self):
        # Muestra "Cabo - Legislación" para que te aclares en el admin
        nombre_curso = self.curso.nombre if self.curso else "Sin Curso"
        return f"{nombre_curso} - {self.nombre}"
class Pregunta(models.Model):
    tema = models.ForeignKey(Tema, on_delete=models.CASCADE, related_name='preguntas') 
    enunciado = models.TextField()
    dificultad = models.IntegerField(default=1)

    def __str__(self):
        return self.enunciado
class Opcion(models.Model):
    pregunta = models.ForeignKey(Pregunta, on_delete=models.CASCADE, related_name='opciones')
    texto = models.CharField(max_length=255)
    es_correcta = models.BooleanField(default=False)
    
    def __str__(self):
        return self.texto
    
class Resultado(models.Model):
    usuario = models.ForeignKey(User, on_delete=models.CASCADE)
    tema = models.ForeignKey(Tema, on_delete=models.CASCADE)
    fecha = models.DateTimeField(auto_now_add=True)
    nota = models.FloatField()
    aciertos = models.IntegerField(default=0)
    fallos = models.IntegerField(default=0)

    def __str__(self):
        return f"Resultado de {self.usuario} en {self.tema}: {self.nota}"
# --- MODELO: PERFIL Y RANGOS ---
class Perfil(models.Model):
    # Lista completa de rangos militares
    RANGOS = [
        ('Recluta', 'Recluta'),
        ('Soldado', 'Soldado'),
        ('Cabo', 'Cabo'),
        ('Cabo Primero', 'Cabo Primero'),
        ('Cabo Mayor', 'Cabo Mayor'),
        ('Sargento', 'Sargento'),
        ('Sargento Primero', 'Sargento Primero'),
        ('Brigada', 'Brigada'),
        ('Subteniente', 'Subteniente'),
        ('Suboficial Mayor', 'Suboficial Mayor'),
        ('Teniente', 'Teniente'),
        ('Capitán', 'Capitán'),
        ('Comandante', 'Comandante'),
        ('Teniente Coronel', 'Teniente Coronel'),
        ('Coronel', 'Coronel'),
        ('General de Brigada', 'General de Brigada'),
        ('General de División', 'General de División'),
        ('Teniente General', 'Teniente General'),
    ]

    usuario = models.OneToOneField(User, on_delete=models.CASCADE)
    
    # --- CAMBIO IMPORTANTE ---
    # En lugar de un booleano simple, ahora guardamos QUÉ cursos tiene
    cursos_activos = models.ManyToManyField(Curso, blank=True, related_name='alumnos')
    # -------------------------

    rango = models.CharField(max_length=30, choices=RANGOS, default='Recluta')
    preguntas_respondidas = models.PositiveIntegerField(default=0)
    
    def __str__(self):
        return f"{self.usuario.username} - {self.rango}"

    # Lógica para subir de rango
    def comprobar_ascenso(self):
        requisitos = {
            'Recluta': 0,
            'Soldado': 10,
            'Cabo': 100,
            'Cabo Primero': 250,
            'Cabo Mayor': 500,
            'Sargento': 750,
            'Sargento Primero': 1000,
            'Brigada': 1250,
            'Subteniente': 1500,
            'Suboficial Mayor': 1750,
            'Teniente': 2000,
            'Capitán': 2250,
            'Comandante': 2500,
            'Teniente Coronel': 2750,
            'Coronel': 3000,
            'General de Brigada': 3500,
            'General de División': 4000,
            'Teniente General': 4500,
        }

        # Vamos de mayor a menor para encontrar el rango más alto que merezca
        nuevo_rango = self.rango
        
        for r, preguntas_necesarias in reversed(requisitos.items()):
            if self.preguntas_respondidas >= preguntas_necesarias:
                nuevo_rango = r
                break 
        
        if self.rango != nuevo_rango:
            self.rango = nuevo_rango
            self.save()
            return True 
        
        return False

# --- SEÑALES ---
@receiver(post_save, sender=User)
def crear_perfil(sender, instance, created, **kwargs):
    if created:
        Perfil.objects.create(usuario=instance)

@receiver(post_save, sender=User)
def guardar_perfil(sender, instance, **kwargs):
    instance.perfil.save()