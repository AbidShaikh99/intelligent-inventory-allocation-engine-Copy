from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView
from .models import Supplier
from rest_framework.permissions import IsAdminUser
from utils.response import success_response, error_response
from .serializers import SupplierPurchaseOrderSerializer,SupplierSerializer,PurchaseOrderReceiveSerializer
from .models import SupplierPurchaseOrder, SupplierPurchaseOrderItem
from products.models import Inventory
from audit.models import InventoryMovement

class SupplierPurchaseOrderCreateAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = SupplierPurchaseOrderSerializer(
            data=request.data
        )

        if not serializer.is_valid():
            return error_response(
                "Purchase order validation failed.",
                serializer.errors,
                status.HTTP_400_BAD_REQUEST,
            )

        purchase_order = serializer.save()

        return success_response(
            "Supplier purchase order created successfully.",
            SupplierPurchaseOrderSerializer(purchase_order).data,
            status.HTTP_201_CREATED,
        )

class SupplierCreateAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = SupplierSerializer(data=request.data)

        if not serializer.is_valid():
            return error_response(
                "Supplier validation failed.",
                serializer.errors,
                status.HTTP_400_BAD_REQUEST,
            )

        supplier = serializer.save()

        return success_response(
            "Supplier created successfully.",
            SupplierSerializer(supplier).data,
            status.HTTP_201_CREATED,
        )
class ReceiveSupplierPurchaseOrderAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, pk):
        serializer = PurchaseOrderReceiveSerializer(data=request.data)

        if not serializer.is_valid():
            return error_response(
                "Receipt validation failed.",
                serializer.errors,
                status.HTTP_400_BAD_REQUEST,
            )

        received_items = serializer.validated_data["items"]

        with transaction.atomic():
            purchase_order = (
                SupplierPurchaseOrder.objects
                .select_for_update()
                .filter(pk=pk)
                .first()
            )

            if purchase_order is None:
                return error_response(
                    "Purchase order not found.",
                    None,
                    status.HTTP_404_NOT_FOUND,
                )

            if purchase_order.status in (
                SupplierPurchaseOrder.Status.RECEIVED,
                SupplierPurchaseOrder.Status.CANCELLED,
            ):
                return error_response(
                    "This purchase order cannot receive more stock.",
                    {"status": purchase_order.status},
                    status.HTTP_400_BAD_REQUEST,
                )

            item_ids = [item["product_id"] for item in received_items]

            po_items = {
                item.product_id: item
                for item in SupplierPurchaseOrderItem.objects
                .select_for_update()
                .filter(
                    purchase_order=purchase_order,
                    product_id__in=item_ids,
                )
                .order_by("product_id")
            }

            if len(po_items) != len(item_ids):
                return error_response(
                    "One or more products do not belong to this purchase order.",
                    None,
                    status.HTTP_400_BAD_REQUEST,
                )

            inventory_rows = {}

            for product_id in sorted(item_ids):
                inventory = (
                    Inventory.objects
                    .select_for_update()
                    .filter(
                        warehouse=purchase_order.warehouse,
                        product_id=product_id,
                    )
                    .first()
                )

                if inventory is None:
                    return error_response(
                        "Inventory record not found for a purchase-order product.",
                        {"product_id": product_id},
                        status.HTTP_400_BAD_REQUEST,
                    )

                inventory_rows[product_id] = inventory

            for item in received_items:
                po_item = po_items[item["product_id"]]

                if (
                    po_item.received_quantity + item["quantity"]
                    > po_item.ordered_quantity
                ):
                    return error_response(
                        "Received quantity cannot exceed ordered quantity.",
                        {
                            "product_id": item["product_id"],
                            "ordered_quantity": po_item.ordered_quantity,
                            "already_received": po_item.received_quantity,
                            "requested_receipt": item["quantity"],
                        },
                        status.HTTP_400_BAD_REQUEST,
                    )

            for item in received_items:
                product_id = item["product_id"]
                quantity = item["quantity"]
                po_item = po_items[product_id]
                inventory = inventory_rows[product_id]

                inventory.available_quantity += quantity
                inventory.save(
                    update_fields=["available_quantity"]
                )

                po_item.received_quantity += quantity
                po_item.save(update_fields=["received_quantity"])

                InventoryMovement.objects.create(
                    inventory=inventory,
                    movement_type="SUPPLIER_RECEIPT",
                    available_change=quantity,
                    reserved_change=0,
                    damaged_change=0,
                    reference=f"PO-{purchase_order.pk}",
                    reason=(
                        f"Received {quantity} units against "
                        f"supplier purchase order {purchase_order.pk}"
                    ),
                )

            all_items = list(
                SupplierPurchaseOrderItem.objects
                .filter(purchase_order=purchase_order)
            )

            if all(
                item.received_quantity == item.ordered_quantity
                for item in all_items
            ):
                purchase_order.status = (
                    SupplierPurchaseOrder.Status.RECEIVED
                )
            else:
                purchase_order.status = (
                    SupplierPurchaseOrder.Status.PARTIALLY_RECEIVED
                )

            purchase_order.save(
                update_fields=["status", "updated_at"]
            )

        return success_response(
            "Supplier stock received successfully.",
            {
                "purchase_order_id": purchase_order.id,
                "status": purchase_order.status,
                "received_items": [
                    {
                        "product_id": item["product_id"],
                        "received_quantity": item["quantity"],
                    }
                    for item in received_items
                ],
            },
            status.HTTP_200_OK,
        )