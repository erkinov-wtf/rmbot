from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("account", "0006_user_public_photo"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="public_photo_blob",
            field=models.BinaryField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="user",
            name="public_photo_mime",
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
    ]
