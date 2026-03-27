import hashlib
import hmac
import base64
import json
import logging
from decimal import Decimal
from django.conf import settings
from Crypto.Cipher import DES3

logger = logging.getLogger('simulador')

class RedsysPayment:
    PRECIO_BASE = Decimal('9.99')
    
    CURSOS_PRECIOS = {
        'cabo': 'Ascenso a Cabo',
        'cabo-primero': 'Cabo Primero',
        'permanencia': 'Permanencia',
    }
    
    @classmethod
    def calcular_importe(cls, perfil, curso_slug=None):
        saldo_total = Decimal(str(perfil.descuento_acumulado or 0))
        importe_final = max(Decimal('0.00'), cls.PRECIO_BASE - saldo_total)
        importe_centimos = int(importe_final * 100)
        return importe_centimos, saldo_total, importe_final
    
    @classmethod
    def crear_pago(cls, request, perfil, curso_slug, importe_centimos, numero_pedido):
        # CREDENCIALES DE PRUEBAS (SANDBOX)
        merchant_code = '999008881'
        terminal = '001'  # Terminal de 3 dígitos
        secret_key = 'sq7H5Yz6IFZH8Ut440936khq79293474'
        
        # El pedido DEBE tener al menos 4 dígitos. Redsys recomienda 12.
        order_id = str(numero_pedido).zfill(4)[:12]

        # Los nombres de las claves dentro del JSON deben ir en MAYÚSCULAS
        # IMPORTANTE: El amount debe ser integer, no string
        amount_int = int(importe_centimos) if importe_centimos else 0
        
        merchant_params = {
            'DS_MERCHANT_AMOUNT': amount_int,
            'DS_MERCHANT_ORDER': order_id,
            'DS_MERCHANT_MERCHANTCODE': merchant_code,
            'DS_MERCHANT_CURRENCY': 978,  # Integer, no string
            'DS_MERCHANT_TRANSACTIONTYPE': '0', # Autorización
            'DS_MERCHANT_TERMINAL': terminal,  # Enviar como string para sandbox
            'DS_MERCHANT_URLOK': settings.REDSYS_URL_OK,
            'DS_MERCHANT_URLKO': settings.REDSYS_URL_KO,
            'DS_MERCHANT_MERCHANTURL': settings.REDSYS_WEBHOOK_URL,
            'DS_MERCHANT_PRODUCTDESCRIPTION': f"Suscripcion {cls.CURSOS_PRECIOS.get(curso_slug, 'ProMilitar')}"[:125],
            'DS_MERCHANT_TITULAR': (request.user.get_full_name() or request.user.username)[:60],
            'DS_MERCHANT_MERCHANTNAME': 'PROMilitar',
        }

        # 1. Convertir a JSON (sin espacios) y a Base64
        json_params = json.dumps(merchant_params, separators=(',', ':'))
        b64_params = base64.b64encode(json_params.encode()).decode()
        
        # Debug: mostrar JSON y decodificar params
        print(f"✅ REDSYS JSON: {json_params}")
        decoded = base64.b64decode(b64_params).decode()
        print(f"✅ REDSYS DECODED: {decoded}")
        
        # 2. Generar la firma electrónica
        signature = cls._generar_firma_v1(order_id, b64_params, secret_key)
        
        print(f"✅ REDSYS DEBUG: Enviando {importe_centimos} cts | Pedido {order_id} | Signature: {signature[:10]}...")

        return {
            'Ds_MerchantParameters': b64_params,
            'Ds_Signature': signature,
            'Ds_SignatureVersion': 'HMAC_SHA256_V1',
            'Ds_MerchantCode': merchant_code,
            # Datos para el HTML
            'importe': float(importe_centimos) / 100.0,
            'curso_nombre': cls.CURSOS_PRECIOS.get(curso_slug, 'Curso'),
            # Debug info (sin guion bajo inicial)
            'debug_order': order_id,
            'debug_amount': amount_int,
        }

    @classmethod
    def _generar_firma_v1(cls, order, b64_params, secret_key):
        # A. Decodificar la clave de comercio
        key = base64.b64decode(secret_key)
        
        # B. Triple DES (3DES) requiere que el bloque sea múltiplo de 8
        # Redsys espera que el order_id se cifre con la clave para generar una 'key' de sesión
        iv = b'\0\0\0\0\0\0\0\0'
        cipher = DES3.new(key, DES3.MODE_CBC, iv)
        
        # Rellenamos el pedido con ceros hasta 16 bytes (múltiplo de 8)
        order_bytes = order.encode().ljust(16, b'\0')
        derived_key = cipher.encrypt(order_bytes)
        
        # C. HMAC-SHA256 de los parámetros usando la clave derivada
        signature_hash = hmac.new(derived_key, b64_params.encode(), hashlib.sha256).digest()
        return base64.b64encode(signature_hash).decode()