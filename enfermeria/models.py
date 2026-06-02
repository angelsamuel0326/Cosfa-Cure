from django.db import models
from django.contrib.auth.models import User
import datetime


class GradoEscolar(models.Model):
    """Grados configurables por la institución (creables y borrables desde la UI)."""
    nombre    = models.CharField(max_length=10, unique=True, verbose_name='Nombre del grado')
    orden     = models.PositiveSmallIntegerField(default=0, verbose_name='Orden de visualización')
    activo    = models.BooleanField(default=True, verbose_name='Activo')
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Grado Escolar'
        verbose_name_plural = 'Grados Escolares'
        ordering = ['orden', 'nombre']

    def __str__(self):
        return self.nombre

    @property
    def total_estudiantes(self):
        return Estudiante.objects.filter(grado=self.nombre).count()


class Estudiante(models.Model):
    # GRADO_CHOICES se mantiene como fallback legacy; los grados reales vienen de GradoEscolar
    GRADO_CHOICES = [
        ('1A','1A'),('1B','1B'),('2A','2A'),('2B','2B'),
        ('3A','3A'),('3B','3B'),('4A','4A'),('4B','4B'),
        ('5A','5A'),('5B','5B'),('6A','6A'),('6B','6B'),
        ('7A','7A'),('7B','7B'),('8A','8A'),('8B','8B'),
        ('9A','9A'),('9B','9B'),('10A','10A'),('10B','10B'),
        ('11A','11A'),('11B','11B'),
    ]
    ESTADO_ACADEMICO_CHOICES = [
        ('activo',    'Activo'),
        ('graduado',  'Graduado'),
        ('retirado',  'Retirado'),
        ('trasladado','Trasladado'),
    ]
    TIPO_SANGRE_CHOICES = [
        ('A+','A+'),('A-','A-'),('B+','B+'),('B-','B-'),
        ('AB+','AB+'),('AB-','AB-'),('O+','O+'),('O-','O-'),
    ]
    SEXO_CHOICES = [
        ('M','Masculino'),('F','Femenino'),('O','Otro'),
    ]
    REGIMEN_CHOICES = [
        ('contributivo','Contributivo'),('subsidiado','Subsidiado'),
        ('especial','Régimen especial'),('ninguno','Sin aseguramiento'),
    ]
    PARENTESCO_CHOICES = [
        ('madre','Madre'),('padre','Padre'),('abuelo','Abuelo/a'),
        ('tio','Tío/a'),('hermano','Hermano/a'),('otro','Otro'),
    ]
    # Datos básicos
    nombre               = models.CharField(max_length=100, verbose_name='Nombre completo', db_index=True)
    numero_documento     = models.CharField(max_length=20, unique=True, verbose_name='Número de documento')
    grado                = models.CharField(max_length=10, db_index=True)  # choices dinámicos desde GradoEscolar
    fecha_nacimiento     = models.DateField(null=True, blank=True, verbose_name='Fecha de nacimiento')
    # Estado académico
    estado_academico     = models.CharField(max_length=12, choices=ESTADO_ACADEMICO_CHOICES, default='activo', db_index=True, verbose_name='Estado académico')
    anio_lectivo         = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name='Año lectivo', help_text='Año escolar actual del estudiante')
    sexo                 = models.CharField(max_length=1, choices=SEXO_CHOICES, blank=True, verbose_name='Sexo biológico', db_index=True)
    # Salud
    tipo_sangre          = models.CharField(max_length=5, choices=TIPO_SANGRE_CHOICES, blank=True, verbose_name='Tipo de sangre')
    peso_kg              = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True, verbose_name='Peso (kg)')
    talla_cm             = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True, verbose_name='Talla (cm)')
    alergias             = models.TextField(blank=True, verbose_name='Alergias conocidas')
    condiciones_medicas  = models.TextField(blank=True, verbose_name='Condiciones médicas')
    medicamentos_perm    = models.TextField(blank=True, verbose_name='Medicamentos de uso permanente')
    discapacidad         = models.TextField(blank=True, verbose_name='Discapacidad o necesidad especial')
    # Seguro / EPS
    eps                  = models.CharField(max_length=100, blank=True, verbose_name='EPS / Aseguradora')
    regimen              = models.CharField(max_length=15, choices=REGIMEN_CHOICES, blank=True, verbose_name='Régimen de salud')
    numero_poliza        = models.CharField(max_length=50, blank=True, verbose_name='N.° póliza / carné EPS')
    tel_contacto_eps     = models.CharField(max_length=30, blank=True, verbose_name='Teléfono de contacto / urgencias EPS')
    # Acudiente principal
    acudiente            = models.CharField(max_length=100, verbose_name='Nombre del acudiente')
    cc_acudiente         = models.CharField(max_length=20, blank=True, verbose_name='Cédula del acudiente')
    parentesco_acudiente = models.CharField(max_length=10, choices=PARENTESCO_CHOICES, blank=True, verbose_name='Parentesco')
    telefono_acudiente   = models.CharField(max_length=20, verbose_name='Teléfono acudiente')
    telefono_alternativo = models.CharField(max_length=20, blank=True, verbose_name='Teléfono alternativo')
    correo_acudiente     = models.EmailField(blank=True, verbose_name='Correo del acudiente')
    direccion_residencia = models.CharField(max_length=200, blank=True, verbose_name='Dirección de residencia')
    # Contacto de emergencia adicional
    contacto_emergencia  = models.CharField(max_length=100, blank=True, verbose_name='Contacto emergencia adicional')
    tel_emergencia       = models.CharField(max_length=20, blank=True, verbose_name='Teléfono emergencia adicional')
    # Otros
    foto                 = models.ImageField(upload_to='estudiantes/', blank=True, null=True)
    fecha_registro       = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Estudiante'
        verbose_name_plural = 'Estudiantes'
        ordering = ['nombre']
        indexes = [
            models.Index(fields=['nombre', 'grado']),
            models.Index(fields=['grado', 'sexo']),
        ]

    def __str__(self):
        return f"{self.nombre} - {self.grado}"

    @property
    def edad(self):
        """Calcula la edad actual en años a partir de fecha_nacimiento."""
        if not self.fecha_nacimiento:
            return None
        hoy = datetime.date.today()
        anios = hoy.year - self.fecha_nacimiento.year
        if (hoy.month, hoy.day) < (self.fecha_nacimiento.month, self.fecha_nacimiento.day):
            anios -= 1
        return anios

    @property
    def total_consultas(self):
        return self.consultas.count()

    @property
    def frecuente(self):
        """Más de 4 visitas en los últimos 30 días."""
        desde = datetime.date.today() - datetime.timedelta(days=30)
        return self.consultas.filter(fecha_hora__date__gte=desde).count() >= 4


