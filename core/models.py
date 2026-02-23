from django.db import models
from django.core.validators import MinValueValidator
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.db.models import Max
from datetime import date, timedelta
from decimal import Decimal
from .utils import obtener_feriados_peru
import math


# --- UTILIDADES DE FECHA ---
def obtener_siguiente_dia_habil(fecha):
    if not fecha:
        return date.today()
    feriados_actual = obtener_feriados_peru(fecha.year)
    if fecha.month == 12:
        feriados_actual += obtener_feriados_peru(fecha.year + 1)

    while fecha.weekday() >= 5 or fecha in feriados_actual:
        fecha += timedelta(days=1)
        if fecha.year != feriados_actual[0].year and fecha.month > 1:
            feriados_actual = obtener_feriados_peru(fecha.year)
    return fecha


# --- OPCIONES (CHOICES) ---
ESTADOS_PROYECTO = [
    ('Planos', 'En Planos'),
    ('Preventa', 'En Preventa'),
    ('Construccion', 'En Construcción'),
    ('Entregado', 'Entregado')
]
TIPO_GASTO = [('Directo', 'Gasto Directo'), ('Indirecto', 'Gasto Indirecto')]
ESTADO_DISPONIBILIDAD = [('Disponible', 'Disponible'), ('Separado', 'Separado'), ('Vendido', 'Vendido')]
ESTADO_PAGO = [('Pendiente', 'Pendiente'), ('Pagado', 'Pagado')]
TIPOS_FINANCIAMIENTO = [
    ('Hipotecario', 'Crédito Hipotecario'),
    ('Directo', 'Crédito Directo'),
    ('Contado', 'Al Contado'),
]
ESTADOS_INTERES = [
    ('Seguimiento', 'En Seguimiento'),
    ('Negociacion', 'En Negociación'),
    ('Comprado', 'VENTA CERRADA'),
    ('Caido', 'Venta Caída')
]
OPCIONES_MONEDA = [
    ('PEN', 'S/ (Soles)'),
    ('USD', '$ (Dólares)'),
]
TIPO_DOC_INVERSOR = [
    ('DNI', 'DNI'),
    ('RUC', 'RUC')
]


# ==========================================
# MÓDULO PROYECTOS
# ==========================================

class Proyecto(models.Model):
    nombre = models.CharField(max_length=200)
    ubicacion = models.CharField(max_length=255)
    estado = models.CharField(max_length=50, choices=ESTADOS_PROYECTO, default='Planos')
    fecha_inicio = models.DateField()
    fecha_entrega = models.DateField(null=True, blank=True)

    total_unidades = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    meta_ventas_banco = models.IntegerField(default=0, editable=False)
    banco_activado = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        if self.total_unidades > 0:
            self.meta_ventas_banco = math.ceil(self.total_unidades * 0.30)
        super().save(*args, **kwargs)

    def unidades_disponibles(self):
        return Departamento.objects.filter(tipo__proyecto=self, estado_disponibilidad='Disponible').count()

    def __str__(self): return self.nombre


class Documento(models.Model):
    TIPO_DOC_CHOICES = [
        ('PLANO', 'Plano de Departamento'),
        ('COMPROBANTE', 'Comprobante de Pago (Voucher)'),
        ('RETENCION', 'Certificado de Retención'),
        ('CONTRATO', 'Contrato / Documento Legal'),
        ('OTROS', 'Otros'),
    ]

    tipo = models.CharField(max_length=20, choices=TIPO_DOC_CHOICES)
    archivo = models.FileField(upload_to='casa18/documentos/%Y/%m/', null=True, blank=True)
    descripcion = models.CharField(max_length=255, blank=True, help_text="Ej: Voucher de transferencia - Cuota 1")
    fecha_subida = models.DateTimeField(auto_now_add=True, null=True)

    departamento = models.ForeignKey('Departamento', on_delete=models.CASCADE, null=True, blank=True, related_name='documentos')
    inversion = models.ForeignKey('Inversion', on_delete=models.CASCADE, null=True, blank=True, related_name='documentos')
    prestamo = models.ForeignKey('PrestamoTercero', on_delete=models.CASCADE, null=True, blank=True, related_name='documentos')

    class Meta:
        verbose_name = "Archivo / Documento"
        verbose_name_plural = "Archivos / Documentos"

    def __str__(self):
        return f"{self.get_tipo_display()} - {self.descripcion or self.id}"


