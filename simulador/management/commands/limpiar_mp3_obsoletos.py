"""
Comando de gestión para limpiar MP3s obsoletos del caché de audio.

Los MP3s obsoletos son aquellos que:
1. No corresponden a ningún tema existente
2. Tienen un hash diferente al contenido_texto actual del tema

Uso:
    python manage.py limpiar_mp3_obsoletos
    python manage.py limpiar_mp3_obsoletos --dry-run  # Solo muestra qué se eliminaría
"""

from django.core.management.base import BaseCommand
from django.conf import settings
from simulador.models import Tema
from pathlib import Path
import hashlib
import re


class Command(BaseCommand):
    help = 'Elimina MP3s obsoletos del caché de audio'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Muestra qué archivos se eliminarían sin eliminarlos realmente',
        )

    def handle(self, *args, **options):
        cache_dir = Path(settings.MEDIA_ROOT) / 'audio_cache'
        
        if not cache_dir.exists():
            self.stdout.write(self.style.WARNING('El directorio de caché no existe.'))
            return
        
        dry_run = options['dry_run']
        mp3_files = list(cache_dir.glob('tema_*.mp3'))
        
        if not mp3_files:
            self.stdout.write(self.style.SUCCESS('No hay archivos MP3 en el caché.'))
            return
        
        self.stdout.write(f'Analizando {len(mp3_files)} archivos MP3...')
        
        # Obtener todos los temas con contenido_texto
        temas = Tema.objects.filter(contenido_texto__isnull=False).exclude(contenido_texto='')
        temas_dict = {}
        
        for tema in temas:
            texto = tema.contenido_texto.strip()
            contenido_hash = hashlib.md5(texto.encode('utf-8')).hexdigest()
            temas_dict[tema.id] = contenido_hash[:8]
        
        eliminados = 0
        obsoletos = 0
        inexistentes = 0
        
        for mp3_file in mp3_files:
            # Extraer tema_id del nombre del archivo: tema_X_hash.mp3
            match = re.match(r'tema_(\d+)_([a-f0-9]+)\.mp3', mp3_file.name)
            
            if not match:
                # Archivo con formato incorrecto
                if dry_run:
                    self.stdout.write(f'  [ELIMINAR] {mp3_file.name} (formato incorrecto)')
                else:
                    mp3_file.unlink()
                    self.stdout.write(self.style.WARNING(f'  Eliminado: {mp3_file.name} (formato incorrecto)'))
                eliminados += 1
                continue
            
            tema_id = int(match.group(1))
            hash_archivo = match.group(2)
            
            # Verificar si el tema existe
            if tema_id not in temas_dict:
                # El tema ya no existe
                if dry_run:
                    self.stdout.write(f'  [ELIMINAR] {mp3_file.name} (tema {tema_id} no existe)')
                else:
                    mp3_file.unlink()
                    self.stdout.write(self.style.WARNING(f'  Eliminado: {mp3_file.name} (tema {tema_id} no existe)'))
                eliminados += 1
                inexistentes += 1
                continue
            
            # Verificar si el hash coincide con el contenido actual
            hash_actual = temas_dict[tema_id]
            if hash_archivo != hash_actual:
                # El contenido del tema ha cambiado
                if dry_run:
                    self.stdout.write(f'  [ELIMINAR] {mp3_file.name} (hash obsoleto: {hash_archivo} != {hash_actual})')
                else:
                    mp3_file.unlink()
                    self.stdout.write(self.style.WARNING(f'  Eliminado: {mp3_file.name} (contenido obsoleto)'))
                eliminados += 1
                obsoletos += 1
                continue
            
            # El archivo es válido
            self.stdout.write(f'  [OK] {mp3_file.name}')
        
        # Resumen
        self.stdout.write('')
        if dry_run:
            self.stdout.write(self.style.SUCCESS(f'Resumen (modo dry-run):'))
            self.stdout.write(f'  - Archivos válidos: {len(mp3_files) - eliminados}')
            self.stdout.write(f'  - Se eliminarían: {eliminados}')
            if inexistentes > 0:
                self.stdout.write(f'    - Temas inexistentes: {inexistentes}')
            if obsoletos > 0:
                self.stdout.write(f'    - Contenido obsoleto: {obsoletos}')
            self.stdout.write('')
            self.stdout.write('Ejecuta sin --dry-run para eliminar realmente los archivos.')
        else:
            self.stdout.write(self.style.SUCCESS(f'Limpieza completada:'))
            self.stdout.write(f'  - Archivos eliminados: {eliminados}')
            if inexistentes > 0:
                self.stdout.write(f'    - Temas inexistentes: {inexistentes}')
            if obsoletos > 0:
                self.stdout.write(f'    - Contenido obsoleto: {obsoletos}')
            self.stdout.write(f'  - Archivos válidos restantes: {len(mp3_files) - eliminados}')
