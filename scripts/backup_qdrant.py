import os
import sys
import requests
from qdrant_client import QdrantClient
from pathlib import Path
import boto3

# Make sure we can import our API settings
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "apps" / "api" / "src"))
from rag_api.core.settings import get_settings

def backup_qdrant():
    settings = get_settings()
    collection_name = settings.collection_name
    
    # 1. Connect to Qdrant
    qdrant_url = f"http://{settings.qdrant_host}:{settings.qdrant_port}"
    print(f"Connecting to Qdrant at {qdrant_url}...")
    client = QdrantClient(url=qdrant_url)
    
    # 2. Trigger Snapshot
    print(f"Creating snapshot for collection: {collection_name}...")
    snapshot_info = client.create_snapshot(collection_name=collection_name)
    snapshot_name = snapshot_info.name
    print(f"Snapshot created successfully: {snapshot_name}")
    
    # 3. Download Snapshot locally to a tmp file
    download_url = f"{qdrant_url}/collections/{collection_name}/snapshots/{snapshot_name}"
    tmp_path = Path(f"/tmp/{snapshot_name}")
    print(f"Downloading snapshot from {download_url}...")
    
    with requests.get(download_url, stream=True) as r:
        r.raise_for_status()
        with open(tmp_path, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
                
    print(f"Downloaded snapshot to {tmp_path} ({tmp_path.stat().st_size} bytes)")
    
    # 4. Upload to MinIO
    bucket_name = settings.object_store_bucket or "rag-pipeline-ingest"
    object_key = f"qdrant-backups/{collection_name}/{snapshot_name}"
    
    print(f"Uploading snapshot to Object Store (MinIO) at {bucket_name}/{object_key}...")
    s3_client = boto3.client(
        "s3",
        endpoint_url=settings.object_store_endpoint,
        aws_access_key_id=settings.object_store_access_key,
        aws_secret_access_key=settings.object_store_secret_key,
        region_name="us-east-1" # MinIO default dummy region
    )
    
    # Ensure bucket exists
    try:
        s3_client.head_bucket(Bucket=bucket_name)
    except:
        s3_client.create_bucket(Bucket=bucket_name)

    s3_client.upload_file(str(tmp_path), bucket_name, object_key)
    print("Upload complete!")
    
    # 5. Cleanup
    print("Cleaning up local file and Qdrant server snapshot...")
    tmp_path.unlink()
    # Delete from Qdrant server so we don't bloat the container disk
    client.delete_snapshot(collection_name=collection_name, snapshot_name=snapshot_name)
    
    print("Backup workflow completed successfully!")

if __name__ == "__main__":
    backup_qdrant()
