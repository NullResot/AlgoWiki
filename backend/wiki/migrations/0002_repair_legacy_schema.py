from django.db import DatabaseError, migrations


MODEL_ORDER = [
    "User",
    "Category",
    "ExtensionPage",
    "Article",
    "ArticleComment",
    "ArticleStar",
    "RevisionProposal",
    "IssueTicket",
    "Question",
    "Answer",
    "Announcement",
    "AnnouncementRead",
    "ContributionEvent",
]


def _table_columns(connection, table_name):
    # For SQLite, introspection.get_table_description may be very slow on some
    # environments. Use PRAGMA directly to avoid expensive metadata probing.
    if connection.vendor == "sqlite":
        quoted_table = '"%s"' % table_name.replace('"', '""')
        with connection.cursor() as cursor:
            cursor.execute(f"PRAGMA table_info({quoted_table})")
            return {row[1] for row in cursor.fetchall()}

    with connection.cursor() as cursor:
        description = connection.introspection.get_table_description(cursor, table_name)
        return {column.name for column in description}


def repair_legacy_schema(apps, schema_editor):
    connection = schema_editor.connection
    known_tables = set(connection.introspection.table_names())

    for model_name in MODEL_ORDER:
        model = apps.get_model("wiki", model_name)
        table_name = model._meta.db_table

        if table_name not in known_tables:
            schema_editor.create_model(model)
            known_tables = set(connection.introspection.table_names())
            continue

        existing_columns = _table_columns(connection, table_name)
        for field in model._meta.local_fields:
            if field.column in existing_columns:
                continue
            try:
                schema_editor.add_field(model, field)
                existing_columns.add(field.column)
            except DatabaseError:
                existing_columns = _table_columns(connection, table_name)
                if field.column in existing_columns:
                    continue
                raise

        known_tables = set(connection.introspection.table_names())
        for many_to_many in model._meta.local_many_to_many:
            through_model = many_to_many.remote_field.through
            if not through_model._meta.auto_created:
                continue
            through_table = through_model._meta.db_table
            if through_table in known_tables:
                continue
            schema_editor.create_model(through_model)
            known_tables.add(through_table)


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("wiki", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(repair_legacy_schema, migrations.RunPython.noop),
    ]
