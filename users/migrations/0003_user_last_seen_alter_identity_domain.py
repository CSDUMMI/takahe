# Generated by Django 4.1.3 on 2022-11-17 04:18

import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0002_identity_public_key_id"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="last_seen",
            field=models.DateTimeField(
                auto_now_add=True, default=django.utils.timezone.now
            ),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name="identity",
            name="domain",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="identities",
                to="users.domain",
            ),
        ),
    ]
