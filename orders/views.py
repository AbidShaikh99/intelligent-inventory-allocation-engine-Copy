from django.core.exceptions import ValidationError,ObjectDoesNotExist
from rest_framework import status
from rest_framework.permissions import IsAdminUser,AllowAny
from rest_framework.views import APIView
from orders.models import Order,OrderItem
from allocation.models import AllocationPlan
from allocation.serializers import AllocationPlanSerializer
from utils.response import success_response, error_response
from orders.serializers import (
    OrderCreateSerializer,
    OrderSerializer,
    CancelOrderRequestSerializer
)
from orders.services import create_order,cancel_order
from utils.response import success_response, error_response


class OrderCreateAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = OrderCreateSerializer(data=request.data)

        if not serializer.is_valid():
            return error_response(
                "Order validation failed.",
                serializer.errors,
                status.HTTP_400_BAD_REQUEST,
            )

        try:
            order = create_order(
                validated_data=serializer.validated_data.copy()
            )

        except ValidationError as exc:
            return error_response(
                "Unable to create order.",
                exc.messages,
                status.HTTP_400_BAD_REQUEST,
            )

        return success_response(
            "Order created successfully.",
            OrderSerializer(order).data,
            status.HTTP_201_CREATED,
        )

class CancelOrderAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, order_id):
        request_serializer = CancelOrderRequestSerializer(
            data=request.data
        )

        if not request_serializer.is_valid():
            return error_response(
                "Validation failed.",
                request_serializer.errors,
                status.HTTP_400_BAD_REQUEST,
            )

        try:
            order = cancel_order(order_id=order_id)

        except ObjectDoesNotExist:
            return error_response(
                "Order not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        except ValueError as exc:
            return error_response(
                str(exc),
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        return success_response(
            "Order cancelled successfully.",
            OrderSerializer(order).data,
            status.HTTP_200_OK,
        )

class OrderAllocationAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, order_id):
        # Step 1: Find the order.
        order = Order.objects.filter(id=order_id).first()

        if order is None:
            return error_response(
                "Order not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        # Step 2: Get all allocation plans for this order.
        plans = (
            AllocationPlan.objects
            .filter(order_id=order.id)
            .select_related("order")
            .prefetch_related(
                "lines__warehouse",
                "lines__order_item__product",
            )
            .order_by("-created_at", "-id")
        )

        # Step 3: Serialize the allocation plans.
        allocation_data = AllocationPlanSerializer(
            plans,
            many=True,
        ).data

        # Step 4: Return the order and its allocation information.
        return success_response(
            "Order allocation details retrieved successfully.",
            {
                "order_id": order.id,
                "order_status": order.status,
                "delivery_city": order.delivery_city,
                "priority": order.priority,
                "allocation_plans": allocation_data,
            },
            status.HTTP_200_OK,
        )
class BackorderListAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        orders = (
            Order.objects
            .filter(status=Order.Status.BACKORDERED)
            .order_by("created_at", "id")
        )

        results = []

        for order in orders:
            order_items = (
                OrderItem.objects
                .filter(order=order)
                .select_related("product")
            )

            results.append({
                "order_id": order.id,
                "customer_name": order.customer_name,
                "delivery_city": order.delivery_city,
                "priority": order.priority,
                "promised_delivery_at": order.promised_delivery_at,
                "status": order.status,
                "created_at": order.created_at,
                "items": [
                    {
                        "product_id": item.product_id,
                        "product_name": item.product.name,
                        "sku": item.product.sku,
                        "ordered_quantity": item.quantity,
                    }
                    for item in order_items
                ],
            })

        return success_response(
            "Backorders retrieved successfully.",
            {
                "count": len(results),
                "backorders": results,
            },
            status.HTTP_200_OK,
        )
