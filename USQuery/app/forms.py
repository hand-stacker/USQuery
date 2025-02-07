from random import choice
from app import utils
from encodings import search_function
from re import search
from django import forms
from django_select2 import forms as s2forms
from django.contrib.auth.forms import AuthenticationForm
from django.utils.translation import gettext_lazy as _
from SenateQuery import models as SQmodels

YEAR_CHOICES = ["2019", "2020"]

# ...
# when migrating to web, make sure to change this to link to STATE ID's rather than full name for efficiency
state_list = (('!', 'Any State'),('Alabama', 'Alabama'),('Alaska', 'Alaska'),('Arizona','Arizona'),('Arkansas', 'Arkansas'),('California','California'),('Colorado','Colorado'),
              ('Connecticut','Connecticut'),('Delaware','Delaware'),('Florida','Florida'),('Georgia','Georgia'),('Hawaii','Hawaii'),('Idaho','Idaho'),
              ('Indiana','Indiana'),('Illinois','Illinois'),('Iowa','Iowa'),('Kansas','Kansas'),('Kentucky','Kentucky'),('Louisiana','Louisiana'),
              ('Maine','Maine'),('Maryland','Maryland'),('Massachusetts','Massachusetts'),('Michigan','Michigan'),('Minnesota','Minnesota'),
              ('Mississippi','Mississippi'),('Missouri','Missouri'),('Montana','Montana'),('Nebraska','Nebraska'),('Nevada','Nevada'),
              ('New Hampshire','New Hampshire'),('New Jersey','New Jersey'),('New Mexico','New Mexico'),('New York','New York'),
              ('North Carolina','North Carolina'),('North Dakota','North Dakota'),('Ohio','Ohio'),('Oklahoma','Oklahoma'),('Oregon','Oregon'),
              ('Pennsylvania','Pennsylvania'),('Rhode Island','Rhode Island'),('South Carolina','South Carolina'),('South Dakota','South Dakota'),
              ('Tennessee','Tennessee'),('Texas','Texas'),('Utah','Utah'),('Vermont','Vermont'),('Virginia','Virginia'),('Washington','Washington'),
              ('West Virginia','West Virginia'),('Wisconsin','Wisconsin'),('Wyoming','Wyoming'))

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
    
class CongressForm(forms.Form):
    congress = forms.ModelChoiceField(
        queryset=SQmodels.Congress.objects.all(),
        empty_label="Select a Congress"        
        )
    
class SenatorForm(forms.Form):
    congress_sen = forms.ModelChoiceField(
        queryset=SQmodels.Congress.objects.all(),
        empty_label="Select a Congress"
        )
    
    state_sen = forms.ChoiceField(
        choices=state_list,
        required=False
        )
    
    senator = forms.ModelChoiceField(
        queryset=SQmodels.Member.objects.none(),
        empty_label="Select a Senator"
        )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['senator'].queryset = SQmodels.Member.objects.none()

        if 'congress_sen' in self.data:
            congress_id = self.data.get('congress_sen')
            self.fields['senator'].queryset = SQmodels.Congress.objects.get(congress_num__exact=int(congress_id)).members.filter(membership__chamber = 'Senate')
            if 'state_sen' in self.data:
                state = self.data.get('state_sen')
                self.fields['senator'].queryset = self.fields['senator'].queryset.filter(membership__state = state)
    
class RepresentativeForm(forms.Form):
    congress_rep = forms.ModelChoiceField(
        queryset=SQmodels.Congress.objects.all(),
        empty_label="Select a Congress"
        )
    
    state_rep = forms.ChoiceField(
        choices=state_list,
        required=False
        )

    representative = forms.ModelChoiceField(
        queryset=SQmodels.Member.objects.none(),
        empty_label="Select a Representative"
        )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['representative'].queryset = SQmodels.Member.objects.none()

        if 'congress_rep' in self.data:
            congress_id = self.data.get('congress_rep')
            self.fields['representative'].queryset = SQmodels.Congress.objects.get(congress_num__exact=int(congress_id)).members.filter(membership__chamber = 'House of Representatives')
            if 'state_rep' in self.data:
                state = self.data.get('state_rep')
                self.fields['representative'].queryset = self.fields['representative'].queryset.filter(membership__state = state)
            
class DateForm(forms.Form):
    start_date = forms.DateField(input_formats='%Y,%m,%d',widget=forms.SelectDateWidget(years=YEAR_CHOICES))
    end_date = forms.DateField(input_formats='%Y,%m,%d',widget=forms.SelectDateWidget(years=YEAR_CHOICES))