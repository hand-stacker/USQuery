import requests
from .models import Device, FavoriteSubject, StarredBill
from asgiref.sync import sync_to_async

EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"
EXPO_BATCH_SIZE = 100  # Expo recommends up to 100 messages per request


async def send_bill_notification(bill_id, title, body):
    users = await sync_to_async(list)(
        StarredBill.objects.filter(bill_id=bill_id, is_active=True).values_list("user_profile__id", flat=True)
    )
    if not users:
        return
    tokens = await sync_to_async(list)(
        Device.objects.filter(user_profile__id__in=users, user_profile__enabled_bill_notif=True, is_active=True).values_list("device_token", flat=True)
    )
    if not tokens:
        return

    # Build and send messages in Expo-compatible batches
    for i in range(0, len(tokens), EXPO_BATCH_SIZE):
        batch_tokens = tokens[i : i + EXPO_BATCH_SIZE]
        messages = [
            {
                "to": token,
                "sound": "default",
                "title": title,
                "body": body,
                "data": {"screen" : "Bill_info", "bill_id": bill_id},
            }
            for token in batch_tokens
        ]

        # Run the blocking HTTP call in a thread (sync_to_async) so we don't block the event loop
        await sync_to_async(requests.post)(EXPO_PUSH_URL, json=messages)

async def send_floor_notification(chamber: str, bill_ids: list, profile_ids: list):
    """
    Send a floor notification for the given chamber to specific user profiles.

    Args:
        chamber:     'house' or 'senate'
        bill_ids:    bill IDs that had floor actions
        profile_ids: UserProfile IDs to notify
    """
    if not bill_ids or not profile_ids:
        return
    tokens = await sync_to_async(list)(
        Device.objects.filter(
            user_profile__id__in=profile_ids,
            is_active=True,
        ).values_list("device_token", flat=True)
    )
    if not tokens:
        return
    if chamber == 'house':
        title = "House Floor Activity"
        body = "New actions were taken on the House floor."
        filter_type = "House"
    else:
        title = "Senate Floor Activity"
        body = "New actions were taken on the Senate floor."
        filter_type = "Senate"
    data = {
        "screen": "Bill_Search",
        "sort": "datedesc",
        "filters": {"type": filter_type},
        "highlight": bill_ids,
    }
    for i in range(0, len(tokens), EXPO_BATCH_SIZE):
        batch = tokens[i : i + EXPO_BATCH_SIZE]
        messages = [
            {"to": token, "sound": "default", "title": title, "body": body, "data": data}
            for token in batch
        ]
        await sync_to_async(requests.post)(EXPO_PUSH_URL, json=messages)

async def send_subject_notification(subjects, title, body):
    users = await sync_to_async(set)(
        FavoriteSubject.objects.filter(subject_id__in=subjects, is_active=True).values_list("user_profile__id", flat=True)
    )
    if not users:
        return
    tokens = await sync_to_async(list)(
        Device.objects.filter(user_profile__id__in=users, user_profile__enabled_subject_notif=True, is_active=True).values_list("device_token", flat=True)
    )
    if not tokens:
        return

    # Build and send messages in Expo-compatible batches
    for i in range(0, len(tokens), EXPO_BATCH_SIZE):
        batch_tokens = tokens[i : i + EXPO_BATCH_SIZE]
        messages = [
            {
                "to": token,
                "sound": "default",
                "title": title,
                "body": body,
                "data" : {"screen" : "Bill_FYP", "sort": "datedesc"}
            }
            for token in batch_tokens
        ]

        # Run the blocking HTTP call in a thread (sync_to_async) so we don't block the event loop
        await sync_to_async(requests.post)(EXPO_PUSH_URL, json=messages)

