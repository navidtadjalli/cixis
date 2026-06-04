from rest_framework import serializers

from .models import CafeMenuSnapshot, DayClosingSyncRecord


class CafeMenuSnapshotSerializer(serializers.Serializer):
    cafe_slug = serializers.CharField(max_length=120)
    version = serializers.CharField(max_length=120)
    published_at = serializers.DateTimeField()
    categories = serializers.ListField(required=False)

    def create(self, validated_data):
        return CafeMenuSnapshot.objects.create(
            cafe_slug=validated_data["cafe_slug"],
            payload=dict(self.initial_data),
            version=validated_data["version"],
            published_at=validated_data["published_at"],
        )


class DayClosingSyncRecordSerializer(serializers.Serializer):
    cafe_slug = serializers.CharField(max_length=120)
    business_date = serializers.DateField()

    def create(self, validated_data):
        return DayClosingSyncRecord.objects.create(
            cafe_slug=validated_data["cafe_slug"],
            payload=dict(self.initial_data),
            business_date=validated_data["business_date"],
        )