class Consulta(models.Model):
    MOTIVO_CHOICES = [
        ('dolor_cabeza','Dolor de cabeza'),('dolor_estomago','Dolor de estómago'),
        ('fiebre','Fiebre'),('lesion','Lesión / Golpe'),('mareo','Mareo'),
        ('nauseas','Náuseas / Vómito'),('dolor_garganta','Dolor de garganta'),
        ('alergias','Reacción alérgica'),('otro','Otro'),
    ]
    ESTADO_CHOICES = [
        ('atendido',         'Atendido en enfermería'),
        ('regreso_clase',    'Regreso a clases'),
        ('remitido_casa',    'Remitido a casa'),
        ('remitido_hospital','Remitido al hospital'),
    ]
    estudiante               = models.ForeignKey(Estudiante, on_delete=models.CASCADE, related_name='consultas', db_index=True)
    fecha_hora               = models.DateTimeField(auto_now_add=True, db_index=True)
    hora_atencion            = models.TimeField(verbose_name='Hora de atención', help_text='Hora exacta en que se atendió al estudiante')
    motivo                   = models.CharField(max_length=50, choices=MOTIVO_CHOICES, db_index=True)
    descripcion_sintomas     = models.TextField()
    tratamiento              = models.TextField()
    medicamento              = models.ForeignKey('Medicamento', on_delete=models.SET_NULL, null=True, blank=True, related_name='consultas_usadas')
    cantidad_usada           = models.PositiveIntegerField(default=1)
    medicamento_suministrado = models.CharField(max_length=100, blank=True)
    dosis                    = models.CharField(max_length=50, blank=True)
    estado                   = models.CharField(max_length=20, choices=ESTADO_CHOICES, db_index=True)
    observaciones            = models.TextField(blank=True)
    # Signos vitales
    temperatura              = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True, verbose_name='Temperatura (°C)')
    presion_arterial         = models.CharField(max_length=20, blank=True, verbose_name='Presión arterial')
    frecuencia_cardiaca      = models.PositiveIntegerField(null=True, blank=True, verbose_name='Frec. cardíaca (lpm)')
    frecuencia_respiratoria  = models.PositiveIntegerField(null=True, blank=True, verbose_name='Frec. respiratoria (rpm)')
    peso                     = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True, verbose_name='Peso (kg)')
    talla                    = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True, verbose_name='Talla (cm)')
    # Notificación al acudiente
    acudiente_notificado     = models.BooleanField(default=False, verbose_name='Acudiente notificado')
    hora_notificacion        = models.TimeField(null=True, blank=True, verbose_name='Hora de notificación')
    quien_atendio_llamada    = models.CharField(max_length=100, blank=True, verbose_name='Quién atendió la llamada')
    detalle_notificacion     = models.TextField(blank=True, verbose_name='Detalle de la notificación')
    # Regreso a clase — correos de notificación
    correo_padre_madre       = models.EmailField(blank=True, verbose_name='Correo padre/madre (regreso a clase)')
    correo_docente           = models.EmailField(blank=True, verbose_name='Correo del docente (regreso a clase)')
    notificacion_clase_enviada = models.BooleanField(default=False, verbose_name='Notificación de clase enviada')

    class Meta:
        verbose_name = 'Consulta'
        verbose_name_plural = 'Consultas'
        ordering = ['-fecha_hora']
        indexes = [
            models.Index(fields=['-fecha_hora']),
            models.Index(fields=['estudiante', '-fecha_hora']),
            models.Index(fields=['estado', '-fecha_hora']),
            models.Index(fields=['motivo', '-fecha_hora']),
        ]

    def __str__(self):
        return f"{self.estudiante.nombre} - {self.get_motivo_display()}"


