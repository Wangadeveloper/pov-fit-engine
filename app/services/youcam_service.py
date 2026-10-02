import httpx
import logging
import uuid
import os
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class YouCamVTOService:
    """
    Synchronous YouCam AI Clothes Virtual Try-On service.
    Uses Perfect Corp S2S REST API v2.0.
    """

    @property
    def api_key(self) -> str:
        return os.environ.get("YOUCAM_API_KEY", "").strip()

    @property
    def base_url(self) -> str:
        return os.environ.get("YOUCAM_API_BASE_URL", "https://yce-api-01.makeupar.com/s2s").rstrip("/")

    def get_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def create_tryon_task(
        self,
        user_photo_url: str,
        garment_image_url: str,
        garment_category: str = "upper_body",
        recommended_size: str = "M",
    ) -> Dict[str, Any]:
        """
        Submits a virtual try-on task to YouCam.
        """
        if not self.api_key:
            return self._sandbox_fallback(user_photo_url, garment_image_url, "No YouCam API Key configured.")

        # Ensure image URLs are valid public URLs for YouCam S2S API
        src_url = user_photo_url
        ref_url = garment_image_url

        # Fallback for localhost URLs when running locally so YouCam can fetch images
        if not src_url.startswith("https://"):
            if src_url.startswith("http://localhost") or src_url.startswith("http://127.0.0.1") or src_url.startswith("/"):
                # Use standard high-quality model photo for local dev testing with live YouCam API
                src_url = "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=600"

        if not ref_url.startswith("https://"):
            if ref_url.startswith("http://localhost") or ref_url.startswith("http://127.0.0.1") or ref_url.startswith("/"):
                ref_url = "https://images.unsplash.com/photo-1521572267360-ee0c2909d518?w=600"

        endpoint = f"{self.base_url}/v2.0/task/cloth-v3"
        payload = {
            "src_file_url": src_url,
            "ref_file_url": ref_url,
            "garment_category": garment_category,
        }

        try:
            with httpx.Client(timeout=15.0) as client:
                resp = client.post(endpoint, json=payload, headers=self.get_headers())
                if resp.status_code == 200:
                    data = resp.json()
                    task_data = data.get("data", {}) if isinstance(data.get("data"), dict) else {}
                    task_id = task_data.get("task_id") or data.get("task_id")
                    if task_id:
                        return {
                            "success": True,
                            "task_id": task_id,
                            "status": "processing",
                            "provider": "YouCam AI Virtual Try-On (Live)",
                            "sandbox": False,
                        }
                logger.warning(f"YouCam API response error {resp.status_code}: {resp.text}")
        except Exception as e:
            logger.warning(f"YouCam API connection error: {e}. Using sandbox mode.")

        return self._sandbox_fallback(user_photo_url, garment_image_url, "Live API submission error. Showing preview overlay.")

    def _sandbox_fallback(self, user_photo_url: str, garment_image_url: str, note: str) -> Dict[str, Any]:
        sim_task_id = f"youcam-sandbox-{uuid.uuid4().hex[:10]}"
        return {
            "success": True,
            "task_id": sim_task_id,
            "status": "success",
            "result_url": garment_image_url,
            "provider": "YouCam AI Virtual Try-On (Sandbox)",
            "sandbox": True,
            "sandbox_note": note,
        }

    def get_task_result(self, task_id: str) -> Dict[str, Any]:
        """
        Polls YouCam for the result of a try-on task.
        """
        if task_id.startswith("youcam-sandbox-"):
            return {
                "task_id": task_id,
                "status": "success",
                "progress": 100,
                "provider": "YouCam AI Virtual Try-On (Sandbox)",
            }

        endpoint = f"{self.base_url}/v2.0/task/cloth-v3/{task_id}"
        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.get(endpoint, headers={"Authorization": f"Bearer {self.api_key}"})
                resp.raise_for_status()
                data = resp.json()
                task_data = data.get("data", {}) if isinstance(data.get("data"), dict) else {}
                raw_status = task_data.get("task_status", "processing")
                results = task_data.get("results") or {}
                result_url = results.get("url") if isinstance(results, dict) else None

                if raw_status == "success" and result_url:
                    return {
                        "task_id": task_id,
                        "status": "success",
                        "progress": 100,
                        "result_url": result_url,
                        "provider": "YouCam AI Virtual Try-On (Live)",
                    }
                elif raw_status in ["error", "failed"]:
                    err_msg = task_data.get("error") or task_data.get("error_message") or "YouCam generation failed"
                    return {
                        "task_id": task_id,
                        "status": "error",
                        "error": str(err_msg),
                        "message": str(err_msg),
                    }
                else:
                    return {
                        "task_id": task_id,
                        "status": "processing",
                        "progress": 50,
                    }
        except Exception as e:
            logger.error(f"Error polling YouCam task {task_id}: {e}")
            return {
                "task_id": task_id,
                "status": "error",
                "message": str(e),
            }

    @staticmethod
    def map_category(product_category: str) -> str:
        """Maps product category string to YouCam garment_category value (upper_body | lower_body | full_body)."""
        cat = (product_category or "").lower()
        if any(k in cat for k in ["jeans", "trousers", "shorts", "pants", "bottoms", "skirt"]):
            return "lower_body"
        if any(k in cat for k in ["dress", "jumpsuit", "overall", "gown"]):
            return "full_body"
        return "upper_body"


youcam_service = YouCamVTOService()

