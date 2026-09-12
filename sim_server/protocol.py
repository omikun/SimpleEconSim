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
    SELECT_NATION = "SELECT_NATION"
    SELECT_REGION = "SELECT_REGION"
    RELOAD_WORLD = "RELOAD_WORLD"


class ServerEvent(str, Enum):
    """Enumeration of event types broadcast from the server to clients."""
    TURN_ADVANCED = "TURN_ADVANCED"
    TICKER_MESSAGE = "TICKER_MESSAGE"
    ACTION_RESOLVED = "ACTION_RESOLVED"
    VIOLATION_DETECTED = "VIOLATION_DETECTED"
    WORLD_RESET = "WORLD_RESET"


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
