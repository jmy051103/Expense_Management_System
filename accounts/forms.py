from django import forms
from django.contrib.auth.models import User
from .models import Profile

class UserEditForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["username", "first_name", "email", "is_staff"]
        labels = {
            "username": "아이디",
            "first_name": "이름",
            "email": "이메일",
            "is_staff": "스태프 여부",
        }
        widgets = {
            "username": forms.TextInput(attrs={"class": "inp", "placeholder": "아이디"}),
            "first_name": forms.TextInput(attrs={"class": "inp", "placeholder": "이름"}),
            "email": forms.EmailInput(attrs={"class": "inp", "placeholder": "이메일"}),
        }

class ProfileEditForm(forms.ModelForm):
    department = forms.ChoiceField(
        choices=[("", "부서 선택")] + Profile.DEPT_CHOICES,
        required=True
    )
    role = forms.ChoiceField(
        choices=[("", "직책 선택")] + Profile.ROLE_CHOICES,
        required=True
    )
    access = forms.ChoiceField(
        choices=[("", "권한 선택")] + Profile.ACCESS_CHOICES,
        required=True
    )

    class Meta:
        model = Profile
        fields = ["department", "role", "access"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ("department", "role", "access"):
            self.fields[name].widget.attrs.update({"class": "inp"})