class HistorialCambio(models.Model):
    ACCION_CHOICES = [
        ('crear','Creado'),('editar','Editado'),('eliminar','Eliminado'),
    ]
    usuario     = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    accion      = models.CharField(max_length=10, choices=ACCION_CHOICES)
    modelo      = models.CharField(max_length=50)
    descripcion = models.TextField()
    fecha       = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-fecha']

    def __str__(self):
        return f"{self.usuario} – {self.accion} {self.modelo}"


class Remision(models.Model):
    ESTADO_CHOICES = [('pendiente','Pendiente'),('en_proceso','En proceso'),('resuelto','Resuelto')]
    TIPO_DESTINO_CHOICES = [('hospital','Hospital / Centro médico'),('casa','Casa del estudiante')]
    estudiante       = models.ForeignKey(Estudiante, on_delete=models.CASCADE, related_name='remisiones', db_index=True)
    fecha_hora       = models.DateTimeField(auto_now_add=True, db_index=True)
    motivo           = models.TextField()
    tipo_destino     = models.CharField(max_length=10, choices=TIPO_DESTINO_CHOICES, default='hospital', verbose_name='Tipo de destino')
    hospital_destino = models.CharField(max_length=150, blank=True, verbose_name='Hospital / Clínica de destino')
    eps              = models.CharField(max_length=100, blank=True)
    numero_eps       = models.CharField(max_length=50, blank=True, verbose_name='Número de carné / póliza EPS')
    numero_contacto_eps = models.CharField(max_length=30, blank=True, verbose_name='Número de contacto EPS')
    acompanante      = models.CharField(max_length=100, blank=True, default='')
    hora_salida      = models.TimeField()
    hora_llegada     = models.TimeField(null=True, blank=True, verbose_name='Hora de llegada / regreso')
    estado           = models.CharField(max_length=15, choices=ESTADO_CHOICES, default='pendiente', db_index=True)
    observaciones    = models.TextField(blank=True)
    seguimiento_posterior = models.TextField(blank=True, verbose_name='Seguimiento posterior / diagnóstico recibido')
    # Notificación al acudiente
    acudiente_notificado  = models.BooleanField(default=False, verbose_name='¿Se notificó al acudiente?')
    hora_notificacion     = models.TimeField(null=True, blank=True, verbose_name='Hora de notificación')
    quien_atendio_llamada = models.CharField(max_length=100, blank=True, verbose_name='¿Quién atendió la llamada?')
    detalle_notificacion  = models.TextField(blank=True, verbose_name='Detalle de lo informado')
    # Signos vitales
    temperatura           = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True, verbose_name='Temperatura (°C)')
    presion_arterial      = models.CharField(max_length=20, blank=True, verbose_name='Presión arterial')
    frecuencia_cardiaca   = models.PositiveIntegerField(null=True, blank=True, verbose_name='Frec. cardíaca (lpm)')
    frecuencia_respiratoria = models.PositiveIntegerField(null=True, blank=True, verbose_name='Frec. respiratoria (rpm)')
    peso                  = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True, verbose_name='Peso (kg)')
    talla                 = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True, verbose_name='Talla (cm)')
    # Correos
    correo_padre_madre = models.EmailField(blank=True, verbose_name='Correo padre / madre / acudiente')
    correo_docente     = models.EmailField(blank=True, verbose_name='Correo del docente')
    consulta_origen  = models.ForeignKey('Consulta', null=True, blank=True, on_delete=models.SET_NULL, related_name='remisiones_auto', verbose_name='Consulta de origen')

    class Meta:
        verbose_name = 'Remisión'
        verbose_name_plural = 'Remisiones'
        ordering = ['-fecha_hora']
        indexes = [
            models.Index(fields=['estado', '-fecha_hora']),
            models.Index(fields=['estudiante', '-fecha_hora']),
        ]

    def __str__(self):
        destino = self.hospital_destino if self.tipo_destino == 'hospital' else 'Casa del estudiante'
        return f"Remisión: {self.estudiante.nombre} → {destino}"

    @property
    def destino_display(self):
        if self.tipo_destino == 'casa':
            return 'Casa del estudiante'
        return self.hospital_destino or 'Hospital / Centro médico'


