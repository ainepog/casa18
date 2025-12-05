from django.contrib import admin
from django import forms
from .models import (
    Proyecto, Documento,
    Proveedor, Gasto, ProveedorProyecto,
    Inversor, Inversion, CuotaInversion,
    TipoDepartamento, Departamento, Cliente, Venta, ClienteProyecto
)

# ================================================
# 1. INVERSIONES Y CUOTAS (El Corazón del MVP)
# ================================================

class CuotaInversionInline(admin.TabularInline):
    model = CuotaInversion
    extra = 0
    readonly_fields = ('fecha_programada', 'total_pagar', 'alerta_estado')
    fields = ('nro_cuota', 'fecha_programada', 'alerta_estado', 'total_pagar', 'estado', 'fecha_pago_real')
    can_delete = False

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        formfield = super().formfield_for_dbfield(db_field, request, **kwargs)
        if db_field.name == 'alerta_estado':
            formfield.widget = forms.TextInput(attrs={'readonly':'readonly', 'style': 'border:none; background:none; font-weight:bold;'})
        return formfield

class InversionAdmin(admin.ModelAdmin):
    inlines = [CuotaInversionInline]
    # Usamos los nombres reales de tus modelos
    list_display = ('id', 'inversor', 'proyecto_nombre', 'capital_monto', 'estado', 'ver_progreso')
    list_filter = ('estado', 'proyecto')
    search_fields = ('inversor__nombre_completo',)
    autocomplete_fields = ['inversor', 'proyecto']

    def proyecto_nombre(self, obj): return obj.proyecto.nombre

    def ver_progreso(self, obj):
        pagadas = obj.cuotas.filter(estado='Pagado').count()
        total = obj.total_cuotas
        return f"{pagadas}/{total}"

# ================================================
# 2. PROYECTOS Y DEPARTAMENTOS
# ================================================

class TipoDepartamentoInline(admin.TabularInline):
    model = TipoDepartamento
    extra = 0
    fields = ('nombre', 'area_m2', 'precio_base', 'descripcion')

class ProyectoAdmin(admin.ModelAdmin):
    inlines = [TipoDepartamentoInline]
    list_display = ('nombre', 'estado', 'total_unidades', 'banco_activado_check')
    search_fields = ('nombre',)
    list_filter = ('estado', 'banco_activado')

    def banco_activado_check(self, obj):
        return "✅ SÍ" if obj.banco_activado else "❌ NO"
    banco_activado_check.short_description = "Banco OK"


class DepartamentoInline(admin.TabularInline):
    model = Departamento
    extra = 0
    fields = ('nro', 'piso', 'area_m2', 'ver_precio_base', 'estado_disponibilidad')
    readonly_fields = ('ver_precio_base',)  # Solo lectura

    def ver_precio_base(self, obj):
        return obj.tipo.precio_base

    ver_precio_base.short_description = "Precio Lista (Base)"


class DepartamentoAdmin(admin.ModelAdmin):
    list_display = ('nro', 'obtener_proyecto', 'tipo', 'ver_precio', 'estado_disponibilidad')
    list_filter = ('estado_disponibilidad',)
    search_fields = ('nro',)

    def obtener_proyecto(self, obj):
        return obj.tipo.proyecto.nombre

    def ver_precio(self, obj):
        return obj.tipo.precio_base

    ver_precio.short_description = "Precio Base"



# ================================================
# 3. CLIENTES, INVERSORES Y VENTAS
# ================================================

class ClienteAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'correo', 'telefono')
    search_fields = ('nombre', 'correo') # Necesario para el autocomplete

class InversorAdmin(admin.ModelAdmin):
    list_display = ('nombre_completo', 'nro_doc', 'correo', 'telefono')
    search_fields = ('nombre_completo', 'nro_doc') # Necesario para el autocomplete


class VentaAdmin(admin.ModelAdmin):
    list_display = ('id', 'cliente', 'departamento', 'ver_precio_lista', 'descuento_porcentaje', 'ver_monto_final',
                    'tipo_financiamiento')

    list_filter = ('fecha_venta', 'tipo_financiamiento')

    search_fields = ('cliente__nombre', 'departamento__nro')
    autocomplete_fields = ['cliente', 'departamento']

    fields = (
        'cliente',
        'departamento',
        'fecha_venta',
        'precio_lista',
        'descuento_porcentaje',
        'monto',
        # Sección Banco
        'tipo_financiamiento',
        'entidad_financiera',
        'porcentaje_financiado'
    )

    readonly_fields = ('precio_lista', 'monto')

    def ver_precio_lista(self, obj):
        return f"S/ {obj.precio_lista:,.2f}"

    ver_precio_lista.short_description = "Precio Lista"

    def ver_monto_final(self, obj):
        return f"S/ {obj.monto:,.2f}"

    ver_monto_final.short_description = "Monto Final"

class InteresInline(admin.TabularInline):
    model = ClienteProyecto
    extra = 1
    autocomplete_fields = ['proyecto']

class ClienteAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'correo', 'telefono', 'ver_proyectos_interes')
    search_fields = ('nombre', 'correo')
    inlines = [InteresInline]

    def ver_proyectos_interes(self, obj):
        intereses = obj.clienteproyecto_set.all()
        return ", ".join([i.proyecto.nombre for i in intereses])
    ver_proyectos_interes.short_description = "Proyectos de Interés"

# ================================================
# 4. REGISTRO FINAL
# ================================================

admin.site.register(Inversion, InversionAdmin)
admin.site.register(Proyecto, ProyectoAdmin)
admin.site.register(Departamento, DepartamentoAdmin)
admin.site.register(Cliente, ClienteAdmin)
admin.site.register(Inversor, InversorAdmin)
admin.site.register(Venta, VentaAdmin)

# Registros simples
admin.site.register(Proveedor)
admin.site.register(Gasto)
admin.site.register(TipoDepartamento)
admin.site.register(Documento)
admin.site.register(ProveedorProyecto)

# ================================================
# 5. Interface
# ================================================
admin.site.site_header = "ERP Inmobiliaria"
admin.site.site_title = "Panel Admin"
admin.site.index_title = "Gestión General"