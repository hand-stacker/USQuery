from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _
from SenateQuery import models as SQmodels
from BillQuery import models as BQmodels

CLORO_CHOICES = ((1, 'YEA'), (0, 'NAY'), (2, 'PRES'), (3, 'NOVT'))

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

classic_form = {"class": "dark-01 overflow-scroll rounded-3","style" : "max-width:240px;"}
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

    member = forms.ModelChoiceField(
        queryset=SQmodels.Member.objects.none(),
        empty_label="Select a Member"
        )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["congress"].widget.attrs.update(classic_form)
        self.fields["chamber"].widget.attrs.update(classic_form)
        self.fields["state"].widget.attrs.update(classic_form)
        self.fields["member"].widget.attrs.update(classic_form)
   
class CloroChoice(forms.Form): 
    cloro_choice = forms.ChoiceField(
        choices = CLORO_CHOICES
        )
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["cloro_choice"].widget.attrs.update(classic_form)

class CalendarDateForm(forms.Form):
    bill_type = forms.ChoiceField(
        choices = type_list
        )
    start_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date',"class": "dark-01 rounded-3"}))
    end_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date',"class": "dark-01 rounded-3"}))
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["bill_type"].widget.attrs.update(classic_form)

class BillForm(forms.Form):
    congress = forms.ModelChoiceField(
        queryset=SQmodels.Congress.objects.all(),
        required=True,
        empty_label="Select a Congress"
        )
    bill_type_2 = forms.ChoiceField(
        choices = type_list,
        required=True
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
    bill_num = forms.ModelChoiceField(
        queryset=BQmodels.Bill.objects.none(),
        required=True
        )
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        super(BillForm, self).__init__(*args, **kwargs)
        self.fields["congress"].widget.attrs.update(classic_form)
        self.fields["bill_type_2"].widget.attrs.update(classic_form)
        self.fields["bill_num"].widget.attrs.update(classic_form)
        self.fields["bill_subjects"].widget.attrs.update(classic_form)
        self.fields["bill_geo_entities"].widget.attrs.update(classic_form)
        self.fields["bill_organizations"].widget.attrs.update(classic_form)


class VoteForm(forms.Form):
    bill_type = forms.ChoiceField(
        choices = (('!', 'All'),('h', 'House'),('s', 'Senate')),
        )
    start_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date',"class": "dark-01 rounded-3"}))
    end_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date',"class": "dark-01 rounded-3"}))
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["bill_type"].widget.attrs.update(classic_form)

class RegisterForm(UserCreationForm):
    email = forms.EmailField()
    email2 = forms.EmailField(label="Confirm email")

    class Meta:
        model = User
        fields = ("email", "password1", "password2")

    def clean(self):
        cleaned = super().clean()
        email = cleaned.get("email")
        email2 = cleaned.get("email2")

        if email and email2 and email != email2:
            raise forms.ValidationError("Emails do not match")

        if User.objects.filter(email=email).exists():
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
