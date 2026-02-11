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
from app.models import EmailVerification
from django.contrib.auth.views import PasswordResetView
from .serializers import RegisterSerializer, VerifySerializer, ResendSerializer, LoginSerializer
from django.http import JsonResponse



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