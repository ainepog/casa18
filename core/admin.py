from django.contrib import admin
from .models import Inversion, CuotaInversion, Proyecto, Cliente, Venta  # e importa tus otros modelos


# 1. Creamos una vista "en línea" de las cuotas
class CuotaInversionInline(admin.TabularInline):
    model = CuotaInversion
    extra = 0  # No mostrar filas vacías extra
    readonly_fields = ('fecha_programada', 'total_pagar', 'alerta_estado')  # Que nadie edite la fecha calculada a mano
    can_delete = False  # Para que no borren cuotas por error
    fields = ('nro_cuota', 'fecha_programada', 'alerta_estado', 'total_pagar', 'estado', 'fecha_pago_real')


# 2. Configuramos el Admin de la Inversión para que use esa vista
class InversionAdmin(admin.ModelAdmin):
    inlines = [CuotaInversionInline]  # <--- ESTO ES LA CLAVE
    list_display = ('inversor', 'proyecto', 'capital_monto', 'estado', 'ver_progreso')
    list_filter = ('estado', 'proyecto')

    # Un "campo falso" para mostrar progreso en la lista principal
    def ver_progreso(self, obj):
        pagadas = obj.cuotas.filter(estado='Pagado').count()
        total = obj.total_cuotas
        return f"{pagadas}/{total} Cuotas"



admin.site.register(Inversion, InversionAdmin)
admin.site.register(Proyecto)

