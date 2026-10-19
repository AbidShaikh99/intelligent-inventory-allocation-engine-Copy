from django.core.exceptions import ObjectDoesNotExist
from rest_framework import status
from rest_framework.permissions import IsAdminUser,AllowAny
from rest_framework.views import APIView
from allocation.reservation_services import reserve_allocation_plan
from allocation.models import AllocationPlan

from allocation.serializers import (
    AllocationRequestSerializer,
    AllocationPlanSerializer,
    ReservationRequestSerializer
)
from allocation.services import create_allocation_plan,rebalance_eligible_orders
from utils.response import success_response, error_response


class OrderAllocationAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, order_id):
        request_serializer = AllocationRequestSerializer(
            data=request.data
        )

        if not request_serializer.is_valid():
            return error_response(
                "Allocation request validation failed.",
                request_serializer.errors,
                status.HTTP_400_BAD_REQUEST,
            )

        try:
            plan = create_allocation_plan(
                order_id=order_id,
                **request_serializer.validated_data,
            )

        except ObjectDoesNotExist:
            return error_response(
                "Order not found.",
                {"order_id": order_id},
                status.HTTP_404_NOT_FOUND,
            )

        except ValueError as exc:
            return error_response(
                "Allocation could not be created.",
                {"detail": str(exc)},
                status.HTTP_400_BAD_REQUEST,
            )

        except RuntimeError as exc:
            return error_response(
                "Optimization could not be completed.",
                {"detail": str(exc)},
                status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        return success_response(
            "Allocation plan created successfully.",
            AllocationPlanSerializer(plan).data,
            status.HTTP_201_CREATED,
        )

class ReserveAllocationPlanAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, plan_id):
        serializer = ReservationRequestSerializer(data=request.data)

        if not serializer.is_valid():
            return error_response(
                "Reservation request validation failed.",
                serializer.errors,
                status.HTTP_400_BAD_REQUEST,
            )

        try:
            plan = reserve_allocation_plan(plan_id=plan_id)

        except ObjectDoesNotExist:
            return error_response(
                "Allocation plan not found.",
                {"plan_id": plan_id},
                status.HTTP_404_NOT_FOUND,
            )

        except ValueError as exc:
            return error_response(
                "Inventory reservation failed.",
                {"detail": str(exc)},
                status.HTTP_400_BAD_REQUEST,
            )

        return success_response(
            "Inventory reserved successfully.",
            AllocationPlanSerializer(plan).data,
            status.HTTP_200_OK,
        )

class AllocationRebalanceAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = AllocationRequestSerializer(data=request.data)

        if not serializer.is_valid():
            return error_response(
                "Rebalance request validation failed.",
                serializer.errors,
                status.HTTP_400_BAD_REQUEST,
            )

        try:
            summary = rebalance_eligible_orders(
                **serializer.validated_data
            )
        except RuntimeError as exc:
            return error_response(
                "Allocation rebalance could not be completed.",
                {"detail": str(exc)},
                status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        return success_response(
            "Allocation rebalance completed.",
            summary,
            status.HTTP_200_OK,
        )


class AllocationDecisionAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, plan_id):
        plan = (
            AllocationPlan.objects
            .filter(pk=plan_id)
            .prefetch_related(
                "lines__warehouse",
                "lines__order_item__product",
            )
            .first()
        )

        if plan is None:
            return error_response(
                "Allocation plan not found.",
                {"plan_id": plan_id},
                status.HTTP_404_NOT_FOUND,
            )

        serializer = AllocationPlanSerializer(plan)

        return success_response(
            "Allocation decision retrieved successfully.",
            serializer.data,
            status.HTTP_200_OK,
        )
