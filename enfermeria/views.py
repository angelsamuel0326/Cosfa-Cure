from django.db import models as django_models
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth import logout as auth_logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Q, Count, Sum, F
from django.utils import timezone
from django.http import HttpResponse, JsonResponse
from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
import datetime, json
import urllib.request as _urllib_req
import os
from email.mime.image import MIMEImage


# ── CONTROL DE ROL ────────────────────────────────────────────────────────────
def es_admin(user):
    """Devuelve True si el usuario tiene rol admin o es superusuario."""
    if user.is_superuser:
        return True
    try:
        return user.perfilusuario.rol == 'admin'
    except Exception:
        return False


def admin_required(view_func):
    """Decorador: requiere login + rol admin. Si no, redirige con mensaje."""
    from functools import wraps
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            from django.contrib.auth.views import redirect_to_login
            return redirect_to_login(request.get_full_path())
        if not es_admin(request.user):
            messages.error(request, '🚫 No tienes permiso para realizar esta acción.')
            return redirect('dashboard')
        return view_func(request, *args, **kwargs)
    return _wrapped


# ── LOGO CID HELPER ───────────────────────────────────────────────────────────
def _get_logo_path():
    """Devuelve la ruta absoluta al logo del colegio."""
    return os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        'static', 'icons', 'logo_cosfa.png'
    )


def _adjuntar_logo(msg):
    """
    Adjunta el logo del colegio al EmailMultiAlternatives como imagen inline (CID).
    El HTML debe referenciar el logo así:  <img src="cid:logo_cosfa">
    Funciona en Gmail, Outlook y todos los clientes de correo principales.
    """
    logo_path = _get_logo_path()
    if not os.path.exists(logo_path):
        return msg
    with open(logo_path, 'rb') as f:
        img = MIMEImage(f.read(), _subtype='png')
    img.add_header('Content-ID', '<logo_cosfa>')
    img.add_header('Content-Disposition', 'inline', filename='logo_cosfa.png')
    msg.attach(img)
    return msg

try:
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment
    OPENPYXL_OK = True
except ImportError:
    OPENPYXL_OK = False

from .models import (
    Estudiante, Docente, Consulta, ConsultaDocente, Remision, Seguimiento, Medicamento,
    MovimientoInventario, MedicamentoConsulta, ConsentimientoRemision,
    HistorialCambio, PerfilUsuario, MensajeChatbot, SesionChatbot, GradoEscolar,
    Notificacion, CorreoCoordinador, RegistroAperturaCorreo,
)
from .forms import (EstudianteForm, DocenteForm, ConsultaForm, ConsultaDocenteForm, RemisionForm,
                    SeguimientoForm, MedicamentoForm, MovimientoForm)



def custom_login(request):
    """Vista de login personalizada que detecta el código secreto admin (262728)."""
    from django.contrib.auth import authenticate, login as auth_login
    from django.contrib.auth.forms import AuthenticationForm
    from .models import PerfilUsuario

    # Leer clave admin dinámica (si fue cambiada) o usar la predeterminada
    import os as _os
    _secret_file = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))), 'cosfa_cure', 'admin_secret.txt')
    try:
        with open(_secret_file, 'r') as _sf:
            ADMIN_SECRET = _sf.read().strip() or None
    except Exception:
        ADMIN_SECRET = None

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        admin_secret = request.POST.get('admin_secret', '').strip()
        next_url = request.POST.get('next', '') or request.GET.get('next', '')

        user = authenticate(request, username=username, password=password)
        if user is not None:
            auth_login(request, user)
            # Si se envió el código secreto correcto, asignar rol admin
            if ADMIN_SECRET and admin_secret == ADMIN_SECRET:
                perfil, _ = PerfilUsuario.objects.get_or_create(usuario=user)
                if perfil.rol != PerfilUsuario.ROL_ADMIN:
                    perfil.rol = PerfilUsuario.ROL_ADMIN
                    perfil.save(update_fields=['rol'])
            return redirect(next_url or 'dashboard')
        else:
            # Credenciales incorrectas — mostrar el form con error
            form = AuthenticationForm(request, data=request.POST)
            form.is_valid()  # para poblar errors
            return render(request, 'registration/login.html', {
                'form': form,
                'next': next_url,
                'admin_secret': ADMIN_SECRET,
                'login_error': True,
            })

    # GET
    form = AuthenticationForm(request)
    next_url = request.GET.get('next', '')
    return render(request, 'registration/login.html', {
        'form': form,
        'next': next_url,
        'admin_secret': ADMIN_SECRET,
    })


def landing(request):
    """Landing page — visible siempre, incluso estando autenticado."""
    return render(request, 'enfermeria/landing.html')


def registro_usuario(request):
    """Paso 1: Recibe username, email y password, envía código OTP."""
    from .models import CodigoVerificacion
    import random, hashlib
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email    = request.POST.get('email', '').strip().lower()
        password = request.POST.get('password', '')
        password2 = request.POST.get('password2', '')

        if not username or not email or not password:
            messages.error(request, 'Todos los campos son obligatorios.')
            return render(request, 'enfermeria/registro.html')
        if password != password2:
            messages.error(request, 'Las contraseñas no coinciden.')
            return render(request, 'enfermeria/registro.html')
        if User.objects.filter(username=username).exists():
            messages.error(request, 'Ese nombre de usuario ya existe.')
            return render(request, 'enfermeria/registro.html')
        if User.objects.filter(email=email).exists():
            messages.error(request, 'Ese correo ya está registrado.')
            return render(request, 'enfermeria/registro.html')
        if len(password) < 8:
            messages.error(request, 'La contraseña debe tener al menos 8 caracteres.')
            return render(request, 'enfermeria/registro.html')

        codigo = str(random.randint(100000, 999999))
        # Hash password para no guardarla en texto plano
        from django.contrib.auth.hashers import make_password
        hashed = make_password(password)

        # Borrar códigos anteriores para el mismo email
        CodigoVerificacion.objects.filter(email=email).delete()
        CodigoVerificacion.objects.create(email=email, username=username, password=hashed, codigo=codigo)

        # Enviar correo
        try:
            send_mail(
                subject='COSFA CURE – Código de verificación',
                message=f'Tu código de verificación es: {codigo}\nVigencia: 10 minutos.',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                fail_silently=True,
            )
            request.session['registro_email'] = email
            messages.success(request, f'Código enviado a {email}')
            return redirect('verificar_codigo')
        except Exception as e:
            messages.error(request, f'No se pudo enviar el correo: {e}')
            return render(request, 'enfermeria/registro.html')


    es_primer = User.objects.count() == 0
    return render(request, 'enfermeria/registro.html', {'es_primer_usuario': es_primer})


def verificar_codigo(request):
    """Paso 2: Verifica el código OTP y crea el usuario."""
    from .models import CodigoVerificacion, PerfilUsuario
    email = request.session.get('registro_email')
    if not email:
        return redirect('registro_usuario')

    if request.method == 'POST':
        codigo_ingresado = request.POST.get('codigo', '').strip()
        try:
            obj = CodigoVerificacion.objects.filter(email=email, verificado=False).latest('creado_en')
        except CodigoVerificacion.DoesNotExist:
            messages.error(request, 'No hay código pendiente. Regístrate de nuevo.')
            return redirect('registro_usuario')

        if not obj.esta_vigente():
            messages.error(request, 'El código expiró. Regístrate de nuevo.')
            obj.delete()
            return redirect('registro_usuario')

        if obj.codigo != codigo_ingresado:
            messages.error(request, 'Código incorrecto.')
            return render(request, 'enfermeria/verificar_codigo.html', {'email': email})

        # Crear usuario
        from django.contrib.auth.hashers import is_password_usable
        es_primer_usuario = User.objects.count() == 0
        user = User(username=obj.username, email=email)
        user.password = obj.password  # ya hasheado
        if es_primer_usuario:
            # El primer usuario es superusuario con acceso total
            user.is_staff = True
            user.is_superuser = True
        user.save()
        perfil, _ = PerfilUsuario.objects.get_or_create(usuario=user)
        if es_primer_usuario:
            perfil.rol = PerfilUsuario.ROL_ADMIN
            perfil.save(update_fields=['rol'])

        obj.verificado = True
        obj.save()
        del request.session['registro_email']

        if es_primer_usuario:
            # Guardar en sesión y redirigir al login — el modal aparecerá en el dashboard
            request.session['admin_setup_user'] = user.username
            messages.success(request, '¡Cuenta creada! Inicia sesión para continuar.')
            return redirect('login')
        else:
            messages.success(request, '¡Cuenta creada! Ahora puedes ingresar.')
            return redirect('login')

    return render(request, 'enfermeria/verificar_codigo.html', {'email': email})


def admin_setup(request):
    """Página de configuración del código de seguridad para el primer admin."""
    username = request.session.get('admin_setup_user')
    if not username:
        return redirect('login')
    return render(request, 'enfermeria/admin_setup.html', {'username': username})


def guardar_codigo_admin(request):
    """Guarda el código de seguridad elegido por el primer admin (AJAX POST)."""
    import json, os, re
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Método no permitido'}, status=405)

    username = request.session.get('admin_setup_user')
    if not username:
        return JsonResponse({'ok': False, 'error': 'Sesión inválida.'}, status=403)

    try:
        data = json.loads(request.body)
        codigo = str(data.get('codigo', '')).strip()
    except Exception:
        return JsonResponse({'ok': False, 'error': 'Datos inválidos.'}, status=400)

    if not re.fullmatch(r'\d{6}', codigo):
        return JsonResponse({'ok': False, 'error': 'El código debe ser exactamente 6 dígitos.'})

    # Guardar en admin_secret.txt (clave activa)
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    secret_file  = os.path.join(base_dir, 'cosfa_cure', 'admin_secret.txt')
    default_file = os.path.join(base_dir, 'cosfa_cure', 'admin_secret_default.txt')
    try:
        with open(secret_file, 'w') as f:
            f.write(codigo)
        # Guardar también como clave predeterminada SOLO si aún no existe
        if not os.path.exists(default_file):
            with open(default_file, 'w') as f:
                f.write(codigo)
    except Exception as e:
        return JsonResponse({'ok': False, 'error': f'No se pudo guardar: {e}'})

    # Limpiar sesión de setup
    request.session.pop('admin_setup_user', None)
    return JsonResponse({'ok': True})


def reenviar_codigo(request):
    """Reenvía el código OTP al correo almacenado en sesión (AJAX POST)."""
    import random, json
    from .models import CodigoVerificacion
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Método no permitido'}, status=405)
    email = request.session.get('registro_email')
    if not email:
        return JsonResponse({'ok': False, 'error': 'Sesión expirada. Regístrate de nuevo.'})
    # Recuperar datos del registro previo
    try:
        obj_prev = CodigoVerificacion.objects.filter(email=email, verificado=False).latest('creado_en')
    except CodigoVerificacion.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'No hay registro pendiente.'})
    # Cooldown: no reenviar si el código tiene menos de 60 seg
    from django.utils import timezone
    elapsed = (timezone.now() - obj_prev.creado_en).total_seconds()
    if elapsed < 60:
        wait = int(60 - elapsed)
        return JsonResponse({'ok': False, 'error': f'Espera {wait}s antes de reenviar.'})
    codigo = str(random.randint(100000, 999999))
    CodigoVerificacion.objects.filter(email=email).delete()
    CodigoVerificacion.objects.create(
        email=email, username=obj_prev.username,
        password=obj_prev.password, codigo=codigo
    )
    try:
        send_mail(
            subject='COSFA CURE — Nuevo código de verificación',
            message=f'Tu nuevo código de verificación es: {codigo}\nVigencia: 10 minutos.',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=False,
        )
    except Exception as e:
        return JsonResponse({'ok': False, 'error': f'No se pudo enviar: {e}'})
    return JsonResponse({'ok': True, 'msg': f'Código reenviado a {email}'})


def logout_view(request):
    """Cierra sesión y redirige al login. Acepta GET y POST (incluye sendBeacon)."""
    auth_logout(request)
    if request.headers.get('x-requested-with') == 'XMLHttpRequest' or not request.accepts('text/html'):
        return HttpResponse(status=204)
    return redirect('login')


def _log(request, accion, modelo, descripcion):
    HistorialCambio.objects.create(
        usuario=request.user, accion=accion, modelo=modelo, descripcion=descripcion
    )

# ── HELPER: Tracking apertura de correos ─────────────────────────────────────
import secrets as _secrets

def _crear_registro_tracking(tipo, destinatario_email, destinatario_nombre='',
                              enviado_por=None, objeto_id=None, objeto_tipo=''):
    """
    Crea un RegistroAperturaCorreo y devuelve el token único.
    Si la tabla no existe aún (migración pendiente), igual genera el token.
    """
    token = _secrets.token_urlsafe(32)
    try:
        RegistroAperturaCorreo.objects.create(
            tipo               = tipo,
            destinatario_email = destinatario_email,
            destinatario_nombre= destinatario_nombre,
            token              = token,
            enviado_por        = enviado_por,
            objeto_id          = objeto_id,
            objeto_tipo        = objeto_tipo,
        )
    except Exception:
        pass  # Si la migración no se corrió, igual se genera el token y las URLs
    return token


def _get_tracking_urls(token, request=None):
    """
    Devuelve las URLs absolutas del píxel y del enlace de confirmación.
    Usa SITE_URL de settings para garantizar URL pública (ngrok o dominio real).
    """
    pixel_path   = f'/correo/pixel/{token}/'
    confirm_path = f'/correo/confirmar/{token}/'

    # Prioridad 1: SITE_URL explícita en settings (ngrok o producción)
    site_url = getattr(settings, 'SITE_URL', '').rstrip('/')
    if site_url:
        return site_url + pixel_path, site_url + confirm_path

    # Prioridad 2: construir desde el request (funciona si USE_X_FORWARDED_HOST=True)
    if request:
        base = request.build_absolute_uri('/').rstrip('/')
        return base + pixel_path, base + confirm_path

    # Fallback: ruta relativa (no funciona para tracking externo)
    return pixel_path, confirm_path


def _registrar_apertura(token, metodo, request=None):
    """
    Marca el correo como abierto y crea notificación interna.
    Retorna el registro o None si el token no existe.
    """
    try:
        reg = RegistroAperturaCorreo.objects.get(token=token)
    except RegistroAperturaCorreo.DoesNotExist:
        return None

    reg.veces_abierto += 1

    # Solo notificar la primera apertura real
    primera_vez = not reg.abierto
    if primera_vez:
        reg.abierto         = True
        reg.fecha_apertura  = timezone.now()
        reg.metodo_apertura = metodo
        if request:
            reg.ip_apertura = (
                request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip()
                or request.META.get('REMOTE_ADDR', '')
            )
            reg.user_agent = request.META.get('HTTP_USER_AGENT', '')[:500]

    reg.save()

    if primera_vez:
        # Notificar a todos los usuarios activos del sistema
        from django.contrib.auth.models import User
        tipo_labels = dict(RegistroAperturaCorreo.TIPO_CHOICES)
        metodo_txt  = 'abrió' if metodo == 'pixel' else 'confirmó recepción de'
        nombre_dest = reg.destinatario_nombre or reg.destinatario_email
        hora        = reg.fecha_apertura.strftime('%H:%M')
        titulo  = f'👁️ {nombre_dest} {metodo_txt} el correo'
        mensaje = (f'{tipo_labels.get(reg.tipo, reg.tipo)} — '
                   f'{reg.destinatario_email} — {hora}')
        url_notif = '/correo/historial/'

        for u in User.objects.filter(is_active=True):
            Notificacion.objects.create(
                usuario = u,
                tipo    = 'sistema',
                titulo  = titulo,
                mensaje = mensaje,
                url     = url_notif,
            )

    return reg


# ── HELPER: Notificaciones de seguimiento ────────────────────────────────────
def _notificar_seguimiento_nuevo(seguimiento, usuario):
    """Notifica a todos los usuarios activos cuando se programa un nuevo seguimiento."""
    from django.contrib.auth.models import User
    hoy = datetime.date.today()
    dias = (seguimiento.fecha - hoy).days
    if dias == 0:
        cuando = 'para hoy'
    elif dias == 1:
        cuando = 'para mañana'
    elif dias > 0:
        cuando = f'en {dias} días ({seguimiento.fecha.strftime("%d/%m/%Y")})'
    else:
        cuando = f'el {seguimiento.fecha.strftime("%d/%m/%Y")} (vencido)'

    titulo  = f'📋 Nuevo seguimiento: {seguimiento.estudiante.nombre}'
    mensaje = (f'{seguimiento.get_tipo_display()} programado {cuando} '
               f'— {seguimiento.descripcion[:100]}')
    url     = f'/enfermeria/calendario/'

    for u in User.objects.filter(is_active=True):
        Notificacion.objects.create(
            usuario=u, tipo='seguimiento',
            titulo=titulo, mensaje=mensaje, url=url,
        )


def _notificar_seguimiento_completado(seguimiento, usuario):
    """Notifica a todos cuando un seguimiento es completado o extendido."""
    from django.contrib.auth.models import User
    if seguimiento.continuado:
        titulo  = f'🔄 Seguimiento extendido: {seguimiento.estudiante.nombre}'
        mensaje = (f'{seguimiento.get_tipo_display()} extendido hasta '
                   f'{seguimiento.fecha_fin.strftime("%d/%m/%Y") if seguimiento.fecha_fin else "nueva fecha"}')
    else:
        titulo  = f'✅ Seguimiento completado: {seguimiento.estudiante.nombre}'
        mensaje = (f'{seguimiento.get_tipo_display()} cerrado correctamente. '
                   f'{("Evolución: " + seguimiento.evolucion[:80]) if seguimiento.evolucion else ""}')
    url = f'/enfermeria/seguimientos/{seguimiento.pk}/'

    for u in User.objects.filter(is_active=True):
        Notificacion.objects.create(
            usuario=u, tipo='seguimiento',
            titulo=titulo, mensaje=mensaje, url=url,
        )


def _notificar_seguimientos_vencidos():
    """Crea notificaciones internas para seguimientos vencidos y próximos a vencer.
    Llamado desde el management command diario."""
    from django.contrib.auth.models import User
    hoy      = datetime.date.today()
    en_7     = hoy + datetime.timedelta(days=7)

    vencidos = Seguimiento.objects.filter(completado=False, fecha__lt=hoy).select_related('estudiante')
    proximos = Seguimiento.objects.filter(completado=False, fecha__gte=hoy, fecha__lte=en_7).select_related('estudiante')

    usuarios = list(User.objects.filter(is_active=True))
    creadas  = 0

    for u in usuarios:
        if vencidos.exists():
            nombres = ', '.join(s.estudiante.nombre for s in vencidos[:3])
            extra   = f' y {vencidos.count()-3} más' if vencidos.count() > 3 else ''
            Notificacion.objects.create(
                usuario=u, tipo='seguimiento',
                titulo=f'🔴 {vencidos.count()} seguimiento(s) vencido(s)',
                mensaje=f'Sin completar: {nombres}{extra}. Revisa el calendario.',
                url='/enfermeria/calendario/',
            )
            creadas += 1
        if proximos.exists():
            nombres = ', '.join(s.estudiante.nombre for s in proximos[:3])
            extra   = f' y {proximos.count()-3} más' if proximos.count() > 3 else ''
            Notificacion.objects.create(
                usuario=u, tipo='seguimiento',
                titulo=f'🟡 {proximos.count()} seguimiento(s) esta semana',
                mensaje=f'Próximos 7 días: {nombres}{extra}.',
                url='/enfermeria/calendario/',
            )
            creadas += 1

    return creadas


# ── CORREO 1: Consulta registrada → acudiente ─────────────────────────────────
def _correo_consulta_acudiente(consulta, request=None):
    est = consulta.estudiante
    destinatario = est.correo_acudiente
    if not destinatario:
        return False, 'Sin correo de acudiente registrado'
    try:
        token = _crear_registro_tracking(
            tipo='acudiente',
            destinatario_email=destinatario,
            destinatario_nombre=est.acudiente or '',
            objeto_id=consulta.pk,
            objeto_tipo='Consulta',
        )
        pixel_url, confirm_url = _get_tracking_urls(token, request)
        asunto = f'[COSFA CURE] Atención médica: {est.nombre} — {consulta.get_motivo_display()}'
        html   = render_to_string('enfermeria/emails/consulta_acudiente.html', {
            'estudiante': est, 'consulta': consulta,
            'pixel_url': pixel_url, 'confirm_url': confirm_url,
        })
        texto  = (
            f"Estimado/a {est.acudiente},\n\n"
            f"{est.nombre} ({est.grado}) fue atendido/a en enfermería el "
            f"{timezone.localtime(consulta.fecha_hora).strftime('%d/%m/%Y a las %H:%M')}.\n"
            f"Motivo: {consulta.get_motivo_display()}\n"
            f"Tratamiento: {consulta.tratamiento}\n"
            f"Estado: {consulta.get_estado_display()}\n\n"
            f"— COSFA CURE | Colegio San Francisco de Asís"
        )
        msg = EmailMultiAlternatives(asunto, texto, settings.DEFAULT_FROM_EMAIL, [destinatario])
        msg.attach_alternative(html, 'text/html')
        msg.mixed_subtype = 'related'
        _adjuntar_logo(msg)
        msg.send()
        return True, destinatario
    except Exception as e:
        return False, str(e)


# ── CORREO 2: Remisión registrada → acudiente ─────────────────────────────────
def _correo_remision_acudiente(remision, request=None):
    est = remision.estudiante
    # Prioridad: correo ingresado en el form de remisión, luego el del perfil del estudiante
    destinatario = (getattr(remision, 'correo_padre_madre', '') or '').strip() or est.correo_acudiente
    if not destinatario:
        return False, 'Sin correo de acudiente registrado'
    try:
        token = _crear_registro_tracking(
            tipo='remision',
            destinatario_email=destinatario,
            destinatario_nombre=est.acudiente or '',
            objeto_id=remision.pk,
            objeto_tipo='Remision',
        )
        pixel_url, confirm_url = _get_tracking_urls(token, request)
        destino_texto = remision.destino_display
        es_casa = remision.tipo_destino == 'casa'
        if es_casa:
            asunto = f'[COSFA CURE] AVISO: {est.nombre} debe ser recogido/a en el colegio'
            template_email = 'enfermeria/emails/remision_casa_acudiente.html'
        else:
            asunto = f'[COSFA CURE] REMISION MEDICA: {est.nombre} hacia {destino_texto}'
            template_email = 'enfermeria/emails/remision_acudiente.html'
        html   = render_to_string(template_email, {
            'estudiante': est, 'remision': remision,
            'pixel_url': pixel_url, 'confirm_url': confirm_url,
        })
        if es_casa:
            texto  = (
                f"Estimado/a {est.acudiente},\n\n"
                f"Le informamos que {est.nombre} ({est.grado}) ha sido dado/a de alta en enfermería "
                f"y está esperando ser recogido/a en el colegio.\n"
                f"Hora de salida de enfermería: {remision.hora_salida.strftime('%H:%M')}\n"
                f"Motivo: {remision.motivo}\n\n"
                f"Por favor acérquese al colegio a la mayor brevedad para recoger al/la estudiante.\n"
                f"— COSFA CURE | Colegio San Francisco de Asís"
            )
        else:
            texto  = (
                f"Estimado/a {est.acudiente},\n\n"
                f"URGENTE: {est.nombre} ha sido remitido/a a {destino_texto}.\n"
                f"Hora de salida: {remision.hora_salida.strftime('%H:%M')}\n"
                f"Motivo: {remision.motivo}\n"
                f"Acompañante: {remision.acompanante}\n\n"
                f"Por favor comuníquese con el colegio de inmediato.\n"
                f"— COSFA CURE | Colegio San Francisco de Asís"
            )
        msg = EmailMultiAlternatives(asunto, texto, settings.DEFAULT_FROM_EMAIL, [destinatario])
        msg.attach_alternative(html, 'text/html')
        msg.mixed_subtype = 'related'
        _adjuntar_logo(msg)
        msg.send()
        return True, destinatario
    except Exception as e:
        return False, str(e)


# ── CORREO 3: Alerta de inventario → enfermera ────────────────────────────────
def _correo_alerta_inventario(correo_enfermera, nombre_enfermera='Enfermera'):
    # Filtros en BD — no cargar todos los medicamentos en Python
    hoy     = datetime.date.today()
    en_30   = hoy + datetime.timedelta(days=30)
    vencidos    = list(Medicamento.objects.filter(fecha_vencimiento__lte=hoy))
    bajo_stock  = list(Medicamento.objects.filter(
        cantidad_actual__lte=django_models.F('cantidad_minima'),
        fecha_vencimiento__gt=hoy))
    prox_vencer = list(Medicamento.objects.filter(
        fecha_vencimiento__gt=hoy, fecha_vencimiento__lte=en_30))
    # Siempre enviar el correo — si no hay alertas, informa que todo está bien
    try:
        total  = len(vencidos) + len(bajo_stock) + len(prox_vencer)
        if total > 0:
            asunto = f'[COSFA CURE] Alerta inventario: {total} medicamento(s) requieren atencion'
        else:
            asunto = '[COSFA CURE] Inventario al día — todo en orden'
        html   = render_to_string('enfermeria/emails/alerta_inventario.html', {
            'nombre_enfermera': nombre_enfermera,
            'vencidos': vencidos,
            'bajo_stock': bajo_stock,
            'proximos_vencer': prox_vencer,
        })
        texto  = (
            f"Hola {nombre_enfermera},\n\n"
            f"Alertas en inventario:\n"
            f"- Vencidos: {len(vencidos)}\n"
            f"- Stock bajo: {len(bajo_stock)}\n"
            f"- Proximos a vencer: {len(prox_vencer)}\n\n"
            f"Ingrese al sistema para gestionar el inventario.\n"
            f"— COSFA CURE"
        )
        msg = EmailMultiAlternatives(asunto, texto, settings.DEFAULT_FROM_EMAIL, [correo_enfermera])
        msg.attach_alternative(html, 'text/html')
        msg.mixed_subtype = 'related'
        _adjuntar_logo(msg)
        msg.send()
        return True, correo_enfermera
    except Exception as e:
        return False, str(e)



def _enviar_notificacion_consulta(consulta, destinatarios):
    """Envía notificación HTML bonita de consulta a la lista de destinatarios dada."""
    if not destinatarios:
        return False
    est = consulta.estudiante
    asunto = f'[COSFA CURE] Atención médica: {est.nombre} — {consulta.get_motivo_display()}'
    # Usamos el mismo template HTML que ya existía para acudiente
    html = render_to_string('enfermeria/emails/consulta_acudiente.html', {
        'estudiante': est,
        'consulta': consulta,
    })
    texto = (
        f"Estimado/a,\n\n"
        f"{est.nombre} ({est.grado}) fue atendido/a en enfermería.\n"
        f"Motivo: {consulta.get_motivo_display()}\n"
        f"Tratamiento: {consulta.tratamiento}\n"
        f"Estado: {consulta.get_estado_display()}\n"
        f"Observaciones: {consulta.observaciones or 'Ninguna'}\n\n"
        f"— COSFA CURE | Sistema de Enfermería Escolar"
    )
    try:
        msg = EmailMultiAlternatives(asunto, texto, settings.DEFAULT_FROM_EMAIL, destinatarios)
        msg.attach_alternative(html, 'text/html')
        msg.mixed_subtype = 'related'
        _adjuntar_logo(msg)
        msg.send()
        if consulta.estado == 'regreso_clase':
            Consulta.objects.filter(pk=consulta.pk).update(notificacion_clase_enviada=True)
            consulta.notificacion_clase_enviada = True
        return True
    except Exception:
        return False


# Alias para compatibilidad con código de edición que llama _enviar_notificacion_clase
def _enviar_notificacion_clase(consulta):
    destinatarios = [e for e in [consulta.correo_padre_madre, consulta.correo_docente] if e]
    return _enviar_notificacion_consulta(consulta, destinatarios)


def _enviar_notificacion_generica(consulta, destinatarios):
    return _enviar_notificacion_consulta(consulta, destinatarios)



@login_required
def busqueda_global(request):
    q = request.GET.get('q', '').strip()
    resultados = {'estudiantes': [], 'consultas': [], 'medicamentos': []}
    if q:
        resultados['estudiantes'] = Estudiante.objects.filter(
            Q(nombre__icontains=q) | Q(numero_documento__icontains=q) | Q(grado__icontains=q))[:8]
        resultados['consultas'] = Consulta.objects.select_related('estudiante').filter(
            Q(estudiante__nombre__icontains=q) | Q(motivo__icontains=q) | Q(descripcion_sintomas__icontains=q))[:8]
        resultados['medicamentos'] = Medicamento.objects.filter(
            Q(nombre__icontains=q) | Q(descripcion__icontains=q))[:8]
    return render(request, 'enfermeria/busqueda.html', {'q': q, 'resultados': resultados})


# ── DASHBOARD ─────────────────────────────────────────────────────────────────
@login_required
def dashboard(request):
    # Verificar si hay un admin_setup pendiente (usuario salió sin poner el código)
    admin_setup_user = request.session.get('admin_setup_user')
    mostrar_admin_setup = bool(admin_setup_user)

    # Asegurar que la sesión tenga la foto de perfil actualizada
    if 'foto_perfil' not in request.session:
        try:
            perfil_dash = PerfilUsuario.objects.get(usuario=request.user)
            if perfil_dash.foto:
                request.session['foto_perfil'] = perfil_dash.foto.url
        except PerfilUsuario.DoesNotExist:
            pass

    hoy  = timezone.localdate()   # usa la zona horaria del proyecto (America/Bogota)
    hora = timezone.localtime().hour
    if hora < 12:
        saludo = 'Buenos días'
    elif hora < 18:
        saludo = 'Buenas tardes'
    else:
        saludo = 'Buenas noches'

    nombre_usuario = request.user.get_full_name() or request.user.username

    # ── Medicamentos: filtros en BD, no en Python ────────────────────────────
    hoy_med = datetime.date.today()
    en_30   = hoy_med + datetime.timedelta(days=30)
    medicamentos    = list(Medicamento.objects.all())          # necesario para total
    bajo_stock      = list(Medicamento.objects.filter(cantidad_actual__lte=django_models.F('cantidad_minima')))
    vencidos        = list(Medicamento.objects.filter(fecha_vencimiento__lte=hoy_med))
    proximos_vencer = list(Medicamento.objects.filter(
        fecha_vencimiento__gt=hoy_med, fecha_vencimiento__lte=en_30))
    consultas_hoy   = Consulta.objects.filter(fecha_hora__date=hoy).count()
    seguimientos_prox = Seguimiento.objects.filter(
        completado=False, fecha__gte=hoy, fecha__lte=hoy+datetime.timedelta(days=7))
    seguimientos_hoy = Seguimiento.objects.filter(
        completado=False, fecha=hoy).select_related('estudiante').order_by('estudiante__nombre')

    alertas_msg = []
    if consultas_hoy:
        alertas_msg.append(f'{consultas_hoy} consulta{"s" if consultas_hoy != 1 else ""} registrada{"s" if consultas_hoy != 1 else ""} hoy')
    if proximos_vencer:
        alertas_msg.append(f'{len(proximos_vencer)} medicamento{"s" if len(proximos_vencer) != 1 else ""} próximo{"s" if len(proximos_vencer) != 1 else ""} a vencer')
    if vencidos:
        alertas_msg.append(f'{len(vencidos)} medicamento{"s" if len(vencidos) != 1 else ""} vencido{"s" if len(vencidos) != 1 else ""}')
    if not alertas_msg:
        alertas_msg = ['todo en orden por ahora']

    # Calcular consultas por día — 1 sola query en lugar de 7
    from django.db.models.functions import TruncDate
    DIAS_ES = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom']
    desde_semana = hoy - datetime.timedelta(days=6)
    conteos_semana = {
        row['dia']: row['total']
        for row in Consulta.objects.filter(fecha_hora__date__gte=desde_semana)
            .annotate(dia=TruncDate('fecha_hora'))
            .values('dia')
            .annotate(total=Count('id'))
    }
    semana_data = []
    max_count = 0
    for i in range(6, -1, -1):
        dia_date = hoy - datetime.timedelta(days=i)
        count = conteos_semana.get(dia_date, 0)
        semana_data.append({
            'dia': DIAS_ES[dia_date.weekday()],
            'label': dia_date.strftime('%d/%m'),
            'count': count,
            'hoy': (i == 0),
            'max': 0,
            'pct': 0,
        })
        if count > max_count:
            max_count = count
    for d in semana_data:
        d['max'] = max_count
        d['pct'] = int((d['count'] / max_count) * 100) if max_count > 0 else 4

    context = {
        'saludo':             saludo,
        'nombre_usuario':     nombre_usuario,
        'alertas_msg':        ' y '.join(alertas_msg),
        'total_estudiantes':  Estudiante.objects.count(),
        'consultas_hoy':      consultas_hoy,
        'total_medicamentos': len(medicamentos),
        'bajo_stock':         bajo_stock,
        'proximos_vencer':    proximos_vencer,
        'vencidos':           vencidos,
        'consultas_recientes':Consulta.objects.select_related('estudiante').order_by('-fecha_hora')[:6],
        'alertas_medicas':    Estudiante.objects.filter(Q(alergias__gt='') | Q(condiciones_medicas__gt=''))[:4],
        'seguimientos_prox':  seguimientos_prox,
        'seguimientos_hoy':   seguimientos_hoy,
        'remisiones_pendientes': Remision.objects.filter(estado='pendiente').count(),
        'historial_reciente': HistorialCambio.objects.select_related('usuario').order_by('-fecha')[:25],
        'consultas_semana':   semana_data,
        'estudiantes_frecuentes': Estudiante.objects.annotate(
            n_consultas_recientes=Count(
                'consultas',
                filter=Q(consultas__fecha_hora__date__gte=datetime.date.today() - datetime.timedelta(days=30))
            )
        ).filter(n_consultas_recientes__gte=4).order_by('-n_consultas_recientes')[:5],
        'alertas_patron': _calcular_alertas_patron_dashboard(),
        'mostrar_admin_setup': mostrar_admin_setup,
        'admin_username': admin_setup_user or '',
    }
    return render(request, 'enfermeria/dashboard.html', context)


