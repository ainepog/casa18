from django.contrib import admin
from django import forms
from .models import (
    Proyecto, Documento,
    Proveedor, Gasto, ProveedorProyecto,
    Inversor, Inversion, CuotaInversion,
    TipoDepartamento, Departamento, Cliente, Venta
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
    # Mostramos los TIPOS dentro del proyecto (porque Depto no tiene enlace directo a Proyecto)
    model = TipoDepartamento
    extra = 0

class ProyectoAdmin(admin.ModelAdmin):
    inlines = [TipoDepartamentoInline]
    list_display = ('nombre', 'estado', 'total_unidades', 'banco_activado_check')
    search_fields = ('nombre',)
    list_filter = ('estado', 'banco_activado')

    def banco_activado_check(self, obj):
        return "✅ SÍ" if obj.banco_activado else "❌ NO"
    banco_activado_check.short_description = "Banco OK"

class DepartamentoAdmin(admin.ModelAdmin):
    list_display = ('nro', 'obtener_proyecto', 'tipo', 'precio', 'estado_disponibilidad')
    list_filter = ('estado_disponibilidad',)
    search_fields = ('nro',)

    def obtener_proyecto(self, obj):
        return obj.tipo.proyecto.nombre
    obtener_proyecto.short_description = "Proyecto"

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
    # 'monto' es el campo real, no 'precio_venta_final'
    list_display = ('id', 'cliente', 'departamento', 'monto', 'fecha_venta')
    list_filter = ('fecha_venta',)
    search_fields = ('cliente__nombre', 'departamento__nro')
    autocomplete_fields = ['cliente', 'departamento']

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
# 5. MAQUILLAJE
# ================================================
admin.site.site_header = "ERP Inmobiliaria"
admin.site.site_title = "Panel Admin"
admin.site.index_title = "Gestión General"