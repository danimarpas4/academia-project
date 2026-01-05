import csv
from django.core.management.base import BaseCommand
from simulador.models import Tema, Pregunta, Opcion

class Command(BaseCommand):
    help = 'Carga preguntas masivamente desde un archivo CSV'

    def handle(self, *args, **kwargs):
        # Nombre del archivo (asumimos que está en la raíz)
        archivo = 'preguntas.csv'
        
        self.stdout.write(f"Iniciando carga desde {archivo}...")

        try:
            with open(archivo, mode='r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                
                count = 0
                for row in reader:
                    # 1. Obtener o Crear el Tema (para no duplicarlos)
                    tema_nombre = row['tema'].strip()
                    tema_obj, created = Tema.objects.get_or_create(nombre=tema_nombre)
                    
                    # 2. Crear la Pregunta
                    pregunta = Pregunta.objects.create(
                        tema=tema_obj,
                        enunciado=row['enunciado']
                    )

                    # 3. Crear las 4 opciones
                    # Mapeamos A,B,C,D con sus textos
                    opciones_raw = [
                        ('A', row['opcion_a']),
                        ('B', row['opcion_b']),
                        ('C', row['opcion_c']),
                        ('D', row['opcion_d']),
                    ]

                    correcta_letra = row['correcta'].strip().upper()

                    for letra, texto in opciones_raw:
                        es_la_buena = (letra == correcta_letra)
                        
                        Opcion.objects.create(
                            pregunta=pregunta,
                            texto=texto,
                            es_correcta=es_la_buena
                        )
                    
                    count += 1
            
            self.stdout.write(self.style.SUCCESS(f'¡Éxito! Se han cargado {count} preguntas nuevas.'))

        except FileNotFoundError:
            self.stdout.write(self.style.ERROR('Error: No encuentro el archivo preguntas.csv en la raíz.'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error desconocido: {str(e)}'))