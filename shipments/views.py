from django.core.exceptions import ObjectDoesNotExist

from rest_framework import status
from rest_framework.permissions import IsAdminUser, AllowAny
from rest_framework.views import APIView

from shipments.serializers import (
    CreateShipmentRequestSerializer,
    ShipmentSerializer,
    ShipmentStatusUpdateSerializer
)
from shipments.services import create_shipments_for_plan,update_shipment_status
from utils.response import success_response, error_response


class CreateShipmentsAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, plan_id):
        request_serializer = CreateShipmentRequestSerializer(
            data=request.data
        )

        if not request_serializer.is_valid():
            return error_response(
                message="Invalid shipment creation request.",
                data=request_serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        if not request_serializer.validated_data["confirm"]:
            return error_response(
                message="Shipment creation was not confirmed.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        try:
            shipments, created_count = create_shipments_for_plan(
                plan_id=plan_id
            )

        except ObjectDoesNotExist:
            return error_response(
                message="Allocation plan not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        except ValueError as exc:
            return error_response(
                message=str(exc),
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        return success_response(
            message=(
                f"Shipment creation processed successfully. "
                f"{created_count} new shipment(s) created."
            ),
            data={
                "allocation_plan_id": plan_id,
                "created_count": created_count,
                "shipments": ShipmentSerializer(
                    shipments, many=True
                ).data,
            },
            status_code=status.HTTP_201_CREATED if created_count else status.HTTP_200_OK,
        )

class UpdateShipmentStatusAPIView(APIView):
    permission_classes = [AllowAny]

    def patch(self, request, shipment_id):
        request_serializer = ShipmentStatusUpdateSerializer(
            data=request.data
        )

        if not request_serializer.is_valid():
            return error_response(
                message="Invalid shipment status.",
                data=request_serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        try:
            shipment = update_shipment_status(
                shipment_id=shipment_id,
                new_status=request_serializer.validated_data["status"],
            )

        except ObjectDoesNotExist:
            return error_response(
                message="Shipment not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        except ValueError as exc:
            return error_response(
                message=str(exc),
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        return success_response(
            message="Shipment status updated successfully.",
            data=ShipmentSerializer(shipment).data,
        )