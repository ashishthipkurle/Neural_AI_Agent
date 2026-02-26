 package com.neuralai.agent.ui.components

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.onSizeChanged
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlin.math.sqrt
import kotlin.random.Random

// Represents a single floating node in the geometric background
data class Node(
    var x: Float,
    var y: Float,
    var vx: Float,
    var vy: Float
)

@Composable
fun GeometricBackground(modifier: Modifier = Modifier) {
    var width by remember { mutableFloatStateOf(0f) }
    var height by remember { mutableFloatStateOf(0f) }

    // Initialize nodes only once the layout gets a size
    var nodes by remember { mutableStateOf<List<Node>>(emptyList()) }
    var frameTicker by remember { mutableStateOf(0) }

    LaunchedEffect(width, height) {
        if (width > 0 && height > 0 && nodes.isEmpty()) {
            val initialNodes = List(30) {
                Node(
                    x = Random.nextFloat() * width,
                    y = Random.nextFloat() * height,
                    vx = (Random.nextFloat() - 0.5f) * 2f, // Speed multiplier
                    vy = (Random.nextFloat() - 0.5f) * 2f
                )
            }
            nodes = initialNodes
        }
    }

    LaunchedEffect(Unit) {
        while (isActive) {
            delay(16) // ~60fps
            if (width > 0 && height > 0 && nodes.isNotEmpty()) {
                // Update positions
                for (node in nodes) {
                    node.x += node.vx
                    node.y += node.vy

                    // Bounce off walls
                    if (node.x < 0 || node.x > width) node.vx *= -1
                    if (node.y < 0 || node.y > height) node.vy *= -1
                }
                // Trigger recompose
                frameTicker++
            }
        }
    }

    Canvas(
        modifier = modifier
            .fillMaxSize()
            .onSizeChanged {
                width = it.width.toFloat()
                height = it.height.toFloat()
            }
    ) {
        // Tie to frameTicker to force recomposition on tick
        val tick = frameTicker
        
        // Deep black space background
        drawRect(color = Color(0xFF050505))

        if (nodes.isEmpty()) return@Canvas

        val connectDistance = 300f

        // Draw connecting lines
        for (i in nodes.indices) {
            for (j in i + 1 until nodes.size) {
                val dx = nodes[i].x - nodes[j].x
                val dy = nodes[i].y - nodes[j].y
                val distSq = (dx * dx) + (dy * dy)

                if (distSq < (connectDistance * connectDistance)) {
                    val opacity = 1f - (sqrt(distSq) / connectDistance)
                    val lineAlpha = (opacity * 0.15f).coerceIn(0f, 1f) // Max 15% opacity
                    drawLine(
                        color = Color.White.copy(alpha = lineAlpha),
                        start = Offset(nodes[i].x, nodes[i].y),
                        end = Offset(nodes[j].x, nodes[j].y),
                        strokeWidth = 1f
                    )
                }
            }
        }

        // Draw nodes
        for (node in nodes) {
            drawCircle(
                color = Color.White.copy(alpha = 0.2f),
                radius = 3f,
                center = Offset(node.x, node.y)
            )
        }
    }
}
