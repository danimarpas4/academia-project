from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login
from django.contrib.auth.forms import UserCreationForm
from django.utils import timezone
from django.db.models import Avg, Count, Q
from django.contrib import messages 
from django.http import HttpResponse, Http404, FileResponse, JsonResponse
from django.conf import settings
from .models import Tema, Pregunta, Examen, Opcion, Resultado, Perfil, Curso
import random
import io
import logging
import os
import hashlib
import json
import google.generativeai as genai
from pathlib import Path
from gtts import gTTS

logger = logging.getLogger(__name__)

# --- 1. GESTIÓN DE USUARIOS Y ACCESO ---

def landing(request):
    return render(request, "simulador/landing.html")

def inicio(request):
    return redirect("landing")

def registro(request):
    # Define a mapping from URL slugs to database names for robustness
    CURSO_SLUG_MAP = {
        "cabo": "Ascenso a Cabo",
        "cabo-primero": "Cabo Primero",
        "permanencia": "Permanencia", # Nuevo curso
    }

    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            
            # Get curso slug from the hidden form input
            curso_slug = request.POST.get("curso")
            if curso_slug and curso_slug in CURSO_SLUG_MAP: # Asegúrate de que el slug no esté vacío
                curso_nombre = CURSO_SLUG_MAP[curso_slug]
                try:
                    curso_a_inscribir = Curso.objects.get(nombre=curso_nombre)
                    # The post_save signal on User creates the profile, so we can access it here.
                    user.perfil.cursos_activos.add(curso_a_inscribir)
                except Curso.DoesNotExist:
                    # Log this event, as it indicates a mismatch between links and DB
                    logger.warning(f"Intento de registro para un curso no existente con slug: {curso_slug}")
            else:
                # Si no se especifica curso, o el slug es inválido, no se inscribe en ninguno
                logger.info(f"Registro sin curso específico o con slug inválido: {curso_slug}")

            user.backend = "django.contrib.auth.backends.ModelBackend" 
            login(request, user)
            return redirect("portada")
    else:
        # Handle GET request
        form = UserCreationForm()
        curso_slug = request.GET.get("curso")

    # Pass slug to template for the hidden input
    context = {
        "form": form,
        "curso_slug": curso_slug
    }
    return render(request, "registration/registro.html", context)

# --- 2. DASHBOARD Y PERFIL ---

@login_required
def portada(request):
    perfil, created = Perfil.objects.get_or_create(usuario=request.user)
    
    # Lógica de días de prueba
    dias_prueba = 15
    diferencia = timezone.now() - request.user.date_joined
    dias_restantes = max(0, dias_prueba - diferencia.days)
    esta_en_prueba = (perfil.cursos_activos.count() == 0)

    # Ranking Global
    ranking = Perfil.objects.select_related("usuario").order_by("-preguntas_respondidas")[:50]
    mi_posicion = Perfil.objects.filter(preguntas_respondidas__gt=perfil.preguntas_respondidas).count() + 1

    contexto = {
        "esta_en_prueba": esta_en_prueba,
        "dias_restantes": dias_restantes,
        "perfil": perfil,
        "ranking": ranking,
        "mi_posicion": mi_posicion,
    }
    return render(request, "simulador/portada.html", contexto)

@login_required
def perfil(request):
    perfil, created = Perfil.objects.get_or_create(usuario=request.user)
    return render(request, "simulador/perfil.html", {"perfil": perfil})

@login_required
def estadisticas(request):
    perfil, created = Perfil.objects.get_or_create(usuario=request.user)
    intentos = Resultado.objects.filter(usuario=request.user)
    
    context = {
        "perfil": perfil,
        "total_intentos": intentos.count(),
        "promedio_nota": round(intentos.aggregate(Avg("nota"))["nota__avg"] or 0, 2),
        "total_preguntas": perfil.preguntas_respondidas,
        "datos_grafico": intentos.order_by("fecha")[:10],
        "ranking": Perfil.objects.select_related("usuario").order_by("-preguntas_respondidas")[:50],
    }
    return render(request, "simulador/estadisticas.html", context)

# --- 3. MOTOR DE EXÁMENES (Separación Estricta por Materia) ---

@login_required
def configurar_test(request):
    """
    Separamos los temas en 4 bloques estrictos para la interfaz.
    Cada lista alimenta un acordeón independiente en el HTML.
    """
    context = {
        "temas_cabo": Tema.objects.filter(Q(materia="CABO") | Q(materia__isnull=True)),
        "temas_ingles": Tema.objects.filter(materia="INGLÉS"),
        "temas_geografia": Tema.objects.filter(materia="GEOGRAFÍA"),
        "temas_informatica": Tema.objects.filter(materia="INFORMÁTICA"),
    }
    return render(request, "simulador/configurar_test.html", context)

@login_required
def generar_test(request):
    """ Crea un objeto Examen seleccionando preguntas de las materias elegidas """
    if request.method == "POST":
        temas_ids = request.POST.getlist("temas")
        cantidad = int(request.POST.get("cantidad", 10))
        
        # Filtramos preguntas que pertenezcan a los temas seleccionados
        preguntas_pool = list(Pregunta.objects.filter(tema_id__in=temas_ids))
        
        if not preguntas_pool:
            messages.error(request, "No hay preguntas disponibles para la selección actual.")
            return redirect("configurar_test")

        # Ajustamos cantidad si el pool es pequeño
        cantidad = min(len(preguntas_pool), cantidad)
        seleccionadas = random.sample(preguntas_pool, cantidad)

        # Creamos la sesión de examen en la base de datos
        nuevo_examen = Examen.objects.create(usuario=request.user)
        nuevo_examen.preguntas.set(seleccionadas)
        
        return redirect("ver_examen", examen_id=nuevo_examen.id)
        
    return redirect("configurar_test")