def _calcular_alertas_patron_dashboard():
    """
    Detecta patrones de salud repetidos en los últimos 21 días
    para mostrar alertas preventivas en el dashboard.
    Retorna lista de dicts con: estudiante, grado, motivo, veces, recomendacion, urgente, periodo_texto.
    """
    hace_21_dias = timezone.now() - datetime.timedelta(days=21)
    from django.db.models import Count as _Count, Min as _Min, Max as _Max

    # Agrupar por (estudiante, motivo) con >= 3 consultas en 21 días
    patrones = (
        Consulta.objects
        .filter(fecha_hora__gte=hace_21_dias)
        .values('estudiante__id', 'estudiante__nombre', 'estudiante__grado', 'motivo')
        .annotate(total=_Count('id'), primera=_Min('fecha_hora'), ultima=_Max('fecha_hora'))
        .filter(total__gte=3)
        .order_by('-total')[:8]
    )

    alertas = []
    motivos_display = dict(Consulta.MOTIVO_CHOICES)
    for p in patrones:
        motivo_key = p['motivo']
        veces      = p['total']

        # Calcular período real entre primera y última consulta del patrón
        primera = p['primera']
        ultima  = p['ultima']
        if primera and ultima:
            diff = (ultima.date() - primera.date()).days
            if diff == 0:
                periodo_texto = 'el mismo día'
            elif diff == 1:
                periodo_texto = '2 días'
            elif diff < 7:
                periodo_texto = f'{diff + 1} días'
            elif diff < 14:
                periodo_texto = '1 semana'
            elif diff < 21:
                periodo_texto = '2 semanas'
            else:
                periodo_texto = '3 semanas'
        else:
            periodo_texto = '21 días'

        alertas.append({
            'estudiante_pk': p['estudiante__id'],
            'estudiante':    p['estudiante__nombre'],
            'grado':         p['estudiante__grado'],
            'motivo':        motivos_display.get(motivo_key, motivo_key),
            'motivo_key':    motivo_key,
            'veces':         veces,
            'urgente':       veces >= 4,
            'recomendacion': _recomendacion_patron(motivo_key, veces),
            'periodo_texto': periodo_texto,
        })
    return alertas


# ── ESTUDIANTES ───────────────────────────────────────────────────────────────
@login_required
def lista_estudiantes(request):
    from django.core.paginator import Paginator
    q        = request.GET.get('q', '')
    f_grado  = request.GET.get('grado', '')
    f_sexo   = request.GET.get('sexo', '')
    f_alerta = request.GET.get('alerta', '')
    f_estado = request.GET.get('estado_academico', 'activo')  # por defecto sólo activos
    f_eps    = request.GET.get('eps', '')
    f_condicion = request.GET.get('condicion', '')
    qs = Estudiante.objects.all()
    if q:
        qs = qs.filter(Q(nombre__icontains=q) | Q(numero_documento__icontains=q) | Q(grado__icontains=q))
    if f_grado:
        qs = qs.filter(grado=f_grado)
    if f_sexo:
        qs = qs.filter(sexo=f_sexo)
    if f_alerta == 'si':
        qs = qs.filter(
            Q(alergias__isnull=False) & ~Q(alergias='') | Q(condiciones_medicas__isnull=False) & ~Q(condiciones_medicas='')
        )
    if f_estado:
        qs = qs.filter(estado_academico=f_estado)
    if f_eps:
        qs = qs.filter(eps__icontains=f_eps)
    if f_condicion:
        qs = qs.filter(condiciones_medicas__icontains=f_condicion)
    # Stats globales
    todos = Estudiante.objects.all()
    total_estudiantes = todos.count()
    con_alertas = todos.filter(
        Q(alergias__isnull=False) & ~Q(alergias='') | Q(condiciones_medicas__isnull=False) & ~Q(condiciones_medicas='')
    ).count()
    hay_filtros = any([q, f_grado, f_sexo, f_alerta, f_eps, f_condicion, f_estado not in ('', 'activo')])
    paginator = Paginator(qs, 20)
    page_obj  = paginator.get_page(request.GET.get('page'))
    # Grados dinámicos desde BD
    grados_db = list(GradoEscolar.objects.filter(activo=True).order_by('orden','nombre').values_list('nombre','nombre'))
    # EPS únicas para sugerencias
    eps_lista = list(Estudiante.objects.exclude(eps='').values_list('eps', flat=True).distinct().order_by('eps')[:50])
    return render(request, 'enfermeria/estudiantes_lista.html', {
        'estudiantes': page_obj, 'query': q, 'page_obj': page_obj,
        'f_grado': f_grado, 'f_sexo': f_sexo, 'f_alerta': f_alerta,
        'f_estado_academico': f_estado,
        'f_eps': f_eps, 'f_condicion': f_condicion,
        'hay_filtros': hay_filtros,
        'total_estudiantes': total_estudiantes,
        'con_alertas': con_alertas,
        'grado_choices': grados_db or Estudiante.GRADO_CHOICES,
        'sexo_choices': Estudiante.SEXO_CHOICES,
        'estado_academico_choices': Estudiante.ESTADO_ACADEMICO_CHOICES,
        'grados_lista': GradoEscolar.objects.order_by('orden','nombre'),
        'eps_lista': eps_lista,
    })


@admin_required
def nuevo_estudiante(request):
    form = EstudianteForm(request.POST or None, request.FILES or None)
    if form.is_valid():
        e = form.save()
        _log(request, 'crear', 'Estudiante', f'Registrado: {e.nombre} ({e.grado})')
        messages.success(request, f'Estudiante {e.nombre} registrado.')
        return redirect('historial_estudiante', pk=e.pk)
    return render(request, 'enfermeria/estudiante_form.html', {'form':form,'titulo':'Nuevo Estudiante'})


@admin_required
def editar_estudiante(request, pk):
    est  = get_object_or_404(Estudiante, pk=pk)
    form = EstudianteForm(request.POST or None, request.FILES or None, instance=est)
    if form.is_valid():
        form.save()
        _log(request, 'editar', 'Estudiante', f'Editado: {est.nombre}')
        messages.success(request, 'Datos actualizados.')
        return redirect('historial_estudiante', pk=pk)
    return render(request, 'enfermeria/estudiante_form.html', {'form':form,'titulo':f'Editar: {est.nombre}','estudiante':est})


@login_required
def historial_estudiante(request, pk):
    est          = get_object_or_404(Estudiante, pk=pk)
    consultas    = est.consultas.all()
    remisiones   = est.remisiones.prefetch_related('consentimiento').all()
    seguimientos = est.seguimientos.all()
    # Consultas con estado de traslado/salida — solo remisiones reales, NO regreso a clase
    consultas_traslado = consultas.filter(
        estado__in=('remitido_hospital', 'remitido_casa')
    ).order_by('-fecha_hora')
    por_motivo = list(consultas.values('motivo').annotate(n=Count('id')).order_by('-n')[:5])
    for item in por_motivo:
        item['label'] = dict(Consulta.MOTIVO_CHOICES).get(item['motivo'], item['motivo'])
    vitales_qs = consultas.filter(
        peso__isnull=False
    ).order_by('fecha_hora').values('fecha_hora', 'peso', 'talla')
    vitales_list   = list(vitales_qs)
    vitales_labels = json.dumps([timezone.localtime(v['fecha_hora']).strftime('%d/%m/%Y') for v in vitales_list])
    vitales_peso   = json.dumps([float(v['peso']) for v in vitales_list])
    vitales_talla  = json.dumps([float(v['talla']) if v['talla'] else None for v in vitales_list])
    # Calcular IMC: peso(kg) / (talla(m))^2 — solo cuando ambos datos estén disponibles
    def calc_imc(peso, talla):
        try:
            p = float(peso)
            t = float(talla) / 100.0  # cm → m
            if t > 0:
                return round(p / (t * t), 1)
        except (TypeError, ValueError, ZeroDivisionError):
            pass
        return None
    vitales_imc = json.dumps([calc_imc(v['peso'], v['talla']) for v in vitales_list])
    # IMC e interpretación del último registro disponible
    ultimo_imc = None
    ultimo_imc_label = ''
    ultimo_imc_color = '#64748b'
    for v in reversed(vitales_list):
        val = calc_imc(v['peso'], v['talla'])
        if val is not None:
            ultimo_imc = val
            if val < 18.5:
                ultimo_imc_label = 'Bajo peso'
                ultimo_imc_color = '#3b82f6'
            elif val < 25:
                ultimo_imc_label = 'Normal'
                ultimo_imc_color = '#22c55e'
            elif val < 30:
                ultimo_imc_label = 'Sobrepeso'
                ultimo_imc_color = '#f59e0b'
            else:
                ultimo_imc_label = 'Obesidad'
                ultimo_imc_color = '#ef4444'
            break
    # Datos para el calendario de remisiones
    # Formato: {"YYYY-MM-DD": [{"tipo": ..., "destino": ..., "estado": ...}, ...]}
    cal_data = {}
    for r in remisiones:
        dia = timezone.localtime(r.fecha_hora).strftime('%Y-%m-%d')
        destino = 'Casa del estudiante' if r.tipo_destino == 'casa' else (r.hospital_destino or 'Hospital')
        cal_data.setdefault(dia, []).append({
            'tipo': r.tipo_destino,
            'destino': destino,
            'estado': r.get_estado_display(),
            'pk': r.pk,
        })
    for c in consultas_traslado:
        dia = timezone.localtime(c.fecha_hora).strftime('%Y-%m-%d')
        if c.estado == 'remitido_casa':
            tipo_cal = 'casa'
            destino_cal = 'Casa del estudiante'
        else:
            tipo_cal = 'hospital'
            destino_cal = 'Hospital / Centro médico'
        cal_data.setdefault(dia, []).append({
            'tipo': tipo_cal,
            'destino': destino_cal,
            'estado': c.get_estado_display(),
            'pk': None,
        })
    from django.core.paginator import Paginator
    pag_consultas = Paginator(consultas.order_by('-fecha_hora'), 15)
    page_consultas = pag_consultas.get_page(request.GET.get('page'))
    # Datos para el calendario de consultas
    cal_consultas = {}
    for c in consultas:
        dia = timezone.localtime(c.fecha_hora).strftime('%Y-%m-%d')
        cal_consultas.setdefault(dia, []).append({
            'motivo': c.get_motivo_display(),
            'estado': c.get_estado_display(),
            'hora': timezone.localtime(c.fecha_hora).strftime('%H:%M'),
            'pk': c.pk,
        })
    return render(request, 'enfermeria/historial_estudiante.html', {
        'estudiante':est,'consultas':page_consultas,'remisiones':remisiones,'consultas_traslado':consultas_traslado,
        'seguimientos':seguimientos,'por_motivo':por_motivo,
        'page_obj': page_consultas,
        'motivos_labels': json.dumps([x['label'] for x in por_motivo]),
        'motivos_data':   json.dumps([x['n']     for x in por_motivo]),
        'vitales_labels': vitales_labels,
        'vitales_peso':   vitales_peso,
        'vitales_talla':  vitales_talla,
        'vitales_imc':    vitales_imc,
        'tiene_vitales':  bool(vitales_list),
        'ultimo_imc':     ultimo_imc,
        'ultimo_imc_label': ultimo_imc_label,
        'ultimo_imc_color': ultimo_imc_color,
        'cal_remisiones_json': json.dumps(cal_data),
        'cal_consultas_json': json.dumps(cal_consultas),
    })


@admin_required
def eliminar_estudiante(request, pk):
    est = get_object_or_404(Estudiante, pk=pk)
    if request.method == 'POST':
        nom = est.nombre
        _log(request, 'eliminar', 'Estudiante', f'Eliminado: {nom}')
        est.delete()
        messages.success(request, f'Estudiante {nom} eliminado.')
        return redirect('lista_estudiantes')
    return render(request, 'enfermeria/confirmar_eliminar.html', {'objeto':est})


@login_required
def carnet_pdf(request, pk):
    return render(request, 'enfermeria/carnet_pdf.html', {'estudiante': get_object_or_404(Estudiante, pk=pk)})


# ── CONSULTAS ─────────────────────────────────────────────────────────────────
@login_required
def lista_consultas(request):
    from django.core.paginator import Paginator
    from django.db.models import Count
    q        = request.GET.get('q', '')
    f_estado = request.GET.get('estado', '')
    f_grado  = request.GET.get('grado', '')
    f_motivo = request.GET.get('motivo', '')
    f_fecha  = request.GET.get('fecha', '')

    qs = Consulta.objects.select_related('estudiante').order_by('-fecha_hora')
    if q:
        qs = qs.filter(Q(estudiante__nombre__icontains=q)|Q(motivo__icontains=q))
    if f_estado:
        qs = qs.filter(estado=f_estado)
    if f_grado:
        qs = qs.filter(estudiante__grado=f_grado)
    if f_motivo:
        qs = qs.filter(motivo=f_motivo)
    if f_fecha:
        try:
            from datetime import datetime as _dt
            qs = qs.filter(fecha_hora__date=_dt.strptime(f_fecha, '%Y-%m-%d').date())
        except ValueError:
            pass

    hoy = timezone.now().date()
    total_mes  = Consulta.objects.filter(fecha_hora__year=hoy.year, fecha_hora__month=hoy.month).count()
    total_hoy  = Consulta.objects.filter(fecha_hora__date=hoy).count()
    remitidas  = Consulta.objects.filter(estado__in=['remitido_casa','remitido_hospital']).count()
    motivo_top = (Consulta.objects.filter(fecha_hora__year=hoy.year, fecha_hora__month=hoy.month)
                  .values('motivo').annotate(c=Count('motivo')).order_by('-c').first())
    motivos_dict = dict(Consulta.MOTIVO_CHOICES)
    motivo_top_label = motivos_dict.get(motivo_top['motivo'], '') if motivo_top else '—'

    paginator = Paginator(qs, 20)
    page_obj  = paginator.get_page(request.GET.get('page'))
    return render(request, 'enfermeria/consultas_lista.html', {
        'consultas': page_obj, 'query': q, 'page_obj': page_obj,
        'f_estado': f_estado, 'f_grado': f_grado, 'f_motivo': f_motivo, 'f_fecha': f_fecha,
        'total_mes': total_mes, 'total_hoy': total_hoy,
        'remitidas': remitidas, 'motivo_top_label': motivo_top_label,
        'grados': Estudiante.GRADO_CHOICES,
        'motivo_choices': Consulta.MOTIVO_CHOICES,
        'estado_choices': Consulta.ESTADO_CHOICES,
        'hay_filtros': any([q, f_estado, f_grado, f_motivo, f_fecha]),
        'today_str': hoy.isoformat(),
    })


def _meds_json():
    return json.dumps({
        str(m.pk): {
            'stock': m.cantidad_actual,
            'unidad': m.unidad,
            'nombre': m.nombre,
            'imagen': m.imagen.url if m.imagen else None,
            'categoria': m.categoria,
        }
        for m in Medicamento.objects.all()
    })


@admin_required
def nueva_consulta(request, estudiante_pk=None):
    initial = {}
    if estudiante_pk:
        est = get_object_or_404(Estudiante, pk=estudiante_pk)
        initial['estudiante'] = est
        # Pre-llenar correo del acudiente si existe
        if est.correo_acudiente:
            initial['correo_padre_madre'] = est.correo_acudiente
    form = ConsultaForm(request.POST or None, initial=initial)
    if form.is_valid():
        c = form.save(commit=False)
        c.save()
        # Procesar múltiples medicamentos
        med_ids   = request.POST.getlist('med_ids[]')
        med_cants = request.POST.getlist('med_cants[]')
        med_dosis = request.POST.getlist('med_dosis[]')
        nombres = []
        for i, mid in enumerate(med_ids):
            if not mid:
                continue
            try:
                med  = Medicamento.objects.get(pk=mid)
                cant = max(1, int(med_cants[i]) if i < len(med_cants) and med_cants[i] else 1)
                dos  = med_dosis[i] if i < len(med_dosis) else ''
                # ── VALIDACIÓN DE STOCK ───────────────────────────────────────
                if med.cantidad_actual < cant:
                    messages.error(
                        request,
                        f'❌ Stock insuficiente para {med.nombre}: '
                        f'disponible {med.cantidad_actual} {med.unidad}, solicitado {cant}.'
                    )
                    # Revertir medicamentos ya guardados en este ciclo
                    for mc_rev in c.medicamentos_usados.all():
                        if mc_rev.medicamento:
                            mc_rev.medicamento.cantidad_actual += mc_rev.cantidad
                            mc_rev.medicamento.save()
                    c.medicamentos_usados.all().delete()
                    c.delete()
                    return render(request, 'enfermeria/consulta_form.html', {
                        'form': ConsultaForm(request.POST, initial=initial),
                        'medicamentos_json': _meds_json(),
                    })
                # ─────────────────────────────────────────────────────────────
                MedicamentoConsulta.objects.create(consulta=c, medicamento=med, cantidad=cant, dosis=dos)
                med.cantidad_actual -= cant
                med.save()
                MovimientoInventario.objects.create(medicamento=med, tipo='salida', cantidad=cant,
                    motivo=f'Consulta #{c.pk} – {c.estudiante.nombre}')
                nombres.append(med.nombre)
                if med.stock_bajo:
                    messages.warning(request, f'⚠️ Stock bajo: {med.nombre} ({med.cantidad_actual} {med.unidad} restantes)')
            except (Medicamento.DoesNotExist, ValueError):
                continue
        c.medicamento_suministrado = ', '.join(nombres)
        c.save()

        # Enviar correos según el estado
        if c.estado == 'regreso_clase':
            # Notificación de regreso a clase (correos del formulario)
            if c.correo_padre_madre or c.correo_docente:
                enviado = _enviar_notificacion_clase(c)
                if enviado:
                    messages.info(request, '📧 Notificación de regreso a clase enviada por correo.')
                else:
                    messages.warning(request, '⚠️ No se pudo enviar la notificación por correo. Verifique la configuración.')
        elif c.estado == 'atendido':
            # Para atendido: enviar a correos del formulario si los llenó, o al acudiente registrado
            destinatarios_form = [e for e in [c.correo_padre_madre, c.correo_docente] if e]
            if destinatarios_form:
                _enviar_notificacion_generica(c, destinatarios_form)
                messages.info(request, f'📧 Notificación enviada por correo.')
            elif c.estudiante.correo_acudiente:
                ok, info = _correo_consulta_acudiente(c, request=request)
                if ok:
                    messages.info(request, f'📧 Resumen de consulta enviado al acudiente ({info}).')
        else:
            # remitido_casa / remitido_hospital: usar correos del formulario si los puso
            destinatarios_form = [e for e in [c.correo_padre_madre, c.correo_docente] if e]
            if destinatarios_form:
                _enviar_notificacion_generica(c, destinatarios_form)

        # Crear remisión automáticamente SOLO para remitido_hospital o remitido_casa
        if c.estado in ('remitido_hospital', 'remitido_casa'):
            import datetime as _dt
            tipo = 'hospital' if c.estado == 'remitido_hospital' else 'casa'
            hosp = request.POST.get('hospital_destino_consulta', '').strip() or (
                '' if tipo == 'casa' else 'Hospital / Centro médico'
            )
            acomp = request.POST.get('acompanante_consulta', '').strip() or c.estudiante.acudiente or 'Por definir'
            hora_real = _dt.datetime.now().time()
            r_auto = Remision.objects.create(
                estudiante=c.estudiante,
                tipo_destino=tipo,
                hospital_destino=hosp,
                eps=c.estudiante.eps or '',
                motivo=c.descripcion_sintomas or c.get_motivo_display(),
                acompanante=acomp,
                estado='pendiente',
                hora_salida=hora_real,
                consulta_origen=c,
            )
            # Enviar correo urgente de remisión al acudiente
            ok_rem, info_rem = _correo_remision_acudiente(r_auto, request=request)
            if ok_rem:
                messages.info(request, f'📧 Alerta de remisión enviada al acudiente ({info_rem}).')
            messages.info(request, f'📋 Remisión creada automáticamente en el módulo de Remisiones.')

        _log(request, 'crear', 'Consulta', f'Nueva consulta: {c.estudiante.nombre} – {c.get_motivo_display()}')
        messages.success(request, 'Consulta registrada correctamente.')
        return redirect(f'/consultas/{c.pk}/?ver_pdf=1')
    return render(request, 'enfermeria/consulta_form.html', {'form':form,'medicamentos_json':_meds_json()})


@login_required
def detalle_consulta(request, pk):
    return render(request, 'enfermeria/detalle_consulta.html', {'consulta': get_object_or_404(Consulta, pk=pk)})


@admin_required
def eliminar_consulta(request, pk):
    consulta = get_object_or_404(Consulta, pk=pk)
    if request.method == 'POST':
        # Devolver medicamentos al inventario antes de eliminar
        for mc in consulta.medicamentos_usados.all():
            if mc.medicamento:
                mc.medicamento.cantidad_actual += mc.cantidad
                mc.medicamento.save()
                MovimientoInventario.objects.create(
                    medicamento=mc.medicamento, tipo='entrada', cantidad=mc.cantidad,
                    motivo=f'Eliminación consulta #{consulta.pk} – {consulta.estudiante.nombre}'
                )
        # Eliminar remisiones creadas automáticamente desde esta consulta
        remisiones_auto = consulta.remisiones_auto.all()
        n_rem = remisiones_auto.count()
        remisiones_auto.delete()
        desc = f'Eliminada consulta #{consulta.pk}: {consulta.estudiante.nombre} – {consulta.get_motivo_display()}'
        if n_rem:
            desc += f' (+ {n_rem} remisión automática eliminada)'
        _log(request, 'eliminar', 'Consulta', desc)
        consulta.delete()
        if n_rem:
            messages.info(request, f'Consulta y su remisión asociada eliminadas correctamente.')
        else:
            messages.success(request, 'Consulta eliminada correctamente.')
        return redirect('lista_consultas')
    # Verificar si tiene remisión automática para mostrar aviso
    tiene_remision_auto = consulta.remisiones_auto.exists()
    return render(request, 'enfermeria/detalle_consulta.html', {
        'consulta': consulta,
        'remision_automatica': tiene_remision_auto,
    })


@admin_required
def editar_consulta(request, pk):
    consulta = get_object_or_404(Consulta, pk=pk)
    estado_original = consulta.estado  # guardar estado antes de editar
    form = ConsultaForm(request.POST or None, instance=consulta)
    if form.is_valid():
        c = form.save(commit=False)
        for mc in consulta.medicamentos_usados.all():
            if mc.medicamento:
                mc.medicamento.cantidad_actual += mc.cantidad
                mc.medicamento.save()
                MovimientoInventario.objects.create(medicamento=mc.medicamento, tipo='entrada',
                    cantidad=mc.cantidad, motivo=f'Corrección edición consulta #{consulta.pk}')
        consulta.medicamentos_usados.all().delete()
        c.save()
        med_ids   = request.POST.getlist('med_ids[]')
        med_cants = request.POST.getlist('med_cants[]')
        med_dosis = request.POST.getlist('med_dosis[]')
        nombres = []
        for i, mid in enumerate(med_ids):
            if not mid:
                continue
            try:
                med  = Medicamento.objects.get(pk=mid)
                cant = max(1, int(med_cants[i]) if i < len(med_cants) and med_cants[i] else 1)
                dos  = med_dosis[i] if i < len(med_dosis) else ''
                # ── VALIDACIÓN DE STOCK (el stock ya fue devuelto arriba) ─────
                if med.cantidad_actual < cant:
                    messages.error(
                        request,
                        f'❌ Stock insuficiente para {med.nombre}: '
                        f'disponible {med.cantidad_actual} {med.unidad}, solicitado {cant}.'
                    )
                    # Revertir lo que ya se descontó en este ciclo parcial
                    for mc_rev in c.medicamentos_usados.all():
                        if mc_rev.medicamento:
                            mc_rev.medicamento.cantidad_actual += mc_rev.cantidad
                            mc_rev.medicamento.save()
                    c.medicamentos_usados.all().delete()
                    return render(request, 'enfermeria/consulta_form.html', {
                        'form': form, 'medicamentos_json': _meds_json(),
                        'editar': True, 'consulta': consulta,
                    })
                # ─────────────────────────────────────────────────────────────
                MedicamentoConsulta.objects.create(consulta=c, medicamento=med, cantidad=cant, dosis=dos)
                med.cantidad_actual -= cant
                med.save()
                MovimientoInventario.objects.create(medicamento=med, tipo='salida', cantidad=cant,
                    motivo=f'Edición consulta #{c.pk} – {c.estudiante.nombre}')
                nombres.append(med.nombre)
                if med.stock_bajo:
                    messages.warning(request, f'⚠️ Stock bajo: {med.nombre} ({med.cantidad_actual} {med.unidad} restantes)')
            except (Medicamento.DoesNotExist, ValueError):
                continue
        c.medicamento_suministrado = ', '.join(nombres)
        c.save()

        # Solo enviar notificación si el estado CAMBIÓ
        if c.estado == 'regreso_clase' and estado_original != 'regreso_clase':
            if c.correo_padre_madre or c.correo_docente:
                enviado = _enviar_notificacion_clase(c)
                if enviado:
                    messages.info(request, '📧 Notificación de regreso a clase enviada por correo.')
        elif c.estado == 'atendido' and estado_original != 'atendido':
            destinatarios_form = [e for e in [c.correo_padre_madre, c.correo_docente] if e]
            if destinatarios_form:
                _enviar_notificacion_generica(c, destinatarios_form)
                messages.info(request, '📧 Notificación enviada por correo.')

        # Crear remisión automática SOLO para remitido_hospital / remitido_casa
        estados_remision = ('remitido_hospital', 'remitido_casa')
        if c.estado in estados_remision and estado_original not in estados_remision:
            import datetime as _dt
            tipo = 'hospital' if c.estado == 'remitido_hospital' else 'casa'
            hosp = request.POST.get('hospital_destino_consulta', '').strip() or (
                '' if tipo == 'casa' else 'Hospital / Centro médico'
            )
            acomp = request.POST.get('acompanante_consulta', '').strip() or c.estudiante.acudiente or 'Por definir'
            r_auto = Remision.objects.create(
                estudiante=c.estudiante,
                tipo_destino=tipo,
                hospital_destino=hosp,
                eps=c.estudiante.eps or '',
                motivo=c.descripcion_sintomas or c.get_motivo_display(),
                acompanante=acomp,
                estado='pendiente',
                hora_salida=_dt.datetime.now().time(),
                consulta_origen=c,
            )
            ok_rem, info_rem = _correo_remision_acudiente(r_auto, request=request)
            if ok_rem:
                messages.info(request, f'📧 Alerta de remisión enviada al acudiente ({info_rem}).')
            messages.info(request, '📋 Remisión creada automáticamente al cambiar el estado.')

        _log(request, 'editar', 'Consulta', f'Editada consulta #{c.pk} – {c.estudiante.nombre}')
        messages.success(request, 'Consulta actualizada.')
        return redirect('detalle_consulta', pk=c.pk)
    return render(request, 'enfermeria/consulta_form.html', {
        'form':form,'medicamentos_json':_meds_json(),'editar':True,'consulta':consulta})



# ── DOCENTES (BASE DE DATOS) ──────────────────────────────────────────────────
@login_required
def lista_docentes(request):
    from django.core.paginator import Paginator
    q       = request.GET.get('q','').strip()
    f_area  = request.GET.get('area','')
    f_activo = request.GET.get('activo','')
    qs = Docente.objects.all()
    if q:
        qs = qs.filter(Q(nombre__icontains=q) | Q(cedula__icontains=q) | Q(area__icontains=q) | Q(grados_asignados__icontains=q))
    if f_area:
        qs = qs.filter(area=f_area)
    if f_activo == 'si':
        qs = qs.filter(activo=True)
    elif f_activo == 'no':
        qs = qs.filter(activo=False)
    total        = Docente.objects.count()
    total_activos= Docente.objects.filter(activo=True).count()
    con_alertas  = Docente.objects.filter(
        Q(alergias__isnull=False) & ~Q(alergias='') | Q(condiciones_medicas__isnull=False) & ~Q(condiciones_medicas='')
    ).count()
    paginator = Paginator(qs, 20)
    page_obj  = paginator.get_page(request.GET.get('page'))
    return render(request, 'enfermeria/docentes_lista.html', {
        'docentes': page_obj, 'query': q, 'page_obj': page_obj,
        'f_area': f_area, 'f_activo': f_activo,
        'total': total, 'total_activos': total_activos, 'con_alertas': con_alertas,
        'area_choices': Docente.AREA_CHOICES,
    })


@admin_required
def nuevo_docente(request):
    form = DocenteForm(request.POST or None, request.FILES or None)
    if form.is_valid():
        d = form.save()
        _log(request, 'crear', 'Docente', f'Registrado: {d.nombre}')
        messages.success(request, f'Docente {d.nombre} registrado correctamente.')
        return redirect('historial_docente', pk=d.pk)
    return render(request, 'enfermeria/docente_form.html', {'form': form, 'titulo': 'Nuevo Docente'})


@admin_required
def editar_docente(request, pk):
    doc  = get_object_or_404(Docente, pk=pk)
    form = DocenteForm(request.POST or None, request.FILES or None, instance=doc)
    if form.is_valid():
        form.save()
        _log(request, 'editar', 'Docente', f'Editado: {doc.nombre}')
        messages.success(request, 'Datos del docente actualizados.')
        return redirect('historial_docente', pk=pk)
    return render(request, 'enfermeria/docente_form.html', {
        'form': form, 'titulo': f'Editar: {doc.nombre}', 'docente': doc
    })


@login_required
def historial_docente(request, pk):
    doc       = get_object_or_404(Docente, pk=pk)
    consultas = doc.consultas_docente.all()
    por_motivo = list(consultas.values('motivo').annotate(n=Count('id')).order_by('-n')[:5])
    for item in por_motivo:
        item['label'] = dict(ConsultaDocente.MOTIVO_CHOICES).get(item['motivo'], item['motivo'])
    from django.core.paginator import Paginator
    pag_doc = Paginator(consultas.order_by('-fecha_hora'), 5)
    page_consultas_doc = pag_doc.get_page(request.GET.get('page'))
    return render(request, 'enfermeria/historial_docente.html', {
        'docente': doc,
        'consultas': page_consultas_doc,
        'page_obj': page_consultas_doc,
        'por_motivo': por_motivo,
        'motivos_labels': json.dumps([x['label'] for x in por_motivo]),
        'motivos_data':   json.dumps([x['n']     for x in por_motivo]),
    })


@admin_required
def eliminar_docente(request, pk):
    doc = get_object_or_404(Docente, pk=pk)
    if request.method == 'POST':
        nom = doc.nombre
        _log(request, 'eliminar', 'Docente', f'Eliminado: {nom}')
        doc.delete()
        messages.success(request, f'Docente {nom} eliminado.')
        return redirect('lista_docentes')
    return render(request, 'enfermeria/confirmar_eliminar.html', {
        'objeto': doc,
        'cancelar_url': 'lista_docentes',
    })


# ── CONSULTAS DOCENTES ────────────────────────────────────────────────────────
@login_required
def lista_consultas_docentes(request):
    from django.core.paginator import Paginator
    qs = ConsultaDocente.objects.all()
    q = request.GET.get('q', '').strip()
    if q:
        qs = qs.filter(
            django_models.Q(nombre_completo__icontains=q) |
            django_models.Q(cedula__icontains=q) |
            django_models.Q(area_grado__icontains=q)
        )
    paginator = Paginator(qs, 20)
    page = request.GET.get('page')
    consultas = paginator.get_page(page)
    return render(request, 'enfermeria/consultas_docentes_lista.html', {
        'consultas': consultas, 'q': q,
    })


@admin_required
def nueva_consulta_docente(request, docente_pk=None):
    import datetime as _dt
    initial = {'hora_atencion': _dt.datetime.now().strftime('%H:%M')}
    if docente_pk:
        initial['docente'] = docente_pk
    form = ConsultaDocenteForm(request.POST or None, initial=initial)
    if form.is_valid():
        c = form.save(commit=False)
        # Sincronizar campos de texto con el docente FK
        if c.docente:
            c.nombre_completo = c.docente.nombre
            c.cedula          = c.docente.cedula
            c.area_grado      = c.docente.get_area_display()
            c.eps             = c.docente.eps
            c.tipo            = c.docente.tipo or 'Docente'
        # Procesar insumos
        med_ids   = request.POST.getlist('med_ids[]')
        med_cants = request.POST.getlist('med_cants[]')
        c.save()
        nombres = []
        for i, mid in enumerate(med_ids):
            if not mid:
                continue
            try:
                med  = Medicamento.objects.get(pk=mid)
                cant = max(1, int(med_cants[i]) if i < len(med_cants) and med_cants[i] else 1)
                if med.cantidad_actual < cant:
                    messages.error(request, f'❌ Stock insuficiente para {med.nombre}.')
                    c.delete()
                    return render(request, 'enfermeria/consulta_docente_form.html', {
                        'form': ConsultaDocenteForm(request.POST, initial=initial),
                        'medicamentos_json': _meds_json(),
                    })
                MovimientoInventario.objects.create(medicamento=med, tipo='salida', cantidad=cant,
                    motivo=f'Consulta docente #{c.pk} – {c.nombre_completo}')
                med.cantidad_actual -= cant
                med.save()
                nombres.append(med.nombre)
                if med.stock_bajo:
                    messages.warning(request, f'⚠️ Stock bajo: {med.nombre} ({med.cantidad_actual} {med.unidad} restantes)')
            except (Medicamento.DoesNotExist, ValueError):
                continue
        c.medicamento_suministrado = ', '.join(nombres)
        c.save()
        _log(request, 'crear', 'ConsultaDocente', f'Nueva consulta docente: {c.nombre_completo} – {c.get_motivo_display()}')
        messages.success(request, 'Consulta de docente registrada correctamente.')
        return redirect('historial_docente', pk=c.docente.pk) if c.docente else redirect('lista_consultas_docentes')
    doc = Docente.objects.get(pk=docente_pk) if docente_pk else None
    return render(request, 'enfermeria/consulta_docente_form.html', {
        'form': form, 'medicamentos_json': _meds_json(), 'docente': doc,
    })


