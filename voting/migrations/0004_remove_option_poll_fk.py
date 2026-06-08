from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("voting", "0003_migrate_options_to_pools"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="option",
            name="poll",
        ),
        migrations.AlterField(
            model_name="option",
            name="pool",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="options",
                to="voting.optionspool",
            ),
        ),
    ]
