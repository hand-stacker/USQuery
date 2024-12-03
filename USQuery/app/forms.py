"""
Definition of forms.
"""

from encodings import search_function
from re import search
from django import forms
from django_select2 import forms as s2forms
from django.contrib.auth.forms import AuthenticationForm
from django.utils.translation import gettext_lazy as _
from SenateQuery import models as SQmodels

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

class SenatorForm(forms.Form):
    congress_sen = forms.ModelChoiceField(
        queryset=SQmodels.Congress.objects.all(),
        empty_label="Select a Congress"
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
    
class RepresentativeForm(forms.Form):
    congress_rep = forms.ModelChoiceField(
        queryset=SQmodels.Congress.objects.all(),
        empty_label="Select a Congress"
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