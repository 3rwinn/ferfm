# Generated by Django 5.0.6 on 2025-05-02 11:10

import django.db.models.deletion
import knowledge_base.models
import pgvector.django.vector
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("knowledge_base", "0001_enable_pgvector"),
    ]

    operations = [
        migrations.CreateModel(
            name="KnowledgeDocument",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "file",
                    models.FileField(
                        upload_to=knowledge_base.models.knowledge_upload_path,
                        verbose_name="Document File",
                    ),
                ),
                (
                    "original_filename",
                    models.CharField(
                        blank=True, max_length=255, verbose_name="Original Filename"
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("PENDING", "Pending"),
                            ("PROCESSING", "Processing"),
                            ("COMPLETED", "Completed"),
                            ("FAILED", "Failed"),
                        ],
                        default="PENDING",
                        max_length=20,
                        verbose_name="Processing Status",
                    ),
                ),
                (
                    "uploaded_at",
                    models.DateTimeField(auto_now_add=True, verbose_name="Uploaded At"),
                ),
                (
                    "processed_at",
                    models.DateTimeField(
                        blank=True, null=True, verbose_name="Processed At"
                    ),
                ),
                (
                    "error_message",
                    models.TextField(
                        blank=True, null=True, verbose_name="Error Message"
                    ),
                ),
            ],
            options={
                "verbose_name": "Knowledge Document",
                "verbose_name_plural": "Knowledge Documents",
                "ordering": ["-uploaded_at"],
            },
        ),
        migrations.CreateModel(
            name="DocumentChunk",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("text_content", models.TextField(verbose_name="Text Content")),
                (
                    "embedding",
                    pgvector.django.vector.VectorField(
                        dimensions=384, verbose_name="Embedding"
                    ),
                ),
                (
                    "metadata",
                    models.JSONField(blank=True, null=True, verbose_name="Metadata"),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "document",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="chunks",
                        to="knowledge_base.knowledgedocument",
                        verbose_name="Parent Document",
                    ),
                ),
            ],
            options={
                "verbose_name": "Document Chunk",
                "verbose_name_plural": "Document Chunks",
                "indexes": [
                    models.Index(
                        fields=["document"], name="knowledge_b_documen_279ad4_idx"
                    )
                ],
            },
        ),
    ]
