package com.neuralai.agent.core.graph.nodes

import com.neuralai.agent.core.graph.GraphNode
import com.neuralai.agent.core.graph.GraphState
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class PolicyNode @Inject constructor() : GraphNode {
    override val name = "policy"

    override suspend fun process(state: GraphState): GraphState {
        val lower = state.userInput.lowercase()
        
        val risk = when {
            // High risk: destructive actions
            lower.contains("delete") || lower.contains("wipe") || lower.contains("format") -> "HIGH"
            // Medium risk: phone actions
            lower.contains("call") || lower.contains("sms") || lower.contains("send") -> "MEDIUM"
            // Low risk: everything else
            else -> "LOW"
        }
        return state.copy(riskLevel = risk)
    }
}
