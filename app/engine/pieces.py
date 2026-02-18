class Piece:
    def __init__(self, team, shape, name=None):
        self.team = team      # 'white' or 'black' [cite: 7]
        self.shape = shape    # 'square' or 'round'
        self.is_square = (shape == 'square')
        self.name = name      # e.g. 'sleeve', 'lapel', 'belt', 'choke', 'lock'

    def __repr__(self):
        # Useful for debugging the 2D array in the console
        return f"{self.team[0].upper()}{self.shape[0].upper()}"

    def to_dict(self):
        """Convert Piece to dictionary for JSON serialization."""
        return {
            'team': self.team,
            'shape': self.shape,
            'name': self.name,
        }

    @staticmethod
    def from_dict(data):
        """Create Piece from dictionary."""
        if data is None:
            return None
        return Piece(data['team'], data['shape'], name=data.get('name'))
