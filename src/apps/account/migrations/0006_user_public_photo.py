from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("account", "0005_remove_user_email_remove_user_patronymic"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="public_photo",
            field=models.FileField(
                blank=True,
                null=True,
                upload_to="users/public_photos/",
            ),
        ),
    ]
