from io import BytesIO
from pathlib import Path
import warnings
from PIL import Image, ImageOps, UnidentifiedImageError
from fastapi import HTTPException

FORMATS = {"JPEG", "PNG", "WEBP"}

def decode_image(raw: bytes, max_pixels: int) -> Image.Image:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(raw)) as original:
                if original.format not in FORMATS:
                    raise HTTPException(415, "Use uma imagem JPG, PNG ou WEBP.")
                if original.width*original.height > max_pixels or getattr(original,"n_frames",1)>1:
                    raise HTTPException(413, "Imagem grande demais ou animada.")
                original.load()
                return ImageOps.exif_transpose(original).convert("RGB")
    except HTTPException: raise
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise HTTPException(422, "O arquivo não contém uma imagem válida.")

def save_images(image: Image.Image, directory: Path):
    directory.mkdir(parents=True, exist_ok=False)
    # Re-encoding removes EXIF and avoids publishing user-supplied byte streams.
    image.save(directory / "source.jpg", "JPEG", quality=90)
    thumbnail=image.copy(); thumbnail.thumbnail((640,480))
    thumbnail.save(directory / "thumbnail.jpg", "JPEG", quality=85)
