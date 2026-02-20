"""
Pydantic request and response models for the Push Fight REST API.

These models provide automatic request validation, serialization, and
OpenAPI schema generation. They define the contract between the frontend
and backend — every API call passes through one of these models.

Request models validate incoming JSON payloads (coordinates, directions,
game configuration). Response models define the shape of outgoing data.

Note: The frontend receives camelCase JSON via state_serializer.py for
WebSocket updates.  These Pydantic models use snake_case (FastAPI
auto-converts to camelCase in OpenAPI docs but not in JSON responses).
"""

from typing import List, Optional, Literal
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Request models — incoming payloads from the frontend
# ---------------------------------------------------------------------------

class CreateGameRequest(BaseModel):
    """Configuration for starting a new game session.

    Attributes:
        mode:         'pvp' (player vs player) or 'pvai' (player vs AI).
        difficulty:   AI difficulty level (only used in pvai mode).
        player_color: Which team the human controls in pvai mode.
    """
    mode: Literal["pvp", "pvai"] = "pvp"
    difficulty: Literal["easy", "medium", "hard"] = "medium"
    player_color: Literal["white", "black"] = "white"


class MoveRequest(BaseModel):
    """Slide a piece from one cell to another.

    Coordinates are [y, x] where y=row (0–9) and x=column (0–3).
    """
    from_pos: List[int] = Field(..., min_length=2, max_length=2)
    to_pos: List[int] = Field(..., min_length=2, max_length=2)


class PushRequest(BaseModel):
    """Push with a square piece in a cardinal direction.

    Attributes:
        piece:     [y, x] position of the pushing square piece.
        direction: [dy, dx] unit vector (e.g. [1, 0] = push south).
    """
    piece: List[int] = Field(..., min_length=2, max_length=2)
    direction: List[int] = Field(..., min_length=2, max_length=2)


class SetupPlaceRequest(BaseModel):
    """Place a named piece during the setup phase.

    The piece name determines both its shape (square or round) and
    its identity for voice control (e.g. 'sleeve', 'neck').
    """
    y: int
    x: int
    name: str  # One of: sleeve, lapel, belt, neck, joint


class AskRequest(BaseModel):
    """Question for the RAG-powered AI referee."""
    question: str = Field(..., min_length=1, max_length=500)


# ---------------------------------------------------------------------------
# Response models — outgoing payloads to the frontend
# ---------------------------------------------------------------------------

class PieceResponse(BaseModel):
    """A single piece's identity on the board."""
    team: str    # 'white' or 'black'
    shape: str   # 'square' or 'round'


class CellResponse(BaseModel):
    """A single cell in the board grid."""
    y: int
    x: int
    kill_zone: bool
    piece: Optional[PieceResponse]
    is_anchor: bool


class PiecesPushedOff(BaseModel):
    """Count of eliminated pieces for one team, by shape."""
    squares: int
    rounds: int


class GameStateResponse(BaseModel):
    """Complete snapshot of a game session for the frontend.

    Includes board layout, turn state, win conditions, and AI metadata.
    """
    session_id: str
    board: List[List[CellResponse]]   # 10 rows × 4 columns
    current_player: str
    moves_made: int
    push_completed: bool
    can_move: bool
    can_push: bool
    game_over: bool
    winner: Optional[str]
    pieces_pushed_off: dict           # {'white': {...}, 'black': {...}}
    mode: str                         # 'pvp' or 'pvai'
    ai_team: Optional[str]
    is_ai_turn: bool


class ActionResponse(BaseModel):
    """Standard response for state-mutating actions (move, push, etc.)."""
    success: bool
    message: str
    state: GameStateResponse


class ValidMovesResponse(BaseModel):
    """List of valid destination coordinates for a selected piece."""
    moves: List[List[int]]  # Each element is [y, x]


class ValidPushesResponse(BaseModel):
    """List of valid push directions for a selected square piece."""
    directions: List[List[int]]  # Each element is [dy, dx]


class SaveListResponse(BaseModel):
    """List of available saved game filenames."""
    saves: List[str]


class HealthResponse(BaseModel):
    """Simple health check response."""
    status: str = "ok"
