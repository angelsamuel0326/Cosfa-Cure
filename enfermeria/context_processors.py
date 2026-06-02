def rol_usuario(request):
    """Expone `usuario_es_admin` a todos los templates."""
    if not request.user.is_authenticated:
        return {'usuario_es_admin': False}
    if request.user.is_superuser:
        return {'usuario_es_admin': True}
    try:
        es_admin = request.user.perfilusuario.rol == 'admin'
    except Exception:
        es_admin = False
    return {'usuario_es_admin': es_admin}
