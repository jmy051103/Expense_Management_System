# accounts/forms.py
from django import forms
from django.contrib.auth.models import User
from .models import Profile

class UserEditForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["username", "first_name", "email", "is_active", "is_staff"]
        labels = {
            "username": "아이디",
            "first_name": "이름",
            "email": "이메일",
            "is_active": "활성",
            "is_staff": "스태프 여부",
        }
        widgets = {
            "username": forms.TextInput(attrs={"class": "inp"}),
            "first_name": forms.TextInput(attrs={"class": "inp"}),
            "email": forms.EmailInput(attrs={"class": "inp"}),
        }

class ProfileEditForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ["department", "role", "access"]
        labels = {
            "department": "부서",
            "role": "직책",
            "access": "권한",
        }
        widgets = {
            "department": forms.TextInput(attrs={"class": "inp"}),
            "role": forms.TextInput(attrs={"class": "inp"}),
            "access": forms.TextInput(attrs={"class": "inp"}),
        }