class Seguimiento(models.Model):
    TIPO_CHOICES = [
        ('control','Control médico'),('vacuna','Vacunación'),
        ('revision','Revisión general'),('otro','Otro'),
    ]
    estudiante     = models.ForeignKey(Estudiante, on_delete=models.CASCADE, related_name='seguimientos', db_index=True)
    tipo           = models.CharField(max_length=20, choices=TIPO_CHOICES)
    fecha          = models.DateField(verbose_name='Fecha inicio', db_index=True)
    fecha_fin      = models.DateField(null=True, blank=True, verbose_name='Fecha fin (opcional)')
    descripcion    = models.TextField()
    completado     = models.BooleanField(default=False, db_index=True)
    continuado     = models.BooleanField(default=False, verbose_name='Continúa en seguimiento')
    evolucion      = models.TextField(blank=True, verbose_name='Evolución / Notas de cierre')
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Seguimiento'
        verbose_name_plural = 'Seguimientos'
        ordering = ['fecha']
        indexes = [
            models.Index(fields=['completado', 'fecha']),
        ]

    def __str__(self):
        return f"{self.estudiante.nombre} - {self.get_tipo_display()}"

    @property
    def vencido(self):
        """Vencido solo cuando la fecha de FIN (o inicio si no hay fin) ya pasó."""
        if self.completado:
            return False
        hoy = datetime.date.today()
        fecha_limite = self.fecha_fin if self.fecha_fin else self.fecha
        return fecha_limite < hoy

    @property
    def proximo(self):
        hoy = datetime.date.today()
        fecha_limite = self.fecha_fin if self.fecha_fin else self.fecha
        return not self.completado and hoy <= fecha_limite <= hoy + datetime.timedelta(days=7)


class Medicamento(models.Model):
    UNIDAD_CHOICES = [
        ('tabletas','Tabletas'),('capsulas','Cápsulas'),('ml','Mililitros (ml)'),
        ('mg','Miligramos (mg)'),('unidades','Unidades'),('sobres','Sobres'),
        ('rollos','Rollos'),('pares','Pares'),('bolsas','Bolsas'),
    ]
    CATEGORIA_CHOICES = [
        ('insumo','Insumo / Primeros auxilios'),
        ('medicamento','Medicamento (requiere prescripción)'),
    ]
    nombre              = models.CharField(max_length=100, db_index=True)
    categoria           = models.CharField(max_length=20, choices=CATEGORIA_CHOICES, default='insumo', verbose_name='Categoría', db_index=True)
    descripcion         = models.TextField(blank=True)
    cantidad_actual     = models.IntegerField()
    cantidad_minima     = models.IntegerField(default=5)
    unidad              = models.CharField(max_length=20, choices=UNIDAD_CHOICES)
    fecha_vencimiento   = models.DateField(db_index=True)
    imagen              = models.ImageField(upload_to='medicamentos/', blank=True, null=True, verbose_name='Imagen del medicamento')
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Insumo / Medicamento'
        verbose_name_plural = 'Insumos y Botiquín'
        ordering = ['categoria', 'nombre']

    def __str__(self):
        return f"{self.nombre} ({self.cantidad_actual} {self.unidad})"

    @property
    def stock_bajo(self):
        return self.cantidad_actual <= self.cantidad_minima

    @property
    def dias_para_vencer(self):
        return (self.fecha_vencimiento - datetime.date.today()).days

    @property
    def proximo_vencer(self):
        return 0 < self.dias_para_vencer <= 30

    @property
    def vencido(self):
        return self.dias_para_vencer <= 0


class MovimientoInventario(models.Model):
    TIPO_CHOICES = [('entrada','Entrada'),('salida','Salida')]
    medicamento = models.ForeignKey(Medicamento, on_delete=models.CASCADE, related_name='movimientos', db_index=True)
    tipo        = models.CharField(max_length=10, choices=TIPO_CHOICES)
    cantidad    = models.IntegerField()
    motivo      = models.CharField(max_length=200)
    fecha       = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-fecha']

    def __str__(self):
        return f"{self.get_tipo_display()} - {self.medicamento.nombre}: {self.cantidad}"


