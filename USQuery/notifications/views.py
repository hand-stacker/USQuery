from rest_framework.views import APIView
from rest_framework.response import Response
from app.models import UserProfile
from .models import Device, StarredBill
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from .push import send_bill_notification
from django.core.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated

# Registers a new device for a user_profile
# expects a device_token and platform to add device, and an access_token for verification
class RegisterDevice(APIView):
    authentication_classes = []
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not request.user.is_active:
            return Response({"error" :"Verify your email."}, status=403)
        user_profile = UserProfile.objects.get_or_create(user=request.user)

        token = request.data.get("device_token")
        platform = request.data.get("platform")

        if not token or not platform:
            return Response({"error": "Missing fields"}, status=400)
        try:
            Device.objects.update_or_create(
                device_token=token,
                user_profile = user_profile,
                defaults={"platform": platform}
            )
        except ValidationError as e:
            return Response(e, status=400)


        return Response({"status": "registered"})

# unregisters a device
# expects a device_token to delete, and an access_token for verification
class UnregisterDevice(APIView):
    authentication_classes = []
    permission_classes = [IsAuthenticated]
    def post(self, request):
        if not request.user.is_active:
            return Response({"error" :"Verify your email."}, status=403)
        user_profile = UserProfile.objects.get_or_create(user=request.user)
        token = request.data.get("device_token")

        Device.objects.filter(
            device_token=token,
            user_profile=user_profile).delete()
        return Response({"status" : "device unregistered"}, status=200)



# Stars a bill for all devices of a user
# expects acces_token for verification
class StarBill(APIView):
    authentication_classes = []
    permission_classes = [IsAuthenticated]

    def post(self, request):
        bill_id = request.data.get("bill_id")
        if not request.user.is_active:
            return Response({"error" :"Verify your email."}, status=403)

        user_profile = UserProfile.objects.get_or_create(user=request.user)
        StarredBill.objects.get_or_create(
            user_profile=user_profile,
            bill_id=bill_id
        )

        return Response({"status": "starred"})

# Unstars a bill for all devices of a user
# expects acces_token for verification
class UnstarBill(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        bill_id = request.data.get("bill_id")
        if not request.user.is_active:
            return Response({"error" :"Verify your email."}, status=403)
        user_profile = UserProfile.objects.get_or_create(user=request.user)
        user_profile.get_starred_bills().filter(bill_id=bill_id).delete()
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