# ==========================================
# MÓDULO CONSTRUCCIÓN (GASTOS)
# ==========================================

class Proveedor(models.Model):
    razon_social = models.CharField(max_length=200, unique=True)
    ruc = models.CharField(max_length=20, unique=True)
    tipo_servicio = models.CharField(max_length=100)
    telefono = models.CharField(max_length=20, null=True, blank=True)
    correo = models.EmailField(null=True, blank=True)

    class Meta: verbose_name_plural = "Proveedores"
    def __str__(self): return self.razon_social


class ProveedorProyecto(models.Model):
    proyecto = models.ForeignKey(Proyecto, on_delete=models.CASCADE)
    proveedor = models.ForeignKey(Proveedor, on_delete=models.CASCADE)
    tipo_contrato = models.CharField(max_length=100)
    moneda = models.CharField(max_length=3, choices=OPCIONES_MONEDA, default='PEN')
    monto_estimado = models.DecimalField(max_digits=12, decimal_places=2)
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField(null=True, blank=True)

    def __str__(self): return f"{self.proveedor} en {self.proyecto}"


class Gasto(models.Model):
    proyecto = models.ForeignKey(Proyecto, on_delete=models.CASCADE)
    proveedor = models.ForeignKey(Proveedor, on_delete=models.SET_NULL, null=True, blank=True)
    tipo_gasto = models.CharField(max_length=20, choices=TIPO_GASTO)
    descripcion = models.CharField(max_length=255)

    moneda = models.CharField(max_length=3, choices=OPCIONES_MONEDA, default='PEN')
    monto = models.DecimalField(max_digits=12, decimal_places=2)

    fecha_gasto = models.DateField()
    nro_comprobante = models.CharField(max_length=50, null=True, blank=True)
    comprobante = models.FileField(upload_to='gasto_comprobantes/', null=True, blank=True)
    estado = models.CharField(max_length=20, choices=ESTADO_PAGO, default='Pagado')

    def __str__(self): return f"{self.descripcion}"


# ==========================================
# MÓDULO INVERSIONES
# ==========================================

class Inversor(models.Model):
    BANCOS_CHOICES = [
        ('BCP', 'Banco de Crédito del Perú (BCP)'),
        ('BBVA', 'BBVA Continental'),
        ('INTERBANK', 'Interbank'),
        ('SCOTIABANK', 'Scotiabank'),
        ('BANBIF', 'BanBif'),
        ('PICHINCHA', 'Banco Pichincha'),
        ('NACION', 'Banco de la Nación'),
        ('CAJA_AREQUIPA', 'Caja Arequipa'),
        ('OTRO', 'Otro...'),
    ]
    nombre_completo = models.CharField(max_length=200)
    tipo_documento = models.CharField(max_length=10, choices=TIPO_DOC_INVERSOR, default='DNI')
    nro_doc = models.CharField(max_length=20, unique=True)
    direccion = models.CharField(max_length=255, null=True, blank=True)
    correo = models.EmailField(null=True, blank=True)
    telefono = models.CharField(max_length=20, null=True, blank=True)
    banco = models.CharField(max_length=50, choices=BANCOS_CHOICES, blank=True, null=True, verbose_name='Banco de Abono')
    cuenta_abono = models.CharField(max_length=50, blank=True, null=True, verbose_name='Número de Cuenta')
    cci = models.CharField(max_length=50, blank=True, null=True, verbose_name='Código de Cuenta Interbancario (CCI)')

    banco_personalizado = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name='Especificar Otro Banco')

    class Meta: verbose_name_plural = "Inversores"

    def __str__(self): return self.nombre_completo

    @property
    def nombre_banco_real(self):
        if self.banco == 'OTRO':
            return self.banco_personalizado or 'No especificado'
        return self.get_banco_display()


