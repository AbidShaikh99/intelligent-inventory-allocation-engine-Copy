from django.utils import timezone
from rest_framework import serializers

from orders.models import Order, OrderItem
from products.models import Product


class OrderItemCreateSerializer(serializers.Serializer):

    product_id = serializers.IntegerField(min_value=1)
    quantity = serializers.IntegerField(min_value=1)

    def validate_product_id(self, value):
        if not Product.objects.filter(
            pk=value,
            is_active=True,
        ).exists():
            raise serializers.ValidationError(
                "Product does not exist or is inactive."
            )

        return value


class OrderCreateSerializer(serializers.ModelSerializer):

    items = OrderItemCreateSerializer(
        many=True,
        allow_empty=False,
    )

    class Meta:
        model = Order
        fields = [
            "id",
            "customer_name",
            "customer_email",
            "delivery_city",
            "delivery_address",
            "priority",
            "promised_delivery_at",
            "items",
        ]
        read_only_fields = ["id"]

    def validate_items(self, value):
        product_ids = [
            item["product_id"]
            for item in value
        ]

        if len(product_ids) != len(set(product_ids)):
            raise serializers.ValidationError(
                "Each product can appear only once per order."
            )

        return value

    def validate_promised_delivery_at(self, value):
        if value <= timezone.now():
            raise serializers.ValidationError(
                "Promised delivery must be in the future."
            )

        return value

class OrderItemSerializer(serializers.ModelSerializer):

    product_sku = serializers.CharField(
        source="product.sku",
        read_only=True,
    )

    product_name = serializers.CharField(
        source="product.name",
        read_only=True,
    )

    class Meta:
        model = OrderItem
        fields = [
            "id",
            "product",
            "product_sku",
            "product_name",
            "quantity",
        ]


class OrderSerializer(serializers.ModelSerializer):

    items = OrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = [
            "id",
            "customer_name",
            "customer_email",
            "delivery_city",
            "delivery_address",
            "priority",
            "promised_delivery_at",
            "status",
            "items",
            "created_at",
            "updated_at",
        ]


class CancelOrderRequestSerializer(serializers.Serializer):
    confirm = serializers.BooleanField(required=True)

    def validate_confirm(self, value):
        if value is not True:
            raise serializers.ValidationError(
                "Order cancellation must be explicitly confirmed."
            )
        return value
