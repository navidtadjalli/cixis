"""DRF serializers for the POS API."""
from decimal import Decimal

from rest_framework import serializers

from . import services, staff_shift
from .models import (
    Category,
    Employee,
    GuestCode,
    Order,
    OrderItem,
    Payment,
    Product,
    ResourcePurchase,
    ShiftAttendance,
    StaffConsumption,
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
        fields = ["id", "name", "sort_order", "is_active", "staff_free_monthly_quota"]
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
            "staff_free_monthly_quota",
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


class EmployeeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Employee
        fields = ["id", "name", "sort_order", "is_active"]
        read_only_fields = ["id", "is_active"]


class ShiftAttendanceSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source="employee.name", read_only=True)
    # Derived from the shift bounds so the entry screen can echo the tally back
    # without re-implementing the math; the monthly report recomputes the same.
    late_minutes = serializers.SerializerMethodField()
    early_minutes = serializers.SerializerMethodField()
    overtime_minutes = serializers.SerializerMethodField()
    shift_count = serializers.SerializerMethodField()

    class Meta:
        model = ShiftAttendance
        fields = [
            "id",
            "employee",
            "employee_name",
            "business_date",
            "shift",
            "check_in",
            "check_out",
            "is_full_day",
            "late_minutes",
            "early_minutes",
            "overtime_minutes",
            "shift_count",
        ]
        read_only_fields = ["id"]
        # The view upserts on (employee, business_date, shift) via
        # update_or_create, so drop the auto unique-together validator that would
        # otherwise 400 a re-save of an existing row.
        validators = []

    def _metrics(self, obj):
        return staff_shift.compute(
            obj.shift, obj.is_full_day, obj.check_in, obj.check_out
        )

    def get_late_minutes(self, obj):
        return self._metrics(obj)["late_minutes"]

    def get_early_minutes(self, obj):
        return self._metrics(obj)["early_minutes"]

    def get_overtime_minutes(self, obj):
        return self._metrics(obj)["overtime_minutes"]

    def get_shift_count(self, obj):
        return self._metrics(obj)["shift_count"]


class StaffConsumptionSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source="employee.name", read_only=True)
    quantity = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=Decimal("0.01"),
        coerce_to_string=False,
        required=False,
        default=Decimal("1"),
    )
    line_total = serializers.DecimalField(
        max_digits=14,
        decimal_places=2,
        coerce_to_string=False,
        read_only=True,
    )

    class Meta:
        model = StaffConsumption
        fields = [
            "id",
            "employee",
            "employee_name",
            "business_date",
            "shift",
            "product",
            "product_name_snapshot",
            "unit_price_snapshot",
            "quantity",
            "line_total",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "product_name_snapshot",
            "unit_price_snapshot",
            "line_total",
            "created_at",
        ]
        # Defaulted to today's business date in create when omitted.
        extra_kwargs = {"business_date": {"required": False}}

    def create(self, validated_data):
        """Snapshot the product name/price and compute the line total on write."""
        product = validated_data["product"]
        quantity = validated_data.get("quantity", Decimal("1"))
        validated_data["product_name_snapshot"] = product.name
        validated_data["unit_price_snapshot"] = product.price
        validated_data["line_total"] = Decimal(product.price) * quantity
        if not validated_data.get("business_date"):
            validated_data["business_date"] = services.business_today()
        return super().create(validated_data)


class GuestCodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = GuestCode
        fields = [
            "id",
            "code",
            "guest_name",
            "guest_count",
            "men_count",
            "women_count",
            "paid_entry",
            "sort_order",
        ]
        read_only_fields = ["id"]