class MedicamentoConsulta(models.Model):
    """Permite registrar múltiples medicamentos por consulta."""
    consulta    = models.ForeignKey('Consulta', on_delete=models.CASCADE, related_name='medicamentos_usados')
    medicamento = models.ForeignKey(Medicamento, on_delete=models.SET_NULL, null=True, related_name='usos_consulta')
    cantidad    = models.PositiveIntegerField(default=1)
    dosis       = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return f"{self.medicamento.nombre} x{self.cantidad} — Consulta #{self.consulta_id}"


class Docente(models.Model):
    """Base de datos de docentes del colegio."""
    TIPO_SANGRE_CHOICES = [
        ('A+','A+'),('A-','A-'),('B+','B+'),('B-','B-'),
        ('AB+','AB+'),('AB-','AB-'),('O+','O+'),('O-','O-'),
    ]
    SEXO_CHOICES = [
        ('M','Masculino'),('F','Femenino'),('O','Otro'),
    ]
    REGIMEN_CHOICES = [
        ('contributivo','Contributivo'),('subsidiado','Subsidiado'),
        ('especial','Régimen especial'),('ninguno','Sin aseguramiento'),
    ]
    AREA_CHOICES = [
        ('matematicas','Matemáticas'),('ciencias_naturales','Ciencias Naturales'),
        ('ciencias_sociales','Ciencias Sociales'),('lenguaje','Lenguaje / Español'),
        ('ingles','Inglés'),('educacion_fisica','Educación Física'),
        ('arte','Arte / Música'),('tecnologia','Tecnología / Informática'),
        ('religion','Religión'),('etica','Ética y Valores'),
        ('preescolar','Preescolar'),('primaria','Primaria'),
        ('coordinacion','Coordinación'),('directivo','Directivo'),
        ('administrativo','Administrativo'),('otro','Otro'),
    ]
    VINCULACION_CHOICES = [
        ('planta','Planta'),('provisional','Provisional'),
        ('contrato','Contrato'),('hora_catedra','Hora cátedra'),
    ]
    # Datos básicos
    nombre               = models.CharField(max_length=150, verbose_name='Nombre completo', db_index=True)
    cedula               = models.CharField(max_length=20, unique=True, verbose_name='Cédula de ciudadanía')
    fecha_nacimiento     = models.DateField(verbose_name='Fecha de nacimiento')
    sexo                 = models.CharField(max_length=1, choices=SEXO_CHOICES, blank=True, verbose_name='Sexo biológico')
    tipo                 = models.CharField(max_length=30, default='Docente', verbose_name='Tipo')
    area                 = models.CharField(max_length=30, choices=AREA_CHOICES, verbose_name='Área / Cargo')
    grados_asignados     = models.CharField(max_length=200, blank=True, verbose_name='Grados / Grupos que atiende')
    vinculacion          = models.CharField(max_length=20, choices=VINCULACION_CHOICES, blank=True, verbose_name='Tipo de vinculación')
    # Contacto
    telefono             = models.CharField(max_length=20, verbose_name='Teléfono celular')
    telefono_alternativo = models.CharField(max_length=20, blank=True, verbose_name='Teléfono alternativo')
    correo               = models.EmailField(blank=True, verbose_name='Correo institucional')
    correo_personal      = models.EmailField(blank=True, verbose_name='Correo personal')
    direccion_residencia = models.CharField(max_length=200, blank=True, verbose_name='Dirección de residencia')
    # Salud
    tipo_sangre          = models.CharField(max_length=5, choices=TIPO_SANGRE_CHOICES, blank=True, verbose_name='Tipo de sangre')
    eps                  = models.CharField(max_length=100, blank=True, verbose_name='EPS / Aseguradora')
    regimen              = models.CharField(max_length=15, choices=REGIMEN_CHOICES, blank=True, verbose_name='Régimen de salud')
    alergias             = models.TextField(blank=True, verbose_name='Alergias conocidas')
    condiciones_medicas  = models.TextField(blank=True, verbose_name='Condiciones médicas')
    medicamentos_perm    = models.TextField(blank=True, verbose_name='Medicamentos de uso permanente')
    # Contacto de emergencia
    contacto_emergencia  = models.CharField(max_length=100, blank=True, verbose_name='Contacto de emergencia')
    parentesco_emergencia= models.CharField(max_length=50, blank=True, verbose_name='Parentesco')
    tel_emergencia       = models.CharField(max_length=20, blank=True, verbose_name='Teléfono de emergencia')
    # Admin
    foto                 = models.ImageField(upload_to='docentes/', blank=True, null=True)
    fecha_registro       = models.DateTimeField(auto_now_add=True)
    activo               = models.BooleanField(default=True, verbose_name='Activo en la institución')

    class Meta:
        verbose_name = 'Docente'
        verbose_name_plural = 'Docentes'
        ordering = ['nombre']
        indexes = [
            models.Index(fields=['nombre']),
            models.Index(fields=['cedula']),
            models.Index(fields=['area']),
        ]

    def __str__(self):
        return f"{self.nombre} ({self.get_area_display()})"

    @property
    def total_consultas(self):
        return self.consultas_docente.count()

    @property
    def frecuente(self):
        desde = datetime.date.today() - datetime.timedelta(days=30)
        return self.consultas_docente.filter(fecha_hora__date__gte=desde).count() >= 4


