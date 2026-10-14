from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("candidates", "0002_channel_labels"),
    ]

    operations = [
        # Every screening before CONTRACTS v4 was for the one driver role; new rows always set it.
        migrations.AddField(
            model_name="conversation",
            name="vacancy_id",
            field=models.CharField(db_index=True, default="driver", max_length=64),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="conversation",
            name="preference_score",
            field=models.FloatField(db_index=True, default=0.0),
        ),
    ]
