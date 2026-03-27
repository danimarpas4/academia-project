from django.contrib.auth.models import User
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver

# 1. MODELO: CURSO
class Curso(models.Model):
    nombre = models.CharField(max_length=100) # Ej: "Ascenso a Cabo", "Cabo Primero"
    descripcion = models.TextField(blank=True)
    precio = models.DecimalField(max_digits=6, decimal_places=2, default=0.00)
    
    def __str__(self):
        return self.nombre

# 2. MODELO: TEMA (Con soporte para Inglés, Geografía e Informática)
class Tema(models.Model):
    MATERIAS_CHOICES = [
        ('CABO', 'Legislación / Cabo'),
        ('INGLÉS', 'Inglés'),
        ('GEOGRAFÍA', 'Geografía'),
        ('INFORMÁTICA', 'Informática'),
    ]

    curso = models.ForeignKey(Curso, on_delete=models.CASCADE, related_name='temas', null=True, blank=True)
    
    materia = models.CharField(
        max_length=20, 
        choices=MATERIAS_CHOICES, 
        default='CABO',
        help_text="Categoría para agrupar en los acordeones de la web"
    )
    
    # Ordenación táctica compatible con JSON
    capitulo = models.IntegerField(default=0)
    bloque = models.IntegerField(default=0)
    numero_tema = models.IntegerField(default=0)

    nombre = models.CharField(max_length=200, help_text="Ej: Reales Ordenanzas")
    archivo_pdf = models.FileField(upload_to='temarios/', blank=True, null=True)
    archivo_audio = models.FileField(upload_to='temas_audio/', blank=True, null=True, help_text="Archivo MP3 generado")
    contenido_texto = models.TextField(blank=True, null=True, help_text="Texto opcional del tema")

    class Meta:
        ordering = ['materia', 'capitulo', 'bloque', 'numero_tema']

    def __str__(self):
        return f"[{self.get_materia_display()}] {self.nombre}"

# 3. MODELO: PREGUNTA
class Pregunta(models.Model):
    tema = models.ForeignKey(Tema, on_delete=models.CASCADE, related_name='preguntas') 
    enunciado = models.TextField()
    explicacion = models.TextField(blank=True, null=True, help_text="Se muestra al fallar o corregir")
    dificultad = models.IntegerField(default=1) # 1: Fácil, 2: Medio, 3: Difícil

    def __str__(self):
        return f"{self.tema.nombre} - {self.enunciado[:50]}..."

# 4. MODELO: OPCIONES DE RESPUESTA
class Opcion(models.Model):
    pregunta = models.ForeignKey(Pregunta, on_delete=models.CASCADE, related_name='opciones')
    texto = models.CharField(max_length=255)
    es_correcta = models.BooleanField(default=False)
    
    def __str__(self):
        return self.texto

# 5. MODELO: EXAMEN (Sesión de Test)
# Este modelo es necesario para agrupar las preguntas de un test específico
class Examen(models.Model):
    usuario = models.ForeignKey(User, on_delete=models.CASCADE)
    fecha = models.DateTimeField(auto_now_add=True)
    completado = models.BooleanField(default=False)
    # Guardamos qué preguntas se incluyeron en esta sesión
    preguntas = models.ManyToManyField(Pregunta)

    def __str__(self):
        return f"Test de {self.usuario.username} ({self.fecha.strftime('%d/%m/%Y %H:%M')})"

# 6. MODELO: RESULTADO
class Resultado(models.Model):
    usuario = models.ForeignKey(User, on_delete=models.CASCADE)
    # Vinculamos el resultado a un Examen (sesión) concreto
    examen = models.OneToOneField(Examen, on_delete=models.CASCADE, null=True, blank=True)
    # Opcional: vinculación a tema si es un test de un solo tema
    tema = models.ForeignKey(Tema, on_delete=models.CASCADE, null=True, blank=True)
    
    fecha = models.DateTimeField(auto_now_add=True)
    nota = models.FloatField(default=0.0)
    aciertos = models.IntegerField(default=0)
    fallos = models.IntegerField(default=0)
    blancos = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.usuario.username} - Nota: {self.nota}"

# 7. MODELO: PERFIL Y RANGOS
class Perfil(models.Model):
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
    cursos_activos = models.ManyToManyField(Curso, blank=True, related_name='alumnos')
    rango = models.CharField(max_length=30, choices=RANGOS, default='Recluta')
    preguntas_respondidas = models.PositiveIntegerField(default=0)
    codigo_referido = models.CharField(max_length=12, unique=True, blank=True, null=True, help_text="Código único para referral")
    referido_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='referidos')
    descuento_acumulado = models.DecimalField(max_digits=8, decimal_places=2, default=0.00)
    es_premium = models.BooleanField(default=False, help_text="Indica si el usuario tiene suscripción premium activa")
    
    def __str__(self):
        return f"{self.usuario.username} - {self.rango}"

    def comprobar_ascenso(self):
        requisitos = {
            'Recluta': 0, 'Soldado': 10, 'Cabo': 100, 'Cabo Primero': 250,
            'Cabo Mayor': 500, 'Sargento': 750, 'Sargento Primero': 1000,
            'Brigada': 1250, 'Subteniente': 1500, 'Suboficial Mayor': 1750,
            'Teniente': 2000, 'Capitán': 2250, 'Comandante': 2500,
            'Teniente Coronel': 2750, 'Coronel': 3000, 'General de Brigada': 3500,
            'General de División': 4000, 'Teniente General': 4500,
        }

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


