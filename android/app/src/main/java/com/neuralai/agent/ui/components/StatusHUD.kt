package com.neuralai.agent.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.neuralai.agent.core.AIState
import com.neuralai.agent.ui.theme.CyanGlow
import com.neuralai.agent.ui.theme.NeuralBlack
import com.neuralai.agent.ui.theme.PurpleAccent

@Composable
fun StatusHUD(
    aiState: AIState,
    systemStatus: String,
    modifier: Modifier = Modifier
) {
    val statusColor = when (aiState) {
        AIState.IDLE -> CyanGlow
        AIState.THINKING -> PurpleAccent
        AIState.LISTENING -> Color.Green
        AIState.SPEAKING -> CyanGlow
        AIState.EXECUTING -> Color.White
        AIState.ERROR -> Color.Red
    }

    Row(
        modifier = modifier
            .fillMaxWidth()
            .background(NeuralBlack.copy(alpha = 0.7f))
            .padding(horizontal = 16.dp, vertical = 8.dp),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically
    ) {
        // System Info
        Column {
            Text(
                text = "NEURAL AGENT // ANDROID_NATIVE",
                color = CyanGlow,
                fontSize = 12.sp,
                fontWeight = FontWeight.Bold,
                letterSpacing = 1.sp
            )
            Text(
                text = "SYSTEM: $systemStatus",
                color = Color.White.copy(alpha = 0.7f),
                fontSize = 10.sp,
                letterSpacing = 0.5.sp
            )
        }

        // State Indicator
        Row(
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            Text(
                text = aiState.name,
                color = statusColor,
                fontSize = 12.sp,
                fontWeight = FontWeight.Bold,
                letterSpacing = 1.sp
            )
            
            Box(
                modifier = Modifier
                    .size(8.dp)
                    .clip(CircleShape)
                    .background(statusColor)
            )
        }
    }
}
