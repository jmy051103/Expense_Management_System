# expenses/signals.py
import io
from PIL import Image, ImageOps
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.files.base import ContentFile
from .models import ContractImage

def _resize_to_jpeg(file, max_side):
    img = Image.open(file)
    img = ImageOps.exif_transpose(img)  # 회전 보정
    img = img.convert("RGB")
    img.thumbnail((max_side, max_side))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=82, optimize=True)
    return ContentFile(buf.getvalue())

@receiver(post_save, sender=ContractImage)
def make_derivatives(sender, instance: ContractImage, created, **kwargs):
    if not created or not instance.original:
        return
    base = instance.original.name.rsplit(".", 1)[0]
    # 240/1200 파생본 저장
    instance.thumb.save(base.replace("/orig/", "/thumb/") + "_240.jpg",  _resize_to_jpeg(instance.original, 240),  save=False)
    instance.medium.save(base.replace("/orig/", "/medium/") + "_1200.jpg", _resize_to_jpeg(instance.original, 1200), save=False)
    instance.filename = instance.original.name.split("/")[-1]
    instance.save(update_fields=["thumb", "medium", "filename"])