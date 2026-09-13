with open("apps/api/src/rag_api/adapters/storage/image_store.py", "r") as f:
    text = f.read()

target = """        self.bucket = bucket
        existing = {b["Name"] for b in self._client.list_buckets().get("Buckets", [])}
        if bucket not in existing:
            self._client.create_bucket(Bucket=bucket)"""

replacement = """        self.bucket = bucket
        self._bucket_created = False
        
    def _ensure_bucket(self):
        if not self._bucket_created:
            try:
                existing = {b["Name"] for b in self._client.list_buckets().get("Buckets", [])}
                if self.bucket not in existing:
                    self._client.create_bucket(Bucket=self.bucket)
                self._bucket_created = True
            except Exception:
                pass"""

text = text.replace(target, replacement)

target2 = """    def put(self, image_bytes: bytes, content_type: str) -> str:"""
replacement2 = """    def put(self, image_bytes: bytes, content_type: str) -> str:
        self._ensure_bucket()"""
text = text.replace(target2, replacement2)

with open("apps/api/src/rag_api/adapters/storage/image_store.py", "w") as f:
    f.write(text)

