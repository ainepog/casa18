from django.contrib import admin
from django import forms
from django.utils.html import format_html
from .models import (
    Proyecto, Documento, Proveedor, Gasto, ProveedorProyecto,
    Inversor, Inversion, CuotaInversion,
    TipoDepartamento, Departamento, Cliente, Venta, ClienteProyecto
)


def formato_dinero(monto, moneda):

    if monto is None: return "0.00"
    simbolo = 'S/' if moneda == 'PEN' else '$'
    return f"{simbolo} {monto:,.2f}"


# ================================================
# 1. MODELOS BASE
# ================================================

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


class ProyectoAdmin(admin.ModelAdmin):
    class TipoDepartamentoInline(admin.TabularInline):
        model = TipoDepartamento
        extra = 0
        fields = ('nombre', 'area_m2', 'precio_base')

    inlines = [TipoDepartamentoInline]
    list_display = ('nombre', 'estado', 'total_unidades', 'banco_activado_check')
    search_fields = ('nombre',)
    list_filter = ('estado', 'banco_activado')

    def banco_activado_check(self, obj):
        return "SÍ" if obj.banco_activado else "NO"

    banco_activado_check.short_description = "Banco OK"


class DepartamentoAdmin(admin.ModelAdmin):
    list_display = ('nro', 'obtener_proyecto', 'tipo', 'ver_precio', 'estado_disponibilidad')
    list_filter = ('estado_disponibilidad', 'tipo__proyecto')
    search_fields = ('nro',)

    def obtener_proyecto(self, obj):
        return obj.tipo.proyecto.nombre

    obtener_proyecto.short_description = "Proyecto"

    def ver_precio(self, obj):
        return f"{obj.tipo.precio_base:,.2f}"

    ver_precio.short_description = "Precio Base"


class InversorAdmin(admin.ModelAdmin):
    list_display = ('nombre_completo', 'nro_doc', 'correo', 'telefono')
    search_fields = ('nombre_completo', 'nro_doc')


class ProveedorAdmin(admin.ModelAdmin):
    list_display = ('razon_social', 'ruc', 'tipo_servicio')
    search_fields = ('razon_social', 'ruc')

# ================================================
# 2. INVERSIONES Y CUOTAS
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


class InversionAdmin(admin.ModelAdmin):
    inlines = [CuotaInversionInline]
    list_display = ('id', 'inversor', 'proyecto', 'ver_capital', 'fecha_desembolso', 'estado')
    list_filter = ('proyecto', 'estado', 'moneda', 'frecuencia_nombre')
    search_fields = ('inversor__nombre_completo', 'id')

    autocomplete_fields = ['inversor', 'proyecto']

    save_on_top = True

    @admin.display(description='Capital', ordering='capital_monto')
    def ver_capital(self, obj):
        return formato_dinero(obj.capital_monto, obj.moneda)


# ================================================
# 3. DASHBOARD DE PAGOS
# ================================================
class CuotaInversionAdmin(admin.ModelAdmin):
    list_display = ('ver_info', 'nro_cuota', 'fecha_programada', 'ver_monto', 'alerta_visual', 'estado')
    list_filter = ('estado', 'fecha_programada', 'inversion__proyecto', 'inversion__moneda')
    search_fields = ('inversion__inversor__nombre_completo',)
    date_hierarchy = 'fecha_programada'
    ordering = ('fecha_programada',)

    def ver_info(self, obj): return f"{obj.inversion.inversor} ({obj.inversion.proyecto.nombre})"

    ver_info.short_description = "Inversor / Proyecto"

    def ver_monto(self, obj):
        return format_html("<b>{}</b>", formato_dinero(obj.total_pagar, obj.inversion.moneda))

    ver_monto.short_description = "Monto a Pagar"

    def alerta_visual(self, obj): return obj.alerta_estado()

    alerta_visual.short_description = "Alerta"


# ================================================
# 4. GASTOS Y VENTAS
# ================================================
class GastoAdmin(admin.ModelAdmin):
    list_display = ('descripcion', 'proyecto', 'fecha_gasto', 'ver_monto', 'tipo_gasto')
    list_filter = ('proyecto', 'moneda', 'tipo_gasto')
    search_fields = ('descripcion', 'proveedor__razon_social')

    autocomplete_fields = ['proveedor', 'proyecto']

    @admin.display(description='Monto')
    def ver_monto(self, obj): return formato_dinero(obj.monto, obj.moneda)


class VentaAdmin(admin.ModelAdmin):
    list_display = ('cliente', 'departamento', 'fecha_venta', 'ver_precio', 'tipo_financiamiento')
    list_filter = ('fecha_venta', 'tipo_financiamiento')

    autocomplete_fields = ['cliente', 'departamento']

    fields = (
        'cliente',
        'departamento',
        'fecha_venta',
        'moneda',
        'descuento_porcentaje',
        'precio_lista',
        'monto',
        'tipo_financiamiento',
    )
    readonly_fields = ('precio_lista', 'monto')

    @admin.display(description='Precio Venta')
    def ver_precio(self, obj): return formato_dinero(obj.monto, obj.moneda)


class ProveedorProyectoAdmin(admin.ModelAdmin):
    list_display = ('proveedor', 'proyecto', 'tipo_contrato', 'ver_monto')

    autocomplete_fields = ['proveedor', 'proyecto']

    @admin.display(description='Monto Contrato')
    def ver_monto(self, obj): return formato_dinero(obj.monto_estimado, obj.moneda)


# ================================================
# 5. REGISTRO FINAL
# ================================================

admin.site.register(Inversion, InversionAdmin)
admin.site.register(CuotaInversion, CuotaInversionAdmin)
admin.site.register(Gasto, GastoAdmin)
admin.site.register(Venta, VentaAdmin)
admin.site.register(ProveedorProyecto, ProveedorProyectoAdmin)

admin.site.register(Proyecto, ProyectoAdmin)
admin.site.register(Cliente, ClienteAdmin)
admin.site.register(Departamento, DepartamentoAdmin)
admin.site.register(Inversor, InversorAdmin)
admin.site.register(Proveedor, ProveedorAdmin)

admin.site.register(TipoDepartamento)
admin.site.register(Documento)
admin.site.register(ClienteProyecto)

# ================================================
# 6. INTERFAZ
# ================================================
admin.site.site_header = "ERP Inmobiliaria"
admin.site.site_title = "Panel Admin"
admin.site.index_title = "Gestión General"