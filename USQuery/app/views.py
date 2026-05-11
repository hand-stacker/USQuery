from datetime import datetime
from urllib import request
from django.core.cache import cache
from django.contrib import messages
from django.contrib.auth.models import User
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpRequest, HttpResponseRedirect, HttpResponse, HttpResponseForbidden, JsonResponse
from django.views.decorators.http import require_GET
from rest_framework.decorators import api_view
from rest_framework.views import Response
from SenateQuery.models import Congress, Membership
from BillQuery.models import Vote, Bill
from notifications.models import UserProfile
from strawberryAPI.graphql.utils import batch_load_summaries
from app import siteutils, utils
from app.forms import RegisterForm, VerificationForm
from app.models import EmailVerification
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth import login as django_login
from django.contrib.auth.views import LoginView
from django.views.decorators.http import require_POST

# New imports for account deletion management
from django.urls import reverse
from app.models import UserProfile as AppUserProfile

# OAuth helpers (shared with mobile via REST endpoints)
from google.oauth2 import id_token as google_id_token
from google.auth.transport import requests as google_requests
import jwt
import logging

logger = logging.getLogger(__name__)


def home(request):
    """Renders the home page."""
    assert isinstance(request, HttpRequest)
    try:
        congress = Congress.objects.get(congress_num = 119)
    except:
        return HttpResponseRedirect('/member-query')
    vote_list = Vote.objects.filter(congress = congress)[0:16].all()
    vote_table = utils.voteTablePage(vote_list)
    return render(
        request,
        'app/index.html',
        {
            'title':'Home Page',
            'vote_table' : vote_table,
        }
    )

def contact(request):
    """Renders the contact page.""" 
    assert isinstance(request, HttpRequest)
    return render(
        request,
        'app/contact.html',
        {
            'title':'Contact',
        }
    )

def about(request):
    """Renders the about page.""" 
    assert isinstance(request, HttpRequest)
    return render(
        request,
        'app/about.html',
        {
            'title':'About',
        }
    )

def my_congress_privacy_policy(request):
    """Renders the privacy policy page."""
    assert isinstance(request, HttpRequest)
    return render(
        request,
        'app/my_congress_privacy_policy.html',
        {
            'title': 'Privacy Policy',
        }
    )

class CustomLoginView(LoginView):
    """
    Subclass of Django's LoginView that, when the submitted credentials are correct
    but the user account is inactive (not yet verified), redirects to the verify-email page
    so the user can enter their verification code instead of just getting a login error.
    """
    def form_invalid(self, form):
        # Django authenticate() will return None for inactive users :/
        # To detect correct credentials for unactivated accounts,
        # fetch the user and use check_password() directly.
        username = form.data.get('username')
        password = form.data.get('password')
        if username and password:
            user = None
            try:
                user = User.objects.get(username=username)
            except User.DoesNotExist:
                try:
                    user = User.objects.get(email=username)
                except User.DoesNotExist:
                    user = None
            if user is not None and user.check_password(password) and not user.is_active:
                messages.info(self.request, "Account not verified. Enter your verification code.")
                return redirect('verify-email', email=user.email)

        return super().form_invalid(form)

