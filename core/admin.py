from datetime import date, timedelta, datetime
import calendar
from django.contrib import admin
from django import forms
from django.core.checks import messages
from django.template.response import TemplateResponse
from django.utils.html import format_html
from django.db.models import Sum
from django.urls import path
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.http import HttpResponseRedirect
from django.contrib.admin import DateFieldListFilter

from .models import (
    Proyecto, Documento, Proveedor, Gasto, ProveedorProyecto,
    Inversor, Inversion, CuotaInversion, AgendaPagos,
    UnidadInmobiliaria, Cliente, Venta, ClienteProyecto,
    PrestamoTercero, CuotaPrestamoTercero
)
from .widgets import CustomFileWidget


def formato_dinero(monto, moneda):
    if monto is None: return "0.00"
    simbolo = 'S/' if moneda == 'PEN' else '$'
    return f"{simbolo} {monto:,.2f}"


# ================================================
# 0. FILTRO PERSONALIZADO
# ================================================
class FiltroCobrosFuturos(admin.SimpleListFilter):
    title = 'Filtros de Tiempo'
    parameter_name = 'vencimiento'

    def lookups(self, request, model_admin):
        return (
            ('vencidos', 'Vencidos'),
            ('hoy', 'Hoy'),
            ('semana_pasada', 'Semana Pasada'),
            ('esta_semana', 'Esta Semana'),
            ('mes_pasado', 'Mes Pasado'),
            ('este_mes', 'Este Mes'),
            ('proximo_mes', 'Próximo Mes'),
        )

    def queryset(self, request, queryset):
        hoy = date.today()

        if self.value() == 'vencidos':
            return queryset.filter(fecha_programada__lt=hoy).exclude(estado='Pagado')

        elif self.value() == 'hoy':
            return queryset.filter(fecha_programada=hoy)

        elif self.value() == 'semana_pasada':
            inicio_semana_actual = hoy - timedelta(days=hoy.weekday())
            inicio_semana_pasada = inicio_semana_actual - timedelta(days=7)
            fin_semana_pasada = inicio_semana_actual - timedelta(days=1)
            return queryset.filter(fecha_programada__range=[inicio_semana_pasada, fin_semana_pasada])

        elif self.value() == 'esta_semana':
            inicio_semana = hoy - timedelta(days=hoy.weekday())
            fin_semana = inicio_semana + timedelta(days=6)
            return queryset.filter(fecha_programada__range=[inicio_semana, fin_semana])

        elif self.value() == 'mes_pasado':
            primer_dia_este_mes = date(hoy.year, hoy.month, 1)
            ultimo_dia_mes_pasado = primer_dia_este_mes - timedelta(days=1)
            primer_dia_mes_pasado = date(ultimo_dia_mes_pasado.year, ultimo_dia_mes_pasado.month, 1)
            return queryset.filter(fecha_programada__range=[primer_dia_mes_pasado, ultimo_dia_mes_pasado])

        elif self.value() == 'este_mes':
            ultimo_dia = calendar.monthrange(hoy.year, hoy.month)[1]
            inicio_mes = date(hoy.year, hoy.month, 1)
            fin_mes = date(hoy.year, hoy.month, ultimo_dia)
            return queryset.filter(fecha_programada__range=[inicio_mes, fin_mes])

        elif self.value() == 'proximo_mes':
            prox_mes = hoy.month + 1 if hoy.month < 12 else 1
            prox_anio = hoy.year if hoy.month < 12 else hoy.year + 1
            ultimo_dia_prox = calendar.monthrange(prox_anio, prox_mes)[1]
            inicio = date(prox_anio, prox_mes, 1)
            fin = date(prox_anio, prox_mes, ultimo_dia_prox)
            return queryset.filter(fecha_programada__range=[inicio, fin])

        return queryset

# ================================================
# 1. MODELOS BASE
# ================================================

