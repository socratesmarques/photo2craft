import base64
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
                normalized = ImageOps.exif_transpose(original)
                if normalized.mode in ("RGBA", "LA") or "transparency" in normalized.info:
                    rgba = normalized.convert("RGBA")
                    background = Image.new("RGBA", rgba.size, (255,255,255,255))
                    normalized = Image.alpha_composite(background, rgba)
                result = normalized.convert("RGB")
                result.info.clear()
                return result
    except HTTPException: raise
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise HTTPException(422, "O arquivo não contém uma imagem válida.")

def save_images(image: Image.Image, directory: Path):
    directory.mkdir(parents=True, exist_ok=False)
    # Re-encoding removes EXIF and avoids publishing user-supplied byte streams.
    image.save(directory / "source.png", "PNG", compress_level=3)
    thumbnail=image.copy(); thumbnail.thumbnail((640,480))
    thumbnail.save(directory / "thumbnail.jpg", "JPEG", quality=85)


def encode_reference(image: Image.Image, max_edge: int = 1280) -> str:
    """One lossless, bounded copy for vision; no upscaling or JPEG color bleeding."""
    small = image.copy()
    small.thumbnail((max_edge, max_edge), Image.Resampling.LANCZOS)
    output = BytesIO()
    small = small.convert("RGB")
    small.info.clear()
    small.save(output, "PNG", compress_level=3)
    return base64.b64encode(output.getvalue()).decode("ascii")
