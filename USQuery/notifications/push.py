import requests
from .models import StarredBill

EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"

def send_bill_notification(bill_id, title, body):
    tokens = (
        StarredBill.objects
        .filter(bill_id=bill_id)
        .values_list("device__device_token", flat=True)
    )

    messages = [
        {
            "to": token,
            "sound": "default",
            "title": title,
            "body": body,
            "data": {"bill_id": bill_id},
        }
        for token in tokens
    ]

    if messages:
        requests.post(EXPO_PUSH_URL, json=messages)

