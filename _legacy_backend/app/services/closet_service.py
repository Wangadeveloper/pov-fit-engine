import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.models.closet import ClosetItem
from app.schemas.closet import ClosetItemCreate, ClosetItemUpdate
from app.services.fit_service import FitService
from typing import List, Optional

class ClosetService:
    @staticmethod
    async def add_item(db: AsyncSession, user_id: uuid.UUID, data: ClosetItemCreate) -> ClosetItem:
        # Create Closet Item
        item = ClosetItem(
            user_id=user_id,
            brand_name=data.brand_name,
            category=data.category,
            subcategory=data.subcategory,
            size_label=data.size_label,
            color=data.color,
            fit_label=data.fit_label,
            fit_rating=data.fit_rating,
            tight_loose_regions=data.tight_loose_regions,
            notes=data.notes,
            image_url=data.image_url
        )
        db.add(item)
        await db.commit()
        await db.refresh(item)
        
        # Propagate changes to the Fit Passport
        profile = await FitService.get_or_create_profile(db, user_id)
        
        # If user says it is "perfect", "too_tight", etc. - we can add attributes if regions are specified
        category_lower = data.category.lower()
        is_bottom = any(kw in category_lower for kw in ["jeans", "trousers", "shorts", "pants", "bottoms"])
        cat_key = "bottoms" if is_bottom else "tops"
        
        for region, fit_value in data.tight_loose_regions.items():
            norm_val = "good"
            if "tight" in fit_value:
                norm_val = "tight"
            elif "loose" in fit_value:
                norm_val = "loose"
            await FitService.add_or_update_attribute(
                db=db,
                profile_id=profile.id,
                category=cat_key,
                key=region.lower(),
                value=norm_val
            )
            
        await FitService.recalculate_metrics(db, profile)
        db.add(profile)
        await db.commit()
        
        return item

    @staticmethod
    async def get_user_closet(db: AsyncSession, user_id: uuid.UUID) -> List[ClosetItem]:
        stmt = select(ClosetItem).where(ClosetItem.user_id == user_id)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def update_item(
        db: AsyncSession, 
        user_id: uuid.UUID, 
        item_id: uuid.UUID, 
        data: ClosetItemUpdate
    ) -> Optional[ClosetItem]:
        stmt = select(ClosetItem).where(ClosetItem.id == item_id, ClosetItem.user_id == user_id)
        result = await db.execute(stmt)
        item = result.scalars().first()
        if not item:
            return None
            
        update_dict = data.model_dump(exclude_unset=True)
        for key, val in update_dict.items():
            setattr(item, key, val)
            
        db.add(item)
        await db.commit()
        await db.refresh(item)
        
        # Recalculate passport
        profile = await FitService.get_or_create_profile(db, user_id)
        
        # Propagate tight/loose regions if updated
        if data.tight_loose_regions is not None:
            category_lower = item.category.lower()
            is_bottom = any(kw in category_lower for kw in ["jeans", "trousers", "shorts", "pants", "bottoms"])
            cat_key = "bottoms" if is_bottom else "tops"
            for region, fit_value in data.tight_loose_regions.items():
                norm_val = "good"
                if "tight" in fit_value:
                    norm_val = "tight"
                elif "loose" in fit_value:
                    norm_val = "loose"
                await FitService.add_or_update_attribute(
                    db=db,
                    profile_id=profile.id,
                    category=cat_key,
                    key=region.lower(),
                    value=norm_val
                )

        await FitService.recalculate_metrics(db, profile)
        db.add(profile)
        await db.commit()
        
        return item

    @staticmethod
    async def delete_item(db: AsyncSession, user_id: uuid.UUID, item_id: uuid.UUID) -> bool:
        stmt = select(ClosetItem).where(ClosetItem.id == item_id, ClosetItem.user_id == user_id)
        result = await db.execute(stmt)
        item = result.scalars().first()
        if not item:
            return False
            
        await db.delete(item)
        await db.commit()
        
        # Recalculate passport completeness
        profile = await FitService.get_or_create_profile(db, user_id)
        await FitService.recalculate_metrics(db, profile)
        db.add(profile)
        await db.commit()
        
        return True
