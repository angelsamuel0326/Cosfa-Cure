from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from django.conf import settings
from django.conf.urls.static import static
from enfermeria import views as enf_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('',       enf_views.landing, name='home'),   # ← Landing page pública
    path('login/',  enf_views.custom_login, name='login'),
    path('logout/', enf_views.logout_view, name='logout'),

    # ── Recuperación de contraseña ────────────────────────────────────────────
    path('password-reset/',
         auth_views.PasswordResetView.as_view(
             template_name='registration/password_reset_form.html',
             email_template_name='registration/password_reset_email.html',
             html_email_template_name='registration/password_reset_email.html',
             subject_template_name='registration/password_reset_subject.txt',
         ),
         name='password_reset'),

    path('password-reset/done/',
         auth_views.PasswordResetDoneView.as_view(
             template_name='registration/password_reset_done.html',
         ),
         name='password_reset_done'),

    path('password-reset-confirm/<uidb64>/<token>/',
         auth_views.PasswordResetConfirmView.as_view(
             template_name='registration/password_reset_confirm.html',
         ),
         name='password_reset_confirm'),

    path('password-reset-complete/',
         auth_views.PasswordResetCompleteView.as_view(
             template_name='registration/password_reset_complete.html',
         ),
         name='password_reset_complete'),
    # ─────────────────────────────────────────────────────────────────────────

    path('', include('enfermeria.urls')),
]

# Servir archivos de media siempre (incluso con DEBUG=False en desarrollo local)
from django.views.static import serve as _serve
from django.urls import re_path as _re_path
urlpatterns += [
    _re_path(r'^media/(?P<path>.*)$', _serve, {'document_root': settings.MEDIA_ROOT}),
]
