from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login
from django.contrib.auth.forms import UserCreationForm
from django.utils import timezone
from django.db.models import Avg, Count
from django.contrib.auth.models import User
from django.contrib import messages 
from django.db import models
from .models import Tema, Pregunta, Opcion, Resultado, Perfil, Curso

from django.http import HttpResponse, Http404, FileResponse
from django.conf import settings
from gtts import gTTS
import io
import logging
import os
from pathlib import Path
import hashlib

logger = logging.getLogger(__name__)

# --- VISTA PÚBLICA (INICIO) ---
def inicio(request):
    if request.user.is_authenticated:
        return redirect('portada')
    return render(request, 'simulador/inicio.html')

# --- REGISTRO DE USUARIOS ---
def registro(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save() 
            # El signal crea el perfil automáticamente
            login(request, user)
            return redirect('portada')
    else:
        form = UserCreationForm()
    return render(request, 'registration/registro.html', {'form': form})

# --- VISTAS DEL DASHBOARD (PRIVADO) ---

# En academia_project/simulador/views.py

@login_required
def portada(request):
    # Obtenemos el perfil
    perfil, created = Perfil.objects.get_or_create(usuario=request.user)
    
    # Lógica de días restantes
    dias_prueba = 15
    diferencia = timezone.now() - request.user.date_joined
    dias_restantes = dias_prueba - diferencia.days

    # Comprobamos cursos
    num_cursos = perfil.cursos_activos.count()
    esta_en_prueba = (num_cursos == 0)

    # --- LÓGICA DEL RANKING (NUEVO) ---
    # 1. Obtener los 50 mejores por preguntas respondidas
    ranking = Perfil.objects.select_related('usuario').order_by('-preguntas_respondidas')[:50]
    
    # 2. Calcular la posición exacta del usuario actual
    # Contamos cuántos usuarios tienen más preguntas respondidas que el usuario actual y sumamos 1
    mi_posicion = Perfil.objects.filter(preguntas_respondidas__gt=perfil.preguntas_respondidas).count() + 1
    # ----------------------------------

    contexto = {
        'esta_en_prueba': esta_en_prueba,
        'dias_restantes': dias_restantes,
        'usuario': request.user,
        'perfil': perfil,
        'cursos_activos': perfil.cursos_activos.all(),
        # Nuevas variables para el template
        'ranking': ranking,
        'mi_posicion': mi_posicion,
    }
    return render(request, 'simulador/portada.html', contexto)

@login_required
def ver_temario(request):
    # Mostramos solo temas que tienen PDF o contenido_texto para descargar/escuchar
    from django.db.models import Q
    temas = Tema.objects.filter(
        (Q(archivo_pdf__isnull=False) & ~Q(archivo_pdf='')) | 
        (Q(contenido_texto__isnull=False) & ~Q(contenido_texto=''))
    ).distinct().order_by('nombre')
    return render(request, 'simulador/temario.html', {'temas': temas})


@login_required
def descargar_tema_mp3(request, tema_id):
    """
    Genera y devuelve un MP3 con el contenido del tema.
    Usa caché para evitar regenerar el MP3 cada vez.
    """
    tema = get_object_or_404(Tema, id=tema_id)

    if not tema.contenido_texto or not tema.contenido_texto.strip():
        logger.warning(f"Intento de generar MP3 para tema {tema_id} sin contenido_texto")
        messages.error(request, "Este tema aún no tiene contenido de texto para convertir a audio.")
        return redirect('ver_temario')

    try:
        # Directorio para caché de MP3s
        cache_dir = Path(settings.MEDIA_ROOT) / 'audio_cache'
        cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Generar hash del contenido para saber si el MP3 está actualizado
        texto = tema.contenido_texto.strip()
        contenido_hash = hashlib.md5(texto.encode('utf-8')).hexdigest()
        mp3_filename = f"tema_{tema.id}_{contenido_hash[:8]}.mp3"
        mp3_path = cache_dir / mp3_filename
        
        # Si el MP3 ya existe en caché, servirlo directamente
        if mp3_path.exists():
            logger.info(f"Sirviendo MP3 desde caché para tema {tema_id}")
            is_download = request.GET.get('download', 'false').lower() == 'true'
            response = FileResponse(
                open(mp3_path, 'rb'),
                content_type="audio/mpeg"
            )
            filename = f"tema_{tema.id}_{tema.nombre[:30]}.mp3".replace(" ", "_").replace("/", "_")
            if is_download:
                response["Content-Disposition"] = f'attachment; filename="{filename}"'
            else:
                response["Content-Disposition"] = f'inline; filename="{filename}"'
            return response
        
        # Si no existe, generarlo
        logger.info(f"Generando MP3 para tema {tema_id} ({tema.nombre}), texto de {len(texto)} caracteres")
        
        # Dividir el texto en fragmentos si es muy largo (gTTS tiene límites)
        max_chars_per_chunk = 4000
        chunks = []
        
        if len(texto) > max_chars_per_chunk:
            paragraphs = texto.split('\n\n')
            current_chunk = ""
            
            for para in paragraphs:
                if len(current_chunk) + len(para) + 2 <= max_chars_per_chunk:
                    current_chunk += para + "\n\n" if current_chunk else para + "\n\n"
                else:
                    if current_chunk:
                        chunks.append(current_chunk.strip())
                    if len(para) > max_chars_per_chunk:
                        sentences = para.split('. ')
                        current_chunk = ""
                        for sent in sentences:
                            if len(current_chunk) + len(sent) + 2 <= max_chars_per_chunk:
                                current_chunk += sent + ". " if current_chunk else sent + ". "
                            else:
                                if current_chunk:
                                    chunks.append(current_chunk.strip())
                                current_chunk = sent + ". "
                        if current_chunk:
                            chunks.append(current_chunk.strip())
                            current_chunk = ""
                    else:
                        current_chunk = para + "\n\n"
            
            if current_chunk:
                chunks.append(current_chunk.strip())
        else:
            chunks = [texto]
        
        logger.info(f"Texto dividido en {len(chunks)} fragmentos")
        
        # Generar audio para cada fragmento y combinarlos
        mp3_buffers = []
        for i, chunk in enumerate(chunks):
            logger.info(f"Generando audio para fragmento {i+1}/{len(chunks)} ({len(chunk)} caracteres)")
            try:
                tts = gTTS(text=chunk, lang="es", slow=False)
                chunk_buffer = io.BytesIO()
                tts.write_to_fp(chunk_buffer)
                chunk_buffer.seek(0)
                mp3_buffers.append(chunk_buffer.read())
            except Exception as e:
                logger.error(f"Error al generar fragmento {i+1}: {str(e)}")
                raise
        
        # Combinar todos los fragmentos
        mp3_data = b''.join(mp3_buffers)
        logger.info(f"MP3 generado correctamente, tamaño total: {len(mp3_data)} bytes")
        
        # Limpiar MP3s obsoletos del mismo tema antes de guardar el nuevo
        tema_pattern = f"tema_{tema.id}_*.mp3"
        for old_file in cache_dir.glob(tema_pattern):
            if old_file != mp3_path and old_file.exists():
                try:
                    old_file.unlink()
                    logger.info(f"MP3 obsoleto eliminado: {old_file.name}")
                except Exception as e:
                    logger.warning(f"No se pudo eliminar MP3 obsoleto {old_file.name}: {str(e)}")
        
        # Guardar en caché
        with open(mp3_path, 'wb') as f:
            f.write(mp3_data)
        logger.info(f"MP3 guardado en caché: {mp3_path}")

        # Determinar si es una descarga directa o reproducción en el navegador
        is_download = request.GET.get('download', 'false').lower() == 'true'
        
        response = HttpResponse(mp3_data, content_type="audio/mpeg")
        filename = f"tema_{tema.id}_{tema.nombre[:30]}.mp3".replace(" ", "_").replace("/", "_")
        
        if is_download:
            response["Content-Disposition"] = f'attachment; filename="{filename}"'
        else:
            response["Content-Disposition"] = f'inline; filename="{filename}"'
            response["Accept-Ranges"] = "bytes"
            response["Content-Length"] = str(len(mp3_data))
        
        return response
        
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        logger.error(f"Error al generar MP3 para tema {tema.id}: {str(e)}\n{error_trace}")
        messages.error(request, f"Error al generar el archivo de audio: {str(e)}")
        return redirect('ver_temario')

@login_required
def configurar_test(request):
    if request.method == 'POST':
        tema_id = request.POST.get('tema_seleccionado')
        if tema_id:
            return redirect('examen', tema_id=tema_id)
            
    # Mostrar todos los temas que tienen preguntas disponibles para hacer tests
    # Usamos annotate para contar las preguntas y filtramos solo los que tienen al menos 1
    temas = Tema.objects.annotate(
        num_preguntas=Count('preguntas')
    ).filter(num_preguntas__gt=0).order_by('nombre')
    
    return render(request, 'simulador/configurar_test.html', {'temas': temas})

@login_required
def estadisticas(request):
    resultados = Resultado.objects.filter(usuario=request.user).order_by('-fecha')
    
    promedio = resultados.aggregate(Avg('nota'))['nota__avg']
    promedio = round(promedio, 1) if promedio else 0
    total_tests = resultados.count()

    # Ranking
    ranking_usuarios = User.objects.annotate(media_global=Avg('resultado__nota')) \
                                   .filter(media_global__isnull=False) \
                                   .order_by('-media_global')
    
    mi_posicion = "-"
    total_alumnos = ranking_usuarios.count()
    
    for index, user_rank in enumerate(ranking_usuarios):
        if user_rank.id == request.user.id:
            mi_posicion = index + 1
            break

    ultimos_10 = resultados[:10][::-1]
    fechas_grafica = [r.fecha.strftime("%d/%m") for r in ultimos_10]
    notas_grafica = [float(r.nota) for r in ultimos_10]

    contexto = {
        'resultados': resultados,
        'promedio': promedio,
        'total_tests': total_tests,
        'fechas_grafica': fechas_grafica,
        'notas_grafica': notas_grafica,
        'mi_posicion': mi_posicion,
        'total_alumnos': total_alumnos
    }
    return render(request, 'simulador/estadisticas.html', contexto)

# --- VISTAS DEL EXAMEN ---

@login_required
def examen(request, tema_id):
    tema = get_object_or_404(Tema, id=tema_id)
    perfil = request.user.perfil
    
    # --- SEGURIDAD DE CURSOS ---
    # Verificamos si el usuario tiene el curso al que pertenece este tema
    if tema.curso: # Si el tema tiene un curso asignado
        if tema.curso not in perfil.cursos_activos.all():
            messages.error(request, "No tienes acceso a este curso. Por favor, suscríbete.")
            return redirect('iniciar_pago')
    
    # Lógica de días de prueba (Opcional, si quieres mantenerla)
    diferencia = timezone.now() - request.user.date_joined
    if perfil.cursos_activos.count() == 0 and diferencia.days > 15:
         return redirect('iniciar_pago')

    if request.method == 'POST':
        puntuacion = 0
        total_preguntas = tema.preguntas.count()
        
        for pregunta in tema.preguntas.all():
            respuesta_id = request.POST.get(f'pregunta_{pregunta.id}')
            if respuesta_id:
                opcion = Opcion.objects.get(id=respuesta_id)
                if opcion.es_correcta:
                    puntuacion += 1
        
        nota = (puntuacion / total_preguntas) * 10 if total_preguntas > 0 else 0
        
        # Guardar progreso
        perfil.preguntas_respondidas += total_preguntas
        perfil.save() # Guardamos para asegurar

        if hasattr(perfil, 'comprobar_ascenso'):
            ascendido = perfil.comprobar_ascenso()
            if ascendido:
                messages.success(request, f"¡ENHORABUENA! Has ascendido al rango de {perfil.rango} 🎖️")

        resultado = Resultado.objects.create(
            usuario=request.user,
            tema=tema,
            nota=nota,
            aciertos=puntuacion,
            fallos=total_preguntas - puntuacion
        )
        return redirect('resultado', resultado_id=resultado.id)

    return render(request, 'simulador/examen.html', {'tema': tema})

@login_required
def resultado(request, resultado_id):
    resultado_obj = get_object_or_404(Resultado, id=resultado_id, usuario=request.user)
    return render(request, 'simulador/resultado.html', {'resultado': resultado_obj})

# --- PAGOS Y PERFIL ---

@login_required
def iniciar_pago(request):
    # Aquí deberías mostrar los cursos disponibles para comprar
    cursos = Curso.objects.all()
    return render(request, 'simulador/bloqueo_pago.html', {'cursos': cursos})

@login_required
def pago_exitoso(request):
    # NOTA: Aquí necesitarás lógica para saber QUÉ curso compró.
    # Por ahora solo mostramos la página de éxito para no dar error.
    return render(request, 'simulador/pago_exitoso.html')

@login_required
def pago_cancelado(request):
    return render(request, 'simulador/pago_cancelado.html')

@login_required
def perfil(request):
    return render(request, 'simulador/perfil.html', {'perfil': request.user.perfil})