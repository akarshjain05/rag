import hashlib
from abc import ABC, abstractmethod
from pathlib import Path

class ImageStore(ABC):
    @abstractmethod
    def save_image(self, image_bytes: bytes, ext: str = ".png") -> str:
        """Saves image bytes and returns a URI or reference."""
        pass

class LocalImageStore(ImageStore):
    def __init__(self, base_dir: str | Path):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def save_image(self, image_bytes: bytes, ext: str = ".png") -> str:
        content_hash = hashlib.sha256(image_bytes).hexdigest()
        filename = f"{content_hash}{ext}"
        filepath = self.base_dir / filename
        
        if not filepath.exists():
            filepath.write_bytes(image_bytes)
            
        return f"local://{filename}"

def build_image_store(backend: str, **kwargs) -> ImageStore:
    if backend == "local":
        return LocalImageStore(base_dir=kwargs.get("base_dir", "/app/data/images"))
    if backend == "s3":
        raise NotImplementedError("S3 image store is not yet implemented.")
    raise ValueError(f"Unknown image store backend: {backend}")
