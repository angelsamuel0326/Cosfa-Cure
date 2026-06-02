from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('enfermeria', '0024_crear_admin_jenifer'),
    ]
    operations = [
        migrations.AlterField(
            model_name='remision',
            name='acompanante',
            field=models.CharField(blank=True, default='', max_length=100),
        ),
    ]
