"""Resource purchases: record and list daily cafe supply purchases."""
from rest_framework import generics

from .. import services
from ..models import ResourcePurchase
from ..serializers import ResourcePurchaseSerializer


class ResourcePurchaseListCreate(generics.ListCreateAPIView):
    serializer_class = ResourcePurchaseSerializer

    def get_queryset(self):
        qs = ResourcePurchase.objects.all()
        day = self.request.query_params.get("date")
        if day:
            qs = qs.filter(business_date=day)
        return qs

    def perform_create(self, serializer):
        serializer.save(business_date=services.business_today())
