"""아이템 Service — Core↔DB 연결, EventBus 통신

architecture.md: Service → Core, Service → DB 허용
Service → Service 금지, EventBus 경유
"""

import json
import uuid

from sqlalchemy.orm import Session

from src.core.event_bus import EventBus, GameEvent
from src.core.event_types import EventTypes
from src.core.item.axiom_mapping import AxiomTagMapping
from src.core.item.constraints import build_item_constraints
from src.core.item.durability import apply_durability_loss, get_durability_ratio
from src.core.item.gift import calculate_gift_affinity
from src.core.item.inventory import (
    calculate_current_bulk,
    calculate_inventory_capacity,
    can_add_item,
)
from src.core.item.models import ItemInstance, ItemPrototype
from src.core.item.registry import PrototypeRegistry
from src.core.item.trade import (
    calculate_counter_price,
    calculate_trade_price,
    evaluate_haggle,
)
from src.core.logging import get_logger
from src.db.models import PlayerModel
from src.db.models_v2 import ItemInstanceModel, ItemPrototypeModel, NPCModel

logger = get_logger(__name__)


class ItemService:
    """아이템 CRUD + 비즈니스 로직"""

    def __init__(
        self,
        db: Session,
        event_bus: EventBus,
        registry: PrototypeRegistry,
        axiom_mapping: AxiomTagMapping,
    ):
        self._db = db
        self._bus = event_bus
        self._registry = registry
        self._axiom_mapping = axiom_mapping
        self._register_event_handlers()

    def _register_event_handlers(self) -> None:
        """EventBus 구독"""
        self._bus.subscribe(EventTypes.DIALOGUE_ENDED, self._on_dialogue_ended)

    # === Prototype 관리 ===

    def get_prototype(self, item_id: str) -> ItemPrototype | None:
        """Registry에서 조회."""
        return self._registry.get(item_id)

    def sync_prototypes_to_db(self) -> int:
        """Registry → DB 동기화. 서버 시작 시 호출.
        seed_items.json의 정적 데이터를 DB에도 저장.
        반환: 동기화된 수량.
        """
        count = 0
        for proto in self._registry.get_all():
            existing = (
                self._db.query(ItemPrototypeModel)
                .filter(ItemPrototypeModel.item_id == proto.item_id)
                .first()
            )
            if existing is None:
                orm = self._prototype_to_orm(proto)
                self._db.add(orm)
                count += 1
        self._db.commit()
        logger.info("Synced %d prototypes to DB", count)
        return count

    # === Instance CRUD ===

    def create_instance(
        self,
        prototype_id: str,
        owner_type: str,
        owner_id: str,
        current_durability: int | None = None,
        acquired_turn: int = 0,
    ) -> ItemInstance:
        """아이템 인스턴스 생성 + DB 저장.
        current_durability 미지정 시 prototype.max_durability 사용.
        item_created 이벤트 발행.
        """
        proto = self._registry.get(prototype_id)
        if proto is None:
            raise ValueError(f"Unknown prototype: {prototype_id}")

        if current_durability is None:
            current_durability = proto.max_durability

        instance_id = str(uuid.uuid4())
        instance = ItemInstance(
            instance_id=instance_id,
            prototype_id=prototype_id,
            owner_type=owner_type,
            owner_id=owner_id,
            current_durability=current_durability,
            acquired_turn=acquired_turn,
        )

        orm = self._instance_to_orm(instance)
        self._db.add(orm)
        self._db.commit()

        self._bus.emit(
            GameEvent(
                event_type=EventTypes.ITEM_CREATED,
                data={
                    "instance_id": instance_id,
                    "prototype_id": prototype_id,
                    "owner_type": owner_type,
                    "owner_id": owner_id,
                    "source": "item_service",
                },
                source="item_service",
            )
        )

        logger.debug("Created item instance %s (proto=%s)", instance_id, prototype_id)
        return instance

    def get_instance(self, instance_id: str) -> ItemInstance | None:
        """인스턴스 조회."""
        orm = (
            self._db.query(ItemInstanceModel)
            .filter(ItemInstanceModel.instance_id == instance_id)
            .first()
        )
        if orm is None:
            return None
        return self._instance_to_core(orm)

    def get_instances_by_owner(
        self, owner_type: str, owner_id: str
    ) -> list[ItemInstance]:
        """소유자별 인스턴스 목록."""
        rows = (
            self._db.query(ItemInstanceModel)
            .filter(
                ItemInstanceModel.owner_type == owner_type,
                ItemInstanceModel.owner_id == owner_id,
            )
            .all()
        )
        return [self._instance_to_core(r) for r in rows]

    def count_instances(
        self, owner_type: str, owner_id: str, prototype_id: str | None = None
    ) -> int:
        """소유자별 아이템 수 (prototype 필터 선택)."""
        q = self._db.query(ItemInstanceModel).filter(
            ItemInstanceModel.owner_type == owner_type,
            ItemInstanceModel.owner_id == owner_id,
        )
        if prototype_id is not None:
            q = q.filter(ItemInstanceModel.prototype_id == prototype_id)
        return q.count()

    # === 소유권 이전 ===

    def transfer_item(
        self,
        instance_id: str,
        to_type: str,
        to_id: str,
        reason: str = "manual",
    ) -> bool:
        """아이템 소유권 이전.
        item_transferred 이벤트 발행.
        반환: 성공 여부.
        """
        orm = (
            self._db.query(ItemInstanceModel)
            .filter(ItemInstanceModel.instance_id == instance_id)
            .first()
        )
        if orm is None:
            logger.warning("Transfer failed: instance %s not found", instance_id)
            return False

        from_type = orm.owner_type
        from_id = orm.owner_id

        orm.owner_type = to_type
        orm.owner_id = to_id
        self._db.commit()

        self._bus.emit(
            GameEvent(
                event_type=EventTypes.ITEM_TRANSFERRED,
                data={
                    "instance_id": instance_id,
                    "from_type": from_type,
                    "from_id": from_id,
                    "to_type": to_type,
                    "to_id": to_id,
                    "reason": reason,
                },
                source="item_service",
            )
        )

        logger.debug(
            "Transferred %s: %s/%s → %s/%s (%s)",
            instance_id,
            from_type,
            from_id,
            to_type,
            to_id,
            reason,
        )
        return True

    # === 내구도 ===

    def use_item(self, instance_id: str) -> dict:
        """아이템 사용 → 내구도 감소.
        파괴 시 broken_result 아이템 자동 생성.
        item_broken 이벤트 발행 (파괴 시).

        Returns: apply_durability_loss 결과 dict
        """
        orm = (
            self._db.query(ItemInstanceModel)
            .filter(ItemInstanceModel.instance_id == instance_id)
            .first()
        )
        if orm is None:
            raise ValueError(f"Instance not found: {instance_id}")

        instance = self._instance_to_core(orm)
        proto = self._registry.get(instance.prototype_id)
        if proto is None:
            raise ValueError(f"Prototype not found: {instance.prototype_id}")

        result = apply_durability_loss(instance, proto)

        orm.current_durability = instance.current_durability
        self._db.commit()

        if result["broken"]:
            self._bus.emit(
                GameEvent(
                    event_type=EventTypes.ITEM_BROKEN,
                    data={
                        "instance_id": instance_id,
                        "prototype_id": instance.prototype_id,
                        "owner_type": instance.owner_type,
                        "owner_id": instance.owner_id,
                        "broken_result": result["broken_result"],
                    },
                    source="item_service",
                )
            )

            if result["broken_result"]:
                self.create_instance(
                    prototype_id=result["broken_result"],
                    owner_type=instance.owner_type,
                    owner_id=instance.owner_id,
                )

            self._db.query(ItemInstanceModel).filter(
                ItemInstanceModel.instance_id == instance_id
            ).delete()
            self._db.commit()

        return result

    # === 거래 ===

    def calculate_price(
        self,
        instance_id: str,
        relationship_status: str,
        is_buying: bool,
        npc_hexaco_h: float,
    ) -> int:
        """거래가 계산. 내구도 자동 반영."""
        instance = self.get_instance(instance_id)
        if instance is None:
            raise ValueError(f"Instance not found: {instance_id}")

        proto = self._registry.get(instance.prototype_id)
        if proto is None:
            raise ValueError(f"Prototype not found: {instance.prototype_id}")

        dur_ratio = get_durability_ratio(instance, proto)
        return calculate_trade_price(
            proto.base_value, relationship_status, is_buying, npc_hexaco_h, dur_ratio
        )

    def process_haggle(
        self,
        proposed_price: int,
        calculated_price: int,
        relationship_status: str,
        npc_hexaco_a: float,
    ) -> dict:
        """흥정 처리. Returns: {"result": str, "counter_price": int|None}"""
        result = evaluate_haggle(
            proposed_price, calculated_price, relationship_status, npc_hexaco_a
        )
        counter_price = None
        if result == "counter":
            counter_price = calculate_counter_price(proposed_price, calculated_price)
        return {"result": result, "counter_price": counter_price}

    def execute_trade(
        self,
        instance_id: str,
        buyer_type: str,
        buyer_id: str,
        seller_type: str,
        seller_id: str,
        price: int,
    ) -> bool:
        """거래 실행 — 아이템 이전 + 통화 처리.
        통화는 Player/NPC의 currency 필드 (DB 직접 갱신).
        잔고 부족 시 False 반환.
        """
        buyer_currency = self._get_currency(buyer_type, buyer_id)
        if buyer_currency is None or buyer_currency < price:
            logger.info(
                "Trade failed: insufficient funds (%s/%s has %s, needs %d)",
                buyer_type,
                buyer_id,
                buyer_currency,
                price,
            )
            return False

        self._set_currency(buyer_type, buyer_id, buyer_currency - price)
        seller_currency = self._get_currency(seller_type, seller_id)
        if seller_currency is not None:
            self._set_currency(seller_type, seller_id, seller_currency + price)

        self.transfer_item(instance_id, buyer_type, buyer_id, reason="trade")
        return True

    # === 선물 ===

    def process_gift(
        self,
        instance_id: str,
        from_type: str,
        from_id: str,
        to_npc_id: str,
        npc_desire_tags: list[str],
    ) -> dict:
        """선물 처리.
        Returns: {"affinity_delta": int, "transferred": bool}
        """
        instance = self.get_instance(instance_id)
        if instance is None:
            return {"affinity_delta": 0, "transferred": False}

        proto = self._registry.get(instance.prototype_id)
        if proto is None:
            return {"affinity_delta": 0, "transferred": False}

        affinity = calculate_gift_affinity(
            proto.base_value, npc_desire_tags, list(proto.tags)
        )

        transferred = self.transfer_item(instance_id, "npc", to_npc_id, reason="gift")

        return {"affinity_delta": affinity, "transferred": transferred}

    # === Constraints ===

    def get_item_constraints(self, player_id: str) -> dict:
        """PC 보유 아이템 → Constraints dict.
        build_item_constraints()에 get_prototype 주입.
        """
        instances = self.get_instances_by_owner("player", player_id)
        return build_item_constraints(instances, self._registry.get)

    # === 인벤토리 ===

    def get_inventory_bulk(self, owner_type: str, owner_id: str) -> int:
        """소유자의 현재 bulk 합계."""
        instances = self.get_instances_by_owner(owner_type, owner_id)
        bulks = []
        for inst in instances:
            proto = self._registry.get(inst.prototype_id)
            if proto:
                bulks.append(proto.bulk)
        return calculate_current_bulk(bulks)

    def get_inventory_capacity(
        self, owner_type: str, owner_id: str, stats: dict[str, int]
    ) -> int:
        """소유자의 인벤토리 용량."""
        return calculate_inventory_capacity(stats)

    def can_add_to_inventory(
        self,
        owner_type: str,
        owner_id: str,
        prototype_id: str,
        stats: dict[str, int],
    ) -> bool:
        """아이템 추가 가능 여부."""
        proto = self._registry.get(prototype_id)
        if proto is None:
            return False
        current_bulk = self.get_inventory_bulk(owner_type, owner_id)
        capacity = calculate_inventory_capacity(stats)
        return can_add_item(current_bulk, capacity, proto.bulk)

    # === EventBus 핸들러 ===

    def _on_dialogue_ended(self, event: GameEvent) -> None:
        """대화 종료 시 거래/선물 아이템 이동 처리.
        event.data에 trade_request, gift_offered가 있으면 처리.
        Alpha에서는 예비 구현 — 실제 데이터 흐름은 dialogue_service가 전달.
        """
        data = event.data
        if not isinstance(data, dict):
            return

        trade_request = data.get("trade_request")
        if trade_request and isinstance(trade_request, dict):
            logger.debug("dialogue_ended: trade_request detected (stub)")

        gift_offered = data.get("gift_offered")
        if gift_offered and isinstance(gift_offered, dict):
            logger.debug("dialogue_ended: gift_offered detected (stub)")

    # === 통화 헬퍼 ===

    def _get_currency(self, owner_type: str, owner_id: str) -> int | None:
        """소유자의 통화 조회."""
        if owner_type == "player":
            player_row = (
                self._db.query(PlayerModel)
                .filter(PlayerModel.player_id == owner_id)
                .first()
            )
            return player_row.currency if player_row else None
        elif owner_type == "npc":
            npc_row = (
                self._db.query(NPCModel).filter(NPCModel.npc_id == owner_id).first()
            )
            return npc_row.currency if npc_row else None
        return None

    def _set_currency(self, owner_type: str, owner_id: str, amount: int) -> None:
        """소유자의 통화 설정."""
        if owner_type == "player":
            player_row = (
                self._db.query(PlayerModel)
                .filter(PlayerModel.player_id == owner_id)
                .first()
            )
            if player_row:
                player_row.currency = amount
                self._db.commit()
        elif owner_type == "npc":
            npc_row = (
                self._db.query(NPCModel).filter(NPCModel.npc_id == owner_id).first()
            )
            if npc_row:
                npc_row.currency = amount
                self._db.commit()

    # === ORM ↔ Core 변환 ===

    def _instance_to_core(self, orm: ItemInstanceModel) -> ItemInstance:
        """ORM → Core"""
        state_tags = json.loads(orm.state_tags) if orm.state_tags else []
        return ItemInstance(
            instance_id=orm.instance_id,
            prototype_id=orm.prototype_id,
            owner_type=orm.owner_type,
            owner_id=orm.owner_id,
            current_durability=orm.current_durability,
            state_tags=state_tags,
            acquired_turn=orm.acquired_turn,
            custom_name=orm.custom_name,
        )

    def _instance_to_orm(self, core: ItemInstance) -> ItemInstanceModel:
        """Core → ORM"""
        return ItemInstanceModel(
            instance_id=core.instance_id,
            prototype_id=core.prototype_id,
            owner_type=core.owner_type,
            owner_id=core.owner_id,
            current_durability=core.current_durability,
            state_tags=json.dumps(core.state_tags, ensure_ascii=False),
            acquired_turn=core.acquired_turn,
            custom_name=core.custom_name,
        )

    def _prototype_to_orm(self, core: ItemPrototype) -> ItemPrototypeModel:
        """Core → ORM (sync용)"""
        return ItemPrototypeModel(
            item_id=core.item_id,
            name_kr=core.name_kr,
            item_type=core.item_type.value,
            weight=core.weight,
            bulk=core.bulk,
            base_value=core.base_value,
            primary_material=core.primary_material,
            axiom_tags=json.dumps(core.axiom_tags, ensure_ascii=False),
            max_durability=core.max_durability,
            durability_loss_per_use=core.durability_loss_per_use,
            broken_result=core.broken_result,
            container_capacity=core.container_capacity,
            flavor_text=core.flavor_text,
            tags=json.dumps(list(core.tags), ensure_ascii=False),
            is_dynamic=False,
        )
