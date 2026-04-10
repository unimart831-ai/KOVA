"""
Reusable soft-delete mixin for models that should never be hard-deleted.
Adds is_deleted + deleted_at fields and a custom manager that excludes deleted rows by default.
"""

from django.db import models
from django.utils import timezone


class SoftDeleteQuerySet(models.QuerySet):
    def delete(self):
        """Soft-delete: set is_deleted=True instead of removing rows."""
        return self.update(is_deleted=True, deleted_at=timezone.now())

    def hard_delete(self):
        """Actually remove rows from the database (use with caution)."""
        return super().delete()

    def alive(self):
        return self.filter(is_deleted=False)

    def dead(self):
        return self.filter(is_deleted=True)


class SoftDeleteManager(models.Manager):
    """Default manager that excludes soft-deleted rows."""

    def get_queryset(self):
        return SoftDeleteQuerySet(self.model, using=self._db).alive()


class SoftDeleteUserManager(SoftDeleteManager):
    """
    Soft-delete manager for User models.
    Inherits from SoftDeleteManager but adds get_by_natural_key and
    create_user/create_superuser needed by Django's auth system.
    """

    def get_by_natural_key(self, username):
        return self.get(**{self.model.USERNAME_FIELD: username})

    @classmethod
    def normalize_email(cls, email):
        """Normalize email by lowercasing the domain part (required by AbstractUser.clean)."""
        email = email or ""
        try:
            email_name, domain_part = email.strip().rsplit("@", 1)
        except ValueError:
            pass
        else:
            email = email_name + "@" + domain_part.lower()
        return email

    def create_user(self, username=None, email=None, password=None, **extra_fields):
        from django.contrib.auth.models import UserManager
        manager = UserManager()
        manager.model = self.model
        manager.auto_created = True
        manager._db = self._db
        return manager.create_user(username=username, email=email, password=password, **extra_fields)

    def create_superuser(self, username=None, email=None, password=None, **extra_fields):
        from django.contrib.auth.models import UserManager
        manager = UserManager()
        manager.model = self.model
        manager.auto_created = True
        manager._db = self._db
        return manager.create_superuser(username=username, email=email, password=password, **extra_fields)


class AllObjectsManager(models.Manager):
    """Manager that includes soft-deleted rows."""

    def get_queryset(self):
        return SoftDeleteQuerySet(self.model, using=self._db)


class SoftDeleteMixin(models.Model):
    """
    Add to any model that needs soft-delete behaviour.

    Usage:
        class MyModel(SoftDeleteMixin, models.Model):
            ...

    - MyModel.objects  → excludes deleted rows (default)
    - MyModel.all_objects → includes deleted rows
    - instance.soft_delete() → marks as deleted
    - instance.restore() → un-deletes
    """

    is_deleted = models.BooleanField(default=False, db_index=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    objects = SoftDeleteManager()
    all_objects = AllObjectsManager()

    class Meta:
        abstract = True

    def soft_delete(self):
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save(update_fields=["is_deleted", "deleted_at"])

    def restore(self):
        self.is_deleted = False
        self.deleted_at = None
        self.save(update_fields=["is_deleted", "deleted_at"])
