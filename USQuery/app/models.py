import uuid
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.utils import timezone
from datetime import timedelta
from pgvector.django import VectorField

SUBSCRIPTION_TYPE = {
    0:'Free',
    1:'Plus',
    2:'Premium',
    3:'Special',
    4:'Plus Pro',
    }

DEVICE_LIMITS = {
    0:5,
    1:5,
    2:5,
    3:1000,
    4:5}

STARRED_BILLS_LIMITS = {
    0:10,
    1:50,
    2:1000,
    3:10000,
    4:100}

STARRED_MEMBERSHIPS_LIMITS = {
    0:3,
    1:10,
    2:100,
    3:1000,
    4:25}

PREDICTION_LIMITS = {
    0:0,
    1:3,
    2:100,
    3:1000000,
    4:10}

DAILY_PREDICTION_CREDITS = {
    0: 0,
    1: 10,
    2: 10000,
    3: 10000,
    4: 30,
}

DAILY_CHAT_LIMITS = {
    0:0,
    1:10,       # Plus: 10 chats/day
    2:10000,    # Premium: gated by monthly token limit, not daily chats
    3:1000000,
    4:30}       # Plus Pro: 30 chats/day

DAILY_CHAT_TOKEN_LIMITS = {
    0:0,
    1:10000,
    2:100000,
    3:1000000,
    4:30000}

DAILY_OUTPUT_TOKEN_LIMITS = {
    0:0,
    1:5000,
    2:50000,
    3:500000,
    4:15000}

# Claude Haiku 4.5 pricing — verified against Anthropic pricing page 2026-06-11
HAIKU_INPUT_COST_PER_TOKEN  = 1.00 / 1_000_000
HAIKU_OUTPUT_COST_PER_TOKEN = 5.00 / 1_000_000

# Anthropic web search tool: $10 per 1,000 searches, billed on top of tokens
# (verified against Anthropic web-search tool docs 2026-06-12)
WEB_SEARCH_COST_PER_SEARCH = 10.00 / 1_000

VOYAGE_COST_PER_TOKEN = 0.12 / 1_000_000

# Output tokens cost 5x input ($5.00 vs $1.00 per 1M), so monthly budgets are
# enforced in cost-weighted units: input_tokens + 5 * output_tokens.
OUTPUT_TOKEN_COST_WEIGHT = 5

MONTHLY_COST_LIMITS = {
    0: 0.0,
    1: float('inf'),  # Plus:     no cost cap; gated by daily chat limit only
    2: float('inf'),  # Premium:  gated by monthly input token limit instead
    3: float('inf'),
    4: float('inf'),  # Plus Pro: no cost cap; gated by daily chat limit only
}

# Premium monthly token budget in cost-weighted units (input + 5*output), so a
# weighted unit costs $1.00/1M regardless of the input:output ratio.
# 5M weighted units = $5.00/mo max token spend.
MONTHLY_TOKEN_BUDGETS = {
    0: 0,           # Free: no access
    1: 0,           # Plus: no token budget; gated by daily chat count
    2: 5_000_000,   # Premium: 5M weighted tokens/month ($5.00 max)
    3: 0,           # Special: no limit
    4: 0,           # Plus Pro: no token budget; gated by daily chat count
}

MONTHLY_WEB_SEARCH_LIMITS = {
    0: 0,            # Free: no chatbot
    1: 30,           # Plus: 30 web searches/month
    2: 200,          # Premium: 200 web searches/month
    3: 1_000_000,    # Special: effectively unlimited
    4: 60,           # Plus Pro: 60 web searches/month
}