class ConsultaDocente(models.Model):
    """Registro de atención médica/enfermería para docentes del colegio."""
    MOTIVO_CHOICES = [
        ('dolor_cabeza','Dolor de cabeza'),('dolor_estomago','Dolor de estómago'),
        ('fiebre','Fiebre'),('lesion','Lesión / Golpe'),('mareo','Mareo'),
        ('nauseas','Náuseas / Vómito'),('dolor_garganta','Dolor de garganta'),
        ('alergias','Reacción alérgica'),('otro','Otro'),
    ]
    ESTADO_CHOICES = [
        ('atendido',         'Atendido en enfermería'),
        ('regreso_clase',    'Regresa a sus actividades'),
        ('remitido_casa',    'Remitido a casa'),
        ('remitido_hospital','Remitido al hospital'),
    ]
    docente                  = models.ForeignKey('Docente', on_delete=models.CASCADE, related_name='consultas_docente', db_index=True, null=True, blank=True)
    nombre_completo          = models.CharField(max_length=150, verbose_name='Nombre completo')
    cedula                   = models.CharField(max_length=20, verbose_name='Cédula')
    edad                     = models.PositiveIntegerField(null=True, blank=True, verbose_name='Edad')
    fecha_nacimiento         = models.DateField(null=True, blank=True, verbose_name='Fecha de nacimiento')
    tipo                     = models.CharField(max_length=30, default='Docente', editable=False, verbose_name='Tipo')
    area_grado               = models.CharField(max_length=150, verbose_name='Área / Grado que atiende')
    eps                      = models.CharField(max_length=100, blank=True, verbose_name='EPS')
    fecha_hora               = models.DateTimeField(auto_now_add=True, db_index=True)
    hora_atencion            = models.TimeField(verbose_name='Hora de atención', help_text='Hora exacta en que se atendió al docente')
    motivo                   = models.CharField(max_length=50, choices=MOTIVO_CHOICES, db_index=True)
    descripcion_sintomas     = models.TextField(verbose_name='Descripción de síntomas')
    tratamiento              = models.TextField(verbose_name='Tratamiento aplicado')
    estado                   = models.CharField(max_length=20, choices=ESTADO_CHOICES, db_index=True)
    observaciones            = models.TextField(blank=True)
    temperatura              = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True, verbose_name='Temperatura (°C)')
    presion_arterial         = models.CharField(max_length=20, blank=True, verbose_name='Presión arterial')
    frecuencia_cardiaca      = models.PositiveIntegerField(null=True, blank=True, verbose_name='Frec. cardíaca (lpm)')
    frecuencia_respiratoria  = models.PositiveIntegerField(null=True, blank=True, verbose_name='Frec. respiratoria (rpm)')
    peso                     = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True, verbose_name='Peso (kg)')
    talla                    = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True, verbose_name='Talla (cm)')
    medicamento_suministrado = models.CharField(max_length=200, blank=True)

    class Meta:
        verbose_name = 'Consulta Docente'
        verbose_name_plural = 'Consultas Docentes'
        ordering = ['-fecha_hora']
        indexes = [
            models.Index(fields=['-fecha_hora']),
            models.Index(fields=['cedula']),
        ]

    def __str__(self):
        return f"{self.nombre_completo} – {self.get_motivo_display()} ({self.fecha_hora:%Y-%m-%d})"


class ConsentimientoRemision(models.Model):
    """Consentimiento digital del acudiente para una remisión médica."""
    remision           = models.OneToOneField(Remision, on_delete=models.CASCADE, related_name='consentimiento')
    fecha_firma        = models.DateTimeField(auto_now_add=True)
    firma_acudiente    = models.TextField(verbose_name='Firma acudiente (base64 SVG)')
    firma_enfermera    = models.TextField(verbose_name='Firma enfermera (base64 SVG)')
    nombre_acudiente   = models.CharField(max_length=150, blank=True)
    nombre_enfermera   = models.CharField(max_length=150, blank=True)
    cc_acudiente       = models.CharField(max_length=20, blank=True, verbose_name='CC acudiente')

    class Meta:
        verbose_name = 'Consentimiento de Remisión'
        verbose_name_plural = 'Consentimientos de Remisión'
        ordering = ['-fecha_firma']

    def __str__(self):
        return f"Consentimiento remisión #{self.remision_id} — {self.remision.estudiante.nombre}"


