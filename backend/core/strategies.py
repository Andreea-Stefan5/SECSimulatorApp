import random
import math
from abc import ABC, abstractmethod

class SchedulingStrategy(ABC):
    @abstractmethod
    def schedule(self, tasks, satellites, current_time):
        """
        Decide which tasks to run on which satellites.
        Returns a list of tuples: (task, satellite)
        """
        pass

class HeuristicStrategy(SchedulingStrategy):
    """
    Greedy strategy: For each task, pick the satellite with the best score.
    Score = Energy + Free CPU.
    """
    def schedule(self, tasks, satellites, current_time):
        assignments = []
        
        for task in tasks:
            best_sat = None
            max_score = -float('inf')
            
            for sat in satellites:
                if sat.can_run(task):
                    # Score function: prioritize energy and cpu availability
                    score = sat.energy + (sat.cpu_total - sat.cpu_used) * 2
                    if score > max_score:
                        max_score = score
                        best_sat = sat
            
            if best_sat:
                assignments.append((task, best_sat))
                
        return assignments

class GeneticStrategy(SchedulingStrategy):
    """
    Genetic Algorithm:
    - Population: List of possible assignments (chromosomes).
    - Gene: Index of satellite for a task.
    - Fitness: Total tasks scheduled + Resource balance.
    """
    def schedule(self, tasks, satellites, current_time):
        if not tasks or not satellites:
            return []

        # Only consider tasks that CAN be scheduled now
        schedulable_tasks = [t for t in tasks if current_time >= t.earliest_start]
        if not schedulable_tasks:
            return []

        POP_SIZE = 20
        GENERATIONS = 5

        # Chromosome: [sat_index_or_None, sat_index_or_None, ...] for each task
        population = []
        for _ in range(POP_SIZE):
            chrom = [random.choice(satellites + [None]) for _ in schedulable_tasks]
            population.append(chrom)

        for _ in range(GENERATIONS):
            # Evaluate fitness
            fitness_scores = []
            for chrom in population:
                score = 0
                temp_sat_usage = {s.sat_id: {'cpu': s.cpu_used, 'mem': s.mem_used, 'energy': s.energy} for s in satellites}
                
                tasks_done = 0
                for i, sat in enumerate(chrom):
                    if sat is None: continue
                    
                    task = schedulable_tasks[i]
                    usage = temp_sat_usage[sat.sat_id]
                    
                    if (sat.connected and
                        usage['cpu'] + task.cpu_req <= sat.cpu_total and
                        usage['mem'] + task.mem_req <= sat.mem_total and
                        usage['energy'] >= task.energy_req):
                        
                        score += 50 # High reward for scheduling
                        usage['cpu'] += task.cpu_req
                        usage['mem'] += task.mem_req
                        usage['energy'] -= task.energy_req
                        tasks_done += 1
                    else:
                        score -= 10 # Penalyze invalid assignment in chromosome
                
                fitness_scores.append((score, chrom))
            
            # Selection (Top 50%)
            fitness_scores.sort(key=lambda x: x[0], reverse=True)
            survivors = [x[1] for x in fitness_scores[:POP_SIZE//2]]
            
            # Crossover & Mutation to refill population
            new_pop = survivors[:]
            while len(new_pop) < POP_SIZE:
                p1, p2 = random.sample(survivors, 2)
                # Crossover
                cut = random.randint(0, len(schedulable_tasks)-1)
                child = p1[:cut] + p2[cut:]
                # Mutation
                if random.random() < 0.1:
                    idx = random.randint(0, len(child)-1)
                    child[idx] = random.choice(satellites + [None])
                new_pop.append(child)
            
            population = new_pop

        # Get best solution
        best_chrom = population[0] # Sorted previously
        assignments = []
        
        
        for i, sat in enumerate(best_chrom):
            if sat:
                assignments.append((schedulable_tasks[i], sat))
                
        return assignments

class RLStrategy(SchedulingStrategy):
    """
    Reinforcement Learning (Q-Learning):
    - State: (Avg CPU Load Low/High, Avg Energy Low/High)
    - Action: Select specific Satellite
    - Reward: Task Success (+1), Failure (-1)
    
    For simplicity: We use a static Q-table here that 'learns' in memory. 
    In a real app, we'd save/load this.
    """
    def __init__(self):
        self.q_table = {} # Key: (state), Value: {sat_id: q_value}
        self.learning_rate = 0.1
        self.discount_factor = 0.9
        self.epsilon = 0.1

    def get_state(self, satellites):
        # Discretize state
        avg_cpu = sum(s.cpu_used/s.cpu_total for s in satellites) / len(satellites)
        avg_energy = sum(s.energy/s.battery_capacity for s in satellites) / len(satellites)
        
        cpu_state = "HIGH" if avg_cpu > 0.7 else "LOW"
        energy_state = "HIGH" if avg_energy > 0.5 else "LOW"
        
        return (cpu_state, energy_state)

    def schedule(self, tasks, satellites, current_time):
        assignments = []
        state = self.get_state(satellites)
        
        if state not in self.q_table:
            self.q_table[state] = {s.sat_id: 0.0 for s in satellites}

        for task in tasks:
            if current_time < task.earliest_start:
                continue

            # Epsilon-greedy
            if random.random() < self.epsilon:
                best_sat_id = random.choice([s.sat_id for s in satellites])
            else:
                best_sat_id = max(self.q_table[state], key=self.q_table[state].get)
            
            sat = next((s for s in satellites if s.sat_id == best_sat_id), None)
            
            if sat and sat.can_run(task):
                assignments.append((task, sat))
                # In strict RL we update Q-value after execution reward. 
                # Here we simulate reward immediately for successful assignment
                reward = 1
                old_q = self.q_table[state][best_sat_id]
                self.q_table[state][best_sat_id] = old_q + self.learning_rate * (reward - old_q)
            else:
                # Penalty for picking bad sat
                reward = -0.5
                if sat:
                     old_q = self.q_table[state][best_sat_id]
                     self.q_table[state][best_sat_id] = old_q + self.learning_rate * (reward - old_q)

        return assignments
