from django.db import migrations


def roles(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Group.objects.get_or_create(name="Manager")
    Group.objects.get_or_create(name="Employee")


class Migration(migrations.Migration):
    dependencies = [("crm", "0001_initial"), ("auth", "0012_alter_user_first_name_max_length")]
    operations = [migrations.RunPython(roles, migrations.RunPython.noop)]
