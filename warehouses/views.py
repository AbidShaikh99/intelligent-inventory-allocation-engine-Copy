from rest_framework.views import APIView
from rest_framework.permissions import IsAdminUser,AllowAny
from rest_framework import status
from rest_framework import generics

from .models import Warehouse,WarehouseShippingRate
from .serializers import WarehouseSerializer,WarehouseShippingRateSerializer
from utils.response import success_response, error_response


class WarehouseCreateAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = WarehouseSerializer(data=request.data)

        if not serializer.is_valid():
            return error_response(
                "Validation failed.",
                serializer.errors,
                status.HTTP_400_BAD_REQUEST,
            )

        warehouse = serializer.save()

        return success_response(
            "Warehouse created successfully.",
            WarehouseSerializer(warehouse).data,
            status.HTTP_201_CREATED,
        )

class WarehouseShippingRateListCreateAPIView(generics.ListCreateAPIView):
    queryset = WarehouseShippingRate.objects.select_related("warehouse").all()
    serializer_class = WarehouseShippingRateSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        rate = serializer.save()

        return success_response(
            message="Shipping rate created successfully.",
            data=self.get_serializer(rate).data,
            status_code=201,
        )


class WarehouseShippingRateDetailAPIView(generics.RetrieveUpdateAPIView):
    queryset = WarehouseShippingRate.objects.select_related("warehouse").all()
    serializer_class = WarehouseShippingRateSerializer
    permission_classes = [AllowAny]
    http_method_names = ["get", "put", "patch", "head", "options"]

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(
            instance,
            data=request.data,
            partial=partial,
        )
        serializer.is_valid(raise_exception=True)
        rate = serializer.save()

        return success_response(
            message="Shipping rate updated successfully.",
            data=self.get_serializer(rate).data,
        )
