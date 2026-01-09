from datetime import date, timedelta
import calendar
from django.contrib import admin
from django import forms
from django.template.response import TemplateResponse
from django.utils.html import format_html
from django.db.models import Sum
from django.http import HttpResponseRedirect
from django.contrib.admin import DateFieldListFilter

# 1. IMPORTAMOS LOS MODELOS (AgendaPagos viene de models.py)
from .models import (
    Proyecto, Documento, Proveedor, Gasto, ProveedorProyecto,
    Inversor, Inversion, CuotaInversion, AgendaPagos,
    TipoDepartamento, Departamento, Cliente, Venta, ClienteProyecto
)

def formato_dinero(monto, moneda):
    if monto is None: return "0.00"
    simbolo = 'S/' if moneda == 'PEN' else '$'
    return f"{simbolo} {monto:,.2f}"


# ================================================
# 0. FILTRO PERSONALIZADO
# ================================================
class FiltroCobrosFuturos(admin.SimpleListFilter):
    title = 'Filtros'
    parameter_name = 'vencimiento'

    def lookups(self, request, model_admin):
        return (
            ('vencidos', 'Vencidos'),
            ('hoy', 'Hoy'),
            ('esta_semana', 'Esta Semana'),
            ('este_mes', 'Este Mes'),
            ('proximo_mes', 'Próximo Mes'),
        )

    def queryset(self, request, queryset):
        hoy = date.today()

        if self.value() == 'vencidos':
            return queryset.filter(fecha_programada__lt=hoy)

        if self.value() == 'hoy':
            return queryset.filter(fecha_programada=hoy)

        if self.value() == 'esta_semana':
            inicio_semana = hoy - timedelta(days=hoy.weekday())
            fin_semana = inicio_semana + timedelta(days=6)
            return queryset.filter(fecha_programada__gte=hoy, fecha_programada__lte=fin_semana)

        if self.value() == 'este_mes':
            ultimo_dia = calendar.monthrange(hoy.year, hoy.month)[1]
            fin_mes = date(hoy.year, hoy.month, ultimo_dia)
            return queryset.filter(fecha_programada__gte=hoy, fecha_programada__lte=fin_mes)

        if self.value() == 'proximo_mes':
            if hoy.month == 12:
                prox_mes = 1
                prox_anio = hoy.year + 1
            else:
                prox_mes = hoy.month + 1
                prox_anio = hoy.year

            ultimo_dia_prox = calendar.monthrange(prox_anio, prox_mes)[1]
            inicio = date(prox_anio, prox_mes, 1)
            fin = date(prox_anio, prox_mes, ultimo_dia_prox)
            return queryset.filter(fecha_programada__gte=inicio, fecha_programada__lte=fin)


# ================================================
# 1. MODELOS BASE
# ================================================

@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'correo', 'telefono', 'ver_proyectos_interes')
    search_fields = ('nombre', 'correo', 'telefono')

    class InteresInline(admin.TabularInline):
        model = ClienteProyecto
        extra = 1
        autocomplete_fields = ['proyecto']

    inlines = [InteresInline]

    def ver_proyectos_interes(self, obj):
        intereses = obj.clienteproyecto_set.all()
        return ", ".join([i.proyecto.nombre for i in intereses])

    ver_proyectos_interes.short_description = "Proyectos de Interés"


@admin.register(Proyecto)
class ProyectoAdmin(admin.ModelAdmin):
    class TipoDepartamentoInline(admin.TabularInline):
        model = TipoDepartamento
        extra = 0
        fields = ('nombre', 'area_m2', 'precio_base', 'plano_modelo')

    inlines = [TipoDepartamentoInline]
    list_display = ('nombre', 'estado', 'ver_disponibles', 'total_unidades', 'banco_activado_check')
    search_fields = ('nombre',)
    list_filter = ('estado', 'banco_activado')

    def ver_disponibles(self, obj):
        return f"{obj.unidades_disponibles()} / {obj.total_unidades}"

    ver_disponibles.short_description = "Und. Disp."

    def banco_activado_check(self, obj):
        return "SÍ" if obj.banco_activado else "NO"

    banco_activado_check.short_description = "Banco OK"


