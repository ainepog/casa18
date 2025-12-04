# Create your models here.
from django.db import models
from django.core.validators import MinValueValidator
from decimal import Decimal
import math
from django.db.models.signals import post_save
from django.dispatch import receiver
import holidays
from datetime import timedelta, date

pe_holidays = holidays.PE()

def obtener_siguiente_dia_habil(fecha):
    """
    Si la fecha cae sábado (5), domingo (6) o Feriado,
    se mueve al siguiente día laborable.
    """
    # Mientras sea fin de semana O sea feriado en Perú
    while fecha.weekday() >= 5 or fecha in pe_holidays:
        fecha += timedelta(days=1)
    return fecha


# --- UTILIDADES (Opciones para selectores) ---
ESTADOS_PROYECTO = [('Planos', 'En Planos'),('Preventa', 'En Preventa'), ('Construccion', 'En Construcción'), ('Entregado', 'Entregado')]
TIPO_GASTO = [('Directo', 'Gasto Directo'), ('Indirecto', 'Gasto Indirecto')]
FRECUENCIA_PAGO = [('Mensual', 'Mensual'), ('Bimestral', 'Bimestral'), ('Trimestral', 'Trimestral')]
ESTADO_DISPONIBILIDAD = [('Disponible', 'Disponible'), ('Separado', 'Separado'), ('Vendido', 'Vendido')]


# ==========================================
# MÓDULO CENTRAL (PROYECTOS)
# ==========================================

class Proyecto(models.Model):
    nombre = models.CharField(max_length=200)
    ubicacion = models.CharField(max_length=255)
    estado = models.CharField(max_length=50, choices=ESTADOS_PROYECTO, default='Planos')
    fecha_inicio = models.DateField()
    fecha_entrega = models.DateField(null=True, blank=True)

    # Regla del Banco
    total_unidades = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    meta_ventas_banco = models.IntegerField(default=0, editable=False,
                                            help_text="Calculado automáticamente (30% del total)")
    banco_activado = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        # Lógica Automática 1: Calcular meta del banco (Ceiling del 30%)
        if self.total_unidades > 0:
            self.meta_ventas_banco = math.ceil(self.total_unidades * 0.30)
        # Lógica Automática 2: Activar banco si hay suficientes ventas (se vería en el futuro)
        # Por ahora lo dejamos manual o base
        super().save(*args, **kwargs)

    def __str__(self):
        return self.nombre


class Documento(models.Model):
    proyecto = models.ForeignKey(Proyecto, on_delete=models.CASCADE)
    nombre = models.CharField(max_length=200)
    tipo = models.CharField(max_length=100)  # Licencia, Contrato, etc.
    fecha_emision = models.DateField(null=True, blank=True)
    fecha_vencimiento = models.DateField(null=True, blank=True)
    url_archivo = models.URLField(help_text="Link a Google Drive / Dropbox")
    estado = models.CharField(max_length=50, default='Vigente')

    def __str__(self):
        return f"{self.nombre} ({self.proyecto.nombre})"


# ==========================================
# MÓDULO 2: CONSTRUCCIÓN Y PROVEEDORES
# ==========================================

class Proveedor(models.Model):
    razon_social = models.CharField(max_length=200, unique=True)
    ruc = models.CharField(max_length=20, unique=True)
    tipo_servicio = models.CharField(max_length=100, help_text="Ej: Construcción, Legal, Marketing")
    telefono = models.CharField(max_length=20, null=True, blank=True)
    correo = models.EmailField(null=True, blank=True)

    def __str__(self):
        return self.razon_social


class ProveedorProyecto(models.Model):
    proyecto = models.ForeignKey(Proyecto, on_delete=models.CASCADE)
    proveedor = models.ForeignKey(Proveedor, on_delete=models.CASCADE)
    tipo_contrato = models.CharField(max_length=100)
    monto_estimado = models.DecimalField(max_digits=12, decimal_places=2)
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField(null=True, blank=True)

    def __str__(self):
        return f"{self.proveedor} en {self.proyecto}"


class Gasto(models.Model):
    proyecto = models.ForeignKey(Proyecto, on_delete=models.CASCADE)
    proveedor = models.ForeignKey(Proveedor, on_delete=models.SET_NULL, null=True, blank=True)
    tipo_gasto = models.CharField(max_length=20, choices=TIPO_GASTO)
    descripcion = models.CharField(max_length=255)
    monto = models.DecimalField(max_digits=12, decimal_places=2)
    fecha_gasto = models.DateField()
    nro_comprobante = models.CharField(max_length=50, null=True, blank=True)
    url_comprobante = models.FileField(upload_to='comprobantes/', null=True,
                                       blank=True)  # Ojo: En Railway requiere config extra, usar URLField si quieres simpleza
    estado = models.CharField(max_length=50, default='Pagado')

    def __str__(self):
        return f"{self.descripcion} - S/{self.monto}"


