from rest_framework import serializers
from .models import Member, Membership, Congress

class MemberModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = Member
        fields = '__all__'

class MembershipModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = Membership
        fields = '__all__'


class CongressModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = Congress
        fields = ['congress_num', 'end_year', 'start_year']