@admin.register(Departamento)
class DepartamentoAdmin(admin.ModelAdmin):
    list_display = ('nro', 'obtener_proyecto', 'tipo', 'ver_area', 'ver_precio', 'estado_disponibilidad')
    list_filter = ('estado_disponibilidad', 'tipo__proyecto')
    search_fields = ('nro',)

    def obtener_proyecto(self, obj):
        return obj.tipo.proyecto.nombre

    obtener_proyecto.short_description = "Proyecto"

    def ver_precio(self, obj):
        return f"{obj.tipo.precio_base:,.2f}"

    ver_precio.short_description = "Precio Base"

    def ver_area(self, obj):
        return f"{obj.tipo.area_m2} m²"

    ver_area.short_description = "Área"


@admin.register(Inversor)
class InversorAdmin(admin.ModelAdmin):
    list_display = ('nombre_completo', 'tipo_documento', 'nro_doc', 'telefono')
    list_filter = ('tipo_documento',)
    search_fields = ('nombre_completo', 'nro_doc')


@admin.register(Proveedor)
class ProveedorAdmin(admin.ModelAdmin):
    list_display = ('razon_social', 'ruc', 'tipo_servicio')
    search_fields = ('razon_social', 'ruc')


# Registros simples
admin.site.register(Documento)
admin.site.register(TipoDepartamento)
admin.site.register(ClienteProyecto)


# ================================================
# 2. INVERSIONES (Gestión del Contrato)
# ================================================

class CuotaInversionInline(admin.TabularInline):
    model = CuotaInversion
    extra = 0
    can_delete = False
    fields = ('nro_cuota', 'ver_bruto', 'ver_impuesto', 'ver_neto',
              'ver_amortizacion', 'ver_total', 'fecha_programada', 'alerta_estado')
    readonly_fields = fields

    def ver_bruto(self, obj): return formato_dinero(obj.interes_bruto, obj.inversion.moneda)

    ver_bruto.short_description = "Int. Bruto"

    def ver_impuesto(self, obj): return formato_dinero(obj.monto_impuesto, obj.inversion.moneda)

    ver_impuesto.short_description = "Impuesto"

    def ver_neto(self, obj): return formato_dinero(obj.interes_neto, obj.inversion.moneda)

    ver_neto.short_description = "Int. Neto"

    def ver_amortizacion(self, obj): return formato_dinero(obj.amortizacion_capital, obj.inversion.moneda)

    ver_amortizacion.short_description = "Amortización"

    def ver_total(self, obj):
        return format_html("<b>{}</b>", formato_dinero(obj.total_pagar, obj.inversion.moneda))

    ver_total.short_description = "A Pagar"

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        formfield = super().formfield_for_dbfield(db_field, request, **kwargs)
        if db_field.name == 'alerta_estado':
            formfield.widget = forms.TextInput(attrs={
                'readonly': 'readonly',
                'style': 'border:none; background:none; font-weight:bold; font-size:1.1em;'
            })
        return formfield


@admin.register(Inversion)
class InversionAdmin(admin.ModelAdmin):
    inlines = [CuotaInversionInline]
    list_display = ('id', 'inversor', 'proyecto', 'ver_capital', 'fecha_desembolso', 'estado')
    list_filter = ('proyecto', 'estado', 'moneda', 'frecuencia')
    search_fields = ('inversor__nombre_completo', 'id')
    autocomplete_fields = ['inversor', 'proyecto']
    save_on_top = True

    @admin.display(description='Capital', ordering='capital_monto')
    def ver_capital(self, obj):
        return formato_dinero(obj.capital_monto, obj.moneda)


# ================================================
# 3. AGENDA DE PAGOS
# ================================================

