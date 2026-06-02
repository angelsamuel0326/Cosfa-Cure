from django import forms
from .models import Estudiante, Consulta, ConsultaDocente, Docente, Remision, Seguimiento, Medicamento, MovimientoInventario, GradoEscolar

W  = {'class': 'form-control'}
WS = {'class': 'form-select'}
WT = {'class': 'form-control', 'rows': 3}


def _get_grado_choices():
    """
    Devuelve grados predeterminados (1A-11B) más los creados manualmente en BD.
    Siempre muestra los grados base aunque la tabla esté vacía.
    """
    GRADOS_BASE = [
        '1A','1B','2A','2B','3A','3B','4A','4B','5A','5B',
        '6A','6B','7A','7B','8A','8B','9A','9B','10A','10B','11A','11B',
    ]
    base = [(g, g) for g in GRADOS_BASE]
    try:
        # Grados personalizados creados por el usuario que no estén ya en los base
        extras = list(
            GradoEscolar.objects
            .filter(activo=True)
            .exclude(nombre__in=GRADOS_BASE)
            .order_by('orden', 'nombre')
            .values_list('nombre', 'nombre')
        )
        return [('', '---------')] + base + extras
    except Exception:
        return [('', '---------')] + base


class EstudianteForm(forms.ModelForm):
    # Campo explícito para que el widget Select funcione correctamente
    # (el modelo usa CharField sin choices, por lo que Django genera TextInput por defecto)
    grado = forms.ChoiceField(
        choices=_get_grado_choices,   # callable → se evalúa en cada instancia
        widget=forms.Select(attrs=WS),
        label='Grado',
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Recargar choices dinámicos en cada instancia (por si la BD cambió)
        self.fields['grado'].choices = _get_grado_choices()
        # Asegurar que la fecha de nacimiento existente se muestre correctamente
        # en el input type="date" (requiere formato YYYY-MM-DD)
        self.fields['fecha_nacimiento'].widget = forms.DateInput(
            attrs={**W, 'type': 'date'},
            format='%Y-%m-%d',
        )
        if self.instance and self.instance.pk and self.instance.fecha_nacimiento:
            self.initial['fecha_nacimiento'] = self.instance.fecha_nacimiento.strftime('%Y-%m-%d')

    class Meta:
        model  = Estudiante
        fields = [
            'nombre', 'numero_documento', 'grado', 'fecha_nacimiento', 'sexo',
            'tipo_sangre', 'peso_kg', 'talla_cm',
            'alergias', 'condiciones_medicas', 'medicamentos_perm', 'discapacidad',
            'eps', 'regimen', 'numero_poliza', 'tel_contacto_eps',
            'acudiente', 'cc_acudiente', 'parentesco_acudiente',
            'telefono_acudiente', 'telefono_alternativo',
            'correo_acudiente', 'direccion_residencia',
            'contacto_emergencia', 'tel_emergencia',
            'foto',
        ]
        widgets = {
            'nombre':               forms.TextInput(attrs={**W, 'placeholder': 'Apellidos y nombres completos'}),
            'numero_documento':     forms.TextInput(attrs={**W, 'placeholder': 'Cédula o tarjeta de identidad'}),
            'grado':                forms.Select(attrs=WS),
            'fecha_nacimiento':     forms.DateInput(attrs={**W, 'type': 'date'}),
            'sexo':                 forms.Select(attrs=WS),
            'tipo_sangre':          forms.Select(attrs=WS),
            'peso_kg':              forms.NumberInput(attrs={**W, 'step': '0.1', 'min': '1', 'placeholder': 'ej. 52.5'}),
            'talla_cm':             forms.NumberInput(attrs={**W, 'step': '0.1', 'min': '50', 'placeholder': 'ej. 158.0'}),
            'alergias':             forms.Textarea(attrs={**WT, 'placeholder': 'Medicamentos, alimentos, picaduras, látex…'}),
            'condiciones_medicas':  forms.Textarea(attrs={**WT, 'placeholder': 'Asma, diabetes, epilepsia, cardiopatías…'}),
            'medicamentos_perm':    forms.Textarea(attrs={**WT, 'rows': 2, 'placeholder': 'Nombre, dosis y frecuencia de cada medicamento'}),
            'discapacidad':         forms.Textarea(attrs={**WT, 'rows': 2, 'placeholder': 'Motriz, visual, auditiva, cognitiva…'}),
            'eps':                  forms.TextInput(attrs={**W, 'placeholder': 'ej. Sura, Nueva EPS, Sanitas'}),
            'regimen':              forms.Select(attrs=WS),
            'numero_poliza':        forms.TextInput(attrs={**W, 'placeholder': 'Número de carné o póliza EPS'}),
            'tel_contacto_eps':     forms.TextInput(attrs={**W, 'placeholder': 'ej. 01 8000 910 097'}),
            'acudiente':            forms.TextInput(attrs={**W, 'placeholder': 'Nombre completo del acudiente'}),
            'cc_acudiente':         forms.TextInput(attrs={**W, 'placeholder': 'Cédula de ciudadanía del acudiente'}),
            'parentesco_acudiente': forms.Select(attrs=WS),
            'telefono_acudiente':   forms.TextInput(attrs={**W, 'placeholder': 'Celular o fijo principal'}),
            'telefono_alternativo': forms.TextInput(attrs={**W, 'placeholder': 'Número alternativo (opcional)'}),
            'correo_acudiente':     forms.EmailInput(attrs={**W, 'placeholder': 'correo@ejemplo.com'}),
            'direccion_residencia': forms.TextInput(attrs={**W, 'placeholder': 'Calle, barrio, municipio…'}),
            'contacto_emergencia':  forms.TextInput(attrs={**W, 'placeholder': 'Nombre de otro familiar o tutor'}),
            'tel_emergencia':       forms.TextInput(attrs={**W, 'placeholder': 'Teléfono de ese contacto'}),
            'foto':                 forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
        }


class ConsultaForm(forms.ModelForm):
    class Meta:
        model  = Consulta
        fields = ['estudiante','hora_atencion','motivo','descripcion_sintomas','tratamiento',
                  'estado','observaciones',
                  'temperatura','presion_arterial','frecuencia_cardiaca',
                  'frecuencia_respiratoria','peso','talla',
                  'acudiente_notificado','hora_notificacion',
                  'quien_atendio_llamada','detalle_notificacion',
                  'correo_padre_madre','correo_docente']
        widgets = {
            'estudiante':              forms.Select(attrs=WS),
            'hora_atencion':           forms.TimeInput(attrs={**W,'type':'time'}),
            'motivo':                  forms.Select(attrs=WS),
            'descripcion_sintomas':    forms.Textarea(attrs=WT),
            'tratamiento':             forms.Textarea(attrs=WT),
            'estado':                  forms.Select(attrs=WS),
            'observaciones':           forms.Textarea(attrs={**WT,'rows':2}),
            'temperatura':             forms.NumberInput(attrs={**W,'step':'0.1','placeholder':'36.5'}),
            'presion_arterial':        forms.TextInput(attrs={**W,'placeholder':'120/80'}),
            'frecuencia_cardiaca':     forms.NumberInput(attrs={**W,'placeholder':'70'}),
            'frecuencia_respiratoria': forms.NumberInput(attrs={**W,'placeholder':'18'}),
            'peso':                    forms.NumberInput(attrs={**W,'step':'0.1','placeholder':'55.0'}),
            'talla':                   forms.NumberInput(attrs={**W,'step':'0.1','placeholder':'160.0'}),
            'acudiente_notificado':    forms.CheckboxInput(attrs={'class':'form-check-input'}),
            'hora_notificacion':       forms.TimeInput(attrs={**W,'type':'time'}),
            'quien_atendio_llamada':   forms.TextInput(attrs={**W,'placeholder':'Nombre de quien atendió'}),
            'detalle_notificacion':    forms.Textarea(attrs={**WT,'rows':2,'placeholder':'Qué se informó al acudiente'}),
            'correo_padre_madre':      forms.EmailInput(attrs={**W,'placeholder':'correo_padre_o_madre@ejemplo.com'}),
            'correo_docente':          forms.EmailInput(attrs={**W,'placeholder':'correo_docente@colegio.edu.co'}),
        }
        labels = {
            'hora_atencion': 'Hora de atención *',
        }


class RemisionForm(forms.ModelForm):
    class Meta:
        model  = Remision
        fields = ['estudiante','eps','numero_eps','numero_contacto_eps','hora_salida','hora_llegada',
                  'motivo','tipo_destino','hospital_destino','acompanante',
                  'estado','observaciones','seguimiento_posterior',
                  'temperatura','presion_arterial','frecuencia_cardiaca',
                  'frecuencia_respiratoria','peso','talla',
                  'acudiente_notificado','hora_notificacion','quien_atendio_llamada','detalle_notificacion',
                  'correo_padre_madre','correo_docente']
        widgets = {
            'estudiante':            forms.Select(attrs=WS),
            'eps':                   forms.TextInput(attrs=W),
            'numero_eps':            forms.TextInput(attrs={**W,'placeholder':'Ej: 123456789'}),
            'numero_contacto_eps':   forms.TextInput(attrs={**W,'placeholder':'Ej: 01 8000 123 456'}),
            'hora_salida':           forms.TimeInput(attrs={**W,'type':'time'}),
            'hora_llegada':          forms.TimeInput(attrs={**W,'type':'time'}),
            'motivo':                forms.Textarea(attrs={**WT,'rows':2,'placeholder':'Describe el motivo de la remisión…'}),
            'tipo_destino':          forms.Select(attrs=WS),
            'hospital_destino':      forms.TextInput(attrs={**W,'placeholder':'Nombre del hospital o clínica'}),
            'acompanante':           forms.TextInput(attrs=W),
            'estado':                forms.Select(attrs=WS),
            'observaciones':         forms.Textarea(attrs={**WT,'rows':2}),
            'seguimiento_posterior': forms.Textarea(attrs={**WT,'rows':2,'placeholder':'Diagnóstico recibido, indicaciones médicas, regreso a clases…'}),
            'temperatura':             forms.NumberInput(attrs={**W,'step':'0.1','placeholder':'36.5'}),
            'presion_arterial':        forms.TextInput(attrs={**W,'placeholder':'120/80'}),
            'frecuencia_cardiaca':     forms.NumberInput(attrs={**W,'placeholder':'70'}),
            'frecuencia_respiratoria': forms.NumberInput(attrs={**W,'placeholder':'18'}),
            'peso':                    forms.NumberInput(attrs={**W,'step':'0.1','placeholder':'55.0'}),
            'talla':                   forms.NumberInput(attrs={**W,'step':'0.1','placeholder':'160.0'}),
            'acudiente_notificado':  forms.CheckboxInput(attrs={'class':'form-check-input'}),
            'hora_notificacion':     forms.TimeInput(attrs={**W,'type':'time'}),
            'quien_atendio_llamada': forms.TextInput(attrs={**W,'placeholder':'Nombre de quien atendió'}),
            'detalle_notificacion':  forms.Textarea(attrs={**WT,'rows':2,'placeholder':'Qué se informó al acudiente'}),
            'correo_padre_madre':    forms.EmailInput(attrs={**W,'placeholder':'correo_padre_o_madre@ejemplo.com'}),
            'correo_docente':        forms.EmailInput(attrs={**W,'placeholder':'correo_docente@colegio.edu.co'}),
        }
        labels = {
            'hora_salida':           'Hora de atención / salida *',
            'hora_llegada':          'Hora de llegada / regreso (opcional)',
            'seguimiento_posterior': 'Seguimiento posterior / diagnóstico recibido',
        }


class SeguimientoForm(forms.ModelForm):
    class Meta:
        model  = Seguimiento
        fields = ['estudiante','tipo','fecha','fecha_fin','descripcion','completado']
        widgets = {
            'estudiante':  forms.Select(attrs=WS),
            'tipo':        forms.Select(attrs=WS),
            'fecha':       forms.DateInput(attrs={**W,'type':'date'}),
            'fecha_fin':   forms.DateInput(attrs={**W,'type':'date'}),
            'descripcion': forms.Textarea(attrs=WT),
            'completado':  forms.CheckboxInput(attrs={'class':'form-check-input'}),
        }
        labels = {
            'fecha':     'Fecha inicio *',
            'fecha_fin': 'Fecha fin (opcional)',
        }


class MedicamentoForm(forms.ModelForm):
    class Meta:
        model  = Medicamento
        fields = ['nombre','categoria','descripcion','cantidad_actual','cantidad_minima','unidad','fecha_vencimiento','imagen']
        widgets = {
            'nombre':            forms.TextInput(attrs=W),
            'categoria':         forms.Select(attrs=WS),
            'descripcion':       forms.Textarea(attrs={**WT,'rows':2}),
            'cantidad_actual':   forms.NumberInput(attrs={**W,'min':'0'}),
            'cantidad_minima':   forms.NumberInput(attrs={**W,'min':'1'}),
            'unidad':            forms.Select(attrs=WS),
            'fecha_vencimiento': forms.DateInput(attrs={**W,'type':'date'}),
            'imagen':            forms.FileInput(attrs={'class':'form-control','accept':'image/*'}),
        }
        labels = {
            'categoria': 'Categoría del ítem',
        }
        help_texts = {
            'categoria': 'Insumos: alcohol, gasas, vendas, etc. Medicamentos: solo con prescripción médica y autorización del acudiente.',
        }


class MovimientoForm(forms.ModelForm):
    class Meta:
        model  = MovimientoInventario
        fields = ['medicamento','tipo','cantidad','motivo']
        widgets = {
            'medicamento': forms.Select(attrs=WS),
            'tipo':        forms.Select(attrs=WS),
            'cantidad':    forms.NumberInput(attrs={**W,'min':'1'}),
            'motivo':      forms.TextInput(attrs=W),
        }


class DocenteForm(forms.ModelForm):
    class Meta:
        model  = Docente
        fields = [
            'nombre','cedula','fecha_nacimiento','sexo','tipo',
            'area','grados_asignados','vinculacion',
            'telefono','telefono_alternativo','correo','correo_personal','direccion_residencia',
            'tipo_sangre','eps','regimen',
            'alergias','condiciones_medicas','medicamentos_perm',
            'contacto_emergencia','parentesco_emergencia','tel_emergencia',
            'foto','activo',
        ]
        widgets = {
            'nombre':                forms.TextInput(attrs={**W,'placeholder':'Apellidos y nombres completos'}),
            'cedula':                forms.TextInput(attrs={**W,'placeholder':'Número de cédula de ciudadanía'}),
            'fecha_nacimiento':      forms.DateInput(attrs={**W,'type':'date'}),
            'sexo':                  forms.Select(attrs=WS),
            'tipo':                  forms.TextInput(attrs={**W,'placeholder':'Docente, Coordinador, Rector…'}),
            'area':                  forms.Select(attrs=WS),
            'grados_asignados':      forms.TextInput(attrs={**W,'placeholder':'Ej: 8A, 9B, 10A'}),
            'vinculacion':           forms.Select(attrs=WS),
            'telefono':              forms.TextInput(attrs={**W,'placeholder':'Celular principal'}),
            'telefono_alternativo':  forms.TextInput(attrs={**W,'placeholder':'Opcional'}),
            'correo':                forms.EmailInput(attrs={**W,'placeholder':'correo@colegio.edu.co'}),
            'correo_personal':       forms.EmailInput(attrs={**W,'placeholder':'correo@personal.com'}),
            'direccion_residencia':  forms.TextInput(attrs={**W,'placeholder':'Calle, barrio, municipio…'}),
            'tipo_sangre':           forms.Select(attrs=WS),
            'eps':                   forms.TextInput(attrs={**W,'placeholder':'Ej: Sura, Nueva EPS, Sanitas'}),
            'regimen':               forms.Select(attrs=WS),
            'alergias':              forms.Textarea(attrs={**WT,'placeholder':'Medicamentos, alimentos, picaduras…'}),
            'condiciones_medicas':   forms.Textarea(attrs={**WT,'placeholder':'Asma, diabetes, hipertensión…'}),
            'medicamentos_perm':     forms.Textarea(attrs={**WT,'rows':2,'placeholder':'Nombre, dosis y frecuencia'}),
            'contacto_emergencia':   forms.TextInput(attrs={**W,'placeholder':'Nombre del familiar o contacto'}),
            'parentesco_emergencia': forms.TextInput(attrs={**W,'placeholder':'Ej: Esposa, Hijo, Hermano'}),
            'tel_emergencia':        forms.TextInput(attrs={**W,'placeholder':'Teléfono del contacto'}),
            'foto':                  forms.FileInput(attrs={'class':'form-control','accept':'image/*'}),
            'activo':                forms.CheckboxInput(attrs={'class':'form-check-input'}),
        }


class ConsultaDocenteForm(forms.ModelForm):
    class Meta:
        model  = ConsultaDocente
        fields = ['docente','hora_atencion','motivo','descripcion_sintomas','tratamiento',
                  'estado','observaciones',
                  'temperatura','presion_arterial','frecuencia_cardiaca',
                  'frecuencia_respiratoria','peso','talla']
        widgets = {
            'docente':                 forms.Select(attrs=WS),
            'hora_atencion':           forms.TimeInput(attrs={**W,'type':'time'}),
            'motivo':                  forms.Select(attrs=WS),
            'descripcion_sintomas':    forms.Textarea(attrs=WT),
            'tratamiento':             forms.Textarea(attrs=WT),
            'estado':                  forms.Select(attrs=WS),
            'observaciones':           forms.Textarea(attrs={**WT,'rows':2}),
            'temperatura':             forms.NumberInput(attrs={**W,'step':'0.1','placeholder':'36.5'}),
            'presion_arterial':        forms.TextInput(attrs={**W,'placeholder':'120/80'}),
            'frecuencia_cardiaca':     forms.NumberInput(attrs={**W,'placeholder':'70'}),
            'frecuencia_respiratoria': forms.NumberInput(attrs={**W,'placeholder':'18'}),
            'peso':                    forms.NumberInput(attrs={**W,'step':'0.1','placeholder':'55.0'}),
            'talla':                   forms.NumberInput(attrs={**W,'step':'0.1','placeholder':'160.0'}),
        }
        labels = {
            'docente':      'Docente *',
            'hora_atencion':'Hora de atención *',
        }


# ── Validación condicional: hospital_destino solo es requerido si tipo_destino='hospital'
from django.core.exceptions import ValidationError as _ValidationError
_OrigRemisionForm = RemisionForm
class RemisionForm(_OrigRemisionForm):
    def clean(self):
        cleaned = super().clean()
        tipo = cleaned.get('tipo_destino', 'hospital')
        hosp = cleaned.get('hospital_destino', '').strip()
        acomp = cleaned.get('acompanante', '').strip()
        if tipo == 'hospital' and not hosp:
            self.add_error('hospital_destino', 'Ingresa el nombre del hospital o clínica.')
        # acompanante solo requerido si destino=hospital
        if tipo == 'hospital' and not acomp:
            self.add_error('acompanante', 'Ingresa el nombre del acompañante.')
        return cleaned
