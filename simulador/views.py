from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import login
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.utils import timezone
from django.db.models import Avg, Count, Q
from django.contrib import messages 
from django.http import HttpResponse, Http404, HttpResponseForbidden, FileResponse, JsonResponse
from django.conf import settings
from .models import Tema, Pregunta, Examen, Opcion, Resultado, Perfil, Curso, HistorialDescuento, DocumentoContexto
from .redsys_payment import RedsysPayment

import random
import logging
import os
import hashlib
import json
import re
import requests
from datetime import datetime
from pathlib import Path
from decimal import Decimal
from gtts import gTTS

logger = logging.getLogger(__name__)

# --- 1. GESTIÓN DE USUARIOS Y ACCESO ---

def landing(request):
    return render(request, "simulador/landing.html")

def inicio(request):
    return redirect("landing")

CURSOS_DISPONIBLES = {
    'cabo': {'nombre': 'Ascenso a Cabo', 'activo': True},
    'cabo-primero': {'nombre': 'Cabo Primero', 'activo': True},
    'permanencia': {'nombre': 'Permanencia', 'activo': False},
}

def signup_course(request, curso_slug):
    if request.user.is_authenticated:
        return redirect("portada")
    
    if curso_slug not in CURSOS_DISPONIBLES or not CURSOS_DISPONIBLES[curso_slug]['activo']:
        messages.error(request, "Este curso aún no está disponible.")
        return redirect("landing")
    
    request.session['curso_seleccionado'] = curso_slug
    return redirect("registro")

def registro(request):
    CURSO_SLUG_MAP = {
        "cabo": "Ascenso a Cabo",
        "cabo-primero": "Cabo Primero",
        "permanencia": "Permanencia", 
    }

    codigo_referido = request.GET.get("ref", "")

    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            
            curso_slug = request.POST.get("curso")
            if curso_slug and curso_slug in CURSO_SLUG_MAP:
                curso_nombre = CURSO_SLUG_MAP[curso_slug]
                try:
                    curso_a_inscribir = Curso.objects.get(nombre=curso_nombre)
                    user.perfil.cursos_activos.add(curso_a_inscribir)
                except Curso.DoesNotExist:
                    logger.warning(f"Intento de registro para un curso no existente: {curso_slug}")
            else:
                logger.info(f"Registro sin curso específico: {curso_slug}")

            codigo_ref = request.POST.get("codigo_referido", "").strip()
            if codigo_ref:
                try:
                    perfil_referidor = Perfil.objects.get(codigo_referido=codigo_ref.upper())
                    if perfil_referidor.usuario != user:
                        user.perfil.referido_por = perfil_referidor.usuario
                        user.perfil.descuento_acumulado += 3.00
                        user.perfil.save()
                        perfil_referidor.descuento_acumulado += 5.00
                        perfil_referidor.save()
                        
                        HistorialDescuento.objects.create(
                            usuario=user,
                            motivo='ALTA_REFERIDO',
                            cuantia=Decimal('3.00'),
                            saldo_resultante=user.perfil.descuento_acumulado
                        )
                        HistorialDescuento.objects.create(
                            usuario=perfil_referidor.usuario,
                            motivo='RECOMPENSA_RECLUTA',
                            cuantia=Decimal('5.00'),
                            saldo_resultante=perfil_referidor.descuento_acumulado
                        )
                        
                        logger.info(
                            f"[REFERRAL FRAUD-PREVENTION] Usuario {user.username} (ID:{user.id}) "
                            f"se registró con referido de {perfil_referidor.usuario.username} (ID:{perfil_referidor.usuario.id}). "
                            f"Descuento aplicado: nuevo usuario +3.00€ (total: {user.perfil.descuento_acumulado}€), "
                            f"referidor +5.00€ (total: {perfil_referidor.descuento_acumulado}€). "
                            f"Código usado: {codigo_ref.upper()}"
                        )
                except Perfil.DoesNotExist:
                    logger.warning(f"[REFERRAL FRAUD-PREVENTION] Código de referido inválido: {codigo_ref}")

            user.backend = "django.contrib.auth.backends.ModelBackend" 
            login(request, user)
            
            curso_seleccionado = request.session.pop('curso_seleccionado', None)
            if curso_seleccionado and curso_seleccionado in CURSOS_DISPONIBLES:
                request.session['curso_a_pagar'] = curso_seleccionado
            
            return redirect("portada")
    else:
        form = UserCreationForm()

    curso_seleccionado = request.session.get('curso_seleccionado', request.GET.get("curso"))
    if curso_seleccionado in CURSOS_DISPONIBLES:
        curso_info = CURSOS_DISPONIBLES[curso_seleccionado]
    else:
        curso_info = None

    context = {
        "form": form,
        "curso_slug": curso_seleccionado,
        "curso_info": curso_info,
        "codigo_referido": codigo_referido
    }
    return render(request, "registration/registro.html", context)

# --- 2. DASHBOARD Y PERFIL ---

