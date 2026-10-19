from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.utils import timezone
from ortools.sat.python import cp_model

from products.models import Inventory
from warehouses.models import Warehouse, WarehouseShippingRate


def money_to_cents(value):
    """Convert a monetary amount to integer cents."""
    return int(
        (Decimal(value) * 100).quantize(
            Decimal("1"),
            rounding=ROUND_HALF_UP,
        )
    )


def optimize_order(order, max_shipments=2):
    """
    Return the lowest-cost allocation among plans that fulfill
    the maximum possible number of requested units.

    This function calculates a plan only. It does not reserve stock.
    """

    if max_shipments < 1:
        raise ValueError("max_shipments must be at least 1.")

    items = list(
        order.items.select_related("product").order_by("id")
    )

    if not items:
        raise ValueError("Cannot allocate an order without items.")

    now = timezone.now()
    destination = order.delivery_city.strip()

    warehouses = list(
        Warehouse.objects.filter(
            status=Warehouse.Status.ACTIVE,
        ).order_by("id")
    )

    rates = list(
        WarehouseShippingRate.objects.filter(
            destination_city__iexact=destination,
            is_active=True,
            warehouse__in=warehouses,
        ).select_related("warehouse").order_by("id")
    )

    # One active rate per warehouse and destination is expected.
    rate_by_warehouse = {}
    for rate in rates:
        rate_by_warehouse.setdefault(rate.warehouse_id, rate)

    inventory_rows = Inventory.objects.filter(
        product_id__in=[item.product_id for item in items],
        warehouse__in=warehouses,
    ).order_by("warehouse_id", "product_id")

    stock_by_pair = {
        (row.product_id, row.warehouse_id): row.available_quantity
        for row in inventory_rows
    }

    # Keep reasons for why warehouse options were excluded.
    decisions = []
    eligible = {}

    for item in items:
        eligible[item.id] = []

        for warehouse in warehouses:
            stock = stock_by_pair.get(
                (item.product_id, warehouse.id), 0
            )
            rate = rate_by_warehouse.get(warehouse.id)
            reasons = []

            if stock <= 0:
                reasons.append("No available stock for this product.")

            if warehouse.processing_capacity <= 0:
                reasons.append("Warehouse capacity is zero.")

            if rate is None:
                reasons.append(
                    "No active shipping rate for the destination city."
                )
            else:
                estimated_delivery = now + timedelta(
                    hours=rate.transit_hours
                )

                if estimated_delivery > order.promised_delivery_at:
                    reasons.append(
                        "Estimated delivery is after the promised deadline."
                    )

            is_eligible = not reasons

            decisions.append({
                "order_item_id": item.id,
                "product_sku": item.product.sku,
                "warehouse_id": warehouse.id,
                "warehouse_name": warehouse.name,
                "eligible": is_eligible,
                "reasons": reasons,
            })

            if is_eligible:
                eligible[item.id].append({
                    "warehouse": warehouse,
                    "rate": rate,
                    "stock": stock,
                    "delivery_at": estimated_delivery,
                })

    # If no item can be supplied from any warehouse, return no allocation.
    if not any(eligible.values()):
        return {
            "status": "INFEASIBLE",
            "requested_units": sum(item.quantity for item in items),
            "allocated_units": 0,
            "shipment_count": 0,
            "total_shipping_cost_cents": 0,
            "lines": [],
            "decisions": decisions,
            "reason": "No eligible warehouse options were found.",
        }

    model = cp_model.CpModel()

    quantity_vars = {}
    assignment_vars = {}
    shipment_vars = {}

    cost_terms = []

    for warehouse in warehouses:
        shipment_vars[warehouse.id] = model.NewBoolVar(
            f"shipment_{warehouse.id}"
        )

    for item in items:
        item_vars = []

        for option in eligible[item.id]:
            warehouse = option["warehouse"]
            rate = option["rate"]
            key = (item.id, warehouse.id)

            max_quantity = min(
                item.quantity,
                option["stock"],
                warehouse.processing_capacity,
            )

            quantity = model.NewIntVar(
                0,
                max_quantity,
                f"qty_item_{item.id}_warehouse_{warehouse.id}",
            )

            assigned = model.NewBoolVar(
                f"assigned_item_{item.id}_warehouse_{warehouse.id}"
            )

            quantity_vars[key] = quantity
            assignment_vars[key] = assigned

            # A warehouse assignment must supply at least one unit.
            model.Add(quantity <= max_quantity * assigned)
            model.Add(quantity >= assigned)

            # Any assignment means that this warehouse is shipping.
            model.Add(
                shipment_vars[warehouse.id] >= assigned
            )

            item_vars.append(quantity)

            # Fixed cost is charged once per warehouse shipment.
            fixed_cost_cents = money_to_cents(rate.fixed_cost)

            # Round the per-unit weight-based cost to cents.
            unit_cost = (
                Decimal(item.product.weight_kg)
                * Decimal(rate.cost_per_kg)
            )
            unit_cost_cents = money_to_cents(unit_cost)

            cost_terms.append(
                unit_cost_cents * quantity
            )

        # Never allocate more than the requested quantity.
        if item_vars:
            model.Add(sum(item_vars) <= item.quantity)

    # A warehouse can fulfill multiple products, but its total assigned
    # item units cannot exceed its processing capacity.
    for warehouse in warehouses:
        warehouse_quantities = [
            quantity_vars[(item.id, warehouse.id)]
            for item in items
            if (item.id, warehouse.id) in quantity_vars
        ]

        if warehouse_quantities:
            model.Add(
                sum(warehouse_quantities)
                <= warehouse.processing_capacity
            )

        warehouse_assignments = [
            assignment_vars[(item.id, warehouse.id)]
            for item in items
            if (item.id, warehouse.id) in assignment_vars
        ]

        if warehouse_assignments:
            model.Add(
                shipment_vars[warehouse.id]
                <= sum(warehouse_assignments)
            )
        else:
            model.Add(shipment_vars[warehouse.id] == 0)

        rate = rate_by_warehouse.get(warehouse.id)
        if rate is not None:
            cost_terms.append(
                money_to_cents(rate.fixed_cost)
                * shipment_vars[warehouse.id]
            )

    # Respect the maximum number of distinct warehouse shipments.
    model.Add(
        sum(shipment_vars.values()) <= max_shipments
    )

    total_allocated = sum(quantity_vars.values())

    # First optimization goal: maximize fulfilled units.
    model.Maximize(total_allocated)

    solver = cp_model.CpSolver()
    status = solver.Solve(model)

    if status != cp_model.OPTIMAL:
        raise RuntimeError(
            "The optimizer could not prove the maximum fulfillment."
        )

    maximum_units = sum(
        solver.Value(variable)
        for variable in quantity_vars.values()
    )

    # Second goal: among plans with maximum fulfillment, minimize cost.
    model.Add(total_allocated == maximum_units)
    model.Minimize(sum(cost_terms))

    solver = cp_model.CpSolver()
    status = solver.Solve(model)

    if status != cp_model.OPTIMAL:
        raise RuntimeError(
            "The optimizer could not prove the minimum-cost plan."
        )

    lines = []
    total_cost_cents = 0
    used_warehouses = set()

    for item in items:
        for option in eligible[item.id]:
            warehouse = option["warehouse"]
            rate = option["rate"]
            key = (item.id, warehouse.id)

            quantity = solver.Value(quantity_vars[key])

            if quantity <= 0:
                continue

            unit_cost_cents = money_to_cents(
                Decimal(item.product.weight_kg)
                * Decimal(rate.cost_per_kg)
            )
            line_cost_cents = unit_cost_cents * quantity

            lines.append({
                "order_item_id": item.id,
                "warehouse_id": warehouse.id,
                "quantity": quantity,
                "shipping_cost_cents": line_cost_cents,
                "estimated_delivery_at": option["delivery_at"],
            })

            total_cost_cents += line_cost_cents
            used_warehouses.add(warehouse.id)

    # Add the fixed shipping fee once for each selected warehouse.
    for warehouse_id in used_warehouses:
        rate = rate_by_warehouse[warehouse_id]
        total_cost_cents += money_to_cents(rate.fixed_cost)

    requested_units = sum(item.quantity for item in items)

    if maximum_units == requested_units:
        result_status = "FULL"
    elif maximum_units > 0:
        result_status = "PARTIAL"
    else:
        result_status = "INFEASIBLE"

    return {
        "status": result_status,
        "requested_units": requested_units,
        "allocated_units": maximum_units,
        "shipment_count": len(used_warehouses),
        "total_shipping_cost_cents": total_cost_cents,
        "lines": lines,
        "decisions": decisions,
        "reason": (
            "All requested units can be allocated."
            if result_status == "FULL"
            else "Only part of the requested quantity can be allocated."
            if result_status == "PARTIAL"
            else "No feasible allocation was found."
        ),
    }