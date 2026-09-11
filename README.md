# Satellite Edge Computing (SEC) Simulator & Scheduler

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.22711218.svg)](https://doi.org/10.5281/zenodo.22711218)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A multi-threaded, object-oriented Python simulator designed to evaluate task scheduling algorithms in a Low Earth Orbit (LEO) Satellite Edge Computing environment. This platform explicitly models the strict physical constraints of space networks, including dynamic orbital visibility, intermittent solar charging cycles, and hardware resource limits.

## Key Features

*   **Real-Time GUI:** A Tkinter-based interactive dashboard featuring a 2D orbital projection, live telemetry, system alerts, and task execution logs.
*   **Physical & Mathematical Modeling:** 
    *   **Visibility Threshold:** Euclidean distance calculations limiting uplinks to `<5000` km.
    *   **Energy Cycles:** A strict 60-second temporal loop (36s sunlight charging / 24s eclipse drain).
    *   **Resource Allocation:** A deterministic Two-Phase state machine (Reserved vs. Used) preventing CPU/Memory over-commitment.
*   **Asynchronous API:** A Flask-based REST API running on a daemon thread for non-blocking task ingestion.
*   **Data Persistence:** SQL Server integration for logging historical execution metrics and constellation configurations.

## Scheduling Strategies

The simulator evaluates and compares three distinct algorithmic approaches for computational offloading:
1.  **Heuristic (Greedy):** A localized scoring algorithm prioritizing nodes with high energy and low CPU utilization. Ultra-fast, but prone to localized resource exhaustion.
2.  **Genetic Algorithm (GA):** A global evolutionary search utilizing crossover and mutation operators to batch-process task queues, maximizing parallel execution and constellation sustainability.
3.  **Reinforcement Learning (Q-Learning):** An autonomous agent modeled via a Markov Decision Process (MDP) that iteratively learns an optimal offloading policy based on global CPU and energy states.

   
