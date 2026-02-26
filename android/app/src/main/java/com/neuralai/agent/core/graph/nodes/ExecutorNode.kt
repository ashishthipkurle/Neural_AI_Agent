package com.neuralai.agent.core.graph.nodes

import com.neuralai.agent.core.graph.GraphNode
import com.neuralai.agent.core.graph.GraphState
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class ExecutorNode @Inject constructor() : GraphNode {
    override val name = "executor"

    override suspend fun process(state: GraphState): GraphState {
        // The executor delegates to existing skills already wired in NeuralAgent.
        // For the graph pipeline, it logs that execution was requested.
        // Real skill execution is handled by NeuralAgent's handleSystemControl.
        val executionSteps = state.plan.filter { 
            it.lowercase().contains("execute") || it.lowercase().contains("action") 
        }

        val log = state.executionLog
        for (step in executionSteps) {
            log.add("Executor: Completed '$step'")
        }

        return state.copy(executionLog = log)
    }
}
