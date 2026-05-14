from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.conf import settings
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from django.contrib.auth.forms import PasswordResetForm
from app.models import EmailVerification, UserProfile
from django.contrib.auth.views import PasswordResetView
from .serializers import RegisterSerializer, VerifySerializer, ResendSerializer, LoginSerializer, GoogleOAuthSerializer, AppleOAuthSerializer
from django.http import JsonResponse
from google.oauth2 import id_token as google_id_token
from google.auth.transport import requests as google_requests
import jwt
import json
import requests as http_requests


def _get_google_allowed_client_ids():
    """
    Prefer GOOGLE_CLIENT_IDS (comma-separated) when set,
    otherwise fall back to GOOGLE_CLIENT_ID.
    """
    multi = getattr(settings, "GOOGLE_CLIENT_IDS", None)
    if multi:
        ids = [s.strip() for s in str(multi).split(",") if s.strip()]
        if ids:
            return ids
    single = getattr(settings, "GOOGLE_CLIENT_ID", None)
    return [single] if single else []


def _verify_google_id_token(token: str):
    allowed = _get_google_allowed_client_ids()
    if not allowed:
        raise ValueError("Google OAuth is not configured.")

    last_exc = None
    for aud in allowed:
        try:
            return google_id_token.verify_oauth2_token(
                token,
                google_requests.Request(),
                aud,
            )
        except ValueError as exc:
            last_exc = exc
            continue
    raise ValueError(str(last_exc or "Invalid Google token"))



@api_view(['POST'])
@permission_classes([AllowAny])
def api_register(request):
    s = RegisterSerializer(data=request.data)
    s.is_valid(raise_exception=True)
    email = s.validated_data['email'].lower()
    password = s.validated_data['password']

    user = User.objects.create(username=email, email=email, is_active=False)
    user.set_password(password)
    user.save()

    verification = EmailVerification.objects.create(user=user)

    send_mail(
        subject="Verify your USQuery account",
        message=f"Your verification code is:\n\n{verification.code}\n\nThis code will expire in 10 minutes.",
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=False,
    )

    return Response({"status": "success", "email": user.email}, status=status.HTTP_201_CREATED)

