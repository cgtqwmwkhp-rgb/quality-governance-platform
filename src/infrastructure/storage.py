"""Blob storage service abstraction.

Provides secure file upload/download with signed URLs.
Supports Azure Blob Storage in production, local filesystem in development.
"""

import hashlib
import hmac
import logging
import os
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import quote, urlencode

from src.core.config import settings

logger = logging.getLogger(__name__)


class StorageError(Exception):
    """Base exception for storage operations."""

    pass


class StorageNotConfiguredError(StorageError):
    """Raised when storage is not configured."""

    pass


class BlobStorageService(ABC):
    """Abstract base class for blob storage operations."""

    @abstractmethod
    async def upload(
        self,
        storage_key: str,
        content: bytes,
        content_type: str,
        metadata: Optional[dict] = None,
    ) -> str:
        """Upload a file to blob storage.

        Args:
            storage_key: Unique storage path/key for the file
            content: File content as bytes
            content_type: MIME type of the file
            metadata: Optional metadata to store with the file

        Returns:
            The storage key (same as input for confirmation)

        Raises:
            StorageError: If upload fails
        """
        pass

    @abstractmethod
    async def download(self, storage_key: str) -> bytes:
        """Download a file from blob storage.

        Args:
            storage_key: Storage path/key of the file

        Returns:
            File content as bytes

        Raises:
            StorageError: If download fails or file not found
        """
        pass

    @abstractmethod
    async def delete(self, storage_key: str) -> bool:
        """Delete a file from blob storage.

        Args:
            storage_key: Storage path/key of the file

        Returns:
            True if deleted, False if not found

        Raises:
            StorageError: If delete fails
        """
        pass

    @abstractmethod
    def get_signed_url(
        self,
        storage_key: str,
        expires_in_seconds: int = 3600,
        content_disposition: Optional[str] = None,
    ) -> str:
        """Generate a signed URL for secure download.

        Args:
            storage_key: Storage path/key of the file
            expires_in_seconds: URL expiry time (default 1 hour)
            content_disposition: Optional content-disposition header

        Returns:
            Signed URL string
        """
        pass

    @abstractmethod
    async def exists(self, storage_key: str) -> bool:
        """Check if a file exists in storage.

        Args:
            storage_key: Storage path/key of the file

        Returns:
            True if exists, False otherwise
        """
        pass


class LocalFileStorageService(BlobStorageService):
    """Local filesystem storage for development.

    Files are stored in ./storage/evidence/ directory.
    """

    def __init__(self, base_path: str = "./storage/evidence"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"LocalFileStorageService initialized at {self.base_path.absolute()}")

    def _get_full_path(self, storage_key: str) -> Path:
        """Get full filesystem path for storage key."""
        safe_key = storage_key.lstrip("/")
        full_path = (self.base_path / safe_key).resolve()
        if not str(full_path).startswith(str(self.base_path.resolve())):
            raise ValueError("Path traversal detected")
        full_path.parent.mkdir(parents=True, exist_ok=True)
        return full_path

    async def upload(
        self,
        storage_key: str,
        content: bytes,
        content_type: str,
        metadata: Optional[dict] = None,
    ) -> str:
        """Upload file to local filesystem."""
        try:
            full_path = self._get_full_path(storage_key)
            full_path.write_bytes(content)

            # Store metadata in sidecar file
            if metadata:
                import json

                meta_path = full_path.with_suffix(full_path.suffix + ".meta.json")
                meta_path.write_text(
                    json.dumps(
                        {
                            "content_type": content_type,
                            "metadata": metadata,
                            "uploaded_at": datetime.now(timezone.utc).isoformat(),
                        }
                    )
                )

            logger.info(f"Uploaded file to local storage: {storage_key} ({len(content)} bytes)")
            return storage_key
        except Exception as e:
            logger.error(f"Local storage upload failed: {e}")
            raise StorageError(f"Upload failed: {e}") from e

    async def download(self, storage_key: str) -> bytes:
        """Download file from local filesystem."""
        try:
            full_path = self._get_full_path(storage_key)
            if not full_path.exists():
                raise StorageError(f"File not found: {storage_key}")
            return full_path.read_bytes()
        except StorageError:
            raise
        except Exception as e:
            logger.error(f"Local storage download failed: {e}")
            raise StorageError(f"Download failed: {e}") from e

    async def delete(self, storage_key: str) -> bool:
        """Delete file from local filesystem."""
        try:
            full_path = self._get_full_path(storage_key)
            if full_path.exists():
                full_path.unlink()
                # Also delete metadata sidecar if exists
                meta_path = full_path.with_suffix(full_path.suffix + ".meta.json")
                if meta_path.exists():
                    meta_path.unlink()
                logger.info(f"Deleted file from local storage: {storage_key}")
                return True
            return False
        except Exception as e:
            logger.error(f"Local storage delete failed: {e}")
            raise StorageError(f"Delete failed: {e}") from e

    def get_signed_url(
        self,
        storage_key: str,
        expires_in_seconds: int = 3600,
        content_disposition: Optional[str] = None,
    ) -> str:
        """Generate a pseudo-signed URL for local development.

        In development, this returns a local API endpoint that serves the file.
        """
        # Create a simple HMAC signature for development
        expiry = datetime.now(timezone.utc) + timedelta(seconds=expires_in_seconds)
        expiry_ts = int(expiry.timestamp())

        # Simple signature using app secret key
        message = f"{storage_key}:{expiry_ts}"
        signature = hmac.new(
            settings.secret_key.encode(),
            message.encode(),
            hashlib.sha256,
        ).hexdigest()[:16]

        params = {
            "key": storage_key,
            "expires": expiry_ts,
            "sig": signature,
        }
        if content_disposition:
            params["cd"] = content_disposition

        return f"/api/v1/evidence-assets/download?{urlencode(params)}"

    async def exists(self, storage_key: str) -> bool:
        """Check if file exists in local filesystem."""
        full_path = self._get_full_path(storage_key)
        return full_path.exists()


