"""ORM models."""

from __future__ import annotations

import datetime as dt
from enum import StrEnum

from sqlalchemy import (
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


class MealSlot(StrEnum):
    breakfast = "breakfast"
    lunch = "lunch"
    dinner = "dinner"


SLOT_ORDER = [MealSlot.breakfast, MealSlot.lunch, MealSlot.dinner]


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(80))
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    pantry_items: Mapped[list[PantryItem]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    recipes: Mapped[list[Recipe]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class PantryItem(Base):
    __tablename__ = "pantry_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    quantity: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(20), default="")
    expires_on: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped[User] = relationship(back_populates="pantry_items")

    def days_left(self, today: dt.date) -> int | None:
        if self.expires_on is None:
            return None
        return (self.expires_on - today).days


class Recipe(Base):
    __tablename__ = "recipes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(160))
    servings: Mapped[int] = mapped_column(Integer, default=2)
    instructions: Mapped[str] = mapped_column(Text, default="")
    # How the recipe got here: typed in, imported by Claude, or by the local parser.
    source: Mapped[str] = mapped_column(String(20), default="manual")
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped[User] = relationship(back_populates="recipes")
    ingredients: Mapped[list[RecipeIngredient]] = relationship(
        back_populates="recipe",
        cascade="all, delete-orphan",
        order_by="RecipeIngredient.position",
    )


class RecipeIngredient(Base):
    __tablename__ = "recipe_ingredients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    recipe_id: Mapped[int] = mapped_column(ForeignKey("recipes.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    name: Mapped[str] = mapped_column(String(120))
    quantity: Mapped[float | None] = mapped_column(Float, nullable=True)
    unit: Mapped[str] = mapped_column(String(20), default="")
    note: Mapped[str] = mapped_column(String(160), default="")

    recipe: Mapped[Recipe] = relationship(back_populates="ingredients")


class MealPlanEntry(Base):
    __tablename__ = "meal_plan_entries"
    __table_args__ = (UniqueConstraint("user_id", "day", "slot", "recipe_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    day: Mapped[dt.date] = mapped_column(Date, index=True)
    slot: Mapped[str] = mapped_column(String(12))
    recipe_id: Mapped[int] = mapped_column(ForeignKey("recipes.id", ondelete="CASCADE"))
    servings: Mapped[int] = mapped_column(Integer, default=2)

    recipe: Mapped[Recipe] = relationship()
