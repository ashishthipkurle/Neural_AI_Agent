package com.neuralai.agent.core.graph

data class GraphState(
    val userInput: String = "",
    val intent: String = "",
    val riskLevel: String = "LOW",       // LOW, MEDIUM, HIGH
    val plan: List<String> = emptyList(), // Sub-goals
    val researchResults: String = "",
    val executionLog: MutableList<String> = mutableListOf(),
    val finalResponse: String = "",
    val nextAgent: String = "",           // planner, researcher, executor, synthesizer
    val isComplete: Boolean = false,
    val currentStep: Int = 0,
    val maxSteps: Int = 5                 // Safety: prevent infinite loops
)