class UserProfile(models.Model):
    class SubType(models.IntegerChoices):
        Free = 0
        Plus = 1
        Premium = 2
        Special = 3
        PlusPro = 4

    class OAuthProvider(models.TextChoices):
        GOOGLE = 'google', 'Google'
        APPLE = 'apple', 'Apple'

    # Which processor owns the current paid subscription. Stripe is the web and
    # Android path; Apple is StoreKit in-app purchase (required on iOS by App
    # Store guideline 3.1.1). Null means the user has never paid.
    class BillingProvider(models.TextChoices):
        STRIPE = 'stripe', 'Stripe'
        APPLE = 'apple', 'Apple'

    class FloorNotifFrequency(models.IntegerChoices):
        CONSISTENT = 0, 'Consistent'
        DAILY = 1, 'Daily'

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
    billing_provider = models.CharField(
        max_length=10,
        choices=BillingProvider,
        null=True,
        blank=True,
    )
    # Apple's stable identifier for the subscription across renewals (transactionId
    # changes every billing period, originalTransactionId does not). Denormalized
    # from AppleSubscription so the Stripe endpoints' guards are a field read.
    apple_original_transaction_id = models.CharField(max_length=64, null=True, blank=True, db_index=True)
    subscription_period_end = models.DateTimeField(null=True, blank=True)
    subscription_cancel_at_period_end = models.BooleanField(default=False)
    subscription_change_at_period_end = models.SmallIntegerField(default=-1) # if -1 we do not change, otherwise if R(0-4) change to set type
    enabled_house_floor_notif = models.BooleanField(default=False)
    enabled_senate_floor_notif = models.BooleanField(default=False)
    house_floor_notif_frequency = models.SmallIntegerField(
        choices=FloorNotifFrequency, default=FloorNotifFrequency.DAILY)
    senate_floor_notif_frequency = models.SmallIntegerField(
        choices=FloorNotifFrequency, default=FloorNotifFrequency.DAILY)
    house_floor_notif_time = models.SmallIntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(23)])
    senate_floor_notif_time = models.SmallIntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(23)])
    house_floor_notif_timezone = models.CharField(max_length=10, null=True, blank=True)
    senate_floor_notif_timezone = models.CharField(max_length=10, null=True, blank=True)

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

    #delete after most users upgrade mobile app
    def get_predicton_limit(self):
        return PREDICTION_LIMITS[self.user_type]

    def get_daily_prediction_credits(self):
        return DAILY_PREDICTION_CREDITS[self.user_type]

    # for future use, limits daily prediction views
    def get_chat_limit(self):
        return DAILY_CHAT_LIMITS[self.user_type]

    # for future use, limits daily prediction views
    def get_chat_token_limit(self):
        return DAILY_CHAT_TOKEN_LIMITS[self.user_type]

    def get_chat_output_limit(self):
        return DAILY_OUTPUT_TOKEN_LIMITS[self.user_type]

    def get_monthly_cost_limit(self) -> float:
        return MONTHLY_COST_LIMITS[self.user_type]

    def get_monthly_token_budget(self) -> int:
        return MONTHLY_TOKEN_BUDGETS[self.user_type]

    def get_monthly_web_search_limit(self) -> int:
        return MONTHLY_WEB_SEARCH_LIMITS[self.user_type]


class AppleSubscription(models.Model):
    """An Apple (StoreKit 2) auto-renewable subscription bound to a user account.

    One row per originalTransactionId, which is Apple's stable identifier for a
    subscription across renewals and tier changes. The uniqueness constraint is
    what stops a single Apple ID from farming entitlements onto many accounts:
    a transaction already bound to another user is rejected at verify time.

    UserProfile stays the source of truth for what the app is allowed to do
    (user_type and the subscription_* fields); this model records the Apple-side
    state that produced it, so notifications can be reconciled and replayed.
    """

    class Environment(models.TextChoices):
        SANDBOX = 'Sandbox', 'Sandbox'
        PRODUCTION = 'Production', 'Production'

    id = models.BigAutoField(primary_key=True)
    original_transaction_id = models.CharField(max_length=64, unique=True, db_index=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='apple_subscriptions')
    product_id = models.CharField(max_length=128)
    tier = models.SmallIntegerField(default=0)
    environment = models.CharField(max_length=16, choices=Environment)
    latest_transaction_id = models.CharField(max_length=64, null=True, blank=True)
    expires_date = models.DateTimeField(null=True, blank=True)
    auto_renew_status = models.BooleanField(default=True)
    # The product that will be billed at the next renewal. When it differs from
    # product_id the user has scheduled a deferred downgrade.
    auto_renew_product_id = models.CharField(max_length=128, null=True, blank=True)
    # Optional UUID the client may attach at purchase time; lets an unmatched
    # notification be attributed to a user without a client round-trip.
    app_account_token = models.UUIDField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    # signedDate of the most recent payload applied. Apple does not guarantee
    # delivery order, so an older payload must never overwrite newer state.
    last_signed_date = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.original_transaction_id} ({self.product_id})'


