"""DRF serializers for the POS API."""
from rest_framework import serializers

from . import services
from .models import (
    Category,
    Order,
    OrderItem,
    Payment,
    Product,
    ResourcePurchase,
    Table,
)


class ResourcePurchaseSerializer(serializers.ModelSerializer):
    class Meta:
        model = ResourcePurchase
        fields = [
            "id",
            "name",
            "quantity",
            "unit",
            "cost",
            "note",
            "business_date",
            "created_at",
        ]
        read_only_fields = ["id", "business_date", "created_at"]


class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = [
            "id",
            "order",
            "product",
            "product_name_snapshot",
            "unit_price_snapshot",
            "quantity",
            "paid_quantity",
            "line_total",
        ]
        read_only_fields = [
            "id",
            "order",
            "product_name_snapshot",
            "unit_price_snapshot",
            "paid_quantity",
            "line_total",
        ]


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = ["id", "order", "amount", "method", "payer_label", "note", "created_at"]
        read_only_fields = ["id", "order", "created_at"]


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    payments = PaymentSerializer(many=True, read_only=True)
    table_id = serializers.IntegerField(source="table.id", read_only=True)
    table_name = serializers.CharField(source="table.name", read_only=True, default=None)

    class Meta:
        model = Order
        fields = [
            "id",
            "order_number",
            "mode",
            "table",
            "table_id",
            "table_name",
            "event_customer_label",
            "is_preset",
            "status",
            "subtotal",
            "paid_amount",
            "remaining_amount",
            "business_date",
            "opened_at",
            "closed_at",
            "items",
            "payments",
        ]
        read_only_fields = [
            "id",
            "order_number",
            "is_preset",
            "subtotal",
            "paid_amount",
            "remaining_amount",
            "business_date",
            "opened_at",
            "closed_at",
        ]


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
            "is_publishable",
            "is_active",
            "sort_order",
        ]
        read_only_fields = ["id", "is_active"]


class TableSerializer(serializers.ModelSerializer):
    """Table list/detail with derived (not stored) status + active order summary."""

    active_order_id = serializers.SerializerMethodField()
    active_order_total = serializers.SerializerMethodField()
    active_order_created_at = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()

    class Meta:
        model = Table
        fields = [
            "id",
            "name",
            "sort_order",
            "active_order_id",
            "active_order_total",
            "active_order_created_at",
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

    def get_active_order_created_at(self, obj):
        order = self._active(obj)
        return order.created_at if order else None

    def get_status(self, obj):
        return services.table_status(self._active(obj))
