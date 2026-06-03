"""Tables CRUD API with soft delete and active-order guard."""
from rest_framework import status, viewsets
from rest_framework.response import Response

from .. import services
from ..models import Table
from ..serializers import TableSerializer


class TableViewSet(viewsets.ModelViewSet):
    """CRUD for tables.

    - list/retrieve return active tables only, with derived status.
    - create accepts {name}; sort_order defaults to end of list.
    - destroy is a soft delete, blocked when an active order is open/partially paid.
    """

    serializer_class = TableSerializer
    queryset = Table.objects.filter(is_active=True)

    def perform_create(self, serializer):
        if serializer.validated_data.get("sort_order") in (None, 0):
            last = (
                Table.objects.filter(is_active=True)
                .order_by("-sort_order")
                .values_list("sort_order", flat=True)
                .first()
            )
            serializer.save(sort_order=(last or 0) + 1)
        else:
            serializer.save()

    def destroy(self, request, *args, **kwargs):
        table = self.get_object()
        active = services.active_order_for_table(table)
        if active and active.status in services.BLOCKING_STATUSES:
            return Response(
                {"detail": "میز دارای سفارش باز است و قابل حذف نیست."},
                status=status.HTTP_409_CONFLICT,
            )
        table.is_active = False
        table.save(update_fields=["is_active", "updated_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)
