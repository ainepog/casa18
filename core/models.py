# Create your models here.
from django.db import models
from django.core.validators import MinValueValidator
from decimal import Decimal
import math
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from datetime import date, timedelta
from .utils import obtener_feriados_peru
from decimal import Decimal

def obtener_siguiente_dia_habil(fecha):
    if not fecha:
        return date.today()

    feriados_anio = obtener_feriados_peru(fecha.year)

    if fecha.month == 12:
        feriados_anio += obtener_feriados_peru(fecha.year + 1)

    # 3. Validación
    while fecha.weekday() >= 5 or fecha in feriados_anio:
        fecha += timedelta(days=1)

        # Si cambiamos de año en el bucle, recargamos la lista
        if fecha.year != feriados_anio[0].year and fecha.month > 1:
            feriados_anio = obtener_feriados_peru(fecha.year)

    return fecha

# --- UTILIDADES (Opciones para selectores) ---
ESTADOS_PROYECTO = [('Planos', 'En Planos'),('Preventa', 'En Preventa'), ('Construccion', 'En Construcción'), ('Entregado', 'Entregado')]
TIPO_GASTO = [('Directo', 'Gasto Directo'), ('Indirecto', 'Gasto Indirecto')]
FRECUENCIA_PAGO = [('Mensual', 'Mensual'), ('Bimestral', 'Bimestral'), ('Trimestral', 'Trimestral')]
ESTADO_DISPONIBILIDAD = [('Disponible', 'Disponible'), ('Separado', 'Separado'), ('Vendido', 'Vendido')]
TIPOS_FINANCIAMIENTO = [
    ('Hipotecario', 'Crédito Hipotecario (Banco)'),
    ('Directo', 'Crédito Directo (Inmobiliaria)'),
    ('Contado', 'Al Contado / Transferencia'),
]
ESTADOS_INTERES = [
    ('Seguimiento', 'En Seguimiento (Frio/Tibio)'),
    ('Negociacion', 'En Negociación (Caliente)'),
    ('Comprado', 'VENTA CERRADA (Éxito)'),
    ('Caido', 'Venta Caída / No Interesado')
]

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

    class Meta:
        verbose_name = "Proveedor"
        verbose_name_plural = "Proveedores"

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
    correo = models.EmailField(null=True, blank=True)
    telefono = models.CharField(max_length=20, null=True, blank=True)
    direccion = models.TextField(null=True, blank=True)

    class Meta:
        verbose_name = "Inversores"
        verbose_name_plural = "Inversores"

    def __str__(self):
        return self.nombre_completo


