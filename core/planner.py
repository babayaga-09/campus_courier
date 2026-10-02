import heapq
import time
from typing import List, Tuple, Dict, Set
from models import Node
from environment import SurgicalLabEnvironment

class ForkliftPlanner:
    """A* path planner comparing different heuristics"""
    def __init__(self, environment: SurgicalLabEnvironment):
        self.env = environment
        
    def a_star(self, start: Tuple[int, int], goal: Tuple[int, int], heuristic_type: str = 'manhattan') -> Tuple[List[Tuple[int, int]], int, float]:
        start_time = time.time()
        nodes_expanded = 0
        
        # ---------------------------------------------------------
        # SETUP: We have initialized the starting node for you!
        # ---------------------------------------------------------
        start_node = Node(start[0], start[1])
        start_node.g = 0
        
        # Choose the correct heuristic based on the function argument
        if heuristic_type == 'manhattan':
            start_node.h = self.env.manhattan_distance(start[0], start[1], goal[0], goal[1])
        elif heuristic_type == 'euclidean':
            start_node.h = self.env.euclidean_distance(start[0], start[1], goal[0], goal[1])
        elif heuristic_type == 'chebyshev':
            start_node.h = self.env.chebyshev_distance(start[0], start[1], goal[0], goal[1])
        else:
            raise ValueError("Invalid heuristic")
            
        start_node.f = start_node.g + start_node.h
        
        # Data Structures you will need
        open_set = []
        heapq.heappush(open_set, start_node)
        
        closed_set: Set[Node] = set()
        open_dict: Dict[Tuple[int, int], Node] = {(start[0], start[1]): start_node}
        
        path = []
        # ---------------------------------------------------------
        # TODO 1: THE CORE LOOP
        # Loop as long as there are nodes in the open_set
        # ---------------------------------------------------------
        
        while open_set:
            # 1. Pop the node with the lowest f-score from open_set using heapq
            current = heapq.heappop(open_set)
            
            # 2. (Optional but recommended) Check if this node is stale using open_dict
            
            # 3. Check if the current node is the goal! 
            # If yes, reconstruct the path using the .parent attributes, reverse it, and return it.
            if (current.x, current.y) == goal:
                while current:
                    path.append((current.x, current.y))
                    current = current.parent
                path.reverse() # Flips list to Start -> Goal
                return path, nodes_expanded, time.time() - start_time                    


            
            # 4. Add the current node to the closed_set and increment nodes_expanded
            closed_set.add(current)
            nodes_expanded += 1

            # ---------------------------------------------------------
            # TODO 2: EVALUATING NEIGHBORS
            # ---------------------------------------------------------
            # 5. Use self.env.get_neighbors(current.x, current.y) to get valid moves

            for x,y in self.env.get_neighbors(current.x, current.y):

                if (x,y) in closed_set:
                    continue

                neighbor = Node(x, y)

                tentative_g = current.g + 1

                if((x, y) not in open_dict) or (tentative_g < open_dict[(x, y)].g):
                    if (x,y) in open_dict: 
                        neighbor = open_dict[(x, y)]
                    neighbor.parent = current
                    neighbor.g = tentative_g

                    if heuristic_type == 'manhattan': 
                        neighbor.h = self.env.manhattan_distance(x, y, goal[0], goal[1])
                    elif heuristic_type == 'euclidean': 
                        neighbor.h = self.env.euclidean_distance(x, y, goal[0], goal[1])
                    elif heuristic_type == 'chebyshev':
                        neighbor.h = self.env.chebyshev_distance(x, y, goal[0], goal[1])
                    else:
                        raise ValueError("Invalid heuristic")

                    neighbor.f = neighbor.g + neighbor.h
                    heapq.heappush(open_set, neighbor)
                    open_dict[(x, y)] = neighbor



            
            # For each neighbor:
                # a. Skip if it is already in the closed_set
                
                # b. Calculate the tentative_g score (current g + 1)
                
                # c. If it's a new node OR the tentative_g is better than its existing g:
                     # - Update its parent, g, h, and f scores
                     # - Push it to the open_set
                     # - Update the open_dict

	   # ---------------------------------------------------------
            # DUMMY RETURN: If the code reaches here without returning 
            # a real path, we return a fake one to prevent test hangs.
            # return function provides a template for what your return should contain. Please delete is once you are done. 
            # Type of return: path is a list of nodes where each node is marked by Node(x, y), where both x and y are integers. Nodes expanded is an integer. 
            # ---------------------------------------------------------
            # fake_path = [start, goal]
            # dummy_nodes_expanded = 1

            # print("Path: ", path)
            # print("Nodes Expanded:", nodes_expanded)
            # return path, nodes_expanded, time.time() - start_time                    
	
                    
        # Returns empty list if no path is found
        return [], nodes_expanded, time.time() - start_time