class AppleNotification(models.Model):
    """An App Store Server Notification V2 we received, kept for idempotency.

    Apple retries a notification for up to three days, so the same
    notificationUUID arrives repeatedly. The unique constraint makes the webhook
    idempotent; the row also serves as an audit trail for notifications that
    arrived before their subscription was bound to a user.
    """

    id = models.BigAutoField(primary_key=True)
    notification_uuid = models.CharField(max_length=64, unique=True, db_index=True)
    notification_type = models.CharField(max_length=64)
    subtype = models.CharField(max_length=64, null=True, blank=True)
    original_transaction_id = models.CharField(max_length=64, null=True, blank=True, db_index=True)
    signed_date = models.DateTimeField(null=True, blank=True)
    environment = models.CharField(max_length=16, blank=True, default='')
    processed = models.BooleanField(default=False)
    error = models.TextField(blank=True, default='')
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-received_at']

    def __str__(self):
        return f'{self.notification_type} {self.notification_uuid}'


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
    web_searches = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=['session', 'created_at'])]


class ApiUsageEvent(models.Model):
    """AI API usage that isn't captured on ChatMessage (summaries, prediction
    feature extraction, RAG helper calls, embeddings). One row per API call
    (or one aggregated row per batch for embeddings)."""
    class Service(models.IntegerChoices):
        CLAUDE = 0, 'Claude'
        VOYAGE = 1, 'Voyage'

    id = models.BigAutoField(primary_key=True)
    service = models.SmallIntegerField(choices=Service)
    # e.g. 'summary', 'prediction', 'chat_helper', 'rag_helper', 'indexing', 'retrieval'
    purpose = models.CharField(max_length=32)
    input_tokens = models.IntegerField(default=0)
    output_tokens = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        indexes = [models.Index(fields=['service', 'created_at'])]

    def estimated_cost(self) -> float:
        if self.service == self.Service.VOYAGE:
            return self.input_tokens * VOYAGE_COST_PER_TOKEN
        return (self.input_tokens * HAIKU_INPUT_COST_PER_TOKEN
                + self.output_tokens * HAIKU_OUTPUT_COST_PER_TOKEN)


class InfrastructureCost(models.Model):
    """Manually entered fixed monthly costs (hosting, DB, domains, ...) so the
    dashboard can show true net margin. Enter via Django admin; `month` should
    be the first day of the month the cost applies to."""
    id = models.BigAutoField(primary_key=True)
    month = models.DateField(db_index=True)
    name = models.CharField(max_length=100)
    amount_usd = models.DecimalField(max_digits=8, decimal_places=2)

    class Meta:
        unique_together = [('month', 'name')]

    def __str__(self):
        return f"{self.month:%Y-%m} {self.name}: ${self.amount_usd}"


DOC_TYPES = {0:'bill_text', 1:'cost_estimate', 2:'action_history'}
class BillChunk(models.Model):
    id = models.BigAutoField(primary_key=True)
    document_type = models.SmallIntegerField(default=0)
    bill_id = models.IntegerField(db_index=True)
    chunk_index = models.IntegerField()
    content = models.TextField()
    embedding = VectorField(dimensions=1024)
    def get_doc_type(self):
        return DOC_TYPES[self.document_type]
    class Meta:
        unique_together = [('bill_id', 'document_type', 'chunk_index')]


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