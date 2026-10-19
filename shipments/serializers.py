
from rest_framework import serializers

from shipments.models import Shipment


class CreateShipmentRequestSerializer(serializers.Serializer):
    confirm = serializers.BooleanField(required=True)

    def validate_confirm(self, value):
        if value is not True:
            raise serializers.ValidationError(
                "Shipment creation must be explicitly confirmed."
            )
        return value


class ShipmentSerializer(serializers.ModelSerializer):
    warehouse_name = serializers.CharField(
        source="warehouse.name",
        read_only=True,
    )

    class Meta:
        model = Shipment
        fields = [
            "id",
            "allocation_plan",
            "warehouse",
            "warehouse_name",
            "status",
            "tracking_number",
            "estimated_delivery_at",
            "dispatched_at",
            "delivered_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

class ShipmentStatusUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=[
            Shipment.Status.READY,
            Shipment.Status.DISPATCHED,
            Shipment.Status.DELIVERED,
        ]
    )