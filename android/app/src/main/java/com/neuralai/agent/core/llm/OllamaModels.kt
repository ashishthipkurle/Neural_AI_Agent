package com.neuralai.agent.core.llm

import kotlinx.serialization.Serializable

@Serializable
data class ChatMsg(
    val role: String,
    val content: String,
    val images: List<String>? = null
)

@Serializable
data class ChatRequest(
    val model: String,
    val messages: List<ChatMsg>,
    val stream: Boolean = false,
    val options: Map<String, String>? = null
)

@Serializable
data class ChatResponse(
    val model: String,
    val created_at: String,
    val message: ChatMsg,
    val done: Boolean,
    val total_duration: Long? = null,
    val load_duration: Long? = null,
    val prompt_eval_count: Int? = null,
    val prompt_eval_duration: Long? = null,
    val eval_count: Int? = null,
    val eval_duration: Long? = null
)