class Inversion(models.Model):
    inversor = models.ForeignKey('Inversor', on_delete=models.CASCADE)
    proyecto = models.ForeignKey('Proyecto', on_delete=models.CASCADE)

    capital_monto = models.DecimalField(max_digits=12, decimal_places=2)
    fecha_desembolso = models.DateField()
    tea_anual = models.DecimalField(max_digits=5, decimal_places=2)
    plazo_meses = models.IntegerField()
    frecuencia_nombre = models.CharField(max_length=20, choices=[('Mensual', 'Mensual'), ('Trimestral', 'Trimestral')])
    estado = models.CharField(max_length=20, default='Activo')

    class Meta:
        verbose_name = "Inversiones"
        verbose_name_plural = "Inversiones"

    def __str__(self):
        return f"Inv {self.id} - {self.inversor}"

    def generar_cronograma_pagos(self):
        self.cuotas.all().delete()

        tea_valor = float(self.tea_anual)
        tea_decimal = tea_valor / 100.0 if tea_valor >= 1.0 else tea_valor
        tasa_diaria = (1 + tea_decimal) ** (1 / 360) - 1
        dias_por_periodo = 90 if self.frecuencia_nombre == 'Trimestral' else 30

        fecha_anterior = self.fecha_desembolso
        num_cuotas = int(self.plazo_meses / (3 if dias_por_periodo == 90 else 1))
        hoy = date.today()

        for i in range(1, num_cuotas + 1):
            fecha_tentativa = fecha_anterior + timedelta(days=dias_por_periodo)
            fecha_final = obtener_siguiente_dia_habil(fecha_tentativa)
            dias_reales = (fecha_final - fecha_anterior).days

            capital_float = float(self.capital_monto)
            interes_bruto_val = capital_float * tasa_diaria * dias_reales
            impuesto_val = interes_bruto_val * 0.05
            interes_neto_val = interes_bruto_val - impuesto_val

            es_ultima = (i == num_cuotas)
            amortizacion_val = capital_float if es_ultima else 0.0
            total_val = interes_neto_val + amortizacion_val

            estado_inicial = 'Pagado' if fecha_final < hoy else 'Pendiente'

            CuotaInversion.objects.create(
                inversion=self,
                nro_cuota=i,
                fecha_programada=fecha_final,
                dias_periodo=dias_reales,
                saldo_capital=self.capital_monto,
                interes_bruto=Decimal(f"{interes_bruto_val:.2f}"),
                monto_impuesto=Decimal(f"{impuesto_val:.2f}"),
                interes_neto=Decimal(f"{interes_neto_val:.2f}"),
                amortizacion_capital=Decimal(f"{amortizacion_val:.2f}"),
                total_pagar=Decimal(f"{total_val:.2f}"),
                es_ultima_cuota=es_ultima,
                estado=estado_inicial
            )

            fecha_anterior = fecha_final
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
    dias_periodo = models.IntegerField(default=0, verbose_name="Días")

    saldo_capital = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    interes_bruto = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Int. Bruto")
    monto_impuesto = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Impuesto (5%)")
    interes_neto = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Int. Neto")
    amortizacion_capital = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Amortización")
    total_pagar = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="A Pagar")

    es_ultima_cuota = models.BooleanField(default=False)
    estado = models.CharField(max_length=20, choices=[('Pendiente', 'Pendiente'), ('Pagado', 'Pagado')],
                              default='Pendiente')
    comprobante = models.FileField(upload_to='comprobantes/', null=True, blank=True)

    def alerta_estado(self):
        if not self.fecha_programada: return "—"
        if self.estado == 'Pagado': return "Pagado"

        dias_restantes = (self.fecha_programada - date.today()).days

        if dias_restantes < 0:
            return f"VENCIDO hace ({abs(dias_restantes)} días)"
        elif dias_restantes <= 1:
            return "Vence Pronto"
        else:
            return f"Faltan {dias_restantes} días"

    def __str__(self):
        return f"Cuota #{self.nro_cuota}"

@receiver(post_save, sender=CuotaInversion)
def verificar_fin_inversion(sender, instance, **kwargs):
    if instance.estado == 'Pagado':
        inv_padre = instance.inversion

        pendientes = inv_padre.cuotas.filter(estado='Pendiente').exists()

        if not pendientes:
            Inversion.objects.filter(id=inv_padre.id).update(estado='Finalizado')
            print(f"Inversión {inv_padre.id} finalizada")

@receiver(post_save, sender=Inversion)
def trigger_generar_cronograma(sender, instance, created, **kwargs):
    if instance.estado == 'Finalizado':
        return

    if instance.capital_monto and instance.fecha_desembolso:
         instance.generar_cronograma_pagos()

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

# ==========================================
# MÓDULO 3: VENTAS Y CLIENTES (CRM)
# ==========================================

class TipoDepartamento(models.Model):
    proyecto = models.ForeignKey(Proyecto, on_delete=models.CASCADE)
    nombre = models.CharField(max_length=100)  # Ej: Flat Tipo A

    # 1. NUEVO: Aquí definimos el área "oficial" para este tipo de depa
    area_m2 = models.DecimalField(max_digits=6, decimal_places=2, default=0, verbose_name="Área (m²)")

    precio_base = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text="Precio sugerido")
    descripcion = models.TextField(blank=True)
    plano_modelo = models.URLField(blank=True, null=True)

    def __str__(self):
        return f"{self.nombre} ({self.area_m2} m²)"


