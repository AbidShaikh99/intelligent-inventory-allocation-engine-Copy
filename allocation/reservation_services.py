from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.utils import timezone

from allocation.models import AllocationPlan
from audit.models import InventoryMovement
from orders.models import Order
from products.models import Inventory


@transaction.atomic
def reserve_allocation_plan(*, plan_id):
    # Lock the plan so two requests cannot reserve it simultaneously.
    plan = AllocationPlan.objects.select_for_update().get(
        pk=plan_id
    )

    # Lock the order as well.
    order = Order.objects.select_for_update().get(
        pk=plan.order_id
    )

    if plan.status != AllocationPlan.Status.FULL:
        raise ValueError(
            "Only fully allocated plans can be reserved."
        )

    if (
        plan.reservation_status
        != AllocationPlan.ReservationStatus.PENDING
    ):
        raise ValueError(
            "This allocation plan is not pending reservation."
        )

    # Do not reserve an old plan after a newer plan was created.
    latest_plan = (
        AllocationPlan.objects.filter(order_id=order.id)
        .order_by("-created_at", "-id")
        .first()
    )

    if latest_plan is None or latest_plan.id != plan.id:
        raise ValueError(
            "This is not the latest allocation plan for the order."
        )

    if order.status != Order.Status.ALLOCATION_PLANNED:
        raise ValueError(
            f"Order cannot be reserved from status {order.status}."
        )

    lines = list(
        plan.lines.select_related("order_item__product", "warehouse")
        .order_by(
            "warehouse_id",
            "order_item__product_id",
            "id",
        )
    )

    if not lines:
        raise ValueError(
            "The allocation plan has no allocation lines."
        )

    # Lock and validate every inventory row before changing any stock.
    locked_inventory = {}
    for line in lines:
        key = (
            line.warehouse_id,
            line.order_item.product_id,
        )

        if key not in locked_inventory:
            try:
                inventory = Inventory.objects.select_for_update().get(
                    warehouse_id=key[0],
                    product_id=key[1],
                )
            except Inventory.DoesNotExist:
                raise ValueError(
                    "Inventory record is missing for a selected allocation."
                )

            locked_inventory[key] = inventory

        inventory = locked_inventory[key]

        if inventory.available_quantity < line.quantity:
            raise ValueError(
                f"Insufficient stock for product "
                f"{line.order_item.product.sku} at "
                f"warehouse {line.warehouse.name}. "
                f"Available: {inventory.available_quantity}, "
                f"required: {line.quantity}."
            )

    # All lines passed validation. Apply the stock changes.
    for line in lines:
        key = (
            line.warehouse_id,
            line.order_item.product_id,
        )
        inventory = locked_inventory[key]

        inventory.available_quantity -= line.quantity
        inventory.reserved_quantity += line.quantity

        inventory.save(
            update_fields=[
                "available_quantity",
                "reserved_quantity",
                "updated_at",
            ]
        )

        InventoryMovement.objects.create(
            inventory=inventory,
            movement_type=InventoryMovement.MovementType.RESERVATION,
            available_change=-line.quantity,
            reserved_change=line.quantity,
            damaged_change=0,
            reference=f"ALLOCATION-PLAN-{plan.id}",
            reason=(
                f"Reserved for order {order.id}, "
                f"allocation plan {plan.id}."
            ),
        )

    plan.reservation_status = (
        AllocationPlan.ReservationStatus.RESERVED
    )
    plan.save(update_fields=["reservation_status"])

    order.status = Order.Status.RESERVED
    order.save(update_fields=["status", "updated_at"])

    return plan