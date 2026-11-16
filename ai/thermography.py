"""Conservative intake adapter: displays user thermal imagery; never estimates core temp."""
from pathlib import Path

ALLOWED_IMAGE_TYPES = {".png", ".jpg", ".jpeg", ".tif", ".tiff"}


def analyze_thermal_image(image: bytes, filename: str) -> dict:
    if not isinstance(image, bytes) or not image:
        raise ValueError("A non-empty user-provided thermal image is required")
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_IMAGE_TYPES:
        raise ValueError("Unsupported image type")
    return {
        "status": "user_image_received",
        "filename": Path(filename).name,
        "size_bytes": len(image),
        "media_type": "image",
        "core_temperature_inferred": False,
        "notice": "No core-temperature estimate is produced. Thermal image values require calibrated device metadata and clinical interpretation.",
    }
