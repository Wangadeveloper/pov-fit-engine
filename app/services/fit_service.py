import uuid

from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from app.models.fit_profile import FitProfile, FitAttribute
from app.models.closet import ClosetItem
from app.models.feedback import FitFeedback
from app.schemas.fit import FitProfileUpdate, OnboardingDetails
from typing import List, Optional

class FitService:
    @staticmethod
    def get_or_create_profile(db, user_id: uuid.UUID) -> FitProfile:
        stmt = select(FitProfile).where(FitProfile.user_id == user_id).options(
            selectinload(FitProfile.attributes)
        )
        result = db.session.execute(stmt)
        profile = result.scalars().first()
        
        if not profile:
            profile = FitProfile(
                user_id=user_id,
                preferred_top_fit="regular",
                preferred_bottom_fit="straight",
                preferred_jacket_fit="regular",
                comfort_preferences=[],
                confidence=0.25,
                profile_completeness=0.15,
                calibration_level="low"
            )
            db.session.add(profile)
            db.session.commit()
            db.session.refresh(profile)
            
            # Reload to include attributes relationship
            stmt = select(FitProfile).where(FitProfile.id == profile.id).options(
                selectinload(FitProfile.attributes)
            )
            result = db.session.execute(stmt)
            profile = result.scalars().first()
            
        return profile

    @staticmethod
    def update_profile(db, user_id: uuid.UUID, update_data: FitProfileUpdate) -> FitProfile:
        profile = FitService.get_or_create_profile(db, user_id)
        
        update_dict = update_data.model_dump(exclude_unset=True)
        for key, val in update_dict.items():
            setattr(profile, key, val)
            
        FitService.recalculate_metrics(db, profile)
        db.session.add(profile)
        db.session.commit()
        db.session.refresh(profile)
        return profile

    @staticmethod
    def save_onboarding(db, user_id: uuid.UUID, data: OnboardingDetails) -> FitProfile:
        profile = FitService.get_or_create_profile(db, user_id)
        
        profile.preferred_top_fit = data.preferred_top_fit
        profile.preferred_bottom_fit = data.preferred_bottom_fit
        profile.preferred_jacket_fit = data.preferred_jacket_fit
        profile.comfort_preferences = data.comfort_preferences
        profile.height_cm = data.height_cm
        profile.weight_kg = data.weight_kg
        
        FitService.recalculate_metrics(db, profile)
        db.session.add(profile)
        db.session.commit()
        db.session.refresh(profile)
        return profile

    @staticmethod
    def add_or_update_attribute(
        db, 
        profile_id: uuid.UUID, 
        category: str, 
        key: str, 
        value: str
    ) -> FitAttribute:
        stmt = select(FitAttribute).where(
            FitAttribute.fit_profile_id == profile_id,
            FitAttribute.category == category,
            FitAttribute.attribute_key == key
        )
        result = db.session.execute(stmt)
        attribute = result.scalars().first()
        
        if attribute:
            attribute.attribute_value = value
        else:
            attribute = FitAttribute(
                fit_profile_id=profile_id,
                category=category,
                attribute_key=key,
                attribute_value=value
            )
            db.session.add(attribute)
            
        db.session.commit()
        return attribute

    @staticmethod
    def recalculate_metrics(db, profile: FitProfile) -> None:
        # 1. Recalculate Completeness
        completeness = 0.0
        
        # Base visual fits: 15% each (total 45%)
        if profile.preferred_top_fit: completeness += 0.15
        if profile.preferred_bottom_fit: completeness += 0.15
        if profile.preferred_jacket_fit: completeness += 0.15
        
        # Comfort preferences: 15%
        if profile.comfort_preferences: completeness += 0.15
        
        # Optional parameters (height/weight): 10%
        if profile.height_cm or profile.weight_kg: completeness += 0.10
        
        # Query closet items count
        stmt_closet = select(ClosetItem).where(ClosetItem.user_id == profile.user_id)
        res_closet = db.session.execute(stmt_closet)
        closet_count = len(res_closet.scalars().all())
        if closet_count > 0:
            completeness += 0.15  # 15% if they have at least 1 closet item
            
        # Query feedback count
        stmt_fb = select(FitFeedback).where(FitFeedback.user_id == profile.user_id)
        res_fb = db.session.execute(stmt_fb)
        fb_count = len(res_fb.scalars().all())
        if fb_count > 0:
            completeness += 0.15  # 15% if they have submitted feedback
            
        profile.profile_completeness = round(min(1.0, completeness), 2)
        
        # 2. Recalculate Calibration Level
        total_signals = closet_count + fb_count
        if total_signals >= 8:
            profile.calibration_level = "high"
        elif total_signals >= 3:
            profile.calibration_level = "medium"
        else:
            profile.calibration_level = "low"

        # 3. Recalculate Confidence Score
        confidence = 0.25
        confidence += min(0.30, closet_count * 0.10)
        confidence += min(0.40, fb_count * 0.15)
        profile.confidence = round(min(1.0, confidence), 2)
