package com.neuralai.agent.core.graph

import com.neuralai.agent.core.graph.nodes.*
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class AgentGraph @Inject constructor(
    private val intentNode: IntentNode,
    private val policyNode: PolicyNode,
    private val supervisorNode: SupervisorNode,
    private val plannerNode: PlannerNode,
    private val researcherNode: ResearcherNode,
    private val executorNode: ExecutorNode,
    private val synthesizerNode: SynthesizerNode
) {
    suspend fun process(input: String): String {
        var state = GraphState(userInput = input)

        // Phase 1: Classify + Assess
        state = intentNode.process(state)
        state = policyNode.process(state)

        // Phase 2: Route through Supervisor loop
        state = supervisorNode.process(state)

        while (!state.isComplete && state.currentStep < state.maxSteps) {
            state = when (state.nextAgent) {
                "planner" -> plannerNode.process(state)
                "researcher" -> researcherNode.process(state)
                "executor" -> executorNode.process(state)
                "synthesizer" -> synthesizerNode.process(state)
                else -> break
            }
            // Re-evaluate after each node
            if (!state.isComplete) {
                state = supervisorNode.process(state)
            }
        }

        // Phase 3: Final synthesis if not already done
        if (state.finalResponse.isEmpty()) {
            state = synthesizerNode.process(state)
        }

        return state.finalResponse
    }
}
