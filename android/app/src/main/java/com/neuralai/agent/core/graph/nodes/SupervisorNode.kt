package com.neuralai.agent.core.graph.nodes

import com.neuralai.agent.core.graph.GraphNode
import com.neuralai.agent.core.graph.GraphState
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class SupervisorNode @Inject constructor() : GraphNode {
    override val name = "supervisor"

    override suspend fun process(state: GraphState): GraphState {
        // Safety check: max iterations
        if (state.currentStep >= state.maxSteps) {
            return state.copy(isComplete = true, nextAgent = "synthesizer")
        }

        val intent = state.intent.uppercase()

        // If we have no plan yet, route to planner for complex intents
        if (state.plan.isEmpty() && intent in listOf("WEB_SEARCH", "CHAT", "SYSTEM_CONTROL")) {
            return state.copy(nextAgent = "planner", currentStep = state.currentStep + 1)
        }

        // If plan exists but research not started, route to researcher
        if (state.plan.isNotEmpty() && state.researchResults.isEmpty() && 
            state.plan.any { it.lowercase().contains("search") || it.lowercase().contains("research") }) {
            return state.copy(nextAgent = "researcher", currentStep = state.currentStep + 1)
        }

        // If there are execution tasks remaining
        if (state.plan.isNotEmpty() && state.plan.any { it.lowercase().contains("execute") || it.lowercase().contains("action") }) {
            if (state.executionLog.size < state.plan.count { it.lowercase().contains("execute") || it.lowercase().contains("action") }) {
                return state.copy(nextAgent = "executor", currentStep = state.currentStep + 1)
            }
        }

        // Otherwise, synthesize
        return state.copy(isComplete = true, nextAgent = "synthesizer")
    }
}