class Inversion(models.Model):
    inversor = models.ForeignKey(Inversor, on_delete=models.CASCADE)
    proyecto = models.ForeignKey(Proyecto, on_delete=models.CASCADE)

    moneda = models.CharField(max_length=3, choices=OPCIONES_MONEDA, default='PEN')
    capital_monto = models.DecimalField(max_digits=12, decimal_places=2)
    fecha_desembolso = models.DateField()
    tea_anual = models.DecimalField(max_digits=5, decimal_places=2)
    plazo_meses = models.IntegerField()
    frecuencia = models.CharField(max_length=20, choices=[('Mensual', 'Mensual'), ('Trimestral', 'Trimestral')])

    RESPONSABLE_CHOICES = [
        ('PROYECTO', 'Proyecto'),
        ('CASA18', 'Casa 18 (Gasto corporativo)'),
        ('COMPARTIDO', 'Compartido (Múltiples destinos)'),
    ]

    responsable_pago = models.CharField(
        max_length=20,
        choices=RESPONSABLE_CHOICES,
        default='PROYECTO',
        verbose_name='Responsable de los Intereses'
    )

    destino_fondos = models.TextField(
        blank=True,
        null=True,
        verbose_name='Destino de los Fondos / Descripción',
        help_text='Ej: $80k para Casa Porta, $20k para remodelación de oficinas Casa 18.'
    )

    TIPO_CALCULO_CHOICES = [
        ('FINANCIERO', 'Financiero (Días exactos - Monto Variable)'),
        ('COMERCIAL', 'Comercial (360 días - Monto Fijo)'),
        ('MANUAL', 'Manual (Personalizado)'),
        ('EQUITY', 'Socio / Capital a Riesgo (Equity)'),
    ]
    tipo_calculo = models.CharField(
        max_length=20,
        choices=TIPO_CALCULO_CHOICES,
        default='FINANCIERO'
    )
    # ===========================================

    estado = models.CharField(max_length=20, default='Activo', editable=False)

    class Meta:
        verbose_name_plural = "Inversiones"

    def __str__(self):
        return f"Inv {self.id} - {self.inversor}"

    def generar_cronograma_pagos(self):
        if self.frecuencia == 'Trimestral':
            frecuencia_anual = 4
            meses_a_sumar = 3
        else:
            frecuencia_anual = 12
            meses_a_sumar = 1

        tasa_diaria_financiera = Decimal(0)
        monto_interes_comercial = Decimal(0)

        if self.tipo_calculo == 'MANUAL':
            return

        # ====================================================
        # BLOQUE CORREGIDO PARA EQUITY (Socios Capitalistas)
        # ====================================================
        if self.tipo_calculo == 'EQUITY':
            self.cuotas.all().delete()

            if self.proyecto and self.proyecto.fecha_entrega:
                fecha_fin = self.proyecto.fecha_entrega
            else:
                fecha_fin = self.fecha_desembolso  # Fallback

            self.cuotas.create(
                nro_cuota=1,
                fecha_programada=fecha_fin,
                interes_bruto=0,
                monto_impuesto=0,
                interes_neto=0,
                amortizacion_capital=self.capital_monto,
                total_pagar=self.capital_monto,
                estado='Pendiente'
            )
            return

        if self.tipo_calculo == 'FINANCIERO':
            tea_valor = float(self.tea_anual)
            tea_decimal = tea_valor / 100.0
            tasa_diaria_financiera = Decimal((1 + tea_decimal) ** (1 / 360) - 1)
        else:
            tasa_periodo = (self.tea_anual / 100) / frecuencia_anual
            monto_interes_comercial = self.capital_monto * tasa_periodo

        num_cuotas = int(self.plazo_meses / meses_a_sumar)
        fecha_actual = self.fecha_desembolso
        hoy = date.today()

        cuotas_existentes = {c.nro_cuota: c for c in self.cuotas.all()}
        cuotas_a_crear = []
        cuotas_a_actualizar = []

        for i in range(1, num_cuotas + 1):
            fecha_programada = fecha_actual + timedelta(days=30 * meses_a_sumar)
            fecha_final = obtener_siguiente_dia_habil(fecha_programada)
            dias_reales = (fecha_final - fecha_actual).days

            if self.tipo_calculo == 'FINANCIERO':
                interes_bruto = self.capital_monto * tasa_diaria_financiera * dias_reales
            else:
                interes_bruto = monto_interes_comercial

            impuesto = interes_bruto * Decimal('0.05')
            neto = interes_bruto - impuesto

            es_ultima = (i == num_cuotas)
            amortizacion = self.capital_monto if es_ultima else Decimal('0.00')
            total = neto + amortizacion

            cuota = cuotas_existentes.get(i)

            if cuota:
                cuota.fecha_programada = fecha_final
                cuota.dias_periodo = dias_reales
                cuota.saldo_capital = self.capital_monto
                cuota.interes_bruto = interes_bruto
                cuota.monto_impuesto = impuesto
                cuota.interes_neto = neto
                cuota.amortizacion_capital = amortizacion
                cuota.total_pagar = total
                cuota.es_ultima_cuota = es_ultima

                cuotas_a_actualizar.append(cuota)
            else:
                estado_ini = 'Pagado' if fecha_final < hoy else 'Pendiente'
                # Aquí usamos self.cuotas.model en lugar de CuotaInversion directo
                nueva_cuota = self.cuotas.model(
                    inversion=self,
                    nro_cuota=i,
                    fecha_programada=fecha_final,
                    dias_periodo=dias_reales,
                    saldo_capital=self.capital_monto,
                    interes_bruto=interes_bruto,
                    monto_impuesto=impuesto,
                    interes_neto=neto,
                    amortizacion_capital=amortizacion,
                    total_pagar=total,
                    es_ultima_cuota=es_ultima,
                    estado=estado_ini
                )
                cuotas_a_crear.append(nueva_cuota)

            fecha_actual = fecha_final

        if cuotas_a_actualizar:
            self.cuotas.model.objects.bulk_update(cuotas_a_actualizar, [
                'fecha_programada', 'dias_periodo', 'saldo_capital', 'interes_bruto',
                'monto_impuesto', 'interes_neto', 'amortizacion_capital', 'total_pagar',
                'es_ultima_cuota'
            ])

        if cuotas_a_crear:
            self.cuotas.model.objects.bulk_create(cuotas_a_crear)

        self.cuotas.filter(nro_cuota__gt=num_cuotas).delete()

        self.actualizar_estado_general()

    def actualizar_estado_general(self):
        hay_pendientes = self.cuotas.filter(estado='Pendiente').exists()
        nuevo_estado = 'Activo' if hay_pendientes else 'Finalizado'
        Inversion.objects.filter(id=self.id).update(estado=nuevo_estado)


