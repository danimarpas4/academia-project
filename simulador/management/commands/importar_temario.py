import os
import re
from django.core.management.base import BaseCommand
from simulador.models import DocumentoContexto, Curso


class Command(BaseCommand):
    help = 'Importa PDFs del directorio media/temarios/ como DocumentosContexto'

    def add_arguments(self, parser):
        parser.add_argument(
            '--carpeta',
            type=str,
            default='ascenso_a_cabo',
            help='Carpeta dentro de media/temarios/ a procesar (default: ascenso_a_cabo)',
        )
        parser.add_argument(
            '--curso-id',
            type=int,
            default=1,
            help='ID del curso al que asociar (default: 1 - Ascenso a Cabo)',
        )
        parser.add_argument(
            '--skip-existing',
            action='store_true',
            help='No procesar si ya existe un documento con el mismo nombre',
        )
        parser.add_argument(
            '--extract-only',
            action='store_true',
            help='Solo extraer texto de PDFs ya existentes en la BD',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Sobrescribir contenido_texto aunque ya exista',
        )

    def handle(self, *args, **options):
        carpeta = options['carpeta']
        curso_id = options['curso_id']
        skip_existing = options['skip_existing']
        extract_only = options['extract_only']
        force = options['force']

        try:
            curso = Curso.objects.get(id=curso_id)
        except Curso.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'No existe curso con ID {curso_id}'))
            return

        base_dir = os.path.join(settings.MEDIA_ROOT, 'temarios', carpeta)
        if not os.path.isdir(base_dir):
            self.stdout.write(self.style.ERROR(f'Carpeta no encontrada: {base_dir}'))
            return

        self.stdout.write(self.style.SUCCESS(f'\nProcesando carpeta: {carpeta}'))
        self.stdout.write(f'Curso: {curso.nombre} (ID: {curso_id})')
        self.stdout.write(f'Base: {base_dir}\n')

        extensiones = ['.pdf', '.txt']
        archivos = [f for f in os.listdir(base_dir) if any(f.lower().endswith(ext) for ext in extensiones)]

        if not archivos:
            self.stdout.write(self.style.WARNING('No se encontraron PDFs o TXTs'))
            return

        creados = 0
        existentes = 0
        errores = 0
        extraidos = 0

        for nombre_archivo in sorted(archivos):
            ruta_completa = os.path.join(base_dir, nombre_archivo)
            
            if extract_only:
                continue

            nombre_base = os.path.splitext(nombre_archivo)[0]
            
            if skip_existing and DocumentoContexto.objects.filter(nombre__icontains=nombre_base).exists():
                self.stdout.write(f'  ⏭ Saltando (ya existe): {nombre_archivo}')
                existentes += 1
                continue

            try:
                doc = DocumentoContexto.objects.create(
                    curso=curso,
                    nombre=nombre_base,
                    tipo='TEMARIO',
                    archivo=f'temarios/{carpeta}/{nombre_archivo}',
                )
                self.stdout.write(self.style.SUCCESS(f'  ✓ Creado: {nombre_base}'))
                
                if nombre_archivo.lower().endswith('.pdf'):
                    texto = doc.extraer_texto_pdf()
                    if texto:
                        self.stdout.write(f'    → Extraídos {len(texto):,} caracteres')
                        extraidos += 1
                    else:
                        self.stdout.write(self.style.WARNING(f'    → No se pudo extraer texto'))
                
                creados += 1
                
            except Exception as e:
                errores += 1
                self.stdout.write(self.style.ERROR(f'  ✗ Error: {str(e)}'))

        self.stdout.write(self.style.SUCCESS(f'\n========== RESUMEN =========='))
        self.stdout.write(f'Documentos creados: {creados}')
        self.stdout.write(f'Documentos ya existentes (saltados): {existentes}')
        self.stdout.write(f'Textos extraídos: {extraidos}')
        self.stdout.write(f'Errores: {errores}')
        self.stdout.write(self.style.SUCCESS('============================\n'))


from django.conf import settings