@login_required
def portada(request):
    perfil, created = Perfil.objects.get_or_create(usuario=request.user)
    
    curso_a_pagar = request.session.pop('curso_a_pagar', None)
    
    dias_prueba = 15
    diferencia = timezone.now() - request.user.date_joined
    dias_restantes = max(0, dias_prueba - diferencia.days)
    esta_en_prueba = (perfil.cursos_activos.count() == 0)

    ranking = Perfil.objects.select_related("usuario").order_by("-preguntas_respondidas")[:50]
    mi_posicion = Perfil.objects.filter(preguntas_respondidas__gt=perfil.preguntas_respondidas).count() + 1

    site_url = request.build_absolute_uri('/').rstrip('/')
    referral_link = f"{site_url}/registro/?ref={perfil.codigo_referido}"

    historial_descuento = HistorialDescuento.objects.filter(usuario=request.user)[:5]
    
    curso_activo = None
    if perfil.cursos_activos.exists():
        curso_activo = perfil.cursos_activos.first()
    
    cursos_disponibles = CURSOS_DISPONIBLES
    
    referidos_count = User.objects.filter(perfil__referido_por=request.user).count()

    contexto = {
        "esta_en_prueba": esta_en_prueba,
        "dias_restantes": dias_restantes,
        "perfil": perfil,
        "es_premium": perfil.es_premium,
        "ranking": ranking,
        "mi_posicion": mi_posicion,
        "referral_code": perfil.codigo_referido,
        "referral_link": referral_link,
        "saldo_descuento": perfil.descuento_acumulado,
        "historial_descuento": historial_descuento,
        "precio_base": RedsysPayment.PRECIO_BASE,
        "curso_a_pagar": curso_a_pagar,
        "curso_activo": curso_activo,
        "cursos_disponibles": cursos_disponibles,
        "referidos_count": referidos_count,
    }
    
    if curso_a_pagar:
        messages.info(request, f"¡Estás a un paso! Completa tu inscripción al curso {CURSOS_DISPONIBLES.get(curso_a_pagar, {}).get('nombre', curso_a_pagar)}.")
    
    return render(request, "simulador/portada.html", contexto)

@login_required
def perfil(request):
    perfil, created = Perfil.objects.get_or_create(usuario=request.user)
    site_url = request.build_absolute_uri('/').rstrip('/')
    referral_link = f"{site_url}/registro/?ref={perfil.codigo_referido}"
    return render(request, "simulador/perfil.html", {
        "perfil": perfil,
        "referral_link": referral_link
    })

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


@login_required
def escalafon(request):
    """Vista del Escalafón de Alumnos - Ranking por nota media"""
    perfil, created = Perfil.objects.get_or_create(usuario=request.user)
    
    # Obtener ranking de usuarios con al menos 1 test completado
    ranking_completo = (
        Resultado.objects
        .values('usuario__username', 'usuario__id')
        .annotate(
            nota_media=Avg('nota'),
            tests_completados=Count('id')
        )
        .filter(tests_completados__gte=1)
        .order_by('-nota_media')
    )
    
    # Top 10 general (para todos)
    top_10 = list(ranking_completo[:10])
    
    # Posición del usuario actual
    posicion_usuario = None
    nota_media_usuario = None
    tests_usuario = 0
    
    for i, item in enumerate(ranking_completo, 1):
        if item['usuario__id'] == request.user.id:
            posicion_usuario = i
            nota_media_usuario = round(item['nota_media'], 2)
            tests_usuario = item['tests_completados']
            break
    
    # Generar alias para cada usuario
    def generar_alias(username, user_id):
        """Genera un alias semi-anónimo"""
        primera = username[0].upper() if username else 'A'
        ultima = username[-1].upper() if username else 'Z'
        numero = (user_id % 100)
        return f"{primera}***{ultima}_{numero}"
    
    # Preparar datos con alias y posiciones
    ranking_con_posicion = []
    for i, item in enumerate(top_10, 1):
        ranking_con_posicion.append({
            'posicion': i,
            'alias': generar_alias(item['usuario__username'], item['usuario__id']),
            'nota_media': round(item['nota_media'], 2),
            'tests_completados': item['tests_completados'],
            'es_usuario': item['usuario__id'] == request.user.id,
        })
    
    context = {
        'perfil': perfil,
        'ranking': ranking_con_posicion,
        'posicion_usuario': posicion_usuario,
        'nota_media_usuario': nota_media_usuario,
        'tests_usuario': tests_usuario,
        'total_participantes': ranking_completo.count(),
    }
    
    return render(request, 'simulador/escalafon.html', context)

@login_required
def mis_referidos(request):
    perfil, created = Perfil.objects.get_or_create(usuario=request.user)
    referidos = User.objects.filter(perfil__referido_por=request.user).select_related('perfil')
    
    context = {
        "perfil": perfil,
        "codigo_referido": perfil.codigo_referido,
        "referidos": referidos,
        "total_referidos": referidos.count(),
    }
    return render(request, "simulador/referidos.html", context)

@login_required
def perfil_referidos(request):
    perfil, created = Perfil.objects.get_or_create(usuario=request.user)
    site_url = request.build_absolute_uri('/').rstrip('/')
    referral_link = f"{site_url}/registro/?ref={perfil.codigo_referido}"
    
    context = {
        "perfil": perfil,
        "codigo_referido": perfil.codigo_referido,
        "referral_link": referral_link,
    }
    return render(request, "simulador/perfil_referidos.html", context)

@login_required
def plan_premium(request):
    """
    Página que muestra el plan premium y motiva al usuario a suscribirse.
    """
    perfil = request.user.perfil
    precio_base = RedsysPayment.PRECIO_BASE
    saldo_descuento = perfil.descuento_acumulado
    
    importe_final = max(Decimal('0.00'), precio_base - saldo_descuento)
    
    context = {
        'perfil': perfil,
        'precio_base': precio_base,
        'saldo_descuento': saldo_descuento,
        'importe_final': importe_final,
    }
    return render(request, 'simulador/plan_premium.html', context)

# --- 3. MOTOR DE EXÁMENES ---

@login_required
def configurar_test(request):
    # Solo mostramos en pantalla los temas que tienen 1 o más preguntas.
    temas_con_preguntas = Tema.objects.annotate(num_preguntas=Count('preguntas')).filter(num_preguntas__gt=0)
    
    context = {
        "temas_cabo": temas_con_preguntas.filter(Q(materia="CABO") | Q(materia__isnull=True)),
        "temas_ingles": temas_con_preguntas.filter(materia="INGLÉS"),
        "temas_geografia": temas_con_preguntas.filter(materia="GEOGRAFÍA"),
        "temas_informatica": temas_con_preguntas.filter(materia="INFORMÁTICA"),
    }
    return render(request, "simulador/configurar_test.html", context)

