package com.neuralai.agent.core.graph

interface GraphNode {
    val name: String
    suspend fun process(state: GraphState): GraphState
}
