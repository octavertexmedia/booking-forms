from django.db import migrations


def set_null_on_package_delete(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            "ALTER TABLE workshop_registration "
            "DROP CONSTRAINT IF EXISTS workshop_registration_package_id_fkey"
        )
        cursor.execute(
            "ALTER TABLE workshop_registration "
            "ADD CONSTRAINT workshop_registration_package_id_fkey "
            "FOREIGN KEY (package_id) REFERENCES workshop_workshoppackage(id) "
            "ON DELETE SET NULL DEFERRABLE INITIALLY DEFERRED"
        )


def restore_restrict_package_delete(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            "ALTER TABLE workshop_registration "
            "DROP CONSTRAINT IF EXISTS workshop_registration_package_id_fkey"
        )
        cursor.execute(
            "ALTER TABLE workshop_registration "
            "ADD CONSTRAINT workshop_registration_package_id_fkey "
            "FOREIGN KEY (package_id) REFERENCES workshop_workshoppackage(id) "
            "DEFERRABLE INITIALLY DEFERRED"
        )


class Migration(migrations.Migration):
    """Match the live FK to the model: deleting a package must SET NULL on registrations."""

    dependencies = [
        ("workshop", "0005_reminder_hours"),
    ]

    operations = [
        migrations.RunPython(set_null_on_package_delete, restore_restrict_package_delete),
    ]