@login_required
def generar_test(request):
    if request.method == "POST":
        temas_ids = request.POST.getlist("temas")
        cantidad = int(request.POST.get("cantidad", 10))
        
        # 1. Evitar colapsos si no marcan nada
        if not temas_ids:
            messages.warning(request, "⚠️ No has seleccionado ningún tema. Marca al menos una casilla de instrucción.")
            return redirect("configurar_test")
        
        preguntas_pool = list(Pregunta.objects.filter(tema_id__in=temas_ids))
        
        # 2. Seguro antifallos de Base de Datos
        if not preguntas_pool:
            messages.error(request, "❌ No hay preguntas en la base de datos para los temas seleccionados. Ejecuta /sincronizar/")
            return redirect("configurar_test")

        # FIX TÁCTICO: Purgar exámenes zombies (a medias) antes de crear uno nuevo
        Examen.objects.filter(usuario=request.user, completado=False).delete()

        cantidad = min(len(preguntas_pool), cantidad)
        seleccionadas = random.sample(preguntas_pool, cantidad)

        # 3. Creación Segura
        nuevo_examen = Examen.objects.create(usuario=request.user)
        nuevo_examen.preguntas.add(*seleccionadas) # Mucho más robusto en SQLite que set()
        
        # 4. Verificación de Integridad
        if nuevo_examen.preguntas.count() == 0:
            nuevo_examen.delete()
            messages.error(request, "Fallo crítico en la armería: El simulacro se ha generado vacío. Inténtalo de nuevo.")
            return redirect("configurar_test")
            
        return redirect("ver_examen", examen_id=nuevo_examen.id)
        
    return redirect("configurar_test")

@login_required
def ver_examen(request, examen_id):
    examen_obj = get_object_or_404(Examen, id=examen_id, usuario=request.user)
    perfil = request.user.perfil
    es_premium = perfil.es_premium
    
    MAX_PREGUNTAS_FREE = 10
    
    total_preguntas = examen_obj.preguntas.count()
    mostrar_aviso_free = False
    
    if not es_premium and total_preguntas > MAX_PREGUNTAS_FREE:
        preguntas_limite = list(examen_obj.preguntas.all()[:MAX_PREGUNTAS_FREE])
        examen_obj.preguntas.set(preguntas_limite)
        mostrar_aviso_free = True
    
    if examen_obj.preguntas.count() == 0:
        examen_obj.delete()
        messages.warning(request, "⚠️ Has entrado en un simulacro corrupto o antiguo. Ha sido purgado, genera uno nuevo por favor.")
        return redirect("configurar_test")
    
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

        perfil.preguntas_respondidas += total
        perfil.save()
        perfil.comprobar_ascenso()

        res = Resultado.objects.create(
            usuario=request.user,
            examen=examen_obj,
            nota=nota,
            aciertos=aciertos,
            fallos=total - aciertos
        )
        return redirect("resultado", resultado_id=res.id)

    return render(request, "simulador/examen.html", {
        "examen": examen_obj, 
        "es_premium": es_premium, 
        "max_preguntas": MAX_PREGUNTAS_FREE if not es_premium else None,
        "mostrar_aviso_free": mostrar_aviso_free
    })

@login_required
def examen(request):
    # Purgar cualquier zombie que haya quedado flotando antes de intentar redirigir
    Examen.objects.filter(usuario=request.user, completado=False, preguntas__isnull=True).delete()
    
    ultimo = Examen.objects.filter(usuario=request.user, completado=False).last()
    if ultimo and ultimo.preguntas.count() > 0:
        return redirect("ver_examen", examen_id=ultimo.id)
    return redirect("configurar_test")

@login_required
def resultado(request, resultado_id):
    res = get_object_or_404(Resultado, id=resultado_id, usuario=request.user)
    return render(request, "simulador/resultado.html", {"resultado": res})

# --- 4. TEMARIO Y MP3 ---

@login_required
def ver_temario(request, curso_slug=None):
    temas = Tema.objects.all().order_by("materia", "capitulo", "numero_tema")
    perfil = request.user.perfil
    es_premium = perfil.es_premium
    
    primer_tema_id = temas.first().id if temas.exists() else None
    
    return render(request, "simulador/temario.html", {
        "temas": temas, 
        "es_premium": es_premium,
        "primer_tema_id": primer_tema_id
    })

@login_required
def descargar_tema_mp3(request, tema_id):
    perfil = request.user.perfil
    
    if not perfil.es_premium:
        logger.warning(f"[MP3] Usuario {request.user} sin premium intentó acceder al tema {tema_id}")
        return HttpResponseForbidden("⚠️ Acceso denegado. Suscripción Premium requerida.")
    
    tema = get_object_or_404(Tema, id=tema_id)
    
    if not tema.contenido_texto:
        messages.error(request, "Este tema no tiene texto para generar audio.")
        return redirect("ver_temario")
    
    audio_dir = Path(settings.MEDIA_ROOT) / "temas_audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    
    texto_contenido = tema.contenido_texto[:8000]
    contenido_hash = hashlib.md5(texto_contenido.encode("utf-8")).hexdigest()
    mp3_filename = f"tema_{tema.id}_{contenido_hash[:8]}.mp3"
    mp3_path = audio_dir / mp3_filename
    
    necesita_generar = False
    
    if tema.archivo_audio:
        archivo_bd = Path(settings.MEDIA_ROOT) / tema.archivo_audio.name
        if archivo_bd.exists():
            if archivo_bd.name == mp3_filename:
                logger.info(f"[MP3 CACHE] Hit: {mp3_filename} para tema {tema.id}")
                return FileResponse(open(archivo_bd, "rb"), content_type="audio/mpeg")
            else:
                logger.info(f"[MP3] Contenido cambió, regenerando para tema {tema.id}")
                archivo_bd.unlink(missing_ok=True)
                necesita_generar = True
        else:
            tema.archivo_audio = None
            tema.save(update_fields=['archivo_audio'])
            necesita_generar = True
    elif mp3_path.exists():
        tema.archivo_audio.name = f"temas_audio/{mp3_filename}"
        tema.save(update_fields=['archivo_audio'])
        logger.info(f"[MP3 CACHE] Archivo encontrado en disco, vinculado: {mp3_filename}")
        return FileResponse(open(mp3_path, "rb"), content_type="audio/mpeg")
    else:
        necesita_generar = True
    
    if necesita_generar:
        try:
            logger.info(f"[MP3] Generando: {mp3_filename}")
            tts = gTTS(text=texto_contenido, lang="es", slow=False)
            tts.save(str(mp3_path))
            
            tema.archivo_audio.name = f"temas_audio/{mp3_filename}"
            tema.save(update_fields=['archivo_audio'])
            
            logger.info(f"[MP3] ✓ Generado y cacheado: {mp3_filename}")
            
        except Exception as e:
            logger.error(f"[MP3] ✗ Error gTTS: {e}")
            messages.error(request, "Error al generar el audio. Inténtalo más tarde.")
            return redirect("ver_temario")
    
    return FileResponse(open(mp3_path, "rb"), content_type="audio/mpeg")

