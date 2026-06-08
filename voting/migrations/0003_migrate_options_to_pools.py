from django.db import migrations


def migrate_forward(apps, schema_editor):
    Poll = apps.get_model("voting", "Poll")
    Option = apps.get_model("voting", "Option")
    OptionsPool = apps.get_model("voting", "OptionsPool")

    for poll in Poll.objects.all():
        options = Option.objects.filter(poll=poll)
        if options.exists():
            pool = OptionsPool.objects.create(name=poll.title)
            options.update(pool=pool)
            poll.options_pool = pool
            poll.save(update_fields=["options_pool"])


def migrate_backward(apps, schema_editor):
    Option = apps.get_model("voting", "Option")
    Option.objects.filter(pool__isnull=False).update(pool=None)

    Poll = apps.get_model("voting", "Poll")
    Poll.objects.update(options_pool=None)

    OptionsPool = apps.get_model("voting", "OptionsPool")
    OptionsPool.objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [
        ("voting", "0002_optionspool_alter_option_poll_option_pool_and_more"),
    ]

    operations = [
        migrations.RunPython(migrate_forward, migrate_backward),
    ]
