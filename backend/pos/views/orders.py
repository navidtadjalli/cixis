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

        # Resolve a requested table move first so we can swap, not orphan.
        new_table_id = None
        if "table_id" in request.data:
            new_table_id = request.data["table_id"]
        elif "table" in request.data:
            new_table_id = request.data["table"]

        if new_table_id is not None and str(new_table_id) != str(order.table_id):
            from ..models import Table

            old_table_id = order.table_id
            target = get_object_or_404(Table, pk=new_table_id)
            # If the destination already holds an active order, push that order
            # onto the vacated table instead of leaving it orphaned (its table
            # was being overwritten). This makes a move into an occupied table a
            # two-way swap of the orders.
            existing = services.active_order_for_table(target)
            if existing and existing.id != order.id and old_table_id is not None:
                existing.table_id = old_table_id
                existing.save(update_fields=["table_id", "updated_at"])
            order.table_id = target.id

        for field in ("status", "event_customer_label"):
            if field in request.data:
                setattr(order, field, request.data[field])
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
        # NOTE: deliberately no day-close check. Day-closing is administrative
        # and may run a day late; the cafe keeps serving across the close (e.g.
        # Ramadan 4am opens), so orders must stay editable regardless of it.
        product = get_object_or_404(
            Product, pk=request.data.get("product_id") or request.data.get("product")
        )
        quantity = int(request.data.get("quantity", 1))
        if quantity < 1:
            raise ValidationError({"quantity": "تعداد باید حداقل ۱ باشد."})

        # Merge into an existing line for the same product at the same price
        # so repeated clicks bump the quantity instead of adding new cards.
        item = order.items.filter(
            product=product, unit_price_snapshot=product.price
        ).first()
        if item is not None:
            item.quantity += quantity
            item.line_total = item.unit_price_snapshot * item.quantity
            item.save(update_fields=["quantity", "line_total", "updated_at"])
            created = False
        else:
            item = OrderItem.objects.create(
                order=order,
                product=product,
                product_name_snapshot=product.name,
                unit_price_snapshot=product.price,
                quantity=quantity,
                line_total=product.price * quantity,
            )
            created = True
        services.recalc_order_totals(order)
        return Response(
            OrderItemSerializer(item).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], url_path="add-items-from")
    def add_items_from(self, request, pk=None):
        """Move every item of ``source_order_id`` into this order.

        Lines for the same product at the same snapshot price merge by quantity;
        the source order is left empty (and becomes deletable).
        """
        target = self.get_object()
        if target.status in LOCKED_STATUSES:
            return Response(
                {"detail": "سفارش پرداخت‌شده/بسته‌شده قابل ویرایش نیست."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        source_id = request.data.get("source_order_id") or request.data.get("source")
        source = get_object_or_404(Order, pk=source_id)
        if source.id == target.id:
            raise ValidationError({"source_order_id": "مبدأ و مقصد یکسان است."})
        if source.status in LOCKED_STATUSES:
            return Response(
                {"detail": "سفارش مبدأ پرداخت‌شده/بسته‌شده است."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        for item in list(source.items.all()):
            existing = target.items.filter(
                product=item.product,
                unit_price_snapshot=item.unit_price_snapshot,
            ).first()
            if existing is not None:
                existing.quantity += item.quantity
                existing.line_total = existing.unit_price_snapshot * existing.quantity
                existing.save(update_fields=["quantity", "line_total", "updated_at"])
                item.delete()
            else:
                item.order = target
                item.save(update_fields=["order", "updated_at"])

        services.recalc_order_totals(source)
        services.recalc_order_totals(target)
        return Response(self.get_serializer(target).data)

    @action(detail=True, methods=["post"], url_path="payments")
    def add_payment(self, request, pk=None):
        from .payments import create_payment

        return create_payment(self.get_object(), request)

    def destroy(self, request, *args, **kwargs):
        order = self.get_object()
        # An order can only be discarded while it is genuinely empty — no items
        # and no recorded payments. Anything with history must be settled, not
        # deleted, to keep day-closing totals honest.
        if order.items.exists():
            return Response(
                {"detail": "سفارش دارای اقلام است و قابل حذف نیست."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if order.payments.exists():
            return Response(
                {"detail": "سفارش دارای پرداخت است و قابل حذف نیست."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        order.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


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
        # NOTE: no day-close check here either — see add_item rationale.
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
