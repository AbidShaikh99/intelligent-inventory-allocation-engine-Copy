
from django.utils import timezone
from rest_framework import serializers

from products.models import Product
from warehouses.models import Warehouse
from .models import (
    Supplier,
    SupplierPurchaseOrder,
    SupplierPurchaseOrderItem,
)


class SupplierPurchaseOrderItemSerializer(serializers.ModelSerializer):
    product_id = serializers.PrimaryKeyRelatedField(
        source="product",
        queryset=Product.objects.filter(is_active=True),
    )

    class Meta:
        model = SupplierPurchaseOrderItem
        fields = (
            "id",
            "product_id",
            "ordered_quantity",
            "received_quantity",
        )
        read_only_fields = ("id", "received_quantity")

    def validate_ordered_quantity(self, value):
        if value <= 0:
            raise serializers.ValidationError(
                "Ordered quantity must be greater than zero."
            )
        return value


class SupplierPurchaseOrderSerializer(serializers.ModelSerializer):
    supplier_id = serializers.PrimaryKeyRelatedField(
        source="supplier",
        queryset=Supplier.objects.filter(is_active=True),
    )

    warehouse_id = serializers.PrimaryKeyRelatedField(
        source="warehouse",
        queryset=Warehouse.objects.filter(
            status=Warehouse.Status.ACTIVE
        ),
    )

    items = SupplierPurchaseOrderItemSerializer(many=True)

    class Meta:
        model = SupplierPurchaseOrder
        fields = (
            "id",
            "supplier_id",
            "warehouse_id",
            "expected_delivery_at",
            "status",
            "items",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "status",
            "created_at",
            "updated_at",
        )

    def validate_expected_delivery_at(self, value):
        if value <= timezone.now():
            raise serializers.ValidationError(
                "Expected delivery date must be in the future."
            )
        return value

    def validate_items(self, items):
        if not items:
            raise serializers.ValidationError(
                "At least one product is required."
            )

        product_ids = [item["product"].id for item in items]

        if len(product_ids) != len(set(product_ids)):
            raise serializers.ValidationError(
                "A product can appear only once in a purchase order."
            )

        return items

    def create(self, validated_data):
        items_data = validated_data.pop("items")

        from django.db import transaction

        with transaction.atomic():
            purchase_order = SupplierPurchaseOrder.objects.create(
                **validated_data
            )

            SupplierPurchaseOrderItem.objects.bulk_create([
                SupplierPurchaseOrderItem(
                    purchase_order=purchase_order,
                    **item_data,
                )
                for item_data in items_data
            ])

        return purchase_order

class SupplierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supplier
        fields = [
            "id",
            "name",
            "email",
            "phone",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_name(self, value):
        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                "Supplier name is required."
            )

        return value

class PurchaseOrderReceiveSerializer(serializers.Serializer):
    items = serializers.ListField(
        child=serializers.DictField(),
        allow_empty=False,
    )

    def validate_items(self, items):
        seen = set()

        for item in items:
            if set(item.keys()) != {"product_id", "quantity"}:
                raise serializers.ValidationError(
                    "Each item must contain only product_id and quantity."
                )

            product_id = item["product_id"]
            quantity = item["quantity"]

            if not isinstance(product_id, int) or isinstance(product_id, bool):
                raise serializers.ValidationError(
                    "product_id must be an integer."
                )

            if not isinstance(quantity, int) or isinstance(quantity, bool) or quantity <= 0:
                raise serializers.ValidationError(
                    "quantity must be a positive integer."
                )

            if product_id in seen:
                raise serializers.ValidationError(
                    "A product can appear only once per receipt."
                )

            seen.add(product_id)

        return items