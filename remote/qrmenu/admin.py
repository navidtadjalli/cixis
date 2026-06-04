from django.contrib import admin

from .models import CafeMenuSnapshot, DayClosingSyncRecord


@admin.register(CafeMenuSnapshot)
class CafeMenuSnapshotAdmin(admin.ModelAdmin):
    list_display = ("cafe_slug", "version", "published_at", "received_at")
    list_filter = ("cafe_slug",)
    search_fields = ("cafe_slug", "version")
    readonly_fields = ("received_at",)


@admin.register(DayClosingSyncRecord)
class DayClosingSyncRecordAdmin(admin.ModelAdmin):
    list_display = ("cafe_slug", "business_date", "received_at")
    list_filter = ("cafe_slug", "business_date")
    search_fields = ("cafe_slug",)
    readonly_fields = ("received_at",)
