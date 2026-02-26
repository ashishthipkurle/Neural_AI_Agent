package com.neuralai.agent.core.graph.nodes

import com.neuralai.agent.core.graph.GraphNode
import com.neuralai.agent.core.graph.GraphState
import com.neuralai.agent.core.llm.OllamaClient
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class SynthesizerNode @Inject constructor(
    private val ollamaClient: OllamaClient
) : GraphNode {
    override val name = "synthesizer"

    override suspend fun process(state: GraphState): GraphState {
        val synthesisPrompt = buildString {
            appendLine("User originally asked: \"${state.userInput}\"")
            appendLine()
            if (state.plan.isNotEmpty()) {
                appendLine("Plan: ${state.plan.joinToString(", ")}")
            }
            if (state.researchResults.isNotEmpty()) {
                appendLine("Research data: ${state.researchResults.take(4000)}")
            }
            if (state.executionLog.isNotEmpty()) {
                appendLine("Execution log: ${state.executionLog.joinToString("; ")}")
            }
            appendLine()
            appendLine("Synthesize all the above into a clear, concise final answer for the user.")
        }

        val response = ollamaClient.chat(
            model = "qwen2.5:0.5b",
            systemPrompt = "You are a synthesis agent. Combine all research and execution data into a single, natural-sounding response. Be concise.",
            userMessage = synthesisPrompt
        )

        return state.copy(finalResponse = response, isComplete = true)
    }
}