class RolClienteFilter(admin.SimpleListFilter):
    title = 'Rol del Cliente'
    parameter_name = 'rol'

    def lookups(self, request, model_admin):
        return (
            ('lead', 'Leads (Inmobiliaria)'),
            ('prestatario', 'Prestatarios'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'lead':
            return queryset.filter(es_prospecto_inmobiliario=True)
        if self.value() == 'prestatario':
            return queryset.filter(es_prestatario=True)
        if self.value() == 'ambos':
            return queryset.filter(es_prospecto_inmobiliario=True, es_prestatario=True)
        return queryset


# --- 2. TU ADMINISTRADOR DE CLIENTES ACTUALIZADO ---
@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = (
        'nombre',
        'nro_documento',
        'telefono',
        'es_prospecto_inmobiliario',
        'es_prestatario',
        'ver_proyectos_interes'
    )

    # Conectamos el filtro unificado aquí
    list_filter = (RolClienteFilter,)

    list_editable = ('es_prospecto_inmobiliario', 'es_prestatario')

    search_fields = ('nombre', 'correo', 'nro_documento')

    fieldsets = (
        ('Información Personal', {
            'fields': ('nombre', 'tipo_documento', 'nro_documento', 'correo', 'telefono', 'direccion')
        }),
        ('Rol del Cliente en Casa18', {
            'fields': ('es_prospecto_inmobiliario', 'es_prestatario'),
            'description': 'Marca las casillas según el tipo de relación con la empresa.'
        }),
    )

    class InteresInline(admin.TabularInline):
        model = ClienteProyecto
        extra = 1
        autocomplete_fields = ['proyecto']

    inlines = [InteresInline]

    def ver_proyectos_interes(self, obj):
        intereses = obj.intereses_proyectos.all()
        if not intereses:
            return "-"
        return ", ".join([i.proyecto.nombre for i in intereses])

    ver_proyectos_interes.short_description = "Proyectos de Interés"

    # ====================================================================
    # CONTROL DE ACCESO
    # ====================================================================
    # def get_queryset(self, request):
    #     qs = super().get_queryset(request)
    #     if not request.user.is_superuser:
    #         return qs.exclude(es_prestatario=True)
    #     return qs

@admin.register(Proyecto)
class ProyectoAdmin(admin.ModelAdmin):
    search_fields = ['nombre']
    list_display = (
        'nombre_resaltado',
        'estado',
        'unidades_info',
        'ver_area_vendida',
        'ver_recaudacion',
        'ver_promedio_m2'
    )
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

    @admin.display(description='Área Vendida')
    def ver_area_vendida(self, obj):
        if obj.tipo == 'EMPRESARIAL':
            return "-"
        return f"{obj.area_vendida_total()} m²"

    @admin.display(description='Precio Prom. / m²')
    def ver_promedio_m2(self, obj):
        if obj.tipo == 'EMPRESARIAL':
            return "-"

        promedio = obj.precio_promedio_m2()
        if promedio > 0:
            return f"$ {promedio:,.2f} / m²"
        return "Sin ventas"

    @admin.display(description='Total Recaudado')
    def ver_recaudacion(self, obj):
        if obj.tipo == 'EMPRESARIAL':
            return "-"
        return f"$ {obj.total_recaudado():,.2f}"

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
    extra = 1
    fields = ('tipo', 'archivo', 'descripcion')


class UnidadInmobiliariaForm(forms.ModelForm):
    generar_en_lote = forms.BooleanField(
        required=False,
        label='Generar en Lote',
        help_text='Marca esta casilla si quieres crear varias cocheras o depósitos de golpe.'
    )
    numero_inicial = forms.IntegerField(
        required=False,
        initial=1,
        label='Número Inicial',
        help_text='Desde qué número empezamos (Ej: 1)'
    )
    cantidad = forms.IntegerField(
        required=False,
        initial=10,
        label='Cantidad a generar',
        help_text='¿Cuántas unidades se crearán?'
    )

    class Meta:
        model = UnidadInmobiliaria
        fields = '__all__'
        help_texts = {
            'numero': "Si vas a generar en lote, escribe aquí solo el PREFIJO (Ej: 'Sótano 1 - Cochera '). Si es solo una unidad, pon su número normal (Ej: '101')."
        }


@admin.register(UnidadInmobiliaria)
class UnidadInmobiliariaAdmin(admin.ModelAdmin):
    form = UnidadInmobiliariaForm

    list_display = ('numero', 'tipo', 'proyecto', 'precio_venta', 'estado_disponibilidad')
    list_filter = ('proyecto', 'tipo', 'estado_disponibilidad')
    search_fields = ('numero', 'proyecto__nombre')

    fieldsets = (
        ('Información Base', {
            'fields': ('proyecto', 'tipo', 'numero', 'precio_venta', 'area_m2', 'estado_disponibilidad')
        }),
        ('Creación en bloque (Opcional)', {
            'fields': ('generar_en_lote', 'numero_inicial', 'cantidad'),
            'classes': ('collapse',)
        }),
    )

    def save_model(self, request, obj, form, change):
        if not change and form.cleaned_data.get('generar_en_lote'):
            cantidad = form.cleaned_data.get('cantidad') or 1
            inicio = form.cleaned_data.get('numero_inicial') or 1
            prefijo = obj.numero

            obj.numero = f"{prefijo}{inicio}"
            super().save_model(request, obj, form, change)

            unidades_extra = []
            for i in range(1, cantidad):
                num_actual = inicio + i
                nombre_final = f"{prefijo}{num_actual}"

                if not UnidadInmobiliaria.objects.filter(proyecto=obj.proyecto, numero=nombre_final).exists():
                    unidades_extra.append(
                        UnidadInmobiliaria(
                            proyecto=obj.proyecto,
                            tipo=obj.tipo,
                            numero=nombre_final,
                            precio_venta=obj.precio_venta,
                            area_m2=obj.area_m2,
                            estado_disponibilidad=obj.estado_disponibilidad
                        )
                    )

            if unidades_extra:
                UnidadInmobiliaria.objects.bulk_create(unidades_extra)
                messages.success(request, f"Se generaron {len(unidades_extra) + 1} unidades en total.")
        else:
            super().save_model(request, obj, form, change)

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

# ================================================
# 2. INVERSIONES
# ================================================
class CuotaInversionInline(admin.TabularInline):
    model = CuotaInversion
    extra = 0
    can_delete = False


    fields = (
        'nro_cuota', 'fecha_programada',
        'ver_bruto', 'ver_impuesto', 'ver_neto', 'ver_amortizacion', 'ver_total',
        'estado', 'fecha_pago_real', 'comprobante'
    )


    readonly_fields = (
        'nro_cuota', 'fecha_programada',
        'ver_bruto', 'ver_impuesto', 'ver_neto', 'ver_amortizacion', 'ver_total',
        'ver_capital_invertido'
    )

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
        from django.utils.html import format_html # Por si acaso falta el import
        return format_html("<b>{}</b>", formato_dinero(obj.total_pagar, obj.inversion.moneda))
    ver_total.short_description = "A Pagar"

    def ver_capital_invertido(self, obj):
        from django.utils.html import format_html
        return format_html("<b>{}</b>", formato_dinero(obj.amortizacion_capital, obj.inversion.moneda))
    ver_capital_invertido.short_description = "Capital Invertido"

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        formfield = super().formfield_for_dbfield(db_field, request, **kwargs)

        if formfield:
            if db_field.name in ['interes_bruto', 'monto_impuesto', 'interes_neto', 'amortizacion_capital',
                                 'total_pagar']:
                formfield.widget.attrs.update({'style': 'width: 100px;'})
            if db_field.name == 'nro_cuota':
                formfield.widget.attrs.update({
                    'readonly': 'readonly',
                    'style': 'width: 50px; background: #eee; border: none; text-align: center; font-weight: bold;'
                })
        return formfield


    def get_fields(self, request, obj=None):
        if obj and obj.tipo_calculo == 'MANUAL':
            return ('nro_cuota', 'fecha_programada', 'interes_bruto', 'monto_impuesto',
                    'interes_neto', 'amortizacion_capital', 'total_pagar', 'estado')

        elif obj and obj.tipo_calculo == 'EQUITY':
            return 'nro_cuota', 'ver_capital_invertido', 'fecha_programada', 'estado'

        else:
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in ['tea_anual', 'plazo_meses', 'frecuencia']:
            if campo in self.fields:
                self.fields[campo].required = False


@admin.register(Inversion)
class InversionAdmin(admin.ModelAdmin):
    form = InversionForm

    inlines = [CuotaInversionInline, DocumentoInline]

    list_display = ('id', 'inversor', 'proyecto', 'ver_capital', 'responsable_pago', 'fecha_desembolso', 'estado')
    list_filter = ('inversor','proyecto', 'responsable_pago', 'estado', 'moneda', 'frecuencia')
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

class FiltroEstadoAgenda(admin.SimpleListFilter):
    title = 'Estado'
    parameter_name = 'estado_custom'

    def lookups(self, request, model_admin):
        return (
            ('Pendiente', 'Pendientes'),
            ('Pagado', 'Pagado'),
        )

    def choices(self, changelist):
        yield {
            'selected': self.value() is None,
            'query_string': changelist.get_query_string(remove=[self.parameter_name]),
            'display': 'Todos',
        }
        yield {
            'selected': self.value() == 'Pendiente',
            'query_string': changelist.get_query_string({self.parameter_name: 'Pendiente'}, []),
            'display': 'Pendientes',
        }
        yield {
            'selected': self.value() == 'Pagado',
            'query_string': changelist.get_query_string({self.parameter_name: 'Pagado'}, []),
            'display': 'Pagado',
        }

    def queryset(self, request, queryset):
        from datetime import date
        from django.db.models import Q

        if self.value() == 'Pendiente':
            hoy = date.today()
            return queryset.filter(
                Q(estado='Pendiente') |
                Q(estado='Pagado', fecha_programada__gte=hoy)
            )
        if self.value() == 'Pagado':
            return queryset.filter(estado='Pagado')
        return queryset

@admin.register(AgendaPagos)
class AgendaPagosAdmin(admin.ModelAdmin):
    def get_list_display(self, request):
        if request.user.is_superuser:
            return ('ver_proyecto', 'ver_inversor', 'nro_cuota', 'ver_monto', 'ver_fecha_editable', 'ver_estado',
                    'accion_comprobante')
        return (
        'ver_proyecto', 'ver_inversor', 'nro_cuota', 'ver_monto', 'ver_fecha', 'ver_estado', 'accion_comprobante')

    fields = ('inversion', 'nro_cuota', 'estado', 'ver_ultima_edicion', 'comprobante', 'factura', 'retencion',
              'ver_fecha_vencimiento')
    readonly_fields = ('inversion', 'nro_cuota', 'ver_ultima_edicion', 'ver_fecha_vencimiento')

    def get_queryset(self, request):
        return super().get_queryset(request)

    list_filter = (
        FiltroCobrosFuturos,
        FiltroEstadoAgenda,  # Filtro personalizado conectado
        'inversion__inversor',
        'inversion__proyecto',
        'inversion__moneda'
    )

    search_fields = ('inversion__inversor__nombre_completo',)
    ordering = ('fecha_programada',)
    list_per_page = 20

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

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

    @admin.display(description='Fecha de Vencimiento')
    def ver_fecha_vencimiento(self, obj):
        if obj.fecha_programada:
            return obj.fecha_programada.strftime('%d/%m/%Y')
        return "-"

    @admin.display(description='Última Modificación')
    def ver_ultima_edicion(self, obj):
        from django.utils.html import format_html

        if obj.estado_log:
            return format_html(
                '<span style="color: #6c757d; font-style: italic;">{}</span>',
                obj.estado_log
            )
        return format_html('<span style="color: #adb5bd; font-style: italic;">Sin registro de ediciones</span>')

    @admin.display(description='Fecha de Pago', ordering='fecha_programada')
    def ver_fecha(self, obj):
        if obj.estado == 'Pagado' and obj.fecha_pago_real:
            return obj.fecha_pago_real.strftime('%d/%m/%Y')
        return obj.fecha_pago_texto()

    @admin.display(description='Fecha de Pago', ordering='fecha_programada')
    def ver_fecha_editable(self, obj):
        if obj.estado == 'Pagado' and obj.fecha_pago_real:
            texto = obj.fecha_pago_real.strftime('%d/%m/%Y')
            iso = obj.fecha_pago_real.strftime('%Y-%m-%d')
        else:
            texto = obj.fecha_pago_texto()
            iso = obj.fecha_programada.strftime('%Y-%m-%d') if obj.fecha_programada else ''

        es_equity = getattr(obj.inversion, 'tipo_calculo', '') == 'EQUITY'

        if es_equity:
            return format_html(
                '''
                <div style="display: flex; align-items: center; gap: 8px;">
                    <span>{texto}</span>
                    <input type="date" id="input-fecha-cuota-{id}" value="{iso}" style="display: none;" 
                           onchange="guardarFechaCuota({id}, this.value)">
                    <a href="javascript:void(0);" onclick="abrirCalendarioCuota('{id}')" style="color: #007bff; margin-top: 3px;" title="Editar Fecha">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                            <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
                            <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
                        </svg>
                    </a>
                </div>
                ''', id=obj.id, texto=texto, iso=iso
            )
        return texto

    @admin.display(description='Estado')
    def ver_estado(self, obj):
        log_texto = getattr(obj, 'estado_log', '')
        html_log = f'<div style="font-size: 11px; color: #888; margin-top: 4px; line-height: 1.1;">{log_texto}</div>' if log_texto else ''

        if obj.estado == 'Pagado':
            return format_html('<span style="color: #28a745; font-weight: bold;">Pagado</span>{}',
                               format_html(html_log))

        if not obj.fecha_programada:
            return format_html('-{}', format_html(html_log))

        dias = (obj.fecha_programada - date.today()).days
        if dias < 0:
            estado_html = f'<span style="color: #dc3545;">Vencido ({abs(dias)} días)</span>'
        elif dias <= 1:
            estado_html = "Vence pronto"
        else:
            estado_html = f"Faltan {dias} días"

        return format_html('{}{}', format_html(estado_html), format_html(html_log))

    def save_model(self, request, obj, form, change):
        if change:
            nombre = request.user.first_name or request.user.username
            fecha_hora = datetime.now().strftime("%d/%m/%Y %H:%M")
            obj.estado_log = f"Editado por {nombre} el {fecha_hora}"

        super().save_model(request, obj, form, change)

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('<int:cuota_id>/upload-ajax/', self.admin_site.admin_view(self.upload_ajax_view),
                 name='agendapagos-upload-ajax'),
            path('<int:cuota_id>/editar-fecha/', self.admin_site.admin_view(self.editar_fecha_ajax),
                 name='agendapagos-editar-fecha'),
        ]
        return custom_urls + urls

    def editar_fecha_ajax(self, request, cuota_id):
        import json
        if not request.user.is_superuser:
            return JsonResponse({'status': 'error', 'message': 'Acceso denegado.'}, status=403)

        if request.method == 'POST':
            try:
                data = json.loads(request.body)
                cuota = get_object_or_404(AgendaPagos, id=cuota_id)
                nueva_fecha = data.get('fecha')

                if cuota.estado == 'Pagado':
                    cuota.fecha_pago_real = nueva_fecha
                else:
                    cuota.fecha_programada = nueva_fecha

                # Firma
                nombre = request.user.first_name or request.user.username
                fecha_hora = datetime.now().strftime("%d/%m/%Y %H:%M")
                cuota.estado_log = f"Editado por {nombre} el {fecha_hora}"

                cuota.save()
                return JsonResponse({'status': 'ok'})
            except Exception as e:
                return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
        return JsonResponse({'status': 'error'}, status=400)

    def upload_ajax_view(self, request, cuota_id):
        if request.method == 'POST':
            cuota = get_object_or_404(AgendaPagos, id=cuota_id)
            nombre = request.user.first_name or request.user.username
            fecha_hora = datetime.now().strftime("%d/%m/%Y %H:%M")
            nota = f"por {nombre} el {fecha_hora}"

            if 'comprobante' in request.FILES:
                cuota.comprobante_log = f"Actualizado {nota}" if cuota.comprobante else f"Subido {nota}"
                cuota.comprobante = request.FILES['comprobante']
            elif 'factura' in request.FILES:
                cuota.factura_log = f"Actualizado {nota}" if cuota.factura else f"Subido {nota}"
                cuota.factura = request.FILES['factura']
            elif 'retencion' in request.FILES:
                cuota.retencion_log = f"Actualizado {nota}" if cuota.retencion else f"Subido {nota}"
                cuota.retencion = request.FILES['retencion']
            else:
                return JsonResponse({'status': 'error', 'message': 'Archivo no válido'}, status=400)

            # Firma global
            cuota.estado_log = f"Editado por {nombre} el {fecha_hora}"
            cuota.save()
            return JsonResponse({'status': 'ok'})

        return JsonResponse({'status': 'error'}, status=400)

    @admin.display(description='Comprobante')
    def accion_comprobante(self, obj):
        if obj.comprobante:
            return format_html(
                '<div style="text-align: center; line-height: 1;">'
                '<a href="{url}" target="_blank" title="Ver Documento">'
                '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#007bff" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: middle;">'
                '<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>'
                '<circle cx="12" cy="12" r="3"></circle>'
                '</svg></a></div>',
                url=obj.comprobante.url
            )
        else:
            return format_html(
                '<div style="text-align: center;">'
                '<a href="javascript:void(0);" onclick="abrirModalUpload({id})" style="text-decoration: none;" title="Subir Constancia">'
                '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#28a745" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">'
                '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>'
                '<polyline points="17 8 12 3 7 8"></polyline>'
                '<line x1="12" y1="3" x2="12" y2="15"></line>'
                '</svg></a></div>',
                id=obj.id
            )

    change_list_template = 'admin/core/agendapagos/change_list.html'
    change_form_template = 'admin/core/agendapagos/change_form.html'

    def changelist_view(self, request, extra_context=None):
        if not request.GET and request.path == request.get_full_path():
            return HttpResponseRedirect(request.path + "?vencimiento=este_mes&estado_custom=Pendiente")

        response = super().changelist_view(request, extra_context)
        if isinstance(response, TemplateResponse) and hasattr(response, 'context_data'):
            try:
                cl = response.context_data.get('cl')
                if cl:
                    qs = cl.queryset
                    resumen = qs.order_by().values('inversion__moneda').annotate(total=Sum('total_pagar'))
                    totales = {item['inversion__moneda']: item['total'] for item in resumen}
                    response.context_data['totales_por_moneda'] = totales
            except (AttributeError, KeyError):
                pass
        return response

    def formfield_for_dbfield(self, db_field, **kwargs):
        if db_field.name in ['comprobante', 'factura', 'retencion']:
            kwargs['widget'] = CustomFileWidget
        return super().formfield_for_dbfield(db_field, **kwargs)

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if obj:
            for field in ['comprobante', 'factura', 'retencion']:
                if field in form.base_fields:
                    form.base_fields[field].widget.attrs['data-obj-id'] = obj.id
        return form

    class Media:
        js = ('admin/js/vendor/jquery/jquery.js',)
        css = {
            'all': ('css/custom_admin.css',)
        }

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
    list_display = ('cliente', 'unidad', 'fecha_venta', 'ver_precio', 'tipo_financiamiento')
    list_filter = ('fecha_venta', 'tipo_financiamiento')

    autocomplete_fields = ['cliente', 'unidad']

    fields = (
        'cliente', 'unidad', 'fecha_venta', 'moneda',
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
# MÓDULO DE PRÉSTAMOS A TERCEROS
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

        if formfield:
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