import hashlib
from pathlib import Path
from django.core.management.base import BaseCommand
from django.conf import settings
from gtts import gTTS


class Command(BaseCommand):
    help = 'Genera archivos MP3 a partir del contenido de texto de Temas o DocumentoContexto'

    def add_arguments(self, parser):
        parser.add_argument(
            '--tipo',
            type=str,
            choices=['tema', 'documento', 'todos'],
            default='todos',
            help='Tipo de contenido a procesar (tema, documento, todos)',
        )
        parser.add_argument(
            '--id',
            type=int,
            help='ID específico del tema o documento',
        )
        parser.add_argument(
            '--max-chars',
            type=int,
            default=8000,
            help='Máximo de caracteres por MP3 (default: 8000)',
        )
        parser.add_argument(
            '--voz',
            type=str,
            default='es',
            help='Idioma de la voz (default: es para español)',
        )
        parser.add_argument(
            '--lento',
            action='store_true',
            help='Genera audio más lento (mejor comprensión)',
        )

    def generar_mp3(self, contenido, nombre, max_chars, lang, slow):
        if not contenido:
            return None, "Sin contenido"
        
        contenido = contenido[:max_chars]
        contenido_hash = hashlib.md5(contenido.encode("utf-8")).hexdigest()
        
        safe_nombre = "".join(c for c in nombre if c.isalnum() or c in " -_").strip()[:30]
        filename = f"{safe_nombre}_{contenido_hash[:8]}.mp3"
        
        output_dir = Path(settings.MEDIA_ROOT) / "temas_audio"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        mp3_path = output_dir / filename
        
        if mp3_path.exists():
            return mp3_path, "Ya existe (cache)"
        
        try:
            tts = gTTS(text=contenido, lang=lang, slow=slow)
            tts.save(str(mp3_path))
            return mp3_path, "Generado"
        except Exception as e:
            return None, f"Error: {str(e)}"

    def handle(self, *args, **options):
        from simulador.models import Tema, DocumentoContexto
        
        tipo = options['tipo']
        item_id = options['id']
        max_chars = options['max_chars']
        lang = options['voz']
        slow = options['lento']
        
        self.stdout.write(self.style.SUCCESS(f'\nGenerando MP3s...'))
        self.stdout.write(f'Tipo: {tipo} | Max chars: {max_chars} | Voz: {lang} | Lento: {slow}\n')
        
        if tipo in ['tema', 'todos']:
            if item_id:
                temas = Tema.objects.filter(id=item_id)
            else:
                temas = Tema.objects.filter(contenido_texto__isnull=False).exclude(contenido_texto='')
        else:
            temas = Tema.objects.none()
        
        if tipo in ['documento', 'todos']:
            if item_id:
                documentos = DocumentoContexto.objects.filter(id=item_id)
            else:
                documentos = DocumentoContexto.objects.filter(contenido_texto__isnull=False).exclude(contenido_texto='')
        else:
            documentos = DocumentoContexto.objects.none()
        
        generados = 0
        errores = 0
        skipped = 0
        
        for tema in temas:
            self.stdout.write(f'\n[TEMA {tema.id}] {tema.nombre}...')
            
            if tema.archivo_audio and Path(settings.MEDIA_ROOT) / tema.archivo_audio.name:
                self.stdout.write(f'  ⚠ Ya tiene MP3: {tema.archivo_audio.name}')
                skipped += 1
                continue
            
            mp3_path, estado = self.generar_mp3(
                tema.contenido_texto,
                f"tema_{tema.id}",
                max_chars,
                lang,
                slow
            )
            
            if mp3_path:
                tema.archivo_audio = f"temas_audio/{mp3_path.name}"
                tema.save(update_fields=['archivo_audio'])
                self.stdout.write(self.style.SUCCESS(f'  ✓ {mp3_path.name} ({mp3_path.stat().st_size // 1024}KB)'))
                generados += 1
            else:
                self.stdout.write(self.style.ERROR(f'  ✗ {estado}'))
                errores += 1
        
        for doc in documentos:
            self.stdout.write(f'\n[DOC {doc.id}] {doc.nombre}...')
            
            mp3_path, estado = self.generar_mp3(
                doc.contenido_texto,
                f"doc_{doc.id}_{doc.tipo}",
                max_chars,
                lang,
                slow
            )
            
            if mp3_path:
                self.stdout.write(self.style.SUCCESS(f'  ✓ {mp3_path.name} ({mp3_path.stat().st_size // 1024}KB)'))
                self.stdout.write(f'  ℹ Nota: Vincula manualmente al curso en el admin')
                generados += 1
            else:
                self.stdout.write(self.style.ERROR(f'  ✗ {estado}'))
                errores += 1
        
        self.stdout.write(self.style.SUCCESS(f'\n========== RESUMEN =========='))
        self.stdout.write(f'MP3s generados: {generados}')
        self.stdout.write(f'Saltados (ya existen): {skipped}')
        self.stdout.write(f'Errores: {errores}')
        self.stdout.write('==============================\n')
