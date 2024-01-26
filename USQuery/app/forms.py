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
    congress = forms.ModelChoiceField(
        queryset=SQmodels.Congress.objects.all(),
        label="Congress:",
        #widget= s2forms.ModelSelect2Widget(model=SQmodels.Congress,
                                   #search_fields=['congress_num__icontains'],
                                   #)
    )
    senator = forms.ModelChoiceField(
        queryset=SQmodels.Congress.objects.get(congress_num__exact=117).senators,
        label="Senator:",
        #widget=s2forms.ModelSelect2Widget(
            #model=SQmodels.Member,
            #search_fields = ['full_name_icontains'],
            #dependent_fields={'congress': 'congress'},
            #max_results=200, 
            #)
        )
    
class RepresentativeForm(forms.Form):
    congress = forms.ModelChoiceField(
        queryset=SQmodels.Congress.objects.all(),
        label="Congress:",
        #widget= s2forms.ModelSelect2Widget(model=SQmodels.Congress,
                           #        search_fields=['congress_num__icontains'],
                           #        )
    )
    representative = forms.ModelChoiceField(
        queryset=SQmodels.Congress.objects.get(congress_num__exact=117).representatives,
        label="Representative:",
        #widget=s2forms.ModelSelect2Widget(
          #  model=SQmodels.Senator,
           # search_fields = ['full_name_icontains'],
           # dependent_fields={'congress': 'congress'},
           # max_results=200, 
           # )
        )