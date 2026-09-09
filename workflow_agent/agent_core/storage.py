"""
Pluggable SpecStorage Abstraction for API Specifications.

Supports local filesystem storage by default, with pluggable support for
Google Cloud Storage (gs://) and AWS S3 / Lambda (s3://) URI schemes.
"""
import abc
import os
import logging
from typing import Optional
from django.conf import settings

logger = logging.getLogger(__name__)

DEFAULT_SPECS_DIR = getattr(settings, 'SPECS_DIR', os.path.join(getattr(settings, 'BASE_DIR', '.'), 'specs'))


class SpecStorage(abc.ABC):
    """Abstract Base Class for API Spec Storage Backends."""

    @abc.abstractmethod
    def read(self, path: str) -> str:
        """Read spec text content from given path/URI."""
        pass

    @abc.abstractmethod
    def write(self, path: str, content: str) -> None:
        """Write spec text content to given path/URI."""
        pass

    @abc.abstractmethod
    def exists(self, path: str) -> bool:
        """Check if spec exists at given path/URI."""
        pass


class LocalSpecStorage(SpecStorage):
    """Local filesystem storage backend."""

    def __init__(self, base_dir: Optional[str] = None):
        self.base_dir = base_dir or DEFAULT_SPECS_DIR

    def _resolve_path(self, path: str) -> str:
        if os.path.isabs(path):
            return path
        return os.path.join(self.base_dir, path)

    def read(self, path: str) -> str:
        full_path = self._resolve_path(path)
        if not os.path.exists(full_path):
            raise FileNotFoundError(f"Spec file not found at local path: '{full_path}'")
        with open(full_path, 'r', encoding='utf-8') as f:
            return f.read()

    def write(self, path: str, content: str) -> None:
        full_path = self._resolve_path(path)
        dir_name = os.path.dirname(full_path)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(content)
        logger.info(f"Wrote API spec to local path: '{full_path}'")

    def exists(self, path: str) -> bool:
        full_path = self._resolve_path(path)
        return os.path.exists(full_path)


class GcsSpecStorage(SpecStorage):
    """Google Cloud Storage (gs://) backend plugin stub."""

    def __init__(self, bucket_name: Optional[str] = None):
        self.bucket_name = bucket_name or os.environ.get('GCS_SPECS_BUCKET', 'workflow-specs')
        self.local_fallback = LocalSpecStorage()

    def read(self, path: str) -> str:
        if path.startswith('gs://'):
            # If google-cloud-storage installed, use it; else fallback to local/mock
            try:
                from google.cloud import storage
                client = storage.Client()
                # Parse gs://bucket/blob_path
                parts = path[5:].split('/', 1)
                bucket_name = parts[0]
                blob_name = parts[1] if len(parts) > 1 else ''
                bucket = client.bucket(bucket_name)
                blob = bucket.blob(blob_name)
                return blob.download_as_text()
            except ImportError:
                logger.warning("google-cloud-storage library not installed; falling back to local storage simulation.")
                clean_path = path.replace('gs://', '').replace('/', '_')
                return self.local_fallback.read(clean_path)
        return self.local_fallback.read(path)

    def write(self, path: str, content: str) -> None:
        if path.startswith('gs://'):
            try:
                from google.cloud import storage
                client = storage.Client()
                parts = path[5:].split('/', 1)
                bucket_name = parts[0]
                blob_name = parts[1] if len(parts) > 1 else ''
                bucket = client.bucket(bucket_name)
                blob = bucket.blob(blob_name)
                blob.upload_from_string(content, content_type='text/yaml')
                logger.info(f"Uploaded API spec to GCS: '{path}'")
                return
            except ImportError:
                logger.warning("google-cloud-storage library not installed; writing to local storage simulation.")
                clean_path = path.replace('gs://', '').replace('/', '_')
                return self.local_fallback.write(clean_path, content)
        return self.local_fallback.write(path, content)

    def exists(self, path: str) -> bool:
        if path.startswith('gs://'):
            try:
                from google.cloud import storage
                client = storage.Client()
                parts = path[5:].split('/', 1)
                bucket = client.bucket(parts[0])
                blob = bucket.blob(parts[1] if len(parts) > 1 else '')
                return blob.exists()
            except Exception:
                clean_path = path.replace('gs://', '').replace('/', '_')
                return self.local_fallback.exists(clean_path)
        return self.local_fallback.exists(path)


class S3SpecStorage(SpecStorage):
    """AWS S3 / Lambda (s3://) backend plugin stub."""

    def __init__(self, bucket_name: Optional[str] = None):
        self.bucket_name = bucket_name or os.environ.get('S3_SPECS_BUCKET', 'workflow-specs')
        self.local_fallback = LocalSpecStorage()

    def read(self, path: str) -> str:
        if path.startswith('s3://'):
            try:
                import boto3
                s3 = boto3.client('s3')
                parts = path[5:].split('/', 1)
                bucket_name = parts[0]
                key = parts[1] if len(parts) > 1 else ''
                obj = s3.get_object(Bucket=bucket_name, Key=key)
                return obj['Body'].read().decode('utf-8')
            except ImportError:
                logger.warning("boto3 library not installed; falling back to local storage simulation.")
                clean_path = path.replace('s3://', '').replace('/', '_')
                return self.local_fallback.read(clean_path)
        return self.local_fallback.read(path)

    def write(self, path: str, content: str) -> None:
        if path.startswith('s3://'):
            try:
                import boto3
                s3 = boto3.client('s3')
                parts = path[5:].split('/', 1)
                bucket_name = parts[0]
                key = parts[1] if len(parts) > 1 else ''
                s3.put_object(Bucket=bucket_name, Key=key, Body=content.encode('utf-8'))
                logger.info(f"Uploaded API spec to S3: '{path}'")
                return
            except ImportError:
                logger.warning("boto3 library not installed; writing to local storage simulation.")
                clean_path = path.replace('s3://', '').replace('/', '_')
                return self.local_fallback.write(clean_path, content)
        return self.local_fallback.write(path, content)

    def exists(self, path: str) -> bool:
        clean_path = path.replace('s3://', '').replace('/', '_')
        return self.local_fallback.exists(clean_path)


def get_storage(path_or_uri: str) -> SpecStorage:
    """
    Factory function routing by URI scheme.
    - gs:// -> GcsSpecStorage
    - s3:// -> S3SpecStorage
    - otherwise -> LocalSpecStorage
    """
    if not path_or_uri:
        return LocalSpecStorage()

    if path_or_uri.startswith('gs://'):
        return GcsSpecStorage()
    elif path_or_uri.startswith('s3://'):
        return S3SpecStorage()
    else:
        return LocalSpecStorage()
