from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import Device, StarredBill

class RegisterDevice(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        token = request.data.get("device_token")
        platform = request.data.get("platform")

        if not token or not platform:
            return Response({"error": "Missing fields"}, status=400)

        Device.objects.update_or_create(
            device_token=token,
            defaults={"platform": platform}
        )

        return Response({"status": "registered"})

class StarBill(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        token = request.data.get("device_token")
        bill_id = request.data.get("bill_id")

        device = Device.objects.filter(device_token=token).first()
        if not device:
            return Response({"error": "Device not registered"}, status=400)

        StarredBill.objects.get_or_create(
            device=device,
            bill_id=bill_id
        )

        return Response({"status": "starred"})

class UnstarBill(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        token = request.data.get("device_token")
        bill_id = request.data.get("bill_id")

        device = Device.objects.filter(device_token=token).first()
        if not device:
            return Response({"error": "Device not registered"}, status=400)

        StarredBill.objects.filter(
            device=device,
            bill_id=bill_id
        ).delete()

        return Response({"status": "unstarred"})
