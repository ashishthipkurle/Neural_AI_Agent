package com.neuralai.agent.ui.navigation

import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Code
import androidx.compose.material.icons.filled.DateRange
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.List
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.navigation.NavHostController
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import com.neuralai.agent.ui.MainViewModel
import com.neuralai.agent.ui.screens.*
import com.neuralai.agent.core.skills.vision.VisionEngine

object Destinations {
    const val MAIN = "main" // The "Agent" globe
    const val DASHBOARD = "dashboard"
    const val SETTINGS = "settings"
    const val HISTORY = "history"
    const val CAMERA = "camera"
    const val TRADING = "trading"
    const val CODE_EDITOR = "code_editor"
}

data class BottomNavItem(
    val title: String,
    val route: String,
    val icon: ImageVector
)

@Composable
fun AppNavigation(
    mainViewModel: MainViewModel = hiltViewModel()
) {
    val navController = rememberNavController()

    val aiState by mainViewModel.aiState.collectAsState()
    val systemStatus by mainViewModel.systemStatus.collectAsState()
    val messages by mainViewModel.messages.collectAsState(initial = emptyList())
    val isProcessing by mainViewModel.isProcessing.collectAsState()
    val currentSpeechText by mainViewModel.currentSpeechText.collectAsState()
    val audioRms by mainViewModel.audioRms.collectAsState()
    val isWakeListening by mainViewModel.isWakeListening.collectAsState()
    
    val visionEngine = mainViewModel.visionEngine

    val items = listOf(
        BottomNavItem("Agent", Destinations.MAIN, Icons.Default.Home),
        BottomNavItem("Trading", Destinations.TRADING, Icons.Default.DateRange),
        BottomNavItem("Code", Destinations.CODE_EDITOR, Icons.Default.Code)
    )

    Scaffold(
        bottomBar = {
            NavigationBar(
                containerColor = com.neuralai.agent.ui.theme.NeuralDark,
                contentColor = com.neuralai.agent.ui.theme.CyanGlow,
                modifier = Modifier.height(56.dp),
                tonalElevation = 0.dp
            ) {
                val navBackStackEntry by navController.currentBackStackEntryAsState()
                val currentRoute = navBackStackEntry?.destination?.route

                items.forEach { item ->
                    NavigationBarItem(
                        icon = { Icon(item.icon, contentDescription = item.title, modifier = Modifier.size(20.dp)) },
                        label = { Text(item.title, fontSize = 10.sp) },
                        selected = currentRoute == item.route,
                        colors = NavigationBarItemDefaults.colors(
                            selectedIconColor = com.neuralai.agent.ui.theme.NeuralDark,
                            selectedTextColor = com.neuralai.agent.ui.theme.CyanGlow,
                            indicatorColor = com.neuralai.agent.ui.theme.CyanGlow,
                            unselectedIconColor = com.neuralai.agent.ui.theme.SlateText,
                            unselectedTextColor = com.neuralai.agent.ui.theme.SlateText
                        ),
                        onClick = {
                            navController.navigate(item.route) {
                                navController.graph.startDestinationRoute?.let { route ->
                                    popUpTo(route) { saveState = true }
                                }
                                launchSingleTop = true
                                restoreState = true
                            }
                        }
                    )
                }
            }
        }
    ) { innerPadding ->
        NavHost(
            navController = navController,
            startDestination = Destinations.MAIN,
            modifier = Modifier.padding(innerPadding)
        ) {
            composable(Destinations.MAIN) {
                MainScreen(
                    aiState = aiState,
                    systemStatus = systemStatus,
                    messages = messages,
                    isProcessing = isProcessing,
                    currentSpeechText = currentSpeechText,
                    audioRms = audioRms,
                    isWakeListening = isWakeListening,
                    onSendMessage = { mainViewModel.submitCommand(it) },
                    onStopProcessing = { mainViewModel.stopProcessing() },
                    onMicClick = { mainViewModel.toggleListening() },
                    onDashboardClick = { navController.navigate(Destinations.DASHBOARD) },
                    onCameraClick = { navController.navigate(Destinations.CAMERA) },
                    onSettingsClick = { navController.navigate(Destinations.SETTINGS) },
                    onHistoryClick = { navController.navigate(Destinations.HISTORY) }
                )
            }
            
            composable(Destinations.CAMERA) {
                CameraScreen(
                    visionEngine = visionEngine,
                    onBack = { navController.popBackStack() }
                )
            }
            
            composable(Destinations.DASHBOARD) {
                DashboardScreen(onBack = { navController.popBackStack() })
            }
            
            composable(Destinations.SETTINGS) {
                SettingsScreen(onBack = { navController.popBackStack() })
            }
            
            composable(Destinations.HISTORY) {
                HistoryScreen(messages = messages, onBack = { navController.popBackStack() })
            }
            
            composable(Destinations.TRADING) {
                TradingScreen(onBack = { navController.popBackStack() })
            }
            
            composable(Destinations.CODE_EDITOR) {
                CodeEditorScreen()
            }
        }
    }
}
