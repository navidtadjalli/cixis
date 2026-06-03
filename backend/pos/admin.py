"""Django admin registrations for POS models."""
from django.contrib import admin

from . import models

for _model in (
    models.Category,
    models.Product,
    models.Table,
    models.Order,
    models.OrderItem,
    models.Payment,
    models.DayClosing,
    models.ResourcePurchase,
    models.ResourceSuggestion,
    models.BackupRecord,
    models.MenuPublishRecord,
    models.SyncRecord,
    models.AppSetting,
):
    admin.site.register(_model)
