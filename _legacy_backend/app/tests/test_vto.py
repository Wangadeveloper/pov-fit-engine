import pytest
import pytest_asyncio
from app.services.youcam_service import youcam_service

@pytest.mark.asyncio
async def test_youcam_service_create_try_on_task():
    user_photo = "https://images.unsplash.com/photo-1534528741775-53994a69daeb?q=80&w=1000"
    garment_image = "https://images.unsplash.com/photo-1521572267360-ee0c2909d518?q=80&w=1000"
    
    result = await youcam_service.create_try_on_task(
        user_photo_url=user_photo,
        garment_image_url=garment_image,
        category="top",
        recommended_size="M"
    )
    
    assert result is not None
    assert "task_id" in result
    assert result["status"] == "success"
    assert "result_url" in result
    assert "YouCam" in result.get("provider", "")

@pytest.mark.asyncio
async def test_youcam_service_get_task_status():
    status_res = await youcam_service.get_task_status("youcam-vto-test123")
    assert status_res is not None
    assert status_res["status"] == "success"