@login_required
def ver_examen(request, examen_id):
    """ Muestra y corrige un examen específico """
    examen_obj = get_object_or_404(Examen, id=examen_id, usuario=request.user)
    
    if request.method == "POST":
        aciertos = 0
        total = examen_obj.preguntas.count()
        
        for pregunta in examen_obj.preguntas.all():
            respuesta_id = request.POST.get(f"pregunta_{pregunta.id}")
            if respuesta_id:
                try:
                    opcion = Opcion.objects.get(id=respuesta_id, pregunta=pregunta)
                    if opcion.es_correcta:
                        aciertos += 1
                except Opcion.DoesNotExist:
                    pass
        
        nota = (aciertos / total * 10) if total > 0 else 0
        examen_obj.completado = True
        examen_obj.save()

        # Actualizar perfil del alumno (puntos y rango)
        perfil = request.user.perfil
        perfil.preguntas_respondidas += total
        perfil.save()
        perfil.comprobar_ascenso()

        # Registrar el resultado final
        res = Resultado.objects.create(
            usuario=request.user,
            examen=examen_obj,
            nota=nota,
            aciertos=aciertos,
            fallos=total - aciertos
        )
        return redirect("resultado", resultado_id=res.id)

    return render(request, "simulador/examen.html", {"examen": examen_obj})

@login_required
def examen(request):
    """
    Redirige al examen activo o al configurador
    """
    ultimo = Examen.objects.filter(usuario=request.user, completado=False).last()
    if ultimo:
        return redirect("ver_examen", examen_id=ultimo.id)
    return redirect("configurar_test")

@login_required
def resultado(request, resultado_id):
    res = get_object_or_404(Resultado, id=resultado_id, usuario=request.user)
    return render(request, "simulador/resultado.html", {"resultado": res})

# --- 4. TEMARIO Y MP3 ---

@login_required
def ver_temario(request):
    temas = Tema.objects.all().order_by("materia", "capitulo", "numero_tema")
    return render(request, "simulador/temario.html", {"temas": temas})

@login_required
def descargar_tema_mp3(request, tema_id):
    tema = get_object_or_404(Tema, id=tema_id)
    
    if tema.archivo_audio:
        return FileResponse(tema.archivo_audio.open(), content_type="audio/mpeg")

    if not tema.contenido_texto:
        messages.error(request, "Este tema no tiene texto para generar audio.")
        return redirect("ver_temario")

    cache_dir = Path(settings.MEDIA_ROOT) / "audio_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    
    contenido_hash = hashlib.md5(tema.contenido_texto.encode("utf-8")).hexdigest()
    mp3_path = cache_dir / f"tema_{tema.id}_{contenido_hash[:8]}.mp3"

    if not mp3_path.exists():
        try:
            tts = gTTS(text=tema.contenido_texto[:5000], lang="es")
            tts.save(str(mp3_path))
        except Exception as e:
            logger.error(f"Error gTTS: {e}")
            return redirect("ver_temario")

    return FileResponse(open(mp3_path, "rb"), content_type="audio/mpeg")



# --- 5. PASARELA DE PAGOS ---



@login_required

def iniciar_pago(request):

    cursos = Curso.objects.all()

    return render(request, "simulador/bloqueo_pago.html", {"cursos": cursos})



@login_required

def pago_exitoso(request):

    messages.success(request, "Pago verificado. ¡Instrucción completa desbloqueada!")

    return redirect("portada")



@login_required

def pago_cancelado(request):

    messages.warning(request, "Operación de pago cancelada.")

    return redirect("portada")



# --- 6. INSTRUCTOR IA ---



@login_required
def ask_ia_instructor(request):
    if request.method != "POST":
        return JsonResponse({"error": "Solo se permiten peticiones POST."}, status=405)

    try:
        data = json.loads(request.body)
        question = data.get("question")
        tema_id = data.get("tema_id")

        if not question:
            return JsonResponse({"error": "El parámetro \"question\" es obligatorio."}, status=400)

        context_text = ""
        # 1. Obtener contexto del tema si se proporciona
        if tema_id:
            try:
                tema = Tema.objects.get(id=tema_id)
                if tema.contenido_texto:
                    context_text = tema.contenido_texto
            except Tema.DoesNotExist:
                pass
        
        # 2. Configuración de Gemini (Usando la API Key del .env vía settings)
        api_key = settings.GEMINI_API_KEY
        if not api_key:
            return JsonResponse({"error": "Error: API Key de Gemini no configurada."}, status=500)

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-1.5-flash")

        # 3. Construir el prompt
        instrucciones_base = "Eres un instructor militar experto de la academia ProMilitar. Responde de forma clara, profesional y concisa."
        
        if context_text:
            prompt = f"{instrucciones_base}\n\nUsa este fragmento del temario para responder:\n{context_text[:30000]}\n\nDuda del alumno: {question}\n\nInstrucción: Si la respuesta no está en el texto, indícalo pero trata de orientar al alumno con tu conocimiento general siempre en un contexto de ascenso militar."
        else:
            prompt = f"{instrucciones_base}\n\nDuda del alumno: {question}"

        response = model.generate_content(prompt)
        return JsonResponse({"answer": response.text})

    except Exception as e:
        logger.error(f"Error en Instructor IA: {e}")
        return JsonResponse({"error": "Error interno del servidor."}, status=500)
