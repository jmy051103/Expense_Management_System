# expenses/signals.py
import io, os
from PIL import Image, ImageOps
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from .models import ContractImage

# ---------- 공통 유틸 ----------
def _delete_storage_file(name: str):
    """스토리지(S3 등)에서 안전하게 삭제"""
    if not name:
        return
    try:
        if default_storage.exists(name):
            default_storage.delete(name)
    except Exception as e:
        # 로깅만 하고 무시(실패해도 트랜잭션 막지 않음)
        print(f"[WARN] storage delete failed: {name} ({e})")

def _resize_to_jpeg(file, max_side):
    img = Image.open(file)
    img = ImageOps.exif_transpose(img)  # 회전 보정
    img = img.convert("RGB")
    img.thumbnail((max_side, max_side))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=82, optimize=True)
    return ContentFile(buf.getvalue())

def _derive_names_from_original(orig_name: str):
    """
    원본 경로 -> 파생 경로 생성
    ex) contracts/orig/2025/10/09/abc.png
      -> contracts/thumb/2025/10/09/abc_240.jpg
      -> contracts/medium/2025/10/09/abc_1200.jpg
    """
    if not orig_name:
        return None, None
    # 확장자 제거
    base, _ext = os.path.splitext(orig_name)
    thumb = base.replace("/orig/", "/thumb/") + "_240.jpg"
    medium = base.replace("/orig/", "/medium/") + "_1200.jpg"
    return thumb, medium


# ---------- 파생본 생성 ----------
@receiver(post_save, sender=ContractImage)
def make_derivatives(sender, instance: ContractImage, created, **kwargs):
    if not created or not instance.original:
        return

    # 파생 경로 계산
    thumb_name, medium_name = _derive_names_from_original(instance.original.name)

    # 저장 (upload_to 가 붙은 '절대 경로'로 저장하므로 name 인자로 경로를 넘겨도 OK)
    instance.thumb.save(thumb_name,  _resize_to_jpeg(instance.original, 240),  save=False)
    instance.medium.save(medium_name, _resize_to_jpeg(instance.original, 1200), save=False)

    # 원본 파일명만 기록
    instance.filename = os.path.basename(instance.original.name)
    instance.save(update_fields=["thumb", "medium", "filename"])


# ---------- 원본/파생본 교체 시 이전 파일 정리 ----------
@receiver(pre_save, sender=ContractImage)
def cleanup_files_on_replace(sender, instance: ContractImage, **kwargs):
    if not instance.pk:
        return  # 새 객체

    try:
        old = ContractImage.objects.get(pk=instance.pk)
    except ContractImage.DoesNotExist:
        return

    # 원본이 바뀌면 예전 파생본/원본 삭제
    if old.original and instance.original and old.original.name != instance.original.name:
        # 예전 파생 경로 계산 후 삭제
        old_thumb, old_medium = _derive_names_from_original(old.original.name)
        _delete_storage_file(old_thumb)
        _delete_storage_file(old_medium)
        _delete_storage_file(old.original.name)

    # 파생 필드가 수동 갱신되었을 때도 안전 삭제
    if old.thumb and instance.thumb and old.thumb.name != instance.thumb.name:
        _delete_storage_file(old.thumb.name)
    if old.medium and instance.medium and old.medium.name != instance.medium.name:
        _delete_storage_file(old.medium.name)


# ---------- 어떤 경로로든 객체가 삭제될 때 S3 파일도 삭제 ----------
@receiver(post_delete, sender=ContractImage)
def delete_files_with_record(sender, instance: ContractImage, **kwargs):
    _delete_storage_file(getattr(instance, "thumb", None) and instance.thumb.name)
    _delete_storage_file(getattr(instance, "medium", None) and instance.medium.name)
    _delete_storage_file(getattr(instance, "original", None) and instance.original.name)