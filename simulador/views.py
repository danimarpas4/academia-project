from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login
from django.contrib.auth.forms import UserCreationForm
from django.utils import timezone
from django.db.models import Avg, Count, Q
from django.contrib import messages 
from django.http import HttpResponse, Http404, FileResponse
from django.conf import settings
from .models import Tema, Pregunta, Opcion, Resultado, Perfil, Curso
import random
import io
import logging
import os
import hashlib
from pathlib import Path
from gtts import gTTS

logger = logging.getLogger(__name__)

# --- 1. GESTIÓN DE USUARIOS Y ACCESO ---

def inicio(request):
    if request.user.is_authenticated:
        return redirect('portada')
    return render(request, 'simulador/inicio.html')

def registro(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            # --- FIX IMPORTANTE PARA EL ERROR DE LOGIN ---
            user.backend = 'django.contrib.auth.backends.ModelBackend' 
            login(request, user)
            return redirect('portada')
    else:
        form = UserCreationForm()
    return render(request, 'registration/registro.html', {'form': form})

# --- 2. DASHBOARD Y PERFIL ---

@login_required
def portada(request):
    perfil, created = Perfil.objects.get_or_create(usuario=request.user)
    
    # Lógica de días restantes
    dias_prueba = 15
    diferencia = timezone.now() - request.user.date_joined
    dias_restantes = max(0, dias_prueba - diferencia.days)
    esta_en_prueba = (perfil.cursos_activos.count() == 0)

    # Ranking
    ranking = Perfil.objects.select_related('usuario').order_by('-preguntas_respondidas')[:50]
    mi_posicion = Perfil.objects.filter(preguntas_respondidas__gt=perfil.preguntas_respondidas).count() + 1

    contexto = {
        'esta_en_prueba': esta_en_prueba,
        'dias_restantes': dias_restantes,
        'perfil': perfil,
        'ranking': ranking,
        'mi_posicion': mi_posicion,
    }
    return render(request, 'simulador/portada.html', contexto)

@login_required
def perfil(request):
    return render(request, 'simulador/perfil.html', {'perfil': request.user.perfil})

@login_required
def estadisticas(request):
    perfil, created = Perfil.objects.get_or_create(usuario=request.user)
    intentos = Resultado.objects.filter(usuario=request.user)
    
    context = {
        'perfil': perfil,
        'total_intentos': intentos.count(),
        'promedio_nota': round(intentos.aggregate(Avg('nota'))['nota__avg'] or 0, 2),
        'total_preguntas': perfil.preguntas_respondidas,
        'datos_grafico': intentos.order_by('fecha')[:10],
        'ranking': Perfil.objects.select_related('usuario').order_by('-preguntas_respondidas')[:50],
    }
    return render(request, 'simulador/estadisticas.html', context)

# --- 3. MOTOR DE EXÁMENES (NUEVO SISTEMA) ---

@login_required
def configurar_test(request):
    if request.method == 'POST':
        # Recogemos configuración
        temas_ids = request.POST.getlist('temas')
        cantidad = int(request.POST.get('cantidad', 10))
        tiempo = int(request.POST.get('tiempo', 0))

        if not temas_ids:
            temas_ids = list(Tema.objects.values_list('id', flat=True))

        # Guardamos en sesión
        request.session['config_test'] = {
            'temas_ids': temas_ids,
            'cantidad': cantidad,
            'tiempo': tiempo
        }
        return redirect('examen') # Redirige a la vista examen (sin ID)

    # GET: Mostrar formulario
    temas = Tema.objects.annotate(num_preguntas=Count('preguntas')).filter(num_preguntas__gt=0).order_by('nombre')
    return render(request, 'simulador/configurar_test.html', {'temas': temas})

@login_required
def examen(request):
    # 1. Si es POST, es que está ENTREGANDO el examen para corregir
    if request.method == 'POST':
        puntuacion = 0
        total_respondidas = 0
        
        # Iteramos sobre los datos recibidos para buscar respuestas
        # Los inputs en el HTML se llaman "pregunta_ID"
        for key, value in request.POST.items():
            if key.startswith('pregunta_'):
                total_respondidas += 1 # Contamos cuántas intentó (aunque esto es relativo)
                opcion_id = value
                try:
                    opcion = Opcion.objects.get(id=opcion_id)
                    if opcion.es_correcta:
                        puntuacion += 1
                except Opcion.DoesNotExist:
                    pass
        
        # Recuperamos cuántas preguntas eran en total desde la sesión para la nota real
        config = request.session.get('config_test', {})
        total_preguntas = config.get('cantidad', total_respondidas)
        
        # Cálculo de nota
        nota = (puntuacion / total_preguntas) * 10 if total_preguntas > 0 else 0
        
        # Guardar en Perfil
        perfil = request.user.perfil
        perfil.preguntas_respondidas += total_preguntas
        perfil.save()
        
        if hasattr(perfil, 'comprobar_ascenso'):
             if perfil.comprobar_ascenso():
                 messages.success(request, f"¡ASCENSO! Nuevo rango: {perfil.rango} 🎖️")

        # Guardar Resultado
        # Nota: Como es multipregunta, asignamos al primer tema o "General"
        tema_ref = Tema.objects.filter(id__in=config.get('temas_ids', [])).first()
        
        resultado = Resultado.objects.create(
            usuario=request.user,
            tema=tema_ref, # Referencia
            nota=nota,
            aciertos=puntuacion,
            fallos=total_preguntas - puntuacion
        )
        return redirect('resultado', resultado_id=resultado.id)

    # 2. Si es GET, está EMPEZANDO el examen
    config = request.session.get('config_test')
    if not config:
        return redirect('configurar_test')

    temas_ids = config['temas_ids']
    cantidad = config['cantidad']
    tiempo = config['tiempo']

    preguntas_pool = list(Pregunta.objects.filter(tema__id__in=temas_ids))
    
    if len(preguntas_pool) < cantidad:
        cantidad = len(preguntas_pool)
        
    preguntas_seleccionadas = random.sample(preguntas_pool, cantidad)

    return render(request, 'simulador/examen.html', {
        'preguntas': preguntas_seleccionadas,
        'tiempo_limite': tiempo
    })

@login_required
def resultado(request, resultado_id):
    resultado_obj = get_object_or_404(Resultado, id=resultado_id, usuario=request.user)
    return render(request, 'simulador/resultado.html', {'resultado': resultado_obj})

# --- 4. TEMARIO Y MP3 ---

@login_required
def ver_temario(request):
    temas = Tema.objects.filter(
        (Q(archivo_pdf__isnull=False) & ~Q(archivo_pdf='')) | 
        (Q(contenido_texto__isnull=False) & ~Q(contenido_texto=''))
    ).distinct().order_by('nombre')
    return render(request, 'simulador/temario.html', {'temas': temas})

@login_required
def descargar_tema_mp3(request, tema_id):
    tema = get_object_or_404(Tema, id=tema_id)
    if not tema.contenido_texto:
        return redirect('ver_temario')

    # Lógica simplificada de caché
    cache_dir = Path(settings.MEDIA_ROOT) / 'audio_cache'
    cache_dir.mkdir(parents=True, exist_ok=True)
    contenido_hash = hashlib.md5(tema.contenido_texto.encode('utf-8')).hexdigest()
    mp3_path = cache_dir / f"tema_{tema.id}_{contenido_hash[:8]}.mp3"

    if not mp3_path.exists():
        try:
            tts = gTTS(text=tema.contenido_texto[:5000], lang="es") # Limitado por seguridad
            tts.save(str(mp3_path))
        except Exception as e:
            return redirect('ver_temario')

    return FileResponse(open(mp3_path, 'rb'), content_type="audio/mpeg")

# --- 5. PAGOS ---

@login_required
def iniciar_pago(request):
    cursos = Curso.objects.all()
    return render(request, 'simulador/bloqueo_pago.html', {'cursos': cursos})

@login_required
def pago_exitoso(request):
    return render(request, 'simulador/pago_exitoso.html')

@login_required
def pago_cancelado(request):
    return render(request, 'simulador/pago_cancelado.html')