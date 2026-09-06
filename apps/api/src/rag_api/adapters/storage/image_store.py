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

import botocore.client

class S3ImageStore(ImageStore):
    def __init__(self, bucket: str, endpoint_url: str | None, access_key: str | None, secret_key: str | None):
        import boto3
        self._client = boto3.client(
            "s3", endpoint_url=endpoint_url,
            aws_access_key_id=access_key, aws_secret_access_key=secret_key, region_name="us-east-1",
            config=botocore.client.Config(s3={'addressing_style': 'path'}, signature_version='s3v4')
        )
        self.bucket = bucket
        existing = {b["Name"] for b in self._client.list_buckets().get("Buckets", [])}
        if bucket not in existing:
            self._client.create_bucket(Bucket=bucket)

    def put(self, image_bytes: bytes, content_type: str) -> str:
        import hashlib
        image_hash = hashlib.sha256(image_bytes).hexdigest()
        self._client.put_object(Bucket=self.bucket, Key=image_hash, Body=image_bytes, ContentType=content_type)
        return image_hash

    def get(self, image_hash: str) -> tuple[bytes, str] | None:
        try:
            obj = self._client.get_object(Bucket=self.bucket, Key=image_hash)
            return obj["Body"].read(), obj.get("ContentType", "application/octet-stream")
        except self._client.exceptions.NoSuchKey:
            return None

    def url_for(self, image_hash: str) -> str:
        return f"/v1/images/{image_hash}"

def build_image_store(backend: str, **kwargs) -> ImageStore:
    if backend == "local":
        return LocalImageStore(base_dir=kwargs.get("base_dir", "./data/images"))
    if backend == "s3":
        return S3ImageStore(
            bucket=kwargs.get("bucket", "images"),
            endpoint_url=kwargs.get("endpoint_url"),
            access_key=kwargs.get("access_key"),
            secret_key=kwargs.get("secret_key"),
        )
    raise ValueError(f"Unknown image store backend: {backend}")
