# Generated by Django 4.1.7 on 2023-02-14 22:30

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("activities", "0010_stator_indexes"),
    ]

    operations = [
        migrations.AddField(
            model_name="postinteraction",
            name="value",
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
        migrations.AlterField(
            model_name="postinteraction",
            name="type",
            field=models.CharField(
                choices=[("like", "Like"), ("boost", "Boost"), ("vote", "Vote")],
                max_length=100,
            ),
        ),
    ]
