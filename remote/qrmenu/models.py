from django.db import models


class CafeMenuSnapshot(models.Model):
    cafe_slug = models.CharField(max_length=120, db_index=True)
    payload = models.JSONField()
    version = models.CharField(max_length=120)
    published_at = models.DateTimeField()
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-received_at"]
        indexes = [
            models.Index(fields=["cafe_slug", "-received_at"]),
        ]

    def __str__(self):
        return f"{self.cafe_slug} ({self.version})"


class DayClosingSyncRecord(models.Model):
    cafe_slug = models.CharField(max_length=120)
    payload = models.JSONField()
    business_date = models.DateField()
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-received_at"]
        indexes = [
            models.Index(fields=["cafe_slug", "business_date"]),
        ]

    def __str__(self):
        return f"{self.cafe_slug} - {self.business_date}"
