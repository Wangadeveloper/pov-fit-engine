import uuid

from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from app.models.feedback import FitFeedback
from app.models.purchase import Purchase
from app.models.product import ProductVariant, Product
from app.schemas.feedback import FitFeedbackCreate
from app.services.fit_service import FitService
from typing import Optional

class FeedbackService:
    @staticmethod
    def submit_feedback(db, user_id: uuid.UUID, data: FitFeedbackCreate) -> FitFeedback:
        # 1. Fetch Purchase
        stmt_purchase = select(Purchase).where(
            Purchase.id == data.purchase_id,
            Purchase.user_id == user_id
        ).options(
            selectinload(Purchase.variant).selectinload(ProductVariant.product)
        )
        purchase_res = db.session.execute(stmt_purchase)
        purchase = purchase_res.scalars().first()
        if not purchase:
            raise ValueError("Purchase record not found.")

        # Update purchase status
        purchase.status = data.outcome_label

        # 2. Check if feedback already exists for this purchase
        stmt_feedback = select(FitFeedback).where(FitFeedback.purchase_id == data.purchase_id)
        feedback_res = db.session.execute(stmt_feedback)
        feedback = feedback_res.scalars().first()

        if feedback:
            # Update existing
            feedback.outcome_label = data.outcome_label
            feedback.reason_label = data.reason_label
            feedback.tight_loose_regions = data.tight_loose_regions
            feedback.would_buy_again = data.would_buy_again
            feedback.final_size_worn = data.final_size_worn
        else:
            # Create new
            feedback = FitFeedback(
                user_id=user_id,
                purchase_id=data.purchase_id,
                outcome_label=data.outcome_label,
                reason_label=data.reason_label,
                tight_loose_regions=data.tight_loose_regions,
                would_buy_again=data.would_buy_again,
                final_size_worn=data.final_size_worn
            )
            db.session.add(feedback)

        # 3. Propagate feedback outcomes to the Fit Passport / Fit Genome
        profile = FitService.get_or_create_profile(db, user_id)
        
        category = purchase.variant.product.category.lower()
        is_bottom = any(kw in category for kw in ["jeans", "trousers", "shorts", "pants", "bottoms"])
        cat_key = "bottoms" if is_bottom else "tops"
        
        # Save regional tight/loose feedback to fit attributes
        for region, fit_value in data.tight_loose_regions.items():
            # fit_value can be too_tight, too_loose, perfect, tight, loose
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

        # 4. Trigger metrics recalculation
        FitService.recalculate_metrics(db, profile)
        db.session.add(profile)
        db.session.add(purchase)
        
        db.session.commit()
        db.session.refresh(feedback)
        return feedback