# ==========================================
# MÓDULO 1: INVERSIONES (LÓGICA FINANCIERA)
# ==========================================

class Inversor(models.Model):
    nombre_completo = models.CharField(max_length=200)
    tipo_doc = models.CharField(max_length=20, default='DNI')
    nro_doc = models.CharField(max_length=20, unique=True)
    correo = models.EmailField()
    telefono = models.CharField(max_length=20, null=True, blank=True)
    direccion = models.TextField(null=True, blank=True)

    def __str__(self):
        return self.nombre_completo


class Inversion(models.Model):
    inversor = models.ForeignKey(Inversor, on_delete=models.CASCADE)
    proyecto = models.ForeignKey(Proyecto, on_delete=models.CASCADE)
    capital_monto = models.DecimalField(max_digits=12, decimal_places=2)
    fecha_desembolso = models.DateField()
    tea_anual = models.DecimalField(max_digits=5, decimal_places=4)
    plazo_meses = models.IntegerField()
    frecuencia_nombre = models.CharField(max_length=20, choices=FRECUENCIA_PAGO)

    dias_periodo = models.IntegerField(editable=False, default=0)
    tasa_periodo = models.DecimalField(max_digits=10, decimal_places=6, editable=False, default=0)
    total_cuotas = models.IntegerField(editable=False, default=0)

    # Estados: Activo, Cancelado (Pagado Total), Mora
    estado = models.CharField(max_length=20, default='Activo')

    def save(self, *args, **kwargs):
        # ... (Tu lógica de cálculo de tasas se mantiene igual) ...
        if self.frecuencia_nombre == 'Mensual':
            self.dias_periodo = 30
        elif self.frecuencia_nombre == 'Bimestral':
            self.dias_periodo = 60
        elif self.frecuencia_nombre == 'Trimestral':
            self.dias_periodo = 90

        base = Decimal(1) + self.tea_anual
        exponente = Decimal(self.dias_periodo) / Decimal(360)
        self.tasa_periodo = Decimal(math.pow(float(base), float(exponente))) - 1

        if self.dias_periodo > 0:
            self.total_cuotas = int(self.plazo_meses / (self.dias_periodo / 30))

        super().save(*args, **kwargs)

    def __str__(self):
        return f"Inv {self.id} - {self.inversor}"


class CuotaInversion(models.Model):
    inversion = models.ForeignKey(Inversion, related_name='cuotas', on_delete=models.CASCADE)
    nro_cuota = models.IntegerField()
    fecha_programada = models.DateField()  # Esta se calculará evitando feriados
    fecha_pago_real = models.DateField(null=True, blank=True)  # Cuándo pagó de verdad

    es_ultima_cuota = models.BooleanField(default=False)

    saldo_capital = models.DecimalField(max_digits=12, decimal_places=2)
    interes_bruto = models.DecimalField(max_digits=12, decimal_places=2)
    monto_impuesto = models.DecimalField(max_digits=12, decimal_places=2)
    interes_neto = models.DecimalField(max_digits=12, decimal_places=2)
    amortizacion_capital = models.DecimalField(max_digits=12, decimal_places=2)
    total_pagar = models.DecimalField(max_digits=12, decimal_places=2)

    # Estado: Pendiente -> Pagado
    estado = models.CharField(max_length=20, default='Pendiente',
                              choices=[('Pendiente', 'Pendiente'), ('Pagado', 'Pagado')])

    def __str__(self):
        return f"Cuota {self.nro_cuota} - {self.inversion.inversor}"

    def alerta_estado(self):
        # 1. PROTECCIÓN: Si no hay fecha programada (porque es nueva), no hacemos nada
        if not self.fecha_programada:
            return "—"

        if self.estado == 'Pagado':
            return " Pagado"

        # Ahora sí es seguro restar porque sabemos que hay fecha
        dias_restantes = (self.fecha_programada - date.today()).days

        if dias_restantes < 0:
            return "VENCIDO"
        elif dias_restantes <= 1:
            return "Vence Mañana/Hoy"
        else:
            return f" Faltan {dias_restantes} días"