@admin.register(AgendaPagos)
class AgendaPagosAdmin(admin.ModelAdmin):
    list_display = ('ver_proyecto', 'ver_inversor', 'nro_cuota', 'ver_monto', 'ver_fecha', 'ver_dias_restantes')

    def get_queryset(self, request):
        return super().get_queryset(request).filter(estado='Pendiente')

    list_filter = (
        FiltroCobrosFuturos,
        'inversion__proyecto',
        'inversion__moneda'
    )

    search_fields = ('inversion__inversor__nombre_completo',)
    ordering = ('fecha_programada',)
    list_per_page = 20

    # Columnas
    def ver_proyecto(self, obj):
        return obj.inversion.proyecto.nombre

    ver_proyecto.short_description = "Proyecto"
    ver_proyecto.admin_order_field = 'inversion__proyecto__nombre'

    def ver_inversor(self, obj):
        return obj.inversion.inversor.nombre_completo

    ver_inversor.short_description = "Inversor"
    ver_inversor.admin_order_field = 'inversion__inversor__nombre_completo'

    def ver_monto(self, obj):
        simbolo = 'S/' if obj.inversion.moneda == 'PEN' else '$'
        monto_str = f"{simbolo} {obj.total_pagar:,.2f}"
        return format_html("<span style='color:green; font-weight:bold'>{}</span>", monto_str)

    ver_monto.short_description = "Monto a Pagar"

    def ver_fecha(self, obj):
        return obj.fecha_pago_texto()

    ver_fecha.short_description = "Fecha de Pago"
    ver_fecha.admin_order_field = 'fecha_programada'

    def ver_dias_restantes(self, obj):
        return obj.alerta_estado()

    ver_dias_restantes.short_description = "Días Restantes"

    # LÓGICA DE TOTALES Y REDIRECCIÓN
    change_list_template = 'admin/core/agendapagos/change_list.html'

    def changelist_view(self, request, extra_context=None):
        # 1. Filtro automático (Default)
        if not request.GET and request.path == request.get_full_path():
            return HttpResponseRedirect(request.path + "?vencimiento=este_mes")

        # 2. Totales
        response = super().changelist_view(request, extra_context)
        if isinstance(response, TemplateResponse) and hasattr(response, 'context_data'):
            try:
                cl = response.context_data.get('cl')
                if cl:
                    qs = cl.queryset
                    # USAMOS .order_by() PARA QUE LA SUMA SEA CORRECTA
                    resumen = qs.order_by().values('inversion__moneda').annotate(total=Sum('total_pagar'))
                    totales = {item['inversion__moneda']: item['total'] for item in resumen}
                    response.context_data['totales_por_moneda'] = totales
            except (AttributeError, KeyError):
                pass
        return response


# ================================================
# 4. GASTOS Y VENTAS
# ================================================

@admin.register(Gasto)
class GastoAdmin(admin.ModelAdmin):
    list_display = ('descripcion', 'proyecto', 'fecha_gasto', 'ver_monto', 'estado', 'tipo_gasto')
    list_filter = ('proyecto', 'moneda', 'estado', 'tipo_gasto')
    search_fields = ('descripcion', 'proveedor__razon_social')
    autocomplete_fields = ['proveedor', 'proyecto']

    @admin.display(description='Monto')
    def ver_monto(self, obj): return formato_dinero(obj.monto, obj.moneda)


@admin.register(Venta)
class VentaAdmin(admin.ModelAdmin):
    list_display = ('cliente', 'departamento', 'fecha_venta', 'ver_precio', 'tipo_financiamiento')
    list_filter = ('fecha_venta', 'tipo_financiamiento')
    autocomplete_fields = ['cliente', 'departamento']
    fields = (
        'cliente', 'departamento', 'fecha_venta', 'moneda',
        'descuento_porcentaje', 'precio_lista', 'monto', 'tipo_financiamiento',
    )
    readonly_fields = ('precio_lista', 'monto')

    @admin.display(description='Precio Venta')
    def ver_precio(self, obj): return formato_dinero(obj.monto, obj.moneda)


@admin.register(ProveedorProyecto)
class ProveedorProyectoAdmin(admin.ModelAdmin):
    list_display = ('proveedor', 'proyecto', 'tipo_contrato', 'ver_monto')
    autocomplete_fields = ['proveedor', 'proyecto']

    @admin.display(description='Monto Contrato')
    def ver_monto(self, obj): return formato_dinero(obj.monto_estimado, obj.moneda)


# CONFIGURACIÓN FINAL
admin.site.site_header = "ERP Inmobiliaria"
admin.site.site_title = "Panel Admin"
admin.site.index_title = "Gestión General"