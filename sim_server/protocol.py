"""
sim_server/protocol.py — Client-Server communication protocol definitions.
"""

from enum import Enum
from typing import Any, Dict, Optional


class CommandType(str, Enum):
    """Enumeration of client actions sent to the simulation server."""
    STEP = "STEP"
    PLAY = "PLAY"
    PAUSE = "PAUSE"
    SET_SPEED = "SET_SPEED"
    SET_POLICY = "SET_POLICY"
    SUBMIT_INTENT = "SUBMIT_INTENT"
    DIPLOMATIC_ACTION = "DIPLOMATIC_ACTION"
    SOVEREIGN_BOND = "SOVEREIGN_BOND"
    BUILD_PROJECT = "BUILD_PROJECT"
    RESEARCH_TECH = "RESEARCH_TECH"
    RECRUIT_UNIT = "RECRUIT_UNIT"
    SELECT_NATION = "SELECT_NATION"
    SELECT_REGION = "SELECT_REGION"
    ENCLOSE_PLOT = "ENCLOSE_PLOT"
    CADASTRE_TOGGLE_LAND_USE = "CADASTRE_TOGGLE_LAND_USE"
    RESTORE_COMMONS = "RESTORE_COMMONS"
    PROVINCE_DECREE = "PROVINCE_DECREE"
    FRONTIER_EXPEDITION = "FRONTIER_EXPEDITION"
    FISCAL_TRANSFER_RESOLVE = "FISCAL_TRANSFER_RESOLVE"
    PURCHASE_FOREIGN_BOND = "PURCHASE_FOREIGN_BOND"
    SET_BORDER_POLICY = "SET_BORDER_POLICY"
    SET_FACTORY_SAFETY = "SET_FACTORY_SAFETY"
    SET_TRUCK_ACT = "SET_TRUCK_ACT"
    RELOAD_WORLD = "RELOAD_WORLD"
    GET_STATE = "GET_STATE"


class ServerEvent(str, Enum):
    """Enumeration of event types broadcast from the server to clients."""
    TURN_ADVANCED = "TURN_ADVANCED"
    TICKER_MESSAGE = "TICKER_MESSAGE"
    ACTION_RESOLVED = "ACTION_RESOLVED"
    VIOLATION_DETECTED = "VIOLATION_DETECTED"
    WORLD_RESET = "WORLD_RESET"
    STATE_SNAPSHOT = "STATE_SNAPSHOT"


class CommandMessage:
    """Encapsulates a client request to the server."""
    def __init__(self, cmd_type: CommandType, payload: Optional[Dict[str, Any]] = None,
                 client_id: str = "player_1"):
        self.cmd_type = cmd_type
        self.payload = payload or {}
        self.client_id = client_id

    def to_dict(self) -> Dict[str, Any]:
        return {
            'cmd': self.cmd_type.value if isinstance(self.cmd_type, CommandType) else str(self.cmd_type),
            'payload': self.payload,
            'client_id': self.client_id
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CommandMessage':
        return cls(
            cmd_type=CommandType(data.get('cmd', CommandType.STEP)),
            payload=data.get('payload', {}),
            client_id=data.get('client_id', 'player_1')
        )
