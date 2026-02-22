import os
from imagekitio import ImageKit
from app.config import settings

class ImageKitService:
    def __init__(self):
        # The Stainless version of the SDK only takes private_key in __init__
        self.imagekit = ImageKit(
            private_key=settings.imagekit_private_key,
        )
        self.url_endpoint = settings.imagekit_url_endpoint

    def upload_file(self, file_bytes: bytes, file_name: str, folder: str = "/uploads"):
        """
        Uploads a file to ImageKit and returns the URL.
        """
        try:
            upload_response = self.imagekit.files.upload(
                file=file_bytes,
                file_name=file_name,
                folder=folder,
                use_unique_file_name=True,
            )
            return upload_response.url
        except Exception as e:
            raise RuntimeError(f"ImageKit upload failed: {str(e)}")

imagekit_service = ImageKitService()
