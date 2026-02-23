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
    TipoDepartamento, Departamento, Cliente, Venta, ClienteProyecto,
    PrestamoTercero, CuotaPrestamoTercero
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
    search_fields = ('nombre', 'correo', 'nro_documento')

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
    search_fields = ['nombre']

    list_display = ('nombre_resaltado', 'tipo', 'estado', 'unidades_info', 'banco_ok')
    list_filter = ('tipo', 'estado')

    @admin.display(description='Nombre del Proyecto')
    def nombre_resaltado(self, obj):
        if obj.tipo == 'EMPRESARIAL':
            return format_html('<strong style="color: #28a745;">{}</strong>', obj.nombre)
        return obj.nombre

    @admin.display(description='Und. Disp.')
    def unidades_info(self, obj):
        if obj.tipo == 'EMPRESARIAL':
            return "-"
        return f"{obj.unidades_disponibles()} / {obj.total_unidades}"

    @admin.display(description='Banco OK', boolean=True)
    def banco_ok(self, obj):
        if obj.tipo == 'EMPRESARIAL':
            return None
        return obj.banco_activado

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)

        if obj is None or obj.tipo == 'INMOBILIARIO':
            if 'estado' in form.base_fields:
                choices = [c for c in form.base_fields['estado'].choices if c[0] != 'Operativo']
                form.base_fields['estado'].choices = choices
        return form

    def get_fieldsets(self, request, obj=None):
        if obj and obj.tipo == 'EMPRESARIAL':
            return (
                ('Información del Fondo', {
                    'fields': ('tipo', 'nombre', 'estado', 'ubicacion')
                }),
            )
        return super().get_fieldsets(request, obj)


class DocumentoInline(admin.TabularInline):
    model = Documento
    extra = 1  # Te muestra un espacio vacío listo para subir un archivo
    fields = ('tipo', 'archivo', 'descripcion')

@admin.register(Departamento)
class DepartamentoAdmin(admin.ModelAdmin):
    list_display = ('nro', 'obtener_proyecto', 'tipo', 'ver_area', 'ver_precio', 'estado_disponibilidad')
    list_filter = ('estado_disponibilidad', 'tipo__proyecto')
    search_fields = ('nro',)
    inlines = [DocumentoInline]

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
    # Usamos nuestra nueva función para mostrar el nombre correcto en la tabla
    list_display = ('nombre_completo', 'tipo_documento', 'nro_doc', 'telefono', 'ver_banco_real', 'cuenta_abono')
    list_filter = ('tipo_documento', 'banco')
    search_fields = ('nombre_completo', 'nro_doc', 'cuenta_abono')
    fieldsets = (
        ('Datos Personales', {
            'fields': ('nombre_completo', 'tipo_documento', 'nro_doc', 'telefono', 'correo')
        }),
        ('Datos Bancarios y Tributarios', {
            # Agregamos banco_personalizado justo debajo de banco
            'fields': ('banco', 'banco_personalizado', 'cuenta_abono', 'cci')
        }),
    )

    @admin.display(description='Banco')
    def ver_banco_real(self, obj):
        return obj.nombre_banco_real

    class Media:
        js = ('js/banco_dinamico.js',)

@admin.register(Proveedor)
class ProveedorAdmin(admin.ModelAdmin):
    list_display = ('razon_social', 'ruc', 'tipo_servicio')
    search_fields = ('razon_social', 'ruc')


# Registros simples
admin.site.register(Documento)
admin.site.register(ClienteProyecto)
admin.site.register(TipoDepartamento)