@login_required
def detalle_consulta_docente(request, pk):
    consulta = get_object_or_404(ConsultaDocente, pk=pk)
    return render(request, 'enfermeria/detalle_consulta_docente.html', {'consulta': consulta})


@admin_required
def editar_consulta_docente(request, pk):
    consulta = get_object_or_404(ConsultaDocente, pk=pk)
    form = ConsultaDocenteForm(request.POST or None, instance=consulta)
    if form.is_valid():
        c = form.save(commit=False)
        c.tipo = 'Docente'
        # ── PASO 1: Devolver stock de los medicamentos anteriores ─────────────
        # Sin este paso, cada edición descuenta stock nuevo sin devolver el
        # stock del medicamento que se usó originalmente (bug de stock doble).
        meds_anteriores = {}
        for linea in (consulta.medicamento_suministrado or '').split(','):
            nombre = linea.strip()
            if nombre:
                meds_anteriores[nombre] = meds_anteriores.get(nombre, 0) + 1

        movs_anteriores = MovimientoInventario.objects.filter(
            motivo__startswith=f'Edición consulta docente #{consulta.pk}'
        ).order_by('-fecha')

        for mov in movs_anteriores:
            if mov.tipo == 'salida' and mov.medicamento:
                mov.medicamento.cantidad_actual += mov.cantidad
                mov.medicamento.save()
                MovimientoInventario.objects.create(
                    medicamento=mov.medicamento,
                    tipo='entrada',
                    cantidad=mov.cantidad,
                    motivo=f'Corrección edición consulta docente #{consulta.pk}'
                )
        # ─────────────────────────────────────────────────────────────────────

        # ── PASO 2: Re-procesar medicamentos nuevos ───────────────────────────
        med_ids   = request.POST.getlist('med_ids[]')
        med_cants = request.POST.getlist('med_cants[]')
        c.save()
        nombres = []
        for i, mid in enumerate(med_ids):
            if not mid:
                continue
            try:
                med  = Medicamento.objects.get(pk=mid)
                cant = max(1, int(med_cants[i]) if i < len(med_cants) and med_cants[i] else 1)
                if med.cantidad_actual < cant:
                    messages.error(request, f'❌ Stock insuficiente para {med.nombre}: '
                                            f'disponible {med.cantidad_actual}, solicitado {cant}.')
                    continue
                MovimientoInventario.objects.create(medicamento=med, tipo='salida', cantidad=cant,
                    motivo=f'Edición consulta docente #{c.pk}')
                med.cantidad_actual -= cant
                med.save()
                if med.stock_bajo:
                    messages.warning(request, f'⚠️ Stock bajo: {med.nombre} ({med.cantidad_actual} restantes)')
                if med.nombre not in nombres:
                    nombres.append(med.nombre)
            except (Medicamento.DoesNotExist, ValueError):
                continue
        c.medicamento_suministrado = ', '.join(nombres)
        c.save()
        _log(request, 'editar', 'ConsultaDocente', f'Editada consulta docente #{c.pk} – {c.nombre_completo}')
        messages.success(request, 'Consulta de docente actualizada.')
        return redirect('detalle_consulta_docente', pk=c.pk)
    return render(request, 'enfermeria/consulta_docente_form.html', {
        'form': form, 'medicamentos_json': _meds_json(),
        'editar': True, 'consulta': consulta,
    })


@admin_required
def eliminar_consulta_docente(request, pk):
    consulta = get_object_or_404(ConsultaDocente, pk=pk)
    if request.method == 'POST':
        _log(request, 'eliminar', 'ConsultaDocente', f'Eliminada consulta docente #{consulta.pk}: {consulta.nombre_completo}')
        consulta.delete()
        messages.success(request, 'Consulta de docente eliminada correctamente.')
        return redirect('lista_consultas_docentes')
    return render(request, 'enfermeria/confirmar_eliminar.html', {
        'objeto': consulta,
        'cancelar_url': 'lista_consultas_docentes',
    })


# ── REMISIONES ────────────────────────────────────────────────────────────────
@login_required
def lista_remisiones(request):
    from django.core.paginator import Paginator
    q             = request.GET.get('q', '')
    filtro_estado = request.GET.get('estado', '')
    filtro_destino= request.GET.get('destino', '')
    filtro_fecha  = request.GET.get('fecha', '')

    qs = Remision.objects.select_related('estudiante').order_by('-fecha_hora')
    if q:
        qs = qs.filter(Q(estudiante__nombre__icontains=q) | Q(motivo__icontains=q) | Q(hospital_destino__icontains=q))
    if filtro_estado:
        qs = qs.filter(estado=filtro_estado)
    if filtro_destino:
        qs = qs.filter(tipo_destino=filtro_destino)
    if filtro_fecha:
        try:
            fecha = datetime.datetime.strptime(filtro_fecha, '%Y-%m-%d').date()
            qs = qs.filter(fecha_hora__date=fecha)
        except ValueError:
            pass

    all_qs = Remision.objects.all()
    paginator = Paginator(qs, 20)
    page_obj  = paginator.get_page(request.GET.get('page'))
    return render(request, 'enfermeria/remisiones_lista.html', {
        'remisiones':       page_obj,
        'query':            q,
        'page_obj':         page_obj,
        'filtro_estado':    filtro_estado,
        'filtro_destino':   filtro_destino,
        'filtro_fecha':     filtro_fecha,
        'total_remisiones': all_qs.count(),
        'total_pendientes': all_qs.filter(estado='pendiente').count(),
        'total_en_proceso': all_qs.filter(estado='en_proceso').count(),
        'total_resueltos':  all_qs.filter(estado='resuelto').count(),
        'total_hospital':   all_qs.filter(tipo_destino='hospital').count(),
        'total_casa':       all_qs.filter(tipo_destino='casa').count(),
        'hay_filtros': any([q, filtro_estado, filtro_destino, filtro_fecha]),
        'today_str': datetime.date.today().isoformat(),
    })


@login_required
def cambiar_estado_remision(request, pk):
    from .models import ConsentimientoRemision
    from django.utils import timezone
    if request.method == 'POST':
        remision = get_object_or_404(Remision, pk=pk)
        nuevo_estado = request.POST.get('estado', '')

        # pendiente → en_proceso: requiere consentimiento firmado
        if nuevo_estado == 'en_proceso':
            tiene_consentimiento = ConsentimientoRemision.objects.filter(remision=remision).exists()
            if not tiene_consentimiento:
                messages.error(request,
                    '⚠️ No se puede avanzar a "En proceso" sin el consentimiento firmado. '
                    'Primero obtén la firma del acudiente.')
                return redirect('lista_remisiones')

        # en_proceso → resuelto: registrar hora de salida real
        if nuevo_estado == 'resuelto':
            hora_salida_real = request.POST.get('hora_salida_real', '')
            if hora_salida_real:
                try:
                    from datetime import datetime
                    remision.hora_salida = datetime.strptime(hora_salida_real, '%H:%M').time()
                except ValueError:
                    pass
            remision.estado = nuevo_estado
            remision.save(update_fields=['estado', 'hora_salida'])
            _log(request, 'editar', 'Remisión', f'Estado cambiado a resuelto — remisión #{remision.pk}')
            messages.success(request, f'✅ Remisión completada. El estudiante salió de las instalaciones.')
            return redirect('lista_remisiones')

        if nuevo_estado in ('pendiente', 'en_proceso', 'resuelto'):
            remision.estado = nuevo_estado
            remision.save(update_fields=['estado'])
            _log(request, 'editar', 'Remisión', f'Estado cambiado a {nuevo_estado} — remisión #{remision.pk}')
            if nuevo_estado == 'en_proceso':
                messages.success(request, '🖊️ Consentimiento verificado. Remisión en proceso de salida.')
            else:
                messages.success(request, f'Estado actualizado a "{remision.get_estado_display()}".')
    return redirect('lista_remisiones')


@admin_required
def nueva_remision(request, estudiante_pk=None):
    initial = {}
    if estudiante_pk:
        est = get_object_or_404(Estudiante, pk=estudiante_pk)
        initial['estudiante'] = est; initial['eps'] = est.eps
    form = RemisionForm(request.POST or None, initial=initial)
    if form.is_valid():
        r = form.save()
        # Correo al acudiente/padre con alerta de remisión
        ok, info = _correo_remision_acudiente(r, request=request)
        if ok:
            messages.info(request, f'📧 Alerta de remisión enviada al acudiente ({info}).')
        else:
            messages.warning(request, f'⚠️ No se pudo enviar correo al acudiente: {info}')
        # Correo al docente si se ingresó
        correo_doc = (getattr(r, 'correo_docente', '') or '').strip()
        if correo_doc:
            try:
                from django.core.mail import EmailMultiAlternatives
                est = r.estudiante
                asunto_doc = f'[COSFA CURE] Remisión: {est.nombre} ha salido del colegio'
                texto_doc = (
                    f"Estimado/a docente,\n\n"
                    f"Le informamos que {est.nombre} ({est.grado}) ha sido remitido/a.\n"
                    f"Destino: {r.destino_display}\n"
                    f"Motivo: {r.motivo}\n\n"
                    f"— COSFA CURE | Colegio San Francisco de Asís"
                )
                msg_doc = EmailMultiAlternatives(asunto_doc, texto_doc, settings.DEFAULT_FROM_EMAIL, [correo_doc])
                msg_doc.send()
                messages.info(request, f'📧 Correo enviado al docente ({correo_doc}).')
            except Exception as e_doc:
                messages.warning(request, f'⚠️ No se pudo enviar correo al docente: {e_doc}')
        _log(request, 'crear', 'Remisión', f'Remisión: {r.estudiante.nombre} → {r.hospital_destino}')
        messages.success(request, f'Remisión registrada para {r.estudiante.nombre}.')
        return redirect('lista_remisiones')
    return render(request, 'enfermeria/remision_form.html', {'form':form})


@admin_required
def editar_remision(request, pk):
    rem  = get_object_or_404(Remision, pk=pk)
    form = RemisionForm(request.POST or None, instance=rem)
    if form.is_valid():
        form.save()
        _log(request, 'editar', 'Remisión', f'Editada remisión #{rem.pk}')
        messages.success(request, 'Remisión actualizada.')
        return redirect('lista_remisiones')
    return render(request, 'enfermeria/remision_form.html', {'form':form,'editar':True})


@admin_required
def eliminar_remision(request, pk):
    remision = get_object_or_404(Remision, pk=pk)
    if request.method == 'POST':
        desc = f'Eliminada remisión #{remision.pk}: {remision.estudiante.nombre} → {remision.destino_display}'
        _log(request, 'eliminar', 'Remisión', desc)
        remision.delete()
        messages.success(request, 'Remisión eliminada correctamente.')
        return redirect('lista_remisiones')
    return render(request, 'enfermeria/confirmar_eliminar.html', {
        'objeto': remision,
        'cancelar_url': 'lista_remisiones',
    })


# ── SEGUIMIENTOS ──────────────────────────────────────────────────────────────
@login_required
def calendario_seguimientos(request):
    hoy           = datetime.date.today()
    # Rango del mes actual para pre-cargar datos
    mes_inicio    = hoy.replace(day=1)
    mes_fin       = (mes_inicio + datetime.timedelta(days=62)).replace(day=1) - datetime.timedelta(days=1)

    seguimientos  = Seguimiento.objects.select_related('estudiante').order_by('fecha')
    vencidos      = [s for s in seguimientos if s.vencido]

    # Datos para el calendario completo (últimos 2 meses + próximo mes)
    rango_inicio  = hoy.replace(day=1) - datetime.timedelta(days=31)
    rango_fin     = mes_fin + datetime.timedelta(days=31)

    consultas_mes   = Consulta.objects.select_related('estudiante').filter(
        fecha_hora__date__gte=rango_inicio, fecha_hora__date__lte=rango_fin
    ).order_by('fecha_hora')
    remisiones_mes  = Remision.objects.select_related('estudiante').filter(
        fecha_hora__date__gte=rango_inicio, fecha_hora__date__lte=rango_fin
    ).order_by('fecha_hora')
    seguimientos_mes = seguimientos.filter(
        fecha__lte=rango_fin
    ).filter(
        Q(fecha_fin__gte=rango_inicio) | Q(fecha_fin__isnull=True, fecha__gte=rango_inicio)
    )
    movimientos_mes  = MovimientoInventario.objects.select_related('medicamento').filter(
        fecha__date__gte=rango_inicio, fecha__date__lte=rango_fin
    ).order_by('fecha')

    return render(request, 'enfermeria/calendario.html', {
        'seguimientos':    seguimientos,
        'vencidos':        vencidos,
        'hoy':             hoy,
        'consultas_mes':   consultas_mes,
        'remisiones_mes':  remisiones_mes,
        'seguimientos_mes':seguimientos_mes,
        'movimientos_mes': movimientos_mes,
    })


@admin_required
def nuevo_seguimiento(request, estudiante_pk=None):
    initial = {}
    if estudiante_pk:
        initial['estudiante'] = get_object_or_404(Estudiante, pk=estudiante_pk)
    form = SeguimientoForm(request.POST or None, initial=initial)
    if form.is_valid():
        s = form.save()
        _log(request, 'crear', 'Seguimiento', f'Seguimiento: {s.estudiante.nombre} – {s.get_tipo_display()} ({s.fecha})')
        _notificar_seguimiento_nuevo(s, request.user)
        messages.success(request, 'Seguimiento programado.')
        return redirect('calendario_seguimientos')
    return render(request, 'enfermeria/seguimiento_form.html', {'form':form})


@login_required
def completar_seguimiento(request, pk):
    s = get_object_or_404(Seguimiento, pk=pk)
    if request.method == 'POST':
        continuar = request.POST.get('continuar') == '1'
        evolucion = request.POST.get('evolucion', '').strip()
        if continuar:
            # Extiende la fecha fin del seguimiento en 7 días y mantiene activo
            import datetime as _dt
            nueva_fecha = _dt.date.today() + _dt.timedelta(days=7)
            s.fecha_fin = nueva_fecha
            s.continuado = True
            s.save()
            _log(request, 'editar', 'Seguimiento', f'Continuado: {s.estudiante.nombre} – {s.get_tipo_display()}')
            _notificar_seguimiento_completado(s, request.user)
            messages.info(request, f'Seguimiento extendido hasta {nueva_fecha.strftime("%d/%m/%Y")}.')
        else:
            s.completado = True
            s.evolucion = evolucion
            s.save()
            _log(request, 'editar', 'Seguimiento', f'Completado: {s.estudiante.nombre} – {s.get_tipo_display()}')
            _notificar_seguimiento_completado(s, request.user)
            messages.success(request, 'Seguimiento cerrado correctamente.')
        # Redirigir al historial del estudiante si viene de ahí
        ref = request.POST.get('next', '')
        if ref:
            return redirect(ref)
        return redirect('calendario_seguimientos')
    # GET: completar sin modal (compatibilidad)
    s.completado = True; s.save()
    _log(request, 'editar', 'Seguimiento', f'Completado: {s.estudiante.nombre} – {s.get_tipo_display()}')
    messages.success(request, 'Seguimiento completado.')
    return redirect('calendario_seguimientos')


# ── INVENTARIO ────────────────────────────────────────────────────────────────
@login_required
def inventario(request):
    from django.core.paginator import Paginator
    q           = request.GET.get('q', '')
    filtro_cat  = request.GET.get('categoria', '')
    qs = Medicamento.objects.all().order_by('categoria', 'nombre')
    if q:
        qs = qs.filter(Q(nombre__icontains=q) | Q(descripcion__icontains=q))
    if filtro_cat:
        qs = qs.filter(categoria=filtro_cat)
    hoy_inv = datetime.date.today()
    en_30   = hoy_inv + datetime.timedelta(days=30)
    bajo_stock  = list(Medicamento.objects.filter(cantidad_actual__lte=django_models.F('cantidad_minima')))
    prox_vencer = list(Medicamento.objects.filter(fecha_vencimiento__gt=hoy_inv, fecha_vencimiento__lte=en_30))
    vencidos = list(Medicamento.objects.filter(fecha_vencimiento__lte=datetime.date.today()))
    paginator   = Paginator(qs, 20)
    page_obj    = paginator.get_page(request.GET.get('page'))
    return render(request, 'enfermeria/inventario.html', {
        'medicamentos':   page_obj,
        'bajo_stock':     bajo_stock,
        'proximos_vencer': prox_vencer,
        'vencidos':       vencidos,
        'query':          q,
        'filtro_cat':     filtro_cat,
        'insumos_count':  Medicamento.objects.filter(categoria='insumo').count(),
        'meds_count':     Medicamento.objects.filter(categoria='medicamento').count(),
    })


@admin_required
def nuevo_medicamento(request):
    form = MedicamentoForm(request.POST or None, request.FILES or None)
    if form.is_valid():
        m = form.save()
        _log(request, 'crear', 'Medicamento', f'Registrado: {m.nombre}')
        messages.success(request, f'Ítem "{m.nombre}" registrado en el inventario.')
        return redirect('detalle_medicamento', pk=m.pk)
    return render(request, 'enfermeria/medicamento_form.html', {'form': form, 'titulo': 'Nuevo ítem del botiquín'})


@login_required
def detalle_medicamento(request, pk):
    med         = get_object_or_404(Medicamento, pk=pk)
    usos        = med.usos_consulta.select_related('consulta', 'consulta__estudiante').order_by('-consulta__fecha_hora')
    movimientos = med.movimientos.order_by('-fecha')
    total_usado = usos.aggregate(total=Sum('cantidad'))['total'] or 0
    return render(request, 'enfermeria/detalle_medicamento.html', {
        'medicamento': med,
        'usos': usos,
        'movimientos': movimientos,
        'total_usado': total_usado,
    })


@admin_required
def editar_medicamento(request, pk):
    med  = get_object_or_404(Medicamento, pk=pk)
    form = MedicamentoForm(request.POST or None, request.FILES or None, instance=med)
    if form.is_valid():
        form.save()
        _log(request, 'editar', 'Medicamento', f'Editado: {med.nombre}')
        messages.success(request, 'Medicamento actualizado.')
        return redirect('detalle_medicamento', pk=med.pk)
    return render(request, 'enfermeria/medicamento_form.html', {'form':form,'titulo':f'Editar: {med.nombre}','med':med})


@admin_required
def registrar_movimiento(request):
    form = MovimientoForm(request.POST or None)
    if form.is_valid():
        mov = form.save()
        med = mov.medicamento
        if mov.tipo == 'entrada':
            med.cantidad_actual += mov.cantidad
        else:
            med.cantidad_actual = max(0, med.cantidad_actual - mov.cantidad)
        med.save()
        _log(request, 'editar', 'Inventario', f'{mov.get_tipo_display()} {mov.cantidad} {med.unidad} de {med.nombre}')
        messages.success(request, 'Movimiento registrado.')
        return redirect('inventario')
    return render(request, 'enfermeria/movimiento_form.html', {'form':form})


# ── ALERTA INVENTARIO POR CORREO ─────────────────────────────────────────────
@login_required
def enviar_alerta_inventario(request):
    """Vista que envía manualmente el correo de alerta de inventario a la enfermera."""
    if request.method == 'POST':
        correo    = request.POST.get('correo_destino', '').strip()
        nombre    = request.user.get_full_name() or request.user.username
        if not correo:
            correo = request.user.email
        if not correo:
            messages.error(request, '⚠️ No hay correo destino. Ingresa un correo o configura el tuyo en el perfil.')
            return redirect('inventario')
        ok, info = _correo_alerta_inventario(correo, nombre)
        if ok:
            messages.success(request, f'📧 Correo de alerta enviado correctamente a {info}.')
        elif 'Sin alertas' in str(info):
            messages.info(request, '✅ No hay alertas activas en este momento. El inventario está en buen estado.')
        else:
            messages.warning(request, f'⚠️ No se pudo enviar el correo: {info}')
        return redirect('inventario')
    return redirect('inventario')


# ── REPORTES ──────────────────────────────────────────────────────────────────
@login_required
def reportes(request):
    fecha_desde = request.GET.get('fecha_desde', '')
    fecha_hasta = request.GET.get('fecha_hasta', '')
    grado_f     = request.GET.get('grado', '')
    motivo_f    = request.GET.get('motivo', '')
    vista       = request.GET.get('vista', 'mes')   # 'mes' o 'semana'
    tipo        = request.GET.get('tipo', 'estudiantes')  # 'estudiantes' o 'docentes'

    hoy = datetime.date.today()
    hoy_str = hoy.isoformat()
    es_filtro_hoy = (fecha_desde == hoy_str and fecha_hasta == hoy_str)

    if tipo == 'docentes':
        # ── ESTADÍSTICAS DOCENTES ──────────────────────────────────────────
        qs = ConsultaDocente.objects.all()
        if fecha_desde:
            try: qs = qs.filter(fecha_hora__date__gte=datetime.date.fromisoformat(fecha_desde))
            except ValueError: pass
        if fecha_hasta:
            try: qs = qs.filter(fecha_hora__date__lte=datetime.date.fromisoformat(fecha_hasta))
            except ValueError: pass

        por_motivo = list(qs.values('motivo').annotate(total=Count('id')).order_by('-total'))
        motivos_doc = dict(ConsultaDocente.MOTIVO_CHOICES) if hasattr(ConsultaDocente, 'MOTIVO_CHOICES') else {}
        for item in por_motivo:
            item['label'] = motivos_doc.get(item['motivo'], item['motivo'])

        por_area = list(qs.values('docente__area').annotate(total=Count('id')).order_by('-total'))

        por_mes = []
        for i in range(5, -1, -1):
            mes   = hoy.replace(day=1) - datetime.timedelta(days=i*30)
            total = qs.filter(fecha_hora__year=mes.year, fecha_hora__month=mes.month).count()
            por_mes.append({'mes': mes.strftime('%b %Y'), 'total': total})

        por_semana = []
        for i in range(7, -1, -1):
            inicio_sem = hoy - datetime.timedelta(days=hoy.weekday()) - datetime.timedelta(weeks=i)
            fin_sem    = inicio_sem + datetime.timedelta(days=6)
            total      = qs.filter(fecha_hora__date__gte=inicio_sem, fecha_hora__date__lte=fin_sem).count()
            por_semana.append({'semana': f'{inicio_sem.strftime("%d/%m")}–{fin_sem.strftime("%d/%m")}', 'total': total})

        desde_30 = hoy - datetime.timedelta(days=30)
        docentes_frecuentes = (ConsultaDocente.objects.filter(fecha_hora__date__gte=desde_30)
                               .values('docente__id', 'docente__nombre', 'docente__area')
                               .annotate(visitas=Count('id')).filter(visitas__gte=4).order_by('-visitas')[:10])

        context = {
            'tipo': 'docentes',
            'por_motivo': por_motivo,
            'por_mes': por_mes, 'por_semana': por_semana,
            'motivos_labels': json.dumps([x['label'] for x in por_motivo[:6]]),
            'motivos_data':   json.dumps([x['total'] for x in por_motivo[:6]]),
            'meses_labels':   json.dumps([x['mes']   for x in por_mes]),
            'meses_data':     json.dumps([x['total'] for x in por_mes]),
            'semanas_labels': json.dumps([x['semana'] for x in por_semana]),
            'semanas_data':   json.dumps([x['total']  for x in por_semana]),
            'grados_labels':  json.dumps([x['docente__area'] or '—' for x in por_area[:8]]),
            'grados_data':    json.dumps([x['total'] for x in por_area[:8]]),
            'total_consultas': qs.count(),
            'total_docentes':  Docente.objects.count(),
            'docentes_activos': Docente.objects.filter(activo=True).count(),
            'docentes_frecuentes': docentes_frecuentes,
            'fecha_desde': fecha_desde, 'fecha_hasta': fecha_hasta,
            'motivos_choices': ConsultaDocente.MOTIVO_CHOICES if hasattr(ConsultaDocente, 'MOTIVO_CHOICES') else [],
            'grados_choices': [],
            'vista': vista,
            'hoy_str': hoy_str, 'es_filtro_hoy': es_filtro_hoy,
        }
    else:
        # ── ESTADÍSTICAS ESTUDIANTES ───────────────────────────────────────
        qs = Consulta.objects.all()
        if fecha_desde:
            try: qs = qs.filter(fecha_hora__date__gte=datetime.date.fromisoformat(fecha_desde))
            except ValueError: pass
        if fecha_hasta:
            try: qs = qs.filter(fecha_hora__date__lte=datetime.date.fromisoformat(fecha_hasta))
            except ValueError: pass
        if grado_f:
            qs = qs.filter(estudiante__grado=grado_f)
        if motivo_f:
            qs = qs.filter(motivo=motivo_f)

        por_motivo = list(qs.values('motivo').annotate(total=Count('id')).order_by('-total'))
        for item in por_motivo:
            item['label'] = dict(Consulta.MOTIVO_CHOICES).get(item['motivo'], item['motivo'])
        por_grado = list(qs.values('estudiante__grado').annotate(total=Count('id')).order_by('-total'))

        por_mes = []
        for i in range(5, -1, -1):
            mes   = hoy.replace(day=1) - datetime.timedelta(days=i*30)
            total = qs.filter(fecha_hora__year=mes.year, fecha_hora__month=mes.month).count()
            por_mes.append({'mes': mes.strftime('%b %Y'), 'total': total})

        por_semana = []
        for i in range(7, -1, -1):
            inicio_sem = hoy - datetime.timedelta(days=hoy.weekday()) - datetime.timedelta(weeks=i)
            fin_sem    = inicio_sem + datetime.timedelta(days=6)
            total      = qs.filter(fecha_hora__date__gte=inicio_sem, fecha_hora__date__lte=fin_sem).count()
            por_semana.append({'semana': f'{inicio_sem.strftime("%d/%m")}–{fin_sem.strftime("%d/%m")}', 'total': total})

        desde_30 = hoy - datetime.timedelta(days=30)
        frecuentes = (Consulta.objects.filter(fecha_hora__date__gte=desde_30)
                      .values('estudiante__id','estudiante__nombre','estudiante__grado')
                      .annotate(visitas=Count('id')).filter(visitas__gte=4).order_by('-visitas')[:10])

        context = {
            'tipo': 'estudiantes',
            'por_motivo': por_motivo, 'por_grado': por_grado,
            'por_mes': por_mes, 'por_semana': por_semana,
            'motivos_labels': json.dumps([x['label'] for x in por_motivo[:6]]),
            'motivos_data':   json.dumps([x['total'] for x in por_motivo[:6]]),
            'meses_labels':   json.dumps([x['mes']   for x in por_mes]),
            'meses_data':     json.dumps([x['total'] for x in por_mes]),
            'semanas_labels': json.dumps([x['semana'] for x in por_semana]),
            'semanas_data':   json.dumps([x['total']  for x in por_semana]),
            'grados_labels':  json.dumps([x['estudiante__grado'] for x in por_grado[:8]]),
            'grados_data':    json.dumps([x['total'] for x in por_grado[:8]]),
            'total_consultas':   qs.count(),
            'total_remisiones':  Remision.objects.count(),
            'total_estudiantes': Estudiante.objects.count(),
            'estudiantes_frecuentes': frecuentes,
            'fecha_desde': fecha_desde, 'fecha_hasta': fecha_hasta,
            'grado_f': grado_f, 'motivo_f': motivo_f,
            'grados_choices': Estudiante.GRADO_CHOICES,
            'motivos_choices': Consulta.MOTIVO_CHOICES,
            'vista': vista,
            'hoy_str': hoy_str, 'es_filtro_hoy': es_filtro_hoy,
        }
    return render(request, 'enfermeria/reportes.html', context)


# ── PDF EXPORTS ───────────────────────────────────────────────────────────────
@login_required
def pdf_reportes(request):
    """Genera el PDF de reportes/estadísticas para imprimir."""
    fecha_desde = request.GET.get('fecha_desde', '')
    fecha_hasta = request.GET.get('fecha_hasta', '')
    grado_f     = request.GET.get('grado', '')
    motivo_f    = request.GET.get('motivo', '')

    qs = Consulta.objects.all()
    if fecha_desde:
        try: qs = qs.filter(fecha_hora__date__gte=datetime.date.fromisoformat(fecha_desde))
        except ValueError: pass
    if fecha_hasta:
        try: qs = qs.filter(fecha_hora__date__lte=datetime.date.fromisoformat(fecha_hasta))
        except ValueError: pass
    if grado_f:
        qs = qs.filter(estudiante__grado=grado_f)
    if motivo_f:
        qs = qs.filter(motivo=motivo_f)

    por_motivo = list(qs.values('motivo').annotate(total=Count('id')).order_by('-total'))
    for item in por_motivo:
        item['label'] = dict(Consulta.MOTIVO_CHOICES).get(item['motivo'], item['motivo'])
    por_grado = list(qs.values('estudiante__grado').annotate(total=Count('id')).order_by('-total'))

    hoy = datetime.date.today()
    por_mes = []
    for i in range(5, -1, -1):
        mes   = hoy.replace(day=1) - datetime.timedelta(days=i*30)
        total = qs.filter(fecha_hora__year=mes.year, fecha_hora__month=mes.month).count()
        por_mes.append({'mes': mes.strftime('%B %Y'), 'total': total})

    desde_30 = hoy - datetime.timedelta(days=30)
    frecuentes = (Consulta.objects.filter(fecha_hora__date__gte=desde_30)
                  .values('estudiante__nombre','estudiante__grado')
                  .annotate(visitas=Count('id')).filter(visitas__gte=4).order_by('-visitas')[:10])

    context = {
        'por_motivo': por_motivo, 'por_grado': por_grado, 'por_mes': por_mes,
        'total_consultas': qs.count(),
        'total_remisiones': Remision.objects.count(),
        'total_estudiantes': Estudiante.objects.count(),
        'frecuentes': frecuentes,
        'fecha_desde': fecha_desde, 'fecha_hasta': fecha_hasta,
        'grado_f': grado_f, 'motivo_f': motivo_f,
        'fecha_impresion': hoy,
    }
    return render(request, 'enfermeria/pdf_reportes.html', context)


@login_required
def pdf_consultas(request):
    """PDF de registro de citas/consultas."""
    q  = request.GET.get('q', '')
    qs = Consulta.objects.select_related('estudiante').order_by('-fecha_hora')
    if q:
        qs = qs.filter(Q(estudiante__nombre__icontains=q)|Q(motivo__icontains=q))
    return render(request, 'enfermeria/pdf_consultas.html', {
        'consultas': qs,
        'query': q,
        'fecha_impresion': datetime.date.today(),
    })


@login_required
def pdf_movimientos(request):
    """PDF de entradas y salidas de medicamentos."""
    med_pk = request.GET.get('medicamento', '')
    qs = MovimientoInventario.objects.select_related('medicamento').order_by('-fecha')
    medicamento = None
    if med_pk:
        medicamento = get_object_or_404(Medicamento, pk=med_pk)
        qs = qs.filter(medicamento=medicamento)
    return render(request, 'enfermeria/pdf_movimientos.html', {
        'movimientos': qs,
        'medicamento': medicamento,
        'medicamentos': Medicamento.objects.all().order_by('nombre'),
        'fecha_impresion': datetime.date.today(),
    })


# ── HISTORIAL DE CAMBIOS ──────────────────────────────────────────────────────
@login_required
def historial_cambios(request):
    from django.core.paginator import Paginator
    from django.db.models import Count, Q
    from django.contrib.auth.models import User

    # ── Filtros ──────────────────────────────────────────────────────────────
    q          = request.GET.get('q', '').strip()
    f_accion   = request.GET.get('accion', '')
    f_modulo   = request.GET.get('modulo', '')
    f_usuario  = request.GET.get('usuario', '')
    f_desde    = request.GET.get('desde', '')
    f_hasta    = request.GET.get('hasta', '')

    qs = HistorialCambio.objects.select_related('usuario').order_by('-fecha')

    if q:
        qs = qs.filter(descripcion__icontains=q)
    if f_accion:
        qs = qs.filter(accion=f_accion)
    if f_modulo:
        qs = qs.filter(modelo__iexact=f_modulo)
    if f_usuario:
        qs = qs.filter(usuario__username__iexact=f_usuario)
    if f_desde:
        try:
            from datetime import datetime
            qs = qs.filter(fecha__date__gte=datetime.strptime(f_desde, '%Y-%m-%d').date())
        except ValueError:
            pass
    if f_hasta:
        try:
            from datetime import datetime
            qs = qs.filter(fecha__date__lte=datetime.strptime(f_hasta, '%Y-%m-%d').date())
        except ValueError:
            pass

    # ── Stats globales ────────────────────────────────────────────────────────
    todos        = HistorialCambio.objects.all()
    total        = todos.count()
    total_crear  = todos.filter(accion='crear').count()
    total_editar = todos.filter(accion='editar').count()
    total_elim   = todos.filter(accion='eliminar').count()

    # Lista de módulos y usuarios para los filtros
    modulos   = todos.values_list('modelo', flat=True).distinct().order_by('modelo')
    usuarios  = User.objects.filter(historialcambio__isnull=False).distinct().order_by('username')

    hay_filtros = any([q, f_accion, f_modulo, f_usuario, f_desde, f_hasta])

    paginator = Paginator(qs, 25)
    page_obj  = paginator.get_page(request.GET.get('page'))

    import datetime as _dt
    hoy = _dt.date.today()
    ayer = hoy - _dt.timedelta(days=1)

    return render(request, 'enfermeria/historial_cambios.html', {
        'cambios': page_obj, 'page_obj': page_obj,
        'q': q, 'f_accion': f_accion, 'f_modulo': f_modulo,
        'f_usuario': f_usuario, 'f_desde': f_desde, 'f_hasta': f_hasta,
        'hay_filtros': hay_filtros,
        'total': total, 'total_crear': total_crear,
        'total_editar': total_editar, 'total_elim': total_elim,
        'modulos': modulos, 'usuarios': usuarios,
        'today_str': hoy.strftime('%d/%m/%Y'),
        'yesterday_str': ayer.strftime('%d/%m/%Y'),
    })


