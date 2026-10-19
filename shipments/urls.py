
from django.urls import path

from shipments.views import (CreateShipmentsAPIView,UpdateShipmentStatusAPIView)

urlpatterns = [
    path("plans/<int:plan_id>/create/",CreateShipmentsAPIView.as_view(),name="create-shipments"),
    
    path("<int:shipment_id>/status/",UpdateShipmentStatusAPIView.as_view(),name="update-shipment-status"),

]