class CuotaInversion(models.Model):
    inversion = models.ForeignKey(Inversion, related_name='cuotas', on_delete=models.CASCADE)
    nro_cuota = models.IntegerField()
    fecha_programada = models.DateField()
    fecha_pago_real = models.DateField(null=True, blank=True)
    dias_periodo = models.IntegerField(default=0)
    saldo_capital = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    interes_bruto = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    monto_impuesto = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    interes_neto = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    amortizacion_capital = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_pagar = models.DecimalField(max_digits=12, decimal_places=2)
    es_ultima_cuota = models.BooleanField(default=False)
    estado = models.CharField(max_length=20, choices=[('Pendiente', 'Pendiente'), ('Pagado', 'Pagado')],
                              default='Pendiente')
    comprobante = models.FileField(upload_to='comprobantes/', null=True, blank=True)

    def fecha_pago_texto(self):
        if not self.fecha_programada:
            return "-"

        dias = {0: 'Lunes', 1: 'Martes', 2: 'Miércoles', 3: 'Jueves', 4: 'Viernes', 5: 'Sábado', 6: 'Domingo'}
        meses = {1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril', 5: 'Mayo', 6: 'Junio',
                 7: 'Julio', 8: 'Agosto', 9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre'}

        f = self.fecha_programada
        dia_nombre = dias[f.weekday()]
        mes_nombre = meses[f.month]

        return f"{dia_nombre}, {f.day} de {mes_nombre} de {f.year}"
    fecha_pago_texto.short_description = "Fecha de Pago"

    def alerta_estado(self):
        if not self.fecha_programada: return "—"

        if self.estado == 'Pagado': return "Pagado"
        dias = (self.fecha_programada - date.today()).days
        if dias < 0:
            return f"VENCIDO ({abs(dias)} días)"
        elif dias <= 1:
            return "Vence Pronto"
        return f"Faltan {dias} días"

    def __str__(self):
        return f"Cuota #{self.nro_cuota}"

    class Meta: verbose_name_plural = "Cuotas"

class AgendaPagos(CuotaInversion):
    class Meta:
        proxy = True
        verbose_name = "Agenda de Pagos"
        verbose_name_plural = "Agenda de Pagos"

# ==========================================
# MÓDULO VENTAS Y CLIENTES
# ==========================================

class TipoDepartamento(models.Model):
    proyecto = models.ForeignKey(Proyecto, on_delete=models.CASCADE)
    nombre = models.CharField(max_length=100)
    area_m2 = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    precio_base = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    descripcion = models.TextField(blank=True, null=True)
    plano_modelo = models.FileField(upload_to='planos/', null=True, blank=True)

    def __str__(self): return f"{self.nombre} ({self.area_m2} m²)"


class Departamento(models.Model):
    tipo = models.ForeignKey(TipoDepartamento, on_delete=models.CASCADE)
    nro = models.CharField(max_length=20)
    piso = models.IntegerField(default=1)
    estado_disponibilidad = models.CharField(max_length=20, choices=ESTADO_DISPONIBILIDAD, default='Disponible')

    class Meta: unique_together = ('tipo', 'nro')

    def __str__(self): return f"Dpto {self.nro} - {self.tipo.nombre}"


# =====================================================================
# 1. DIRECTORIO CENTRAL DE CLIENTES (Única Fuente de Verdad)
# =====================================================================
class Cliente(models.Model):
    TIPO_DOC_CHOICES = [('DNI', 'DNI'), ('CE', 'CE'), ('RUC', 'RUC'), ('PASAPORTE', 'Pasaporte')]

    nombre = models.CharField(max_length=200, verbose_name="Nombre / Razón Social")
    tipo_documento = models.CharField(max_length=20, choices=TIPO_DOC_CHOICES, default='DNI')
    nro_documento = models.CharField(max_length=20, unique=True, verbose_name="Nro. Documento")
    correo = models.EmailField(blank=True, null=True)
    telefono = models.CharField(max_length=20, blank=True, null=True)
    direccion = models.CharField(max_length=255, blank=True, null=True)

    es_prospecto_inmobiliario = models.BooleanField(default=True, verbose_name="Es Lead/Prospecto")
    es_prestatario = models.BooleanField(default=False, verbose_name="Es Prestatario (Préstamos)")

    def __str__(self):
        return f"{self.nombre} ({self.nro_documento})"


# =====================================================================
# 2. MÓDULO INMOBILIARIO (Ventas y Leads)
# =====================================================================
class ClienteProyecto(models.Model):
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name='intereses_proyectos')
    proyecto = models.ForeignKey('Proyecto', on_delete=models.CASCADE)  # Asumo que 'Proyecto' está definido arriba
    fecha_interes = models.DateField(auto_now_add=True)

    estado_interes = models.CharField(max_length=50, choices=ESTADOS_INTERES, default='Seguimiento')
    observaciones = models.TextField(blank=True)

    class Meta:
        verbose_name = "Interés / Lead"
        verbose_name_plural = "Intereses / Leads"

    def __str__(self):
        return f"{self.cliente.nombre} en {self.proyecto}"