# --- 5. PASARELA DE PAGOS ---

@login_required
def iniciar_pago(request):
    cursos = Curso.objects.all()
    perfil = request.user.perfil
    
    importe_centimos, descuento, importe_final = RedsysPayment.calcular_importe(perfil)
    
    cursos_precio = {
        'cabo': {'nombre': 'Ascenso a Cabo', 'precio': 9.99},
        'cabo-primero': {'nombre': 'Cabo Primero', 'precio': 9.99},
        'permanencia': {'nombre': 'Permanencia', 'precio': 'Proximamente'},
    }
    
    context = {
        'cursos': cursos,
        'cursos_precio': cursos_precio,
        'perfil': perfil,
        'importe_final': importe_final,
        'descuento': descuento,
        'hay_descuento': descuento > 0,
    }
    return render(request, "simulador/bloqueo_pago.html", context)


@login_required
def procesar_pago(request, curso_slug):
    if request.method != 'POST':
        return redirect('iniciar_pago')
    
    perfil = request.user.perfil
    importe_centimos, descuento, importe_final = RedsysPayment.calcular_importe(perfil, curso_slug)
    
    if importe_centimos <= 0:
        messages.success(request, f"¡Tienes {descuento}€ de descuento! Acceso concedido sin pago.")
        return redirect('simulador_curso', curso_slug=curso_slug)
    
    numero_pedido = f"{request.user.id}{timezone.now().strftime('%H%M%S')}"
    
    pago_data = RedsysPayment.crear_pago(
        request=request,
        perfil=perfil,
        curso_slug=curso_slug,
        importe_centimos=importe_centimos,
        numero_pedido=numero_pedido
    )

    request.session['pago_curso_slug'] = curso_slug
    request.session['pago_importe'] = str(importe_centimos)
    request.session['pago_numero'] = numero_pedido
    request.session['pago_descuento'] = str(descuento)
    
    logger.info(
        f"[PAGO REDSYS] Usuario {request.user.username} (ID:{request.user.id}) "
        f"inicia pago para {curso_slug}. Importe: {importe_centimos} centimos "
        f"(Descuento aplicado: {descuento}€). Pedido: {numero_pedido}"
    )
    
    CURSOS_NOMBRE = {
        'cabo': 'Ascenso a Cabo',
        'cabo-primero': 'Cabo Primero',
    }
    
    redsys_url = 'https://sis-t.redsys.es:25443/sis/realizarPago'
    
    # En views.py, dentro de def procesar_pago...
    context = {
        'Ds_MerchantParameters': pago_data['Ds_MerchantParameters'],
        'Ds_Signature': pago_data['Ds_Signature'],
        'Ds_SignatureVersion': 'HMAC_SHA256_V1',
        'Ds_MerchantCode': pago_data.get('Ds_MerchantCode', '999008881'),
        'redsys_url': 'https://sis-t.redsys.es:25443/sis/realizarPago', # URL de Sandbox
        'importe': float(importe_centimos) / 100.0,
        'curso_nombre': 'Ascenso a Cabo',
    }
    return render(request, "simulador/redsys_form.html", context)

