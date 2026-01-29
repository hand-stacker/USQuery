from rest_framework.decorators import api_view
from rest_framework.views import APIView
from rest_framework.response import Response
from app.models import UserProfile
from .models import Device, StarredBill, FavoriteSubject, StarredMembership
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.db import transaction
from .push import send_bill_notification
from django.core.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication

def _validation_error_detail(e: ValidationError):
    if hasattr(e, "message_dict"):
        return e.message_dict
    if hasattr(e, "messages"):
        return e.messages
    return str(e)

# Registers a new device for a user_profile
# expects a device_token and platform to add device, and an access_token for verification
class RegisterDevice(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not request.user.is_active:
            return Response({"error" :"Verify your email."}, status=403)
        user_profile, created = UserProfile.objects.get_or_create(user=request.user)
        token = request.data.get("device_token")
        platform = request.data.get("platform")
        if not token or not platform:
            return Response({"error": "Missing fields"}, status=400)
        try:
            Device.objects.update_or_create(
                device_token=token,
                user_profile = user_profile,
                platform = platform,
                is_active = False,
                defaults={"is_active": True}
            )
        except ValidationError as e:
            return Response({"error": _validation_error_detail(e)}, status=403)

        return Response({"status": "registered"}, status=201)

# unregisters a device
# expects a device_token to delete, and an access_token for verification
class UnregisterDevice(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not request.user.is_active:
            return Response({"error" :"Verify your email."}, status=403)
        user_profile, created = UserProfile.objects.get_or_create(user=request.user)
        token = request.data.get("device_token")
        if not token:
            return Response({"error": "Missing fields"}, status=400)
        user_profile.get_active_devices().filter(device_token=token).update(is_active=False)

        return Response({"status" : "device unregistered"}, status=202)

# Stars a bill for all devices of a user
# expects acces_token for verification
class StarBill(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not request.user.is_active:
            return Response({"error" :"Verify your email."}, status=403)
        user_profile, created = UserProfile.objects.get_or_create(user=request.user)
        bill_id = request.data.get("bill_id")
        if not bill_id:
            return Response({"error": "Missing fields"}, status=400)
        try:
            StarredBill.objects.update_or_create(
                user_profile=user_profile,
                bill_id=bill_id,
                is_active = False,
                defaults={"is_active": True}
            )
        except ValidationError as e:
            return Response({"error": _validation_error_detail(e)}, status=403)

        return Response({"status": "starred"}, status=201)

# Unstars a bill for all devices of a user
# expects acces_token for verification
class UnstarBill(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not request.user.is_active:
            return Response({"error" :"Verify your email."}, status=403)
        user_profile, created = UserProfile.objects.get_or_create(user=request.user)
        bill_id = request.data.get("bill_id")
        if not bill_id:
            return Response({"error": "Missing fields"}, status=400)
        user_profile.get_starred_bills().filter(bill_id=bill_id).update(is_active=False)

        return Response({"status": "unstarred"}, status = 202)

# Stars a bill for all devices of a user
# expects acces_token for verification
class StarMembership(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not request.user.is_active:
            return Response({"error" :"Verify your email."}, status=403)
        user_profile, created = UserProfile.objects.get_or_create(user=request.user)
        membership_id = request.data.get("membership_id")
        if not membership_id:
            return Response({"error": "Missing fields"}, status=400)
        try:
            StarredMembership.objects.update_or_create(
                user_profile=user_profile,
                membership_id=membership_id,
                is_active = False,
                defaults={"is_active": True}
            )
        except ValidationError as e:
            return Response({"error": _validation_error_detail(e)}, status=403)

        return Response({"status": "starred"}, status=201)

# Unstars a bill for all devices of a user
# expects acces_token for verification
class UnstarMembership(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not request.user.is_active:
            return Response({"error" :"Verify your email."}, status=403)
        user_profile, created = UserProfile.objects.get_or_create(user=request.user)
        membership_id = request.data.get("membership_id")
        if not membership_id:
            return Response({"error": "Missing fields"}, status=400)
        user_profile.get_starred_memberships().filter(membership_id=membership_id).update(is_active=False)

        return Response({"status": "unstarred"}, status = 202)

class UpdateFavoriteSubjects(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        with transaction.atomic():
            subject_ids = request.data.get("subject_ids")
            if not request.user.is_active:
                return Response({"error" :"Verify your email."}, status=403)
            user_profile, created = UserProfile.objects.get_or_create(user=request.user)
            # deactivates any active subjects not in the posted list
            user_profile.get_favorite_subjects().exclude(subject_id__in=subject_ids).update(is_active=False)
            # split update and create for list
            existing_objs = FavoriteSubject.objects.filter(user_profile=user_profile, subject_id__in=subject_ids) 
            existing_by_subject_id = {fav.subject_id: fav for fav in existing_objs}
            to_update = []
            to_create = []
            for subject_id in subject_ids:
                fav = existing_by_subject_id.get(subject_id)
                if fav:
                    if not fav.is_active:
                        fav.is_active = True
                        to_update.append(fav)
                else:
                    to_create.append(FavoriteSubject(
                        user_profile=user_profile,
                        subject_id=subject_id))

            if to_update:
                FavoriteSubject.objects.bulk_update(to_update, ["is_active"])
            if to_create:
                FavoriteSubject.objects.bulk_create(to_create)
            return Response({"status": "updated favorites"}, status=202)

# Returns a user's starred bills, starred memberships, and favorite subjects (as last stored in db)
# expects acces_token for verification
@api_view(['GET'])
def getUserPreferences(request):
    user_profile, created = UserProfile.objects.get_or_create(user=request.user)
    # TODO : make one single query rather than 3...
    sb_qs = user_profile.get_starred_bills()
    raw_sb_ids =  list(sb_qs.values_list("bill_id", flat=True))
    starred_bill_ids = []
    for _id in raw_sb_ids:
        try:
            starred_bill_ids.append(int(_id))
        except Exception:
            continue

    sm_qs = user_profile.get_starred_memberships()
    raw_sm_ids =  list(sm_qs.values_list("membership_id", flat=True))
    starred_mem_ids = []
    for _id in raw_sm_ids:
        try:
            starred_mem_ids.append(int(_id))
        except Exception:
            continue

    fs_qs = user_profile.get_favorite_subjects()
    raw_fs_ids =  list(fs_qs.values_list("subject_id", flat=True))
    fav_sub_ids = []
    for _id in raw_fs_ids:
        try:
            fav_sub_ids.append(int(_id))
        except Exception:
            continue

    return Response({"bill_ids": starred_mem_ids, "membership_ids" : starred_mem_ids, "subject_ids" : fav_sub_ids}, status=202)

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
