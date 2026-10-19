from django.db import transaction
from django.core.exceptions import ValidationError

from orders.models import Order, OrderItem
from products.models import Product
from allocation.models import AllocationPlan
from products.models import Inventory
from audit.models import InventoryMovement
from shipments.models import Shipment

@transaction.atomic
def create_order(*, validated_data):
    items_data = validated_data.pop("items")

    product_ids = [
        item["product_id"]
        for item in items_data
    ]

    # Lock product rows and recheck their status.
    products = {
        product.pk: product
        for product in Product.objects.select_for_update().filter(
            pk__in=product_ids
        ).order_by("pk")
    }

    if len(products) != len(set(product_ids)):
        raise ValidationError(
            "One or more products do not exist."
        )

    for product in products.values():
        if not product.is_active:
            raise ValidationError(
                f"Product {product.sku} is inactive."
            )

    order = Order.objects.create(**validated_data)

    order_items = [
        OrderItem(
            order=order,
            product=products[item["product_id"]],
            quantity=item["quantity"],
        )
        for item in items_data
    ]

    OrderItem.objects.bulk_create(order_items)

    return order


@transaction.atomic
def cancel_order(*, order_id):
    order = Order.objects.select_for_update().get(pk=order_id)

    if order.status == Order.Status.CANCELLED:
        raise ValueError("This order has already been cancelled.")

    if order.status == Order.Status.COMPLETED:
        raise ValueError("A completed order cannot be cancelled.")

    plan = (
        AllocationPlan.objects
        .select_for_update()
        .filter(order=order)
        .order_by("-created_at", "-id")
        .first()
    )

    shipments = Shipment.objects.none()

    if plan is not None:
        shipments = Shipment.objects.select_for_update().filter(
            allocation_plan=plan
        )

        if shipments.filter(
            status__in=[
                Shipment.Status.DISPATCHED,
                Shipment.Status.DELIVERED,
            ]
        ).exists():
            raise ValueError(
                "Cancellation is blocked because a shipment "
                "has already been dispatched or delivered."
            )

        if (
            plan.reservation_status
            == AllocationPlan.ReservationStatus.RESERVED
        ):
            lines = list(
                plan.lines.select_related(
                    "warehouse", "order_item__product"
                ).order_by("warehouse_id", "order_item__product_id")
            )

            for line in lines:
                product_id = line.order_item.product_id

                inventory = Inventory.objects.select_for_update().get(
                    warehouse_id=line.warehouse_id,
                    product_id=product_id,
                )

                quantity = line.quantity

                if inventory.reserved_quantity < quantity:
                    raise ValueError(
                        "Reserved inventory is insufficient to release "
                        f"product {product_id} at warehouse "
                        f"{line.warehouse_id}."
                    )

                inventory.reserved_quantity -= quantity
                inventory.available_quantity += quantity

                inventory.save(
                    update_fields=[
                        "reserved_quantity",
                        "available_quantity",
                        "updated_at",
                    ]
                )

                InventoryMovement.objects.create(
                    inventory=inventory,
                    movement_type=InventoryMovement.MovementType.RELEASE,
                    available_change=quantity,
                    reserved_change=-quantity,
                    damaged_change=0,
                    reference=f"ORDER-CANCEL-{order.id}",
                    reason=(
                        f"Released reserved stock after cancelling "
                        f"order {order.id}."
                    ),
                )


        if (
            plan.reservation_status
            == AllocationPlan.ReservationStatus.PENDING
        ):
            plan.reservation_status = (
                AllocationPlan.ReservationStatus.RELEASED
            )
            plan.save(update_fields=["reservation_status"])

        shipments.filter(
            status__in=[
                Shipment.Status.CREATED,
                Shipment.Status.READY,
            ]
        ).update(status=Shipment.Status.CANCELLED)

        if (
            plan.reservation_status
            == AllocationPlan.ReservationStatus.RESERVED
        ):
            plan.reservation_status = (
                AllocationPlan.ReservationStatus.RELEASED
            )
            plan.save(update_fields=["reservation_status"])

    order.status = Order.Status.CANCELLED
    order.save(update_fields=["status", "updated_at"])

    return order