"""Ask Apple to send a TEST notification to our webhook, then report the result.

This is the end-to-end check that App Store Server Notifications are wired up:
Apple posts a real, signed TEST payload to the notification URL configured in
App Store Connect, and the Get Test Notification Status endpoint reports back
what our server answered. A 200 here means the whole path -- Apple's signing,
our URL, our signature verification -- works.

Credentials come from the same settings the rest of apple_iap uses
(APPLE_IAP_KEY_ID, APPLE_IAP_ISSUER_ID, APPLE_IAP_BUNDLE_ID and either
APPLE_IAP_PRIVATE_KEY or APPLE_IAP_PRIVATE_KEY_PATH); there are deliberately no
credential flags, so what this exercises is the config the server actually runs
with.

    python manage.py apple_test_notification --env sandbox
    python manage.py apple_test_notification --env sandbox --token <token>
"""

import logging
import time

from django.core.management.base import BaseCommand, CommandError

from appstoreserverlibrary.api_client import APIError, APIException
from appstoreserverlibrary.models.Environment import Environment

from app import apple_iap

logger = logging.getLogger(__name__)

ENVIRONMENTS = {
    'sandbox': Environment.SANDBOX,
    'production': Environment.PRODUCTION,
}


class Command(BaseCommand):
    help = "Requests an App Store Server TEST notification and reports delivery."

    def add_arguments(self, parser):
        parser.add_argument(
            '--env',
            choices=sorted(ENVIRONMENTS),
            default='sandbox',
            help='App Store environment to request the notification from (default sandbox).',
        )
        parser.add_argument(
            '--token',
            help='Check an existing test notification token instead of requesting a new one.',
        )
        parser.add_argument(
            '--timeout',
            type=int,
            default=60,
            help='Seconds to poll for the delivery result (default 60). Use 0 to skip polling.',
        )

    def handle(self, *args, **options):
        environment = ENVIRONMENTS[options['env']]

        client = apple_iap._api_client(environment)
        if client is None:
            raise CommandError(
                'App Store Server API is not configured. Set APPLE_IAP_KEY_ID, '
                'APPLE_IAP_ISSUER_ID, APPLE_IAP_BUNDLE_ID and APPLE_IAP_PRIVATE_KEY '
                '(or APPLE_IAP_PRIVATE_KEY_PATH).'
            )

        if environment is Environment.SANDBOX and not apple_iap.sandbox_allowed():
            self.stderr.write(self.style.WARNING(
                'APPLE_IAP_ALLOW_SANDBOX is not true: the webhook will reject the '
                'sandbox payload it receives, so expect a non-200 send attempt.'
            ))

        token = options['token']
        if token:
            self.stdout.write(f"Checking existing token in {environment.value}.")
        else:
            try:
                response = client.request_test_notification()
            except APIException as exc:
                raise CommandError(self._describe(exc))

            token = response.testNotificationToken
            if not token:
                raise CommandError('Apple returned no test notification token.')
            self.stdout.write(f"Requested test notification in {environment.value}.")
            self.stdout.write(f"Token: {token}")

        timeout = options['timeout']
        if timeout <= 0:
            self.stdout.write('Skipping status poll. Re-run with --token to check later.')
            return

        status = self._poll(client, token, timeout)
        if status is None:
            self.stderr.write(self.style.WARNING(
                f"Apple had no status after {timeout}s. Re-run with "
                f"--token {token} to check again."
            ))
            return

        self._report(status)

    def _describe(self, exc):
        name = exc.api_error.name if exc.api_error else exc.raw_api_error
        return f"Apple API error (HTTP {exc.http_status_code}, {name}): {exc.error_message}"

    def _poll(self, client, token, timeout):
        """Poll for the status until Apple stops reporting 'not found'.

        Apple returns TEST_NOTIFICATION_NOT_FOUND for a few seconds after the
        request while the notification is still in flight, which is the same
        error it returns for an expired token. Only the timeout tells them
        apart, so treat it as pending until the clock runs out.
        """
        deadline = time.monotonic() + timeout
        while True:
            try:
                return client.get_test_notification_status(token)
            except APIException as exc:
                if exc.api_error is not APIError.TEST_NOTIFICATION_NOT_FOUND:
                    raise CommandError(self._describe(exc))

            if time.monotonic() >= deadline:
                return None
            self.stdout.write('Waiting for Apple to deliver...')
            time.sleep(3)

    def _report(self, status):
        attempts = status.sendAttempts or []
        if not attempts:
            self.stderr.write(self.style.WARNING(
                'Apple recorded no send attempts. Check the Server URL in App Store Connect.'
            ))
        for index, attempt in enumerate(attempts, start=1):
            result = attempt.rawSendAttemptResult or 'UNKNOWN'
            when = apple_iap._ms_to_dt(attempt.attemptDate)
            line = f"Attempt {index}: {result} at {when}"
            if result == 'SUCCESS':
                self.stdout.write(self.style.SUCCESS(line))
            else:
                self.stderr.write(self.style.ERROR(line))

        if not status.signedPayload:
            return

        # Decoding proves the payload verifies against the root CAs we ship,
        # which is the same check the webhook performs on delivery.
        try:
            payload = apple_iap.verify_notification(status.signedPayload)
        except apple_iap.AppleVerificationError as exc:
            self.stderr.write(self.style.ERROR(f"Payload did not verify: {exc}"))
            return

        self.stdout.write(
            f"Payload verified: {payload.rawNotificationType} "
            f"(uuid {payload.notificationUUID})"
        )
