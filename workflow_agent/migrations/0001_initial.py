# Initial migration for workflow_agent — enables pgvector extension

from django.db import migrations

try:
    from pgvector.django import VectorExtension
    _HAS_PGVECTOR = True
except ImportError:
    _HAS_PGVECTOR = False


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('workflow_orchestrator', '0001_initial'),
    ]

    operations = [
        VectorExtension() if _HAS_PGVECTOR else migrations.RunSQL(
            "CREATE EXTENSION IF NOT EXISTS vector;",
            reverse_sql="DROP EXTENSION IF EXISTS vector;"
        ),
    ]