class Venta(models.Model):
    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT, related_name='compras_inmobiliarias')
    departamento = models.OneToOneField('Departamento', on_delete=models.PROTECT)  # Asumo 'Departamento' existe
    fecha_venta = models.DateField()

    moneda = models.CharField(max_length=3, choices=OPCIONES_MONEDA,
                              default='PEN')  # Asegúrate de tener OPCIONES_MONEDA
    precio_lista = models.DecimalField(max_digits=12, decimal_places=2, editable=False)
    descuento_porcentaje = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    monto = models.DecimalField(max_digits=12, decimal_places=2, editable=False)

    tipo_financiamiento = models.CharField(max_length=20, choices=TIPOS_FINANCIAMIENTO, default='Hipotecario')
    entidad_financiera = models.CharField(max_length=100, null=True, blank=True)
    porcentaje_financiado = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)

    def save(self, *args, **kwargs):
        self.precio_lista = self.departamento.tipo.precio_base
        dinero_descontado = self.precio_lista * (self.descuento_porcentaje / Decimal(100))
        self.monto = self.precio_lista - dinero_descontado

        self.departamento.estado_disponibilidad = 'Vendido'
        self.departamento.save()
        super().save(*args, **kwargs)


# =====================================================================
# MÓDULO DE PRÉSTAMOS A TERCEROS (CASA18 PRESTA DINERO)
# =====================================================================

