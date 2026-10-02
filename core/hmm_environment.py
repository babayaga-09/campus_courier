import numpy as np

class WarehouseHMMEnvironment:
    """
    Instructor Scaffold for the Hidden Markov Model Laboratory.
    Maps a 2D Warehouse Grid into a flattened 1D State Space for matrix operations.
    """
    def __init__(self, grid_map: str, sensor_accuracy: float = 0.8):
        lines = [line.strip() for line in grid_map.strip().split('\n')]
        self.height = len(lines)
        self.width = len(lines[0])
        self.num_states = self.height * self.width
        
        # Parse grid map
        self.grid = np.zeros((self.height, self.width), dtype=int)
        for r in range(self.height):
            for c in range(self.width):
                if lines[r][c] == '#':
                    self.grid[r, c] = 1  # Obstacle / Wall
        
        self.sensor_accuracy = sensor_accuracy
        
        # Action space: 0=North, 1=South, 2=East, 3=West
        self.actions = [0, 1, 2, 3]
        self.T = self._build_transition_matrix()
        self.E = self._build_emission_matrix()

    def coord_to_state(self, r: int, c: int) -> int:
        """Converts 2D grid coordinate to 1D vector index."""
        return r * self.width + c

    def state_to_coord(self, state: int) -> tuple[int, int]:
        """Converts 1D vector index to 2D grid coordinate."""
        return (state // self.width, state % self.width)

    def is_walkable(self, r: int, c: int) -> bool:
        if 0 <= r < self.height and 0 <= c < self.width:
            return self.grid[r, c] == 0
        return False

    def _build_transition_matrix(self) -> np.ndarray:
        """
        Builds Transition Tensor T[Action, From_State, To_State].
        Physical Slip Model: 80% chance intended move succeeds,
        10% chance slip right, 10% chance slip left.
        If hitting a wall, the robot stays in place.
        """
        T = np.zeros((4, self.num_states, self.num_states))
        moves = [(-1, 0), (1, 0), (0, 1), (0, -1)]  # N, S, E, W
        slips = [
          [2, 3],  # N (0) slips E (2), W (3)
          [2, 3],  # S (1) slips E (2), W (3)
          [0, 1],  # E (2) slips N (0), S (1)
          [0, 1]   # W (3) slips N (0), S (1)
               ]

        for s in range(self.num_states):
            r, c = self.state_to_coord(s)
            if not self.is_walkable(r, c):
                continue  # Wall states stay zero probability

            for a in range(4):
                # 1. Intended direction (80% probability)
                dr, dc = moves[a]
                nr, nc = (r + dr, c + dc) if self.is_walkable(r + dr, c + dc) else (r, c)
                T[a, s, self.coord_to_state(nr, nc)] += 0.8

                # 2. Slip directions (10% probability each)
                for slip_a in slips[a]: # Directly iterate over the two slip action integers
                    s_dr, s_dc = moves[slip_a]
                    snr, snc = (r + s_dr, c + s_dc) if self.is_walkable(r + s_dr, c + s_dc) else (r, c)
                    T[a, s, self.coord_to_state(snr, snc)] += 0.1

        return T

    def _build_emission_matrix(self) -> np.ndarray:
        """
        Builds Sensor Emission Matrix E[Observation, State].
        Observation = Number of adjacent walls (0, 1, 2, 3, or 4).
        Corrupted array emits true count with probability `sensor_accuracy`,
        and nearby counts with remaining probability.
        """
        num_observations = 5  # Wall counts 0 to 4
        E = np.zeros((num_observations, self.num_states))
        moves = [(-1, 0), (1, 0), (0, 1), (0, -1)]

        for s in range(self.num_states):
            r, c = self.state_to_coord(s)
            if not self.is_walkable(r, c):
                continue

            # Count true surrounding wall obstacles
            wall_count = 0
            for dr, dc in moves:
                if not self.is_walkable(r + dr, c + dc):
                    wall_count += 1

            for obs in range(num_observations):
                if obs == wall_count:
                    E[obs, s] = self.sensor_accuracy
                else:
                    # Uniform noisy distribution over incorrect readings
                    E[obs, s] = (1.0 - self.sensor_accuracy) / (num_observations - 1)

        return E