@admin_required
def borrar_historial_cambios(request):
    """Borra todo el historial de cambios. Solo POST, solo superusuarios."""
    if not request.user.is_superuser:
        messages.error(request, '❌ Solo los superusuarios pueden borrar el historial.')
        return redirect('historial_cambios')
    if request.method == 'POST':
        confirmacion = request.POST.get('confirmacion', '').strip()
        if confirmacion != 'BORRAR HISTORIAL':
            messages.error(request, '❌ Texto de confirmación incorrecto. No se borró nada.')
            return redirect('historial_cambios')
        total = HistorialCambio.objects.count()
        HistorialCambio.objects.all().delete()
        messages.success(request, f'✅ Historial borrado: {total} registros eliminados.')
        return redirect('historial_cambios')
    return redirect('historial_cambios')


@login_required
def pdf_historial_estudiante(request, pk):
    """PDF completo del historial clínico de un estudiante."""
    est = get_object_or_404(Estudiante, pk=pk)
    return render(request, 'enfermeria/pdf_historial_estudiante.html', {
        'estudiante':   est,
        'consultas':    est.consultas.prefetch_related('medicamentos_usados__medicamento').order_by('-fecha_hora'),
        'remisiones':   est.remisiones.order_by('-fecha_hora'),
        'seguimientos': est.seguimientos.order_by('fecha'),
        'fecha_impresion': datetime.date.today(),
    })


@login_required
def pdf_remisiones(request):
    """PDF del listado completo de remisiones."""
    return render(request, 'enfermeria/pdf_remisiones.html', {
        'remisiones':      Remision.objects.select_related('estudiante').order_by('-fecha_hora'),
        'fecha_impresion': datetime.date.today(),
    })


@login_required
def pdf_remision_individual(request, pk):
    """PDF individual de una remision externa."""
    import datetime as _dt
    remision = get_object_or_404(Remision, pk=pk)
    est = remision.estudiante
    today = _dt.date.today()
    edad = today.year - est.fecha_nacimiento.year - (
        (today.month, today.day) < (est.fecha_nacimiento.month, est.fecha_nacimiento.day)
    ) if est.fecha_nacimiento else None
    return render(request, 'enfermeria/pdf_remision_individual.html', {
        'remision':        remision,
        'estudiante':      est,
        'edad':            edad,
        'fecha_impresion': today,
        'enfermera':       request.user.get_full_name() or request.user.username,
    })


# ══════════════════════════════════════════════════════════════════════════════
# CHATBOT IA MÉDICO — Asistente para la enfermera
# ══════════════════════════════════════════════════════════════════════════════

CHATBOT_LIMITE_DIARIO = 50   # mensajes de usuario por día (ajustable)

@login_required
def chatbot_ia(request):
    """Página principal del chatbot médico – con sistema de sesiones."""
    from django.urls import reverse

    # Si viene ?nueva=1 → crear sesión nueva y redirigir
    if request.GET.get('nueva') == '1':
        sesion = SesionChatbot.objects.create(
            usuario=request.user,
            titulo='Nueva conversación',
        )
        return redirect(reverse('chatbot_ia') + f'?sesion={sesion.pk}')

    # Obtener o crear sesión activa
    sesion_id = request.GET.get('sesion')
    sesion_activa = None

    if sesion_id:
        try:
            sesion_activa = SesionChatbot.objects.get(pk=sesion_id, usuario=request.user)
        except SesionChatbot.DoesNotExist:
            pass

    if not sesion_activa:
        # Buscar la sesión más reciente o crear nueva
        sesion_activa = SesionChatbot.objects.filter(
            usuario=request.user
        ).first()
        if not sesion_activa:
            sesion_activa = SesionChatbot.objects.create(
                usuario=request.user,
                titulo='Nueva conversación',
            )
        # Redirigir para que la URL siempre tenga ?sesion=ID
        return redirect(reverse('chatbot_ia') + f'?sesion={sesion_activa.pk}')

    # Cargar historial de la sesión activa (últimos 60 mensajes)
    historial_db = MensajeChatbot.objects.filter(
        usuario=request.user, sesion=sesion_activa
    ).order_by('fecha').values('role', 'content')[:60]
    historial = [
        {'role': m['role'], 'content': m['content']}
        for m in historial_db
    ]

    # Lista de todas las sesiones (barra lateral)
    todas_sesiones = SesionChatbot.objects.filter(
        usuario=request.user
    ).order_by('-actualizada')[:50]

    # Mensajes de usuario enviados hoy (zona horaria Bogotá)
    hoy_bogota = timezone.localdate()
    mensajes_hoy = MensajeChatbot.objects.filter(
        usuario=request.user,
        role='user',
        fecha__date=hoy_bogota,
    ).count()
    restantes = max(0, CHATBOT_LIMITE_DIARIO - mensajes_hoy)

    return render(request, 'enfermeria/chatbot.html', {
        'historial_inicial': json.dumps(historial),
        'mensajes_hoy':      mensajes_hoy,
        'limite_diario':     CHATBOT_LIMITE_DIARIO,
        'restantes':         restantes,
        'sesion_activa':     sesion_activa,
        'todas_sesiones':    todas_sesiones,
    })


@login_required
def chatbot_api(request):
    """Endpoint AJAX: recibe pregunta, llama Anthropic Claude, guarda historial en BD."""
    if request.method != 'POST':
        from django.http import JsonResponse
        return JsonResponse({'error': 'Metodo no permitido'}, status=405)

    from django.http import JsonResponse
    import json as _json
    import time
    import urllib.request as _urllib_req
    import urllib.error

    data = _json.loads(request.body)
    pregunta = data.get('pregunta', '').strip()
    historial = data.get('historial', [])
    sesion_id = data.get('sesion_id')

    if not pregunta:
        return JsonResponse({'error': 'Pregunta vacia'}, status=400)

    # ── Obtener o crear sesión ───────────────────────────────────────────────
    sesion = None
    if sesion_id:
        try:
            sesion = SesionChatbot.objects.get(pk=sesion_id, usuario=request.user)
        except SesionChatbot.DoesNotExist:
            pass
    if not sesion:
        sesion = SesionChatbot.objects.filter(usuario=request.user).first()
        if not sesion:
            sesion = SesionChatbot.objects.create(usuario=request.user, titulo='Nueva conversación')

    # ── Verificar límite diario ──────────────────────────────────────────────
    hoy_bog = timezone.localdate()
    mensajes_hoy_count = MensajeChatbot.objects.filter(
        usuario=request.user, role='user', fecha__date=hoy_bog,
    ).count()
    if mensajes_hoy_count >= CHATBOT_LIMITE_DIARIO:
        ahora_bog  = timezone.localtime()
        medianoche = ahora_bog.replace(hour=0, minute=0, second=0, microsecond=0) + datetime.timedelta(days=1)
        secs_rest  = int((medianoche - ahora_bog).total_seconds())
        horas      = secs_rest // 3600
        minutos    = (secs_rest % 3600) // 60
        tiempo_txt = f'{horas}h {minutos}min' if horas > 0 else f'{minutos} minutos'
        return JsonResponse({
            'quota_agotada': True,
            'tiempo_espera': tiempo_txt,
            'secs_restantes': secs_rest,
        }, status=200)

    # ── Sistema prompt ───────────────────────────────────────────────────────
    system_prompt = (
        "Eres CURE-BOT, el asistente médico inteligente de enfermería escolar del "
        "Colegio San Francisco de Asís (COSFA) en Colombia, integrado en el sistema COSFA CURE. "
        "Eres experto en: enfermería pediátrica y escolar, primeros auxilios, farmacología básica "
        "(dosis pediátricas de ibuprofeno, paracetamol, antihistamínicos, etc.), "
        "signos vitales por edad, protocolos de atención escolar, manejo de urgencias menores, "
        "alergias, convulsiones febriles, traumatismos leves, desmayos y reacciones alérgicas. "
        "Responde siempre en español, de manera clara, estructurada y profesional. "
        "Usa listas, pasos numerados o tablas cuando aporten claridad. "
        "Ante emergencias graves, indica siempre llamar al 123 o remitir al hospital. "
        "No diagnostiques enfermedades graves de forma definitiva; orienta y recomienda valoración médica. "
        "Sé empático, preciso y recuerda que trabajas con niños y adolescentes en edad escolar."
    )

    # ── Construir mensajes para Anthropic ────────────────────────────────────
    # Cargar historial de la sesión desde BD (fuente de verdad)
    mensajes_bd = []
    if sesion:
        mensajes_bd = list(MensajeChatbot.objects.filter(
            usuario=request.user, sesion=sesion
        ).order_by('fecha').values('role', 'content')[:30])

    msgs_anthropic = []
    for m in (mensajes_bd if mensajes_bd else historial[-10:]):
        role = m.get('role', '')
        content = m.get('content', '')
        if role in ('user', 'assistant') and content:
            msgs_anthropic.append({'role': role, 'content': content})

    msgs_anthropic.append({'role': 'user', 'content': pregunta})

    # ── Llamar Anthropic API ─────────────────────────────────────────────────
    ANTHROPIC_API_KEY = getattr(settings, 'ANTHROPIC_API_KEY', '')
    GEMINI_API_KEY    = getattr(settings, 'GEMINI_API_KEY', '')

    respuesta = None
    modelo_usado = ''
    ultimo_error = 'No hay API key configurada.'

    # Intentar Anthropic primero (más confiable)
    if ANTHROPIC_API_KEY:
        try:
            body = _json.dumps({
                'model': 'claude-sonnet-4-20250514',
                'max_tokens': 4000,
                'system': system_prompt,
                'messages': msgs_anthropic,
            }).encode('utf-8')
            req = _urllib_req.Request(
                'https://api.anthropic.com/v1/messages',
                data=body,
                headers={
                    'Content-Type': 'application/json',
                    'x-api-key': ANTHROPIC_API_KEY,
                    'anthropic-version': '2023-06-01',
                },
                method='POST',
            )
            with _urllib_req.urlopen(req, timeout=30) as resp:
                result = _json.loads(resp.read().decode('utf-8'))
            respuesta = result['content'][0]['text']
            modelo_usado = 'claude-sonnet-4'
        except Exception as e:
            ultimo_error = f'Anthropic error: {str(e)}'

    # Fallback a Gemini si Anthropic falla o no está configurado
    if not respuesta and GEMINI_API_KEY:
        contents = []
        for m in msgs_anthropic:
            role = 'model' if m['role'] == 'assistant' else 'user'
            contents.append({'role': role, 'parts': [{'text': m['content']}]})

        intentos_gemini = [
            ('v1beta', 'gemini-2.5-flash'),
            ('v1beta', 'gemini-2.0-flash'),
        ]
        for api_ver, modelo in intentos_gemini:
            body = _json.dumps({
                'system_instruction': {'parts': [{'text': system_prompt}]},
                'contents': contents,
                'generationConfig': {'maxOutputTokens': 1500, 'temperature': 0.4},
            }).encode('utf-8')
            url = (f'https://generativelanguage.googleapis.com/{api_ver}/models/'
                   f'{modelo}:generateContent?key={GEMINI_API_KEY}')
            req = _urllib_req.Request(
                url, data=body,
                headers={'Content-Type': 'application/json'}, method='POST',
            )
            try:
                with _urllib_req.urlopen(req, timeout=30) as resp:
                    result = _json.loads(resp.read().decode('utf-8'))
                respuesta = result['candidates'][0]['content']['parts'][0]['text']
                modelo_usado = modelo
                break
            except urllib.error.HTTPError as e:
                try:
                    eb = _json.loads(e.read().decode('utf-8'))
                    msg = eb.get('error', {}).get('message', str(e))
                    code = eb.get('error', {}).get('code', e.code)
                    status_str = eb.get('error', {}).get('status', '')
                except Exception:
                    msg, code, status_str = str(e), e.code, ''
                es_quota = (
                    code in (429, 503) or
                    'RESOURCE_EXHAUSTED' in status_str or
                    'quota' in msg.lower()
                )
                if es_quota and modelo == intentos_gemini[-1][1]:
                    ahora_bog  = timezone.localtime()
                    medianoche = ahora_bog.replace(hour=0, minute=0, second=0, microsecond=0) + datetime.timedelta(days=1)
                    secs_rest  = int((medianoche - ahora_bog).total_seconds())
                    horas      = secs_rest // 3600
                    minutos    = (secs_rest % 3600) // 60
                    return JsonResponse({
                        'quota_agotada': True,
                        'tiempo_espera': f'{horas}h {minutos}min' if horas else f'{minutos} min',
                        'secs_restantes': secs_rest,
                    }, status=200)
                ultimo_error = f'Gemini HTTP {code} ({modelo}): {msg}'
                time.sleep(0.3)
                continue
            except Exception as e:
                ultimo_error = f'Gemini error ({modelo}): {str(e)}'
                time.sleep(0.3)
                continue

    if not respuesta:
        return JsonResponse({'error': ultimo_error}, status=500)

    # ── Guardar en BD ────────────────────────────────────────────────────────
    if sesion:
        MensajeChatbot.objects.create(
            usuario=request.user, sesion=sesion, role='user', content=pregunta,
        )
        MensajeChatbot.objects.create(
            usuario=request.user, sesion=sesion, role='assistant',
            content=respuesta, modelo_ia=modelo_usado,
        )
        # Auto-título: usar primeros 60 chars de la primera pregunta
        if sesion and sesion.titulo in ('Nueva conversación', ''):
            titulo_auto = pregunta[:60].strip()
            if len(pregunta) > 60:
                titulo_auto += '…'
            sesion.titulo = titulo_auto
            sesion.save(update_fields=['titulo', 'actualizada'])
        elif sesion:
            sesion.save(update_fields=['actualizada'])

        # Limitar historial a 200 mensajes por sesión
        total = MensajeChatbot.objects.filter(sesion=sesion).count()
        if total > 200:
            exceso = total - 200
            ids_viejos = (
                MensajeChatbot.objects.filter(sesion=sesion)
                .order_by('fecha').values_list('id', flat=True)[:exceso]
            )
            MensajeChatbot.objects.filter(id__in=list(ids_viejos)).delete()

    # ── Calcular restantes del día ───────────────────────────────────────────
    mensajes_hoy_new = MensajeChatbot.objects.filter(
        usuario=request.user, role='user', fecha__date=hoy_bog,
    ).count()
    restantes = max(0, CHATBOT_LIMITE_DIARIO - mensajes_hoy_new)

    return JsonResponse({
        'respuesta':    respuesta,
        'modelo_usado': modelo_usado,
        'restantes':    restantes,
        'limite':       CHATBOT_LIMITE_DIARIO,
        'sesion_id':    sesion.pk if sesion else None,
        'sesion_titulo': sesion.titulo if sesion else '',
    })


@login_required
def chatbot_nueva_sesion(request):
    """Crea una nueva sesión de chat y redirige al chatbot."""
    if request.method == 'POST':
        sesion = SesionChatbot.objects.create(
            usuario=request.user,
            titulo='Nueva conversación',
        )
        from django.urls import reverse
        return redirect(reverse('chatbot_ia') + f'?sesion={sesion.pk}')
    return redirect('chatbot_ia')


@login_required
def chatbot_sesion_renombrar(request):
    """Renombra una sesión vía AJAX."""
    from django.http import JsonResponse
    import json as _json
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)
    data = _json.loads(request.body)
    sesion_id = data.get('sesion_id')
    nuevo_titulo = data.get('titulo', '').strip()[:100]
    if not sesion_id or not nuevo_titulo:
        return JsonResponse({'error': 'Datos incompletos'}, status=400)
    try:
        sesion = SesionChatbot.objects.get(pk=sesion_id, usuario=request.user)
        sesion.titulo = nuevo_titulo
        sesion.save(update_fields=['titulo'])
        return JsonResponse({'ok': True, 'titulo': sesion.titulo})
    except SesionChatbot.DoesNotExist:
        return JsonResponse({'error': 'Sesión no encontrada'}, status=404)


@login_required
def chatbot_sesion_borrar(request):
    """Borra una sesión y todos sus mensajes."""
    from django.http import JsonResponse
    import json as _json
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)
    data = _json.loads(request.body)
    sesion_id = data.get('sesion_id')
    try:
        sesion = SesionChatbot.objects.get(pk=sesion_id, usuario=request.user)
        sesion.delete()
        # Buscar próxima sesión disponible
        proxima = SesionChatbot.objects.filter(usuario=request.user).first()
        return JsonResponse({'ok': True, 'proxima_id': proxima.pk if proxima else None})
    except SesionChatbot.DoesNotExist:
        return JsonResponse({'error': 'Sesión no encontrada'}, status=404)


@login_required
def chatbot_limpiar(request):
    """Limpia mensajes de la sesión activa o todo el historial."""
    if request.method == 'POST':
        sesion_id = request.POST.get('sesion_id')
        if sesion_id:
            try:
                sesion = SesionChatbot.objects.get(pk=sesion_id, usuario=request.user)
                MensajeChatbot.objects.filter(sesion=sesion).delete()
                sesion.titulo = 'Nueva conversación'
                sesion.save(update_fields=['titulo'])
                messages.success(request, '🗑️ Conversación limpiada.')
            except SesionChatbot.DoesNotExist:
                pass
        else:
            MensajeChatbot.objects.filter(usuario=request.user).delete()
            SesionChatbot.objects.filter(usuario=request.user).delete()
            messages.success(request, '🗑️ Historial completo eliminado.')
    return redirect('chatbot_ia')


@login_required
def chatbot_diagnostico(request):
    """Diagnóstico: lista los modelos Gemini disponibles para la API key configurada."""
    from django.http import JsonResponse
    import json as _json

    GEMINI_API_KEY = getattr(settings, 'GEMINI_API_KEY', '')
    if not GEMINI_API_KEY:
        return JsonResponse({'error': 'No hay API key configurada'}, status=500)

    resultados = {}
    for api_ver in ['v1beta', 'v1']:
        url = f'https://generativelanguage.googleapis.com/{api_ver}/models?key={GEMINI_API_KEY}'
        req = _urllib_req.Request(url, method='GET')
        try:
            with _urllib_req.urlopen(req, timeout=10) as resp:
                data = _json.loads(resp.read().decode('utf-8'))
            modelos = [m['name'].replace('models/', '') for m in data.get('models', [])
                       if 'generateContent' in m.get('supportedGenerationMethods', [])]
            resultados[api_ver] = modelos
        except _urllib_req.HTTPError as e:
            try:
                body = _json.loads(e.read().decode('utf-8'))
                resultados[api_ver] = f'HTTP {e.code}: {body.get("error", {}).get("message", "?")}'
            except Exception:
                resultados[api_ver] = f'HTTP {e.code}'
        except Exception as ex:
            resultados[api_ver] = str(ex)

    return JsonResponse({'api_key_prefijo': GEMINI_API_KEY[:10] + '...', 'modelos': resultados})


# ═══════════════════════════════════════════════════════════════════════════════
# NUEVAS FUNCIONES v14_fix6
# ═══════════════════════════════════════════════════════════════════════════════

# ── 1. RESUMEN AUTOMÁTICO CON GEMINI ─────────────────────────────────────────
@login_required
def resumen_consulta_ia(request, pk):
    """AJAX POST: genera un resumen médico profesional de la consulta usando Gemini."""
    from django.http import JsonResponse
    import json as _json
    import urllib.request as _req

    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)

    consulta = get_object_or_404(Consulta, pk=pk)
    est = consulta.estudiante

    GEMINI_API_KEY = getattr(settings, 'GEMINI_API_KEY', '')
    if not GEMINI_API_KEY:
        return JsonResponse({'error': 'API key de Gemini no configurada'}, status=500)

    # Construir contexto clínico completo
    meds_lista = ', '.join(
        f"{mc.medicamento.nombre} {mc.cantidad}{mc.medicamento.unidad} ({mc.dosis})"
        for mc in consulta.medicamentos_usados.select_related('medicamento').all()
        if mc.medicamento
    ) or consulta.medicamento_suministrado or 'Ninguno'

    vitales = []
    if consulta.temperatura:        vitales.append(f"T° {consulta.temperatura}°C")
    if consulta.presion_arterial:   vitales.append(f"PA {consulta.presion_arterial}")
    if consulta.frecuencia_cardiaca: vitales.append(f"FC {consulta.frecuencia_cardiaca} lpm")
    if consulta.frecuencia_respiratoria: vitales.append(f"FR {consulta.frecuencia_respiratoria} rpm")
    if consulta.peso:               vitales.append(f"Peso {consulta.peso} kg")
    if consulta.talla:              vitales.append(f"Talla {consulta.talla} cm")

    prompt = f"""Redacta un resumen médico clínico breve, formal y en tercera persona de esta consulta de enfermería escolar. Debe ser UN solo párrafo de máximo 4 oraciones cortas. Termina siempre con punto final. NO uses listas ni encabezados. USA SOLO los datos proporcionados.

Estudiante: {est.nombre}, grado {est.grado}, nacido {est.fecha_nacimiento}. Alergias: {est.alergias or 'ninguna'}. Condiciones: {est.condiciones_medicas or 'ninguna'}.
Consulta del {timezone.localtime(consulta.fecha_hora).strftime('%d/%m/%Y %H:%M')}. Motivo: {consulta.get_motivo_display()}. Síntomas: {consulta.descripcion_sintomas}. Signos vitales: {', '.join(vitales) if vitales else 'no registrados'}. Tratamiento: {consulta.tratamiento}. Medicamentos: {meds_lista}. Estado: {consulta.get_estado_display()}. Observaciones: {consulta.observaciones or 'ninguna'}.

Resumen (un párrafo, máximo 4 oraciones, termina con punto):"""

    payload = _json.dumps({
        'contents': [{'role': 'user', 'parts': [{'text': prompt}]}],
        'generationConfig': {'maxOutputTokens': 300, 'temperature': 0.2, 'stopSequences': ['\n\n']},
    }).encode('utf-8')

    intentos = [('v1beta', 'gemini-2.5-flash'), ('v1beta', 'gemini-2.0-flash'), ('v1', 'gemini-2.0-flash')]
    for api_ver, modelo in intentos:
        url = f'https://generativelanguage.googleapis.com/{api_ver}/models/{modelo}:generateContent?key={GEMINI_API_KEY}'
        req_obj = _req.Request(url, data=payload, headers={'Content-Type': 'application/json'}, method='POST')
        try:
            with _req.urlopen(req_obj, timeout=30) as resp:
                result = _json.loads(resp.read().decode('utf-8'))
            resumen = result['candidates'][0]['content']['parts'][0]['text']
            return JsonResponse({'resumen': resumen, 'modelo': modelo})
        except Exception:
            continue

    return JsonResponse({'error': 'No se pudo conectar con Gemini. Intente de nuevo.'}, status=500)


# ── 2. ALERTA DE PATRÓN DE SALUD ─────────────────────────────────────────────
@login_required
def alerta_patron_salud(request, estudiante_pk):
    """Analiza consultas de los últimos 15 días y detecta patrones repetidos."""
    from django.http import JsonResponse

    est = get_object_or_404(Estudiante, pk=estudiante_pk)
    hace_15_dias = timezone.now() - datetime.timedelta(days=15)

    consultas_recientes = Consulta.objects.filter(
        estudiante=est,
        fecha_hora__gte=hace_15_dias
    ).order_by('motivo', '-fecha_hora')

    # Agrupar por motivo
    from django.db.models import Count as _Count
    conteo = (
        Consulta.objects
        .filter(estudiante=est, fecha_hora__gte=hace_15_dias)
        .values('motivo')
        .annotate(total=_Count('id'))
        .order_by('-total')
    )

    alertas = []
    for item in conteo:
        if item['total'] >= 2:
            # Buscar nombre legible del motivo
            motivo_display = dict(Consulta.MOTIVO_CHOICES).get(item['motivo'], item['motivo'])
            alertas.append({
                'motivo': motivo_display,
                'motivo_key': item['motivo'],
                'veces': item['total'],
                'recomendacion': _recomendacion_patron(item['motivo'], item['total']),
            })

    total_consultas = consultas_recientes.count()

    return JsonResponse({
        'estudiante': est.nombre,
        'grado': est.grado,
        'periodo_dias': 15,
        'total_consultas': total_consultas,
        'alertas': alertas,
        'hay_alerta': len(alertas) > 0,
    })


def _recomendacion_patron(motivo, veces):
    """Devuelve una recomendación según el motivo repetido."""
    recomendaciones = {
        'dolor_cabeza':    'Revisar hidratación, postura y exposición a pantallas. Considerar valoración oftalmológica.',
        'dolor_estomago':  'Evaluar hábitos alimenticios y nivel de estrés. Puede indicar ansiedad escolar.',
        'fiebre':          'Vigilar posible infección recurrente. Recomendar valoración médica externa.',
        'lesion':          'Revisar el contexto de las lesiones. Posible necesidad de intervención psicosocial.',
        'mareo':           'Evaluar tensión arterial, hidratación y posibles problemas vestibulares.',
        'nauseas':         'Indagar sobre alimentación, estrés académico o posible embarazo en adolescentes.',
        'dolor_garganta':  'Puede indicar infección recurrente o amigdalitis crónica. Referir a médico.',
        'alergias':        'Identificar alérgeno específico. Recomendar valoración por alergología.',
        'otro':            'Documentar detalladamente los síntomas para identificar un patrón claro.',
    }
    base = recomendaciones.get(motivo, 'Se recomienda seguimiento médico especializado.')
    if veces >= 4:
        return f'⚠️ URGENTE ({veces} veces): {base}'
    return f'{base}'


# ── 3. PWA: manifest y service worker ────────────────────────────────────────
# _JR = JsonResponse, _HR = HttpResponse (ya importados arriba)
_JR = JsonResponse
_HR = HttpResponse

