"""
Migración 0009 — Índices de rendimiento para escala 1000+ estudiantes
Agrega db_index y Meta.indexes en todos los modelos críticos.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('enfermeria', '0008_perfilusuario_mensajechatbot'),
    ]

    operations = [
        # ── Estudiante ──────────────────────────────────────────────────────
        migrations.AlterField(
            model_name='estudiante',
            name='nombre',
            field=models.CharField(db_index=True, max_length=100, verbose_name='Nombre completo'),
        ),
        migrations.AlterField(
            model_name='estudiante',
            name='grado',
            field=models.CharField(
                choices=[('1A','1A'),('1B','1B'),('2A','2A'),('2B','2B'),('3A','3A'),('3B','3B'),
                         ('4A','4A'),('4B','4B'),('5A','5A'),('5B','5B'),('6A','6A'),('6B','6B'),
                         ('7A','7A'),('7B','7B'),('8A','8A'),('8B','8B'),('9A','9A'),('9B','9B'),
                         ('10A','10A'),('10B','10B'),('11A','11A'),('11B','11B')],
                db_index=True, max_length=5),
        ),
        migrations.AlterField(
            model_name='estudiante',
            name='sexo',
            field=models.CharField(
                blank=True,
                choices=[('M','Masculino'),('F','Femenino'),('O','Otro')],
                db_index=True, max_length=1, verbose_name='Sexo biológico'),
        ),
        migrations.AddIndex(
            model_name='estudiante',
            index=models.Index(fields=['nombre', 'grado'], name='enf_est_nombre_grado_idx'),
        ),
        migrations.AddIndex(
            model_name='estudiante',
            index=models.Index(fields=['grado', 'sexo'], name='enf_est_grado_sexo_idx'),
        ),

        # ── Consulta ────────────────────────────────────────────────────────
        migrations.AlterField(
            model_name='consulta',
            name='fecha_hora',
            field=models.DateTimeField(auto_now_add=True, db_index=True),
        ),
        migrations.AlterField(
            model_name='consulta',
            name='motivo',
            field=models.CharField(
                choices=[('dolor_cabeza','Dolor de cabeza'),('dolor_estomago','Dolor de estómago'),
                         ('fiebre','Fiebre'),('lesion','Lesión / Golpe'),('mareo','Mareo'),
                         ('nauseas','Náuseas / Vómito'),('dolor_garganta','Dolor de garganta'),
                         ('alergias','Reacción alérgica'),('otro','Otro')],
                db_index=True, max_length=50),
        ),
        migrations.AlterField(
            model_name='consulta',
            name='estado',
            field=models.CharField(
                choices=[('atendido','Atendido en enfermería'),('regreso_clase','Regreso a clases'),
                         ('remitido_casa','Remitido a casa'),('remitido_hospital','Remitido al hospital')],
                db_index=True, max_length=20),
        ),
        migrations.AddIndex(
            model_name='consulta',
            index=models.Index(fields=['-fecha_hora'], name='enf_con_fecha_desc_idx'),
        ),
        migrations.AddIndex(
            model_name='consulta',
            index=models.Index(fields=['estudiante', '-fecha_hora'], name='enf_con_est_fecha_idx'),
        ),
        migrations.AddIndex(
            model_name='consulta',
            index=models.Index(fields=['estado', '-fecha_hora'], name='enf_con_estado_fecha_idx'),
        ),
        migrations.AddIndex(
            model_name='consulta',
            index=models.Index(fields=['motivo', '-fecha_hora'], name='enf_con_motivo_fecha_idx'),
        ),

        # ── Remision ────────────────────────────────────────────────────────
        migrations.AlterField(
            model_name='remision',
            name='fecha_hora',
            field=models.DateTimeField(auto_now_add=True, db_index=True),
        ),
        migrations.AlterField(
            model_name='remision',
            name='estado',
            field=models.CharField(
                choices=[('pendiente','Pendiente'),('en_proceso','En proceso'),('resuelto','Resuelto')],
                db_index=True, default='pendiente', max_length=15),
        ),
        migrations.AddIndex(
            model_name='remision',
            index=models.Index(fields=['estado', '-fecha_hora'], name='enf_rem_estado_fecha_idx'),
        ),
        migrations.AddIndex(
            model_name='remision',
            index=models.Index(fields=['estudiante', '-fecha_hora'], name='enf_rem_est_fecha_idx'),
        ),

        # ── Seguimiento ─────────────────────────────────────────────────────
        migrations.AlterField(
            model_name='seguimiento',
            name='fecha',
            field=models.DateField(db_index=True, verbose_name='Fecha inicio'),
        ),
        migrations.AlterField(
            model_name='seguimiento',
            name='completado',
            field=models.BooleanField(db_index=True, default=False),
        ),
        migrations.AddIndex(
            model_name='seguimiento',
            index=models.Index(fields=['completado', 'fecha'], name='enf_seg_comp_fecha_idx'),
        ),

        # ── Medicamento ─────────────────────────────────────────────────────
        migrations.AlterField(
            model_name='medicamento',
            name='nombre',
            field=models.CharField(db_index=True, max_length=100),
        ),
        migrations.AlterField(
            model_name='medicamento',
            name='categoria',
            field=models.CharField(
                choices=[('insumo','Insumo / Primeros auxilios'),
                         ('medicamento','Medicamento (requiere prescripción)')],
                db_index=True, default='insumo', max_length=20, verbose_name='Categoría'),
        ),
        migrations.AlterField(
            model_name='medicamento',
            name='fecha_vencimiento',
            field=models.DateField(db_index=True),
        ),

        # ── HistorialCambio ─────────────────────────────────────────────────
        migrations.AlterField(
            model_name='historialcambio',
            name='fecha',
            field=models.DateTimeField(auto_now_add=True, db_index=True),
        ),

        # ── MensajeChatbot ──────────────────────────────────────────────────
        migrations.AlterField(
            model_name='mensajechatbot',
            name='fecha',
            field=models.DateTimeField(auto_now_add=True, db_index=True),
        ),
        migrations.AlterField(
            model_name='movimientoinventario',
            name='fecha',
            field=models.DateTimeField(auto_now_add=True, db_index=True),
        ),
    ]
