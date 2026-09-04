import hashlib
from abc import ABC, abstractmethod
from pathlib import Path

class ImageStore(ABC):
    @abstractmethod
    def put(self, image_bytes: bytes, content_type: str) -> str:
        pass
    @abstractmethod
    def get(self, image_hash: str) -> tuple[bytes, str] | None:
        pass
    @abstractmethod
    def url_for(self, image_hash: str) -> str:
        pass

class LocalImageStore(ImageStore):
    def __init__(self, base_dir: str | Path):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._meta_dir = self.base_dir / "meta"
        self._meta_dir.mkdir(exist_ok=True)

    def put(self, image_bytes: bytes, content_type: str) -> str:
        image_hash = hashlib.sha256(image_bytes).hexdigest()
        filepath = self.base_dir / image_hash
        metapath = self._meta_dir / f"{image_hash}.meta"
        
        if not filepath.exists():
            filepath.write_bytes(image_bytes)
            metapath.write_text(content_type)
            
        return image_hash

    def get(self, image_hash: str) -> tuple[bytes, str] | None:
        filepath = self.base_dir / image_hash
        metapath = self._meta_dir / f"{image_hash}.meta"
        if not filepath.exists() or not metapath.exists():
            return None
        return filepath.read_bytes(), metapath.read_text().strip()

    def url_for(self, image_hash: str) -> str:
        return f"/v1/images/{image_hash}"

def build_image_store(backend: str, **kwargs) -> ImageStore:
    if backend == "local":
        return LocalImageStore(base_dir=kwargs.get("base_dir", "./data/images"))
    if backend == "s3":
        raise NotImplementedError("S3 image store is not yet implemented.")
    raise ValueError(f"Unknown image store backend: {backend}")
