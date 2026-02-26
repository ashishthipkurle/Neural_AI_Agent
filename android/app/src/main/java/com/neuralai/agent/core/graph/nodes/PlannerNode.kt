package com.neuralai.agent.core.graph.nodes

import com.neuralai.agent.core.graph.GraphNode
import com.neuralai.agent.core.graph.GraphState
import com.neuralai.agent.core.llm.OllamaClient
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class PlannerNode @Inject constructor(
    private val ollamaClient: OllamaClient
) : GraphNode {
    override val name = "planner"

    override suspend fun process(state: GraphState): GraphState {
        val planPrompt = """
            Break the following user request into a numbered list of 2-4 simple, actionable sub-goals. 
            Each sub-goal should start with a verb (Search, Execute, Summarize, etc.).
            User Request: "${state.userInput}"
        """.trimIndent()

        val response = ollamaClient.chat(
            model = "qwen2.5:0.5b",
            systemPrompt = "You are a task planner. Output only a numbered list of sub-goals, nothing else.",
            userMessage = planPrompt
        )

        // Parse numbered list into individual steps
        val steps = response.lines()
            .map { it.trim() }
            .filter { it.isNotEmpty() && (it[0].isDigit() || it.startsWith("-")) }
            .map { it.replace(Regex("^\\d+\\.\\s*"), "").replace(Regex("^-\\s*"), "").trim() }
            .ifEmpty { listOf("Research the topic", "Summarize findings") }

        return state.copy(plan = steps)
    }
}