@login_required
def pago_exitoso(request):
    try:
        curso_slug = request.session.get('pago_curso_slug')
        numero_pedido = request.session.get('pago_numero')
        descuento_usado = Decimal(request.session.get('pago_descuento', '0'))
        
        perfil = request.user.perfil
        
        if curso_slug and curso_slug in CURSOS_DISPONIBLES:
            curso_info = CURSOS_DISPONIBLES[curso_slug]
            if curso_info['activo']:
                try:
                    curso = Curso.objects.get(nombre=curso_info['nombre'])
                    if curso not in perfil.cursos_activos.all():
                        perfil.cursos_activos.add(curso)
                    
                    if not perfil.es_premium:
                        perfil.es_premium = True
                        perfil.save()
                        logger.info(
                            f"[PREMIUM ACTIVADO] Usuario {request.user.username} (ID:{request.user.id}) "
                            f"ha obtenido acceso premium tras el pago. Pedido: {numero_pedido}"
                        )
                    
                    logger.info(
                        f"[PAGO CONFIRMADO] Usuario {request.user.username} (ID:{request.user.id}) "
                        f"ha completado el pago del curso {curso_info['nombre']}. Pedido: {numero_pedido}"
                    )
                except Curso.DoesNotExist:
                    logger.error(f"[PAGO ERROR] Curso no encontrado: {curso_info['nombre']}")
        
        if descuento_usado > 0:
            saldo_anterior = perfil.descuento_acumulado
            descuento_aplicado = min(saldo_anterior, RedsysPayment.PRECIO_BASE)
            saldo_resultante = max(Decimal('0'), saldo_anterior - RedsysPayment.PRECIO_BASE)
            
            perfil.descuento_acumulado = saldo_resultante
            perfil.save()
            
            HistorialDescuento.objects.create(
                usuario=request.user,
                motivo='APLICADO_PAGO',
                cuantia=-descuento_aplicado,
                saldo_resultante=saldo_resultante
            )
            
            if saldo_resultante > 0:
                HistorialDescuento.objects.create(
                    usuario=request.user,
                    motivo='SOBRANTE_PAGO',
                    cuantia=saldo_resultante,
                    saldo_resultante=saldo_resultante
                )
            
            logger.info(
                f"[DESCUENTO APLICADO] Usuario {request.user.username} (ID:{request.user.id}) "
                f"descuento usado: {descuento_aplicado}€, sobrante: {saldo_resultante}€. "
                f"Nuevo saldo: {perfil.descuento_acumulado}€"
            )
        
        for key in ['pago_curso_slug', 'pago_importe', 'pago_numero', 'pago_descuento']:
            request.session.pop(key, None)
        
        messages.success(request, f"¡Pago completado! Tienes acceso a {curso_slug.replace('-', ' ').title()}.")
    except Exception as e:
        logger.error(f"[PAGO ERROR] Error procesando pago exitoso: {str(e)}")
        messages.error(request, "Error procesando el pago. Contacta con soporte.")
    
    return redirect("portada")

@login_required
def pago_cancelado(request):
    for key in ['pago_curso_slug', 'pago_importe', 'pago_numero', 'pago_descuento']:
        request.session.pop(key, None)
    
    messages.warning(request, "El pago ha sido cancelado. Tu descuento sigue disponible.")
    return redirect("iniciar_pago")


@csrf_exempt
def redsys_webhook(request):
    if request.method == 'POST':
        try:
            params = request.POST
            
            logger.info(f"[REDsys WEBHOOK] Recibida respuesta: {dict(params)}")
            
            resultado = RedsysPayment.procesar_respuesta(params)
            
            if resultado.get('success'):
                numero_pedido = resultado.get('pedido', '')
                user_id = int(numero_pedido[:numero_pedido.index(next(c for c in numero_pedido if c.isalpha() and c != '0'))]) if numero_pedido else None
                
                logger.info(
                    f"[REDsys WEBHOOK] Pago confirmado para pedido {numero_pedido}. "
                    f"Ds_Response: {resultado.get('codigo')}"
                )
            else:
                logger.warning(
                    f"[REDsys WEBHOOK] Pago rechazado. Pedido: {resultado.get('pedido')}. "
                    f"Codigo: {resultado.get('codigo')}"
                )
            
            return HttpResponse('OK', content_type='text/plain')
        except Exception as e:
            logger.error(f"[REDsys WEBHOOK ERROR] {str(e)}")
            return HttpResponse('ERROR', content_type='text/plain', status=500)
    
    return HttpResponse('METHOD NOT ALLOWED', status=405)

# --- 6. INSTRUCTOR IA (OPTIMIZADO PARA VPS 4GB) ---

import re
from collections import Counter

def extraer_frases_relevantes(texto, pregunta, num_frases=3):
    """
    Extrae las frases más relevantes del texto basándose en palabras clave de la pregunta.
    Usa un sistema de scoring simple sin embeddings.
    """
    if not texto or not pregunta:
        return ""
    
    palabras_pregunta = set(pregunta.lower().split())
    palabras_excluir = {'el', 'la', 'los', 'las', 'de', 'en', 'a', 'que', 'es', 'por', 'para', 'con', 'una', 'como', 'pero', 'su', 'se', 'lo', 'al', 'del', 'si', 'no', 'me', 'te', 'le', 'qué', 'cómo', 'cuándo', 'dónde', 'quién'}
    palabras_pregunta = palabras_pregunta - palabras_excluir
    
    frases = re.split(r'[.\n]', texto)
    frases = [f.strip() for f in frases if len(f.strip()) > 30 and len(f.strip()) < 500]
    
    mejores_frases = []
    mejores_scores = []
    
    for frase in frases:
        palabras_frase = set(re.findall(r'\b\w{4,}\b', frase.lower()))
        score = len(palabras_frase & palabras_pregunta)
        
        if score > 0:
            for i, (s, f) in enumerate(mejores_scores):
                if score > s:
                    mejores_frases.insert(i, frase)
                    mejores_scores.insert(i, (score, frase))
                    if len(mejores_frases) > num_frases:
                        mejores_frases = mejores_frases[:num_frases]
                        mejores_scores = mejores_scores[:num_frases]
                    break
            else:
                if len(mejores_frases) < num_frases:
                    mejores_frases.append(frase)
                    mejores_scores.append((score, frase))
    
    return " ".join(mejores_frases[:num_frases])


def extraer_parrafos_relevantes(texto, palabras_clave, max_chars=1200):
    """
    Extrae párrafos completos que contengan las palabras clave.
    Busca artículos completos (delimitados por 'Artículo' o 'Art.') o párrafos.
    Elimina 'paja' que no contenga keywords.
    """
    if not texto or not palabras_clave:
        return ""
    
    texto_lower = texto.lower()
    parrafos_encontrados = []
    
    # Dividir por párrafos (doble salto de línea o bloque de artículo)
    bloques = re.split(r'\n\s*\n|(?:Artículo|Art\.?\s*\d+[.:])', texto)
    
    for bloque in bloques:
        bloque = bloque.strip()
        if len(bloque) < 50:
            continue
        
        bloque_lower = bloque.lower()
        
        # Verificar si contiene alguna palabra clave
        contiene_keyword = False
        for kw in palabras_clave:
            if len(kw) >= 4 and kw in bloque_lower:
                contiene_keyword = True
                break
        
        if contiene_keyword:
            # Limpiar el bloque de ruido
            bloque_limpio = limpiar_texto_manual(bloque)
            if len(bloque_limpio) >= 50:
                parrafos_encontrados.append(bloque_limpio)
    
    # Unir los párrafos encontrados hasta max_chars
    resultado = []
    total_chars = 0
    
    for p in parrafos_encontrados:
        if total_chars + len(p) <= max_chars:
            resultado.append(p)
            total_chars += len(p)
        else:
            # Si ya no cabe completo, intentar cortar por oración
            remaining = max_chars - total_chars
            if remaining > 100:
                resultado.append(p[:remaining])
            break
    
    return "\n\n".join(resultado)


