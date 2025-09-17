from django.db import models
from django.contrib.auth.models import User

class Profile(models.Model):
    ROLE_CHOICES = [("대표이사", "대표이사"), ("실장", "실장"), ("부장", "부장"), ("과장", "과장"), ("대리", "대리"), ("주임", "주임"), ("사원", "사원"), ("차장", "차장")]
    DEPT_CHOICES = [("연구개발전담부(디자인팀)", "연구개발전담부(디자인팀)"), ("MD팀(제품기획및개발)", "MD팀(제품기획및개발)"), ("영업팀", "영업팀"), ("회계팀", "회계팀"), ("물류팀", "물류팀")]
    ACCESS_CHOICES = [("관리자모드", "관리자모드"), ("사장모드", "사장모드"), ("직원모드", "직원모드"), ("실장모드", "실장모드")]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    department = models.CharField(max_length=20, choices=DEPT_CHOICES)
    access = models.CharField(max_length=20, choices=ACCESS_CHOICES)

    def __str__(self):
        return f"{self.user.username} / {self.role} / {self.department}"