class PrestamoTercero(models.Model):
    cliente = models.ForeignKey('Cliente', on_delete=models.PROTECT, related_name='prestamos_recibidos')
    motivo_prestamo = models.CharField(max_length=255, verbose_name='Motivo / Concepto',
                                       help_text='Ej: Préstamo personal, compra de auto')

    moneda = models.CharField(max_length=3, choices=OPCIONES_MONEDA, default='PEN')
    capital_monto = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='Monto Prestado')
    fecha_desembolso = models.DateField(verbose_name='Fecha de entrega del dinero')

    tea_anual = models.DecimalField(max_digits=5, decimal_places=2, verbose_name='TEA (%)')
    plazo_meses = models.IntegerField(verbose_name='Plazo (Meses)')
    frecuencia = models.CharField(max_length=20, choices=[('Mensual', 'Mensual'), ('Trimestral', 'Trimestral')],
                                  default='Mensual')

    TIPO_CALCULO_CHOICES = [
        ('FINANCIERO', 'Financiero (Días exactos)'),
        ('COMERCIAL', 'Comercial (360 días)'),
        ('MANUAL', 'Manual (Personalizado)'),
    ]
    tipo_calculo = models.CharField(max_length=20, choices=TIPO_CALCULO_CHOICES, default='FINANCIERO')
    estado = models.CharField(max_length=20, default='Activo', editable=False)

    class Meta:
        verbose_name = "Préstamo a Tercero"
        verbose_name_plural = "Préstamos a Terceros"

    def __str__(self):
        return f"Préstamo {self.id} - {self.cliente}"

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        if self.tipo_calculo in ['FINANCIERO', 'COMERCIAL']:
            self.generar_cronograma_cobros()

    def generar_cronograma_cobros(self):
        from decimal import Decimal
        from datetime import date, timedelta

        if self.tipo_calculo == 'MANUAL':
            return

        frecuencia_anual = 4 if self.frecuencia == 'Trimestral' else 12
        meses_a_sumar = 3 if self.frecuencia == 'Trimestral' else 1

        tasa_diaria_financiera = Decimal(0)
        monto_interes_comercial = Decimal(0)

        if self.tipo_calculo == 'FINANCIERO':
            tea_decimal = float(self.tea_anual) / 100.0
            tasa_diaria_financiera = Decimal((1 + tea_decimal) ** (1 / 360) - 1)
        else:
            tasa_periodo = (self.tea_anual / 100) / frecuencia_anual
            monto_interes_comercial = self.capital_monto * tasa_periodo

        num_cuotas = int(self.plazo_meses / meses_a_sumar)
        fecha_actual = self.fecha_desembolso
        hoy = date.today()

        cuotas_existentes = {c.nro_cuota: c for c in self.cuotas.all()}
        cuotas_a_crear = []
        cuotas_a_actualizar = []

        for i in range(1, num_cuotas + 1):
            fecha_programada = fecha_actual + timedelta(days=30 * meses_a_sumar)
            fecha_final = obtener_siguiente_dia_habil(fecha_programada)
            dias_reales = (fecha_final - fecha_actual).days

            if self.tipo_calculo == 'FINANCIERO':
                interes = self.capital_monto * tasa_diaria_financiera * dias_reales
            else:
                interes = monto_interes_comercial

            es_ultima = (i == num_cuotas)
            amortizacion = self.capital_monto if es_ultima else Decimal('0.00')
            total = interes + amortizacion

            cuota = cuotas_existentes.get(i)
            if cuota:
                cuota.fecha_programada = fecha_final
                cuota.dias_periodo = dias_reales
                cuota.saldo_capital = self.capital_monto
                cuota.interes = interes
                cuota.amortizacion_capital = amortizacion
                cuota.total_pagar = total
                cuota.es_ultima_cuota = es_ultima
                cuotas_a_actualizar.append(cuota)
            else:
                nueva_cuota = self.cuotas.model(
                    prestamo=self,
                    nro_cuota=i,
                    fecha_programada=fecha_final,
                    dias_periodo=dias_reales,
                    saldo_capital=self.capital_monto,
                    interes=interes,
                    amortizacion_capital=amortizacion,
                    total_pagar=total,
                    es_ultima_cuota=es_ultima,
                    estado='Pagado' if fecha_final < hoy else 'Pendiente'
                )
                cuotas_a_crear.append(nueva_cuota)

            fecha_actual = fecha_final

        if cuotas_a_actualizar:
            self.cuotas.model.objects.bulk_update(cuotas_a_actualizar, [
                'fecha_programada', 'dias_periodo', 'saldo_capital', 'interes',
                'amortizacion_capital', 'total_pagar', 'es_ultima_cuota'
            ])
        if cuotas_a_crear:
            self.cuotas.model.objects.bulk_create(cuotas_a_crear)

        self.cuotas.filter(nro_cuota__gt=num_cuotas).delete()
        self.actualizar_estado_general()

    def actualizar_estado_general(self):
        hay_pendientes = self.cuotas.filter(estado__in=['Pendiente', 'Vencido']).exists()
        nuevo_estado = 'Activo' if hay_pendientes else 'Finalizado'
        PrestamoTercero.objects.filter(id=self.id).update(estado=nuevo_estado)


