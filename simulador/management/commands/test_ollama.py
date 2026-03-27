import requests
from django.core.management.base import BaseCommand
from django.conf import settings


class Command(BaseCommand):
    help = 'Verifica la conexión con Ollama y muestra los modelos disponibles'

    def add_arguments(self, parser):
        parser.add_argument(
            '--test-generate',
            action='store_true',
            help='Prueba también una generación simple',
        )
        parser.add_argument(
            '--modelo',
            type=str,
            help='Modelo específico a probar',
        )

    def handle(self, *args, **options):
        ollama_url = getattr(settings, 'OLLAMA_BASE_URL', 'http://localhost:11434')
        modelo = options.get('modelo') or getattr(settings, 'OLLAMA_MODEL', 'qwen2.5:1.5b')
        test_generate = options.get('test_generate', False)
        
        self.stdout.write(f'\n🔍 Verificando conexión con Ollama...\n')
        self.stdout.write(f'   URL: {ollama_url}')
        self.stdout.write(f'   Modelo: {modelo}\n')
        
        try:
            response = requests.get(f'{ollama_url}/api/tags', timeout=10)
            response.raise_for_status()
            data = response.json()
            
            modelos = data.get('models', [])
            
            if modelos:
                self.stdout.write(self.style.SUCCESS(f'✅ Conexión exitosa!'))
                self.stdout.write(f'\n📦 Modelos disponibles ({len(modelos)}):\n')
                
                for m in modelos:
                    nombre = m.get('name', 'Desconocido')
                    tamaño = m.get('size', 0)
                    tamaño_mb = tamaño / (1024 * 1024 * 1024) if tamaño else 0
                    
                    if nombre == modelo:
                        self.stdout.write(self.style.SUCCESS(f'   ✓ {nombre} ({tamaño_mb:.2f} GB) ← CONFIGURADO'))
                    else:
                        self.stdout.write(f'   - {nombre} ({tamaño_mb:.2f} GB)')
                
                modelo_existe = any(m.get('name') == modelo for m in modelos)
                
                if not modelo_existe:
                    self.stdout.write(self.style.WARNING(f'\n⚠️ El modelo "{modelo}" NO está descargado.'))
                    self.stdout.write(f'   Ejecuta: ollama pull {modelo}')
            else:
                self.stdout.write(self.style.WARNING('⚠️ No hay modelos descargados.'))
                self.stdout.write(f'   Ejecuta: ollama pull {modelo}')
                
        except requests.exceptions.ConnectionError:
            self.stdout.write(self.style.ERROR('❌ No se pudo conectar a Ollama.'))
            self.stdout.write(f'   Asegúrate de que Ollama esté corriendo:'))
            self.stdout.write(f'   $ ollama serve'))
            self.stdout.write(f'   O inicia el servicio:'))
            self.stdout.write(f'   $ sudo systemctl start ollama'))
            return
            
        except requests.exceptions.Timeout:
            self.stdout.write(self.style.ERROR('❌ Timeout al conectar con Ollama.'))
            return
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Error: {str(e)}'))
            return
        
        if test_generate and modelo_existe:
            self.stdout.write(f'\n🧪 Probando generación con "{modelo}"...')
            self.stdout.write('   (Esto puede tardar 5-30 segundos en CPU)\n')
            
            try:
                payload = {
                    "model": modelo,
                    "prompt": "Responde solo con: OK",
                    "stream": False,
                    "keep_alive": getattr(settings, 'OLLAMA_KEEPALIVE', '5m')
                }
                
                import time
                inicio = time.time()
                response = requests.post(
                    f'{ollama_url}/api/generate',
                    json=payload,
                    timeout=60
                )
                tiempo = time.time() - inicio
                
                response.raise_for_status()
                data = response.json()
                respuesta = data.get('response', '').strip()
                
                if respuesta:
                    self.stdout.write(self.style.SUCCESS(f'✅ Generación exitosa!'))
                    self.stdout.write(f'   Respuesta: "{respuesta}"')
                    self.stdout.write(f'   Tiempo: {tiempo:.2f}s')
                else:
                    self.stdout.write(self.style.WARNING('⚠️ Respuesta vacía'))
                    
            except requests.exceptions.Timeout:
                self.stdout.write(self.style.WARNING('⚠️ Timeout en generación (normal en CPU)'))
                
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'❌ Error en generación: {str(e)}'))
