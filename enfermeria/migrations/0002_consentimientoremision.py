from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    """
    Añade la tabla ConsentimientoRemision (nueva en v16).
    Esta sí se aplica normalmente (no requiere --fake).
    """

    dependencies = [
        ('enfermeria', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='ConsentimientoRemision',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('fecha_firma', models.DateTimeField(auto_now_add=True)),
                ('firma_acudiente', models.TextField(verbose_name='Firma acudiente (base64 SVG)')),
                ('firma_enfermera', models.TextField(verbose_name='Firma enfermera (base64 SVG)')),
                ('nombre_acudiente', models.CharField(blank=True, max_length=150)),
                ('nombre_enfermera', models.CharField(blank=True, max_length=150)),
                ('cc_acudiente', models.CharField(blank=True, max_length=20, verbose_name='CC acudiente')),
                ('remision', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='consentimiento',
                    to='enfermeria.remision',
                )),
            ],
            options={
                'verbose_name': 'Consentimiento de Remisión',
                'verbose_name_plural': 'Consentimientos de Remisión',
                'ordering': ['-fecha_firma'],
            },
        ),
    ]
