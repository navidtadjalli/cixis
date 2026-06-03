"""DRF serializers for the POS API."""
from rest_framework import serializers

from . import services
from .models import Category, Product, Table


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name", "sort_order", "is_active"]
        read_only_fields = ["id", "is_active"]


class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = [
            "id",
            "category",
            "name",
            "description",
            "price",
            "is_available",
            "is_active",
            "sort_order",
        ]
        read_only_fields = ["id", "is_active"]


class TableSerializer(serializers.ModelSerializer):
    """Table list/detail with derived (not stored) status + active order summary."""

    active_order_id = serializers.SerializerMethodField()
    active_order_total = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()

    class Meta:
        model = Table
        fields = [
            "id",
            "name",
            "sort_order",
            "active_order_id",
            "active_order_total",
            "status",
        ]
        read_only_fields = ["id"]

    def _active(self, obj):
        # Cache per-instance to avoid 3 queries per row.
        if not hasattr(obj, "_active_order_cache"):
            obj._active_order_cache = services.active_order_for_table(obj)
        return obj._active_order_cache

    def get_active_order_id(self, obj):
        order = self._active(obj)
        return order.id if order else None

    def get_active_order_total(self, obj):
        order = self._active(obj)
        return order.subtotal if order else 0

    def get_status(self, obj):
        return services.table_status(self._active(obj))
