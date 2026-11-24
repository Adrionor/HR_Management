from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('reclutamiento', '0010_perfilusuario_notificaciones_telegram_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='puesto',
            name='fecha_registro_sla',
            field=models.DateTimeField(blank=True, editable=False, null=True),
        ),
        migrations.AddField(
            model_name='perfilusuario',
            name='telegram_token_creado',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='proceso',
            name='fecha_envio_jefe_apto',
            field=models.DateTimeField(blank=True, editable=False, null=True),
        ),
    ]
