"""SQLAlchemy declarative base for all ORM models."""

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import JSON


class Base(DeclarativeBase):
    """Base class for all database models."""


class MapNodeModel(Base):
    """ORM model for map nodes."""

    __tablename__ = "map_nodes"

    coordinate: Mapped[str] = mapped_column(String, primary_key=True)
    x: Mapped[int] = mapped_column(Integer, nullable=False)
    y: Mapped[int] = mapped_column(Integer, nullable=False)
    tier: Mapped[int] = mapped_column(Integer, nullable=False)
    axiom_vector: Mapped[dict] = mapped_column(JSON, nullable=False)
    sensory_data: Mapped[dict] = mapped_column(JSON, nullable=False)
    required_tags: Mapped[list] = mapped_column(JSON, default=list)
    cluster_id: Mapped[str | None] = mapped_column(String, nullable=True)
    development_level: Mapped[int] = mapped_column(Integer, default=0)
    discovered_by: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    resources: Mapped[list["ResourceModel"]] = relationship(
        "ResourceModel",
        back_populates="node",
        cascade="all, delete-orphan",
    )
    echoes: Mapped[list["EchoModel"]] = relationship(
        "EchoModel",
        back_populates="node",
        cascade="all, delete-orphan",
    )


class ResourceModel(Base):
    """ORM model for resources."""

    __tablename__ = "resources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    node_coordinate: Mapped[str] = mapped_column(
        String, ForeignKey("map_nodes.coordinate", ondelete="CASCADE"), nullable=False
    )
    resource_type: Mapped[str] = mapped_column(String, nullable=False)
    max_amount: Mapped[int] = mapped_column(Integer, nullable=False)
    current_amount: Mapped[int] = mapped_column(Integer, nullable=False)
    npc_competition: Mapped[float] = mapped_column(Float, default=0.2)

    node: Mapped["MapNodeModel"] = relationship(
        "MapNodeModel", back_populates="resources"
    )


class EchoModel(Base):
    """ORM model for echoes."""

    __tablename__ = "echoes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    node_coordinate: Mapped[str] = mapped_column(
        String, ForeignKey("map_nodes.coordinate", ondelete="CASCADE"), nullable=False
    )
    echo_type: Mapped[str] = mapped_column(String, nullable=False)
    visibility: Mapped[str] = mapped_column(String, nullable=False)
    base_dc: Mapped[int] = mapped_column(Integer, nullable=False)
    timestamp: Mapped[str] = mapped_column(String, nullable=False)
    flavor_text: Mapped[str] = mapped_column(Text, nullable=False)
    source_player_id: Mapped[str | None] = mapped_column(String, nullable=True)

    node: Mapped["MapNodeModel"] = relationship("MapNodeModel", back_populates="echoes")


class PlayerModel(Base):
    """ORM model for players."""

    __tablename__ = "players"

    player_id: Mapped[str] = mapped_column(String, primary_key=True)
    x: Mapped[int] = mapped_column(Integer, default=0)
    y: Mapped[int] = mapped_column(Integer, default=0)
    supply: Mapped[int] = mapped_column(Integer, default=20)
    fame: Mapped[int] = mapped_column(Integer, default=0)
    character_data: Mapped[dict] = mapped_column(JSON, nullable=False)
    discovered_nodes: Mapped[list] = mapped_column(JSON, default=list)
    inventory: Mapped[dict] = mapped_column(JSON, default=dict)
    equipped_tags: Mapped[list] = mapped_column(JSON, default=list)
    active_effects: Mapped[list] = mapped_column(JSON, default=list)
    investigation_penalty: Mapped[int] = mapped_column(Integer, default=0)
    last_action_time: Mapped[str | None] = mapped_column(String, nullable=True)
