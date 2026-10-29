
import logging
import os
import time
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)


class YouCamVTOService:
    """
    YouCam AI Clothes Virtual Try-On V4.

    Supports:
      - Full-body outfits
      - Upper-body garments
      - Lower-body garments
      - Shoes
      - Outerwear
      - Automatic category detection

    IMPORTANT:
    Full-body mode requires a reference image showing a complete outfit.
    A single shirt image is not a complete outfit reference.
    """

    VALID_CATEGORIES = {
        "full_body",
        "upper_body",
        "lower_body",
        "shoes",
        "auto",
        "outer",
    }

    def __init__(self):
        self.api_key = os.getenv("YOUCAM_API_KEY", "").strip()
        self.base_url = os.getenv(
            "YOUCAM_API_BASE_URL",
            "https://yce-api-01.makeupar.com/s2s",
        ).rstrip("/")

        self.timeout = float(
            os.getenv("YOUCAM_TIMEOUT", "30")
        )

    @property
    def task_endpoint(self) -> str:
        return f"{self.base_url}/v2.0/task/cloth-v4"

    def _headers(self) -> Dict[str, str]:
        if not self.api_key:
            raise RuntimeError(
                "YOUCAM_API_KEY is not configured."
            )

        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    @staticmethod
    def map_category(product_category: str) -> str:
        """
        Map catalog categories to YouCam V4 categories.
        """
        cat = (product_category or "").lower().replace("-", "_")

        if any(x in cat for x in (
            "jumpsuit", "romper", "overall",
            "dress", "gown", "one_piece",
            "complete_outfit", "full_outfit",
            "matching_set", "co_ord",
        )):
            return "full_body"

        if any(x in cat for x in (
            "coat", "jacket", "blazer",
            "vest", "outerwear", "trench",
        )):
            return "outer"

        if any(x in cat for x in (
            "shoe", "sneaker", "boot", "heel",
        )):
            return "shoes"

        if any(x in cat for x in (
            "trouser", "pants", "jeans",
            "shorts", "skirt", "bottom",
        )):
            return "lower_body"

        if any(x in cat for x in (
            "shirt", "t_shirt", "tee",
            "top", "blouse", "sweater",
            "hoodie", "cardigan", "polo",
        )):
            return "upper_body"

        return "auto"

    @staticmethod
    def _validate_url(url: str, field: str) -> None:
        if not isinstance(url, str):
            raise ValueError(f"{field} must be a URL.")

        if not url.startswith(("https://", "http://")):
            raise ValueError(
                f"{field} must be an absolute HTTP(S) URL."
            )

        if url.startswith(("http://localhost", "http://127.0.0.1")):
            raise ValueError(
                f"{field} cannot use localhost. "
                "Provide a publicly accessible image URL."
            )

    @staticmethod
    def _parse_response(response: httpx.Response) -> Dict[str, Any]:
        try:
            data = response.json()
        except ValueError:
            data = {"message": response.text[:1000]}

        if response.is_error:
            raise RuntimeError(
                f"YouCam API returned HTTP {response.status_code}: "
                f"{data}"
            )

        # The API can return an application error even when HTTP is 200.
        if isinstance(data, dict):
            status = data.get("status")
            if isinstance(status, int) and status >= 400:
                raise RuntimeError(
                    f"YouCam API error: {data}"
                )

            if data.get("error"):
                raise RuntimeError(
                    f"YouCam API error: {data}"
                )

        return data

    def create_tryon_task(
        self,
        user_photo_url: str,
        garment_image_url: str,
        garment_category: str = "full_body",
        recommended_size: Optional[str] = None,
        change_shoes: bool = True,
        filter_multi_person: str = "normal",
    ) -> Dict[str, Any]:
        """
        Submit a real V4 try-on task.

        For full_body, garment_image_url should show a complete outfit.
        recommended_size is metadata only: YouCam does not use it to
        calculate garment sizing in this request.
        """
        self._validate_url(user_photo_url, "user_photo_url")
        self._validate_url(garment_image_url, "garment_image_url")

        if garment_category not in self.VALID_CATEGORIES:
            raise ValueError(
                f"Invalid garment_category: {garment_category}"
            )

        if filter_multi_person not in ("off", "normal", "strict"):
            raise ValueError(
                "filter_multi_person must be off, normal, or strict."
            )

        payload = {
            "src_file_url": user_photo_url,
            "ref_file_url": garment_image_url,
            "garment_category": garment_category,
            "change_shoes": change_shoes,
            "filter_multi_person": filter_multi_person,
        }

        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(
                self.task_endpoint,
                json=payload,
                headers=self._headers(),
            )
            data = self._parse_response(response)

        task_data = data.get("data") or {}
        task_id = task_data.get("task_id") or data.get("task_id")

        if not task_id:
            raise RuntimeError(
                f"YouCam did not return a task_id: {data}"
            )

        return {
            "success": True,
            "task_id": task_id,
            "status": "processing",
            "provider": "YouCam AI Clothes V4",
            "garment_category": garment_category,
            "recommended_size": recommended_size,
            "sandbox": False,
        }

    def get_task_result(self, task_id: str) -> Dict[str, Any]:
        """
        Retrieve the status and result of a submitted task.
        """
        if not task_id:
            raise ValueError("task_id is required.")

        endpoint = f"{self.task_endpoint}/{task_id}"

        with httpx.Client(timeout=self.timeout) as client:
            response = client.get(
                endpoint,
                headers=self._headers(),
            )
            data = self._parse_response(response)

        task_data = data.get("data") or {}
        raw_status = str(
            task_data.get("task_status", "processing")
        ).lower()

        results = task_data.get("results") or {}
        result_url = (
            results.get("url")
            if isinstance(results, dict)
            else None
        )

        if raw_status == "success":
            if not result_url:
                raise RuntimeError(
                    "Task succeeded but no result URL was returned."
                )

            return {
                "success": True,
                "task_id": task_id,
                "status": "success",
                "progress": 100,
                "result_url": result_url,
                "provider": "YouCam AI Clothes V4",
                "sandbox": False,
            }

        if raw_status in ("error", "failed"):
            return {
                "success": False,
                "task_id": task_id,
                "status": "error",
                "error": (
                    task_data.get("error_message")
                    or task_data.get("error")
                    or "YouCam try-on failed."
                ),
            }

        return {
            "success": True,
            "task_id": task_id,
            "status": "processing",
            "progress": None,
            "provider": "YouCam AI Clothes V4",
            "sandbox": False,
        }

    def wait_for_result(
        self,
        task_id: str,
        poll_interval: float = 3.0,
        timeout: float = 120.0,
    ) -> Dict[str, Any]:
        """
        Poll until success, failure, or timeout.
        Prefer background jobs for production web requests.
        """
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            result = self.get_task_result(task_id)

            if result["status"] in ("success", "error"):
                return result

            time.sleep(poll_interval)

        return {
            "success": False,
            "task_id": task_id,
            "status": "timeout",
            "error": (
                "Try-on is still processing. Poll this task again "
                "instead of submitting a duplicate task."
            ),
        }

    def try_on_full_outfit(
        self,
        user_photo_url: str,
        full_outfit_reference_url: str,
        change_shoes: bool = True,
    ) -> Dict[str, Any]:
        """
        Best choice for a coordinated shirt + trousers outfit,
        or any complete look represented by a suitable reference.
        """
        return self.create_tryon_task(
            user_photo_url=user_photo_url,
            garment_image_url=full_outfit_reference_url,
            garment_category="full_body",
            change_shoes=change_shoes,
        )

    def try_on_product(
        self,
        user_photo_url: str,
        product_image_url: str,
        product_category: str,
    ) -> Dict[str, Any]:
        """
        Try an individual product using its appropriate category.
        """
        category = self.map_category(product_category)

        return self.create_tryon_task(
            user_photo_url=user_photo_url,
            garment_image_url=product_image_url,
            garment_category=category,
        )


youcam_service = YouCamVTOService()
