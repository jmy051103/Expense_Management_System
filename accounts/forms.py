from django import forms
from django.contrib.auth.models import User
from .models import Profile

class UserEditForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["username", "first_name", "email"]  # is_staff는 화면에 안보여줌
        labels = {
            "username": "아이디",
            "first_name": "이름",
            "email": "이메일",
        }
        widgets = {
            "username": forms.TextInput(attrs={"class": "inp", "placeholder": "아이디"}),
            "first_name": forms.TextInput(attrs={"class": "inp", "placeholder": "이름"}),
            "email": forms.EmailInput(attrs={"class": "inp", "placeholder": "이메일"}),
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
            "department": forms.Select(attrs={"class": "inp", "aria-label": "부서 선택"}),
            "role": forms.Select(attrs={"class": "inp", "aria-label": "직책 선택"}),
            "access": forms.Select(attrs={"class": "inp", "aria-label": "권한 선택"}),
        }