from rest_framework import serializers
from .models import Member, Membership, Congress

class MemberModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = Member
        fields = ['full_name', 'image_link', 'official_link', 'office', 'phone', 'birth_year', 'death_year']

class MembershipModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = Membership
        fields = ['id', 'district_num', 'house', 'state', 'party', 'start_date', 'end_date']

class MembershipSimpleModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = Membership
        fields = ['district_num', 'state', 'geoid', 'party', 'member']

class CongressModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = Congress
        fields = ['congress_num', 'end_year', 'start_year']