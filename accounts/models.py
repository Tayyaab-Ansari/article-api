from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    """Our own user model, built on Django's AbstractUser.

    It is empty for now, but having it from day one means we can add
    fields later (phone, avatar, ...) without a painful migration.
    """