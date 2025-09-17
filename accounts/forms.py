# accounts/forms.py
from django import forms
from django.contrib.auth.models import User
from .models import Profile

# accounts/forms.py
from django import forms
from django.contrib.auth.models import User
from .models import Profile

class UserEditForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["username", "first_name", "email", "is_staff"]
        labels = {"username": "아이디", "first_name": "이름", "email": "이메일", "is_staff": "스태프 여부"}
        widgets = {
            "username": forms.TextInput(attrs={"class": "inp"}),
            "first_name": forms.TextInput(attrs={"class": "inp"}),
            "email": forms.EmailInput(attrs={"class": "inp"}),
            "is_staff": forms.CheckboxInput(),  # 체크박스로 표시 권장
        }

class ProfileEditForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ["department", "role", "access"]
        labels = {"department": "부서", "role": "직책", "access": "권한"}
        # 👇 widgets 제거(혹은 Select로 명시)
        # widgets = {
        #     "department": forms.Select(attrs={"class": "inp"}),
        #     "role": forms.Select(attrs={"class": "inp"}),
        #     "access": forms.Select(attrs={"class": "inp"}),
        # }