def register(request):
    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.username = user.email
            user.is_active = False
            user.save()

            verification = EmailVerification.objects.create(user=user)
            send_mail(
                subject="Verify your USQuery account",
                message=(
                    "Thanks for registering with USQuery.\n\n"
                    f"Your verification code is:\n\n{verification.code}\n\n"
                    "This code will expire in 10 minutes."
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=False,
            )

            return redirect("verify-email", email=user.email)
    else:
        form = RegisterForm()

    return render(
        request,
        "app/register.html",
        {
            "form": form,
            "google_client_id": _get_google_web_client_id(),
            "apple_client_id": getattr(settings, "APPLE_CLIENT_ID", None),
        },
    )


def _get_google_web_client_id():
    """
    Client ID used by browser Google Sign-In.
    Prefer GOOGLE_WEB_CLIENT_ID, then fall back to GOOGLE_CLIENT_ID.
    """
    return (
        getattr(settings, "GOOGLE_WEB_CLIENT_ID", None)
        or getattr(settings, "GOOGLE_CLIENT_ID", None)
    )


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


@require_POST
def oauth_google_web(request):
    """
    Web-only endpoint: accepts a Google ID token, creates/links the user,
    and establishes a Django session (so templates see user.is_authenticated).
    """
    token = request.POST.get("id_token") or ""
    if not token:
        return JsonResponse({"detail": "Missing id_token."}, status=400)

    try:
        payload = _verify_google_id_token(token)
    except ValueError as exc:
        return JsonResponse({"detail": f"Invalid Google token: {exc}"}, status=400)

    provider_id = payload.get("sub")
    email = (payload.get("email") or "").lower()
    if not provider_id or not email:
        return JsonResponse({"detail": "Google token did not contain required fields."}, status=400)

    # reuse the same linking logic as the mobile/web API
    from app.api.views import _find_or_create_oauth_user

    user, _is_new = _find_or_create_oauth_user(AppUserProfile.OAuthProvider.GOOGLE, provider_id, email)
    django_login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    return JsonResponse({"detail": "ok", "redirect": "/"}, status=200)


@require_POST
def oauth_apple_web(request):
    """
    Web-only endpoint: accepts an Apple identity token (+ optional email),
    creates/links the user, and establishes a Django session.
    """
    try:
        return _oauth_apple_web_inner(request)
    except Exception as exc:
        logger.exception("Unhandled error in oauth_apple_web")
        return JsonResponse({"detail": f"Server error: {exc}"}, status=500)


def _oauth_apple_web_inner(request):
    token = request.POST.get("identity_token") or ""
    client_email = (request.POST.get("email") or "").lower()
    apple_client_id = getattr(settings, "APPLE_CLIENT_ID", None)
    if not apple_client_id:
        return JsonResponse({"detail": "Apple OAuth is not configured."}, status=503)
    if not token:
        return JsonResponse({"detail": "Missing identity_token."}, status=400)

    try:
        unverified_header = jwt.get_unverified_header(token)
    except jwt.exceptions.DecodeError as exc:
        return JsonResponse({"detail": f"Invalid Apple token: {exc}"}, status=400)

    kid = unverified_header.get("kid")
    if not kid:
        return JsonResponse({"detail": "Invalid Apple token header."}, status=400)

    from app.api.views import _get_apple_public_key, _find_or_create_oauth_user

    public_key = _get_apple_public_key(kid)
    if not public_key:
        return JsonResponse({"detail": "Unable to retrieve Apple public key."}, status=400)

    try:
        payload = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            audience=apple_client_id,
            issuer="https://appleid.apple.com",
        )
    except jwt.ExpiredSignatureError:
        return JsonResponse({"detail": "Apple token has expired."}, status=400)
    except jwt.InvalidTokenError as exc:
        return JsonResponse({"detail": f"Invalid Apple token: {exc}"}, status=400)

    provider_id = payload.get("sub")
    email = (payload.get("email") or "").lower() or client_email
    if not provider_id:
        return JsonResponse({"detail": "Apple token did not contain a subject."}, status=400)
    if not email:
        return JsonResponse({"detail": "Email is required for first-time Apple sign-in."}, status=400)

    user, _is_new = _find_or_create_oauth_user(AppUserProfile.OAuthProvider.APPLE, provider_id, email)
    django_login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    return JsonResponse({"detail": "ok", "redirect": "/"}, status=200)

def verify_email(request, email):
    user = get_object_or_404(User, username=email)
    verification = get_object_or_404(EmailVerification, user=user)

    if request.method == "POST":
        form = VerificationForm(request.POST)
        if form.is_valid():
            submitted_code = form.cleaned_data["code"]

            if verification.code == submitted_code and verification.is_valid():
                user.is_active = True
                user.save()
                verification.delete()
                user_profile, _ = UserProfile.objects.get_or_create(user=user)

                messages.success(
                    request,
                    "Your email has been verified. You may now log in."
                )
                return redirect("login")
            else:
                messages.error(
                    request,
                    "Invalid or expired verification code."
                )
    else:
        form = VerificationForm()

    return render(
        request,
        "app/verify_email.html",
        {"form": form, "email": user.email}
    )

