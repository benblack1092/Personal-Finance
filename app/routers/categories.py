"""CRUD endpoints for categories and rules, plus re-categorization."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.categorize import recategorize_all
from app.database import get_db
from app.models import Category, Rule
from app.schemas import CategoryCreate, CategoryOut, RuleCreate, RuleOut

router = APIRouter(prefix="/api", tags=["categories"])


# --------------------------------------------------------------------------- #
# Categories
# --------------------------------------------------------------------------- #
@router.get("/categories", response_model=list[CategoryOut])
def list_categories(db: Session = Depends(get_db)):
    return list(db.scalars(select(Category).order_by(Category.name)))


@router.post("/categories", response_model=CategoryOut, status_code=201)
def create_category(payload: CategoryCreate, db: Session = Depends(get_db)):
    if db.scalar(select(Category).where(Category.name == payload.name)):
        raise HTTPException(400, "A category with that name already exists")
    cat = Category(**payload.model_dump())
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return cat


@router.delete("/categories/{category_id}", status_code=204)
def delete_category(category_id: int, db: Session = Depends(get_db)):
    cat = db.get(Category, category_id)
    if not cat:
        raise HTTPException(404, "Category not found")
    db.delete(cat)
    db.commit()


# --------------------------------------------------------------------------- #
# Rules
# --------------------------------------------------------------------------- #
@router.get("/rules", response_model=list[RuleOut])
def list_rules(db: Session = Depends(get_db)):
    return list(db.scalars(select(Rule).order_by(Rule.priority.desc(), Rule.id)))


@router.post("/rules", response_model=RuleOut, status_code=201)
def create_rule(payload: RuleCreate, db: Session = Depends(get_db)):
    if not db.get(Category, payload.category_id):
        raise HTTPException(400, "category_id does not exist")
    rule = Rule(**payload.model_dump())
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


@router.delete("/rules/{rule_id}", status_code=204)
def delete_rule(rule_id: int, db: Session = Depends(get_db)):
    rule = db.get(Rule, rule_id)
    if not rule:
        raise HTTPException(404, "Rule not found")
    db.delete(rule)
    db.commit()


@router.post("/rules/apply")
def apply_rules(only_uncategorized: bool = True, db: Session = Depends(get_db)):
    """Re-run all rules over existing transactions."""
    changed = recategorize_all(db, only_uncategorized=only_uncategorized)
    return {"changed": changed}
