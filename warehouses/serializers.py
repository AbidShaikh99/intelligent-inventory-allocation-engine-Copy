from rest_framework import serializers

from .models import Warehouse,WarehouseShippingRate


class WarehouseSerializer(serializers.ModelSerializer):

    class Meta:
        model = Warehouse
        fields = [
            "id",
            "name",
            "city",
            "address",
            "processing_capacity",
            "storage_restrictions",
            "status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
        ]

    def validate_processing_capacity(self, value):
        if value <= 0:
            raise serializers.ValidationError(
                "Processing capacity must be greater than zero."
            )
        return value

    def validate_storage_restrictions(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError(
                "Storage restrictions must be a list."
            )

        if not all(isinstance(item, str) for item in value):
            raise serializers.ValidationError(
                "Each storage restriction must be a string."
            )

        return value


class WarehouseShippingRateSerializer(serializers.ModelSerializer):
    class Meta:
        model = WarehouseShippingRate
        fields = [
            "id",
            "warehouse",
            "destination_city",
            "fixed_cost",
            "cost_per_kg",
            "transit_hours",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_destination_city(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError(
                "Destination city cannot be empty."
            )
        return value

    def validate(self, attrs):
        if attrs.get("transit_hours", 1) < 1:
            raise serializers.ValidationError({
                "transit_hours": "Transit hours must be at least 1."
            })
        return attrs