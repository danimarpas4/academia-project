import json
import os
from django.conf import settings
from django.core.management.base import BaseCommand
from simulador.models import Pregunta, Opcion, Tema, Curso

class Command(BaseCommand):
    help = 'Carga preguntas desde un archivo JSON (formato Bot Telegram)'

    def handle(self, *args, **kwargs):
        # Buscamos el archivo preguntas.json en la raíz
        ruta_json = os.path.join(settings.BASE_DIR, 'preguntas.json')

        if not os.path.exists(ruta_json):
            self.stdout.write(self.style.ERROR(f'❌ No encuentro: {ruta_json}'))
            return

        # 1. Preparar un Tema por defecto
        # Como las preguntas de Telegram a veces vienen sin tema, las metemos en "Importado Telegram"
        # y luego tú las organizas en el panel de admin.
        curso_default, _ = Curso.objects.get_or_create(nombre="Curso General")
        tema_telegram, _ = Tema.objects.get_or_create(
            nombre="Importado Telegram", 
            defaults={'curso': curso_default}
        )

        with open(ruta_json, 'r', encoding='utf-8') as f:
            datos = json.load(f) # Esto convierte el texto JSON en lista de Python
            
            contador = 0
            for item in datos:
                # Intentamos leer los campos. 
                # Aceptamos 'pregunta' (tu formato) o 'question' (formato telegram nativo)
                enunciado = item.get('pregunta') or item.get('question')
                opciones_lista = item.get('opciones') or item.get('options')
                
                # La correcta suele ser un número (índice 0, 1, 2...)
                indice_correcta = item.get('correcta') 
                if indice_correcta is None:
                    indice_correcta = item.get('correct_option_id')

                # Si faltan datos básicos, saltamos esta pregunta
                if not enunciado or not opciones_lista:
                    continue

                # 2. Crear la PREGUNTA (evitando duplicados)
                pregunta, created = Pregunta.objects.get_or_create(
                    enunciado=enunciado,
                    defaults={'tema': tema_telegram}
                )

                if not created:
                    self.stdout.write(f'ℹ️ Ya existe: {enunciado[:30]}...')
                    continue

                # 3. Crear las OPCIONES (Bucle numérico)
                # Aquí recorremos la lista ["Opción A", "Opción B", ...]
                for i, texto_opcion in enumerate(opciones_lista):
                    
                    # Comprobamos si el índice actual (i) coincide con el número de la correcta
                    es_la_buena = (i == indice_correcta)
                    
                    Opcion.objects.create(
                        pregunta=pregunta,
                        texto=texto_opcion,
                        es_correcta=es_la_buena
                    )

                contador += 1
                self.stdout.write(self.style.SUCCESS(f'✅ Importada: {enunciado[:30]}...'))

        self.stdout.write(self.style.SUCCESS(f'\n🚀 ¡Misión cumplida! {contador} preguntas importadas desde el JSON.'))