class Departamento(models.Model):
    tipo = models.ForeignKey(TipoDepartamento, on_delete=models.CASCADE)
    nro = models.CharField(max_length=20)
    piso = models.IntegerField(default=1)

    # 2. CAMBIO: Ahora es opcional (blank=True).
    # Si lo dejas vacío, hereda del Tipo. Si lo llenas, manda este valor (útil para terrazas).
    area_m2 = models.DecimalField(max_digits=6, decimal_places=2, blank=True, null=True, verbose_name="Área Propia")

    estado_disponibilidad = models.CharField(max_length=20, choices=ESTADO_DISPONIBILIDAD, default='Disponible')

    class Meta:
        unique_together = ('tipo', 'nro')

    def save(self, *args, **kwargs):
        # Lógica de Herencia de Área
        if not self.area_m2:
            self.area_m2 = self.tipo.area_m2  # <--- AQUÍ OCURRE LA MAGIA

        super().save(*args, **kwargs)

    def __str__(self):
        return f"Dpto {self.nro} - {self.tipo.nombre}"


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
    estado_interes = models.CharField(max_length=50, choices=ESTADOS_INTERES, default='Seguimiento')
    observaciones = models.TextField(blank=True, help_text="Notas del vendedor: 'Quiere vista al mar', 'Llamar el martes'")

    class Meta:
        unique_together = ('cliente', 'proyecto') # Un cliente solo tiene 1 ficha por proyecto
        verbose_name = "Interés / Lead"
        verbose_name_plural = "Intereses / Leads"

    def __str__(self):
        return f"{self.cliente} en {self.proyecto} ({self.estado_interes})"


class Venta(models.Model):
    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT)
    departamento = models.OneToOneField(Departamento, on_delete=models.PROTECT)
    fecha_venta = models.DateField()

    precio_lista = models.DecimalField(max_digits=12, decimal_places=2, editable=False)
    descuento_porcentaje = models.DecimalField(max_digits=5, decimal_places=2, default=0, help_text="Ej: 5.0 para 5%")
    monto = models.DecimalField(max_digits=12, decimal_places=2, editable=False)

    tipo_financiamiento = models.CharField(
        max_length=20,
        choices=TIPOS_FINANCIAMIENTO,
        default='Hipotecario'
    )

    entidad_financiera = models.CharField(max_length=100, null=True, blank=True,
                                          help_text="Ej: BCP, BBVA (Solo si es Hipotecario)")
    porcentaje_financiado = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)

    def save(self, *args, **kwargs):
        self.precio_lista = self.departamento.tipo.precio_base
        dinero_descontado = self.precio_lista * (self.descuento_porcentaje / Decimal(100))
        self.monto = self.precio_lista - dinero_descontado

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


@receiver(post_save, sender=Venta)
def actualizar_crm_post_venta(sender, instance, created, **kwargs):
    if created:
        cliente_venta = instance.cliente
        # Ruta larga para hallar el proyecto: Venta -> Depa -> Tipo -> Proyecto
        proyecto_venta = instance.departamento.tipo.proyecto

        # Buscamos si existía el interés previo (get_or_create por si fue venta directa sin lead previo)
        interes_obj, fue_creado = ClienteProyecto.objects.get_or_create(
            cliente=cliente_venta,
            proyecto=proyecto_venta
        )

        # Actualizamos el estado a Éxito
        interes_obj.estado_interes = 'Comprado'
        interes_obj.observaciones += f"\n[AUTO] Compró el Dpto {instance.departamento.nro} el {instance.fecha_venta}."
        interes_obj.save()
        print(f" CRM Actualizado: {cliente_venta} ahora figura como COMPRADOR en {proyecto_venta}")