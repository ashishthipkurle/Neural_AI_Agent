package com.neuralai.agent.core.graph.nodes

import com.neuralai.agent.core.IntentParser
import com.neuralai.agent.core.graph.GraphNode
import com.neuralai.agent.core.graph.GraphState
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class IntentNode @Inject constructor(
    private val intentParser: IntentParser
) : GraphNode {
    override val name = "intent"

    override suspend fun process(state: GraphState): GraphState {
        val intent = intentParser.parse(state.userInput)
        return state.copy(intent = intent.name)
    }
}
