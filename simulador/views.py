from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login
from django.contrib.auth.forms import UserCreationForm
from django.utils import timezone
from .models import Tema, Pregunta, Opcion, Resultado, Perfil
from django.db.models import Avg
from django.contrib.auth.models import User

# --- REGISTRO DE USUARIOS ---
def registro(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            # Crear perfil automáticamente
            Perfil.objects.create(usuario=user)
            login(request, user)
            return redirect('portada')
    else:
        form = UserCreationForm()
    return render(request, 'registration/registro.html', {'form': form})

# --- NUEVAS VISTAS DEL DASHBOARD ---

@login_required
def portada(request):
    perfil, created = Perfil.objects.get_or_create(usuario=request.user)
    
    # Lógica de días restantes
    dias_prueba = 15
    diferencia = timezone.now() - request.user.date_joined
    dias_restantes = dias_prueba - diferencia.days

    contexto = {
        'esta_en_prueba': not perfil.esta_suscrito,
        'dias_restantes': dias_restantes,
        'usuario': request.user
    }
    return render(request, 'simulador/portada.html', contexto)

@login_required
def ver_temario(request):
    temas = Tema.objects.all()
    return render(request, 'simulador/temario.html', {'temas': temas})

@login_required
def configurar_test(request):
    # 1. Si el usuario envía el formulario (POST), lo mandamos al examen
    if request.method == 'POST':
        tema_id = request.POST.get('tema_seleccionado')
        # Aquí podríamos añadir lógica para el número de preguntas más adelante
        if tema_id:
            return redirect('examen', tema_id=tema_id)
            
    # 2. Si entra normal (GET), le mostramos la lista de temas para elegir
    temas = Tema.objects.all()
    return render(request, 'simulador/configurar_test.html', {'temas': temas})

@login_required
def estadisticas(request):
    # 1. Datos del usuario actual (lo que ya tenías)
    resultados = Resultado.objects.filter(usuario=request.user).order_by('-fecha')
    
    promedio = resultados.aggregate(Avg('nota'))['nota__avg']
    promedio = round(promedio, 1) if promedio else 0
    total_tests = resultados.count()

    # --- LÓGICA NUEVA: EL RANKING ---
    # Calculamos la media de CADA usuario que haya hecho algún examen
    ranking_usuarios = User.objects.annotate(media_global=Avg('resultado__nota')) \
                                   .filter(media_global__isnull=False) \
                                   .order_by('-media_global')
    
    # Buscamos en qué posición está el usuario actual
    mi_posicion = "-"
    total_alumnos = ranking_usuarios.count()
    
    for index, user_rank in enumerate(ranking_usuarios):
        if user_rank.id == request.user.id:
            mi_posicion = index + 1 # +1 porque los índices empiezan en 0
            break
    # --------------------------------

    # Gráfica (lo que ya tenías)
    ultimos_10 = resultados[:10][::-1]
    fechas_grafica = [r.fecha.strftime("%d/%m") for r in ultimos_10]
    notas_grafica = [float(r.nota) for r in ultimos_10]

    contexto = {
        'resultados': resultados,
        'promedio': promedio,
        'total_tests': total_tests,
        'fechas_grafica': fechas_grafica,
        'notas_grafica': notas_grafica,
        # Nuevas variables para el HTML
        'mi_posicion': mi_posicion,
        'total_alumnos': total_alumnos
    }
    return render(request, 'simulador/estadisticas.html', contexto)

# --- VISTAS DEL EXAMEN (LAS QUE FALTABAN) ---

@login_required
def examen(request, tema_id):
    tema = get_object_or_404(Tema, id=tema_id)
    # Lógica de seguridad de pago
    perfil = request.user.perfil
    diferencia = timezone.now() - request.user.date_joined
    if not perfil.esta_suscrito and diferencia.days > 15:
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
        
        # ... cálculo de la nota anterior ...
        
        nota = (puntuacion / total_preguntas) * 10 if total_preguntas > 0 else 0
        
        # GUARDAR EN BASE DE DATOS
        resultado = Resultado.objects.create(
            usuario=request.user,
            tema=tema,
            nota=nota,            # Aquí usamos 'nota' que es como lo hemos llamado en el modelo
            aciertos=puntuacion,  # Guardamos el número de aciertos
            fallos=total_preguntas - puntuacion # Guardamos los fallos
        )
        return redirect('resultado', resultado_id=resultado.id)

    return render(request, 'simulador/examen.html', {'tema': tema})

@login_required
def resultado(request, resultado_id):
    resultado_obj = get_object_or_404(Resultado, id=resultado_id, usuario=request.user)
    return render(request, 'simulador/resultado.html', {'resultado': resultado_obj})

# --- PAGOS (STRIPE) ---
@login_required
def iniciar_pago(request):
    return render(request, 'simulador/bloqueo_pago.html') # Asegúrate de tener este template o usa uno simple

@login_required
def pago_exitoso(request):
    perfil = request.user.perfil
    perfil.esta_suscrito = True
    perfil.save()
    return render(request, 'simulador/pago_exitoso.html')

@login_required
def pago_cancelado(request):
    return render(request, 'simulador/pago_cancelado.html')

# Pégalo al final de simulador/views.py

@login_required
def perfil(request):
    return render(request, 'simulador/perfil.html')