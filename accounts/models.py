from django.db import models
from django.contrib.auth.models import User

class Profile(models.Model):
    ROLE_CHOICES = [("사장", "사장"), ("부장", "부장"), ("팀장", "팀장")]
    DEPT_CHOICES = [("홍보팀", "홍보팀"), ("기획팀", "기획팀"), ("회장단", "회장단")]
    ACCESS_CHOICES = [("관리자모드", "관리자모드"), ("사장모드", "사장모드"), ("직원모드", "직원모드")]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    department = models.CharField(max_length=20, choices=DEPT_CHOICES)
    access = models.CharField(max_length=20, choices=ACCESS_CHOICES)

    def __str__(self):
        return f"{self.user.username} / {self.role} / {self.department}"