class PerfilUsuario(models.Model):
    """Perfil extendido del usuario de enfermería."""
    ROL_ADMIN  = 'admin'
    ROL_VIEWER = 'viewer'
    ROL_CHOICES = [
        (ROL_ADMIN,  'Administrador'),
        (ROL_VIEWER, 'Solo lectura'),
    ]

    usuario        = models.OneToOneField(User, on_delete=models.CASCADE, related_name='perfilusuario')
    cargo          = models.CharField(max_length=100, blank=True, default='Enfermera/o', verbose_name='Cargo')
    telefono       = models.CharField(max_length=20, blank=True, verbose_name='Teléfono de contacto')
    firma_digital  = models.TextField(blank=True, verbose_name='Firma digital (base64 SVG)')
    foto           = models.ImageField(upload_to='perfiles/', blank=True, null=True, verbose_name='Foto de perfil')
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    rol            = models.CharField(max_length=10, choices=ROL_CHOICES, default=ROL_VIEWER, verbose_name='Rol')

    class Meta:
        verbose_name = 'Perfil de usuario'
        verbose_name_plural = 'Perfiles de usuario'

    def __str__(self):
        return f'Perfil de {self.usuario.username}'

    @property
    def nombre_completo(self):
        nombre = self.usuario.get_full_name()
        return nombre if nombre else self.usuario.username


class MensajeChatbot(models.Model):
    """Historial persistente de conversaciones del chatbot por usuario."""
    ROLE_CHOICES = [('user', 'Usuario'), ('assistant', 'CURE-BOT')]
    usuario    = models.ForeignKey(User, on_delete=models.CASCADE, related_name='mensajes_chatbot', db_index=True)
    sesion     = models.ForeignKey('SesionChatbot', null=True, blank=True, on_delete=models.SET_NULL, related_name='mensajes')
    role       = models.CharField(max_length=10, choices=ROLE_CHOICES)
    content    = models.TextField()
    modelo_ia  = models.CharField(max_length=50, blank=True, verbose_name='Modelo IA usado')
    fecha      = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['fecha']
        verbose_name = 'Mensaje del chatbot'
        verbose_name_plural = 'Historial del chatbot'

    def __str__(self):
        return f'{self.usuario.username} [{self.role}] – {self.fecha:%Y-%m-%d %H:%M}'


# ═══════════════════════════════════════════════════════
#  Sesiones de Chat (estilo ChatGPT)
# ═══════════════════════════════════════════════════════
class SesionChatbot(models.Model):
    """Agrupa mensajes en conversaciones separadas por sesión."""
    usuario   = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sesiones_chatbot', db_index=True)
    titulo    = models.CharField(max_length=120, blank=True, default='Nueva conversación')
    creada    = models.DateTimeField(auto_now_add=True)
    actualizada = models.DateTimeField(auto_now=True)
    activa    = models.BooleanField(default=True)

    class Meta:
        ordering = ['-actualizada']
        verbose_name = 'Sesión de chatbot'
        verbose_name_plural = 'Sesiones de chatbot'

    def __str__(self):
        return f'{self.usuario.username} – {self.titulo} ({self.creada:%Y-%m-%d})'


# ═══════════════════════════════════════════════════════
#  Notificaciones internas del sistema
# ═══════════════════════════════════════════════════════
class Notificacion(models.Model):
    TIPO_CHOICES = [
        ('consulta',     '🩺 Nueva consulta'),
        ('remision',     '🚑 Remisión'),
        ('seguimiento',  '📋 Seguimiento'),
        ('inventario',   '💊 Inventario bajo'),
        ('sistema',      'ℹ️ Sistema'),
    ]
    usuario     = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='notificaciones',
        db_index=True
    )
    tipo        = models.CharField(max_length=20, choices=TIPO_CHOICES, default='sistema')
    titulo      = models.CharField(max_length=200)
    mensaje     = models.TextField()
    url         = models.CharField(max_length=300, blank=True)  # enlace opcional
    leida       = models.BooleanField(default=False, db_index=True)
    fecha       = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-fecha']
        verbose_name = 'Notificación'
        verbose_name_plural = 'Notificaciones'

    def __str__(self):
        return f'[{self.get_tipo_display()}] {self.titulo}'


