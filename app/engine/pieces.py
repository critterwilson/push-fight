"""
Piece model for Push Fight: BJJ Edition.

Each player controls 5 pieces with two distinct shapes:
  - 3 Square pieces (sleeve, lapel, belt) — can initiate pushes
  - 2 Round pieces (neck, joint)          — cannot push, only move

Piece names follow a Brazilian Jiu-Jitsu theme, reflecting grip points
and control positions used in the martial art.

This module provides serialization (to_dict / from_dict) for persisting
game state to JSON and transmitting it over WebSocket.
"""


class Piece:
    """A single game piece belonging to one team.

    Attributes:
        team:      'white' or 'black' — which player owns this piece.
        shape:     'square' or 'round' — determines push eligibility.
        is_square: Convenience boolean; True when the piece can push.
        name:      Human-readable BJJ-themed identifier (e.g. 'sleeve').
    """

    def __init__(self, team: str, shape: str, name: str | None = None):
        self.team = team          # 'white' or 'black'
        self.shape = shape        # 'square' (pusher) or 'round' (non-pusher)
        self.is_square = (shape == 'square')
        self.name = name          # BJJ name: sleeve, lapel, belt, neck, joint

    def __repr__(self) -> str:
        """Short two-character representation for console debugging.

        Format: <Team initial><Shape initial>  e.g. 'WS' = White Square.
        """
        return f"{self.team[0].upper()}{self.shape[0].upper()}"

    def to_dict(self) -> dict:
        """Serialize to a plain dict for JSON / WebSocket payloads."""
        return {
            'team': self.team,
            'shape': self.shape,
            'name': self.name,
        }

    @staticmethod
    def from_dict(data: dict | None) -> "Piece | None":
        """Deserialize from a dict (inverse of to_dict).

        Returns None when *data* is None, which represents an empty cell.
        """
        if data is None:
            return None
        return Piece(data['team'], data['shape'], name=data.get('name'))
