"""Storage provider for XiVault files."""

import abc

import httpx

from xivault.config import settings


class BaseStorage(abc.ABC):
    """Storage provider interface."""

    @abc.abstractmethod
    async def upload_object(self, key: str, data: bytes, content_type: str) -> None:
        """Upload raw bytes to private bucket."""
        pass

    @abc.abstractmethod
    async def download_object(self, key: str) -> bytes:
        """Download raw bytes from private bucket."""
        pass

    @abc.abstractmethod
    async def delete_object(self, key: str) -> None:
        """Delete object from private bucket."""
        pass


class InMemoryStorage(BaseStorage):
    """In-memory storage provider for tests and local fallback."""

    def __init__(self) -> None:
        self.objects: dict[str, tuple[bytes, str]] = {}

    async def upload_object(self, key: str, data: bytes, content_type: str) -> None:
        self.objects[key] = (data, content_type)

    async def download_object(self, key: str) -> bytes:
        if key not in self.objects:
            raise FileNotFoundError(f"Object {key} not found")
        return self.objects[key][0]

    async def delete_object(self, key: str) -> None:
        self.objects.pop(key, None)


class SupabaseStorage(BaseStorage):
    """Supabase private bucket storage via direct REST API calls."""

    def __init__(self, bucket_name: str = "xivault-files") -> None:
        self.bucket_name = bucket_name
        self.base_url = f"{settings.supabase_url.rstrip('/')}/storage/v1/object"
        self.headers = {
            "Authorization": f"Bearer {settings.supabase_service_role_key}",
            "apikey": settings.supabase_service_role_key,
        }

    async def upload_object(self, key: str, data: bytes, content_type: str) -> None:
        url = f"{self.base_url}/{self.bucket_name}/{key}"
        headers = {**self.headers, "Content-Type": content_type, "x-upsert": "true"}
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, content=data, headers=headers)
            resp.raise_for_status()

    async def download_object(self, key: str) -> bytes:
        url = f"{self.base_url}/{self.bucket_name}/{key}"
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, headers=self.headers)
            resp.raise_for_status()
            return resp.content

    async def delete_object(self, key: str) -> None:
        url = f"{self.base_url}/{self.bucket_name}/{key}"
        async with httpx.AsyncClient(timeout=15.0) as client:
            await client.delete(url, headers=self.headers)


_in_memory_storage = InMemoryStorage()


def get_storage() -> BaseStorage:
    """Provide active storage provider."""
    if (
        settings.supabase_service_role_key != "placeholder-key"
        and not settings.supabase_url.startswith("https://placeholder")
    ):
        try:
            return SupabaseStorage()
        except Exception:
            return _in_memory_storage
    return _in_memory_storage
