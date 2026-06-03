"""Categories and Products CRUD API with availability toggle and soft delete."""
from rest_framework import status, viewsets
from rest_framework.response import Response

from ..models import Category, Product
from ..serializers import CategorySerializer, ProductSerializer


class _SoftDeleteViewSet(viewsets.ModelViewSet):
    """Shared soft-delete behaviour for catalog models."""

    def destroy(self, request, *args, **kwargs):
        obj = self.get_object()
        obj.is_active = False
        obj.save(update_fields=["is_active", "updated_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class CategoryViewSet(_SoftDeleteViewSet):
    serializer_class = CategorySerializer
    queryset = Category.objects.filter(is_active=True)

    def perform_create(self, serializer):
        if serializer.validated_data.get("sort_order") in (None, 0):
            last = (
                Category.objects.filter(is_active=True)
                .order_by("-sort_order")
                .values_list("sort_order", flat=True)
                .first()
            )
            serializer.save(sort_order=(last or 0) + 1)
        else:
            serializer.save()


class ProductViewSet(_SoftDeleteViewSet):
    serializer_class = ProductSerializer
    queryset = Product.objects.filter(is_active=True)

    def get_queryset(self):
        qs = Product.objects.filter(is_active=True)
        category = self.request.query_params.get("category")
        if category:
            qs = qs.filter(category_id=category)
        is_available = self.request.query_params.get("is_available")
        if is_available is not None:
            qs = qs.filter(is_available=is_available.lower() in ("1", "true", "yes"))
        return qs

    def perform_create(self, serializer):
        if serializer.validated_data.get("sort_order") in (None, 0):
            category = serializer.validated_data.get("category")
            last = (
                Product.objects.filter(is_active=True, category=category)
                .order_by("-sort_order")
                .values_list("sort_order", flat=True)
                .first()
            )
            serializer.save(sort_order=(last or 0) + 1)
        else:
            serializer.save()
