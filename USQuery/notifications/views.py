from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import Device, StarredBill
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from .push import send_bill_notification

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

        # Validate bill belongs to current congress (IDs starting with "119")
        if bill_id is None or not str(bill_id).startswith("119"):
            return Response("Bill is not from current congress", status=400)

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

@staff_member_required
def send_test_bill_notification(request):
    """
    Admin-only endpoint to send a mock bill notification using send_bill_notification.
    Accessible to staff users (requires admin login).
    """
    # Default mock data
    bill_id = 11903386
    title = "Test Bill Notification"
    body = "This is a mock notification sent from admin test endpoint."

    # Call the push utility; it will look up devices that starred this bill_id
    send_bill_notification(bill_id, title, body)

    return JsonResponse({
        "status": "sent",
        "bill_id": bill_id,
        "title": title,
        "body": body
    })
@staff_member_required
def send_test_bill_notification_exclusion_test(request):
    """
    Admin-only endpoint to send a mock bill notification using send_bill_notification.
    Accessible to staff users (requires admin login).
    """
    # Default mock data
    bill_id = 99999999
    title = "Test Bill Notification"
    body = """Since this bill does not exist, it should not be able to be
            registered as a device's starred bills and thus no notification recieved."""

    # Call the push utility; it will look up devices that starred this bill_id
    send_bill_notification(bill_id, title, body)

    return JsonResponse({
        "status": "sent",
        "bill_id": bill_id,
        "title": title,
        "body": body
    })

@staff_member_required
def MassUnstar(request, congress_num):
    """
    Admin-only endpoint to delete all StarredBill entries whose bill_id starts
    with the provided congress_num.
    """
    prefix = str(congress_num)
    qs = StarredBill.objects.filter(bill_id__startswith=prefix)
    deleted_count, _ = qs.delete()

    return JsonResponse({
        "status": "deleted",
        "congress_num": congress_num,
        "deleted_count": deleted_count
    })