@api_view(['POST'])
@permission_classes([AllowAny])
def api_verify_email(request):
    s = VerifySerializer(data=request.data)
    s.is_valid(raise_exception=True)
    email = s.validated_data['email'].lower()
    code = s.validated_data['code']

    user = get_object_or_404(User, email=email)
    verification = get_object_or_404(EmailVerification, user=user)

    # compare as text because model stores UUIDField
    if str(verification.code) == str(code) and verification.is_valid():
        user.is_active = True
        user.save()
        verification.delete()
        return Response({"detail": "Email verified."}, status=status.HTTP_200_OK)

    return Response({"detail": "Invalid or expired verification code."}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([AllowAny])
def api_resend_verification(request):
    s = ResendSerializer(data=request.data)
    s.is_valid(raise_exception=True)
    email = s.validated_data['email'].lower()

    user = get_object_or_404(User, email=email)
    if user.is_active:
        return Response({"detail": "Account already verified."}, status=status.HTTP_400_BAD_REQUEST)

    verification = get_object_or_404(EmailVerification, user=user)
    if not verification.can_resend():
        return Response({"detail": "Daily resend limit reached."}, status=status.HTTP_429_TOO_MANY_REQUESTS)

    verification.resend()

    send_mail(
        subject="Your new USQuery verification code",
        message=f"Here is your new verification code:\n\n{verification.code}\n\nThis code expires in 10 minutes.",
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=False,
    )

    return Response({"detail": "New code sent."}, status=status.HTTP_200_OK)

@api_view(['POST'])
@permission_classes([AllowAny])
def api_login(request):
    s = LoginSerializer(data=request.data)
    s.is_valid(raise_exception=True)
    username = s.validated_data['email'].lower()
    password = s.validated_data['password']

    # allow login by email or username (your web uses email as username)
    try:
        user = User.objects.get(username=username)
    except User.DoesNotExist:
        try:
            user = User.objects.get(email=username)
        except User.DoesNotExist:
            user = None

    if user is None or not user.check_password(password):
        return Response({"detail": "Invalid credentials."}, status=status.HTTP_401_UNAUTHORIZED)

    refresh = RefreshToken.for_user(user)
    return Response({
        "access": str(refresh.access_token),
        "refresh": str(refresh),
        "is_verified": user.is_active,
        "user_id": user.id,
        "email": user.email,
    }, status=status.HTTP_200_OK)

@api_view(['POST'])
@permission_classes([AllowAny])
def api_reset_password(request):
    email_template_name = "app/password_reset_email.txt"
    subject_template_name = "app/password_reset_subject.txt"
    email = request.data.get("email")
    form = PasswordResetForm(data={"email": email})
    if form.is_valid():
        form.save(
            request=request,
            use_https=True,
            subject_template_name=subject_template_name,
            email_template_name=email_template_name,
            from_email=settings.DEFAULT_FROM_EMAIL,
        )
    return Response(
        {"detail": "If the email exists, a reset link was sent."},
        status=status.HTTP_200_OK,
    )


def _issue_tokens(user):
    """Return a dict with JWT access/refresh tokens for the given user."""
    refresh = RefreshToken.for_user(user)
    return {
        "access": str(refresh.access_token),
        "refresh": str(refresh),
        "user_id": user.id,
        "email": user.email,
    }


def _activate_oauth_user(user):
    """Ensure an OAuth-authenticated user is active and has no pending email verification."""
    if not user.is_active:
        user.is_active = True
        user.save(update_fields=['is_active'])
    EmailVerification.objects.filter(user=user).delete()


def _find_or_create_oauth_user(provider, provider_id, email):
    """
    Resolve an OAuth identity to a Django User + UserProfile.

    Resolution order:
      1. Existing UserProfile with matching provider + provider_id  → return it
      2. Existing User with matching email                          → link OAuth to it
      3. No match                                                    → create new User + UserProfile

    Returns (user, is_new_user).
    """
    # 1. Already linked to this OAuth identity
    try:
        profile = UserProfile.objects.select_related('user').get(
            oauth_provider=provider,
            oauth_provider_id=provider_id,
        )
        user = profile.user
        _activate_oauth_user(user)
        return user, False
    except UserProfile.DoesNotExist:
        pass

    # 2. Email matches an existing account → link
    try:
        user = User.objects.get(email=email)
        profile = user.userprofile
        profile.oauth_provider = provider
        profile.oauth_provider_id = provider_id
        profile.save(update_fields=['oauth_provider', 'oauth_provider_id'])
        _activate_oauth_user(user)
        return user, False
    except User.DoesNotExist:
        pass

    # 3. Brand-new user
    user = User.objects.create(
        username=email,
        email=email,
        is_active=True,  # OAuth users are pre-verified by the provider
    )
    UserProfile.objects.create(
        user=user,
        user_type=UserProfile.SubType.Free,
        oauth_provider=provider,
        oauth_provider_id=provider_id,
    )
    return user, True


@api_view(['POST'])
@permission_classes([AllowAny])
def api_google_oauth(request):
    s = GoogleOAuthSerializer(data=request.data)
    s.is_valid(raise_exception=True)
    token = s.validated_data['id_token']

    try:
        payload = _verify_google_id_token(token)
    except ValueError as exc:
        return Response({"detail": f"Invalid Google token: {exc}"}, status=status.HTTP_400_BAD_REQUEST)

    provider_id = payload['sub']
    email = payload.get('email', '').lower()

    if not email:
        return Response({"detail": "Google token does not contain an email address."}, status=status.HTTP_400_BAD_REQUEST)

    user, is_new = _find_or_create_oauth_user(UserProfile.OAuthProvider.GOOGLE, provider_id, email)
    data = _issue_tokens(user)
    data['is_new_user'] = is_new
    return Response(data, status=status.HTTP_200_OK)


# Cache for Apple's public JWKS to avoid fetching on every request
_apple_jwks_cache = {}

def _get_apple_public_key(kid):
    """Fetch Apple's current JWKS and return the key matching `kid`."""
    if kid not in _apple_jwks_cache:
        resp = http_requests.get("https://appleid.apple.com/auth/keys", timeout=5)
        resp.raise_for_status()
        keys = resp.json().get('keys', [])
        _apple_jwks_cache.clear()
        for k in keys:
            _apple_jwks_cache[k['kid']] = jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(k))
    return _apple_jwks_cache.get(kid)


@api_view(['POST'])
@permission_classes([AllowAny])
def api_apple_oauth(request):
    s = AppleOAuthSerializer(data=request.data)
    s.is_valid(raise_exception=True)
    token = s.validated_data['identity_token']
    client_email = s.validated_data.get('email', '').lower()

    apple_client_id = getattr(settings, 'APPLE_CLIENT_ID', None)
    if not apple_client_id:
        return Response({"detail": "Apple OAuth is not configured."}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    apple_bundle_id = getattr(settings, 'APPLE_BUNDLE_ID', None)
    valid_audiences = [apple_client_id, apple_bundle_id] if apple_bundle_id else apple_client_id

    # Decode header to get kid without verifying signature yet
    try:
        unverified_header = jwt.get_unverified_header(token)
    except jwt.exceptions.DecodeError as exc:
        return Response({"detail": f"Invalid Apple token: {exc}"}, status=status.HTTP_400_BAD_REQUEST)

    kid = unverified_header.get('kid')
    public_key = _get_apple_public_key(kid)
    if not public_key:
        return Response({"detail": "Unable to retrieve Apple public key."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        payload = jwt.decode(
            token,
            public_key,
            algorithms=['RS256'],
            audience=valid_audiences,
            issuer='https://appleid.apple.com',
        )
    except jwt.ExpiredSignatureError:
        return Response({"detail": "Apple token has expired."}, status=status.HTTP_400_BAD_REQUEST)
    except jwt.InvalidTokenError as exc:
        return Response({"detail": f"Invalid Apple token: {exc}"}, status=status.HTTP_400_BAD_REQUEST)

    provider_id = payload['sub']
    # Apple only sends email on first sign-in; fall back to client-supplied value
    email = payload.get('email', '').lower() or client_email

    if not email:
        return Response({"detail": "Email is required for first-time Apple sign-in."}, status=status.HTTP_400_BAD_REQUEST)

    user, is_new = _find_or_create_oauth_user(UserProfile.OAuthProvider.APPLE, provider_id, email)
    data = _issue_tokens(user)
    data['is_new_user'] = is_new
    return Response(data, status=status.HTTP_200_OK)