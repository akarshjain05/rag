import tempfile
from pathlib import Path
import boto3

import botocore.client

class ObjectStore:
    def __init__(self, endpoint_url: str, access_key: str, secret_key: str, bucket: str):
        self._client = boto3.client(
            "s3", endpoint_url=endpoint_url,
            aws_access_key_id=access_key, aws_secret_access_key=secret_key, region_name="us-east-1",
            config=botocore.client.Config(s3={'addressing_style': 'path'}, signature_version='s3v4')
        )

        self.bucket = bucket
        existing = {b["Name"] for b in self._client.list_buckets().get("Buckets", [])}
        if bucket not in existing:
            self._client.create_bucket(Bucket=bucket)

    def upload_fileobj(self, fileobj, key: str) -> None:
        self._client.upload_fileobj(fileobj, self.bucket, key)

    def download_to_tmp(self, key: str) -> Path:
        dest = Path(tempfile.mkdtemp(prefix="rag_stream_")) / Path(key).name
        self._client.download_file(self.bucket, key, str(dest))
        return dest