# ================================================
# 2. INVERSIONES
# ================================================
class CuotaInversionInline(admin.TabularInline):
    model = CuotaInversion
    extra = 0
    can_delete = False

    def ver_bruto(self, obj):
        return formato_dinero(obj.interes_bruto, obj.inversion.moneda)

    ver_bruto.short_description = "Int. Bruto"

    def ver_impuesto(self, obj):
        return formato_dinero(obj.monto_impuesto, obj.inversion.moneda)

    ver_impuesto.short_description = "Impuesto"

    def ver_neto(self, obj):
        return formato_dinero(obj.interes_neto, obj.inversion.moneda)

    ver_neto.short_description = "Int. Neto"

    def ver_amortizacion(self, obj):
        return formato_dinero(obj.amortizacion_capital, obj.inversion.moneda)

    ver_amortizacion.short_description = "Amortización"

    def ver_total(self, obj):
        return format_html("<b>{}</b>", formato_dinero(obj.total_pagar, obj.inversion.moneda))

    ver_total.short_description = "A Pagar"

    # ---> NUEVA COLUMNA EXCLUSIVA PARA SOCIOS <---
    def ver_capital_invertido(self, obj):
        return format_html("<b>{}</b>", formato_dinero(obj.amortizacion_capital, obj.inversion.moneda))

    ver_capital_invertido.short_description = "Capital Invertido"

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        formfield = super().formfield_for_dbfield(db_field, request, **kwargs)
        if db_field.name in ['interes_bruto', 'monto_impuesto', 'interes_neto', 'amortizacion_capital', 'total_pagar']:
            formfield.widget.attrs.update({'style': 'width: 100px;'})
        if db_field.name == 'nro_cuota':
            formfield.widget.attrs.update({
                'readonly': 'readonly',
                'style': 'width: 50px; background: #eee; border: none; text-align: center; font-weight: bold;'
            })
        return formfield

    # ==========================================
    # MAGIA DINÁMICA: CAMBIA SEGÚN EL TIPO
    # ==========================================

    def get_fields(self, request, obj=None):
        if obj and obj.tipo_calculo == 'MANUAL':
            return ('nro_cuota', 'fecha_programada', 'interes_bruto', 'monto_impuesto',
                    'interes_neto', 'amortizacion_capital', 'total_pagar', 'estado')

        elif obj and obj.tipo_calculo == 'EQUITY':
            # ---> MODO EQUITY: Tabla minimalista solo con el capital inicial <---
            return ('nro_cuota', 'ver_capital_invertido', 'fecha_programada', 'estado')

        else:
            # MODO FINANCIERO / COMERCIAL: Todas las columnas completas
            return ('nro_cuota', 'ver_bruto', 'ver_impuesto', 'ver_neto',
                    'ver_amortizacion', 'ver_total', 'fecha_programada', 'estado')

    def get_readonly_fields(self, request, obj=None):
        if obj and obj.tipo_calculo == 'MANUAL':
            return ()
        else:
            return self.get_fields(request, obj)

    def get_extra(self, request, obj=None, **kwargs):
        return 1 if (obj and obj.tipo_calculo == 'MANUAL') else 0

    def has_add_permission(self, request, obj=None):
        return True if (obj and obj.tipo_calculo == 'MANUAL') else False

    def has_delete_permission(self, request, obj=None):
        return True if (obj and obj.tipo_calculo == 'MANUAL') else False

    class Media:
        js = ('js/inversiones_manuales.js',)


class InversionForm(forms.ModelForm):
    class Meta:
        model = Inversion
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Solo relajamos estos 3, la fecha de desembolso vuelve a ser obligatoria normal
        self.fields['tea_anual'].required = False
        self.fields['plazo_meses'].required = False
        self.fields['frecuencia'].required = False

    def clean(self):
        cleaned_data = super().clean()
        tipo_calculo = cleaned_data.get('tipo_calculo')

        if tipo_calculo == 'EQUITY':
            # Rellenamos solo los financieros
            cleaned_data['tea_anual'] = 0
            cleaned_data['plazo_meses'] = 0
            cleaned_data['frecuencia'] = 'Mensual'

            # Limpiamos los errores de estos 3
            self._errors.pop('tea_anual', None)
            self._errors.pop('plazo_meses', None)
            self._errors.pop('frecuencia', None)

        else:
            # Si NO es EQUITY, exigimos los financieros
            if cleaned_data.get('tea_anual') is None:
                self.add_error('tea_anual', 'Este campo es obligatorio.')
            if cleaned_data.get('plazo_meses') is None:
                self.add_error('plazo_meses', 'Este campo es obligatorio.')
            if not cleaned_data.get('frecuencia'):
                self.add_error('frecuencia', 'Este campo es obligatorio.')

        return cleaned_data


