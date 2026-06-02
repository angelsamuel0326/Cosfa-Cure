from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('enfermeria', '0011_consulta_hora_atencion_consultadocente'),
    ]

    operations = [
        migrations.CreateModel(
            name='Docente',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nombre', models.CharField(db_index=True, max_length=150, verbose_name='Nombre completo')),
                ('cedula', models.CharField(max_length=20, unique=True, verbose_name='Cédula de ciudadanía')),
                ('fecha_nacimiento', models.DateField(verbose_name='Fecha de nacimiento')),
                ('sexo', models.CharField(blank=True, choices=[('M', 'Masculino'), ('F', 'Femenino'), ('O', 'Otro')], max_length=1, verbose_name='Sexo biológico')),
                ('tipo', models.CharField(default='Docente', max_length=30, verbose_name='Tipo')),
                ('area', models.CharField(choices=[
                    ('matematicas','Matemáticas'),('ciencias_naturales','Ciencias Naturales'),
                    ('ciencias_sociales','Ciencias Sociales'),('lenguaje','Lenguaje / Español'),
                    ('ingles','Inglés'),('educacion_fisica','Educación Física'),
                    ('arte','Arte / Música'),('tecnologia','Tecnología / Informática'),
                    ('religion','Religión'),('etica','Ética y Valores'),
                    ('preescolar','Preescolar'),('primaria','Primaria'),
                    ('coordinacion','Coordinación'),('directivo','Directivo'),
                    ('administrativo','Administrativo'),('otro','Otro'),
                ], max_length=30, verbose_name='Área / Cargo')),
                ('grados_asignados', models.CharField(blank=True, max_length=200, verbose_name='Grados / Grupos que atiende')),
                ('vinculacion', models.CharField(blank=True, choices=[
                    ('planta','Planta'),('provisional','Provisional'),
                    ('contrato','Contrato'),('hora_catedra','Hora cátedra'),
                ], max_length=20, verbose_name='Tipo de vinculación')),
                ('telefono', models.CharField(max_length=20, verbose_name='Teléfono celular')),
                ('telefono_alternativo', models.CharField(blank=True, max_length=20, verbose_name='Teléfono alternativo')),
                ('correo', models.EmailField(blank=True, verbose_name='Correo institucional')),
                ('correo_personal', models.EmailField(blank=True, verbose_name='Correo personal')),
                ('direccion_residencia', models.CharField(blank=True, max_length=200, verbose_name='Dirección de residencia')),
                ('tipo_sangre', models.CharField(blank=True, choices=[('A+','A+'),('A-','A-'),('B+','B+'),('B-','B-'),('AB+','AB+'),('AB-','AB-'),('O+','O+'),('O-','O-')], max_length=5, verbose_name='Tipo de sangre')),
                ('eps', models.CharField(blank=True, max_length=100, verbose_name='EPS / Aseguradora')),
                ('regimen', models.CharField(blank=True, choices=[('contributivo','Contributivo'),('subsidiado','Subsidiado'),('especial','Régimen especial'),('ninguno','Sin aseguramiento')], max_length=15, verbose_name='Régimen de salud')),
                ('alergias', models.TextField(blank=True, verbose_name='Alergias conocidas')),
                ('condiciones_medicas', models.TextField(blank=True, verbose_name='Condiciones médicas')),
                ('medicamentos_perm', models.TextField(blank=True, verbose_name='Medicamentos de uso permanente')),
                ('contacto_emergencia', models.CharField(blank=True, max_length=100, verbose_name='Contacto de emergencia')),
                ('parentesco_emergencia', models.CharField(blank=True, max_length=50, verbose_name='Parentesco')),
                ('tel_emergencia', models.CharField(blank=True, max_length=20, verbose_name='Teléfono de emergencia')),
                ('foto', models.ImageField(blank=True, null=True, upload_to='docentes/')),
                ('fecha_registro', models.DateTimeField(auto_now_add=True)),
                ('activo', models.BooleanField(default=True, verbose_name='Activo en la institución')),
            ],
            options={
                'verbose_name': 'Docente',
                'verbose_name_plural': 'Docentes',
                'ordering': ['nombre'],
            },
        ),
        migrations.AddIndex(
            model_name='docente',
            index=models.Index(fields=['nombre'], name='enfermeria__nombre_doc_idx'),
        ),
        migrations.AddIndex(
            model_name='docente',
            index=models.Index(fields=['cedula'], name='enfermeria__cedula_doc_idx'),
        ),
        migrations.AddIndex(
            model_name='docente',
            index=models.Index(fields=['area'], name='enfermeria__area_doc_idx'),
        ),
        migrations.AddField(
            model_name='consultadocente',
            name='docente',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='consultas_docente',
                to='enfermeria.docente',
            ),
        ),
    ]
