from django.conf import settings
from django.shortcuts import render
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .authentication import ApiKeyAuthentication
from .models import CafeMenuSnapshot
from .serializers import CafeMenuSnapshotSerializer, DayClosingSyncRecordSerializer


def latest_snapshot(cafe_slug):
    return CafeMenuSnapshot.objects.filter(cafe_slug=cafe_slug).order_by("-received_at").first()


def public_menu_page(request, cafe_slug=None):
    cafe_slug = cafe_slug or settings.DEFAULT_CAFE_SLUG
    snapshot = latest_snapshot(cafe_slug)
    payload = snapshot.payload if snapshot else None
    categories = sorted(
        (payload or {}).get("categories", []),
        key=lambda category: category.get("sort_order", 0),
    )

    for category in categories:
        category["products"] = sorted(
            category.get("products", []),
            key=lambda product: product.get("sort_order", 0),
        )

    cafe_name = (payload or {}).get("cafe_name") or (payload or {}).get("name") or "خروج"
    return render(
        request,
        "qrmenu/menu.html",
        {
            "cafe_slug": cafe_slug,
            "cafe_name": cafe_name,
            "categories": categories,
            "has_snapshot": snapshot is not None,
            "version": snapshot.version if snapshot else None,
            "published_at": snapshot.published_at if snapshot else None,
        },
    )


class PublicMenuJsonView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request, cafe_slug):
        snapshot = latest_snapshot(cafe_slug)
        if snapshot is None:
            return Response({"detail": "Menu snapshot not found."}, status=status.HTTP_404_NOT_FOUND)

        return Response(snapshot.payload)


class MenuSnapshotCreateView(APIView):
    authentication_classes = [ApiKeyAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = CafeMenuSnapshotSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"detail": "Menu snapshot received."}, status=status.HTTP_201_CREATED)


class DayClosingSyncCreateView(APIView):
    authentication_classes = [ApiKeyAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = DayClosingSyncRecordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"detail": "Day closing sync received."}, status=status.HTTP_201_CREATED)