# ═══════════════════════════════════════════════════════
#  Correos enviados al coordinador
# ═══════════════════════════════════════════════════════
class CorreoCoordinador(models.Model):
    MOTIVO_CHOICES = [
        ('urgencia',      '🚨 Urgencia médica'),
        ('remision',      '🚑 Remisión a centro médico'),
        ('accidente',     '⚠️ Accidente escolar'),
        ('medicamento',   '💊 Solicitud de medicamento'),
        ('seguimiento',   '📋 Informe de seguimiento'),
        ('inventario',    '📦 Inventario crítico'),
        ('ausentismo',    '📅 Ausentismo por salud'),
        ('otro',          '📝 Otro motivo'),
    ]
    remitente   = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='correos_enviados_coordinador'
    )
    correo_dest = models.EmailField(verbose_name='Correo del coordinador')
    motivo      = models.CharField(max_length=30, choices=MOTIVO_CHOICES)
    asunto      = models.CharField(max_length=200)
    cuerpo      = models.TextField(verbose_name='Mensaje')
    enviado     = models.BooleanField(default=False)
    fecha       = models.DateTimeField(auto_now_add=True)
    error_msg   = models.TextField(blank=True)

    class Meta:
        ordering = ['-fecha']
        verbose_name = 'Correo al coordinador'
        verbose_name_plural = 'Correos al coordinador'

    def __str__(self):
        return f'{self.get_motivo_display()} → {self.correo_dest} ({self.fecha:%d/%m/%Y})'


class CodigoVerificacion(models.Model):
    """Código OTP de 6 dígitos para verificar registro de nuevos usuarios."""
    email      = models.EmailField(db_index=True)
    username   = models.CharField(max_length=150)
    password   = models.CharField(max_length=255)  # hashed
    codigo     = models.CharField(max_length=6)
    creado_en  = models.DateTimeField(auto_now_add=True)
    verificado = models.BooleanField(default=False)

    class Meta:
        ordering = ['-creado_en']
        verbose_name = 'Código de verificación'

    def esta_vigente(self):
        from django.utils import timezone
        return (timezone.now() - self.creado_en).seconds < 600  # 10 min


# ═══════════════════════════════════════════════════════
#  Tracking de apertura de correos
# ═══════════════════════════════════════════════════════
class RegistroAperturaCorreo(models.Model):
    """
    Registra cuándo un destinatario abre un correo enviado por COSFA CURE.
    Se activa por píxel invisible (1x1px) o por enlace de confirmación manual.
    """
    TIPO_CHOICES = [
        ('coordinador', '📋 Correo al coordinador'),
        ('acudiente',   '👨‍👩‍👧 Correo a acudiente'),
        ('remision',    '🚑 Remisión médica'),
        ('inventario',  '💊 Alerta de inventario'),
        ('seguimiento', '📅 Alerta de seguimiento'),
    ]
    METODO_CHOICES = [
        ('pixel',        'Píxel automático'),
        ('confirmacion', 'Enlace de confirmación'),
    ]

    # Quién envió el correo (enfermera)
    enviado_por     = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='correos_tracking',
        verbose_name='Enviado por',
    )
    # Tipo de correo
    tipo            = models.CharField(max_length=20, choices=TIPO_CHOICES, db_index=True)
    # Referencia al objeto relacionado (consulta, remision, correo_coordinador)
    objeto_id       = models.PositiveIntegerField(null=True, blank=True, db_index=True,
                        verbose_name='ID del objeto relacionado')
    objeto_tipo     = models.CharField(max_length=50, blank=True,
                        verbose_name='Tipo de objeto (Consulta, Remision, etc.)')
    # Destinatario
    destinatario_email = models.EmailField(verbose_name='Email del destinatario')
    destinatario_nombre = models.CharField(max_length=200, blank=True,
                        verbose_name='Nombre del destinatario')
    # Token único para identificar este envío
    token           = models.CharField(max_length=64, unique=True, db_index=True)
    # Resultado
    abierto         = models.BooleanField(default=False, db_index=True)
    fecha_envio     = models.DateTimeField(auto_now_add=True)
    fecha_apertura  = models.DateTimeField(null=True, blank=True)
    metodo_apertura = models.CharField(max_length=15, choices=METODO_CHOICES,
                        blank=True, default='')
    # Extra: IP y User-Agent del que abrió (opcional, informativo)
    ip_apertura     = models.GenericIPAddressField(null=True, blank=True)
    user_agent      = models.TextField(blank=True)
    # Conteo de aperturas (el píxel puede dispararse varias veces)
    veces_abierto   = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['-fecha_envio']
        verbose_name = 'Registro de apertura de correo'
        verbose_name_plural = 'Registros de apertura de correos'
        indexes = [
            models.Index(fields=['token']),
            models.Index(fields=['abierto', 'tipo']),
        ]

    def __str__(self):
        estado = '✅ Abierto' if self.abierto else '⏳ Sin abrir'
        return f'{self.get_tipo_display()} → {self.destinatario_email} [{estado}]'
