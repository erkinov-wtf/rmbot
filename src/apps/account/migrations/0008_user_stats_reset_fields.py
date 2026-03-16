from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("account", "0007_user_public_photo_blob_and_mime"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="stats_reset_at",
            field=models.DateTimeField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name="user",
            name="stats_reset_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.SET_NULL,
                related_name="+",
                to="account.user",
            ),
        ),
        migrations.AddField(
            model_name="user",
            name="stats_reset_note",
            field=models.CharField(blank=True, default="", max_length=500),
        ),
    ]