def limpiar_texto_manual(texto):
    """Limpia el texto eliminando títulos, índices y ruido."""
    resultado = texto
    
    # Eliminar líneas de título del temario
    resultado = re.sub(r'^TEMARIO.*$', '', resultado, flags=re.MULTILINE | re.IGNORECASE)
    resultado = re.sub(r'^BLOQUE\s+[IVXLCDM]+\s*', '', resultado, flags=re.MULTILINE | re.IGNORECASE)
    resultado = re.sub(r'^TEMA\s*\d+[:\.]?\s*', '', resultado, flags=re.MULTILINE | re.IGNORECASE)
    resultado = re.sub(r'^\d+-\w+-\d+\s*$', '', resultado, flags=re.MULTILINE)
    
    # Eliminar líneas muy cortas que son ruido
    lineas = resultado.split('\n')
    lineas = [l.strip() for l in lineas if len(l.strip()) > 10 or l.strip().endswith('.')]
    resultado = '\n'.join(lineas)
    
    # Limpiar espacios múltiples
    resultado = re.sub(r'\n{3,}', '\n\n', resultado)
    resultado = re.sub(r' {2,}', ' ', resultado)
    
    return resultado.strip()


@csrf_exempt
@login_required
def chat_ia(request):
    """
    Instructor IA optimizado para VPS 4GB.
    - Modelo ligero: qwen2.5:1.5b
    - Contexto quirúrgico: solo las 3 frases más relevantes
    - Keep-alive: libera RAM tras 5 min de inactividad
    """
    if request.method == "POST":
        try:
            perfil = request.user.perfil
            if not perfil.es_premium:
                return JsonResponse({
                    "error": "⚠️ Soldado, esta función requiere acceso Premium. Desbloquea el Instructor IA 24/7.",
                    "status": "premium_required",
                    "upgrade_url": "/plan-premium/"
                }, status=403)

            try:
                data = json.loads(request.body)
                pregunta_alumno = data.get("question") or data.get("pregunta")
                tema_id_filtrado = data.get("tema_id")
            except Exception:
                pregunta_alumno = request.POST.get("pregunta")
                tema_id_filtrado = request.POST.get("tema_id")

            if not pregunta_alumno:
                pregunta_alumno = "Hola"

            cursos_alumno = perfil.cursos_activos.all()

            curso_detectado = "CABO" 
            for curso in cursos_alumno:
                if "PRIMERO" in curso.nombre.upper():
                    curso_detectado = "CABO PRIMERO"
                    break 
            
            contexto_relevante = ""
            fuentes_utilizadas = []
            ranking_scores = []
            
            # Extraer palabras clave de la pregunta
            palabras_pregunta = pregunta_alumno.lower().split()
            stop_words = {'el', 'la', 'los', 'las', 'de', 'en', 'que', 'es', 'un', 'una', 'por', 'para', 'con', 'sin', 'sobre', 'y', 'a', 'o', 'cual', 'cuantos', 'cuantas', 'qué', 'cómo', 'cuando', 'dónde'}
            palabras_clave = [p for p in palabras_pregunta if len(p) > 3 and p not in stop_words]
            
            logger.info(f"[IA DEBUG] Palabras clave: {palabras_clave}")
            
            # 1. Buscar en Documentos de Contexto (PDFs/TXTs subidos)
            documentos = DocumentoContexto.objects.filter(
                curso__in=cursos_alumno,
                activo=True,
                contenido_texto__isnull=False
            ).exclude(contenido_texto='')
            
            for doc in documentos:
                contenido_lower = doc.contenido_texto.lower()
                nombre_lower = doc.nombre.lower()
                
                # Calcular puntuación por palabras clave en título y contenido
                score = 0
                palabras_encontradas = 0
                for palabra in palabras_clave:
                    if palabra in nombre_lower:
                        score += 15  # Mucho peso si está en el título
                        palabras_encontradas += 1
                    if palabra in contenido_lower:
                        score += 3
                        palabras_encontradas += 1
                
                if score > 0 and len(doc.contenido_texto) >= 100:
                    ranking_scores.append({
                        'doc': doc,
                        'score': score,
                        'palabras': palabras_encontradas,
                        'nombre': doc.nombre,
                        'chars': len(doc.contenido_texto)
                    })
            
            # Ordenar por puntuación y tomar SOLO los 2 mejores
            ranking_scores.sort(key=lambda x: (x['score'], x['palabras']), reverse=True)
            top_documentos = ranking_scores[:2]
            
            logger.info(f"[IA DEBUG] Ranking de documentos (top 2): {[(d['nombre'][:30], d['score'], d['chars']) for d in top_documentos]}")
            
            # Usar extracción por párrafos completos
            for item in top_documentos:
                doc = item['doc']
                
                # Extraer SOLO párrafos que contengan palabras clave
                parrafos = extraer_parrafos_relevantes(
                    doc.contenido_texto,
                    palabras_clave,
                    max_chars=1000
                )
                
                if parrafos and len(parrafos) >= 50:
                    contexto_relevante += parrafos + "\n\n"
                    fuentes_utilizadas.append(f"Documento: {doc.nombre}")
                    logger.info(f"[IA DEBUG] ✓ {doc.nombre[:40]}: score={item['score']}, chars={len(parrafos)}")
                    logger.info(f"[IA DEBUG] Contenido: {parrafos[:300]}...")
            
            # Si no hay documentos con ranking, buscar en Temas
            if not fuentes_utilizadas:
                temas_del_curso = Tema.objects.filter(materia="CABO", contenido_texto__isnull=False).exclude(contenido_texto='')
                
                for tema in temas_del_curso:
                    if tema.contenido_texto and len(tema.contenido_texto) >= 100:
                        parrafos = extraer_parrafos_relevantes(
                            tema.contenido_texto,
                            palabras_clave,
                            max_chars=800
                        )
                        if parrafos and len(parrafos) >= 50:
                            contexto_relevante += f"{parrafos}\n\n"
                            fuentes_utilizadas.append(f"Tema: {tema.nombre}")
            
            # Verificar si hay contexto con calidad mínima
            if not contexto_relevante.strip() or len(contexto_relevante.strip()) < 50:
                logger.warning("[IA] ⚠ Contexto vacío o insuficiente - No se envía petición a Ollama")
                return JsonResponse({
                    "respuesta": "Información no encontrada en el manual.",
                    "answer": "Información no encontrada en el manual.",
                    "status": "no_context",
                    "sources": []
                })

            # DEBUG: Guardar contexto en archivo para verificación
            try:
                debug_path = os.path.join(settings.BASE_DIR, 'ultimo_contexto.txt')
                with open(debug_path, 'w', encoding='utf-8') as f:
                    f.write(f"PREGUNTA: {pregunta_alumno}\n")
                    f.write(f"FECHA: {datetime.now().isoformat()}\n")
                    f.write(f"PALABRAS CLAVE: {palabras_clave}\n")
                    f.write(f"FUENTES: {fuentes_utilizadas}\n")
                    f.write(f"CONTEXTO TOTAL ({len(contexto_relevante)} chars):\n")
                    f.write("=" * 70 + "\n")
                    f.write(contexto_relevante)
                logger.info(f"[IA DEBUG] Contexto guardado en: {debug_path}")
            except Exception as e:
                logger.error(f"[IA DEBUG] Error guardando contexto: {e}")

            # DEBUG: Mostrar contenido real que se envía
            logger.info("=" * 70)
            logger.info(f"[IA DEBUG] PREGUNTA: {pregunta_alumno}")
            logger.info(f"[IA DEBUG] FUENTES ({len(fuentes_utilizadas)}):")
            for f in fuentes_utilizadas:
                logger.info(f"  - {f}")
            logger.info(f"[IA DEBUG] CONTEXTO TOTAL: {len(contexto_relevante)} chars")
            logger.info("-" * 70)
            logger.info("[IA DEBUG] PRIMEROS 300 CARACTERES DEL CONTENIDO:")
            logger.info(contexto_relevante[:300] if contexto_relevante else "[VACÍO]")
            logger.info("=" * 70)

            # Construir prompt DE LITERALIDAD ABSOLUTA
            prompt = f"""Eres un transcriptor de leyes y manuales militares. Tu función es localizar la frase exacta o el artículo relacionado con la pregunta del alumno.
REGLAS:

Responde citando o parafraseando de forma casi literal el manual.

No resumas. No opines.

Si el texto menciona un número de artículo (ej: Art. 12), inclúyelo siempre en la respuesta.

Si la frase exacta está en el CONTEXTO, transmítela íntegramente.

CONTEXTO:
{contexto_relevante[:1000]}

PREGUNTA:
{pregunta_alumno}

RESPUESTA (solo texto del contexto):"""

            ollama_model = getattr(settings, 'OLLAMA_MODEL', None) or 'qwen2.5:1.5b'
            ollama_url = getattr(settings, 'OLLAMA_BASE_URL', None) or 'http://localhost:11434'
            ollama_keepalive = "24h"
            ollama_timeout = int(getattr(settings, 'OLLAMA_TIMEOUT', 120))
            
            urls_a_probar = list(dict.fromkeys([
                ollama_url,
                'http://localhost:11434',
                'http://127.0.0.1:11434'
            ]))
            
            respuesta_ia = None
            ultimo_error = None
            tipo_error = None
            
            for url_intento, ollama_url in enumerate(urls_a_probar, 1):
                try:
                    ollama_api_url = f"{ollama_url.rstrip('/')}/api/generate"
                    payload = {
                        "model": ollama_model,
                        "prompt": prompt,
                        "stream": True,
                        "keep_alive": ollama_keepalive,
                        "options": {
                            "temperature": 0.1,
                            "num_ctx": getattr(settings, 'OLLAMA_NUM_CTX', 2048),
                            "repeat_penalty": 1.1,
                            "top_p": 0.9
                        }
                    }
                    
                    logger.info(f"[IA] ► Intento {url_intento}/{len(urls_a_probar)}: {ollama_api_url}")
                    logger.info(f"[IA]   Modelo: {ollama_model} | Timeout: {ollama_timeout}s")
                    
                    import time
                    inicio_req = time.time()
                    
                    response = requests.post(ollama_api_url, json=payload, timeout=ollama_timeout, stream=True)
                    tiempo_req = time.time() - inicio_req
                    
                    if response.status_code == 404:
                        tipo_error = "404_NOT_FOUND"
                        ultimo_error = f"Modelo '{ollama_model}' no encontrado. Ejecuta: ollama pull {ollama_model}"
                        logger.warning(f"[IA]   ⚠ {ultimo_error}")
                        continue
                    
                    response.raise_for_status()
                    
                    respuesta_ia = ""
                    chunks_recibidos = 0
                    for line in response.iter_lines():
                        if line:
                            try:
                                data = json.loads(line)
                                chunk = data.get('response', '')
                                if chunk:
                                    respuesta_ia += chunk
                                    chunks_recibidos += 1
                                if data.get('done', False):
                                    break
                            except json.JSONDecodeError:
                                continue
                    
                    respuesta_ia = respuesta_ia.strip()
                    
                    # DEBUG: Verificar cadena de respuesta
                    logger.info(f"[IA DEBUG] Chunks recibidos: {chunks_recibidos}")
                    logger.info(f"[IA DEBUG] Respuesta completa ({len(respuesta_ia)} chars): {respuesta_ia[:200]}...")
                    
                    if respuesta_ia and len(respuesta_ia) > 5:
                        logger.info(f"[IA]   ✓ ÉXITO en {tiempo_req:.2f}s ({len(respuesta_ia)} chars)")
                        break
                    else:
                        tipo_error = "EMPTY_RESPONSE"
                        ultimo_error = "Ollama devolvió respuesta vacía"
                        logger.warning(f"[IA]   ⚠ {ultimo_error}")
                        
                except requests.exceptions.ConnectionError as e:
                    tipo_error = "CONNECTION_REFUSED"
                    ultimo_error = f"Conexión rechazada en {ollama_url}. ¿Está Ollama corriendo?"
                    logger.error(f"[IA]   ✗ {ultimo_error}")
                    logger.error(f"[IA]   Error details: {type(e).__name__}: {str(e)}")
                    continue
                    
                except requests.exceptions.Timeout as e:
                    tipo_error = "TIMEOUT"
                    ultimo_error = f"Timeout de {ollama_timeout}s. La IA tardó demasiado en responder."
                    logger.error(f"[IA]   ⏱ {ultimo_error}")
                    logger.error(f"[IA]   El modelo puede estar cargando o el VPS tiene alta latencia.")
                    continue
                    
                except requests.exceptions.ConnectTimeout as e:
                    tipo_error = "CONNECT_TIMEOUT"
                    ultimo_error = f"Timeout de conexión a {ollama_url}. Red lenta o VPS inaccesible."
                    logger.error(f"[IA]   ✗ {ultimo_error}")
                    continue
                    
                except Exception as e:
                    tipo_error = type(e).__name__.upper()
                    ultimo_error = str(e)
                    logger.error(f"[IA]   ✗ Error {tipo_error}: {ultimo_error}")
                    continue
            
            if respuesta_ia:
                logger.info(f"[IA] ✓ Respuesta enviada al usuario")
                return JsonResponse({
                    "respuesta": respuesta_ia,
                    "answer": respuesta_ia,
                    "status": "success",
                    "provider": "ollama"
                })
            else:
                error_msg = f"Instructor IA no disponible. [{tipo_error}] {ultimo_error}"
                logger.error(f"[IA] ✗ {error_msg}")
                return JsonResponse({
                    "respuesta": f"⚠️ {error_msg}",
                    "answer": f"⚠️ {error_msg}",
                    "status": "error"
                }, status=500)
                
        except Exception as e:
            error_msg = str(e)
            logger.error(f"[IA] Error crítico: {error_msg}")
            return JsonResponse({
                "respuesta": f"⚠️ Error: {error_msg}",
                "answer": f"⚠️ Error: {error_msg}",
                "status": "error"
            }, status=500)

    return render(request, 'simulador/chat_ia.html')

