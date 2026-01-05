from django.utils import timezone
import stripe
from django.conf import settings
from django.urls import reverse
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login
from django.shortcuts import render, get_object_or_404, redirect # <--- Añade redirect
from django.contrib.auth.decorators import login_required # <--- Para proteger vistas
from django.shortcuts import render, get_object_or_404
from .models import Tema, Opcion, Resultado # <--- AÑADE Resultado

# Vista para el Hall de Entrada
def landing(request):
    return render(request, 'simulador/landing.html')

@login_required
def portada(request):
    perfil = request.user.perfil
    
    # --- ZONA DE DEBUG (DIAGNÓSTICO) ---
    ahora = timezone.now()
    fecha_registro = request.user.date_joined
    diferencia = ahora - fecha_registro
    dias_transcurridos = diferencia.days
    
    dias_prueba = 15
    dias_restantes = dias_prueba - dias_transcurridos
    
    
    # LÓGICA DE ACCESO (EL PORTERO)
    # COMENTA ESTAS LÍNEAS CON '#' PARA QUE NO TE ECHE
    if not perfil.esta_suscrito and dias_restantes < 0:
        return redirect('iniciar_pago') 

    # Carga de temas
    temas = Tema.objects.all()

    contexto = {
        'temas': temas,
        'esta_en_prueba': not perfil.esta_suscrito, 
        'dias_restantes': dias_restantes,
        # Pasamos los datos de debug a la pantalla para que los veas
        'debug_registro': fecha_registro,
        'debug_dias': dias_transcurridos
    }

    return render(request, 'simulador/portada.html', contexto)

# ... (imports y función portada igual) ...

@login_required
def examen(request, tema_id):
    tema = get_object_or_404(Tema, pk=tema_id)
    preguntas = tema.preguntas.all()

    if request.method == 'POST':
        aciertos = 0
        total_preguntas = preguntas.count()

        # 1. Recuperamos la lista de detalles para la corrección visual
        detalles = []

        for pregunta in preguntas:
            opcion_id = request.POST.get(f'pregunta_{pregunta.id}')

            respuesta_usuario = None
            respuesta_correcta = pregunta.opciones.get(es_correcta=True)
            es_acierto = False

            if opcion_id:
                opcion_elegida = Opcion.objects.get(id=opcion_id)
                respuesta_usuario = opcion_elegida

                if opcion_elegida.es_correcta:
                    aciertos += 1
                    es_acierto = True

            # Guardamos el detalle
            detalles.append({
                'pregunta': pregunta,
                'respuesta_usuario': respuesta_usuario,
                'respuesta_correcta': respuesta_correcta,
                'es_acierto': es_acierto
            })

        # 2. Calculamos la nota
        nota_final = 0
        if total_preguntas > 0:
            nota_final = (aciertos / total_preguntas) * 10

        # 3. Guardamos en la Base de Datos (Historial)
        Resultado.objects.create(
            usuario=request.user,
            tema=tema,
            nota=nota_final
        )

        # 4. Preparamos el contexto (AQUÍ ES DONDE FALTABA 'detalles')
        contexto = {
            'tema': tema,
            'aciertos': aciertos,
            'total': total_preguntas,
            'nota': round(nota_final, 2),
            'detalles': detalles  # <--- ¡Esto es lo que recupera los colores rojo/verde!
        }
        return render(request, 'simulador/resultado.html', contexto)

    # Si es GET (ver el examen vacío)
    return render(request, 'simulador/examen.html', {'tema': tema, 'preguntas': preguntas})
def registro(request):
    if request.method == 'POST':
        # Cargamos los datos del formulario
        form = UserCreationForm(request.POST)
        if form.is_valid():
            usuario = form.save()
            # Logueamos al usuario directamente tras registrarse
            login(request, usuario)
            return redirect('landing')
    else:
        # Formulario vacío
        form = UserCreationForm()

    return render(request, 'registration/registro.html', {'form': form})

@login_required
def perfil(request):
    # Buscamos SOLO las notas del usuario que está logueado, ordenadas por fecha (más nueva primero)
    historial = Resultado.objects.filter(usuario=request.user).order_by('-fecha')

    return render(request, 'simulador/perfil.html', {'historial': historial})

# Configurar la API Key
stripe.api_key = settings.STRIPE_SECRET_KEY

@login_required
def iniciar_pago(request):
    # Creamos una sesión de pago en Stripe
    session = stripe.checkout.Session.create(
        payment_method_types=['card'],
        line_items=[{
            'price_data': {
                'currency': 'eur',
                'product_data': {
                    'name': 'Curso Ascenso a Cabo - Acceso Total',
                },
                'unit_amount': 1499,  # 1500 céntimos = 15.00€
            },
            'quantity': 1,
        }],
        mode='payment',
        # Rutas a las que volveremos después de pagar
        success_url=request.build_absolute_uri(reverse('pago_exitoso')),
        cancel_url=request.build_absolute_uri(reverse('pago_cancelado')),
    )
    # Redirigimos al usuario a la web de Stripe
    return redirect(session.url, code=303)

@login_required
def pago_exitoso(request):
    # Marcamos al usuario como PAGADO
    perfil = request.user.perfil
    perfil.esta_suscrito = True
    perfil.save()
    return render(request, 'simulador/pago_exitoso.html')

@login_required
def pago_cancelado(request):
    return render(request, 'simulador/pago_cancelado.html')