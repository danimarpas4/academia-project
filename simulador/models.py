from django.contrib.auth.models import User
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver

class Tema(models.Model):
    nombre = models.CharField(max_length=200)
    def __str__(self):
        return self.nombre

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
    nota = models.FloatField()
    fecha = models.DateTimeField(auto_now_add=True) # Se pone la fecha sola automáticamente

    def __str__(self):
        return f"Nota de {self.usuario.username}: {self.nota}"
    
# --- NUEVO MODELO: PERFIL DE PAGO ---
class Perfil(models.Model):
    usuario = models.OneToOneField(User, on_delete=models.CASCADE, related_name='perfil')
    esta_suscrito = models.BooleanField(default=False) # Aquí guardamos si pagó

    def __str__(self):
        return f"Perfil de {self.usuario.username}"

# --- SEÑALES (MAGIA AUTOMÁTICA) ---
# Esto hace que cada vez que se cree un User, se cree su Perfil automáticamente
@receiver(post_save, sender=User)
def crear_perfil(sender, instance, created, **kwargs):
    if created:
        Perfil.objects.create(usuario=instance)

@receiver(post_save, sender=User)
def guardar_perfil(sender, instance, **kwargs):
    instance.perfil.save()