def pwa_manifest(request):
    """Sirve el manifest.json para la PWA."""
    manifest = {
        "name": "COSFA CURE",
        "short_name": "COSFA CURE",
        "description": "Sistema de enfermeria escolar - Colegio San Francisco de Asis",
        "start_url": "/",
        "scope": "/",
        "display": "standalone",
        "background_color": "#0d1b2e",
        "theme_color": "#0ea5a0",
        "orientation": "any",
        "lang": "es-CO",
        "icons": [
            {"src": "/static/icons/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any"},
            {"src": "/static/icons/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any"},
            {"src": "/static/icons/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
            {"src": "/static/icons/apple-touch-icon.png", "sizes": "180x180", "type": "image/png"},
        ],
        "shortcuts": [
            {"name": "Nueva consulta", "url": "/consultas/nueva/", "description": "Registrar una consulta rapida"},
            {"name": "Buscar estudiante", "url": "/buscar/", "description": "Buscar un estudiante"},
            {"name": "Inventario", "url": "/inventario/", "description": "Ver inventario de medicamentos"},
        ],
        "categories": ["medical", "education"],
        "prefer_related_applications": False,
    }
    return _JR(manifest, content_type='application/manifest+json')


def pwa_service_worker(request):
    """Sirve el service worker para la PWA con soporte offline completo."""
    sw_js = """
/* ═══════════════════════════════════════════════════════════════
   COSFA CURE — Service Worker v7 (Offline completo + IndexedDB)
   Estrategia:
     · Estáticos locales  → Cache-first (siempre rápido)
     · CDN externos       → Cache-first (fuentes, íconos)
     · Páginas Django     → Network-first + cache como fallback
     · POST /consultas/   → Cola IndexedDB si no hay red, sync al reconectar
     · Otros POST         → Solo red (no se cachean)
═══════════════════════════════════════════════════════════════ */

const VER        = 'cosfa-v7';
const CACHE_APP  = VER + '-app';      // páginas y HTML
const CACHE_STATIC = VER + '-static'; // JS, CSS, íconos locales
const CACHE_CDN  = VER + '-cdn';      // fuentes y CDN externos

// ── IndexedDB: cola de consultas offline ──────────────────────
const IDB_NAME    = 'cosfacure-offline';
const IDB_VERSION = 1;
const STORE_NAME  = 'consultas_pendientes';

function abrirIDB() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(IDB_NAME, IDB_VERSION);
    req.onupgradeneeded = e => {
      const db = e.target.result;
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        db.createObjectStore(STORE_NAME, { keyPath: 'id', autoIncrement: true });
      }
    };
    req.onsuccess = e => resolve(e.target.result);
    req.onerror   = e => reject(e.target.error);
  });
}

async function guardarConsultaOffline(request) {
  try {
    const body = await request.clone().text();
    const db   = await abrirIDB();
    return new Promise((resolve, reject) => {
      const tx    = db.transaction(STORE_NAME, 'readwrite');
      const store = tx.objectStore(STORE_NAME);
      store.add({
        url:       request.url,
        method:    request.method,
        headers:   [...request.headers.entries()],
        body:      body,
        timestamp: Date.now(),
      });
      tx.oncomplete = () => resolve();
      tx.onerror    = e => reject(e.target.error);
    });
  } catch (err) {
    console.warn('[SW] Error guardando consulta offline:', err);
  }
}

async function sincronizarPendientes() {
  let db;
  try {
    db = await abrirIDB();
  } catch { return; }

  const tx      = db.transaction(STORE_NAME, 'readwrite');
  const store   = tx.objectStore(STORE_NAME);
  const pending = await new Promise((res, rej) => {
    const req = store.getAll();
    req.onsuccess = e => res(e.target.result);
    req.onerror   = e => rej(e.target.error);
  });

  for (const item of pending) {
    try {
      const headers = new Headers(item.headers);
      const resp = await fetch(item.url, {
        method:  item.method,
        headers: headers,
        body:    item.body,
      });
      if (resp.ok || resp.status === 302) {
        // Eliminar de la cola
        const tx2 = db.transaction(STORE_NAME, 'readwrite');
        tx2.objectStore(STORE_NAME).delete(item.id);
        console.log('[SW] Consulta offline sincronizada, id:', item.id);
        // Notificar a los clientes
        const clients = await self.clients.matchAll({ type: 'window' });
        clients.forEach(c => c.postMessage({ type: 'COSFA_SYNC_OK', id: item.id }));
      }
    } catch {
      // Sin red todavía, se intentará en el próximo sync
    }
  }
}

// Escuchar cuando vuelve la conexión para sincronizar
self.addEventListener('message', async e => {
  if (e.data && e.data.type === 'COSFA_ONLINE') {
    await sincronizarPendientes();
  }
});

// Background Sync (donde esté disponible)
self.addEventListener('sync', async e => {
  if (e.tag === 'cosfa-sync-consultas') {
    e.waitUntil(sincronizarPendientes());
  }
});

// Recursos que se pre-cachean en la instalación
const PRE_CACHE_STATIC = [
  '/static/icons/favicon.ico',
  '/static/icons/icon-192.png',
  '/static/icons/icon-512.png',
  '/static/icons/apple-touch-icon.png',
  '/manifest.json',
];

// Páginas de la app que se pre-cachean para offline
const PRE_CACHE_PAGES = [
  '/inicio/',
  '/estudiantes/',
  '/consultas/',
  '/inventario/',
  '/calendario/',
  '/remisiones/',
  '/reportes/',
];

// ── INSTALAR ─────────────────────────────────────────────────
self.addEventListener('install', e => {
  e.waitUntil(Promise.all([
    caches.open(CACHE_STATIC).then(c => c.addAll(PRE_CACHE_STATIC).catch(() => {})),
    caches.open(CACHE_APP).then(c => c.addAll(PRE_CACHE_PAGES).catch(() => {})),
  ]));
  self.skipWaiting();
});

// ── ACTIVAR: limpiar versiones viejas ────────────────────────
self.addEventListener('activate', e => {
  const valid = [CACHE_APP, CACHE_STATIC, CACHE_CDN];
  e.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => !valid.includes(k)).map(k => caches.delete(k)))
    )
  );
  self.clients.claim();
});

// ── FETCH ────────────────────────────────────────────────────
self.addEventListener('fetch', e => {
  const req = e.request;
  const url = new URL(req.url);

  // Ignorar requests que no son GET (POST, etc.) — EXCEPTO nueva consulta
  if (req.method !== 'GET') {
    // Interceptar POST a nueva consulta para cola offline
    if (req.method === 'POST' && (
        url.pathname.startsWith('/nueva-consulta/') ||
        url.pathname.startsWith('/consultas/nueva/') ||
        url.pathname.match(/\/consulta\/nueva\/?/)
    )) {
      e.respondWith(
        fetch(req.clone()).catch(async () => {
          // Sin red: guardar en IndexedDB
          await guardarConsultaOffline(req.clone());
          // Registrar Background Sync si disponible
          if (self.registration.sync) {
            self.registration.sync.register('cosfa-sync-consultas').catch(() => {});
          }
          // Responder con página de confirmación offline
          return new Response(OFFLINE_GUARDADO_PAGE, {
            headers: { 'Content-Type': 'text/html; charset=utf-8' }
          });
        })
      );
      return;
    }
    return;
  }

  // Ignorar requests del admin de Django y del chatbot IA (siempre necesitan red)
  if (url.pathname.startsWith('/admin/') || url.pathname.startsWith('/chatbot/api/')) return;

  // Ignorar requests de extensiones del navegador
  if (!url.protocol.startsWith('http')) return;

  // ── 1. Recursos CDN externos (fuentes Google, Bootstrap Icons) ──
  if (url.origin !== location.origin) {
    e.respondWith(cdnFirst(req));
    return;
  }

  // ── 2. Archivos estáticos locales (/static/) ──
  if (url.pathname.startsWith('/static/') || url.pathname.startsWith('/media/')) {
    e.respondWith(staticFirst(req));
    return;
  }

  // ── 3. Páginas de la app Django ──
  e.respondWith(networkFirstPage(req));
});

// ── ESTRATEGIA: Cache-first para CDN ─────────────────────────
async function cdnFirst(req) {
  const cached = await caches.match(req);
  if (cached) return cached;
  try {
    const resp = await fetch(req);
    if (resp.ok) {
      const cache = await caches.open(CACHE_CDN);
      cache.put(req, resp.clone());
    }
    return resp;
  } catch {
    return cached || new Response('', { status: 503 });
  }
}

// ── ESTRATEGIA: Cache-first para estáticos locales ───────────
async function staticFirst(req) {
  const cached = await caches.match(req);
  if (cached) return cached;
  try {
    const resp = await fetch(req);
    if (resp.ok) {
      const cache = await caches.open(CACHE_STATIC);
      cache.put(req, resp.clone());
    }
    return resp;
  } catch {
    return new Response('', { status: 503 });
  }
}

// ── ESTRATEGIA: Network-first para páginas Django ────────────
async function networkFirstPage(req) {
  try {
    const resp = await fetch(req);
    if (resp.ok) {
      const cache = await caches.open(CACHE_APP);
      cache.put(req, resp.clone());
    }
    return resp;
  } catch {
    // Sin internet — buscar en cache
    const cached = await caches.match(req);
    if (cached) return cached;

    // Intentar servir la página más cercana en cache
    const url = new URL(req.url);
    const fallbacks = [url.pathname.split('/').slice(0, -1).join('/') + '/', '/inicio/', '/'];
    for (const fb of fallbacks) {
      const match = await caches.match(fb);
      if (match) return match;
    }

    // Última opción: página offline embebida
    return new Response(OFFLINE_PAGE, { headers: { 'Content-Type': 'text/html; charset=utf-8' } });
  }
}

// ── PÁGINA OFFLINE ───────────────────────────────────────────
const OFFLINE_PAGE = `<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Sin conexión — COSFA CURE</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    font-family: 'DM Sans', system-ui, sans-serif;
    background: linear-gradient(135deg, #0f2444 0%, #1a3a6e 100%);
    color: #e2eaf5;
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 24px;
  }
  .card {
    background: rgba(255,255,255,.07);
    backdrop-filter: blur(20px);
    border: 1px solid rgba(255,255,255,.12);
    border-radius: 24px;
    padding: 48px 40px;
    text-align: center;
    max-width: 400px;
    width: 100%;
    box-shadow: 0 20px 60px rgba(0,0,0,.4);
  }
  .logo {
    width: 72px; height: 72px; border-radius: 18px;
    background: linear-gradient(135deg, #0ea5a0, #1a3a6e);
    display: flex; align-items: center; justify-content: center;
    font-size: 2rem; margin: 0 auto 24px;
    animation: pulse 2s ease-in-out infinite;
  }
  @keyframes pulse {
    0%,100% { box-shadow: 0 0 0 0 rgba(14,165,160,.4); }
    50%      { box-shadow: 0 0 0 16px rgba(14,165,160,0); }
  }
  h1 { font-size: 1.5rem; font-weight: 700; color: #fff; margin-bottom: 12px; }
  p  { font-size: .95rem; color: rgba(255,255,255,.6); line-height: 1.6; margin-bottom: 8px; }
  .hint {
    background: rgba(14,165,160,.15);
    border: 1px solid rgba(14,165,160,.3);
    border-radius: 12px;
    padding: 14px 16px;
    font-size: .85rem;
    color: #0ea5a0;
    margin: 20px 0;
    text-align: left;
  }
  .hint strong { display: block; margin-bottom: 6px; color: #14c9c3; }
  .hint ul { padding-left: 16px; }
  .hint li { margin-bottom: 4px; }
  .btn {
    display: inline-block;
    background: linear-gradient(135deg, #0ea5a0, #1a3a6e);
    color: white; border: none;
    padding: 14px 32px; border-radius: 50px;
    font-size: 1rem; font-weight: 600;
    cursor: pointer; margin-top: 8px;
    width: 100%;
    transition: opacity .2s;
  }
  .btn:hover { opacity: .85; }
  .status {
    display: flex; align-items: center; justify-content: center; gap: 8px;
    margin-top: 20px; font-size: .8rem; color: rgba(255,255,255,.4);
  }
  .dot-offline {
    width: 8px; height: 8px; border-radius: 50%;
    background: #ef4444;
    animation: blink 1.5s ease-in-out infinite;
  }
  @keyframes blink { 0%,100%{opacity:1} 50%{opacity:.2} }
</style>
</head>
<body>
<div class="card">
  <div class="logo">✚</div>
  <h1>Sin conexión</h1>
  <p>COSFA CURE no puede alcanzar el servidor en este momento.</p>
  <div class="hint">
    <strong>📋 Páginas disponibles sin internet:</strong>
    <ul>
      <li>Dashboard principal</li>
      <li>Lista de estudiantes</li>
      <li>Consultas e inventario</li>
      <li>Calendario de seguimientos</li>
    </ul>
  </div>
  <p>Usa el botón Atrás para volver a una página ya visitada, o espera a recuperar la conexión.</p>
  <button class="btn" onclick="history.back()">← Volver atrás</button>
  <button class="btn" style="background:rgba(255,255,255,.1);margin-top:8px" onclick="location.reload()">🔄 Reintentar</button>
  <div class="status">
    <div class="dot-offline"></div>
    Sin conexión a internet
  </div>
</div>
<script>
  // Detectar cuando vuelve la conexión y recargar automáticamente
  window.addEventListener('online', () => location.reload());
</script>
</body>
</html>`;

// ── PÁGINA: Consulta guardada offline ────────────────────────
const OFFLINE_GUARDADO_PAGE = `<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Guardado sin conexión — COSFA CURE</title>
<style>
  *{margin:0;padding:0;box-sizing:border-box}
  body{font-family:'DM Sans',system-ui,sans-serif;background:linear-gradient(135deg,#0f2444,#1a3a6e);
    color:#e2eaf5;min-height:100vh;display:flex;align-items:center;justify-content:center;padding:24px}
  .card{background:rgba(255,255,255,.07);backdrop-filter:blur(20px);border:1px solid rgba(255,255,255,.12);
    border-radius:24px;padding:48px 40px;text-align:center;max-width:420px;width:100%;box-shadow:0 20px 60px rgba(0,0,0,.4)}
  .ico{width:72px;height:72px;border-radius:18px;background:linear-gradient(135deg,#f59e0b,#d97706);
    display:flex;align-items:center;justify-content:center;font-size:2rem;margin:0 auto 24px;
    animation:pulse 2s ease-in-out infinite}
  @keyframes pulse{0%,100%{box-shadow:0 0 0 0 rgba(245,158,11,.4)}50%{box-shadow:0 0 0 16px rgba(245,158,11,0)}}
  h1{font-size:1.4rem;font-weight:700;color:#fff;margin-bottom:12px}
  p{font-size:.9rem;color:rgba(255,255,255,.65);line-height:1.6;margin-bottom:8px}
  .info{background:rgba(245,158,11,.15);border:1px solid rgba(245,158,11,.3);border-radius:12px;
    padding:14px 16px;font-size:.85rem;color:#fcd34d;margin:20px 0;text-align:left}
  .info strong{display:block;margin-bottom:6px;color:#fde68a}
  .btn{display:inline-block;background:linear-gradient(135deg,#0ea5a0,#1a3a6e);color:#fff;border:none;
    padding:14px 32px;border-radius:50px;font-size:1rem;font-weight:600;cursor:pointer;margin-top:8px;width:100%;transition:opacity .2s}
  .btn:hover{opacity:.85}
  .sync-status{display:flex;align-items:center;justify-content:center;gap:8px;margin-top:20px;
    font-size:.78rem;color:rgba(255,255,255,.4)}
  .dot{width:8px;height:8px;border-radius:50%;background:#f59e0b;animation:blink 1.5s ease-in-out infinite}
  @keyframes blink{0%,100%{opacity:1}50%{opacity:.2}}
</style>
</head>
<body>
<div class="card">
  <div class="ico">📋</div>
  <h1>Consulta guardada localmente</h1>
  <p>No hay conexión a internet, pero la consulta quedó guardada en este dispositivo.</p>
  <div class="info">
    <strong>⏳ Se enviará automáticamente cuando vuelva la conexión:</strong>
    <ul style="padding-left:16px;margin-top:4px">
      <li>Los datos están seguros en este dispositivo</li>
      <li>No cierres ni recargues esta pestaña</li>
      <li>Cuando vuelva el internet, se sincronizará solo</li>
    </ul>
  </div>
  <button class="btn" onclick="history.back()">← Registrar otra consulta</button>
  <div class="sync-status"><div class="dot"></div>Esperando conexión...</div>
</div>
<script>
  window.addEventListener('online', async () => {
    if (navigator.serviceWorker && navigator.serviceWorker.controller) {
      navigator.serviceWorker.controller.postMessage({ type: 'COSFA_ONLINE' });
    }
    document.querySelector('.sync-status').innerHTML = '✅ Conexión restaurada — sincronizando...';
    setTimeout(() => { window.location.href = '/inicio/'; }, 2000);
  });
</script>
</body>
</html>`;
"""
    return _HR(sw_js, content_type='application/javascript')



# ══════════════════════════════════════════════════════════════════════════════
# PDF INDIVIDUAL DE CONSULTA — Formato oficial COSFA
# ══════════════════════════════════════════════════════════════════════════════
@login_required
def pdf_consulta_individual(request, pk):
    import datetime as _dt
    consulta = get_object_or_404(Consulta, pk=pk)
    est = consulta.estudiante
    today = _dt.date.today()
    edad = today.year - est.fecha_nacimiento.year - (
        (today.month, today.day) < (est.fecha_nacimiento.month, est.fecha_nacimiento.day)
    ) if est.fecha_nacimiento else None

    if consulta.estado == 'remitido_hospital':
        template = 'enfermeria/pdf_consulta_remision.html'
    elif consulta.estado == 'regreso_clase':
        template = 'enfermeria/pdf_consulta_regreso_clase.html'
    else:
        # atendido o remitido_casa → formato traslado general
        template = 'enfermeria/pdf_consulta_general.html'

    return render(request, template, {
        'consulta': consulta,
        'estudiante': est,
        'edad': edad,
        'fecha_impresion': today,
        'enfermera': request.user.get_full_name() or request.user.username,
    })


# ══════════════════════════════════════════════════════════════════════════════
# EXPORTAR CONSULTA A EXCEL
# ══════════════════════════════════════════════════════════════════════════════
@login_required
def exportar_consulta_excel(request, pk):
    import csv as _csv
    consulta = get_object_or_404(Consulta, pk=pk)
    est = consulta.estudiante

    resp = HttpResponse(content_type='text/csv; charset=utf-8')
    nombre_archivo = f'consulta_{consulta.pk}_{est.nombre.replace(" ", "_")}.csv'
    resp['Content-Disposition'] = f'attachment; filename="{nombre_archivo}"'
    resp.write('\ufeff')
    writer = _csv.writer(resp)

    # Datos del estudiante
    writer.writerow(['== DATOS DEL ESTUDIANTE =='])
    writer.writerow(['Nombre', 'Grado', 'Documento', 'EPS', 'Tipo Sangre', 'Acudiente'])
    writer.writerow([
        est.nombre, est.grado, est.numero_documento or '',
        est.eps or '', est.tipo_sangre or '', est.acudiente or '',
    ])
    writer.writerow([])

    # Datos de la consulta
    writer.writerow(['== DATOS DE LA CONSULTA =='])
    writer.writerow(['Fecha', 'Hora', 'Motivo', 'Estado'])
    writer.writerow([
        timezone.localtime(consulta.fecha_hora).strftime('%d/%m/%Y'),
        timezone.localtime(consulta.fecha_hora).strftime('%H:%M'),
        consulta.get_motivo_display(),
        consulta.get_estado_display(),
    ])
    writer.writerow([])

    # Signos vitales
    writer.writerow(['== SIGNOS VITALES =='])
    writer.writerow(['Temperatura (C)', 'Presion', 'F. Cardiaca (lpm)', 'F. Resp. (rpm)', 'Peso (kg)', 'Talla (cm)'])
    writer.writerow([
        consulta.temperatura or '',
        consulta.presion_arterial or '',
        consulta.frecuencia_cardiaca or '',
        consulta.frecuencia_respiratoria or '',
        consulta.peso or '',
        consulta.talla or '',
    ])
    writer.writerow([])

    # Motivo clinico
    writer.writerow(['== MOTIVO CLINICO =='])
    writer.writerow(['Sintomas'])
    writer.writerow([consulta.descripcion_sintomas or ''])
    writer.writerow(['Tratamiento'])
    writer.writerow([consulta.tratamiento or ''])
    writer.writerow(['Observaciones'])
    writer.writerow([consulta.observaciones or ''])
    writer.writerow([])

    # Medicamentos
    writer.writerow(['== MEDICAMENTOS SUMINISTRADOS =='])
    writer.writerow(['Medicamento', 'Cantidad', 'Dosis / Indicacion'])
    usos = consulta.medicamentos_usados.all()
    if usos:
        for u in usos:
            writer.writerow([
                u.medicamento.nombre if u.medicamento else '',
                f'{u.cantidad} {u.medicamento.unidad if u.medicamento else ""}',
                u.dosis or '',
            ])
    else:
        writer.writerow([consulta.medicamento_suministrado or 'Ninguno', '', ''])

    return resp


@login_required
def exportar_consulta_xlsx(request, pk):
    """Exporta una consulta individual a Excel (.xlsx) real."""
    if not OPENPYXL_OK:
        messages.error(request, 'openpyxl no instalado.')
        return redirect('detalle_consulta', pk=pk)

    from openpyxl.styles import Font, PatternFill, Alignment

    consulta = get_object_or_404(Consulta, pk=pk)
    est = consulta.estudiante
    st = _excel_styles()

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'Consulta'
    ws.column_dimensions['A'].width = 22
    ws.column_dimensions['B'].width = 35

    def _sec(row, titulo):
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=2)
        c = ws.cell(row=row, column=1, value=titulo)
        c.font = st['header_font']; c.fill = st['header_fill']
        c.alignment = st['center']

    def _row(row, label, value):
        a = ws.cell(row=row, column=1, value=label)
        a.font = Font(bold=True, size=9); a.alignment = st['left']; a.border = st['border']
        b = ws.cell(row=row, column=2, value=value)
        b.font = Font(size=9); b.alignment = st['left']; b.border = st['border']

    # Título
    ws.merge_cells('A1:B1')
    t = ws['A1']
    t.value = f'COSFA CURE — Consulta #{consulta.pk}'
    t.font = st['title_font']; t.fill = st['title_fill']; t.alignment = st['center']
    ws.row_dimensions[1].height = 28

    r = 2
    _sec(r, 'DATOS DEL ESTUDIANTE'); r += 1
    _row(r, 'Nombre', est.nombre); r += 1
    _row(r, 'Grado', est.grado); r += 1
    _row(r, 'Documento', est.numero_documento or ''); r += 1
    _row(r, 'EPS', est.eps or ''); r += 1
    _row(r, 'Tipo Sangre', est.tipo_sangre or ''); r += 1
    _row(r, 'Acudiente', est.acudiente or ''); r += 1

    r += 1
    _sec(r, 'DATOS DE LA CONSULTA'); r += 1
    _row(r, 'Fecha', timezone.localtime(consulta.fecha_hora).strftime('%d/%m/%Y')); r += 1
    _row(r, 'Hora', timezone.localtime(consulta.fecha_hora).strftime('%H:%M')); r += 1
    _row(r, 'Motivo', consulta.get_motivo_display()); r += 1
    _row(r, 'Estado', consulta.get_estado_display()); r += 1

    r += 1
    _sec(r, 'SIGNOS VITALES'); r += 1
    _row(r, 'Temperatura (°C)', consulta.temperatura or ''); r += 1
    _row(r, 'Presión', consulta.presion_arterial or ''); r += 1
    _row(r, 'F. Cardiaca (lpm)', consulta.frecuencia_cardiaca or ''); r += 1
    _row(r, 'F. Respiratoria (rpm)', consulta.frecuencia_respiratoria or ''); r += 1
    _row(r, 'Peso (kg)', consulta.peso or ''); r += 1
    _row(r, 'Talla (cm)', consulta.talla or ''); r += 1

    r += 1
    _sec(r, 'MOTIVO CLÍNICO'); r += 1
    _row(r, 'Síntomas', consulta.descripcion_sintomas or ''); r += 1
    _row(r, 'Tratamiento', consulta.tratamiento or ''); r += 1
    _row(r, 'Observaciones', consulta.observaciones or ''); r += 1

    r += 1
    _sec(r, 'MEDICAMENTOS SUMINISTRADOS'); r += 1
    # Header de medicamentos
    for col, h in enumerate(['Medicamento', 'Cantidad / Dosis'], 1):
        c = ws.cell(row=r, column=col, value=h)
        c.font = Font(bold=True, size=9, color='FFFFFF')
        c.fill = PatternFill('solid', fgColor='3AAFA9')
        c.alignment = st['center']; c.border = st['border']
    r += 1
    usos = consulta.medicamentos_usados.all()
    if usos:
        for u in usos:
            _row(r, u.medicamento.nombre if u.medicamento else '',
                 f'{u.cantidad} {u.medicamento.unidad if u.medicamento else ""} — {u.dosis or ""}')
            r += 1
    else:
        _row(r, consulta.medicamento_suministrado or 'Ninguno', ''); r += 1

    nombre_archivo = f'consulta_{consulta.pk}_{est.nombre.replace(" ", "_")}.xlsx'
    resp = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    resp['Content-Disposition'] = f'attachment; filename="{nombre_archivo}"'
    wb.save(resp)
    return resp



# ══════════════════════════════════════════════════════════════════════════════
# DETALLE Y EDICIÓN DE SEGUIMIENTO
# ══════════════════════════════════════════════════════════════════════════════
@login_required
def detalle_seguimiento(request, pk):
    s = get_object_or_404(Seguimiento, pk=pk)
    return render(request, 'enfermeria/detalle_seguimiento.html', {'seguimiento': s})

@admin_required
def editar_seguimiento(request, pk):
    s = get_object_or_404(Seguimiento, pk=pk)
    form = SeguimientoForm(request.POST or None, instance=s)
    if form.is_valid():
        form.save()
        messages.success(request, 'Seguimiento actualizado.')
        return redirect('calendario_seguimientos')
    return render(request, 'enfermeria/seguimiento_form.html', {'form': form, 'editar': True})


@admin_required
def eliminar_seguimiento(request, pk):
    s = get_object_or_404(Seguimiento, pk=pk)
    if request.method == 'POST':
        desc = f'Eliminado seguimiento #{s.pk}: {s.estudiante.nombre} – {s.get_tipo_display()}'
        _log(request, 'eliminar', 'Seguimiento', desc)
        s.delete()
        messages.success(request, 'Seguimiento eliminado correctamente.')
        return redirect('calendario_seguimientos')
    return render(request, 'enfermeria/confirmar_eliminar.html', {
        'objeto': s,
        'cancelar_url': 'calendario_seguimientos',
    })


# ── CONSENTIMIENTO DIGITAL DE REMISIÓN ────────────────────────────────────────
@login_required
def consentimiento_remision(request, pk):
    """Página de consentimiento digital para una remisión."""
    from .models import ConsentimientoRemision
    remision = get_object_or_404(Remision, pk=pk)
    consentimiento_existente = None
    try:
        consentimiento_existente = remision.consentimiento
    except ConsentimientoRemision.DoesNotExist:
        pass

    context = {
        'remision': remision,
        'estudiante': remision.estudiante,
        'consentimiento': consentimiento_existente,
    }
    return render(request, 'enfermeria/consentimiento_remision.html', context)


@login_required
def guardar_consentimiento_remision(request, pk):
    """Guarda las firmas digitales del consentimiento."""
    from .models import ConsentimientoRemision
    from django.http import JsonResponse
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)
    remision = get_object_or_404(Remision, pk=pk)
    import json as _json
    data = _json.loads(request.body)
    firma_acudiente  = data.get('firma_acudiente', '')
    firma_enfermera  = data.get('firma_enfermera', '')
    nombre_acudiente = data.get('nombre_acudiente', '')
    nombre_enfermera = data.get('nombre_enfermera', '')
    cc_acudiente     = data.get('cc_acudiente', '')
    if not firma_acudiente or not firma_enfermera:
        return JsonResponse({'error': 'Se requieren ambas firmas'}, status=400)
    obj, created = ConsentimientoRemision.objects.update_or_create(
        remision=remision,
        defaults={
            'firma_acudiente':  firma_acudiente,
            'firma_enfermera':  firma_enfermera,
            'nombre_acudiente': nombre_acudiente,
            'nombre_enfermera': nombre_enfermera,
            'cc_acudiente':     cc_acudiente,
        }
    )
    # Auto-avanzar estado a en_proceso al firmar el consentimiento
    if remision.estado == 'pendiente':
        remision.estado = 'en_proceso'
        remision.save(update_fields=['estado'])
        _log(request, 'editar', 'Remisión', f'Consentimiento firmado — estado → en_proceso (remisión #{remision.pk})')
    nuevo_estado = remision.estado
    nuevo_estado_display = remision.get_estado_display()
    return JsonResponse({'ok': True, 'created': created, 'id': obj.pk, 'nuevo_estado': nuevo_estado, 'nuevo_estado_display': nuevo_estado_display})


# ── PERFIL DE USUARIO ─────────────────────────────────────────────────────────

