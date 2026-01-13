"""Drop old filtering tables (data migrated to scope_projectfilter)."""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('scope', '0001_initial'),
    ]

    operations = [
        migrations.RunSQL(
            sql="DROP TABLE IF EXISTS filtering_projectfilter_groups;",
            reverse_sql="",  # No reverse - data would be lost
        ),
        migrations.RunSQL(
            sql="DROP TABLE IF EXISTS filtering_projectfilter;",
            reverse_sql="",  # No reverse - data would be lost
        ),
    ]
