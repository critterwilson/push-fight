class Piece:
    def __init__(self, team, shape):
        self.team = team      # 'white' or 'black' [cite: 7]
        self.shape = shape    # 'square' or 'round' 
        self.is_square = (shape == 'square')

    def __repr__(self):
        # Useful for debugging the 2D array in the console
        return f"{self.team[0].upper()}{self.shape[0].upper()}"

    def to_dict(self):
        """Convert Piece to dictionary for JSON serialization."""
        return {
            'team': self.team,
            'shape': self.shape
        }

    @staticmethod
    def from_dict(data):
        """Create Piece from dictionary."""
        if data is None:
            return None
        return Piece(data['team'], data['shape'])