# --- 7. HERRAMIENTAS DE ADMINISTRADOR (ETL) ---

@login_required
def sincronizar_bd(request):
    """
    Lee el archivo preguntas.json y lo vuelca en la base de datos SQLite
    para que el Simulador Web tenga munición.
    """
    ruta_json = os.path.join(settings.BASE_DIR, 'preguntas.json')
    if not os.path.exists(ruta_json):
        ruta_json = os.path.join(settings.BASE_DIR, 'simulador', 'data', 'preguntas.json')
        if not os.path.exists(ruta_json):
            return JsonResponse({"error": f"No se encuentra el archivo JSON en: {ruta_json}"}, status=404)

    with open(ruta_json, 'r', encoding='utf-8') as f:
        datos = json.load(f)

    temas_creados = 0
    preguntas_creadas = 0

    for item in datos:
        materia_raw = item.get('materia', 'CABO').upper()
        
        if materia_raw in ['LEGISLACION', 'LEGISLACIÓN', 'GENERAL']:
            materia_db = 'CABO'
        elif materia_raw == 'INGLES':
            materia_db = 'INGLÉS'
        elif materia_raw == 'GEOGRAFIA':
            materia_db = 'GEOGRAFÍA'
        elif materia_raw == 'INFORMATICA':
            materia_db = 'INFORMÁTICA'
        else:
            materia_db = materia_raw

        tema, created = Tema.objects.get_or_create(
            materia=materia_db,
            nombre=item.get('titulo_tema', 'Tema General'),
            defaults={
                'capitulo': item.get('capitulo', 0),
                'bloque': item.get('bloque', 0),
                'numero_tema': item.get('tema', 0)
            }
        )
        if created: temas_creados += 1

        pregunta, p_created = Pregunta.objects.get_or_create(
            tema=tema,
            enunciado=item.get('pregunta'),
            defaults={
                'explicacion': item.get('explicacion', ''),
                'dificultad': 2
            }
        )

        if p_created:
            preguntas_creadas += 1
            opciones = item.get('opciones', [])
            correcta_idx = int(item.get('correcta', 0))

            for i, texto_opcion in enumerate(opciones):
                Opcion.objects.create(
                    pregunta=pregunta,
                    texto=texto_opcion,
                    es_correcta=(i == correcta_idx)
                )

    return JsonResponse({
        "status": "success",
        "mensaje": f"Sincronización completa. Temas creados/verificados: {temas_creados}. Nuevas preguntas importadas: {preguntas_creadas}."
    })