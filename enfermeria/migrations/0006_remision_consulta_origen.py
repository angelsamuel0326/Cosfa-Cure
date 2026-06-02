from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [
        ('enfermeria', '0005_seguimiento_evolucion'),
    ]
    operations = [
        migrations.AddField(
            model_name='remision',
            name='consulta_origen',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='remisiones_auto',
                to='enfermeria.consulta',
                verbose_name='Consulta de origen',
            ),
        ),
    ]
