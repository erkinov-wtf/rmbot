from django.contrib.auth.base_user import AbstractBaseUser
from django.db import models

from account import managers
from core.models import SoftDeleteModel, TimestampedModel
from core.utils.constants import AccessRequestStatus, EmployeeLevel, RoleSlug


class Role(TimestampedModel, SoftDeleteModel):
    name = models.CharField(max_length=80)
    slug = models.CharField(max_length=50, unique=True, choices=RoleSlug.choices)

    def __str__(self) -> str:
        return f"{self.name} ({self.slug})"


class User(AbstractBaseUser, TimestampedModel, SoftDeleteModel):
    first_name = models.CharField(max_length=30)
    last_name = models.CharField(max_length=30, blank=True, null=True)
    patronymic = models.CharField(max_length=100, blank=True, null=True)

    username = models.CharField(max_length=150, unique=True)
    phone = models.CharField(max_length=15, unique=True, null=True, blank=True)
    email = models.EmailField(unique=True)
    level = models.PositiveSmallIntegerField(
        choices=EmployeeLevel.choices, default=EmployeeLevel.L1, db_index=True
    )

    roles = models.ManyToManyField(
        Role, through="UserRole", related_name="users", blank=True
    )

    # For Django Admin
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    USERNAME_FIELD = "username"
    REQUIRED_FIELDS = ["first_name", "email"]

    objects = managers.UserManager()

    def __str__(self):
        return f"{self.first_name} (@{self.get_username()})"

    def get_navigation_title(self):
        return f"{self.first_name} {self.last_name}"

    def has_perm(self, perm, obj=None):
        return self.is_superuser

    def has_module_perms(self, app_label):
        return self.is_superuser

    def save(self, *args, **kwargs):
        from django.contrib.auth.hashers import make_password

        if self.password and not self.password.startswith("pbkdf2_sha256$"):
            self.password = make_password(self.password)  # Hash the password

        return super().save(*args, **kwargs)


class UserRole(TimestampedModel, SoftDeleteModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="user_roles")
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name="user_roles")

    class Meta:
        unique_together = ("user", "role")

    def __str__(self) -> str:
        return f"{self.user} -> {self.role}"


class TelegramProfile(TimestampedModel, SoftDeleteModel):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="telegram_profiles",
        null=True,
        blank=True,
    )
    telegram_id = models.BigIntegerField(unique=True, db_index=True)
    username = models.CharField(max_length=32, blank=True, null=True)
    first_name = models.CharField(max_length=255, blank=True, null=True)
    last_name = models.CharField(max_length=255, blank=True, null=True)
    language_code = models.CharField(max_length=8, blank=True, null=True)
    is_bot = models.BooleanField(default=False)
    is_premium = models.BooleanField(default=False)
    verified_at = models.DateTimeField(null=True, blank=True)

    def __str__(self) -> str:
        return f"tg:{self.telegram_id} (@{self.username})"


class AccessRequest(TimestampedModel, SoftDeleteModel):
    telegram_id = models.BigIntegerField(db_index=True)
    username = models.CharField(max_length=32, blank=True, null=True)
    first_name = models.CharField(max_length=255, blank=True, null=True)
    last_name = models.CharField(max_length=255, blank=True, null=True)
    phone = models.CharField(max_length=15, blank=True, null=True)
    note = models.TextField(blank=True, null=True)
    status = models.CharField(
        max_length=20,
        choices=AccessRequestStatus.choices,
        default=AccessRequestStatus.PENDING,
        db_index=True,
    )
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="access_requests",
    )
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["telegram_id", "status"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["telegram_id"],
                condition=models.Q(status=AccessRequestStatus.PENDING),
                name="unique_pending_access_request_per_telegram",
            )
        ]

    def __str__(self) -> str:
        return f"AccessRequest tg:{self.telegram_id} ({self.status})"
