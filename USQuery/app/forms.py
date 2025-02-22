from django import forms
from django_select2 import forms as s2forms
from django.contrib.auth.forms import AuthenticationForm
from django.utils.translation import gettext_lazy as _
from SenateQuery import models as SQmodels

YEAR_CHOICES = ["2019", "2020", '2021', '2022', '2023', '2024', '2025']

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
class BootstrapAuthenticationForm(AuthenticationForm):
    """Authentication form which uses boostrap CSS."""
    username = forms.CharField(max_length=254,
                               widget=forms.TextInput({
                                   'class': 'form-control',
                                   'placeholder': 'User name'}))
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
        self.fields['member'].queryset = SQmodels.Member.objects.none()

        if 'congress' in self.data:
            congress_id = self.data.get('congress')
            is_house = self.data.get('chamber') != 'Senate'
            self.fields['congress'].queryset = SQmodels.Congress.objects.get(congress_num__exact=int(congress_id)).members.filter(membership__house = is_house)
            if 'state' in self.data:
                state = self.data.get('state')
                self.fields['member'].queryset = self.fields['member'].queryset.filter(membership__state = state)
   
class DateForm(forms.Form):
    start_date = forms.DateField(input_formats='%Y,%m,%d',widget=forms.SelectDateWidget(years=YEAR_CHOICES))
    end_date = forms.DateField(input_formats='%Y,%m,%d',widget=forms.SelectDateWidget(years=YEAR_CHOICES))

class CloroChoice(forms.Form): 
    cloro_choice = forms.ChoiceField(
        choices = CLORO_CHOICES
        )