def resend_verification(request, email):
    user = get_object_or_404(User, email=email)
    verification = get_object_or_404(EmailVerification, user=user)

    if user.is_active:
        return HttpResponseForbidden("Account already verified.")

    ip = utils.get_client_ip(request)
    cache_key = f"resend_ip:{ip}"
    attempts = cache.get(cache_key, 0)

    if attempts >= 5:
        messages.error(
            request,
            "Too many resend attempts from this IP. Please try again later."
        )
        return redirect("verify-email", email=user.email)

    if not verification.can_resend():
        messages.error(
            request,
            "Daily resend limit reached. Please try again tomorrow."
        )
        return redirect("verify-email", email=user.email)

    cache.set(cache_key, attempts + 1, timeout=3600)

    verification.resend()

    send_mail(
        subject="Your new USQuery verification code",
        message=(
            "Here is your new verification code:\n\n"
            f"{verification.code}\n\n"
            "This code expires in 10 minutes."
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=False,
    )

    messages.success(
        request,
        "A new verification code has been sent to your email."
    )
    return redirect("verify-email", email=user.email)

@staff_member_required
def updateJSON(request, congress_id) : 
    assert isinstance(request, HttpRequest)
    siteutils.modifyCountyGeoJSON(congress_id)
    return HttpResponseRedirect("/")

@staff_member_required
def updateSTATES(request) : 
    assert isinstance(request, HttpRequest)
    siteutils.modifyStateGeoJSON()
    return HttpResponseRedirect("/")

@require_GET
def robots_txt(request):
    content = """ 
User-agent: *
Disallow: /admin
Disallow: /admin/
Disallow: /admin*
Disallow: /admin/*
Disallow: /login
Disallow: /login/
Disallow: /login*
Disallow: /login/*
Disallow: /logout
Disallow: /logout*
Disallow: /logout/
Disallow: /logout/*
Disallow: /member-query/update-mems
Disallow: /member-query/update-mems/
Disallow: /member-query/update-mems*
Disallow: /member-query/update-mems/*
Disallow: /bill-query/prediction-request
Disallow: /bill-query/prediction-request/
Disallow: /bill-query/prediction-request*
Disallow: /bill-query/prediction-request/*

Crawl-delay: 10
    """
    return HttpResponse(content, content_type="text/plain")


# Page and toggle for scheduling/unscheduling account deletion.
# If user is not authenticated the page shows a button linking to login.
def manage_account_deletion(request):
    """
    GET: show explanation and a single button that schedules or unschedules deletion.
    POST: performs schedule/unschedule and redirects back. POST from anonymous users
    redirects to login.
    """
    if not request.user.is_authenticated:
        # POSTs from anonymous users should go to login with next
        if request.method == "POST":
            return redirect(f"{reverse('login')}?next={request.path}")
        # Render page for anonymous users; template will show a login link
        return render(request, "app/account_delete.html", {"profile": None})

    profile, _ = AppUserProfile.objects.get_or_create(user=request.user)

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "schedule" and not profile.scheduled_for_deletion:
            profile.scheduled_for_deletion = True
            profile.save(update_fields=["scheduled_for_deletion"])
            messages.success(request, "Your account has been scheduled for deletion.")
        elif action == "unschedule" and profile.scheduled_for_deletion:
            profile.scheduled_for_deletion = False
            profile.save(update_fields=["scheduled_for_deletion"])
            messages.success(request, "Account deletion has been cancelled.")
        else:
            messages.info(request, "No change was made.")
        return redirect("account-delete")

    return render(request, "app/account_delete.html", {"profile": profile})

# shows account details (subscrition type and limits)
@api_view(['GET'])
def view_details(request):
    user_profile, created = UserProfile.objects.get_or_create(user=request.user)
    user_type = user_profile.user_type
    device_limit = user_profile.get_device_limit()
    bill_limit = user_profile.get_starred_bills_limit()
    member_limit = user_profile.get_starred_memberships_limit()

    return Response({"user_type": user_type, "device_limit" : device_limit, "bill_limit" : bill_limit, "member_limit" : member_limit}, status=202)

def starred(request):
    """Renders the starred bills and members page with JSON data."""
    assert isinstance(request, HttpRequest)
    if not request.user.is_authenticated:
        return HttpResponseForbidden("Authentication required.")

    user_profile = UserProfile.objects.get(user=request.user)
    
    # Get starred bills
    sb_qs = user_profile.get_starred_bills()
    raw_ids = list(sb_qs.values_list("bill_id", flat=True))
    starred_bill_ids = []
    for _id in raw_ids:
        try:
            starred_bill_ids.append(int(_id))
        except Exception:
            continue

    # Get starred memberships
    sm_qs = user_profile.get_starred_memberships()
    raw_mem_ids = list(sm_qs.values_list("membership_id", flat=True))

    # Fetch full bill objects
    bills_qs = Bill.type_objects.filter(id__in=starred_bill_ids).order_by("-latest_action", "-id")
    bills = list(bills_qs)
    
    # Get summaries for bills - batch_load_summaries is async, so we need to run it
    import asyncio
    summaries = asyncio.run(batch_load_summaries(bills, True))
    
    # Serialize bills
    bills_data = []
    for bill in bills:
        s = summaries.get(bill.id)
        summary_text = s["summary"] if s else ""
        bills_data.append({
            "bill_id": bill.id,
            "title": bill.title,
            "latest_action": bill.latest_action.isoformat() if bill.latest_action else "",
            "summary": summary_text,
        })
    
    # Fetch full membership objects
    memberships_qs = Membership.objects.filter(id__in=raw_mem_ids).select_related("member")
    memberships = list(memberships_qs)
    
    # Serialize memberships
    members_data = []
    for membership in memberships:
        members_data.append({
            "membership_id": membership.id,
            "member_id": membership.member.id,
            "name": membership.member.full_name,
            "image_link": membership.member.image_link or "",
            "state": membership.state,
            "party": membership.party,
            "district_num": membership.district_num,
            "house": membership.house,
            "is_active": not membership.end_date,
        })

    return render(
        request,
        'app/starred.html',
        {
            'title': 'My Starred',
            'year': datetime.now().year,
            'bills_json': bills_data,
            'members_json': members_data,
        }
    )