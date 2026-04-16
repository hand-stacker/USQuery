from django.contrib.auth.models import User
from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password

class RegisterSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Email already registered")
        return value

    def validate_password(self, value):
        validate_password(value)
        return value

class VerifySerializer(serializers.Serializer):
    email = serializers.EmailField()
    code = serializers.CharField()

class ResendSerializer(serializers.Serializer):
    email = serializers.EmailField()

class LoginSerializer(serializers.Serializer):
    email = serializers.CharField()
    password = serializers.CharField(write_only=True)

class GoogleOAuthSerializer(serializers.Serializer):
    id_token = serializers.CharField()

class AppleOAuthSerializer(serializers.Serializer):
    identity_token = serializers.CharField()
    # Apple only sends email on the first sign-in; clients must cache and re-send it
    email = serializers.EmailField(required=False, allow_blank=True)