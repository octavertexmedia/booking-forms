from django.db import migrations


class Migration(migrations.Migration):
    """Match the live FK to the model: deleting a package must SET NULL on registrations."""

    dependencies = [
        ("workshop", "0005_reminder_hours"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                ALTER TABLE workshop_registration
                    DROP CONSTRAINT IF EXISTS workshop_registration_package_id_fkey;
                ALTER TABLE workshop_registration
                    ADD CONSTRAINT workshop_registration_package_id_fkey
                    FOREIGN KEY (package_id)
                    REFERENCES workshop_workshoppackage(id)
                    ON DELETE SET NULL
                    DEFERRABLE INITIALLY DEFERRED;
            """,
            reverse_sql="""
                ALTER TABLE workshop_registration
                    DROP CONSTRAINT IF EXISTS workshop_registration_package_id_fkey;
                ALTER TABLE workshop_registration
                    ADD CONSTRAINT workshop_registration_package_id_fkey
                    FOREIGN KEY (package_id)
                    REFERENCES workshop_workshoppackage(id)
                    DEFERRABLE INITIALLY DEFERRED;
            """,
        ),
    ]
