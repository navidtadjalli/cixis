"""Orders and OrderItems API with price snapshot and total recalculation."""
from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from .. import services
from ..models import Order, OrderItem, Product
from ..serializers import OrderItemSerializer, OrderSerializer

# Orders that may not have their items edited.
LOCKED_STATUSES = (Order.Status.PAID, Order.Status.CLOSED)


class OrderViewSet(viewsets.ModelViewSet):
    serializer_class = OrderSerializer
    queryset = Order.objects.all().prefetch_related("items", "payments")

    def get_queryset(self):
        qs = Order.objects.all().prefetch_related("items", "payments")
        params = self.request.query_params
        if params.get("status"):
            qs = qs.filter(status=params["status"])
        if params.get("table_id"):
            qs = qs.filter(table_id=params["table_id"])
        if params.get("date"):
            qs = qs.filter(business_date=params["date"])
        return qs

    def create(self, request, *args, **kwargs):
        mode = request.data.get("mode", Order.Mode.TABLE)
        table_id = request.data.get("table_id") or request.data.get("table")
        label = request.data.get("event_customer_label")

        if mode == Order.Mode.TABLE:
            if not table_id:
                raise ValidationError({"table_id": "برای سفارش میز، انتخاب میز الزامی است."})
            label = None
        elif mode == Order.Mode.EVENT:
            if not label:
                raise ValidationError(
                    {"event_customer_label": "برای حالت رویداد، نام مشتری الزامی است."}
                )
            table_id = None
        else:
            raise ValidationError({"mode": "حالت سفارش نامعتبر است."})

        order = Order.objects.create(
            mode=mode,
            table_id=table_id,
            event_customer_label=label,
            status=Order.Status.OPEN,
            business_date=services.business_today(),
        )
        return Response(
            self.get_serializer(order).data, status=status.HTTP_201_CREATED
        )

    def update(self, request, *args, **kwargs):
        # Only status + event_customer_label + table (move order) are mutable here.
        order = self.get_object()
        allowed = {}
        for field in ("status", "event_customer_label", "table"):
            if field in request.data:
                allowed[field] = request.data[field]
        if "table_id" in request.data:
            allowed["table"] = request.data["table_id"]
        for field, value in allowed.items():
            setattr(order, "table_id" if field == "table" else field, value)
        order.save()
        return Response(self.get_serializer(order).data)

    @action(detail=True, methods=["post"], url_path="items")
    def add_item(self, request, pk=None):
        order = self.get_object()
        if order.status in LOCKED_STATUSES:
            return Response(
                {"detail": "سفارش پرداخت‌شده/بسته‌شده قابل ویرایش نیست."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        product = get_object_or_404(
            Product, pk=request.data.get("product_id") or request.data.get("product")
        )
        quantity = int(request.data.get("quantity", 1))
        if quantity < 1:
            raise ValidationError({"quantity": "تعداد باید حداقل ۱ باشد."})

        item = OrderItem.objects.create(
            order=order,
            product=product,
            product_name_snapshot=product.name,
            unit_price_snapshot=product.price,
            quantity=quantity,
            line_total=product.price * quantity,
        )
        services.recalc_order_totals(order)
        return Response(
            OrderItemSerializer(item).data, status=status.HTTP_201_CREATED
        )


class OrderItemViewSet(viewsets.ModelViewSet):
    serializer_class = OrderItemSerializer
    queryset = OrderItem.objects.all()
    http_method_names = ["patch", "delete"]

    def _guard(self, item):
        if item.order.status in LOCKED_STATUSES:
            return Response(
                {"detail": "سفارش پرداخت‌شده/بسته‌شده قابل ویرایش نیست."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return None

    def partial_update(self, request, *args, **kwargs):
        item = self.get_object()
        blocked = self._guard(item)
        if blocked:
            return blocked
        quantity = int(request.data.get("quantity", item.quantity))
        if quantity < 1:
            raise ValidationError({"quantity": "تعداد باید حداقل ۱ باشد."})
        item.quantity = quantity
        item.line_total = item.unit_price_snapshot * quantity
        item.save(update_fields=["quantity", "line_total", "updated_at"])
        services.recalc_order_totals(item.order)
        return Response(OrderItemSerializer(item).data)

    def destroy(self, request, *args, **kwargs):
        item = self.get_object()
        blocked = self._guard(item)
        if blocked:
            return blocked
        order = item.order
        item.delete()
        services.recalc_order_totals(order)
        return Response(status=status.HTTP_204_NO_CONTENT)
