from typing import Optional

from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient, ContainerClient

from app.config import STORAGE_ACCOUNT_URL, STORAGE_CONTAINER_NAME

_credential: Optional[DefaultAzureCredential] = None
_container_client: Optional[ContainerClient] = None


def startup() -> None:
    global _credential, _container_client
    _credential = DefaultAzureCredential()
    blob_service_client = BlobServiceClient(account_url=STORAGE_ACCOUNT_URL, credential=_credential)
    _container_client = blob_service_client.get_container_client(STORAGE_CONTAINER_NAME)


def shutdown() -> None:
    if _credential is not None:
        _credential.close()


def upload_file(filename: str, content: bytes) -> str:
    blob_client = _container_client.get_blob_client(filename)
    blob_client.upload_blob(content, overwrite=True)
    return blob_client.url