class CuotaPrestamoTercero(models.Model):
    prestamo = models.ForeignKey(PrestamoTercero, related_name='cuotas', on_delete=models.CASCADE)
    nro_cuota = models.IntegerField()
    fecha_programada = models.DateField()
    dias_periodo = models.IntegerField(default=30)
    saldo_capital = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    interes = models.DecimalField(max_digits=10, decimal_places=2)
    amortizacion_capital = models.DecimalField(max_digits=12, decimal_places=2)
    total_pagar = models.DecimalField(max_digits=12, decimal_places=2)

    es_ultima_cuota = models.BooleanField(default=False)
    estado = models.CharField(max_length=20,
                              choices=[('Pendiente', 'Pendiente'), ('Pagado', 'Pagado'), ('Vencido', 'Vencido')],
                              default='Pendiente')

    class Meta:
        ordering = ['nro_cuota']
        verbose_name = "Cuota de Cobro"
        verbose_name_plural = "Cuotas de Cobro"

    def __str__(self):
        return f"Cuota {self.nro_cuota} - {self.prestamo}"

    def save(self, *args, **kwargs):
        from datetime import date
        hoy = date.today()
        if self.fecha_programada and self.fecha_programada < hoy and self.estado == 'Pendiente':
            self.estado = 'Vencido'
        super().save(*args, **kwargs)



# --- SIGNALS ---

@receiver(post_save, sender=Inversion)
def al_guardar_inversion(sender, instance, created, **kwargs):
    if instance.capital_monto and instance.fecha_desembolso:
        instance.generar_cronograma_pagos()


@receiver([post_save, post_delete], sender=CuotaInversion)
def al_cambiar_cuota(sender, instance, **kwargs):
    try:
        instance.inversion.actualizar_estado_general()
    except Inversion.DoesNotExist:
        pass


@receiver(post_save, sender=Venta)
def acciones_post_venta(sender, instance, created, **kwargs):
    if created:
        cp, _ = ClienteProyecto.objects.get_or_create(
            cliente=instance.cliente,
            proyecto=instance.departamento.tipo.proyecto
        )
        cp.estado_interes = 'Comprado'
        cp.observaciones += f"\n Compró el Dpto {instance.departamento.nro}."
        cp.save()

        proyecto = instance.departamento.tipo.proyecto
        ventas = Venta.objects.filter(departamento__tipo__proyecto=proyecto).count()

        cambios = False
        if ventas >= proyecto.meta_ventas_banco:
            if not proyecto.banco_activado:
                proyecto.banco_activado = True
                cambios = True
            if proyecto.estado in ['Planos', 'Preventa']:
                proyecto.estado = 'Construccion'
                cambios = True
            if cambios:
                proyecto.save()
