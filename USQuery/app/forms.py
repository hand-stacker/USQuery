import datetime
from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.db.models import Q
from django.utils.translation import gettext_lazy as _
from SenateQuery import models as SQmodels
from BillQuery import models as BQmodels

# ...
# when migrating to web, make sure to change this to link to STATE ID's rather than full name for efficiency
state_list = (
    ('All', 'All States'),
    ("AL", "Alabama"),
    ("AK", "Alaska"),
    ("AZ", "Arizona"),
    ("AR", "Arkansas"),
    ("CA", "California"),
    ("CO", "Colorado"),
    ("CT", "Connecticut"),
    ("DE", "Delaware"),
    ("FL", "Florida"),
    ("GA", "Georgia"),
    ("HI", "Hawaii"),
    ("ID", "Idaho"),
    ("IL", "Illinois"),
    ("IN", "Indiana"),
    ("IA", "Iowa"),
    ("KS", "Kansas"),
    ("KY", "Kentucky"),
    ("LA", "Louisiana"),
    ("ME", "Maine"),
    ("MD", "Maryland"),
    ("MA", "Massachusetts"),
    ("MI", "Michigan"),
    ("MN", "Minnesota"),
    ("MS", "Mississippi"),
    ("MO", "Missouri"),
    ("MT", "Montana"),
    ("NE", "Nebraska"),
    ("NV", "Nevada"),
    ("NH", "New Hampshire"),
    ("NJ", "New Jersey"),
    ("NM", "New Mexico"),
    ("NY", "New York"),
    ("NC", "North Carolina"),
    ("ND", "North Dakota"),
    ("OH", "Ohio"),
    ("OK", "Oklahoma"),
    ("OR", "Oregon"),
    ("PA", "Pennsylvania"),
    ("RI", "Rhode Island"),
    ("SC", "South Carolina"),
    ("SD", "South Dakota"),
    ("TN", "Tennessee"),
    ("TX", "Texas"),
    ("UT", "Utah"),
    ("VT", "Vermont"),
    ("VA", "Virginia"),
    ("WA", "Washington"),
    ("WV", "West Virginia"),
    ("WI", "Wisconsin"),
    ("WY", "Wyoming"))
 
chamber_list = (('Senate', 'Senate'),('House of Representatives', 'House'))
chamber_list2 = (('!','All'),('Senate', 'Senate'),('House of Representatives', 'House'))
type_list = (('!','All'),('!H','All House'),('!S','All Senate'),('hr', 'H. R.'),('hres', 'H. Res.'),('hjres', 'H. J. Res.'),('hconres','H. Con. Res.'),
             ('s','S.'),('sres','S. Res.'),('sjres', 'S. J. Res.'), ('sconres', 'S. Con. Res.'))

classic_form = {"class": "dark-01 overflow-scroll rounded-3 mb-3","style" : "max-width:240px;"}
classic_form_lg = {"class": "dark-select-lg overflow-scroll rounded-3"}

date_widget = {'type': 'date', "class": "dark-01 rounded-3 mb-3"}

# Sits inline in the sort row rather than stacked in a form-group, so no bottom margin.
classic_form_inline = {"class": "dark-01 rounded-3", "style": "max-width:190px;"}

sort_list = (('relevance', 'Relevance'), ('datedesc', 'Newest first'))

# Passed as callables so the defaults track the actual current date - a string
# built at import time freezes "today" for the lifetime of the worker process.
def _today():
    return datetime.date.today()

def _a_year_ago():
    return datetime.date.today() - datetime.timedelta(days=365)

class DateRangeMixin(object):
    """Validation for the paired start_date / end_date fields.

    Lives on the form rather than in the view because a hand-built query string
    reaches the view without ever passing through the date pickers, and a
    backwards window matches nothing rather than failing loudly - which reads as
    the search being broken.
    """
    def clean(self):
        cleaned = super().clean()
        start = cleaned.get("start_date")
        end = cleaned.get("end_date")
        if start and end and start > end:
            self.add_error("end_date", "End date cannot be earlier than the start date.")
        return cleaned

class BootstrapAuthenticationForm(AuthenticationForm):
    """Authentication form which uses boostrap CSS."""
    username = forms.CharField(max_length=254,
                               widget=forms.TextInput({
                                   'class': 'form-control',
                                   'placeholder': 'Email address'}))
    password = forms.CharField(label=_("Password"),
                               widget=forms.PasswordInput({
                                   'class': 'form-control',
                                   'placeholder':'Password'}))
    
class MemberForm(forms.Form):
    congress = forms.ModelChoiceField(
        queryset=SQmodels.Congress.objects.all(),
        empty_label="Select a Congress"
        )
    
    chamber = forms.ChoiceField(
        choices = chamber_list)

    state = forms.ChoiceField(
        choices=state_list,
        required=False
        )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["congress"].widget.attrs.update(classic_form_lg)
        self.fields["chamber"].widget.attrs.update(classic_form_lg)
        self.fields["state"].widget.attrs.update(classic_form_lg)
        congress_119 = SQmodels.Congress.objects.get(congress_num=119)
        self.fields["congress"].initial = congress_119
        # Set default congress to 119 if no congress is provided in the data
        if not self.data or 'congress' not in self.data:
            try:
                congress_119 = SQmodels.Congress.objects.get(congress_num=119)
                self.fields["congress"].initial = congress_119
            except SQmodels.Congress.DoesNotExist:
                pass
   
