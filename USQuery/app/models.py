import uuid
from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone
from datetime import timedelta
from pgvector.django import VectorField

SUBSCRIPTION_TYPE = {
    0:'Free', 
    1:'Plus',
    2:'Premium',
    3:'Special'
    }

DEVICE_LIMITS = {
    0:3, 
    1:10,
    2:20,
    3:1000}

STARRED_BILLS_LIMITS = {
    0:10,
    1:50,
    2:100,
    3:1000}

STARRED_MEMBERSHIPS_LIMITS = {
    0:3,
    1:10,
    2:100,
    3:1000}

PREDICTION_LIMITS = {
    0:0,
    1:3,
    2:100,
    3:1000000}

DAILY_CHAT_LIMITS = {
    0:0,
    1:3,
    2:10000,
    3:1000000}

DAILY_CHAT_TOKEN_LIMITS = {
    0:0,
    1:10000,
    2:100000,
    3:1000000}

DAILY_OUTPUT_TOKEN_LIMITS = {
    0:0,
    1:5000,
    2:50000,
    3:500000}

class UserProfile(models.Model):
    class SubType(models.IntegerChoices):
        Free = 0
        Plus = 1
        Premium = 2
        Special = 3

    class OAuthProvider(models.TextChoices):
        GOOGLE = 'google', 'Google'
        APPLE = 'apple', 'Apple'

    id = models.BigAutoField(primary_key=True)
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    user_type = models.IntegerField(choices=SubType, default=0)
    enabled_bill_notif = models.BooleanField(default=True)
    enabled_subject_notif = models.BooleanField(default=True)
    scheduled_for_deletion = models.BooleanField(default=False, db_index=True)
    oauth_provider = models.CharField(
        max_length=10,
        choices=OAuthProvider,
        null=True,
        blank=True,
    )
    oauth_provider_id = models.CharField(max_length=255, null=True, blank=True, db_index=True)
    stripe_customer_id = models.CharField(max_length=255, null=True, blank=True, db_index=True)
    stripe_subscription_id = models.CharField(max_length=255, null=True, blank=True, db_index=True)
    subscription_period_end = models.DateTimeField(null=True, blank=True)
    subscription_cancel_at_period_end = models.BooleanField(default=False)

    def get_active_devices(self):
        return self.devices.filter(is_active=True)

    def get_starred_bills(self):
        return self.starred_bills.filter(is_active=True)

    def get_starred_memberships(self):
        return self.starred_memberships.filter(is_active=True)

    # gets active subjects
    def get_favorite_subjects(self):
        return self.favorite_subjects.filter(is_active=True)

    # gets subscription type
    def get_subscription_type(self):
        return SUBSCRIPTION_TYPE[self.user_type]

    # returns the device limit (int) for this user_profile
    def get_device_limit(self):
        return DEVICE_LIMITS[self.user_type]

    # returns the starred bills limit (int) for this user_profile
    def get_starred_bills_limit(self):
        return STARRED_BILLS_LIMITS[self.user_type]

    # returns the starred memberships limit (int) for this user_profile
    def get_starred_memberships_limit(self):
        return STARRED_MEMBERSHIPS_LIMITS[self.user_type]

    # for future use, limits daily prediction views
    def get_predicton_limit(self):
        return PREDICTION_LIMITS[self.user_type]

    # for future use, limits daily prediction views
    def get_chat_limit(self):
        return DAILY_CHAT_LIMITS[self.user_type]

    # for future use, limits daily prediction views
    def get_chat_token_limit(self):
        return DAILY_CHAT_TOKEN_LIMITS[self.user_type]

    # for future use, limits daily prediction views
    def get_chat_output_limit(self):
        return DAILY_OUTPUT_TOKEN_LIMITS[self.user_type]


class ChatSession(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='chat_sessions')
    bill_id = models.IntegerField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=['user', 'bill_id'])]


class ChatMessage(models.Model):
    class Role(models.TextChoices):
        USER = 'user', 'User'
        ASSISTANT = 'assistant', 'Assistant'

    id = models.BigAutoField(primary_key=True)
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name='messages')
    role = models.CharField(max_length=10, choices=Role)
    content = models.TextField()
    input_tokens = models.IntegerField(default=0)
    output_tokens = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=['session', 'created_at'])]


class BillChunk(models.Model):
    id = models.BigAutoField(primary_key=True)
    bill_id = models.IntegerField(db_index=True)
    chunk_index = models.IntegerField()
    content = models.TextField()
    embedding = VectorField(dimensions=768)

    class Meta:
        unique_together = [('bill_id', 'chunk_index')]


class EmailVerification(models.Model):
    id = models.BigAutoField(primary_key=True)
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    code = models.UUIDField(default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    resend_count = models.PositiveIntegerField(default=0)
    last_resend_date = models.DateField(null=True, blank=True)

    MAX_DAILY_RESENDS = 5

    def is_valid(self):
        return timezone.now() <= self.created_at + timedelta(minutes=10)

    def can_resend(self):
        today = timezone.localdate()

        if self.last_resend_date != today:
            return True

        return self.resend_count < self.MAX_DAILY_RESENDS

    def resend(self):
        today = timezone.localdate()

        if self.last_resend_date != today:
            self.resend_count = 0
            self.last_resend_date = today

        self.resend_count += 1
        self.code = uuid.uuid4()
        self.created_at = timezone.now()

        self.save(
            update_fields=[
                "code",
                "created_at",
                "resend_count",
                "last_resend_date",
            ]
        )