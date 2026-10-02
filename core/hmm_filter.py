import numpy as np

class HMMStateEstimator:
    def __init__(self, num_states: int, transition_tensor: np.ndarray, emission_matrix: np.ndarray):
        """
        Args:
            num_states: Total discrete grid cells N.
            transition_tensor: Shape (4, N, N) -> T[Action, From_State, To_State]
            emission_matrix: Shape (5, N) -> E[Observation, State]
        """
        self.num_states = num_states
        self.T = transition_tensor
        self.E = emission_matrix
        
        # CORRECTED: Initialize Uniform Prior strictly over walkable states.
        # We can identify walkable states because their emission probabilities sum to > 0.
        valid_states_mask = np.sum(self.E, axis=0) > 0
        valid_state_count = np.sum(valid_states_mask)
        
        self.belief_state = np.zeros(num_states, dtype=float)
        if valid_state_count > 0:
            self.belief_state[valid_states_mask] = 1.0 / valid_state_count
        else:
            # Fallback if the map is completely broken
            self.belief_state = np.ones(num_states, dtype=float) / num_states

    def predict(self, action: int) -> np.ndarray:
        """
        Step 1: Time Update (Prediction)
        Applies transition dynamics to project belief forward in time.
        
        Returns:
            Predicted probability array across all states.
        """
        # TODO: Compute predicted belief vector using matrix vector product:
        # P(X_t | e_{1:t-1}) = sum_{X_{t-1}} P(X_t | X_{t-1}, action) * P(X_{t-1} | e_{1:t-1})
        # Hint: Use np.dot or matrix multiplication with self.T[action]
        
        predicted_belief = self.belief_state @ self.T[action] # Placeholder
        return predicted_belief

    def update(self, observation: int, predicted_belief: np.ndarray) -> np.ndarray:
        """
        Step 2: Measurement Update (Correction) & Normalization
        Incorporate noisy sensor reading to prune state space.
        
        Returns:
            Updated and normalized posterior belief vector.
        """
        # TODO:
        # 1. Element-wise multiply predicted_belief by likelihood vector self.E[observation]
        # 2. Compute normalization constant Z = sum(updated_belief)
        # 3. Normalize the state distribution vector
        
        updated_belief = predicted_belief * self.E[observation]
        Z = np.sum(updated_belief)
        updated_belief = updated_belief / Z # Placeholder
        return updated_belief
        
    def bayesian_filter_step(self, action: int, observation: int) -> np.ndarray:
        """Executes a full Predict-and-Update Forward Algorithm cycle."""
        predicted = self.predict(action)
        self.belief_state = self.update(observation, predicted)
        return self.belief_state

    def get_most_likely_state(self) -> int:
        """Returns the state index with highest posterior probability."""
        return int(np.argmax(self.belief_state))