class BillForm(DateRangeMixin, forms.Form):
    bill_type = forms.ChoiceField(
        choices = type_list
        )
    start_date = forms.DateField(
        initial = _a_year_ago,
        widget=forms.DateInput(attrs=date_widget)
        )
    end_date = forms.DateField(
        initial = _today,
        widget=forms.DateInput(attrs=date_widget)
        )
    bill_subjects = forms.ModelMultipleChoiceField(
        queryset=BQmodels.Subject.objects.filter(subtype=0),
        widget=forms.SelectMultiple,
        required=False)
    bill_geo_entities = forms.ModelMultipleChoiceField(
        queryset=BQmodels.Subject.objects.filter(subtype=1),
        widget=forms.SelectMultiple,
        required=False)
    bill_organizations = forms.ModelMultipleChoiceField(
        queryset=BQmodels.Subject.objects.filter(subtype=2),
        widget=forms.SelectMultiple,
        required=False)
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["bill_type"].widget.attrs.update(classic_form)
        self.fields["bill_subjects"].widget.attrs.update(classic_form)
        self.fields["bill_geo_entities"].widget.attrs.update(classic_form)
        self.fields["bill_organizations"].widget.attrs.update(classic_form)

class BillKeywordForm(DateRangeMixin, forms.Form):
    bill_keyword = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'e.g. climate change, or HR 1234'})
        )
    bill_type = forms.ChoiceField(
        choices = type_list,
        required=False
        )
    # Dates are optional: left blank the view falls back to the current Congress.
    # No initial value for the same reason - a prefilled date is not an optional one.
    start_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs=date_widget)
        )
    end_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs=date_widget)
        )
    sorttype = forms.ChoiceField(
        choices = sort_list,
        required=False
        )
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["bill_type"].widget.attrs.update(classic_form)
        self.fields["bill_keyword"].widget.attrs.update(classic_form_lg)
        self.fields["sorttype"].widget.attrs.update(classic_form_inline)

class VoteForm(DateRangeMixin, forms.Form):
    bill_type = forms.ChoiceField(
        choices = (('!', 'All'),('h', 'House'),('s', 'Senate')),
        )
    start_date = forms.DateField(
        initial = _a_year_ago,
        widget=forms.DateInput(attrs=date_widget)
        )
    end_date = forms.DateField(
        initial = _today,
        widget=forms.DateInput(attrs=date_widget)
        )

    # technically votes do not have their own subjects
    # so we filter based on related bill's subjects
    bill_subjects = forms.ModelMultipleChoiceField(
        queryset=BQmodels.Subject.objects.filter(subtype=0),
        widget=forms.SelectMultiple,
        required=False)
    bill_geo_entities = forms.ModelMultipleChoiceField(
        queryset=BQmodels.Subject.objects.filter(subtype=1),
        widget=forms.SelectMultiple,
        required=False)
    bill_organizations = forms.ModelMultipleChoiceField(
        queryset=BQmodels.Subject.objects.filter(subtype=2),
        widget=forms.SelectMultiple,
        required=False)
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["bill_type"].widget.attrs.update(classic_form)
        self.fields["bill_subjects"].widget.attrs.update(classic_form)
        self.fields["bill_geo_entities"].widget.attrs.update(classic_form)
        self.fields["bill_organizations"].widget.attrs.update(classic_form)

class VoteKeywordForm(DateRangeMixin, forms.Form):
    vote_keyword = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'e.g. nomination, or HR 1234'})
        )
    bill_type = forms.ChoiceField(
        choices = (('!', 'All'),('h', 'House'),('s', 'Senate')),
        required=False
        )
    # Dates are optional: left blank the view falls back to the current Congress.
    start_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs=date_widget)
        )
    end_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs=date_widget)
        )
    sorttype = forms.ChoiceField(
        choices = sort_list,
        required=False
        )
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["bill_type"].widget.attrs.update(classic_form)
        self.fields["vote_keyword"].widget.attrs.update(classic_form_lg)
        self.fields["sorttype"].widget.attrs.update(classic_form_inline)

class RegisterForm(UserCreationForm):
    email = forms.EmailField()
    email2 = forms.EmailField(label="Confirm email")

    class Meta:
        model = User
        fields = ("email", "password1", "password2")

    def clean(self):
        cleaned = super().clean()
        # Emails are stored lowercased so web and mobile logins agree.
        email = (cleaned.get("email") or "").lower()
        email2 = (cleaned.get("email2") or "").lower()
        cleaned["email"] = email

        if email and email2 and email != email2:
            raise forms.ValidationError("Emails do not match")

        if email and User.objects.filter(Q(email__iexact=email) | Q(username__iexact=email)).exists():
            raise forms.ValidationError("Email already registered")

        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = self.cleaned_data["email"]
        user.email = self.cleaned_data["email"]
        user.is_active = False  # must verify email first

        if commit:
            user.save()

        return user

class VerificationForm(forms.Form):
    code = forms.UUIDField(
        label="Verification code",
        help_text="Enter the code sent to your email",
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "e.g. 9b6p8op6c-5c74-4c7e-a9e3-8aefb5a94fcb",
            }
        ),
    )
