from decimal import Decimal

from django.db import transaction

from allocation.engine import optimize_order
from allocation.models import AllocationPlan, AllocationLine
from orders.models import Order


@transaction.atomic
def create_allocation_plan(*, order_id, max_shipments=2):
    order = Order.objects.select_for_update().get(pk=order_id)

    if order.status not in [
        Order.Status.PENDING_ALLOCATION,
        Order.Status.BACKORDERED,
    ]:
        raise ValueError(
            f"Cannot allocate an order with status {order.status}."
        )

    result = optimize_order(
        order=order,
        max_shipments=max_shipments,
    )

    plan = AllocationPlan.objects.create(
        order=order,
        status=result["status"],
        total_shipping_cost=(
            Decimal(result["total_shipping_cost_cents"]) / Decimal("100")
        ),
        requested_units=result["requested_units"],
        allocated_units=result["allocated_units"],
        shipment_count=result["shipment_count"],
        decision_details={
            "reason": result["reason"],
            "warehouse_decisions": result["decisions"],
            "max_shipments": max_shipments,
        },
    )

    lines = []

    for line in result["lines"]:
        lines.append(
            AllocationLine(
                plan=plan,
                order_item_id=line["order_item_id"],
                warehouse_id=line["warehouse_id"],
                quantity=line["quantity"],
                shipping_cost=(
                    Decimal(line["shipping_cost_cents"]) / Decimal("100")
                ),
                estimated_delivery_at=line["estimated_delivery_at"],
            )
        )

    AllocationLine.objects.bulk_create(lines)

    if plan.status == AllocationPlan.Status.FULL:
        order.status = Order.Status.ALLOCATION_PLANNED
    else:
        order.status = Order.Status.BACKORDERED

    order.save(update_fields=["status", "updated_at"])

    return plan

def _rebalance_plan_matches(existing_plan, result):
    """Return True when recalculation produces the same allocation."""

    if existing_plan is None:
        return False

    new_total_cost = Decimal(
        result["total_shipping_cost_cents"]
    ) / Decimal("100")

    if (
        existing_plan.status != result["status"]
        or existing_plan.requested_units != result["requested_units"]
        or existing_plan.allocated_units != result["allocated_units"]
        or existing_plan.shipment_count != result["shipment_count"]
        or existing_plan.total_shipping_cost != new_total_cost
    ):
        return False

    existing_lines = sorted(
        (
            line.order_item_id,
            line.warehouse_id,
            line.quantity,
            int(Decimal(line.shipping_cost) * 100),
            line.estimated_delivery_at,
        )
        for line in existing_plan.lines.all()
    )

    proposed_lines = sorted(
        (
            line["order_item_id"],
            line["warehouse_id"],
            line["quantity"],
            line["shipping_cost_cents"],
            line["estimated_delivery_at"],
        )
        for line in result["lines"]
    )

    return existing_lines == proposed_lines


def _save_rebalanced_plan(order, result, max_shipments):
    """Save a new allocation plan and its allocation lines."""

    total_shipping_cost = (
        Decimal(result["total_shipping_cost_cents"]) / Decimal("100")
    )

    plan = AllocationPlan.objects.create(
        order=order,
        status=result["status"],
        total_shipping_cost=total_shipping_cost,
        requested_units=result["requested_units"],
        allocated_units=result["allocated_units"],
        shipment_count=result["shipment_count"],
        decision_details={
            "reason": result["reason"],
            "warehouse_decisions": result["decisions"],
            "max_shipments": max_shipments,
            "trigger": "REBALANCE",
        },
    )

    AllocationLine.objects.bulk_create([
        AllocationLine(
            plan=plan,
            order_item_id=line["order_item_id"],
            warehouse_id=line["warehouse_id"],
            quantity=line["quantity"],
            shipping_cost=(
                Decimal(line["shipping_cost_cents"]) / Decimal("100")
            ),
            estimated_delivery_at=line["estimated_delivery_at"],
        )
        for line in result["lines"]
    ])

    if plan.status == AllocationPlan.Status.FULL:
        order.status = Order.Status.ALLOCATION_PLANNED
    else:
        order.status = Order.Status.BACKORDERED

    order.save(update_fields=["status", "updated_at"])

    return plan


def rebalance_eligible_orders(*, max_shipments=2):
    """
    Recalculate pending and backordered orders in a stable priority order.

    Existing reserved orders are not selected or modified.
    """

    from django.db.models import Case, When, Value, IntegerField

    priority_rank = Case(
        When(priority=Order.Priority.EMERGENCY, then=Value(0)),
        When(priority=Order.Priority.PREMIUM, then=Value(1)),
        When(priority=Order.Priority.EXPRESS, then=Value(2)),
        When(priority=Order.Priority.STANDARD, then=Value(3)),
        default=Value(4),
        output_field=IntegerField(),
    )

    order_ids = list(
        Order.objects.filter(
            status__in=[
                Order.Status.PENDING_ALLOCATION,
                Order.Status.BACKORDERED,
            ]
        )
        .annotate(priority_rank=priority_rank)
        .order_by("priority_rank", "created_at", "id")
        .values_list("id", flat=True)
    )

    summary = {
        "eligible_orders": len(order_ids),
        "plans_created": 0,
        "plans_unchanged": 0,
        "orders_skipped": 0,
        "failures": [],
        "results": [],
    }

    for order_id in order_ids:
        try:
            with transaction.atomic():
                order = Order.objects.select_for_update().get(pk=order_id)

                # The order may have changed after the initial query.
                if order.status not in [
                    Order.Status.PENDING_ALLOCATION,
                    Order.Status.BACKORDERED,
                ]:
                    summary["orders_skipped"] += 1
                    continue

                result = optimize_order(
                    order=order,
                    max_shipments=max_shipments,
                )

                latest_plan = (
                    AllocationPlan.objects
                    .filter(order=order)
                    .order_by("-created_at", "-id")
                    .first()
                )

                if _rebalance_plan_matches(latest_plan, result):
                    # Keep the existing plan instead of creating a duplicate.
                    expected_status = (
                        Order.Status.ALLOCATION_PLANNED
                        if latest_plan.status == AllocationPlan.Status.FULL
                        else Order.Status.BACKORDERED
                    )

                    if order.status != expected_status:
                        order.status = expected_status
                        order.save(update_fields=["status", "updated_at"])

                    summary["plans_unchanged"] += 1
                    summary["results"].append({
                        "order_id": order.id,
                        "result": "UNCHANGED",
                        "allocation_plan_id": latest_plan.id,
                    })
                    continue

                plan = _save_rebalanced_plan(
                    order=order,
                    result=result,
                    max_shipments=max_shipments,
                )

                summary["plans_created"] += 1
                summary["results"].append({
                    "order_id": order.id,
                    "result": "REPLANNED",
                    "allocation_plan_id": plan.id,
                    "plan_status": plan.status,
                })

        except (Order.DoesNotExist, ValueError, RuntimeError) as exc:
            summary["failures"].append({
                "order_id": order_id,
                "detail": str(exc),
            })

    return summary