# 8. MODELO: HISTORIAL DESCUENTO
class HistorialDescuento(models.Model):
    MOTIVOS = [
        ('ALTA_REFERIDO', 'Alta por referido'),
        ('RECOMPENSA_RECLUTA', 'Recluta registrado'),
        ('APLICADO_PAGO', 'Descuento aplicado en pago'),
        ('SOBRANTE_PAGO', 'Sobrante перенесён'),
    ]

    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='historial_descuentos')
    fecha = models.DateTimeField(auto_now_add=True)
    motivo = models.CharField(max_length=30, choices=MOTIVOS)
    cuantia = models.DecimalField(max_digits=6, decimal_places=2)
    saldo_resultante = models.DecimalField(max_digits=8, decimal_places=2, default=0.00)

    class Meta:
        ordering = ['-fecha']
        verbose_name = 'Historial de Descuento'
        verbose_name_plural = 'Historiales de Descuento'

    def __str__(self):
        return f"{self.usuario.username} - {self.get_motivo_display()} ({self.fecha.strftime('%d/%m/%Y')})"

# 9. MODELO: DOCUMENTO CONTEXTO (Para RAG del Tutor IA)
def documento_upload_path(instance, filename):
    """Genera la ruta de subida según el curso y tipo"""
    curso_slug = instance.curso.nombre.lower().replace(' ', '_') if instance.curso else 'general'
    return f'temarios/{curso_slug}/{filename}'

class DocumentoContexto(models.Model):
    TIPOS_DOCUMENTO = [
        ('TEMARIO', 'Temario'),
        ('CONVOCATORIA', 'Convocatoria'),
        ('NORMATIVA', 'Normativa'),
    ]
    
    curso = models.ForeignKey(
        Curso, 
        on_delete=models.CASCADE, 
        related_name='documentos',
        help_text="Curso al que pertenece este documento"
    )
    
    nombre = models.CharField(
        max_length=200, 
        help_text="Nombre descriptivo del documento"
    )
    
    tipo = models.CharField(
        max_length=20,
        choices=TIPOS_DOCUMENTO,
        default='TEMARIO'
    )
    
    archivo = models.FileField(
        upload_to=documento_upload_path,
        blank=True,
        null=True,
        help_text="PDF del temario o convocatoria"
    )
    
    contenido_texto = models.TextField(
        blank=True,
        null=True,
        help_text="Texto extraído automáticamente del PDF"
    )
    
    fecha_subida = models.DateTimeField(auto_now_add=True)
    activo = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['-fecha_subida']
        verbose_name = 'Documento de Contexto'
        verbose_name_plural = 'Documentos de Contexto'
    
    def __str__(self):
        return f"{self.nombre} ({self.get_tipo_display()}) - {self.curso.nombre}"
    
    def extraer_texto_pdf(self):
        """Extrae el texto del PDF o TXT y lo guarda en contenido_texto"""
        if not self.archivo:
            return None
        
        texto = ""
        archivo_path = self.archivo.path
        extension = archivo_path.split('.')[-1].lower()
        
        if extension == 'txt':
            try:
                with open(archivo_path, 'r', encoding='utf-8') as f:
                    texto = f.read()
            except UnicodeDecodeError:
                with open(archivo_path, 'r', encoding='latin-1') as f:
                    texto = f.read()
            except Exception as e:
                return f"Error al leer TXT: {str(e)}"
                
        elif extension == 'pdf':
            try:
                import pdfplumber
                with pdfplumber.open(self.archivo) as pdf:
                    for page in pdf.pages:
                        page_text = page.extract_text()
                        if page_text:
                            texto += page_text + "\n\n"
            except ImportError:
                try:
                    import PyPDF2
                    with open(archivo_path, 'rb') as f:
                        reader = PyPDF2.PdfReader(f)
                        for page in reader.pages:
                            texto += page.extract_text() + "\n\n"
                except Exception as e:
                    return f"Error al procesar con PyPDF2: {str(e)}"
            except Exception as e:
                return f"Error al procesar PDF: {str(e)}"
        else:
            return f"Formato no soportado: {extension}"
        
        self.contenido_texto = texto[:100000]
        self.save()
        return texto

# --- SEÑALES ---
import uuid

def generar_codigo_referido():
    return uuid.uuid4().hex[:8].upper()

@receiver(post_save, sender=User)
def crear_perfil(sender, instance, created, **kwargs):
    if created:
        perfil = Perfil(usuario=instance)
        perfil.codigo_referido = generar_codigo_referido()
        perfil.save()

@receiver(post_save, sender=User)
def guardar_perfil(sender, instance, **kwargs):
    if hasattr(instance, 'perfil'):
        instance.perfil.save()