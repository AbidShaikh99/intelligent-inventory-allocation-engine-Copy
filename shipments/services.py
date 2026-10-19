from django.db import transaction
from django.db.models import Max

from allocation.models import AllocationPlan
from shipments.models import Shipment
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.utils import timezone

from audit.models import InventoryMovement
from orders.models import Order
from products.models import Inventory

@transaction.atomic
def create_shipments_for_plan(*, plan_id):
    plan = AllocationPlan.objects.select_for_update().get(
        pk=plan_id
    )

    if plan.status != AllocationPlan.Status.FULL:
        raise ValueError(
            "Shipments can only be created for fully allocated plans."
        )

    if (
        plan.reservation_status
        != AllocationPlan.ReservationStatus.RESERVED
    ):
        raise ValueError(
            "Reserve the allocation plan's stock before creating shipments."
        )

    lines = plan.lines.all()

    if not lines.exists():
        raise ValueError(
            "Cannot create shipments because the allocation plan has no lines."
        )

    warehouse_etas = list(
        lines.values("warehouse_id").annotate(
            estimated_delivery_at=Max("estimated_delivery_at")
        ).order_by("warehouse_id")
    )

    created_count = 0

    for item in warehouse_etas:
        shipment, created = Shipment.objects.get_or_create(
            allocation_plan=plan,
            warehouse_id=item["warehouse_id"],
            defaults={
                "estimated_delivery_at": item["estimated_delivery_at"],
            },
        )

        if created:
            created_count += 1

    shipments = list(
        Shipment.objects.filter(
            allocation_plan=plan
        ).select_related(
            "warehouse"
        ).order_by("id")
    )

    return shipments, created_count



@transaction.atomic
def update_shipment_status(*, shipment_id, new_status):
    # Read relationship IDs first; acquire locks in a consistent order.
    initial = Shipment.objects.only(
        "allocation_plan_id"
    ).get(pk=shipment_id)

    plan_ref = AllocationPlan.objects.only(
        "order_id"
    ).get(pk=initial.allocation_plan_id)

    order = Order.objects.select_for_update().get(
        pk=plan_ref.order_id
    )

    plan = AllocationPlan.objects.select_for_update().get(
        pk=initial.allocation_plan_id
    )

    shipment = Shipment.objects.select_for_update().get(
        pk=shipment_id,
        allocation_plan=plan,
    )

    # Idempotency: repeating the current status must not repeat side effects.
    if shipment.status == new_status:
        return shipment

    allowed_transitions = {
        Shipment.Status.CREATED: [Shipment.Status.READY],
        Shipment.Status.READY: [Shipment.Status.DISPATCHED],
        Shipment.Status.DISPATCHED: [Shipment.Status.DELIVERED],
        Shipment.Status.DELIVERED: [],
        Shipment.Status.CANCELLED: [],
    }

    if new_status not in allowed_transitions.get(shipment.status, []):
        raise ValueError(
            f"Cannot change shipment status from "
            f"{shipment.status} to {new_status}."
        )

    if order.status == Order.Status.CANCELLED:
        raise ValueError("Cannot update a shipment for a cancelled order.")

    # Deduct reserved inventory only on the first READY -> DISPATCHED change.
    if new_status == Shipment.Status.DISPATCHED:
        if (
            plan.reservation_status
            != AllocationPlan.ReservationStatus.RESERVED
        ):
            raise ValueError(
                "The allocation plan does not have reserved inventory."
            )

        lines = list(
            plan.lines.filter(
                warehouse_id=shipment.warehouse_id
            ).select_related(
                "order_item__product"
            ).order_by(
                "order_item__product_id"
            )
        )

        if not lines:
            raise ValueError(
                "No allocation lines exist for this shipment's warehouse."
            )

        for line in lines:
            inventory = Inventory.objects.select_for_update().get(
                warehouse_id=shipment.warehouse_id,
                product_id=line.order_item.product_id,
            )

            quantity = line.quantity

            if inventory.reserved_quantity < quantity:
                raise ValueError(
                    f"Insufficient reserved stock for product "
                    f"{line.order_item.product_id}."
                )

            inventory.reserved_quantity -= quantity
            inventory.save(
                update_fields=["reserved_quantity", "updated_at"]
            )

            InventoryMovement.objects.create(
                inventory=inventory,
                movement_type=InventoryMovement.MovementType.SHIPMENT,
                available_change=0,
                reserved_change=-quantity,
                damaged_change=0,
                reference=f"SHIPMENT-{shipment.id}",
                reason=(
                    f"Stock dispatched for shipment {shipment.id}, "
                    f"order {order.id}."
                ),
            )

        shipment.dispatched_at = timezone.now()

    if new_status == Shipment.Status.DELIVERED:
        shipment.delivered_at = timezone.now()

    shipment.status = new_status
    shipment.save(
        update_fields=[
            "status",
            "dispatched_at",
            "delivered_at",
            "updated_at",
        ]
    )

    # Recalculate fulfillment status for this allocation plan only.
    statuses = list(
        Shipment.objects.filter(
            allocation_plan=plan
        ).values_list("status", flat=True)
    )

    shipped_statuses = {
        Shipment.Status.DISPATCHED,
        Shipment.Status.DELIVERED,
    }

    if statuses and all(
        status == Shipment.Status.DELIVERED for status in statuses
    ):
        order.status = Order.Status.COMPLETED
        order.save(update_fields=["status", "updated_at"])

    elif statuses and all(
        status in shipped_statuses for status in statuses
    ):
        order.status = Order.Status.SHIPPED
        order.save(update_fields=["status", "updated_at"])

    elif any(status in shipped_statuses for status in statuses):
        order.status = Order.Status.PARTIALLY_SHIPPED
        order.save(update_fields=["status", "updated_at"])

    return shipment