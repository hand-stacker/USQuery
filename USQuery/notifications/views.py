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
from rest_framework.authentication import SessionAuthentication
from rest_framework_simplejwt.authentication import JWTAuthentication
from datetime import datetime, timezone
import asyncio

def _as_bool(value):
    # JSON sends real booleans; form-encoded bodies send strings, and
    # bool("false") would be True.
    if isinstance(value, str):
        return value.strip().lower() in ("true", "1", "yes", "on")
    return bool(value)

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
            # Keyed on the token alone (it's unique): re-registering is a no-op,
            # and a phone that switched accounts moves to the current user.
            Device.objects.update_or_create(
                device_token=token,
                defaults={"user_profile": user_profile, "platform": platform, "is_active": True}
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

class UpdateFloorNotifPreferences(APIView):
    """
    Update floor notification preferences for house and/or senate.

    Request body (all fields optional):
      house (bool)            — enable/disable house floor notifications;
                                defaults time to current UTC hour if first-time enable
      senate (bool)           — enable/disable senate floor notifications;
                                defaults time to current UTC hour if first-time enable
      house_frequency (int)   — 0=consistent (every update run), 1=daily (once at chosen time)
      senate_frequency (int)  — 0=consistent (every update run), 1=daily (once at chosen time)
      house_time (int 0–23)   — preferred local hour for daily house notification
      senate_time (int 0–23)  — preferred local hour for daily senate notification
      house_timezone (str)    — timezone abbreviation e.g. "PST", "EST", "UTC"
      senate_timezone (str)   — timezone abbreviation e.g. "PST", "EST", "UTC"

    Response 202: {"status": "updated floor notif preferences"}
    Response 400: {"error": "..."} on invalid field values
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not request.user.is_active:
            return Response({"error": "Verify your email."}, status=403)
        user_profile, _ = UserProfile.objects.get_or_create(user=request.user)
        update_fields = []
        now_utc_hour = datetime.now(timezone.utc).hour

        house = request.data.get("house")
        if house is not None:
            user_profile.enabled_house_floor_notif = bool(house)
            update_fields.append("enabled_house_floor_notif")
            if house and user_profile.house_floor_notif_time is None:
                user_profile.house_floor_notif_time = now_utc_hour
                user_profile.house_floor_notif_timezone = 'UTC'
                update_fields += ["house_floor_notif_time", "house_floor_notif_timezone"]

        senate = request.data.get("senate")
        if senate is not None:
            user_profile.enabled_senate_floor_notif = bool(senate)
            update_fields.append("enabled_senate_floor_notif")
            if senate and user_profile.senate_floor_notif_time is None:
                user_profile.senate_floor_notif_time = now_utc_hour
                user_profile.senate_floor_notif_timezone = 'UTC'
                update_fields += ["senate_floor_notif_time", "senate_floor_notif_timezone"]

        house_freq = request.data.get("house_frequency")
        if house_freq is not None:
            if house_freq not in (0, 1):
                return Response({"error": "house_frequency must be 0 (consistent) or 1 (daily)"}, status=400)
            user_profile.house_floor_notif_frequency = house_freq
            update_fields.append("house_floor_notif_frequency")

        senate_freq = request.data.get("senate_frequency")
        if senate_freq is not None:
            if senate_freq not in (0, 1):
                return Response({"error": "senate_frequency must be 0 (consistent) or 1 (daily)"}, status=400)
            user_profile.senate_floor_notif_frequency = senate_freq
            update_fields.append("senate_floor_notif_frequency")

        house_time = request.data.get("house_time")
        if house_time is not None:
            if isinstance(house_time, bool) or not isinstance(house_time, int) or not (0 <= house_time <= 23):
                return Response({"error": "house_time must be an integer 0–23"}, status=400)
            user_profile.house_floor_notif_time = house_time
            update_fields.append("house_floor_notif_time")

        senate_time = request.data.get("senate_time")
        if senate_time is not None:
            if isinstance(senate_time, bool) or not isinstance(senate_time, int) or not (0 <= senate_time <= 23):
                return Response({"error": "senate_time must be an integer 0–23"}, status=400)
            user_profile.senate_floor_notif_time = senate_time
            update_fields.append("senate_floor_notif_time")

        house_tz = request.data.get("house_timezone")
        if house_tz is not None:
            user_profile.house_floor_notif_timezone = str(house_tz).upper()[:10]
            update_fields.append("house_floor_notif_timezone")

        senate_tz = request.data.get("senate_timezone")
        if senate_tz is not None:
            user_profile.senate_floor_notif_timezone = str(senate_tz).upper()[:10]
            update_fields.append("senate_floor_notif_timezone")

        if update_fields:
            user_profile.save(update_fields=list(set(update_fields)))

        return Response({"status": "updated floor notif preferences"}, status=202)


# userwide enabling/blocking of either starred bill updates or updates on bills with users' favorite subjects
# expects an access_token for verification
# optional 'bill' and 'subject' fields which are boolean values that update user's preference if exists
class UpdateNotifPreferences(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not request.user.is_active:
            return Response({"error" :"Verify your email."}, status=403)
        user_profile, created = UserProfile.objects.get_or_create(user=request.user)
        update_fields = []
        bill_pref = request.data.get("bill")
        if bill_pref is not None:
            user_profile.enabled_bill_notif = _as_bool(bill_pref)
            update_fields.append("enabled_bill_notif")
        sub_pref = request.data.get("subject")
        if sub_pref is not None:
            user_profile.enabled_subject_notif = _as_bool(sub_pref)
            update_fields.append("enabled_subject_notif")
        if update_fields:
            user_profile.save(update_fields=update_fields)

        return Response({"status" : "updated preferences"}, status=202)

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

# Stars a bill_id/membership_id for all devices of a user
# for internal web use
class StarItemInternal(APIView):
    """Internal endpoint to star a bill_id or membership_id for the logged-in user.
    Uses session authentication (CSRF cookie) and requires the user to be authenticated.
    """
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not request.user.is_active:
            return Response({"error": "Verify your email."}, status=403)
        user_profile, created = UserProfile.objects.get_or_create(user=request.user)
        # Read from POST body (works for JSON or form-encoded requests)
        bill_id = request.data.get("bill_id", None)
        membership_id = request.data.get("membership_id", None)
        if not bill_id and not membership_id:
            return Response({"error": "Missing fields, please specify either a bill_id or membership_id to star."}, status=400)
        if bill_id:
            try:
                StarredBill.objects.update_or_create(
                    user_profile=user_profile,
                    bill_id=bill_id,
                    defaults={"is_active": True}
                )
            except ValidationError as e:
                return Response({"error": _validation_error_detail(e)}, status=403)
        if membership_id:
            try:
                StarredMembership.objects.update_or_create(
                    user_profile=user_profile,
                    membership_id=membership_id,
                    defaults={"is_active": True}
                )
            except ValidationError as e:
                return Response({"error": _validation_error_detail(e)}, status=403)

        return Response({"status": "starred"}, status=201)

# Unstars a bill_id/membership_id for all devices of a user
# for internal web use
class UnstarItemInternal(APIView):
    """Internal endpoint to unstar a bill_id or membership_id for the logged-in user.
    Uses session authentication (CSRF cookie) and requires the user to be authenticated.
    """
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not request.user.is_active:
            return Response({"error": "Verify your email."}, status=403)
        user_profile, created = UserProfile.objects.get_or_create(user=request.user)
        # Read from POST body (works for JSON or form-encoded requests)
        bill_id = request.data.get("bill_id", None)
        membership_id = request.data.get("membership_id", None)
        if not bill_id and not membership_id:
            return Response({"error": "Missing fields"}, status=400)
        if bill_id:
            user_profile.get_starred_bills().filter(bill_id=bill_id).update(is_active=False)
        if membership_id:
            user_profile.get_starred_memberships().filter(membership_id=membership_id).update(is_active=False)

        return Response({"status": "unstarred"}, status=202)

class UpdateFavoriteSubjects(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        with transaction.atomic():
            subject_ids = request.data.get("subject_ids")
            if not request.user.is_active:
                return Response({"error" :"Verify your email."}, status=403)
            if not isinstance(subject_ids, list) or not all(isinstance(s, int) and not isinstance(s, bool) for s in subject_ids):
                return Response({"error": "subject_ids must be a list of integers"}, status=400)
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

    return Response({
        "bill_ids": starred_bill_ids,
        "membership_ids": starred_mem_ids,
        "subject_ids": fav_sub_ids,
        "enabled_bill_notif": user_profile.enabled_bill_notif,
        "enabled_subject_notif": user_profile.enabled_subject_notif,
        "enabled_house_floor_notif": user_profile.enabled_house_floor_notif,
        "enabled_senate_floor_notif": user_profile.enabled_senate_floor_notif,
        "house_floor_notif_frequency": user_profile.house_floor_notif_frequency,
        "senate_floor_notif_frequency": user_profile.senate_floor_notif_frequency,
        "house_floor_notif_time": user_profile.house_floor_notif_time,
        "senate_floor_notif_time": user_profile.senate_floor_notif_time,
        "house_floor_notif_timezone": user_profile.house_floor_notif_timezone,
        "senate_floor_notif_timezone": user_profile.senate_floor_notif_timezone,
    }, status=202)

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
    asyncio.run(send_bill_notification(bill_id, title, body))

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
    asyncio.run(send_bill_notification(bill_id, title, body))

    return JsonResponse({
        "status": "sent",
        "bill_id": bill_id,
        "title": title,
        "body": body
    })

# Admin-only endpoint to delete all StarredBill entries whose bill_id starts
# with the provided congress_num.
# Useful for when new congress starts and we delete old ones from users.
@staff_member_required
def MassUnstar(request, congress_num):

    prefix = str(congress_num)
    qs = StarredBill.objects.filter(bill_id__startswith=prefix)
    deleted_count, _ = qs.delete()

    return JsonResponse({
        "status": "deleted",
        "congress_num": congress_num,
        "deleted_count": deleted_count
    })
