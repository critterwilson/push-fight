"""
Pydantic request and response models for the Push Fight API.
"""

from typing import List, Optional, Literal
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Requests
# ---------------------------------------------------------------------------

class CreateGameRequest(BaseModel):
    mode: Literal["pvp", "pvai"] = "pvp"
    difficulty: Literal["easy", "medium", "hard"] = "medium"
    player_color: Literal["white", "black"] = "white"


class MoveRequest(BaseModel):
    from_pos: List[int] = Field(..., min_length=2, max_length=2)  # [y, x]
    to_pos: List[int] = Field(..., min_length=2, max_length=2)    # [y, x]


class PushRequest(BaseModel):
    piece: List[int] = Field(..., min_length=2, max_length=2)      # [y, x]
    direction: List[int] = Field(..., min_length=2, max_length=2)  # [dy, dx]


class SetupPlaceRequest(BaseModel):
    y: int
    x: int
    name: str  # piece name: sleeve | lapel | belt | neck | joint


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=500)


# ---------------------------------------------------------------------------
# Responses
# ---------------------------------------------------------------------------

class PieceResponse(BaseModel):
    team: str    # 'white' | 'black'
    shape: str   # 'square' | 'round'


class CellResponse(BaseModel):
    y: int
    x: int
    kill_zone: bool
    piece: Optional[PieceResponse]
    is_anchor: bool


class PiecesPushedOff(BaseModel):
    squares: int
    rounds: int


class GameStateResponse(BaseModel):
    session_id: str
    board: List[List[CellResponse]]   # [row][col]
    current_player: str
    moves_made: int
    push_completed: bool
    can_move: bool
    can_push: bool
    game_over: bool
    winner: Optional[str]
    pieces_pushed_off: dict           # {'white': {...}, 'black': {...}}
    mode: str
    ai_team: Optional[str]
    is_ai_turn: bool


class ActionResponse(BaseModel):
    success: bool
    message: str
    state: GameStateResponse


class ValidMovesResponse(BaseModel):
    moves: List[List[int]]  # list of [y, x]


class ValidPushesResponse(BaseModel):
    directions: List[List[int]]  # list of [dy, dx]


class SaveListResponse(BaseModel):
    saves: List[str]


class HealthResponse(BaseModel):
    status: str = "ok"
