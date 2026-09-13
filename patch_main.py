with open("apps/api/src/rag_api/main.py", "r") as f:
    text = f.read()

target = """    image_store_instance = build_image_store(
        settings.image_store_backend, 
        base_dir=settings.image_store_path,
        bucket=settings.object_store_bucket,
        endpoint_url=settings.object_store_endpoint,
        access_key=settings.object_store_access_key,
        secret_key=settings.object_store_secret_key
    )"""

replacement = """    image_store_instance = None
    if settings.image_indexing_enabled:
        image_store_instance = build_image_store(
            settings.image_store_backend, 
            base_dir=settings.image_store_path,
            bucket=settings.object_store_bucket,
            endpoint_url=settings.object_store_endpoint,
            access_key=settings.object_store_access_key,
            secret_key=settings.object_store_secret_key
        )"""

text = text.replace(target, replacement)
with open("apps/api/src/rag_api/main.py", "w") as f:
    f.write(text)