@admin.register(Inversion)
class InversionAdmin(admin.ModelAdmin):
    form = InversionForm

    inlines = [CuotaInversionInline, DocumentoInline]

    list_display = ('id', 'inversor', 'proyecto', 'ver_capital', 'responsable_pago', 'fecha_desembolso', 'estado')
    list_filter = ('proyecto', 'responsable_pago', 'estado', 'moneda', 'frecuencia')
    search_fields = ('inversor__nombre_completo', 'id')
    autocomplete_fields = ['inversor', 'proyecto']
    save_on_top = True

    readonly_fields = ('estado',)

    @admin.display(description='Inversión', ordering='capital_monto')
    def ver_capital(self, obj):
        return formato_dinero(obj.capital_monto, obj.moneda)

    fieldsets = (
        ('Datos del Contrato', {
            'fields': ('inversor', 'proyecto', 'estado')
        }),
        ('Condiciones Financieras', {
            'fields': (
            'capital_monto', 'moneda', 'tea_anual', 'plazo_meses', 'frecuencia', 'tipo_calculo', 'fecha_desembolso')
        }),
        ('Distribución y Responsabilidad', {
            'fields': ('responsable_pago', 'destino_fondos'),
            'classes': ('collapse',)
        }),
    )

    change_list_template = 'admin/core/agendapagos/change_list.html'

    def changelist_view(self, request, extra_context=None):
        response = super().changelist_view(request, extra_context)
        if isinstance(response, TemplateResponse) and hasattr(response, 'context_data'):
            try:
                cl = response.context_data.get('cl')
                if cl:
                    qs = cl.queryset
                    resumen = qs.order_by().values('moneda').annotate(total=Sum('capital_monto'))
                    totales = {item['moneda']: item['total'] for item in resumen}
                    response.context_data['totales_por_moneda'] = totales
            except (AttributeError, KeyError):
                pass
        return response

    class Media:
        js = ('js/equity_dinamico.js',)

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


# =====================================================================
# MÓDULO DE PRÉSTAMOS A TERCEROS (PANEL VISUAL)
# =====================================================================
class CuotaPrestamoTerceroInline(admin.TabularInline):
    model = CuotaPrestamoTercero
    extra = 0
    can_delete = False
    def ver_interes(self, obj):
        return formato_dinero(obj.interes, obj.prestamo.moneda)

    ver_interes.short_description = "Interés"

    def ver_amortizacion(self, obj):
        return formato_dinero(obj.amortizacion_capital, obj.prestamo.moneda)

    ver_amortizacion.short_description = "Amortización"

    def ver_total(self, obj):
        return format_html("<b>{}</b>", formato_dinero(obj.total_pagar, obj.prestamo.moneda))

    ver_total.short_description = "A Pagar"

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        formfield = super().formfield_for_dbfield(db_field, request, **kwargs)
        if db_field.name in ['interes', 'amortizacion_capital', 'total_pagar']:
            formfield.widget.attrs.update({'style': 'width: 100px;'})
        if db_field.name == 'nro_cuota':
            formfield.widget.attrs.update({
                'readonly': 'readonly',
                'style': 'width: 50px; background: #eee; border: none; text-align: center; font-weight: bold;'
            })
        return formfield

    def get_fields(self, request, obj=None):
        if obj and obj.tipo_calculo == 'MANUAL':
            return ('nro_cuota', 'fecha_programada', 'interes',
                    'amortizacion_capital', 'total_pagar', 'estado')
        else:
            return ('nro_cuota', 'ver_interes', 'ver_amortizacion',
                    'ver_total', 'fecha_programada', 'estado')

    def get_readonly_fields(self, request, obj=None):
        if obj and obj.tipo_calculo == 'MANUAL':
            return ()
        else:
            return self.get_fields(request, obj)

    def get_extra(self, request, obj=None, **kwargs):
        return 1 if (obj and obj.tipo_calculo == 'MANUAL') else 0

    def has_add_permission(self, request, obj=None):
        return True if (obj and obj.tipo_calculo == 'MANUAL') else False

    def has_delete_permission(self, request, obj=None):
        return True if (obj and obj.tipo_calculo == 'MANUAL') else False

    # ¡Reutilizamos el script nuclear! Funcionará perfecto aquí también.
    class Media:
        js = ('js/inversiones_manuales.js',)

