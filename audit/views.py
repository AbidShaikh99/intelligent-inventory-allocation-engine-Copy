
from rest_framework import status
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAdminUser,AllowAny

from audit.models import InventoryMovement
from audit.serializers import InventoryMovementSerializer
from utils.response import success_response


class InventoryMovementListAPIView(ListAPIView):
    serializer_class = InventoryMovementSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        queryset = (
            InventoryMovement.objects
            .select_related(
                "inventory",
                "inventory__warehouse",
                "inventory__product",
            )
            .order_by("-created_at", "-id")
        )

        inventory_id = self.request.query_params.get("inventory_id")
        warehouse_id = self.request.query_params.get("warehouse_id")
        product_id = self.request.query_params.get("product_id")
        movement_type = self.request.query_params.get("movement_type")

        if inventory_id:
            queryset = queryset.filter(inventory_id=inventory_id)

        if warehouse_id:
            queryset = queryset.filter(
                inventory__warehouse_id=warehouse_id
            )

        if product_id:
            queryset = queryset.filter(
                inventory__product_id=product_id
            )

        if movement_type:
            queryset = queryset.filter(movement_type=movement_type)

        return queryset

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)

        return success_response(
            "Inventory movements retrieved successfully.",
            serializer.data,
            status.HTTP_200_OK,
        )