@receiver(post_save, sender=Inversion)
def generar_cronograma_pagos(sender, instance, created, **kwargs):
    if created:
        # Solo si es nueva inversión, generamos las cuotas
        saldo_actual = instance.capital_monto
        fecha_base = instance.fecha_desembolso

        for i in range(1, instance.total_cuotas + 1):
            # 1. Calcular Fecha (Sumar días según periodo: 30, 60, 90...)
            dias_a_sumar = instance.dias_periodo * i
            fecha_tentativa = fecha_base + timedelta(days=dias_a_sumar)

            # 2. APLICAR LÓGICA PERÚ (Evitar feriados/findes)
            fecha_final = obtener_siguiente_dia_habil(fecha_tentativa)

            # 3. Determinar si es última cuota
            es_ultima = (i == instance.total_cuotas)

            # 4. Cálculos Financieros
            interes_bruto = saldo_actual * instance.tasa_periodo
            impuesto = interes_bruto * Decimal(0.05)  # 5% Renta
            interes_neto = interes_bruto - impuesto

            # Bullet: Solo amortiza capital al final
            amortizacion = saldo_actual if es_ultima else Decimal(0)
            total = interes_neto + amortizacion

            # 5. Crear la Cuota en BD
            CuotaInversion.objects.create(
                inversion=instance,
                nro_cuota=i,
                fecha_programada=fecha_final,
                es_ultima_cuota=es_ultima,
                saldo_capital=saldo_actual,
                interes_bruto=round(interes_bruto, 2),
                monto_impuesto=round(impuesto, 2),
                interes_neto=round(interes_neto, 2),
                amortizacion_capital=round(amortizacion, 2),
                total_pagar=round(total, 2),
                estado='Pendiente'
            )

@receiver(post_save, sender=CuotaInversion)
def verificar_fin_inversion(sender, instance, **kwargs):
    if instance.estado == 'Pagado':
        # Buscamos la inversión padre
        inv_padre = instance.inversion

        # Contamos cuántas cuotas quedan pendientes
        pendientes = inv_padre.cuotas.filter(estado='Pendiente').count()

        # Si ya no hay pendientes, cerramos el contrato
        if pendientes == 0:
            inv_padre.estado = 'Cancelado'  # O 'Finalizado'
            inv_padre.save()
            print(f"Inversión {inv_padre.id} completada y cancelada")

# ==========================================
# MÓDULO 3: VENTAS Y CLIENTES (CRM)
# ==========================================

class TipoDepartamento(models.Model):
    proyecto = models.ForeignKey(Proyecto, on_delete=models.CASCADE)
    nombre = models.CharField(max_length=100)  # Ej: Flat Tipo A
    descripcion = models.TextField(blank=True)
    plano_modelo = models.URLField(blank=True, null=True)

    def __str__(self):
        return f"{self.nombre} - {self.proyecto}"


class Departamento(models.Model):
    tipo = models.ForeignKey(TipoDepartamento, on_delete=models.CASCADE)
    nro = models.CharField(max_length=20)  # 301
    area_m2 = models.DecimalField(max_digits=6, decimal_places=2)
    precio = models.DecimalField(max_digits=12, decimal_places=2)
    estado_disponibilidad = models.CharField(max_length=20, choices=ESTADO_DISPONIBILIDAD, default='Disponible')

    def __str__(self):
        return f"Dpto {self.nro} ({self.estado_disponibilidad})"


class Cliente(models.Model):
    nombre = models.CharField(max_length=200)
    correo = models.EmailField(unique=True)
    telefono = models.CharField(max_length=20)

    def __str__(self):
        return self.nombre


class ClienteProyecto(models.Model):
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE)
    proyecto = models.ForeignKey(Proyecto, on_delete=models.CASCADE)
    fecha_interes = models.DateField(auto_now_add=True)
    estado_interes = models.CharField(max_length=50, default='Seguimiento')


class Venta(models.Model):
    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT)
    departamento = models.OneToOneField(Departamento,
                                        on_delete=models.PROTECT)  # OneToOne asegura que no se venda 2 veces
    fecha_venta = models.DateField()
    monto = models.DecimalField(max_digits=12, decimal_places=2)
    tipo_financiamiento = models.CharField(max_length=50)  # Hipotecario, etc
    entidad_financiera = models.CharField(max_length=100, null=True, blank=True)
    porcentaje_financiado = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)

    def save(self, *args, **kwargs):
        # Al guardar una venta, marcar el depa como vendido automáticamente
        self.departamento.estado_disponibilidad = 'Vendido'
        self.departamento.save()
        super().save(*args, **kwargs)


@receiver(post_save, sender=Venta)
def verificar_meta_banco(sender, instance, created, **kwargs):
    """
    Cuando se vende un depa, verifica si ya alcanzamos la meta del banco.
    Si es así:
    1. Activa el financiamiento (banco_activado = True).
    2. Cambia el estado del proyecto a 'Construccion'.
    """
    if created:
        # 1. Buscamos el proyecto
        proyecto = instance.departamento.tipo.proyecto
        # 2. Contamos cuántas ventas llevamos
        ventas_actuales = Venta.objects.filter(departamento__tipo__proyecto=proyecto).count()
        # 3. Verificamos si cruzamos la meta
        if ventas_actuales >= proyecto.meta_ventas_banco:
            cambios = False
            # A. Activar Banco
            if not proyecto.banco_activado:
                proyecto.banco_activado = True
                cambios = True
            # B. Cambiar Estado a Construcción (Solo si estaba en fases previas)
            if proyecto.estado in ['Planos', 'Preventa']:
                proyecto.estado = 'Construccion'
                cambios = True
            if cambios:
                proyecto.save()
