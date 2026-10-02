import uuid

from sqlalchemy.future import select
from app.models.closet import ClosetItem
from app.schemas.closet import ClosetItemCreate, ClosetItemUpdate
from app.services.fit_service import FitService
from typing import List, Optional

class ClosetService:
    @staticmethod
    def add_item(db, user_id: uuid.UUID, data: ClosetItemCreate) -> ClosetItem:
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
        db.session.add(item)
        db.session.commit()
        db.session.refresh(item)
        
        # Propagate changes to the Fit Passport
        profile = FitService.get_or_create_profile(db, user_id)
        
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
            FitService.add_or_update_attribute(
                db=db,
                profile_id=profile.id,
                category=cat_key,
                key=region.lower(),
                value=norm_val
            )
            
        FitService.recalculate_metrics(db, profile)
        db.session.add(profile)
        db.session.commit()
        
        return item

    @staticmethod
    def get_user_closet(db, user_id: uuid.UUID) -> List[ClosetItem]:
        stmt = select(ClosetItem).where(ClosetItem.user_id == user_id)
        result = db.session.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    def update_item(
        db, 
        user_id: uuid.UUID, 
        item_id: uuid.UUID, 
        data: ClosetItemUpdate
    ) -> Optional[ClosetItem]:
        stmt = select(ClosetItem).where(ClosetItem.id == item_id, ClosetItem.user_id == user_id)
        result = db.session.execute(stmt)
        item = result.scalars().first()
        if not item:
            return None
            
        update_dict = data.model_dump(exclude_unset=True)
        for key, val in update_dict.items():
            setattr(item, key, val)
            
        db.session.add(item)
        db.session.commit()
        db.session.refresh(item)
        
        # Recalculate passport
        profile = FitService.get_or_create_profile(db, user_id)
        
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
                FitService.add_or_update_attribute(
                    db=db,
                    profile_id=profile.id,
                    category=cat_key,
                    key=region.lower(),
                    value=norm_val
                )

        FitService.recalculate_metrics(db, profile)
        db.session.add(profile)
        db.session.commit()
        
        return item

    @staticmethod
    def delete_item(db, user_id: uuid.UUID, item_id: uuid.UUID) -> bool:
        stmt = select(ClosetItem).where(ClosetItem.id == item_id, ClosetItem.user_id == user_id)
        result = db.session.execute(stmt)
        item = result.scalars().first()
        if not item:
            return False
            
        db.session.delete(item)
        db.session.commit()
        
        # Recalculate passport completeness
        profile = FitService.get_or_create_profile(db, user_id)
        FitService.recalculate_metrics(db, profile)
        db.session.add(profile)
        db.session.commit()
        
        return True