@login_required
def perfil_usuario(request):
    """Vista para ver y editar el perfil del usuario."""
    user = request.user
    # Obtener o crear el perfil extendido
    perfil, _ = PerfilUsuario.objects.get_or_create(usuario=user)

    if request.method == 'POST':
        accion = request.POST.get('accion', 'datos')

        # Mapeo accion → tab para preservar pestaña activa tras redirect
        TAB_MAP = {
            'datos':                 'datos',
            'foto':                  'foto',
            'password':              'seguridad',
            'firma':                 'seguridad',
            'cambiar_clave_admin':   'seguridad',
            'restablecer_clave_admin': 'seguridad',
        }
        tab_destino = TAB_MAP.get(accion, 'datos')

        if accion == 'datos':
            user.first_name = request.POST.get('first_name', user.first_name).strip()
            user.last_name  = request.POST.get('last_name', user.last_name).strip()
            user.email      = request.POST.get('email', user.email).strip()
            user.save()
            perfil.cargo    = request.POST.get('cargo', perfil.cargo).strip()
            perfil.telefono = request.POST.get('telefono', perfil.telefono).strip()
            perfil.save()
            messages.success(request, '✅ Datos actualizados correctamente.')

        elif accion == 'password':
            current = request.POST.get('current_password', '')
            new1    = request.POST.get('new_password1', '')
            new2    = request.POST.get('new_password2', '')
            if not user.check_password(current):
                messages.error(request, '❌ La contraseña actual es incorrecta.')
            elif new1 != new2:
                messages.error(request, '❌ Las contraseñas nuevas no coinciden.')
            elif len(new1) < 6:
                messages.error(request, '❌ La contraseña debe tener al menos 6 caracteres.')
            else:
                user.set_password(new1)
                user.save()
                update_session_auth_hash(request, user)
                messages.success(request, '✅ Contraseña cambiada correctamente.')

        elif accion == 'cambiar_clave_admin':
            nueva = request.POST.get('nueva_clave_admin', '').strip()
            confirmar = request.POST.get('confirmar_clave_admin', '').strip()
            if not nueva.isdigit() or len(nueva) != 6:
                messages.error(request, '❌ La clave admin debe ser exactamente 6 dígitos numéricos.')
            elif nueva != confirmar:
                messages.error(request, '❌ Las claves no coinciden.')
            else:
                # Guardar en settings dinámico via archivo de configuración local
                import os
                settings_local = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'cosfa_cure', 'admin_secret.txt')
                with open(settings_local, 'w') as _f:
                    _f.write(nueva)
                messages.success(request, f'✅ Clave de administrador actualizada correctamente a: {nueva}')

        elif accion == 'restablecer_clave_admin':
            import os
            _base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            _active  = os.path.join(_base, 'cosfa_cure', 'admin_secret.txt')
            _default = os.path.join(_base, 'cosfa_cure', 'admin_secret_default.txt')
            try:
                with open(_default, 'r') as _df:
                    clave_original = _df.read().strip()
                if clave_original:
                    with open(_active, 'w') as _af:
                        _af.write(clave_original)
                    messages.success(request, f'✅ Clave restablecida a la clave original ({clave_original}).')
                else:
                    messages.error(request, '❌ No se encontró una clave original guardada.')
            except FileNotFoundError:
                messages.error(request, '❌ No hay clave original registrada. Configura una nueva clave.')
            except Exception as _e:
                messages.error(request, f'❌ Error al restablecer: {_e}')

        elif accion == 'foto':
            if 'foto' in request.FILES:
                foto_file = request.FILES['foto']
                # Validar tamaño (máx. 5 MB)
                if foto_file.size > 5 * 1024 * 1024:
                    messages.error(request, 'La imagen supera los 5 MB permitidos.')
                else:
                    # Eliminar foto anterior si existe para evitar archivos huérfanos
                    if perfil.foto:
                        try:
                            import os
                            old_path = perfil.foto.path
                            if os.path.isfile(old_path):
                                os.remove(old_path)
                        except Exception:
                            pass
                    perfil.foto = foto_file
                    perfil.save()
                    # Refrescar instancia para que .url sea correcto
                    perfil.refresh_from_db()
                    # Forzar actualización de sesión para sidebar y barra superior
                    request.session['foto_perfil'] = perfil.foto.url
                    request.session.modified = True
                    messages.success(request, 'Foto actualizada correctamente.')
            else:
                messages.error(request, 'No se recibió ninguna foto.')

        elif accion == 'firma':
            firma_b64 = request.POST.get('firma_data', '').strip()
            if firma_b64:
                perfil.firma_digital = firma_b64
                perfil.save()
                messages.success(request, '✅ Firma digital guardada correctamente.')
            else:
                messages.error(request, '❌ No se recibió la firma.')

        return redirect(f'/perfil/?tab={tab_destino}')

    tab_activo = request.GET.get('tab', 'datos')
    tabs_validos = {'datos', 'foto', 'seguridad', 'cierre', 'backup', 'usuarios'}
    if tab_activo not in tabs_validos:
        tab_activo = 'datos'

    # Sincronizar sesión con la foto actual del perfil en cada carga de la página
    if perfil.foto:
        try:
            url_foto = perfil.foto.url
            if request.session.get('foto_perfil') != url_foto:
                request.session['foto_perfil'] = url_foto
                request.session.modified = True
        except Exception:
            pass
    elif 'foto_perfil' in request.session:
        del request.session['foto_perfil']
        request.session.modified = True

    # Lista de usuarios para el tab de gestión (solo visible para admin)
    from .models import PerfilUsuario as _PU
    usuario_es_admin = es_admin(user)
    lista_usuarios = []
    if usuario_es_admin:
        for u in User.objects.exclude(pk=user.pk).select_related('perfilusuario').order_by('username'):
            p = getattr(u, 'perfilusuario', None)
            from django.utils import timezone as _tz
            import datetime as _dt
            _now = _tz.now()
            _last = u.last_login
            if _last:
                _delta = _now - _last
                if _delta.total_seconds() < 300:  # menos de 5 min → en línea
                    _estado = 'online'
                    _ultima = 'En línea ahora'
                elif _delta.days == 0:
                    _h = int(_delta.total_seconds() // 3600)
                    _m = int((_delta.total_seconds() % 3600) // 60)
                    _ultima = f'Hace {_h}h {_m}m' if _h else f'Hace {_m} min'
                    _estado = 'reciente'
                elif _delta.days == 1:
                    _ultima = 'Ayer'
                    _estado = 'inactivo'
                else:
                    _ultima = _last.strftime('%d/%m/%Y')
                    _estado = 'inactivo'
            else:
                _ultima = 'Nunca'
                _estado = 'nunca'
            lista_usuarios.append({
                'user':       u,
                'perfil':     p,
                'rol':        p.rol if p else 'viewer',
                'rol_label':  'Administrador' if (p and p.rol == 'admin') else 'Solo lectura',
                'fecha':      p.fecha_creacion.strftime('%d/%m/%Y') if p else '—',
                'ultima_vez': _ultima,
                'estado':     _estado,
            })

    # Leer clave admin actual y clave original para mostrarlas en perfil
    import os as _os2
    _base2   = _os2.path.dirname(_os2.path.dirname(_os2.path.abspath(__file__)))
    _sf2     = _os2.path.join(_base2, 'cosfa_cure', 'admin_secret.txt')
    _sf2_def = _os2.path.join(_base2, 'cosfa_cure', 'admin_secret_default.txt')
    try:
        with open(_sf2, 'r') as _f2:
            clave_admin_actual = _f2.read().strip() or '——'
    except Exception:
        clave_admin_actual = '——'
    try:
        with open(_sf2_def, 'r') as _f3:
            clave_admin_default = _f3.read().strip() or '——'
    except Exception:
        clave_admin_default = '——'

    return render(request, 'enfermeria/perfil.html', {
        'perfil':              perfil,
        'tab_activo':          tab_activo,
        'usuario_es_admin':    usuario_es_admin,
        'lista_usuarios':      lista_usuarios,
        'clave_admin_actual':  clave_admin_actual,
        'clave_admin_default': clave_admin_default,
    })


# ══════════════════════════════════════════════════════════════════════════════
# BORRAR DATOS DE FIN DE AÑO
# ══════════════════════════════════════════════════════════════════════════════
@admin_required
def borrar_datos_anio(request):
    """
    Borrado selectivo de categorías de datos.
    El usuario elige qué grupos eliminar desde el modal en perfil.html.
    Requiere confirmación escrita 'BORRAR TODO'.
    """
    if request.method != 'POST':
        return redirect('perfil_usuario')

    confirmacion = request.POST.get('confirmacion', '').strip()
    if confirmacion != 'BORRAR TODO':
        messages.error(request, '❌ Texto de confirmación incorrecto. No se borró nada.')
        return redirect('perfil_usuario')

    cats_raw = request.POST.get('categorias', '')
    categorias = [c.strip() for c in cats_raw.split(',') if c.strip()]

    if not categorias:
        messages.error(request, '❌ No se seleccionó ninguna categoría para borrar.')
        return redirect('perfil_usuario')

    eliminados = []

    # Mapa: clave → (label, función de borrado)
    # El orden respeta las FK (dependientes primero)
    def _borrar_chatbot():
        MensajeChatbot.objects.all().delete()
        SesionChatbot.objects.all().delete()

    def _borrar_historial():
        HistorialCambio.objects.all().delete()

    def _borrar_notificaciones():
        Notificacion.objects.all().delete()

    def _borrar_seguimientos():
        Seguimiento.objects.all().delete()

    def _borrar_remisiones():
        ConsentimientoRemision.objects.all().delete()
        Remision.objects.all().delete()

    def _borrar_consultas_est():
        MedicamentoConsulta.objects.filter(consulta__isnull=False).delete()
        Consulta.objects.all().delete()

    def _borrar_consultas_doc():
        ConsultaDocente.objects.all().delete()

    def _borrar_inventario():
        MovimientoInventario.objects.all().delete()
        MedicamentoConsulta.objects.all().delete()
        Medicamento.objects.all().delete()

    def _borrar_estudiantes():
        Estudiante.objects.all().delete()

    def _borrar_docentes():
        Docente.objects.all().delete()

    ORDEN = [
        ('chatbot',        'Chatbot (sesiones y mensajes)',    _borrar_chatbot),
        ('historial',      'Historial de cambios',             _borrar_historial),
        ('notificaciones', 'Notificaciones',                   _borrar_notificaciones),
        ('seguimientos',   'Seguimientos',                     _borrar_seguimientos),
        ('remisiones',     'Remisiones y consentimientos',     _borrar_remisiones),
        ('consultas_est',  'Consultas de estudiantes',         _borrar_consultas_est),
        ('consultas_doc',  'Consultas de docentes',            _borrar_consultas_doc),
        ('inventario',     'Inventario (medicamentos)',        _borrar_inventario),
        ('estudiantes',    'Estudiantes',                      _borrar_estudiantes),
        ('docentes',       'Docentes',                         _borrar_docentes),
    ]

    for key, label, fn in ORDEN:
        if key in categorias:
            fn()
            eliminados.append(label)

    if eliminados:
        resumen = ', '.join(eliminados)
        _log(request, 'eliminar', 'Sistema',
             f'BORRADO SELECTIVO por {request.user.username}: {resumen}')
        messages.success(request, f'✅ Se eliminaron correctamente: {resumen}.')
    else:
        messages.warning(request, '⚠️ No se eliminó ningún dato (categorías no reconocidas).')

    return redirect('perfil_usuario')


# ══════════════════════════════════════════════════════════════════════════════
# EXPORTAR A EXCEL — Consultas, Remisiones, Estudiantes, Inventario
# ══════════════════════════════════════════════════════════════════════════════

def _excel_styles():
    """Helper that returns common openpyxl style objects."""
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    thin = Side(style='thin', color='DDDDDD')
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    return {
        'title_font':   Font(bold=True, color='FFFFFF', size=13),
        'title_fill':   PatternFill('solid', fgColor='0F2444'),
        'header_font':  Font(bold=True, color='FFFFFF', size=9),
        'header_fill':  PatternFill('solid', fgColor='0E7490'),
        'alt_fill':     PatternFill('solid', fgColor='F0FAFA'),
        'center':       Alignment(horizontal='center', vertical='center', wrap_text=True),
        'left':         Alignment(horizontal='left', vertical='center', wrap_text=True),
        'border':       border,
    }


def _auto_width(ws):
    """Auto-fit column widths, skipping merged cells."""
    from openpyxl.cell.cell import MergedCell
    for col in ws.columns:
        max_len = 0
        col_letter = None
        for cell in col:
            if isinstance(cell, MergedCell):
                continue
            if col_letter is None:
                col_letter = cell.column_letter
            try:
                if cell.value:
                    max_len = max(max_len, len(str(cell.value)))
            except Exception:
                pass
        if col_letter:
            ws.column_dimensions[col_letter].width = min(max_len + 4, 50)


@login_required
def exportar_consultas_excel(request):
    import csv as _csv

    q        = request.GET.get('q', '')
    f_estado = request.GET.get('estado', '')
    f_grado  = request.GET.get('grado', '')
    f_motivo = request.GET.get('motivo', '')
    f_fecha  = request.GET.get('fecha', '')

    qs = Consulta.objects.select_related('estudiante').order_by('-fecha_hora')
    if q:
        qs = qs.filter(Q(estudiante__nombre__icontains=q) | Q(motivo__icontains=q))
    if f_estado:
        qs = qs.filter(estado=f_estado)
    if f_grado:
        qs = qs.filter(estudiante__grado=f_grado)
    if f_motivo:
        qs = qs.filter(motivo=f_motivo)
    if f_fecha:
        try:
            from datetime import datetime as _dt
            qs = qs.filter(fecha_hora__date=_dt.strptime(f_fecha, '%Y-%m-%d').date())
        except ValueError:
            pass

    resp = HttpResponse(content_type='text/csv; charset=utf-8')
    resp['Content-Disposition'] = 'attachment; filename="consultas_cosfa.csv"'
    resp.write('﻿')
    writer = _csv.writer(resp)
    writer.writerow(['#', 'Fecha', 'Hora', 'Estudiante', 'Grado', 'Motivo',
                     'Estado', 'Temperatura', 'F. Cardiaca', 'Medicamento', 'Observaciones'])
    for i, c in enumerate(qs, 1):
        writer.writerow([
            i,
            timezone.localtime(c.fecha_hora).strftime('%d/%m/%Y'),
            timezone.localtime(c.fecha_hora).strftime('%H:%M'),
            c.estudiante.nombre,
            c.estudiante.grado,
            c.get_motivo_display(),
            c.get_estado_display(),
            f'{c.temperatura}C' if c.temperatura else '',
            f'{c.frecuencia_cardiaca} lpm' if c.frecuencia_cardiaca else '',
            c.medicamento_suministrado or '',
            (c.observaciones or '')[:200],
        ])
    return resp


@login_required
def exportar_consultas_docentes_excel(request):
    import csv as _csv

    q = request.GET.get('q', '')
    qs = ConsultaDocente.objects.select_related('docente').order_by('-fecha_hora')
    if q:
        qs = qs.filter(
            Q(docente__nombre__icontains=q) |
            Q(motivo__icontains=q) |
            Q(nombre_libre__icontains=q)
        )

    resp = HttpResponse(content_type='text/csv; charset=utf-8')
    resp['Content-Disposition'] = 'attachment; filename="consultas_docentes_cosfa.csv"'
    resp.write('\ufeff')
    writer = _csv.writer(resp)
    writer.writerow(['#', 'Fecha', 'Hora atencion', 'Docente', 'Cedula', 'Area / Cargo',
                     'EPS', 'Motivo', 'Estado', 'Observaciones'])
    for i, c in enumerate(qs, 1):
        writer.writerow([
            i,
            c.fecha_hora.strftime('%d/%m/%Y') if c.fecha_hora else '',
            c.hora_atencion.strftime('%H:%M') if c.hora_atencion else '',
            c.nombre_completo,
            c.docente.cedula if c.docente else '',
            c.docente.area if c.docente else '',
            c.docente.eps if c.docente else '',
            c.get_motivo_display(),
            c.get_estado_display(),
            (c.observaciones or '')[:200],
        ])
    return resp


@login_required
def exportar_remisiones_excel(request):
    import csv as _csv

    q             = request.GET.get('q', '')
    filtro_estado = request.GET.get('estado', '')
    filtro_destino= request.GET.get('destino', '')
    filtro_fecha  = request.GET.get('fecha', '')

    qs = Remision.objects.select_related('estudiante').order_by('-fecha_hora')
    if q:
        qs = qs.filter(Q(estudiante__nombre__icontains=q) | Q(motivo__icontains=q))
    if filtro_estado:
        qs = qs.filter(estado=filtro_estado)
    if filtro_destino:
        qs = qs.filter(tipo_destino=filtro_destino)
    if filtro_fecha:
        try:
            import datetime
            qs = qs.filter(fecha_hora__date=datetime.datetime.strptime(filtro_fecha, '%Y-%m-%d').date())
        except ValueError:
            pass

    resp = HttpResponse(content_type='text/csv; charset=utf-8')
    resp['Content-Disposition'] = 'attachment; filename="remisiones_cosfa.csv"'
    resp.write('\ufeff')
    writer = _csv.writer(resp)
    writer.writerow(['#', 'Fecha', 'Estudiante', 'Grado', 'EPS', 'Destino',
                     'Hospital', 'Motivo', 'Acompanante', 'Hora Salida', 'Estado'])
    for i, r in enumerate(qs, 1):
        writer.writerow([
            i,
            timezone.localtime(r.fecha_hora).strftime('%d/%m/%Y'),
            r.estudiante.nombre,
            r.estudiante.grado,
            r.estudiante.eps or '',
            'Hospital' if r.tipo_destino == 'hospital' else 'Casa',
            r.hospital_destino or '',
            (r.motivo or '')[:150],
            r.acompanante or '',
            r.hora_salida.strftime('%H:%M') if r.hora_salida else '',
            r.estado.replace('_', ' ').title(),
        ])
    return resp


@login_required
def exportar_estudiantes_excel(request):
    import csv as _csv

    q       = request.GET.get('q', '')
    f_grado = request.GET.get('grado', '')
    f_sexo  = request.GET.get('sexo', '')

    qs = Estudiante.objects.all().order_by('grado', 'nombre')
    if q:
        qs = qs.filter(Q(nombre__icontains=q) | Q(numero_documento__icontains=q) | Q(grado__icontains=q))
    if f_grado:
        qs = qs.filter(grado=f_grado)
    if f_sexo:
        qs = qs.filter(sexo=f_sexo)

    resp = HttpResponse(content_type='text/csv; charset=utf-8')
    resp['Content-Disposition'] = 'attachment; filename="estudiantes_cosfa.csv"'
    resp.write('\ufeff')
    writer = _csv.writer(resp)
    writer.writerow(['#', 'Nombre', 'Documento', 'Grado', 'Sexo', 'Fecha Nac.',
                     'EPS', 'Tipo Sangre', 'Acudiente', 'Tel. Acudiente', 'Alergias', 'Condiciones'])
    for i, e in enumerate(qs, 1):
        writer.writerow([
            i,
            e.nombre,
            e.numero_documento or '',
            e.grado,
            e.get_sexo_display() if hasattr(e, 'get_sexo_display') else (e.sexo or ''),
            e.fecha_nacimiento.strftime('%d/%m/%Y') if e.fecha_nacimiento else '',
            e.eps or '',
            e.tipo_sangre or '',
            e.acudiente or '',
            e.telefono_acudiente or '',
            (e.alergias or '')[:100],
            (e.condiciones_medicas or '')[:100],
        ])
    return resp


@login_required
def exportar_inventario_excel(request):
    import csv as _csv

    qs = Medicamento.objects.all().order_by('categoria', 'nombre')

    resp = HttpResponse(content_type='text/csv; charset=utf-8')
    resp['Content-Disposition'] = 'attachment; filename="inventario_cosfa.csv"'
    resp.write('\ufeff')
    writer = _csv.writer(resp)
    writer.writerow(['#', 'Nombre', 'Categoria', 'Stock', 'Unidad', 'Stock Minimo',
                     'Fecha Vencimiento', 'Estado', 'Descripcion'])
    for i, m in enumerate(qs, 1):
        if m.vencido:
            estado = 'VENCIDO'
        elif m.stock_bajo:
            estado = 'Stock bajo'
        elif m.proximo_vencer:
            estado = 'Prox. a vencer'
        else:
            estado = 'OK'
        writer.writerow([
            i,
            m.nombre,
            m.get_categoria_display() if hasattr(m, 'get_categoria_display') else (m.categoria or ''),
            m.cantidad_actual,
            m.unidad or '',
            m.cantidad_minima or '',
            m.fecha_vencimiento.strftime('%d/%m/%Y') if m.fecha_vencimiento else '',
            estado,
            (m.descripcion or '')[:150],
        ])
    return resp


# ══════════════════════════════════════════════════════════════════════════════
# NUEVAS VISTAS v38
# ══════════════════════════════════════════════════════════════════════════════

# ── 1. DETALLE DE REMISIÓN ────────────────────────────────────────────────────
@login_required
def detalle_remision(request, pk):
    """Vista de solo lectura de una remisión con su consentimiento y seguimiento."""
    remision = get_object_or_404(Remision, pk=pk)
    consentimiento = getattr(remision, 'consentimiento', None)
    return render(request, 'enfermeria/detalle_remision.html', {
        'remision':      remision,
        'consentimiento': consentimiento,
    })


# ── 2. NOTIFICACIONES DE SEGUIMIENTOS VENCIDOS / PRÓXIMOS (manual) ───────────
@login_required
def notificaciones_seguimiento(request):
    """
    Envía correo a la enfermera con seguimientos vencidos y próximos a vencer.
    Se llama manualmente desde el dashboard o puede automatizarse con cron.
    """
    hoy = datetime.date.today()
    en_7_dias = hoy + datetime.timedelta(days=7)

    vencidos = Seguimiento.objects.filter(completado=False, fecha__lt=hoy).select_related('estudiante')
    proximos = Seguimiento.objects.filter(completado=False, fecha__gte=hoy, fecha__lte=en_7_dias).select_related('estudiante')

    if not vencidos.exists() and not proximos.exists():
        return _JR({'ok': True, 'mensaje': 'No hay seguimientos pendientes de notificar.'})

    correo_destino = request.user.email
    if not correo_destino:
        return _JR({'ok': False, 'mensaje': 'El usuario no tiene correo registrado. Actualízalo en Perfil.'})

    nombre_enfermera = request.user.get_full_name() or request.user.username

    # Construir cuerpo HTML del correo
    filas_vencidos = ''.join(
        f'<tr><td>{s.estudiante.nombre}</td><td>{s.estudiante.grado}</td>'
        f'<td>{s.get_tipo_display()}</td><td style="color:#dc2626;font-weight:700">{s.fecha}</td>'
        f'<td>{s.descripcion[:80]}</td></tr>'
        for s in vencidos
    )
    filas_proximos = ''.join(
        f'<tr><td>{s.estudiante.nombre}</td><td>{s.estudiante.grado}</td>'
        f'<td>{s.get_tipo_display()}</td><td style="color:#d97706;font-weight:700">{s.fecha}</td>'
        f'<td>{s.descripcion[:80]}</td></tr>'
        for s in proximos
    )
    tabla_style = 'border-collapse:collapse;width:100%;font-size:13px;'
    th_style    = 'background:#0f2444;color:white;padding:8px 12px;text-align:left;'
    td_style    = 'padding:7px 12px;border-bottom:1px solid #e2e8f0;'

    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:700px;margin:0 auto">
      <div style="background:linear-gradient(135deg,#0f2444,#1a3a6e);padding:20px 28px;border-radius:12px 12px 0 0">
        <h2 style="color:white;margin:0">📅 Alerta de Seguimientos — COSFA CURE</h2>
        <p style="color:#94a3b8;margin:6px 0 0">Generada el {hoy.strftime('%d/%m/%Y')} para {nombre_enfermera}</p>
      </div>
      <div style="background:white;padding:24px 28px;border:1px solid #e2e8f0;border-top:none;border-radius:0 0 12px 12px">
    """
    if vencidos.exists():
        html += f"""
        <h3 style="color:#dc2626;margin-top:0">🔴 Seguimientos vencidos ({vencidos.count()})</h3>
        <table style="{tabla_style}">
          <tr>{''.join(f'<th style="{th_style}">{h}</th>' for h in ['Estudiante','Grado','Tipo','Fecha','Descripción'])}</tr>
          {''.join(f'<tr>{"".join(f"<td style={td_style!r}>{c}</td>" for c in [s.estudiante.nombre, s.estudiante.grado, s.get_tipo_display(), str(s.fecha), s.descripcion[:80]])}</tr>' for s in vencidos)}
        </table><br>
        """
    if proximos.exists():
        html += f"""
        <h3 style="color:#d97706">🟡 Próximos 7 días ({proximos.count()})</h3>
        <table style="{tabla_style}">
          <tr>{''.join(f'<th style="{th_style}">{h}</th>' for h in ['Estudiante','Grado','Tipo','Fecha','Descripción'])}</tr>
          {''.join(f'<tr>{"".join(f"<td style={td_style!r}>{c}</td>" for c in [s.estudiante.nombre, s.estudiante.grado, s.get_tipo_display(), str(s.fecha), s.descripcion[:80]])}</tr>' for s in proximos)}
        </table>
        """
    html += """
        <p style="margin-top:24px;font-size:12px;color:#94a3b8">
          Este correo fue generado por COSFA CURE · Colegio San Francisco de Asís
        </p>
      </div>
    </div>
    """
    texto_plano = (
        f"Alerta de seguimientos – {hoy}\n\n"
        f"Vencidos: {vencidos.count()}\n"
        f"Próximos 7 días: {proximos.count()}\n\n"
        "Ingresa al sistema para ver el detalle."
    )
    try:
        msg = EmailMultiAlternatives(
            subject=f'📅 Alerta seguimientos COSFA CURE – {hoy.strftime("%d/%m/%Y")}',
            body=texto_plano,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[correo_destino],
        )
        msg.attach_alternative(html, 'text/html')
        msg.mixed_subtype = 'related'
        _adjuntar_logo(msg)
        msg.send()
        return _JR({
            'ok': True,
            'mensaje': f'Correo enviado a {correo_destino} con {vencidos.count()} vencidos y {proximos.count()} próximos.',
        })
    except Exception as e:
        return _JR({'ok': False, 'mensaje': f'Error al enviar: {str(e)}'})


# ── IMPORTAR / EXPORTAR DOCENTES ──────────────────────────────────────────────

@login_required
def exportar_docentes_excel(request):
    """Exporta la lista de docentes a CSV."""
    import csv as _csv

    q = request.GET.get('q', '')
    f_area = request.GET.get('area', '')
    f_activo = request.GET.get('activo', '')

    qs = Docente.objects.all().order_by('area', 'nombre')
    if q:
        qs = qs.filter(Q(nombre__icontains=q) | Q(cedula__icontains=q) | Q(area__icontains=q))
    if f_area:
        qs = qs.filter(area=f_area)
    if f_activo == 'si':
        qs = qs.filter(activo=True)
    elif f_activo == 'no':
        qs = qs.filter(activo=False)

    resp = HttpResponse(content_type='text/csv; charset=utf-8')
    resp['Content-Disposition'] = 'attachment; filename="docentes_cosfa.csv"'
    resp.write('\ufeff')
    writer = _csv.writer(resp)
    writer.writerow(['#', 'Nombre', 'Cedula', 'Area / Cargo', 'Sexo', 'Fecha Nac.',
                     'EPS', 'Tipo Sangre', 'Telefono', 'Correo', 'Alergias', 'Activo'])
    for i, d in enumerate(qs, 1):
        writer.writerow([
            i, d.nombre, d.cedula or '',
            d.get_area_display() if hasattr(d, 'get_area_display') else (d.area or ''),
            d.get_sexo_display() if hasattr(d, 'get_sexo_display') else (d.sexo or ''),
            d.fecha_nacimiento.strftime('%d/%m/%Y') if d.fecha_nacimiento else '',
            d.eps or '', d.tipo_sangre or '', d.telefono or '', d.correo or '',
            (d.alergias or '')[:100], 'Si' if d.activo else 'No',
        ])
    return resp


# ══════════════════════════════════════════════════════════════════════════════
# EXPORTAR XLSX — Botones de página (generan Excel real, no CSV)
# ══════════════════════════════════════════════════════════════════════════════

@login_required
def exportar_estudiantes_xlsx(request):
    """Exporta la lista de estudiantes a Excel (.xlsx) real con openpyxl."""
    if not OPENPYXL_OK:
        messages.error(request, 'openpyxl no instalado.')
        return redirect('lista_estudiantes')

    from openpyxl.styles import Font

    q       = request.GET.get('q', '')
    f_grado = request.GET.get('grado', '')
    f_sexo  = request.GET.get('sexo', '')

    qs = Estudiante.objects.all().order_by('grado', 'nombre')
    if q:
        qs = qs.filter(Q(nombre__icontains=q) | Q(numero_documento__icontains=q) | Q(grado__icontains=q))
    if f_grado:
        qs = qs.filter(grado=f_grado)
    if f_sexo:
        qs = qs.filter(sexo=f_sexo)

    st = _excel_styles()
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'Estudiantes'

    ws.merge_cells('A1:L1')
    t = ws['A1']
    t.value = 'COSFA CURE — Lista de Estudiantes'
    t.font = st['title_font']; t.fill = st['title_fill']; t.alignment = st['center']
    ws.row_dimensions[1].height = 28

    headers = ['#', 'Nombre', 'Documento', 'Grado', 'Sexo', 'Fecha Nac.',
               'EPS', 'Tipo Sangre', 'Acudiente', 'Tel. Acudiente', 'Alergias', 'Condiciones']
    for col, h in enumerate(headers, 1):
        c = ws.cell(row=2, column=col, value=h)
        c.font = st['header_font']; c.fill = st['header_fill']
        c.alignment = st['center']; c.border = st['border']

    for i, e in enumerate(qs, 1):
        row = i + 2
        fill = st['alt_fill'] if i % 2 == 0 else None
        vals = [
            i, e.nombre, e.numero_documento or '', e.grado,
            e.get_sexo_display() if hasattr(e, 'get_sexo_display') else (e.sexo or ''),
            e.fecha_nacimiento.strftime('%d/%m/%Y') if e.fecha_nacimiento else '',
            e.eps or '', e.tipo_sangre or '', e.acudiente or '',
            e.telefono_acudiente or '', (e.alergias or '')[:100], (e.condiciones_medicas or '')[:100],
        ]
        for col, val in enumerate(vals, 1):
            c = ws.cell(row=row, column=col, value=val)
            c.font = Font(size=9); c.alignment = st['left']; c.border = st['border']
            if fill: c.fill = fill

    _auto_width(ws)
    ws.freeze_panes = 'A3'

    resp = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    resp['Content-Disposition'] = 'attachment; filename="estudiantes_cosfa.xlsx"'
    wb.save(resp)
    return resp


@login_required
def exportar_consultas_xlsx(request):
    """Exporta consultas de estudiantes a Excel (.xlsx) real."""
    if not OPENPYXL_OK:
        messages.error(request, 'openpyxl no instalado.')
        return redirect('lista_consultas')

    from openpyxl.styles import Font

    q        = request.GET.get('q', '')
    f_estado = request.GET.get('estado', '')
    f_grado  = request.GET.get('grado', '')
    f_motivo = request.GET.get('motivo', '')
    f_fecha  = request.GET.get('fecha', '')

    qs = Consulta.objects.select_related('estudiante').order_by('-fecha_hora')
    if q:
        qs = qs.filter(Q(estudiante__nombre__icontains=q) | Q(motivo__icontains=q))
    if f_estado:
        qs = qs.filter(estado=f_estado)
    if f_grado:
        qs = qs.filter(estudiante__grado=f_grado)
    if f_motivo:
        qs = qs.filter(motivo=f_motivo)
    if f_fecha:
        try:
            from datetime import datetime as _dt
            qs = qs.filter(fecha_hora__date=_dt.strptime(f_fecha, '%Y-%m-%d').date())
        except ValueError:
            pass

    st = _excel_styles()
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'Consultas'

    ws.merge_cells('A1:K1')
    t = ws['A1']
    t.value = 'COSFA CURE — Registro de Consultas'
    t.font = st['title_font']; t.fill = st['title_fill']; t.alignment = st['center']
    ws.row_dimensions[1].height = 28

    headers = ['#', 'Fecha', 'Hora', 'Estudiante', 'Grado', 'Motivo',
               'Estado', 'Temperatura', 'F. Cardiaca', 'Medicamento', 'Observaciones']
    for col, h in enumerate(headers, 1):
        c = ws.cell(row=2, column=col, value=h)
        c.font = st['header_font']; c.fill = st['header_fill']
        c.alignment = st['center']; c.border = st['border']

    for i, con in enumerate(qs, 1):
        row = i + 2
        fill = st['alt_fill'] if i % 2 == 0 else None
        vals = [
            i,
            timezone.localtime(con.fecha_hora).strftime('%d/%m/%Y'),
            timezone.localtime(con.fecha_hora).strftime('%H:%M'),
            con.estudiante.nombre, con.estudiante.grado,
            con.get_motivo_display(), con.get_estado_display(),
            f'{con.temperatura}°C' if con.temperatura else '',
            f'{con.frecuencia_cardiaca} lpm' if con.frecuencia_cardiaca else '',
            con.medicamento_suministrado or '', (con.observaciones or '')[:200],
        ]
        for col, val in enumerate(vals, 1):
            c = ws.cell(row=row, column=col, value=val)
            c.font = Font(size=9); c.alignment = st['left']; c.border = st['border']
            if fill: c.fill = fill

    _auto_width(ws)
    ws.freeze_panes = 'A3'

    resp = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    resp['Content-Disposition'] = 'attachment; filename="consultas_cosfa.xlsx"'
    wb.save(resp)
    return resp


@login_required
def exportar_consultas_docentes_xlsx(request):
    """Exporta consultas de docentes a Excel (.xlsx) real."""
    if not OPENPYXL_OK:
        messages.error(request, 'openpyxl no instalado.')
        return redirect('lista_consultas_docentes')

    from openpyxl.styles import Font

    q = request.GET.get('q', '')
    qs = ConsultaDocente.objects.select_related('docente').order_by('-fecha_hora')
    if q:
        qs = qs.filter(
            Q(docente__nombre__icontains=q) | Q(motivo__icontains=q) | Q(nombre_libre__icontains=q)
        )

    st = _excel_styles()
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'Consultas Docentes'

    ws.merge_cells('A1:J1')
    t = ws['A1']
    t.value = 'COSFA CURE — Consultas Docentes'
    t.font = st['title_font']; t.fill = st['title_fill']; t.alignment = st['center']
    ws.row_dimensions[1].height = 28

    headers = ['#', 'Fecha', 'Hora Atención', 'Docente', 'Cédula', 'Area / Cargo',
               'EPS', 'Motivo', 'Estado', 'Observaciones']
    for col, h in enumerate(headers, 1):
        c = ws.cell(row=2, column=col, value=h)
        c.font = st['header_font']; c.fill = st['header_fill']
        c.alignment = st['center']; c.border = st['border']

    for i, con in enumerate(qs, 1):
        row = i + 2
        fill = st['alt_fill'] if i % 2 == 0 else None
        vals = [
            i,
            con.fecha_hora.strftime('%d/%m/%Y') if con.fecha_hora else '',
            con.hora_atencion.strftime('%H:%M') if con.hora_atencion else '',
            con.nombre_completo,
            con.docente.cedula if con.docente else '',
            con.docente.area if con.docente else '',
            con.docente.eps if con.docente else '',
            con.get_motivo_display(), con.get_estado_display(),
            (con.observaciones or '')[:200],
        ]
        for col, val in enumerate(vals, 1):
            c = ws.cell(row=row, column=col, value=val)
            c.font = Font(size=9); c.alignment = st['left']; c.border = st['border']
            if fill: c.fill = fill

    _auto_width(ws)
    ws.freeze_panes = 'A3'

    resp = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    resp['Content-Disposition'] = 'attachment; filename="consultas_docentes_cosfa.xlsx"'
    wb.save(resp)
    return resp


@login_required
def exportar_remisiones_xlsx(request):
    """Exporta remisiones a Excel (.xlsx) real."""
    if not OPENPYXL_OK:
        messages.error(request, 'openpyxl no instalado.')
        return redirect('lista_remisiones')

    from openpyxl.styles import Font

    q             = request.GET.get('q', '')
    filtro_estado = request.GET.get('estado', '')
    filtro_destino= request.GET.get('destino', '')
    filtro_fecha  = request.GET.get('fecha', '')

    qs = Remision.objects.select_related('estudiante').order_by('-fecha_hora')
    if q:
        qs = qs.filter(Q(estudiante__nombre__icontains=q) | Q(motivo__icontains=q))
    if filtro_estado:
        qs = qs.filter(estado=filtro_estado)
    if filtro_destino:
        qs = qs.filter(tipo_destino=filtro_destino)
    if filtro_fecha:
        try:
            import datetime as _dtmod
            qs = qs.filter(fecha_hora__date=_dtmod.datetime.strptime(filtro_fecha, '%Y-%m-%d').date())
        except ValueError:
            pass

    st = _excel_styles()
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'Remisiones'

    ws.merge_cells('A1:K1')
    t = ws['A1']
    t.value = 'COSFA CURE — Registro de Remisiones'
    t.font = st['title_font']; t.fill = st['title_fill']; t.alignment = st['center']
    ws.row_dimensions[1].height = 28

    headers = ['#', 'Fecha', 'Estudiante', 'Grado', 'EPS', 'Destino',
               'Hospital', 'Motivo', 'Acompañante', 'Hora Salida', 'Estado']
    for col, h in enumerate(headers, 1):
        c = ws.cell(row=2, column=col, value=h)
        c.font = st['header_font']; c.fill = st['header_fill']
        c.alignment = st['center']; c.border = st['border']

    for i, r in enumerate(qs, 1):
        row = i + 2
        fill = st['alt_fill'] if i % 2 == 0 else None
        vals = [
            i,
            timezone.localtime(r.fecha_hora).strftime('%d/%m/%Y'),
            r.estudiante.nombre, r.estudiante.grado, r.estudiante.eps or '',
            'Hospital' if r.tipo_destino == 'hospital' else 'Casa',
            r.hospital_destino or '', (r.motivo or '')[:150],
            r.acompanante or '',
            r.hora_salida.strftime('%H:%M') if r.hora_salida else '',
            r.estado.replace('_', ' ').title(),
        ]
        for col, val in enumerate(vals, 1):
            c = ws.cell(row=row, column=col, value=val)
            c.font = Font(size=9); c.alignment = st['left']; c.border = st['border']
            if fill: c.fill = fill

    _auto_width(ws)
    ws.freeze_panes = 'A3'

    resp = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    resp['Content-Disposition'] = 'attachment; filename="remisiones_cosfa.xlsx"'
    wb.save(resp)
    return resp


@login_required
def exportar_inventario_xlsx(request):
    """Exporta inventario a Excel (.xlsx) real."""
    if not OPENPYXL_OK:
        messages.error(request, 'openpyxl no instalado.')
        return redirect('inventario')

    from openpyxl.styles import Font, PatternFill

    qs = Medicamento.objects.all().order_by('categoria', 'nombre')

    st = _excel_styles()
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'Inventario'

    ws.merge_cells('A1:I1')
    t = ws['A1']
    t.value = 'COSFA CURE — Inventario de Medicamentos'
    t.font = st['title_font']; t.fill = st['title_fill']; t.alignment = st['center']
    ws.row_dimensions[1].height = 28

    headers = ['#', 'Nombre', 'Categoría', 'Stock', 'Unidad', 'Stock Mínimo',
               'Fecha Vencimiento', 'Estado', 'Descripción']
    for col, h in enumerate(headers, 1):
        c = ws.cell(row=2, column=col, value=h)
        c.font = st['header_font']; c.fill = st['header_fill']
        c.alignment = st['center']; c.border = st['border']

    rojo  = PatternFill('solid', fgColor='FEE2E2')
    ambar = PatternFill('solid', fgColor='FEF9C3')

    for i, m in enumerate(qs, 1):
        row = i + 2
        if m.vencido:
            estado = 'VENCIDO'; row_fill = rojo
        elif m.stock_bajo:
            estado = 'Stock bajo'; row_fill = ambar
        elif m.proximo_vencer:
            estado = 'Próx. a vencer'; row_fill = ambar
        else:
            estado = 'OK'; row_fill = st['alt_fill'] if i % 2 == 0 else None

        vals = [
            i, m.nombre,
            m.get_categoria_display() if hasattr(m, 'get_categoria_display') else (m.categoria or ''),
            m.cantidad_actual, m.unidad or '', m.cantidad_minima or '',
            m.fecha_vencimiento.strftime('%d/%m/%Y') if m.fecha_vencimiento else '',
            estado, (m.descripcion or '')[:150],
        ]
        for col, val in enumerate(vals, 1):
            c = ws.cell(row=row, column=col, value=val)
            c.font = Font(size=9); c.alignment = st['left']; c.border = st['border']
            if row_fill: c.fill = row_fill

    _auto_width(ws)
    ws.freeze_panes = 'A3'

    resp = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    resp['Content-Disposition'] = 'attachment; filename="inventario_cosfa.xlsx"'
    wb.save(resp)
    return resp


@login_required
def exportar_docentes_xlsx(request):
    """Exporta lista de docentes a Excel (.xlsx) real."""
    if not OPENPYXL_OK:
        messages.error(request, 'openpyxl no instalado.')
        return redirect('lista_docentes')

    from openpyxl.styles import Font

    q        = request.GET.get('q', '')
    f_area   = request.GET.get('area', '')
    f_activo = request.GET.get('activo', '')

    qs = Docente.objects.all().order_by('area', 'nombre')
    if q:
        qs = qs.filter(Q(nombre__icontains=q) | Q(cedula__icontains=q) | Q(area__icontains=q))
    if f_area:
        qs = qs.filter(area=f_area)
    if f_activo == 'si':
        qs = qs.filter(activo=True)
    elif f_activo == 'no':
        qs = qs.filter(activo=False)

    st = _excel_styles()
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'Docentes'

    ws.merge_cells('A1:L1')
    t = ws['A1']
    t.value = 'COSFA CURE — Lista de Docentes'
    t.font = st['title_font']; t.fill = st['title_fill']; t.alignment = st['center']
    ws.row_dimensions[1].height = 28

    headers = ['#', 'Nombre', 'Cédula', 'Area / Cargo', 'Sexo', 'Fecha Nac.',
               'EPS', 'Tipo Sangre', 'Teléfono', 'Correo', 'Alergias', 'Activo']
    for col, h in enumerate(headers, 1):
        c = ws.cell(row=2, column=col, value=h)
        c.font = st['header_font']; c.fill = st['header_fill']
        c.alignment = st['center']; c.border = st['border']

    for i, d in enumerate(qs, 1):
        row = i + 2
        fill = st['alt_fill'] if i % 2 == 0 else None
        vals = [
            i, d.nombre, d.cedula or '',
            d.get_area_display() if hasattr(d, 'get_area_display') else (d.area or ''),
            d.get_sexo_display() if hasattr(d, 'get_sexo_display') else (d.sexo or ''),
            d.fecha_nacimiento.strftime('%d/%m/%Y') if d.fecha_nacimiento else '',
            d.eps or '', d.tipo_sangre or '', d.telefono or '', d.correo or '',
            (d.alergias or '')[:100], 'Sí' if d.activo else 'No',
        ]
        for col, val in enumerate(vals, 1):
            c = ws.cell(row=row, column=col, value=val)
            c.font = Font(size=9); c.alignment = st['left']; c.border = st['border']
            if fill: c.fill = fill

    _auto_width(ws)
    ws.freeze_panes = 'A3'

    resp = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    resp['Content-Disposition'] = 'attachment; filename="docentes_cosfa.xlsx"'
    wb.save(resp)
    return resp



@login_required
def plantilla_importar_estudiantes(request):
    """Descarga la plantilla Excel para carga masiva de estudiantes."""
    if not OPENPYXL_OK:
        messages.error(request, 'openpyxl no instalado.')
        return redirect('lista_estudiantes')

    st = _excel_styles()
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'Plantilla Estudiantes'

    ws.merge_cells('A1:L1')
    t = ws['A1']
    t.value = 'COSFA CURE — Plantilla de Importación de Estudiantes'
    t.font = st['title_font']; t.fill = st['title_fill']; t.alignment = st['center']
    ws.row_dimensions[1].height = 28

    headers = ['nombre*', 'numero_documento', 'grado*', 'sexo (M/F/O)',
               'fecha_nacimiento (YYYY-MM-DD)', 'eps', 'tipo_sangre',
               'acudiente', 'telefono_acudiente', 'alergias', 'condiciones_medicas', 'correo_acudiente']
    for col, h in enumerate(headers, 1):
        c = ws.cell(row=2, column=col, value=h)
        c.font = st['header_font']; c.fill = st['header_fill']
        c.alignment = st['center']; c.border = st['border']

    # Fila de ejemplo
    ejemplo = ['Juan Pérez López', '1001234567', '9A', 'M', '2010-03-15',
               'Sura EPS', 'O+', 'María López', '3001234567', 'Ninguna', 'Ninguna', 'maria@email.com']
    for col, val in enumerate(ejemplo, 1):
        cell = ws.cell(row=3, column=col, value=val)
        cell.fill = st['alt_fill']; cell.border = st['border']; cell.alignment = st['left']

    # Instrucciones
    ws2 = wb.create_sheet('Instrucciones')
    instrucciones = [
        ('Campos', 'Descripción'),
        ('nombre*', 'Nombre completo del estudiante (OBLIGATORIO)'),
        ('numero_documento', 'Número de documento de identidad'),
        ('grado*', 'Ej: 6A, 7B, 8C, 9A, 10B, 11A (OBLIGATORIO)'),
        ('sexo', 'M = Masculino, F = Femenino, O = Otro'),
        ('fecha_nacimiento', 'Formato: AAAA-MM-DD  Ej: 2010-03-15'),
        ('eps', 'Nombre de la EPS o aseguradora'),
        ('tipo_sangre', 'A+, A-, B+, B-, AB+, AB-, O+, O-'),
        ('acudiente', 'Nombre completo del acudiente'),
        ('telefono_acudiente', 'Número de teléfono del acudiente'),
        ('alergias', 'Alergias conocidas (o dejar vacío)'),
        ('condiciones_medicas', 'Condiciones médicas (o dejar vacío)'),
        ('correo_acudiente', 'Correo electrónico del acudiente'),
    ]
    for row, (campo, desc) in enumerate(instrucciones, 1):
        ws2.cell(row=row, column=1, value=campo)
        ws2.cell(row=row, column=2, value=desc)
    ws2.column_dimensions['A'].width = 25
    ws2.column_dimensions['B'].width = 55

    _auto_width(ws)
    resp = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    resp['Content-Disposition'] = 'attachment; filename="plantilla_importar_estudiantes.xlsx"'
    wb.save(resp)
    return resp


@admin_required
def importar_estudiantes_excel(request):
    """Carga masiva de estudiantes desde Excel."""
    if request.method != 'POST':
        return redirect('lista_estudiantes')
    if not OPENPYXL_OK:
        messages.error(request, 'openpyxl no instalado.')
        return redirect('lista_estudiantes')

    archivo = request.FILES.get('archivo_excel')
    if not archivo:
        messages.error(request, 'No se seleccionó ningún archivo.')
        return redirect('lista_estudiantes')

    try:
        import io
        wb = openpyxl.load_workbook(io.BytesIO(archivo.read()), data_only=True)
        ws = wb.active
        creados = 0
        errores = []
        # Detectar si la fila 2 tiene encabezados para saber si hay columna # al inicio
        # Columnas del archivo exportado: #, Nombre, Documento, Grado, Sexo, Fecha Nac., EPS, Tipo Sangre, Acudiente, Tel. Acudiente, Alergias, Condiciones
        # col indices (0-based):          0   1        2          3      4     5            6    7            8          9               10        11
        from datetime import datetime as _dt
        for i, row in enumerate(ws.iter_rows(min_row=3, values_only=True), start=3):
            if not row or all(v is None for v in row):
                continue
            # Detectar si primera columna es número de fila (#) o nombre
            if row[0] is not None and not str(row[0]).strip().replace('.','').isdigit():
                # No hay columna #, nombre está en col 0
                offset = -1
            else:
                offset = 0  # hay columna # en col 0, nombre en col 1
            def col(n):
                idx = n + offset
                return row[idx] if 0 <= idx < len(row) else None
            nombre = str(col(1)).strip() if col(1) else ''
            grado  = str(col(3)).strip() if col(3) else ''
            if not nombre or not grado:
                errores.append(f'Fila {i}: nombre y grado son obligatorios.')
                continue
            fecha_nac = None
            raw_fecha = col(5)
            if raw_fecha:
                try:
                    if hasattr(raw_fecha, 'year'):
                        fecha_nac = raw_fecha.date() if hasattr(raw_fecha, 'date') else raw_fecha
                    else:
                        s = str(raw_fecha).strip()
                        for fmt in ('%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y', '%Y/%m/%d'):
                            try:
                                fecha_nac = _dt.strptime(s, fmt).date()
                                break
                            except ValueError:
                                pass
                except Exception:
                    pass
            Estudiante.objects.get_or_create(
                nombre=nombre,
                defaults={
                    'numero_documento':   str(col(2)).strip() if col(2) else '',
                    'grado':              grado,
                    'sexo':               str(col(4)).strip().upper() if col(4) else '',
                    'fecha_nacimiento':   fecha_nac,
                    'eps':                str(col(6)).strip() if col(6) else '',
                    'tipo_sangre':        str(col(7)).strip() if col(7) else '',
                    'acudiente':          str(col(8)).strip() if col(8) else '',
                    'telefono_acudiente': str(col(9)).strip() if col(9) else '',
                    'alergias':           str(col(10)).strip() if col(10) else '',
                    'condiciones_medicas':str(col(11)).strip() if col(11) else '',
                    'correo_acudiente':   str(col(12)).strip() if col(12) else '',
                }
            )
            creados += 1
        if errores:
            messages.warning(request, f'Se importaron {creados} estudiantes. Errores: {"; ".join(errores[:3])}')
        else:
            messages.success(request, f'✅ Se importaron {creados} estudiantes correctamente.')
        _log(request, 'importar', 'Estudiante', f'Importación masiva: {creados} registros')
    except Exception as e:
        messages.error(request, f'Error al leer el archivo: {e}')
    return redirect('lista_estudiantes')


@login_required
def plantilla_importar_docentes(request):
    """Descarga la plantilla Excel para carga masiva de docentes."""
    if not OPENPYXL_OK:
        messages.error(request, 'openpyxl no instalado.')
        return redirect('lista_docentes')

    st = _excel_styles()
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'Plantilla Docentes'

    ws.merge_cells('A1:L1')
    t = ws['A1']
    t.value = 'COSFA CURE — Plantilla de Importación de Docentes'
    t.font = st['title_font']; t.fill = st['title_fill']; t.alignment = st['center']
    ws.row_dimensions[1].height = 28

    headers = ['nombre*', 'cedula*', 'fecha_nacimiento (YYYY-MM-DD)', 'sexo (M/F/O)',
               'area*', 'grados_asignados', 'vinculacion', 'telefono*', 'correo',
               'eps', 'tipo_sangre', 'alergias']
    for col, h in enumerate(headers, 1):
        c = ws.cell(row=2, column=col, value=h)
        c.font = st['header_font']; c.fill = st['header_fill']
        c.alignment = st['center']; c.border = st['border']

    ejemplo = ['Carlos Gómez', '12345678', '1980-05-20', 'M', 'matematicas',
               '9A, 10B, 11A', 'planta', '3009876543', 'c.gomez@colegio.edu.co',
               'Compensar', 'A+', 'Ninguna']
    for col, val in enumerate(ejemplo, 1):
        cell = ws.cell(row=3, column=col, value=val)
        cell.fill = st['alt_fill']; cell.border = st['border']; cell.alignment = st['left']

    _auto_width(ws)
    resp = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    resp['Content-Disposition'] = 'attachment; filename="plantilla_importar_docentes.xlsx"'
    wb.save(resp)
    return resp


@admin_required
def importar_docentes_excel(request):
    """Carga masiva de docentes desde Excel."""
    if request.method != 'POST':
        return redirect('lista_docentes')
    if not OPENPYXL_OK:
        messages.error(request, 'openpyxl no instalado.')
        return redirect('lista_docentes')

    archivo = request.FILES.get('archivo_excel')
    if not archivo:
        messages.error(request, 'No se seleccionó ningún archivo.')
        return redirect('lista_docentes')

    try:
        import io
        wb = openpyxl.load_workbook(io.BytesIO(archivo.read()), data_only=True)
        ws = wb.active
        creados = 0
        errores = []
        for i, row in enumerate(ws.iter_rows(min_row=3, values_only=True), start=3):
            if not row or not row[0]:
                continue
            nombre = str(row[0]).strip()
            cedula = str(row[1]).strip() if row[1] else ''
            area = str(row[4]).strip() if row[4] else ''
            telefono = str(row[7]).strip() if row[7] else ''
            if not nombre or not cedula or not area:
                errores.append(f'Fila {i}: nombre, cédula y área son obligatorios.')
                continue
            fecha_nac = None
            if row[2]:
                try:
                    from datetime import datetime as _dt
                    if isinstance(row[2], str):
                        fecha_nac = _dt.strptime(row[2], '%Y-%m-%d').date()
                    else:
                        fecha_nac = row[2] if hasattr(row[2], 'year') else datetime.date.today()
                except Exception:
                    fecha_nac = datetime.date.today()
            Docente.objects.get_or_create(
                cedula=cedula,
                defaults={
                    'nombre': nombre,
                    'fecha_nacimiento': fecha_nac or datetime.date.today(),
                    'sexo': str(row[3]).strip().upper() if row[3] else '',
                    'area': area,
                    'grados_asignados': str(row[5]).strip() if row[5] else '',
                    'vinculacion': str(row[6]).strip() if row[6] else '',
                    'telefono': telefono,
                    'correo': str(row[8]).strip() if row[8] else '',
                    'eps': str(row[9]).strip() if row[9] else '',
                    'tipo_sangre': str(row[10]).strip() if row[10] else '',
                    'alergias': str(row[11]).strip() if row[11] else '',
                    'activo': True,
                }
            )
            creados += 1
        if errores:
            messages.warning(request, f'Se importaron {creados} docentes. Errores: {"; ".join(errores[:3])}')
        else:
            messages.success(request, f'✅ Se importaron {creados} docentes correctamente.')
        _log(request, 'importar', 'Docente', f'Importación masiva: {creados} registros')
    except Exception as e:
        messages.error(request, f'Error al leer el archivo: {e}')
    return redirect('lista_docentes')


# ── BÚSQUEDA EN TIEMPO REAL (AJAX) ────────────────────────────────────────────

@login_required
def api_buscar_consultas(request):
    """JSON para búsqueda en tiempo real de consultas."""
    q = request.GET.get('q', '').strip()
    f_estado = request.GET.get('estado', '')
    f_grado = request.GET.get('grado', '')
    f_motivo = request.GET.get('motivo', '')
    f_fecha = request.GET.get('fecha', '')

    qs = Consulta.objects.select_related('estudiante').order_by('-fecha_hora')
    if q:
        qs = qs.filter(Q(estudiante__nombre__icontains=q) | Q(motivo__icontains=q))
    if f_estado:
        qs = qs.filter(estado=f_estado)
    if f_grado:
        qs = qs.filter(estudiante__grado=f_grado)
    if f_motivo:
        qs = qs.filter(motivo=f_motivo)
    if f_fecha:
        try:
            from datetime import datetime as _dt
            qs = qs.filter(fecha_hora__date=_dt.strptime(f_fecha, '%Y-%m-%d').date())
        except ValueError:
            pass

    motivos_dict = dict(Consulta.MOTIVO_CHOICES)
    estados_dict = dict(Consulta.ESTADO_CHOICES)
    resultados = []
    for c in qs[:50]:
        resultados.append({
            'pk': c.pk,
            'estudiante': c.estudiante.nombre,
            'grado': c.estudiante.grado,
            'motivo': motivos_dict.get(c.motivo, c.motivo),
            'estado': estados_dict.get(c.estado, c.estado),
            'fecha': timezone.localtime(c.fecha_hora).strftime('%d/%m/%Y %H:%M'),
            'url': f'/consultas/{c.pk}/',
        })
    return JsonResponse({'resultados': resultados, 'total': qs.count()})


@login_required
def api_buscar_remisiones(request):
    """JSON para búsqueda en tiempo real de remisiones."""
    q = request.GET.get('q', '').strip()
    filtro_estado = request.GET.get('estado', '')
    filtro_destino = request.GET.get('destino', '')
    filtro_fecha = request.GET.get('fecha', '')

    qs = Remision.objects.select_related('estudiante').order_by('-fecha_hora')
    if q:
        qs = qs.filter(Q(estudiante__nombre__icontains=q) | Q(motivo__icontains=q) | Q(hospital_destino__icontains=q))
    if filtro_estado:
        qs = qs.filter(estado=filtro_estado)
    if filtro_destino:
        qs = qs.filter(tipo_destino=filtro_destino)
    if filtro_fecha:
        try:
            import datetime
            qs = qs.filter(fecha_hora__date=datetime.datetime.strptime(filtro_fecha, '%Y-%m-%d').date())
        except ValueError:
            pass

    estados_dict = dict(Remision.ESTADO_CHOICES) if hasattr(Remision, 'ESTADO_CHOICES') else {}
    resultados = []
    for r in qs[:50]:
        resultados.append({
            'pk': r.pk,
            'estudiante': r.estudiante.nombre,
            'grado': r.estudiante.grado,
            'motivo': r.motivo or '—',
            'estado': estados_dict.get(r.estado, r.estado) if r.estado else '—',
            'destino': 'Casa' if r.tipo_destino == 'casa' else (r.hospital_destino or 'Hospital'),
            'fecha': timezone.localtime(r.fecha_hora).strftime('%d/%m/%Y %H:%M'),
            'url': f'/remisiones/{r.pk}/detalle/',
        })
    return JsonResponse({'resultados': resultados, 'total': qs.count()})


# ══════════════════════════════════════════════════════════════════
# GESTIÓN DE GRADOS ESCOLARES
# ══════════════════════════════════════════════════════════════════

@login_required
def grados_lista(request):
    """Lista de grados con opción de crear / borrar."""
    grados = GradoEscolar.objects.order_by('orden', 'nombre')
    return render(request, 'enfermeria/grados_lista.html', {'grados': grados})


@login_required
def crear_grado(request):
    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip().upper()
        orden  = request.POST.get('orden', 0)
        if not nombre:
            messages.error(request, 'El nombre del grado no puede estar vacío.')
            return redirect('grados_lista')
        if GradoEscolar.objects.filter(nombre=nombre).exists():
            messages.warning(request, f'El grado "{nombre}" ya existe.')
            return redirect('grados_lista')
        GradoEscolar.objects.create(nombre=nombre, orden=int(orden or 0))
        _log(request, 'crear', 'GradoEscolar', f'Creado grado: {nombre}')
        messages.success(request, f'Grado "{nombre}" creado exitosamente.')
    return redirect('grados_lista')


@admin_required
def eliminar_grado(request, pk):
    grado = get_object_or_404(GradoEscolar, pk=pk)
    if request.method == 'POST':
        if Estudiante.objects.filter(grado=grado.nombre, estado_academico='activo').exists():
            messages.error(request, f'No se puede eliminar "{grado.nombre}": tiene estudiantes activos asignados.')
            return redirect('grados_lista')
        nombre = grado.nombre
        grado.delete()
        _log(request, 'eliminar', 'GradoEscolar', f'Eliminado grado: {nombre}')
        messages.success(request, f'Grado "{nombre}" eliminado.')
    return redirect('grados_lista')


@login_required
def toggle_grado(request, pk):
    """Activa / desactiva un grado sin borrarlo."""
    grado = get_object_or_404(GradoEscolar, pk=pk)
    grado.activo = not grado.activo
    grado.save()
    estado = 'activado' if grado.activo else 'desactivado'
    messages.success(request, f'Grado "{grado.nombre}" {estado}.')
    return redirect('grados_lista')


# ══════════════════════════════════════════════════════════════════
# PROMOCIÓN / CAMBIO DE AÑO DE ESTUDIANTES
# ══════════════════════════════════════════════════════════════════

@login_required
def promocion_anio(request):
    """Vista para promover, cambiar de grado, graduar o retirar estudiantes."""
    grados = GradoEscolar.objects.filter(activo=True).order_by('orden', 'nombre')
    # Construir mapa grado→siguiente usando orden
    grado_list = list(grados)
    siguiente_grado = {}
    for i, g in enumerate(grado_list):
        if i + 1 < len(grado_list):
            siguiente_grado[g.nombre] = grado_list[i + 1].nombre
        else:
            siguiente_grado[g.nombre] = None  # último grado → graduación

    f_grado = request.GET.get('grado', '')
    estudiantes = Estudiante.objects.filter(estado_academico='activo').order_by('grado', 'nombre')
    if f_grado:
        estudiantes = estudiantes.filter(grado=f_grado)

    anio_actual = datetime.date.today().year

    return render(request, 'enfermeria/promocion_anio.html', {
        'estudiantes': estudiantes,
        'grados': grados,
        'f_grado': f_grado,
        'siguiente_grado': siguiente_grado,
        'anio_actual': anio_actual,
        'estado_choices': Estudiante.ESTADO_ACADEMICO_CHOICES,
    })


@login_required
def promover_estudiante(request, pk):
    """Sube de grado un estudiante individualmente."""
    est = get_object_or_404(Estudiante, pk=pk)
    if request.method == 'POST':
        nuevo_grado  = request.POST.get('nuevo_grado', '').strip()
        nuevo_estado = request.POST.get('estado_academico', 'activo')
        nuevo_anio   = request.POST.get('anio_lectivo', '')
        grado_anterior = est.grado

        if nuevo_grado:
            est.grado = nuevo_grado
        est.estado_academico = nuevo_estado
        if nuevo_anio:
            try:
                est.anio_lectivo = int(nuevo_anio)
            except ValueError:
                pass
        est.save()
        _log(request, 'editar', 'Estudiante',
             f'Promoción: {est.nombre} — grado {grado_anterior}→{est.grado} | estado: {est.estado_academico}')
        messages.success(request, f'"{est.nombre}" actualizado: grado {est.grado}, estado {est.get_estado_academico_display()}.')
    return redirect('promocion_anio')


@login_required
def promover_masivo(request):
    """Sube de grado a todos los estudiantes de un grado específico."""
    if request.method == 'POST':
        grado_origen  = request.POST.get('grado_origen', '')
        grado_destino = request.POST.get('grado_destino', '')
        nuevo_estado  = request.POST.get('estado_masivo', 'activo')
        nuevo_anio    = request.POST.get('anio_lectivo_masivo', '')
        ids_sel       = request.POST.getlist('ids_estudiantes')

        if not grado_origen:
            messages.error(request, 'Debes seleccionar un grado de origen.')
            return redirect('promocion_anio')

        qs = Estudiante.objects.filter(estado_academico='activo', grado=grado_origen)
        if ids_sel:
            qs = qs.filter(pk__in=ids_sel)

        kwargs = {'estado_academico': nuevo_estado}
        if grado_destino:
            kwargs['grado'] = grado_destino
        if nuevo_anio:
            try:
                kwargs['anio_lectivo'] = int(nuevo_anio)
            except ValueError:
                pass

        count = qs.count()
        qs.update(**kwargs)
        _log(request, 'editar', 'Estudiante',
             f'Promoción masiva: {count} estudiantes de {grado_origen} → grado {grado_destino or "(sin cambio)"} / estado {nuevo_estado}')
        messages.success(request, f'{count} estudiante(s) actualizados exitosamente.')
    return redirect('promocion_anio')


# ═══════════════════════════════════════════════════════
#  NOTIFICACIONES — API y vistas
# ═══════════════════════════════════════════════════════

@login_required
def api_notificaciones(request):
    """Devuelve las últimas 30 notificaciones del usuario en JSON."""
    notifs_qs = Notificacion.objects.filter(usuario=request.user).order_by('-fecha')
    no_leidas = notifs_qs.filter(leida=False).count()
    notifs = notifs_qs[:30]
    data = [
        {
            'id':      n.id,
            'tipo':    n.tipo,
            'titulo':  n.titulo,
            'mensaje': n.mensaje,
            'url':     n.url,
            'leida':   n.leida,
            'fecha':   n.fecha.strftime('%d/%m/%Y %H:%M'),
        }
        for n in notifs
    ]
    return JsonResponse({'no_leidas': no_leidas, 'notificaciones': data})


@login_required
def marcar_notificacion_leida(request, pk):
    """Marca una notificación como leída."""
    n = get_object_or_404(Notificacion, pk=pk, usuario=request.user)
    n.leida = True
    n.save(update_fields=['leida'])
    return JsonResponse({'ok': True})


@login_required
def marcar_todas_leidas(request):
    """Marca todas las notificaciones del usuario como leídas."""
    if request.method == 'POST':
        Notificacion.objects.filter(usuario=request.user, leida=False).update(leida=True)
    return JsonResponse({'ok': True})


@admin_required
def borrar_todas_notificaciones(request):
    """Elimina todas las notificaciones del usuario."""
    if request.method == 'POST':
        Notificacion.objects.filter(usuario=request.user).delete()
    return JsonResponse({'ok': True})


@admin_required
def borrar_notificacion_individual(request, pk):
    """Elimina una sola notificación del usuario."""
    if request.method == 'POST':
        Notificacion.objects.filter(pk=pk, usuario=request.user).delete()
    return JsonResponse({'ok': True})


# ═══════════════════════════════════════════════════════
#  CORREO AL COORDINADOR
# ═══════════════════════════════════════════════════════
@login_required
def enviar_correo_coordinador(request):
    """Envía un correo al coordinador y guarda el registro."""
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Método no permitido'}, status=405)

    correo_dest = request.POST.get('correo_dest', '').strip()
    motivo      = request.POST.get('motivo', '').strip()
    motivo_otro = request.POST.get('motivo_otro', '').strip()
    asunto      = request.POST.get('asunto', '').strip()
    cuerpo      = request.POST.get('cuerpo', '').strip()
    adjuntos    = request.FILES.getlist('adjuntos')

    if not all([correo_dest, motivo, asunto, cuerpo]):
        return JsonResponse({'ok': False, 'error': 'Todos los campos son obligatorios.'})

    import re
    if not re.match(r'^[^\s@]+@[^\s@]+\.[^\s@]+$', correo_dest):
        return JsonResponse({'ok': False, 'error': f'El correo "{correo_dest}" no es válido. Verifica que tenga el formato correcto (ej: nombre@gmail.com).'})

    motivo_display = motivo_otro if motivo == 'otro' and motivo_otro else dict(CorreoCoordinador.MOTIVO_CHOICES).get(motivo, motivo)

    registro = CorreoCoordinador(
        remitente   = request.user,
        correo_dest = correo_dest,
        motivo      = motivo,
        asunto      = asunto,
        cuerpo      = cuerpo,
    )

    nombre_enfermera = request.user.get_full_name() or request.user.username
    try:
        token_track = _crear_registro_tracking(
            tipo='coordinador',
            destinatario_email=correo_dest,
            destinatario_nombre='Coordinador/a',
            enviado_por=request.user,
            objeto_id=registro.pk if registro.pk else None,
            objeto_tipo='CorreoCoordinador',
        )
        pixel_url_track, confirm_url_track = _get_tracking_urls(token_track, request)
        cuerpo_html = render_to_string('enfermeria/emails/correo_coordinador.html', {
            'nombre_enfermera': nombre_enfermera,
            'correo_remitente': request.user.email or 'sin correo',
            'motivo_display':   motivo_display,
            'asunto':           asunto,
            'cuerpo':           cuerpo,
            'fecha_hora':       timezone.now().strftime('%d/%m/%Y %H:%M'),
            'pixel_url':        pixel_url_track,
            'confirm_url':      confirm_url_track,
        })
        email = EmailMultiAlternatives(
            subject   = f'[COSFA CURE] {asunto}',
            body      = cuerpo,
            from_email= settings.DEFAULT_FROM_EMAIL,
            to        = [correo_dest],
            reply_to  = [request.user.email] if request.user.email else [],
        )
        email.attach_alternative(cuerpo_html, 'text/html')
        email.mixed_subtype = 'related'
        _adjuntar_logo(email)

        EXTENSIONES_PERMITIDAS = {'jpg','jpeg','png','gif','webp','csv','xlsx','xls'}
        MAX_SIZE = 10 * 1024 * 1024
        for archivo in adjuntos:
            ext = archivo.name.rsplit('.', 1)[-1].lower() if '.' in archivo.name else ''
            if ext not in EXTENSIONES_PERMITIDAS or archivo.size > MAX_SIZE:
                continue
            email.attach(archivo.name, archivo.read(), archivo.content_type)

        email.send(fail_silently=False)
        registro.enviado = True
    except Exception as e:
        registro.error_msg = str(e)
        registro.save()
        return JsonResponse({'ok': False, 'error': f'Error al enviar: {str(e)}'})

    registro.save()

    # Crear notificación interna de confirmación
    Notificacion.objects.create(
        usuario = request.user,
        tipo    = 'sistema',
        titulo  = '✉️ Correo enviado al coordinador',
        mensaje = f'Motivo: {dict(CorreoCoordinador.MOTIVO_CHOICES).get(motivo, motivo)} | Asunto: {asunto}',
    )

    return JsonResponse({'ok': True, 'msg': f'Correo enviado exitosamente a {correo_dest}.'})


# ═══════════════════════════════════════════════════════════════════════════════
# TRACKING DE APERTURA DE CORREOS
# ═══════════════════════════════════════════════════════════════════════════════

def tracking_pixel(request, token):
    """Devuelve GIF 1x1 transparente y registra la apertura automáticamente."""
    GIF = (
        b'\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00'
        b'\xff\xff\xff\x00\x00\x00\x21\xf9\x04\x00\x00\x00\x00\x00'
        b'\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02\x44\x01\x00\x3b'
    )
    _registrar_apertura(token, metodo='pixel', request=request)
    return HttpResponse(GIF, content_type='image/gif')


def tracking_confirmar(request, token):
    """Página de confirmación manual cuando el destinatario hace clic en 'Confirmar recepción'."""
    reg = _registrar_apertura(token, metodo='confirmacion', request=request)
    if reg is None:
        return HttpResponse(
            '<html><body style="font-family:sans-serif;text-align:center;padding:60px">'
            '<h2>Enlace no valido o ya procesado.</h2></body></html>',
            content_type='text/html'
        )
    nombre = reg.destinatario_nombre or reg.destinatario_email
    html = (
        '<!DOCTYPE html><html><head><meta charset="UTF-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>Recepcion confirmada - COSFA CURE</title></head>'
        '<body style="margin:0;padding:0;background:#EBF4F8;font-family:Segoe UI,sans-serif;'
        'display:flex;align-items:center;justify-content:center;min-height:100vh">'
        '<div style="background:#fff;border-radius:16px;padding:48px 40px;text-align:center;'
        'max-width:400px;box-shadow:0 4px 24px rgba(0,60,120,.12)">'
        '<div style="font-size:56px;margin-bottom:16px">&#x2705;</div>'
        '<h1 style="color:#003366;font-size:22px;margin:0 0 12px">Recepcion confirmada</h1>'
        f'<p style="color:#4A5568;font-size:14px;margin:0 0 8px">Gracias, <strong>{nombre}</strong>.</p>'
        '<p style="color:#718096;font-size:13px;margin:0">Hemos registrado que recibiste este correo de<br>'
        '<strong>COSFA CURE &ndash; Colegio San Francisco de Asis</strong>.</p>'
        '<p style="color:#94A3B8;font-size:11px;margin:32px 0 0">Puedes cerrar esta ventana.</p>'
        '</div></body></html>'
    )
    return HttpResponse(html, content_type='text/html')


@login_required
def historial_correos_tracking(request):
    """Historial de aperturas de correos para usuarios del sistema."""
    registros = RegistroAperturaCorreo.objects.select_related('enviado_por').order_by('-fecha_envio')[:200]
    return render(request, 'enfermeria/historial_tracking.html', {'registros': registros})


# ═══════════════════════════════════════════════════════════════════════════════
# NUEVAS FUNCIONES v18  (6 mejoras del backlog)
# ═══════════════════════════════════════════════════════════════════════════════

# ── 1. REAGENDAR SEGUIMIENTO DESDE EL CALENDARIO (AJAX) ──────────────────────
@login_required
def reagendar_seguimiento(request, pk):
    """
    AJAX POST: cambia la fecha (y opcionalmente fecha_fin) de un seguimiento
    directamente desde el modal del calendario, sin abrir el formulario completo.
    Body JSON: { "fecha": "YYYY-MM-DD", "fecha_fin": "YYYY-MM-DD" (opcional) }
    """
    from django.http import JsonResponse
    import json as _json

    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)

    s = get_object_or_404(Seguimiento, pk=pk)
    try:
        data       = _json.loads(request.body)
        nueva_fecha = datetime.date.fromisoformat(data.get('fecha', ''))
    except (ValueError, KeyError):
        return JsonResponse({'error': 'Fecha inválida. Usa formato YYYY-MM-DD.'}, status=400)

    fecha_fin_str = data.get('fecha_fin', '')
    if fecha_fin_str:
        try:
            s.fecha_fin = datetime.date.fromisoformat(fecha_fin_str)
        except ValueError:
            return JsonResponse({'error': 'fecha_fin inválida.'}, status=400)

    # Si la fecha nueva es futura, reactivar el seguimiento (deja de estar vencido)
    if nueva_fecha >= datetime.date.today() and s.completado is False:
        pass  # solo actualizamos fecha
    s.fecha = nueva_fecha
    s.save()

    _log(request, 'editar', 'Seguimiento',
         f'Reagendado desde calendario: {s.estudiante.nombre} – {s.get_tipo_display()} → {nueva_fecha}')

    return JsonResponse({
        'ok': True,
        'msg': f'Seguimiento reagendado para el {nueva_fecha.strftime("%d/%m/%Y")}.',
        'nueva_fecha': nueva_fecha.isoformat(),
        'estudiante': s.estudiante.nombre,
        'tipo': s.get_tipo_display(),
    })


# ── 2 & 3. REPORTE FRECUENTES + GRÁFICA MOTIVOS (API JSON para el frontend) ──
@login_required
def api_reporte_frecuentes(request):
    """
    Devuelve JSON con:
      - top 10 estudiantes más frecuentes en los últimos N días (default 30)
      - distribución de motivos (para pie/bar chart)
      - comparativo mes a mes (últimos 6 meses) automático
    Parámetros GET: dias=30 | tipo=estudiantes|docentes
    """
    from django.http import JsonResponse

    dias = int(request.GET.get('dias', 30))
    tipo = request.GET.get('tipo', 'estudiantes')
    desde = datetime.date.today() - datetime.timedelta(days=dias)

    if tipo == 'docentes':
        qs_base = ConsultaDocente.objects.all()
        frecuentes_raw = (
            qs_base.filter(fecha_hora__date__gte=desde)
            .values('docente__id', 'docente__nombre', 'docente__area')
            .annotate(visitas=Count('id'))
            .filter(visitas__gte=1)
            .order_by('-visitas')[:10]
        )
        frecuentes = [
            {
                'id':      r['docente__id'],
                'nombre':  r['docente__nombre'] or '—',
                'grado':   r['docente__area'] or '—',
                'visitas': r['visitas'],
            }
            for r in frecuentes_raw
        ]
        motivos_raw = (
            qs_base.values('motivo')
            .annotate(total=Count('id'))
            .order_by('-total')
        )
        motivos_choices = dict(getattr(ConsultaDocente, 'MOTIVO_CHOICES', []))
    else:
        qs_base = Consulta.objects.all()
        frecuentes_raw = (
            qs_base.filter(fecha_hora__date__gte=desde)
            .values('estudiante__id', 'estudiante__nombre', 'estudiante__grado')
            .annotate(visitas=Count('id'))
            .filter(visitas__gte=1)
            .order_by('-visitas')[:10]
        )
        frecuentes = [
            {
                'id':      r['estudiante__id'],
                'nombre':  r['estudiante__nombre'],
                'grado':   r['estudiante__grado'],
                'visitas': r['visitas'],
            }
            for r in frecuentes_raw
        ]
        motivos_raw = (
            qs_base.values('motivo')
            .annotate(total=Count('id'))
            .order_by('-total')
        )
        motivos_choices = dict(Consulta.MOTIVO_CHOICES)

    motivos = [
        {'key': r['motivo'], 'label': motivos_choices.get(r['motivo'], r['motivo']), 'total': r['total']}
        for r in motivos_raw
    ]

    # ── 4. Comparativo mes a mes automático (últimos 6 meses) ─────────────────
    hoy = datetime.date.today()
    comparativo = []
    for i in range(5, -1, -1):
        base = hoy.replace(day=1) - datetime.timedelta(days=i * 30)
        mes  = base.replace(day=1)
        # Último día del mes
        if mes.month == 12:
            fin_mes = mes.replace(year=mes.year + 1, month=1, day=1) - datetime.timedelta(days=1)
        else:
            fin_mes = mes.replace(month=mes.month + 1, day=1) - datetime.timedelta(days=1)
        total = qs_base.filter(
            fecha_hora__year=mes.year,
            fecha_hora__month=mes.month
        ).count()
        comparativo.append({
            'mes':    mes.strftime('%b %Y'),
            'anio':   mes.year,
            'numero': mes.month,
            'total':  total,
        })

    # Delta mes actual vs mes anterior
    if len(comparativo) >= 2:
        actual   = comparativo[-1]['total']
        anterior = comparativo[-2]['total']
        delta    = actual - anterior
        delta_pct = round((delta / anterior * 100), 1) if anterior > 0 else None
    else:
        delta = delta_pct = None

    return JsonResponse({
        'frecuentes':  frecuentes,
        'motivos':     motivos,
        'comparativo': comparativo,
        'delta_mes':   delta,
        'delta_pct':   delta_pct,
    })


# ── 5 & 6. CHATBOT CONTEXTUAL CON HISTORIAL DEL ESTUDIANTE E INVENTARIO ──────
@login_required
def chatbot_api_consulta(request):
    """
    Endpoint AJAX especializado para el chatbot *durante* el registro de una consulta.
    Recibe el estudiante_id (si existe) e inyecta:
      - Historial clínico completo del estudiante (alergias, condiciones, medicamentos perm,
        últimas 5 consultas)
      - Inventario disponible en enfermería (solo ítems con stock > 0 y no vencidos)
    Así CURE-BOT puede sugerir medicamentos reales del botiquín y dar contexto clínico.

    Body JSON:
      {
        "pregunta": "...",
        "historial": [...],          // conversación actual (últimos 10 mensajes)
        "estudiante_id": 42          // opcional; null si no hay estudiante aún
      }
    """
    from django.http import JsonResponse
    import json as _json
    import time

    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)

    data         = _json.loads(request.body)
    pregunta     = data.get('pregunta', '').strip()
    historial    = data.get('historial', [])
    estudiante_id = data.get('estudiante_id')

    if not pregunta:
        return JsonResponse({'error': 'Pregunta vacía'}, status=400)

    GEMINI_API_KEY = getattr(settings, 'GEMINI_API_KEY', '')
    if not GEMINI_API_KEY:
        return JsonResponse({'error': 'API key de Gemini no configurada en settings.py'}, status=500)

    # ── Contexto del estudiante ───────────────────────────────────────────────
    contexto_estudiante = ''
    if estudiante_id:
        try:
            est = Estudiante.objects.get(pk=estudiante_id)
            ultimas = (
                Consulta.objects.filter(estudiante=est)
                .order_by('-fecha_hora')[:5]
            )
            hist_txt = '\n'.join(
                f'  • [{c.fecha_hora.strftime("%d/%m/%Y")}] {c.get_motivo_display()}: '
                f'{c.descripcion_sintomas[:120]} — Tratamiento: {c.tratamiento[:80]}'
                for c in ultimas
            ) or '  (Sin consultas previas)'

            contexto_estudiante = (
                f'\n\n=== HISTORIAL CLÍNICO DEL ESTUDIANTE ===\n'
                f'Nombre: {est.nombre}\n'
                f'Grado: {est.grado}  |  Edad aprox: {est.fecha_nacimiento}\n'
                f'Tipo de sangre: {est.tipo_sangre or "No registrado"}\n'
                f'Alergias: {est.alergias or "Ninguna registrada"}\n'
                f'Condiciones médicas: {est.condiciones_medicas or "Ninguna"}\n'
                f'Medicamentos permanentes: {est.medicamentos_perm or "Ninguno"}\n'
                f'EPS: {est.eps or "No registrada"}\n'
                f'Últimas 5 consultas en enfermería:\n{hist_txt}\n'
                f'=========================================\n'
            )
        except Estudiante.DoesNotExist:
            contexto_estudiante = '\n(Estudiante no encontrado en la base de datos)\n'

    # ── Inventario disponible (stock > 0 y no vencido) ───────────────────────
    hoy_inv = datetime.date.today()
    inventario_qs = Medicamento.objects.filter(
        cantidad_actual__gt=0,
        fecha_vencimiento__gt=hoy_inv,
    ).order_by('categoria', 'nombre')

    if inventario_qs.exists():
        inv_lines = '\n'.join(
            f'  • {m.nombre} ({m.get_categoria_display()}) — '
            f'{m.cantidad_actual} {m.get_unidad_display()} '
            f'[vence: {m.fecha_vencimiento.strftime("%d/%m/%Y")}]'
            for m in inventario_qs
        )
        contexto_inventario = (
            f'\n\n=== INVENTARIO DISPONIBLE EN ENFERMERÍA ===\n'
            f'{inv_lines}\n'
            f'IMPORTANTE: Solo sugiere medicamentos o insumos de esta lista.\n'
            f'Indica nombre, dosis orientativa y categoría.\n'
            f'==========================================\n'
        )
    else:
        contexto_inventario = '\n(No hay medicamentos/insumos disponibles en inventario actualmente)\n'

    # ── System prompt enriquecido ─────────────────────────────────────────────
    system_prompt = (
        "Eres CURE-BOT, asistente médico de enfermería escolar del sistema COSFA CURE "
        "(Colegio San Francisco de Asís, Colombia). "
        "Estás asistiendo DURANTE EL REGISTRO DE UNA CONSULTA médica. "
        "Tienes acceso al historial clínico del estudiante y al inventario real de la enfermería. "
        "Cuando sugiereas medicamentos o insumos, SOLO usa los que aparecen en el inventario disponible. "
        "Indica nombre exacto (como aparece en el inventario), dosis orientativa para la edad/peso y categoría. "
        "Nunca inventes medicamentos que no estén en el inventario. "
        "Si el inventario está vacío o no tiene el medicamento adecuado, indícalo explícitamente. "
        "Ten en cuenta las alergias y condiciones médicas del estudiante al recomendar tratamientos. "
        "Responde en español, de forma clara, concisa y profesional. "
        "Si es emergencia grave, siempre indica llamar al 123 o trasladar al estudiante. "
        "Nunca diagnostiques enfermedades graves de forma definitiva."
        + contexto_estudiante
        + contexto_inventario
    )

    contents = []
    for item in historial[-10:]:
        role = item.get('role')
        if role == 'user':
            contents.append({'role': 'user', 'parts': [{'text': item['content']}]})
        elif role == 'assistant':
            contents.append({'role': 'model', 'parts': [{'text': item['content']}]})
    contents.append({'role': 'user', 'parts': [{'text': pregunta}]})

    intentos = [
        ('v1beta', 'gemini-2.5-flash'),
        ('v1beta', 'gemini-2.0-flash'),
        ('v1',     'gemini-2.0-flash'),
    ]
    ultimo_error = 'Error desconocido'

    for api_ver, modelo in intentos:
        if api_ver == 'v1beta':
            body = {
                'system_instruction': {'parts': [{'text': system_prompt}]},
                'contents': contents,
                'generationConfig': {'maxOutputTokens': 1200, 'temperature': 0.3},
            }
        else:
            contents_v1 = [
                {'role': 'user',  'parts': [{'text': system_prompt}]},
                {'role': 'model', 'parts': [{'text': 'Entendido. Tengo el historial del estudiante y el inventario disponible. Listo para asistir.'}]},
            ] + contents
            body = {
                'contents': contents_v1,
                'generationConfig': {'maxOutputTokens': 1200, 'temperature': 0.3},
            }

        payload = _json.dumps(body).encode('utf-8')
        url = (
            f'https://generativelanguage.googleapis.com/{api_ver}/models/'
            f'{modelo}:generateContent?key={GEMINI_API_KEY}'
        )
        req = _urllib_req.Request(
            url, data=payload,
            headers={'Content-Type': 'application/json'},
            method='POST'
        )
        try:
            with _urllib_req.urlopen(req, timeout=30) as resp:
                result = _json.loads(resp.read().decode('utf-8'))
            respuesta = result['candidates'][0]['content']['parts'][0]['text']
            # Guardar en historial del chatbot igual que el endpoint principal
            MensajeChatbot.objects.create(usuario=request.user, role='user', content=pregunta)
            MensajeChatbot.objects.create(
                usuario=request.user, role='assistant',
                content=respuesta, modelo_ia=modelo,
            )
            return JsonResponse({
                'respuesta':    respuesta,
                'modelo_usado': modelo,
                'con_historial': bool(estudiante_id and contexto_estudiante),
                'con_inventario': inventario_qs.exists(),
            })
        except _urllib_req.HTTPError as e:
            try:
                error_body = e.read().decode('utf-8')
                error_data = _json.loads(error_body)
                error_msg = error_data.get('error', {}).get('message', str(e))
            except Exception:
                error_msg = str(e)
            ultimo_error = f'HTTP {e.code} ({api_ver}/{modelo}): {error_msg}'
            time.sleep(0.5)
            continue
        except Exception as e:
            ultimo_error = f'Error ({api_ver}/{modelo}): {str(e)}'
            time.sleep(0.5)
            continue

    return JsonResponse({'error': ultimo_error}, status=500)


# ── API: datos de inventario disponible para el chatbot de consulta ───────────
@login_required
def api_inventario_disponible(request):
    """
    Devuelve JSON con los medicamentos/insumos disponibles (stock > 0, no vencidos).
    Usado por el frontend del formulario de consulta para pre-cargar el contexto
    del chatbot antes de que el usuario escriba.
    """
    from django.http import JsonResponse
    hoy = datetime.date.today()
    items = list(
        Medicamento.objects.filter(
            cantidad_actual__gt=0,
            fecha_vencimiento__gt=hoy,
        ).order_by('categoria', 'nombre').values(
            'id', 'nombre', 'categoria', 'cantidad_actual', 'unidad', 'fecha_vencimiento'
        )
    )
    for item in items:
        item['fecha_vencimiento'] = item['fecha_vencimiento'].isoformat()
        item['categoria_label'] = dict(Medicamento.CATEGORIA_CHOICES).get(item['categoria'], item['categoria'])
        item['unidad_label'] = dict(Medicamento.UNIDAD_CHOICES).get(item['unidad'], item['unidad'])
    return JsonResponse({'items': items, 'total': len(items)})


# ── EXPORTAR REPORTE ESTADÍSTICO A EXCEL ──────────────────────────────────
@login_required
def exportar_reporte_excel(request):
    """
    Genera un Excel completo del módulo Reportes con 4 hojas:
      1. Resumen          – KPIs principales
      2. Comparativo MxM  – consultas por mes (últimos 12 meses)
      3. Top 10 Frecuentes – estudiantes con más visitas en el período
      4. Detalle Motivos   – desglose por motivo + grado
    Respeta los mismos filtros GET que la vista `reportes`.
    """
    if not OPENPYXL_OK:
        messages.error(request, 'openpyxl no instalado. Ejecuta: pip install openpyxl')
        return redirect('reportes')

    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.chart import BarChart, Reference
    from openpyxl.chart.series import DataPoint
    import calendar

    # ── Parámetros ────────────────────────────────────────────────────────────
    fecha_desde = request.GET.get('fecha_desde', '')
    fecha_hasta = request.GET.get('fecha_hasta', '')
    grado_f     = request.GET.get('grado', '')
    motivo_f    = request.GET.get('motivo', '')
    hoy         = datetime.date.today()

    # ── QuerySet base con filtros ──────────────────────────────────────────────
    qs = Consulta.objects.all()
    if fecha_desde:
        try:
            qs = qs.filter(fecha_hora__date__gte=datetime.date.fromisoformat(fecha_desde))
        except ValueError:
            pass
    if fecha_hasta:
        try:
            qs = qs.filter(fecha_hora__date__lte=datetime.date.fromisoformat(fecha_hasta))
        except ValueError:
            pass
    if grado_f:
        qs = qs.filter(estudiante__grado=grado_f)
    if motivo_f:
        qs = qs.filter(motivo=motivo_f)

    # ── Estilos ────────────────────────────────────────────────────────────────
    st = _excel_styles()
    COLOR_NAVY   = '0F2444'
    COLOR_TEAL   = '0E7490'
    COLOR_TEAL2  = '3AAFA9'
    COLOR_ORANGE = 'E8954A'
    COLOR_SAGE   = '52B788'
    COLOR_GOLD   = 'D4A017'
    COLOR_LIGHT  = 'EEF9F8'

    thin   = Side(style='thin', color='DDDDDD')
    medium = Side(style='medium', color=COLOR_TEAL)
    border_thin   = Border(left=thin, right=thin, top=thin, bottom=thin)
    border_header = Border(left=medium, right=medium, top=medium, bottom=medium)

    def _hdr(ws, row, col, value, color=COLOR_TEAL, font_sz=9, bold=True):
        c = ws.cell(row=row, column=col, value=value)
        c.font      = Font(bold=bold, color='FFFFFF', size=font_sz)
        c.fill      = PatternFill('solid', fgColor=color)
        c.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
        c.border    = border_thin
        return c

    def _cell(ws, row, col, value, bold=False, align='left', color=None, font_color='333333', size=9):
        c = ws.cell(row=row, column=col, value=value)
        c.font      = Font(bold=bold, color=font_color, size=size)
        c.alignment = Alignment(horizontal=align, vertical='center', wrap_text=True)
        c.border    = border_thin
        if color:
            c.fill = PatternFill('solid', fgColor=color)
        return c

    def _title_row(ws, row, ncols, text, subtitle=''):
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=ncols)
        c = ws.cell(row=row, column=1, value=text)
        c.font      = Font(bold=True, color='FFFFFF', size=14)
        c.fill      = PatternFill('solid', fgColor=COLOR_NAVY)
        c.alignment = Alignment(horizontal='center', vertical='center')
        ws.row_dimensions[row].height = 30
        if subtitle:
            ws.merge_cells(start_row=row+1, start_column=1, end_row=row+1, end_column=ncols)
            s = ws.cell(row=row+1, column=1, value=subtitle)
            s.font      = Font(italic=True, color='666666', size=8)
            s.alignment = Alignment(horizontal='center', vertical='center')
            ws.row_dimensions[row+1].height = 16

    wb = openpyxl.Workbook()

    # ══════════════════════════════════════════════════════════════════════════
    # HOJA 1 — RESUMEN
    # ══════════════════════════════════════════════════════════════════════════
    ws1 = wb.active
    ws1.title = '📊 Resumen'

    filtro_txt = ' | '.join(filter(None, [
        f'Desde: {fecha_desde}' if fecha_desde else '',
        f'Hasta: {fecha_hasta}' if fecha_hasta else '',
        f'Grado: {grado_f}' if grado_f else '',
        f'Motivo: {motivo_f}' if motivo_f else '',
    ])) or 'Sin filtros — período completo'

    _title_row(ws1, 1, 4, 'COSFA CURE — Reporte Estadístico', filtro_txt)
    ws1.cell(row=2, column=4, value=f'Generado: {hoy.strftime("%d/%m/%Y")}').font = Font(size=7, italic=True, color='999999')

    # KPIs
    total_consultas   = qs.count()
    total_remisiones  = Remision.objects.count()
    total_estudiantes = Estudiante.objects.count()
    desde_30          = hoy - datetime.timedelta(days=30)
    consultas_mes     = qs.filter(fecha_hora__date__gte=desde_30).count()

    kpis = [
        ('Total Consultas (filtro)',   total_consultas,   COLOR_TEAL2),
        ('Consultas últimos 30 días',  consultas_mes,     COLOR_TEAL),
        ('Remisiones realizadas',      total_remisiones,  COLOR_ORANGE),
        ('Estudiantes registrados',    total_estudiantes, COLOR_SAGE),
    ]
    ws1.row_dimensions[4].height = 14
    _hdr(ws1, 5, 1, 'Indicador', COLOR_NAVY, 10)
    _hdr(ws1, 5, 2, 'Valor',     COLOR_NAVY, 10)
    _hdr(ws1, 5, 3, 'Color ref', COLOR_NAVY, 10)
    _hdr(ws1, 5, 4, 'Nota',      COLOR_NAVY, 10)

    notas = [
        'Con los filtros aplicados',
        'Últimos 30 días naturales',
        'Total histórico',
        'Total histórico',
    ]
    for i, (label, valor, color) in enumerate(kpis, 6):
        _cell(ws1, i, 1, label, bold=True)
        _cell(ws1, i, 2, valor,  bold=True, align='center', font_color=color, size=11)
        c3 = ws1.cell(row=i, column=3)
        c3.fill = PatternFill('solid', fgColor=color)
        c3.border = border_thin
        _cell(ws1, i, 4, notas[i-6], font_color='666666', size=8)

    # Top motivos en resumen
    ws1.row_dimensions[11].height = 12
    _hdr(ws1, 12, 1, 'Motivo', COLOR_NAVY, 10)
    _hdr(ws1, 12, 2, 'Total',  COLOR_NAVY, 10)
    _hdr(ws1, 12, 3, '% del total', COLOR_NAVY, 10)
    _hdr(ws1, 12, 4, 'Barra', COLOR_NAVY, 10)

    por_motivo = list(qs.values('motivo').annotate(total=Count('id')).order_by('-total'))
    for item in por_motivo:
        item['label'] = dict(Consulta.MOTIVO_CHOICES).get(item['motivo'], item['motivo'])

    for i, item in enumerate(por_motivo, 13):
        pct = round(item['total'] / total_consultas * 100, 1) if total_consultas else 0
        alt = COLOR_LIGHT if i % 2 == 0 else None
        _cell(ws1, i, 1, item['label'], color=alt)
        _cell(ws1, i, 2, item['total'], bold=True, align='center', color=alt)
        _cell(ws1, i, 3, f'{pct}%', align='center', color=alt)
        bar = '█' * int(pct / 5)
        _cell(ws1, i, 4, bar, font_color=COLOR_TEAL2, color=alt)

    for col, width in [(1, 32), (2, 10), (3, 12), (4, 20)]:
        ws1.column_dimensions[openpyxl.utils.get_column_letter(col)].width = width

    # ══════════════════════════════════════════════════════════════════════════
    # HOJA 2 — COMPARATIVO MES A MES
    # ══════════════════════════════════════════════════════════════════════════
    ws2 = wb.create_sheet('📅 Comparativo MxM')
    _title_row(ws2, 1, 6, 'Comparativo Mes a Mes — Consultas', f'Últimos 12 meses | {filtro_txt}')

    headers_mxm = ['#', 'Mes', 'Año', 'Total Consultas', 'Δ vs mes anterior', '% Variación']
    for col, h in enumerate(headers_mxm, 1):
        _hdr(ws2, 3, col, h, COLOR_NAVY if col == 1 else COLOR_TEAL)
    ws2.row_dimensions[3].height = 18

    meses_data = []
    for i in range(11, -1, -1):
        d = hoy.replace(day=1) - datetime.timedelta(days=i * 30)
        total = qs.filter(fecha_hora__year=d.year, fecha_hora__month=d.month).count()
        meses_data.append({'mes': d.strftime('%B'), 'anio': d.year, 'total': total, 'fecha': d})

    prev = None
    for i, item in enumerate(meses_data, 4):
        alt = COLOR_LIGHT if i % 2 == 0 else None
        delta = item['total'] - prev if prev is not None else 0
        pct_v = f'{round(delta/prev*100,1):+}%' if prev and prev > 0 else ('—' if prev is None else '0%')
        delta_str = f'{delta:+}' if prev is not None else '—'

        _cell(ws2, i, 1, i - 3,         align='center', color=alt)
        _cell(ws2, i, 2, item['mes'].capitalize(), color=alt)
        _cell(ws2, i, 3, item['anio'],   align='center', color=alt)
        c4 = _cell(ws2, i, 4, item['total'], bold=True, align='center', color=alt)
        if item['total'] == max(x['total'] for x in meses_data):
            c4.font = Font(bold=True, color=COLOR_TEAL, size=10)
        _cell(ws2, i, 5, delta_str, align='center',
              font_color=(COLOR_ORANGE if delta > 0 else COLOR_SAGE if delta < 0 else '666666'),
              color=alt)
        _cell(ws2, i, 6, pct_v, align='center',
              font_color=(COLOR_ORANGE if delta > 0 else COLOR_SAGE if delta < 0 else '666666'),
              color=alt)
        prev = item['total']

    # Gráfica de barras embebida
    chart = BarChart()
    chart.type   = 'col'
    chart.title  = 'Consultas por Mes'
    chart.y_axis.title = 'Consultas'
    chart.x_axis.title = 'Mes'
    chart.style  = 10
    chart.width  = 18
    chart.height = 10

    data_ref    = Reference(ws2, min_col=4, min_row=3, max_row=3 + 12)
    cats_ref    = Reference(ws2, min_col=2, min_row=4, max_row=3 + 12)
    chart.add_data(data_ref, titles_from_data=True)
    chart.set_categories(cats_ref)
    ws2.add_chart(chart, 'H3')

    for col, width in [(1,5),(2,14),(3,8),(4,16),(5,18),(6,14)]:
        ws2.column_dimensions[openpyxl.utils.get_column_letter(col)].width = width

    # ══════════════════════════════════════════════════════════════════════════
    # HOJA 3 — TOP 10 ESTUDIANTES FRECUENTES
    # ══════════════════════════════════════════════════════════════════════════
    ws3 = wb.create_sheet('🏆 Top 10 Frecuentes')
    dias_top = int(request.GET.get('dias', 30))
    desde_top = hoy - datetime.timedelta(days=dias_top)

    _title_row(ws3, 1, 6, f'Top 10 Estudiantes Frecuentes', f'Últimos {dias_top} días | {filtro_txt}')

    headers_top = ['#', 'Estudiante', 'Grado', 'Visitas', '% del total', 'Primer visita (período)']
    for col, h in enumerate(headers_top, 1):
        _hdr(ws3, 3, col, h, COLOR_NAVY if col == 1 else COLOR_ORANGE)
    ws3.row_dimensions[3].height = 18

    top10_qs = (
        qs.filter(fecha_hora__date__gte=desde_top)
        .values('estudiante__id', 'estudiante__nombre', 'estudiante__grado')
        .annotate(visitas=Count('id'))
        .order_by('-visitas')[:10]
    )
    total_en_periodo = qs.filter(fecha_hora__date__gte=desde_top).count()

    medallas = ['🥇', '🥈', '🥉'] + [''] * 7

    for i, e in enumerate(top10_qs, 1):
        alt = COLOR_LIGHT if i % 2 == 0 else None
        pct = round(e['visitas'] / total_en_periodo * 100, 1) if total_en_periodo else 0

        # Obtener primera visita del período
        primera = (
            Consulta.objects.filter(
                estudiante_id=e['estudiante__id'],
                fecha_hora__date__gte=desde_top
            ).order_by('fecha_hora').values_list('fecha_hora', flat=True).first()
        )
        primera_str = timezone.localtime(primera).strftime('%d/%m/%Y') if primera else '—'

        rank_str = f'{medallas[i-1]} {i}' if i <= 3 else str(i)
        _cell(ws3, i+3, 1, rank_str,              align='center', color=alt,
              font_color=COLOR_GOLD if i <= 3 else '333333', bold=i<=3)
        _cell(ws3, i+3, 2, e['estudiante__nombre'],  bold=True,  color=alt)
        c3 = _cell(ws3, i+3, 3, e['estudiante__grado'], align='center', color=alt)
        _cell(ws3, i+3, 4, e['visitas'], bold=True, align='center',
              font_color=COLOR_ORANGE if i == 1 else COLOR_TEAL, color=alt, size=11 if i==1 else 9)
        _cell(ws3, i+3, 5, f'{pct}%', align='center', color=alt)
        _cell(ws3, i+3, 6, primera_str, align='center', color=alt, font_color='666666')

    for col, width in [(1,8),(2,32),(3,12),(4,10),(5,12),(6,20)]:
        ws3.column_dimensions[openpyxl.utils.get_column_letter(col)].width = width
    ws3.freeze_panes = 'A4'

    # ══════════════════════════════════════════════════════════════════════════
    # HOJA 4 — DETALLE MOTIVOS × GRADO
    # ══════════════════════════════════════════════════════════════════════════
    ws4 = wb.create_sheet('📋 Motivos × Grado')
    _title_row(ws4, 1, 5, 'Detalle de Consultas por Motivo y Grado', filtro_txt)

    # Tabla motivos
    _hdr(ws4, 3, 1, 'Motivo',  COLOR_NAVY, 10)
    _hdr(ws4, 3, 2, 'Total',   COLOR_NAVY, 10)
    _hdr(ws4, 3, 3, '% total', COLOR_NAVY, 10)
    _hdr(ws4, 3, 4, 'Barra visual', COLOR_NAVY, 10)
    ws4.row_dimensions[3].height = 18

    for i, item in enumerate(por_motivo, 4):
        pct = round(item['total'] / total_consultas * 100, 1) if total_consultas else 0
        alt = COLOR_LIGHT if i % 2 == 0 else None
        _cell(ws4, i, 1, item['label'], color=alt, bold=True)
        _cell(ws4, i, 2, item['total'], align='center', color=alt)
        _cell(ws4, i, 3, f'{pct}%',    align='center', color=alt)
        _cell(ws4, i, 4, '█' * max(1, int(pct/4)), font_color=COLOR_TEAL2, color=alt)

    # Tabla por grado
    offset = len(por_motivo) + 6
    _hdr(ws4, offset, 1, 'Grado', COLOR_NAVY, 10)
    _hdr(ws4, offset, 2, 'Total Consultas', COLOR_NAVY, 10)
    _hdr(ws4, offset, 3, '% total', COLOR_NAVY, 10)
    ws4.row_dimensions[offset].height = 18

    por_grado = list(qs.values('estudiante__grado').annotate(total=Count('id')).order_by('-total'))
    for i, item in enumerate(por_grado, offset + 1):
        pct = round(item['total'] / total_consultas * 100, 1) if total_consultas else 0
        alt = COLOR_LIGHT if i % 2 == 0 else None
        _cell(ws4, i, 1, item['estudiante__grado'] or '—', color=alt, bold=True)
        _cell(ws4, i, 2, item['total'], align='center', color=alt)
        _cell(ws4, i, 3, f'{pct}%',    align='center', color=alt)

    for col, width in [(1,28),(2,16),(3,12),(4,25)]:
        ws4.column_dimensions[openpyxl.utils.get_column_letter(col)].width = width
    ws4.freeze_panes = 'A4'

    # ── Metadatos del workbook ─────────────────────────────────────────────────
    wb.properties.title   = 'COSFA CURE — Reporte Estadístico'
    wb.properties.creator = 'COSFA CURE'
    wb.properties.subject = f'Reportes generados {hoy}'

    # ── Response HTTP ──────────────────────────────────────────────────────────
    filename = f'reporte_cosfa_{hoy.strftime("%Y%m%d")}.xlsx'
    resp = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    resp['Content-Disposition'] = f'attachment; filename="{filename}"'
    wb.save(resp)
    return resp


# ─────────────────────────────────────────────────────────────────────────────
# BACKUP / RESTORE de base de datos SQLite  (v29 – solo superusuarios)
# ─────────────────────────────────────────────────────────────────────────────
import shutil
import tempfile

@admin_required
def backup_bd(request):
    """Descarga una copia del archivo db.sqlite3. Solo superusuarios."""
    if not request.user.is_superuser:
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden('Acceso denegado: se requiere superusuario.')

    from django.conf import settings as dj_settings
    db_path = dj_settings.DATABASES['default']['NAME']
    if not os.path.exists(db_path):
        messages.error(request, '❌ No se encontró el archivo de base de datos.')
        return redirect('perfil_usuario')

    nombre_archivo = f'cosfa_backup_{datetime.date.today().strftime("%Y%m%d_%H%M%S")}.sqlite3'
    response = HttpResponse(content_type='application/octet-stream')
    response['Content-Disposition'] = f'attachment; filename="{nombre_archivo}"'
    with open(db_path, 'rb') as f:
        response.write(f.read())
    _log(request, 'backup', 'BaseDatos', f'Backup descargado: {nombre_archivo}')
    return response


@admin_required
def restore_bd(request):
    """
    Restaura db.sqlite3 desde un archivo .sqlite3 subido por el usuario.
    
    Estrategia compatible con Windows:
    En Windows, el proceso de Django mantiene un lock de SO sobre db.sqlite3
    que impide cualquier operación de archivo (remove, copy, replace) aunque
    se cierren las conexiones de Django. La única solución que funciona es
    vaciar la BD activa y repoblarla tabla por tabla desde el backup,
    todo usando la API de sqlite3 de Python sin tocar el archivo en disco.
    """
    if not request.user.is_superuser:
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden('Acceso denegado: se requiere superusuario.')

    if request.method != 'POST':
        return redirect('perfil_usuario')

    archivo = request.FILES.get('archivo_backup')
    if not archivo:
        messages.error(request, '❌ No se recibió ningún archivo.')
        return redirect('perfil_usuario')

    if not archivo.name.endswith('.sqlite3'):
        messages.error(request, '❌ El archivo debe tener extensión .sqlite3')
        return redirect('perfil_usuario')
    if archivo.size > 200 * 1024 * 1024:
        messages.error(request, '❌ El archivo supera el tamaño máximo permitido (200 MB).')
        return redirect('perfil_usuario')

    import sqlite3 as _sqlite3
    from django.conf import settings as dj_settings
    from django.db import connections

    db_path = str(dj_settings.DATABASES['default']['NAME'])
    tmp_path = None

    try:
        # ── Paso 1: Guardar el archivo subido en un temporal ─────────────
        with tempfile.NamedTemporaryFile(delete=False, suffix='.sqlite3') as tmp:
            for chunk in archivo.chunks():
                tmp.write(chunk)
            tmp_path = tmp.name

        # ── Paso 2: Validar integridad del backup ────────────────────────
        try:
            with _sqlite3.connect(tmp_path) as _chk:
                result = _chk.execute('PRAGMA integrity_check').fetchone()
            if result is None or result[0] != 'ok':
                messages.error(request, '❌ El archivo no pasó la validación de integridad SQLite.')
                return redirect('perfil_usuario')
        except _sqlite3.DatabaseError as db_err:
            messages.error(request, f'❌ Archivo SQLite inválido: {db_err}')
            return redirect('perfil_usuario')

        # ── Paso 3: Restaurar usando la API backup de sqlite3 ────────────
        # sqlite3.Connection.backup() copia datos entre dos conexiones abiertas
        # sin necesidad de mover, borrar ni reemplazar ningún archivo en disco.
        # Esto evita completamente WinError 32 y WinError 5.
        connections['default'].close()  # liberar conexiones de Django

        with _sqlite3.connect(tmp_path) as src_conn,              _sqlite3.connect(db_path) as dst_conn:
            src_conn.backup(dst_conn, pages=100)

        _log(request, 'restore', 'BaseDatos', f'Restauración desde: {archivo.name}')
        messages.success(request, '✅ Base de datos restaurada correctamente. Recarga la aplicación.')

    except Exception as exc:
        messages.error(request, f'❌ Error al restaurar: {exc}')
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

    return redirect('perfil_usuario')


@login_required
def api_datos_estudiante(request, pk):
    """Devuelve EPS, número de póliza y teléfono de contacto EPS del estudiante para autocompletar en remisión."""
    from django.http import JsonResponse
    try:
        est = Estudiante.objects.get(pk=pk)
        return JsonResponse({
            'eps':             est.eps or '',
            'numero_poliza':   est.numero_poliza or '',
            'tel_contacto_eps': est.tel_contacto_eps or '',
        })
    except Estudiante.DoesNotExist:
        return JsonResponse({'eps': '', 'numero_poliza': '', 'tel_contacto_eps': ''})

# ══════════════════════════════════════════════════════════════════════════════
# GESTIÓN DE USUARIOS (solo admin)
# ══════════════════════════════════════════════════════════════════════════════

@admin_required
def gestionar_usuarios(request):
    """Lista de usuarios con opciones para cambiar rol y eliminar."""
    from .models import PerfilUsuario
    if request.method == 'POST':
        accion  = request.POST.get('accion')
        user_id = request.POST.get('user_id')
        try:
            target = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            messages.error(request, 'Usuario no encontrado.')
            return redirect('perfil_usuario') + '?tab=usuarios'

        if target == request.user:
            messages.error(request, 'No puedes modificar tu propio rol.')
            return redirect('/perfil/?tab=usuarios')

        # Solo el superusuario puede gestionar roles y eliminar usuarios
        if not request.user.is_superuser:
            messages.error(request, '⛔ Solo el administrador principal puede gestionar usuarios.')
            return redirect('/perfil/?tab=usuarios')

        # Proteger al superusuario de cualquier modificación
        if target.is_superuser and accion in ('hacer_viewer', 'eliminar'):
            messages.error(request, '⛔ No se pueden quitar permisos ni eliminar al administrador principal del sistema.')
            return redirect('/perfil/?tab=usuarios')

        if accion == 'hacer_admin':
            perfil, _ = PerfilUsuario.objects.get_or_create(usuario=target)
            perfil.rol = PerfilUsuario.ROL_ADMIN
            perfil.save()
            messages.success(request, f'✅ {target.username} ahora es Administrador.')
        elif accion == 'hacer_viewer':
            perfil, _ = PerfilUsuario.objects.get_or_create(usuario=target)
            perfil.rol = PerfilUsuario.ROL_VIEWER
            perfil.save()
            messages.success(request, f'✅ {target.username} ahora es Solo lectura.')
        elif accion == 'eliminar':
            nombre = target.username
            target.delete()
            messages.success(request, f'🗑️ Usuario "{nombre}" eliminado.')

        return redirect('/perfil/?tab=usuarios')

    # GET: lista de usuarios
    usuarios = User.objects.exclude(pk=request.user.pk).select_related('perfilusuario').order_by('username')
    ctx = []
    for u in usuarios:
        perfil = getattr(u, 'perfilusuario', None)
        ctx.append({
            'user':   u,
            'perfil': perfil,
            'rol':    perfil.rol if perfil else 'viewer',
            'rol_label': 'Administrador' if (perfil and perfil.rol == 'admin') else 'Solo lectura',
        })
    return JsonResponse({'usuarios': [
        {
            'id': d['user'].pk,
            'username': d['user'].username,
            'email': d['user'].email,
            'is_superuser': d['user'].is_superuser,
            'rol': d['rol'],
            'rol_label': d['rol_label'],
            'fecha': d['perfil'].fecha_creacion.strftime('%d/%m/%Y') if d['perfil'] else '—',
        }
        for d in ctx
    ]})
