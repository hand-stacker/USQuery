from datetime import datetime
from urllib import request
from django.core.cache import cache
from django.contrib import messages
from django.contrib.auth.models import User
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpRequest, HttpResponseRedirect, HttpResponse, HttpResponseForbidden
from django.views.decorators.http import require_GET
from SenateQuery.models import Congress
from BillQuery.models import Vote
from app import siteutils, utils
from app.forms import RegisterForm, VerificationForm
from app.models import EmailVerification
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.views import LoginView


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

    return render(request, "app/register.html", {"form": form})

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
Disallow: /bill-query/bill
Disallow: /bill-query/bill/
Disallow: /bill-query/bill*
Disallow: /bill-query/bill/*
Disallow: /bill-query/vote
Disallow: /bill-query/vote/
Disallow: /bill-query/vote*
Disallow: /bill-query/vote/*
Allow: /bill-query/bill/119
Allow: /bill-query/bill/119/
Allow: /bill-query/bill/119*
Allow: /bill-query/bill/119/*
Allow: /bill-query/vote/119*

Crawl-delay: 10
    """
    return HttpResponse(content, content_type="text/plain")
