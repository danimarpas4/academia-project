import re
from django.core.management.base import BaseCommand
from simulador.models import DocumentoContexto


class Command(BaseCommand):
    help = 'Limpia y optimiza el contenido de texto de los DocumentosContexto para el Tutor IA'

    def add_arguments(self, parser):
        parser.add_argument(
            '--documento-id',
            type=int,
            help='ID específico del documento a procesar (opcional)',
        )
        parser.add_argument(
            '--extraccion-solo',
            action='store_true',
            help='Solo extrae texto de PDFs sin limpiar',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Muestra detalles del procesamiento',
        )

    def limpiar_texto(self, texto):
        """
        Limpia el texto eliminando 'paja': espacios, índices, bibliografía, etc.
        """
        if not texto:
            return ""
        
        lineas = texto.split('\n')
        lineas_limpias = []
        
        patrones_paja = [
            r'^ ÍNDICE',
            r'^ Í N D I C E',
            r'^BIBLIOGRAFÍA',
            r'^BIBLIOGRAFIA',
            r'^REFERENCIAS',
            r'^FUENTES',
            r'^\s*\d+\s*$',
            r'^\s*Página\s+\d+',
            r'^\s*pag\.\s*\d+',
            r'^\s*©\s*\d{4}',
            r'^\s*Todos\s+los\s+derechos\s+reservados',
            r'^ANEXO\s+I',
            r'^ANEXO\s+II',
            r'^\s*—\s*$',
        ]
        
        texto_limpio_anterior = ""
        
        for i, linea in enumerate(lineas):
            linea_original = linea
            linea = linea.strip()
            
            if not linea:
                continue
            
            if len(linea) < 5:
                continue
            
            es_paja = False
            for patron in patrones_paja:
                if re.match(patron, linea, re.IGNORECASE):
                    es_paja = True
                    break
            
            if es_paja:
                continue
            
            if re.match(r'^[\d\.\,\:]+$', linea):
                continue
            
            linea = re.sub(r'\s+', ' ', linea)
            linea = re.sub(r'\.{3,}', '...', linea)
            linea = re.sub(r'\.{2}\s*\.{2}', '...', linea)
            
            if linea == texto_limpio_anterior:
                continue
            
            lineas_limpias.append(linea)
            texto_limpio_anterior = linea
        
        texto_resultado = ' '.join(lineas_limpias)
        
        texto_resultado = re.sub(r'\s+([.,;:!?])', r'\1', texto_resultado)
        texto_resultado = re.sub(r'([¡¿])\s+', r'\1', texto_resultado)
        texto_resultado = re.sub(r'\(\s+', '(', texto_resultado)
        texto_resultado = re.sub(r'\s+\)', ')', texto_resultado)
        texto_resultado = re.sub(r'\s*–\s*', ' – ', texto_resultado)
        
        return texto_resultado.strip()

    def handle(self, *args, **options):
        verbose = options.get('verbose', False)
        documento_id = options.get('documento_id')
        extraccion_solo = options.get('extraccion_solo', False)
        
        if documento_id:
            documentos = DocumentoContexto.objects.filter(id=documento_id)
        else:
            documentos = DocumentoContexto.objects.filter(activo=True)
        
        total = documentos.count()
        self.stdout.write(self.style.SUCCESS(f'\nProcesando {total} documento(s)...\n'))
        
        procesados = 0
        limpiados = 0
        errores = 0
        
        for doc in documentos:
            try:
                self.stdout.write(f'\n--- {doc.nombre} ---')
                
                if doc.archivo and not doc.contenido_texto:
                    self.stdout.write('  Extrayendo texto del PDF...')
                    texto_extraido = doc.extraer_texto_pdf()
                    if texto_extraido:
                        self.stdout.write(self.style.SUCCESS(f'  ✓ Extraídos {len(texto_extraido)} caracteres'))
                    else:
                        self.stdout.write(self.style.WARNING('  ⚠ No se pudo extraer texto del PDF'))
                        continue
                
                if doc.contenido_texto:
                    texto_original = doc.contenido_texto
                    caracteres_originales = len(texto_original)
                    
                    if not extraccion_solo:
                        texto_limpio = self.limpiar_texto(texto_original)
                        caracteres_limpios = len(texto_limpio)
                        reduccion = ((caracteres_originales - caracteres_limpios) / caracteres_originales) * 100
                        
                        doc.contenido_texto = texto_limpio
                        doc.save()
                        
                        self.stdout.write(f'  Original: {caracteres_originales:,} chars')
                        self.stdout.write(f'  Limpio:   {caracteres_limpios:,} chars')
                        self.stdout.write(f'  Reducción: {reduccion:.1f}%')
                        
                        if verbose:
                            self.stdout.write(f'  Muestra: {texto_limpio[:200]}...')
                        
                        limpiados += 1
                    else:
                        self.stdout.write(f'  Texto actual: {caracteres_originales:,} chars')
                    
                    procesados += 1
                else:
                    self.stdout.write(self.style.WARNING('  ⚠ Sin contenido de texto'))
                    
            except Exception as e:
                errores += 1
                self.stdout.write(self.style.ERROR(f'  ✗ Error: {str(e)}'))
        
        self.stdout.write(self.style.SUCCESS(f'\n========== RESUMEN =========='))
        self.stdout.write(f'Documentos procesados: {procesados}')
        self.stdout.write(f'Documentos limpiados: {limpiados}')
        self.stdout.write(f'Errores: {errores}')
        self.stdout.write(self.style.SUCCESS('============================\n'))
