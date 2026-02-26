package com.neuralai.agent.core.graph.nodes

import com.neuralai.agent.core.graph.GraphNode
import com.neuralai.agent.core.graph.GraphState
import com.neuralai.agent.core.skills.research.WebSearchSkill
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class ResearcherNode @Inject constructor(
    private val webSearchSkill: WebSearchSkill
) : GraphNode {
    override val name = "researcher"

    override suspend fun process(state: GraphState): GraphState {
        // Extract a search query from the user input
        val query = state.userInput.lowercase()
            .replace("research", "")
            .replace("search", "")
            .replace("find", "")
            .replace("for", "")
            .trim()

        val results = webSearchSkill.search(query)
        if (results.isEmpty()) {
            return state.copy(
                researchResults = "No search results found for: $query",
                executionLog = state.executionLog.apply { add("Researcher: No results for '$query'") }
            )
        }

        // Fetch the top result page
        val topResult = results.first()
        val pageText = webSearchSkill.fetchPage(topResult.url)

        val researchSummary = "Source: ${topResult.title}\nURL: ${topResult.url}\n\n$pageText"

        return state.copy(
            researchResults = researchSummary,
            executionLog = state.executionLog.apply { add("Researcher: Fetched '${topResult.title}'") }
        )
    }
}
