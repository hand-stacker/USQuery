import requests
from .models import Device, FavoriteSubject, StarredBill
from asgiref.sync import sync_to_async

EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"
EXPO_BATCH_SIZE = 100  # Expo recommends up to 100 messages per request


async def send_bill_notification(bill_id, title, body):
    users = await sync_to_async(list)(
        StarredBill.objects.filter(bill_id=bill_id).values_list("user_profile__id", flat=True)
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

async def send_subject_notification(subjects, title, body):
    users = await sync_to_async(set)(
        FavoriteSubject.objects.filter(subject_id__in=subjects).values_list("user_profile__id", flat=True)
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

