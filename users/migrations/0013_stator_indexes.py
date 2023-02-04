# Generated by Django 4.1.4 on 2023-02-04 01:05

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0012_block_states"),
    ]

    operations = [
        migrations.AlterField(
            model_name="block",
            name="state_ready",
            field=models.BooleanField(db_index=True, default=True),
        ),
        migrations.AlterField(
            model_name="domain",
            name="state_ready",
            field=models.BooleanField(db_index=True, default=True),
        ),
        migrations.AlterField(
            model_name="follow",
            name="state_ready",
            field=models.BooleanField(db_index=True, default=True),
        ),
        migrations.AlterField(
            model_name="identity",
            name="state_ready",
            field=models.BooleanField(db_index=True, default=True),
        ),
        migrations.AlterField(
            model_name="inboxmessage",
            name="state_ready",
            field=models.BooleanField(db_index=True, default=True),
        ),
        migrations.AlterField(
            model_name="passwordreset",
            name="state_ready",
            field=models.BooleanField(db_index=True, default=True),
        ),
        migrations.AlterField(
            model_name="report",
            name="state_ready",
            field=models.BooleanField(db_index=True, default=True),
        ),
        migrations.AlterIndexTogether(
            name="domain",
            index_together={("state_ready", "state_locked_until", "state")},
        ),
        migrations.AlterIndexTogether(
            name="inboxmessage",
            index_together={("state_ready", "state_locked_until", "state")},
        ),
        migrations.AlterIndexTogether(
            name="passwordreset",
            index_together={("state_ready", "state_locked_until", "state")},
        ),
        migrations.AlterIndexTogether(
            name="report",
            index_together={("state_ready", "state_locked_until", "state")},
        ),
    ]
