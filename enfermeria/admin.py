from django.contrib import admin
from .models import (Estudiante, Docente, Consulta, ConsultaDocente, Remision, Seguimiento,
                     Medicamento, MovimientoInventario, HistorialCambio,
                     MedicamentoConsulta, PerfilUsuario, MensajeChatbot)

@admin.register(Estudiante)
class EstudianteAdmin(admin.ModelAdmin):
    list_display  = ['nombre', 'grado', 'numero_documento', 'eps', 'tipo_sangre']
    search_fields = ['nombre', 'numero_documento']
    list_filter   = ['grado', 'tipo_sangre']


class MedicamentoConsultaInline(admin.TabularInline):
    model = MedicamentoConsulta
    fields = ['medicamento', 'cantidad', 'dosis']
    extra = 1


@admin.register(Consulta)
class ConsultaAdmin(admin.ModelAdmin):
    list_display  = ['estudiante', 'motivo', 'medicamentos_resumen', 'estado', 'fecha_hora', 'acudiente_notificado']
    list_filter   = ['motivo', 'estado']
    search_fields = ['estudiante__nombre']
    inlines       = [MedicamentoConsultaInline]

    def medicamentos_resumen(self, obj):
        usos = obj.medicamentos_usados.select_related('medicamento').all()
        if usos:
            return ', '.join(f'{u.medicamento.nombre} ×{u.cantidad}' for u in usos if u.medicamento)
        return obj.medicamento_suministrado or '—'
    medicamentos_resumen.short_description = 'Medicamentos'


@admin.register(Remision)
class RemisionAdmin(admin.ModelAdmin):
    list_display = ['estudiante', 'hospital_destino', 'eps', 'hora_salida', 'estado']
    list_filter  = ['estado']


@admin.register(Seguimiento)
class SeguimientoAdmin(admin.ModelAdmin):
    list_display = ['estudiante', 'tipo', 'fecha', 'completado']
    list_filter  = ['completado', 'tipo']


class MedicamentoConsultaReadInline(admin.TabularInline):
    model = MedicamentoConsulta
    fields = ['consulta', 'cantidad', 'dosis']
    readonly_fields = ['consulta', 'cantidad', 'dosis']
    extra = 0
    can_delete = False
    verbose_name = 'Consulta que usó este medicamento'
    verbose_name_plural = 'Consultas que usaron este medicamento'


class MovimientoInline(admin.TabularInline):
    model = MovimientoInventario
    fields = ['tipo', 'cantidad', 'motivo', 'fecha']
    readonly_fields = ['fecha']
    extra = 1


@admin.register(Medicamento)
class MedicamentoAdmin(admin.ModelAdmin):
    list_display  = ['nombre', 'cantidad_actual', 'unidad', 'cantidad_minima', 'fecha_vencimiento', 'total_usos']
    list_filter   = ['unidad']
    search_fields = ['nombre']
    inlines       = [MedicamentoConsultaReadInline, MovimientoInline]

    def total_usos(self, obj):
        return obj.usos_consulta.count()
    total_usos.short_description = 'Usos en consultas'


@admin.register(MovimientoInventario)
class MovimientoAdmin(admin.ModelAdmin):
    list_display  = ['medicamento', 'tipo', 'cantidad', 'motivo', 'fecha']
    list_filter   = ['tipo']
    search_fields = ['medicamento__nombre', 'motivo']


@admin.register(HistorialCambio)
class HistorialAdmin(admin.ModelAdmin):
    list_display = ['fecha', 'usuario', 'accion', 'modelo', 'descripcion']
    list_filter  = ['accion', 'modelo']

from .models import ConsentimientoRemision
admin.site.register(ConsentimientoRemision)


@admin.register(Docente)
class DocenteAdmin(admin.ModelAdmin):
    list_display   = ['nombre', 'cedula', 'area', 'grados_asignados', 'eps', 'telefono', 'activo']
    list_filter    = ['area', 'activo', 'vinculacion']
    search_fields  = ['nombre', 'cedula']
    list_editable  = ['activo']


@admin.register(ConsultaDocente)
class ConsultaDocenteAdmin(admin.ModelAdmin):
    list_display  = ['nombre_completo', 'cedula', 'area_grado', 'eps', 'hora_atencion', 'motivo', 'estado', 'fecha_hora']
    list_filter   = ['motivo', 'estado']
    search_fields = ['nombre_completo', 'cedula', 'area_grado']


@admin.register(PerfilUsuario)
class PerfilUsuarioAdmin(admin.ModelAdmin):
    list_display  = ['usuario', 'cargo', 'telefono', 'fecha_creacion']
    search_fields = ['usuario__username', 'usuario__first_name', 'cargo']


@admin.register(MensajeChatbot)
class MensajeChatbotAdmin(admin.ModelAdmin):
    list_display  = ['usuario', 'role', 'modelo_ia', 'fecha', 'content_preview']
    list_filter   = ['role', 'modelo_ia']
    search_fields = ['usuario__username', 'content']
    readonly_fields = ['usuario', 'role', 'content', 'modelo_ia', 'fecha']

    def content_preview(self, obj):
        return obj.content[:60] + '…' if len(obj.content) > 60 else obj.content
    content_preview.short_description = 'Mensaje'
