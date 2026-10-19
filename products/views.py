from django.core.exceptions import ObjectDoesNotExist
from django.db import IntegrityError
from rest_framework import status
from rest_framework.permissions import IsAdminUser,AllowAny
from rest_framework.views import APIView

from .serializers import (
    InventorySerializer,
    InventoryUpdateSerializer,
    ProductSerializer,
)
from .services import update_inventory
from .models import Product
from utils.response import success_response, error_response


class InventoryUpdateAPIView(APIView):
    permission_classes = [AllowAny]

    def put(self, request, warehouse_id, product_id):
        serializer = InventoryUpdateSerializer(data=request.data)

        if not serializer.is_valid():
            return error_response(
                "Validation failed.",
                serializer.errors,
                status.HTTP_400_BAD_REQUEST,
            )

        try:
            inventory = update_inventory(
                warehouse_id=warehouse_id,
                product_id=product_id,
                **serializer.validated_data,
            )

        except ObjectDoesNotExist:
            return error_response(
                "Warehouse or product not found.",
                None,
                status.HTTP_404_NOT_FOUND,
            )

        except ValueError as exc:
            return error_response(
                str(exc),
                None,
                status.HTTP_400_BAD_REQUEST,
            )

        except IntegrityError:
            return error_response(
                "Inventory update could not be completed.",
                None,
                status.HTTP_409_CONFLICT,
            )

        return success_response(
            "Inventory updated successfully.",
            InventorySerializer(inventory).data,
            status.HTTP_200_OK,
        )


class ProductCreateAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ProductSerializer(data=request.data)

        if not serializer.is_valid():
            return error_response(
                "Validation failed.",
                serializer.errors,
                status.HTTP_400_BAD_REQUEST,
            )

        product = serializer.save()

        return success_response(
            "Product created successfully.",
            ProductSerializer(product).data,
            status.HTTP_201_CREATED,
        )