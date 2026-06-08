from django.urls import path
from . import views

urlpatterns = [
    path('inicio/', views.dashboard, name='dashboard'),
    path('landing/', views.landing, name='landing'),
    path('registro/', views.registro_usuario, name='registro_usuario'),
    path('verificar/', views.verificar_codigo, name='verificar_codigo'),
    path('verificar/reenviar/', views.reenviar_codigo, name='reenviar_codigo'),
    path('registro/admin-setup/', views.admin_setup, name='admin_setup'),
    path('registro/guardar-codigo-admin/', views.guardar_codigo_admin, name='guardar_codigo_admin'),
    path('buscar/', views.busqueda_global, name='busqueda_global'),

    # Estudiantes
    path('estudiantes/', views.lista_estudiantes, name='lista_estudiantes'),
    path('estudiantes/nuevo/', views.nuevo_estudiante, name='nuevo_estudiante'),
    path('estudiantes/<int:pk>/editar/', views.editar_estudiante, name='editar_estudiante'),
    path('estudiantes/<int:pk>/historial/', views.historial_estudiante, name='historial_estudiante'),
    path('estudiantes/<int:pk>/eliminar/', views.eliminar_estudiante, name='eliminar_estudiante'),
    path('estudiantes/<int:pk>/estado/', views.cambiar_estado_estudiante, name='cambiar_estado_estudiante'),
    path('estudiantes/<int:pk>/carnet/', views.carnet_pdf, name='carnet_pdf'),
    path('estudiantes/<int:pk>/pdf/', views.pdf_historial_estudiante, name='pdf_historial_estudiante'),

    # Consultas
    path('consultas/', views.lista_consultas, name='lista_consultas'),
    path('consultas/nueva/', views.nueva_consulta, name='nueva_consulta'),
    path('consultas/nueva/<int:estudiante_pk>/', views.nueva_consulta, name='nueva_consulta_estudiante'),
    path('consultas/<int:pk>/', views.detalle_consulta, name='detalle_consulta'),
    path('consultas/<int:pk>/editar/', views.editar_consulta, name='editar_consulta'),
    path('consultas/<int:pk>/eliminar/', views.eliminar_consulta, name='eliminar_consulta'),

    # Remisiones
    path('remisiones/', views.lista_remisiones, name='lista_remisiones'),
    path('remisiones/nueva/', views.nueva_remision, name='nueva_remision'),
    path('remisiones/nueva/<int:estudiante_pk>/', views.nueva_remision, name='nueva_remision_estudiante'),
    path('remisiones/<int:pk>/editar/', views.editar_remision, name='editar_remision'),
    path('remisiones/<int:pk>/eliminar/', views.eliminar_remision, name='eliminar_remision'),

    # Seguimientos / Calendario
    path('calendario/', views.calendario_seguimientos, name='calendario_seguimientos'),
    path('seguimientos/nuevo/', views.nuevo_seguimiento, name='nuevo_seguimiento'),
    path('seguimientos/nuevo/<int:estudiante_pk>/', views.nuevo_seguimiento, name='nuevo_seguimiento_estudiante'),
    path('seguimientos/<int:pk>/completar/', views.completar_seguimiento, name='completar_seguimiento'),

    # Inventario
    path('inventario/', views.inventario, name='inventario'),
    path('inventario/nuevo/', views.nuevo_medicamento, name='nuevo_medicamento'),
    path('inventario/<int:pk>/', views.detalle_medicamento, name='detalle_medicamento'),
    path('inventario/<int:pk>/editar/', views.editar_medicamento, name='editar_medicamento'),
    path('inventario/movimiento/', views.registrar_movimiento, name='registrar_movimiento'),
    path('inventario/alerta-correo/', views.enviar_alerta_inventario, name='enviar_alerta_inventario'),

    # Chatbot IA médico
    path('chatbot/', views.chatbot_ia, name='chatbot_ia'),
    path('chatbot/api/', views.chatbot_api, name='chatbot_api'),
    path('chatbot/diagnostico/', views.chatbot_diagnostico, name='chatbot_diagnostico'),
    path('chatbot/limpiar/', views.chatbot_limpiar, name='chatbot_limpiar'),
    path('chatbot/nueva-sesion/', views.chatbot_nueva_sesion, name='chatbot_nueva_sesion'),
    path('chatbot/sesion/renombrar/', views.chatbot_sesion_renombrar, name='chatbot_sesion_renombrar'),
    path('chatbot/sesion/borrar/', views.chatbot_sesion_borrar, name='chatbot_sesion_borrar'),

    # ── Notificaciones de seguimiento (manual) ───────────────────────────────
    path('seguimientos/notificar/', views.notificaciones_seguimiento, name='notificaciones_seguimiento'),

    # ── IA: resumen automático de consulta ───────────────────────────────────
    path('consultas/<int:pk>/pdf/', views.pdf_consulta_individual, name='pdf_consulta_individual'),
    path('consultas/<int:pk>/resumen-ia/', views.resumen_consulta_ia, name='resumen_consulta_ia'),

    # ── IA: alerta de patrón de salud por estudiante ──────────────────────────
    path('estudiantes/<int:estudiante_pk>/patron-salud/', views.alerta_patron_salud, name='alerta_patron_salud'),

    # ── PWA ───────────────────────────────────────────────────────────────────
    path('manifest.json', views.pwa_manifest, name='pwa_manifest'),
    path('sw.js', views.pwa_service_worker, name='pwa_service_worker'),

    # Perfil de usuario
    path('perfil/', views.perfil_usuario, name='perfil_usuario'),
    path('perfil/borrar-datos/', views.borrar_datos_anio, name='borrar_datos_anio'),
    path('perfil/usuarios/', views.gestionar_usuarios, name='gestionar_usuarios'),

    # Reportes y auditoria
    path('reportes/', views.reportes, name='reportes'),
    path('historial/', views.historial_cambios, name='historial_cambios'),
    path('historial/borrar/', views.borrar_historial_cambios, name='borrar_historial_cambios'),

    # ── Exportar Excel ────────────────────────────────────────────────────────
    path('consultas/<int:pk>/xlsx/', views.exportar_consulta_xlsx, name='exportar_consulta_xlsx'),
    path('consultas/<int:pk>/excel/', views.exportar_consulta_excel, name='exportar_consulta_excel'),

    # ── Seguimiento detalle ───────────────────────────────────────────────────
    path('seguimientos/<int:pk>/', views.detalle_seguimiento, name='detalle_seguimiento'),
    path('seguimientos/<int:pk>/editar/', views.editar_seguimiento, name='editar_seguimiento'),
    path('seguimientos/<int:pk>/eliminar/', views.eliminar_seguimiento, name='eliminar_seguimiento'),

    # ── Consentimiento digital de remisión ───────────────────────────────────
    path('remisiones/<int:pk>/consentimiento/', views.consentimiento_remision, name='consentimiento_remision'),
    path('remisiones/<int:pk>/consentimiento/guardar/', views.guardar_consentimiento_remision, name='guardar_consentimiento_remision'),
    path('remisiones/<int:pk>/estado/', views.cambiar_estado_remision, name='cambiar_estado_remision'),
    path('remisiones/<int:pk>/detalle/', views.detalle_remision, name='detalle_remision'),

    # ── PDF exports ───────────────────────────────────────────────────────────
    path('reportes/pdf/', views.pdf_reportes, name='pdf_reportes'),
    path('consultas/pdf/', views.pdf_consultas, name='pdf_consultas'),
    path('remisiones/pdf/', views.pdf_remisiones, name='pdf_remisiones'),
    path('remisiones/<int:pk>/pdf/', views.pdf_remision_individual, name='pdf_remision_individual'),
    path('inventario/movimientos/pdf/', views.pdf_movimientos, name='pdf_movimientos'),

    # Docentes (base de datos)
    path('docentes/', views.lista_docentes, name='lista_docentes'),
    path('docentes/nuevo/', views.nuevo_docente, name='nuevo_docente'),
    path('docentes/<int:pk>/historial/', views.historial_docente, name='historial_docente'),
    path('docentes/<int:pk>/editar/', views.editar_docente, name='editar_docente'),
    path('docentes/<int:pk>/eliminar/', views.eliminar_docente, name='eliminar_docente'),

    # Consultas Docentes
    path('docentes/consultas/', views.lista_consultas_docentes, name='lista_consultas_docentes'),
    path('docentes/consultas/nueva/', views.nueva_consulta_docente, name='nueva_consulta_docente'),
    path('docentes/<int:docente_pk>/consultas/nueva/', views.nueva_consulta_docente, name='nueva_consulta_docente_desde'),
    path('docentes/consultas/<int:pk>/', views.detalle_consulta_docente, name='detalle_consulta_docente'),
    path('docentes/consultas/<int:pk>/editar/', views.editar_consulta_docente, name='editar_consulta_docente'),
    path('docentes/consultas/<int:pk>/eliminar/', views.eliminar_consulta_docente, name='eliminar_consulta_docente'),

    # ── Excel exports ─────────────────────────────────────────────────────
    path('consultas/excel/', views.exportar_consultas_excel, name='exportar_consultas_excel'),
    path('remisiones/excel/', views.exportar_remisiones_excel, name='exportar_remisiones_excel'),
    path('estudiantes/excel/', views.exportar_estudiantes_excel, name='exportar_estudiantes_excel'),
    path('inventario/excel/', views.exportar_inventario_excel, name='exportar_inventario_excel'),
    path('docentes/excel/', views.exportar_docentes_excel, name='exportar_docentes_excel'),
    path('docentes/consultas/excel/', views.exportar_consultas_docentes_excel, name='exportar_consultas_docentes_excel'),
    path('reportes/excel/', views.exportar_reporte_excel, name='exportar_reporte_excel'),  # v19: Excel estadístico

    # ── Exportar XLSX real (botones de página) ────────────────────────────
    path('estudiantes/xlsx/', views.exportar_estudiantes_xlsx, name='exportar_estudiantes_xlsx'),
    path('consultas/xlsx/', views.exportar_consultas_xlsx, name='exportar_consultas_xlsx'),
    path('consultas/docentes/xlsx/', views.exportar_consultas_docentes_xlsx, name='exportar_consultas_docentes_xlsx'),
    path('remisiones/xlsx/', views.exportar_remisiones_xlsx, name='exportar_remisiones_xlsx'),
    path('inventario/xlsx/', views.exportar_inventario_xlsx, name='exportar_inventario_xlsx'),
    path('docentes/xlsx/', views.exportar_docentes_xlsx, name='exportar_docentes_xlsx'),

    # ── Importar Excel (carga masiva) ─────────────────────────────────────
    path('estudiantes/importar/', views.importar_estudiantes_excel, name='importar_estudiantes_excel'),
    path('estudiantes/plantilla/', views.plantilla_importar_estudiantes, name='plantilla_importar_estudiantes'),
    path('docentes/importar/', views.importar_docentes_excel, name='importar_docentes_excel'),
    path('docentes/plantilla/', views.plantilla_importar_docentes, name='plantilla_importar_docentes'),

    # ── Gestión de Grados Escolares ───────────────────────────────────────
    path('grados/', views.grados_lista, name='grados_lista'),
    path('grados/crear/', views.crear_grado, name='crear_grado'),
    path('grados/<int:pk>/eliminar/', views.eliminar_grado, name='eliminar_grado'),
    path('grados/<int:pk>/toggle/', views.toggle_grado, name='toggle_grado'),

    # ── Promoción de año ──────────────────────────────────────────────────
    path('estudiantes/promocion/', views.promocion_anio, name='promocion_anio'),
    path('estudiantes/<int:pk>/promover/', views.promover_estudiante, name='promover_estudiante'),
    path('estudiantes/promover-masivo/', views.promover_masivo, name='promover_masivo'),

    # ── API búsqueda tiempo real ──────────────────────────────────────────
    path('api/buscar/consultas/', views.api_buscar_consultas, name='api_buscar_consultas'),
    path('api/buscar/remisiones/', views.api_buscar_remisiones, name='api_buscar_remisiones'),

    # ── v18: Reagendar seguimiento desde el calendario ────────────────────
    path('seguimientos/<int:pk>/reagendar/', views.reagendar_seguimiento, name='reagendar_seguimiento'),

    # ── v18: API reporte frecuentes + motivos + comparativo mes a mes ─────
    path('api/reportes/frecuentes/', views.api_reporte_frecuentes, name='api_reporte_frecuentes'),

    # ── v18: Chatbot contextual con historial del estudiante e inventario ─
    path('chatbot/api/consulta/', views.chatbot_api_consulta, name='chatbot_api_consulta'),

    # ── v18: API inventario disponible (para chatbot de consulta) ─────────
    path('api/inventario/disponible/', views.api_inventario_disponible, name='api_inventario_disponible'),
    # ── Notificaciones internas ───────────────────────────────────────────
    # ── Tracking apertura de correos ──────────────────────────────────────────
    path('correo/pixel/<str:token>/',      views.tracking_pixel,              name='tracking_pixel'),
    path('correo/confirmar/<str:token>/',  views.tracking_confirmar,          name='tracking_confirmar'),
    path('correo/historial/',              views.historial_correos_tracking,  name='historial_correos_tracking'),

    path('api/notificaciones/', views.api_notificaciones, name='api_notificaciones'),
    path('api/notificaciones/<int:pk>/leer/', views.marcar_notificacion_leida, name='marcar_notificacion_leida'),
    path('api/notificaciones/leer-todas/', views.marcar_todas_leidas, name='marcar_todas_leidas'),

    # ── Correo al coordinador ─────────────────────────────────────────────
    path('api/correo-coordinador/', views.enviar_correo_coordinador, name='enviar_correo_coordinador'),

    # ── Backup / Restore base de datos (v29 – solo superusuarios) ────────
    path('perfil/backup-bd/',  views.backup_bd,  name='backup_bd'),
    path('perfil/restore-bd/', views.restore_bd, name='restore_bd'),
    path('api/notificaciones/borrar-todas/', views.borrar_todas_notificaciones, name='borrar_todas_notificaciones'),
    path('api/notificaciones/<int:pk>/borrar/', views.borrar_notificacion_individual, name='borrar_notificacion_individual'),
    path('api/estudiante/<int:pk>/datos/', views.api_datos_estudiante, name='api_datos_estudiante'),
]
