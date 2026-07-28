from typing import Any

from sqlalchemy import Boolean, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from lotscope.core.db import Base
from lotscope.core.mixins import TimestampMixin


class UnderwritingProfile(Base, TimestampMixin):
    __tablename__ = "underwriting_profile"
    __table_args__ = (UniqueConstraint("owner_id", "name", name="uq_underwriting_profile_name"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("app_user.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    assumptions: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    buy_box: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
