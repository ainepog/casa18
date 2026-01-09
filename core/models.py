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
    proyecto = models.ForeignKey(Proyecto, on_delete=models.CASCADE)
    nombre = models.CharField(max_length=200)
    tipo = models.CharField(max_length=100)
    fecha_emision = models.DateField(null=True, blank=True)
    archivo = models.FileField(upload_to='documentos_proyecto/', null=True, blank=True)
    estado = models.CharField(max_length=50, default='Vigente')

    def __str__(self): return self.nombre


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
    nombre_completo = models.CharField(max_length=200)
    tipo_documento = models.CharField(max_length=10, choices=TIPO_DOC_INVERSOR, default='DNI')
    nro_doc = models.CharField(max_length=20, unique=True)
    direccion = models.CharField(max_length=255, null=True, blank=True)
    correo = models.EmailField(null=True, blank=True)
    telefono = models.CharField(max_length=20, null=True, blank=True)

    class Meta: verbose_name_plural = "Inversores"

    def __str__(self): return self.nombre_completo


class Inversion(models.Model):
    inversor = models.ForeignKey(Inversor, on_delete=models.CASCADE)
    proyecto = models.ForeignKey(Proyecto, on_delete=models.CASCADE)

    moneda = models.CharField(max_length=3, choices=OPCIONES_MONEDA, default='PEN')
    capital_monto = models.DecimalField(max_digits=12, decimal_places=2)
    fecha_desembolso = models.DateField()
    tea_anual = models.DecimalField(max_digits=5, decimal_places=2)
    plazo_meses = models.IntegerField()
    frecuencia = models.CharField(max_length=20, choices=[('Mensual', 'Mensual'), ('Trimestral', 'Trimestral')])
    estado = models.CharField(max_length=20, default='Activo', editable=False)

    class Meta: verbose_name_plural = "Inversiones"

    def __str__(self): return f"Inv {self.id} - {self.inversor}"

    def generar_cronograma_pagos(self):
        ultima_pagada = self.cuotas.filter(estado='Pagado').aggregate(Max('nro_cuota'))['nro_cuota__max'] or 0
        self.cuotas.filter(nro_cuota__gt=ultima_pagada).delete()


        if self.frecuencia == 'Trimestral':
            frecuencia_anual = 4
            meses_a_sumar = 3
        else:  # Mensual
            frecuencia_anual = 12
            meses_a_sumar = 1


        tasa_periodo_fija = (self.tea_anual / 100) / frecuencia_anual

        monto_interes_fijo = self.capital_monto * tasa_periodo_fija

        num_cuotas = int(self.plazo_meses / meses_a_sumar)
        fecha_actual = self.fecha_desembolso
        cuotas_batch = []
        hoy = date.today()

        for i in range(1, num_cuotas + 1):
            fecha_programada = fecha_actual + timedelta(days=30 * meses_a_sumar)
            fecha_final = obtener_siguiente_dia_habil(fecha_programada)

            dias_reales = (fecha_final - fecha_actual).days

            impuesto = monto_interes_fijo * Decimal('0.05')
            neto = monto_interes_fijo - impuesto

            es_ultima = (i == num_cuotas)
            amortizacion = self.capital_monto if es_ultima else Decimal('0.00')
            total = neto + amortizacion
            estado_ini = 'Pagado' if fecha_final < hoy else 'Pendiente'

            cuotas_batch.append(CuotaInversion(
                inversion=self,
                nro_cuota=i,
                fecha_programada=fecha_final,
                dias_periodo=dias_reales,  # Informativo
                saldo_capital=self.capital_monto,

                interes_bruto=monto_interes_fijo,
                monto_impuesto=impuesto,
                interes_neto=neto,
                amortizacion_capital=amortizacion,
                total_pagar=total,
                es_ultima_cuota=es_ultima,
                estado=estado_ini
            ))

            fecha_actual = fecha_final

        CuotaInversion.objects.bulk_create(cuotas_batch)
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


class Cliente(models.Model):
    nombre = models.CharField(max_length=200)
    correo = models.EmailField(unique=True)
    telefono = models.CharField(max_length=20)

    def __str__(self): return self.nombre


class ClienteProyecto(models.Model):
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE)
    proyecto = models.ForeignKey(Proyecto, on_delete=models.CASCADE)
    fecha_interes = models.DateField(auto_now_add=True)
    estado_interes = models.CharField(max_length=50, choices=ESTADOS_INTERES, default='Seguimiento')
    observaciones = models.TextField(blank=True)

    class Meta:
        verbose_name = "Interés / Lead"
        verbose_name_plural = "Intereses / Leads"

    def __str__(self): return f"{self.cliente} en {self.proyecto}"


class Venta(models.Model):
    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT)
    departamento = models.OneToOneField(Departamento, on_delete=models.PROTECT)
    fecha_venta = models.DateField()

    moneda = models.CharField(max_length=3, choices=OPCIONES_MONEDA, default='PEN')
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

class AgendaPagos(CuotaInversion):
    class Meta:
        proxy = True
        verbose_name = "Calendario de Pagos"
        verbose_name_plural = "Calendario de Pagos"