class PrestamoTerceroForm(forms.ModelForm):
    class Meta:
        model = PrestamoTercero
        fields = '__all__'

    inlines = [CuotaPrestamoTerceroInline, DocumentoInline]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Relajamos los campos para que el modo Manual no se queje si los dejas vacíos
        self.fields['tea_anual'].required = False
        self.fields['plazo_meses'].required = False
        self.fields['frecuencia'].required = False

    def clean(self):
        cleaned_data = super().clean()
        tipo_calculo = cleaned_data.get('tipo_calculo')

        if tipo_calculo in ['FINANCIERO', 'COMERCIAL']:
            if cleaned_data.get('tea_anual') is None:
                self.add_error('tea_anual', 'Obligatorio para cálculos automáticos.')
            if cleaned_data.get('plazo_meses') is None:
                self.add_error('plazo_meses', 'Obligatorio para cálculos automáticos.')
            if not cleaned_data.get('frecuencia'):
                self.add_error('frecuencia', 'Obligatorio para cálculos automáticos.')
        else:
            # Si es MANUAL, autocompletamos con 0 para la base de datos
            cleaned_data['tea_anual'] = cleaned_data.get('tea_anual') or 0
            cleaned_data['plazo_meses'] = cleaned_data.get('plazo_meses') or 0
            cleaned_data['frecuencia'] = cleaned_data.get('frecuencia') or 'Mensual'

            self._errors.pop('tea_anual', None)
            self._errors.pop('plazo_meses', None)
            self._errors.pop('frecuencia', None)

        return cleaned_data

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if 'cliente' in form.base_fields:
            form.base_fields['cliente'].widget.can_add_related = False
            form.base_fields['cliente'].widget.can_change_related = False
            form.base_fields['cliente'].widget.can_delete_related = False
        return form

@admin.register(PrestamoTercero)
class PrestamoTerceroAdmin(admin.ModelAdmin):
    form = PrestamoTerceroForm
    inlines = [CuotaPrestamoTerceroInline]

    list_display = ('id', 'cliente', 'motivo_prestamo', 'ver_capital', 'fecha_desembolso', 'estado')
    list_filter = ('estado', 'moneda', 'frecuencia', 'tipo_calculo')
    search_fields = ('cliente__nombre', 'cliente__nro_documento', 'motivo_prestamo')
    autocomplete_fields = ['cliente']
    save_on_top = True
    readonly_fields = ('estado',)

    @admin.display(description='Monto Prestado', ordering='capital_monto')
    def ver_capital(self, obj):
        return formato_dinero(obj.capital_monto, obj.moneda)

    fieldsets = (
        ('Datos del Prestatario', {
            'fields': ('cliente', 'motivo_prestamo', 'estado')
        }),
        ('Condiciones del Préstamo', {
            'fields': (
            'capital_monto', 'moneda', 'tea_anual', 'plazo_meses', 'frecuencia', 'tipo_calculo', 'fecha_desembolso')
        }),
    )

    # Calculamos los totales en la lista principal (Igual que en Inversiones)
    def changelist_view(self, request, extra_context=None):
        response = super().changelist_view(request, extra_context)
        if isinstance(response, TemplateResponse) and hasattr(response, 'context_data'):
            try:
                cl = response.context_data.get('cl')
                if cl:
                    qs = cl.queryset
                    resumen = qs.order_by().values('moneda').annotate(total=Sum('capital_monto'))
                    totales = {item['moneda']: item['total'] for item in resumen}
                    response.context_data['totales_por_moneda'] = totales
            except (AttributeError, KeyError):
                pass
        return response


# CONFIGURACIÓN FINAL
admin.site.site_header = "ERP Inmobiliaria"
admin.site.site_title = "Panel Admin"
admin.site.index_title = "Gestión General"