class AzureBlobStorageService(BlobStorageService):
    """Azure Blob Storage service for production.

    Uses Azure Storage SDK for secure blob operations.
    """

    def __init__(self, connection_string: str, container_name: str):
        if not connection_string:
            raise StorageNotConfiguredError("Azure Storage connection string not configured")

        self.container_name = container_name
        self._connection_string = connection_string
        self._client = None
        logger.info(f"AzureBlobStorageService initialized for container: {container_name}")

    def _get_client(self):
        """Lazy-load Azure Storage client."""
        if self._client is None:
            try:
                from azure.storage.blob import BlobServiceClient

                self._client = BlobServiceClient.from_connection_string(self._connection_string)
            except ImportError:
                raise StorageError("azure-storage-blob package not installed. Run: pip install azure-storage-blob")
            except Exception as e:
                raise StorageError(f"Failed to create Azure Storage client: {e}")
        return self._client

    def _get_container_client(self):
        """Get container client."""
        return self._get_client().get_container_client(self.container_name)

    def _get_blob_client(self, storage_key: str):
        """Get blob client for a specific key."""
        return self._get_container_client().get_blob_client(storage_key)

    async def upload(
        self,
        storage_key: str,
        content: bytes,
        content_type: str,
        metadata: Optional[dict] = None,
    ) -> str:
        """Upload file to Azure Blob Storage."""
        try:
            blob_client = self._get_blob_client(storage_key)
            blob_client.upload_blob(
                content,
                content_type=content_type,
                metadata=metadata,
                overwrite=True,
            )
            logger.info(f"Uploaded file to Azure Storage: {storage_key} ({len(content)} bytes)")
            return storage_key
        except Exception as e:
            logger.error(f"Azure storage upload failed: {e}")
            raise StorageError(f"Upload failed: {e}") from e

    async def download(self, storage_key: str) -> bytes:
        """Download file from Azure Blob Storage."""
        try:
            blob_client = self._get_blob_client(storage_key)
            stream = blob_client.download_blob()
            return stream.readall()
        except Exception as e:
            logger.error(f"Azure storage download failed: {e}")
            raise StorageError(f"Download failed: {e}") from e

    async def delete(self, storage_key: str) -> bool:
        """Delete file from Azure Blob Storage."""
        try:
            blob_client = self._get_blob_client(storage_key)
            blob_client.delete_blob()
            logger.info(f"Deleted file from Azure Storage: {storage_key}")
            return True
        except Exception as e:
            if "BlobNotFound" in str(e):
                return False
            logger.error(f"Azure storage delete failed: {e}")
            raise StorageError(f"Delete failed: {e}") from e

    def get_signed_url(
        self,
        storage_key: str,
        expires_in_seconds: int = 3600,
        content_disposition: Optional[str] = None,
    ) -> str:
        """Generate a SAS URL for secure download."""
        try:
            from azure.storage.blob import BlobSasPermissions, generate_blob_sas

            expiry = datetime.now(timezone.utc) + timedelta(seconds=expires_in_seconds)

            # Parse account info from connection string
            conn_parts = dict(part.split("=", 1) for part in self._connection_string.split(";") if "=" in part)
            account_name = conn_parts.get("AccountName", "")
            account_key = conn_parts.get("AccountKey", "")

            sas_token = generate_blob_sas(
                account_name=account_name,
                container_name=self.container_name,
                blob_name=storage_key,
                account_key=account_key,
                permission=BlobSasPermissions(read=True),
                expiry=expiry,
                content_disposition=content_disposition,
            )

            return (
                f"https://{account_name}.blob.core.windows.net/{self.container_name}/{quote(storage_key)}?{sas_token}"
            )
        except ImportError:
            raise StorageError("azure-storage-blob package not installed")
        except Exception as e:
            logger.error(f"Failed to generate SAS URL: {e}")
            raise StorageError(f"SAS URL generation failed: {e}") from e

    async def exists(self, storage_key: str) -> bool:
        """Check if blob exists in Azure Storage."""
        try:
            blob_client = self._get_blob_client(storage_key)
            return blob_client.exists()
        except Exception:
            return False


def get_storage_service() -> BlobStorageService:
    """Get the appropriate storage service based on configuration.

    Returns LocalFileStorageService in development, AzureBlobStorageService in production.
    """
    if settings.is_production:
        return AzureBlobStorageService(
            connection_string=settings.azure_storage_connection_string,
            container_name=settings.azure_storage_container_name,
        )
    else:
        return LocalFileStorageService()


# Singleton instance
_storage_service: Optional[BlobStorageService] = None


def storage_service() -> BlobStorageService:
    """Get the singleton storage service instance."""
    global _storage_service
    if _storage_service is None:
        _storage_service = get_storage_service()
    return _storage_service
