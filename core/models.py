from dataclasses import dataclass

@dataclass
class Node:
    """Represents a grid cell for forklift navigation"""
    x: int
    y: int
    g: float = float('inf')  # Cost from start
    h: float = float('inf')  # Heuristic to goal
    f: float = float('inf')  # Total cost
    parent: 'Node' = None
    
    def __lt__(self, other):
        return self.f < other.f

    def __eq__(self, other):
        if not isinstance(other, Node):
            return False
        return self.x == other.x and self.y == other.y

    def __hash__(self):
        return hash((self.x, self.y))
    
   
