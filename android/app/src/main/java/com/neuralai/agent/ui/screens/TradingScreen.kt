package com.neuralai.agent.ui.screens

import android.annotation.SuppressLint
import android.view.MotionEvent
import android.view.ViewGroup
import android.webkit.WebChromeClient
import android.webkit.WebView
import android.webkit.WebViewClient
import android.webkit.WebResourceRequest
import android.webkit.WebSettings
import androidx.compose.animation.*
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Analytics
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.filled.Send
import androidx.compose.material.icons.filled.Visibility
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.PathEffect
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.Fill
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.nativeCanvas
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import com.neuralai.agent.ui.theme.NeuralDark
import com.neuralai.agent.ui.theme.CyanGlow
import com.neuralai.agent.ui.theme.SlateText

// ===== PC-matching color palette =====
private val TrdBg = Color(0xFF030D12)
private val TrdPanel = Color(0xFF030D12)
private val TrdBorder = Color(0x33006688)
private val TrdHeaderBg = Color(0xFF02080B)
private val TrdCyan = Color(0xFF00E5FF)
private val TrdGreen = Color(0xFF27C93F)
private val TrdRed = Color(0xFFFF5F56)
private val TrdPurple = Color(0xFFB388FF)
private val TrdText = Color(0xFFCFD8DC)
private val TrdDim = Color(0xFF546E7A)

// ===== Signal data class (matches PC OverlayCanvas.tsx OverlayMarker) =====
data class OverlaySignal(
    val type: String,           // "BUY" or "SELL"
    val entry: Float,
    val stop: Float,
    val target: Float,
    val confidence: Float,
    val state: String = "STAGED" // STAGED, LOCKED, TARGET_HIT, STOP_HIT, INVALIDATED, CLOSED
)

@SuppressLint("SetJavaScriptEnabled", "ClickableViewAccessibility")
@Composable
fun TradingScreen(
    onBack: () -> Unit
) {
    var webViewRef by remember { mutableStateOf<WebView?>(null) }
    var isLoading by remember { mutableStateOf(true) }
    var loadProgress by remember { mutableIntStateOf(0) }
    var currentUrl by remember { mutableStateOf("https://groww.in/charts/indices/nifty") }
    var urlInput by remember { mutableStateOf(currentUrl) }

    // Analysis panel state
    var showSidebar by remember { mutableStateOf(false) }
    var scanStatus by remember { mutableStateOf("READY") }
    var scanCount by remember { mutableIntStateOf(0) }
    var analysisSummary by remember { mutableStateOf("Waiting for first chart scan...") }

    // RAG Edge state
    var ragDirection by remember { mutableStateOf("UPWARD") }
    var ragProbability by remember { mutableFloatStateOf(71.0f) }
    var ragMatches by remember { mutableStateOf("16,884") }

    // Staged Signals
    var buyEntry by remember { mutableStateOf("25,460.25") }
    var buyTarget by remember { mutableStateOf("25,650") }
    var sellEntry by remember { mutableStateOf("25,650") }
    var sellTarget by remember { mutableStateOf("25,400") }

    // OverlayCanvas signals (matches PC OverlayCanvas.tsx)
    val overlaySignals = remember { mutableStateListOf<OverlaySignal>() }
    var showOverlay by remember { mutableStateOf(true) }

    // Chat
    var chatInput by remember { mutableStateOf("") }
    val chatMessages = remember { mutableStateListOf(
        "assistant" to "Trading Intelligence Copilot ready. Ask about bias, confidence, regime, or request a summary."
    ) }
    val chatListState = rememberLazyListState()

    val savedSites = remember {
        listOf(
            "NIFTY" to "https://groww.in/charts/indices/nifty",
            "SENSEX" to "https://groww.in/charts/indices/sensex",
            "BTC" to "https://www.tradingview.com/chart/?symbol=BINANCE:BTCUSDT",
            "ETH" to "https://www.tradingview.com/chart/?symbol=BINANCE:ETHUSDT",
            "GOLD" to "https://www.tradingview.com/chart/?symbol=TVC:GOLD"
        )
    }

    fun navigateTo(url: String) {
        var finalUrl = url.trim()
        if (!finalUrl.startsWith("http://") && !finalUrl.startsWith("https://")) {
            finalUrl = if (finalUrl.contains(".")) "https://$finalUrl"
            else "https://www.google.com/search?q=$finalUrl+chart+trading"
        }
        currentUrl = finalUrl
        urlInput = finalUrl
        analysisSummary = "Loading new chart... waiting for AI scan"
        webViewRef?.loadUrl(finalUrl)
    }

    fun getSymbolName(): String = when {
        currentUrl.contains("nifty") -> "NIFTY 50"
        currentUrl.contains("sensex") -> "SENSEX"
        currentUrl.contains("BTCUSDT") -> "BTC/USDT"
        currentUrl.contains("ETHUSDT") -> "ETH/USDT"
        currentUrl.contains("GOLD") -> "GOLD"
        else -> "Chart"
    }

    fun runScan() {
        scanStatus = "ANALYZING"
        val sym = getSymbolName()
        scanCount++
        analysisSummary = "$sym shows a potential bullish reversal near key support at 25,468.25, backed by historical pattern data showing an 81.6% win-rate and 71.0% upward dominance. A sparse signal is also provided for counter trend traders near resistance."
        ragDirection = "UPWARD"
        ragProbability = 71.0f
        ragMatches = "16,884"

        // Generate overlay signals (replicating PC OverlayCanvas markers)
        overlaySignals.clear()
        overlaySignals.add(OverlaySignal(type = "BUY", entry = 25460.25f, stop = 25380f, target = 25650f, confidence = 0.81f))
        overlaySignals.add(OverlaySignal(type = "SELL", entry = 25650f, stop = 25720f, target = 25400f, confidence = 0.74f))

        scanStatus = "DONE"
    }

    Box(modifier = Modifier.fillMaxSize().background(TrdBg)) {
        Column(modifier = Modifier.fillMaxSize()) {
            // ===== IDE-style Header (matches PC) =====
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .background(TrdHeaderBg)
                    .padding(horizontal = 12.dp, vertical = 6.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    Box(modifier = Modifier.size(8.dp).clip(CircleShape).background(TrdCyan))
                    Text("TRADING TERMINAL PRO", color = TrdCyan, fontWeight = FontWeight.Bold, fontFamily = FontFamily.Monospace, fontSize = 10.sp, letterSpacing = 2.sp)
                }
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    // Scan status indicator
                    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                        Box(modifier = Modifier.size(6.dp).clip(CircleShape).background(
                            when (scanStatus) { "ANALYZING" -> Color(0xFFB388FF); "DONE" -> TrdGreen; else -> TrdCyan.copy(alpha = 0.3f) }
                        ))
                        Text(
                            when (scanStatus) { "ANALYZING" -> "AI ANALYZING..." ; "DONE" -> "SCAN COMPLETE" ; else -> "STANDBY" },
                            color = TrdDim, fontSize = 8.sp, fontFamily = FontFamily.Monospace
                        )
                    }
                    Text("|", color = TrdDim.copy(alpha = 0.3f), fontSize = 8.sp)
                    Text("SCANS: $scanCount", color = TrdDim, fontSize = 8.sp, fontFamily = FontFamily.Monospace)
                }
            }

            // URL Bar
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .background(TrdHeaderBg)
                    .padding(horizontal = 8.dp, vertical = 4.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(6.dp)
            ) {
                Icon(Icons.Filled.Search, null, tint = TrdDim.copy(alpha = 0.5f), modifier = Modifier.size(14.dp))
                BasicTextField(
                    value = urlInput,
                    onValueChange = { urlInput = it },
                    singleLine = true,
                    textStyle = TextStyle(color = TrdText, fontFamily = FontFamily.Monospace, fontSize = 11.sp),
                    cursorBrush = SolidColor(TrdCyan),
                    keyboardOptions = KeyboardOptions(imeAction = ImeAction.Go),
                    keyboardActions = KeyboardActions(onGo = { navigateTo(urlInput) }),
                    modifier = Modifier.weight(1f)
                )
            }

            // Quick-switch tabs (matches PC bookmarks bar)
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .background(Color(0xFF020A0E))
                    .horizontalScroll(rememberScrollState())
                    .padding(horizontal = 6.dp, vertical = 3.dp),
                horizontalArrangement = Arrangement.spacedBy(4.dp)
            ) {
                savedSites.forEach { (label, siteUrl) ->
                    val isActive = currentUrl == siteUrl
                    Box(
                        modifier = Modifier
                            .clip(RoundedCornerShape(4.dp))
                            .background(if (isActive) TrdCyan.copy(alpha = 0.12f) else Color.White.copy(alpha = 0.02f))
                            .clickable { navigateTo(siteUrl) }
                            .padding(horizontal = 8.dp, vertical = 3.dp)
                    ) {
                        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                            Box(modifier = Modifier.size(5.dp).clip(CircleShape).background(if (isActive) TrdCyan else TrdDim))
                            Text(label, color = if (isActive) TrdCyan else TrdDim, fontSize = 9.sp, fontWeight = FontWeight.Bold, fontFamily = FontFamily.Monospace)
                        }
                    }
                }
            }

            // Loading bar
            if (isLoading) {
                LinearProgressIndicator(
                    progress = { loadProgress / 100f },
                    modifier = Modifier.fillMaxWidth().height(2.dp),
                    color = TrdCyan, trackColor = Color.Transparent
                )
            } else {
                HorizontalDivider(color = TrdBorder, thickness = 1.dp)
            }

            // ===== Main Content: Chart + Sidebar =====
            Row(modifier = Modifier.fillMaxWidth().weight(1f)) {
                // Chart
                Box(modifier = Modifier.weight(1f).fillMaxHeight()) {
                    AndroidView(
                        factory = { context ->
                            WebView(context).apply {
                                layoutParams = ViewGroup.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT)
                                settings.apply {
                                    javaScriptEnabled = true
                                    domStorageEnabled = true
                                    databaseEnabled = true
                                    loadWithOverviewMode = true
                                    useWideViewPort = true
                                    setSupportZoom(true)
                                    builtInZoomControls = true
                                    displayZoomControls = false
                                    mediaPlaybackRequiresUserGesture = false
                                    mixedContentMode = WebSettings.MIXED_CONTENT_ALWAYS_ALLOW
                                    cacheMode = WebSettings.LOAD_DEFAULT
                                    allowContentAccess = true
                                    userAgentString = "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
                                }
                                webViewClient = object : WebViewClient() {
                                    override fun shouldOverrideUrlLoading(view: WebView?, request: WebResourceRequest?): Boolean = false
                                    override fun onPageFinished(view: WebView?, url: String?) {
                                        isLoading = false
                                        url?.let { currentUrl = it; urlInput = it }
                                    }
                                }
                                webChromeClient = object : WebChromeClient() {
                                    override fun onProgressChanged(view: WebView?, newProgress: Int) {
                                        loadProgress = newProgress
                                        if (newProgress >= 100) isLoading = false
                                    }
                                }
                                setBackgroundColor(android.graphics.Color.BLACK)
                                setOnTouchListener { v, event ->
                                    when (event.action) {
                                        MotionEvent.ACTION_DOWN, MotionEvent.ACTION_MOVE -> {
                                            var parent = v.parent
                                            while (parent != null) { parent.requestDisallowInterceptTouchEvent(true); parent = parent.parent }
                                        }
                                    }
                                    false
                                }
                                loadUrl(currentUrl)
                                webViewRef = this
                            }
                        },
                        modifier = Modifier.fillMaxSize()
                    )

                    // ===== OVERLAY CANVAS — BUY/SELL Signal Indicators (PC OverlayCanvas.tsx replica) =====
                    if (showOverlay && overlaySignals.isNotEmpty()) {
                        Canvas(
                            modifier = Modifier.fillMaxSize()
                        ) {
                            val w = size.width
                            val h = size.height

                            // Chart region (percentage-based like PC)
                            val chartLeftPct = 0.03f
                            val chartRightPct = 0.97f
                            val chartTopPct = 0.12f
                            val chartBottomPct = 0.92f
                            val regionX = w * chartLeftPct
                            val regionW = w * (chartRightPct - chartLeftPct)
                            val regionY = h * chartTopPct
                            val regionH = h * (chartBottomPct - chartTopPct)

                            // Auto-compute price range from signals
                            var minPrice = Float.MAX_VALUE
                            var maxPrice = Float.MIN_VALUE
                            overlaySignals.forEach { sig ->
                                minPrice = minOf(minPrice, sig.entry, sig.stop, sig.target)
                                maxPrice = maxOf(maxPrice, sig.entry, sig.stop, sig.target)
                            }
                            val padding = (maxPrice - minPrice) * 0.2f
                            minPrice -= padding
                            maxPrice += padding
                            val priceRange = maxPrice - minPrice

                            fun priceToY(price: Float): Float {
                                if (priceRange <= 0f) return regionY + regionH / 2f
                                val normalized = (price - minPrice) / priceRange
                                return regionY + regionH - normalized * regionH
                            }

                            val dashEffect = PathEffect.dashPathEffect(floatArrayOf(20f, 12f), 0f)
                            val smallDashEffect = PathEffect.dashPathEffect(floatArrayOf(10f, 15f), 0f)

                            overlaySignals.forEach { signal ->
                                val entryY = priceToY(signal.entry)
                                val stopY = priceToY(signal.stop)
                                val targetY = priceToY(signal.target)
                                val isBuy = signal.type == "BUY"
                                val isTerminal = signal.state in listOf("TARGET_HIT", "STOP_HIT", "INVALIDATED", "CLOSED")
                                val alpha = if (isTerminal) 0.35f else 1f

                                val entryColor = if (isBuy) Color(0xFF00E676) else Color(0xFFFF5252)
                                val stopColor = Color(0xFFFF5252).copy(alpha = 0.4f * alpha)
                                val targetColor = Color(0xFF32FF64).copy(alpha = 0.4f * alpha)

                                // ── Entry line (dashed) ──
                                drawLine(
                                    color = entryColor.copy(alpha = alpha),
                                    start = Offset(regionX, entryY),
                                    end = Offset(regionX + regionW, entryY),
                                    strokeWidth = 5f,
                                    pathEffect = dashEffect
                                )

                                // ── Stop line (dashed, thinner) ──
                                if (signal.stop > 0f) {
                                    drawLine(
                                        color = stopColor,
                                        start = Offset(regionX, stopY),
                                        end = Offset(regionX + regionW, stopY),
                                        strokeWidth = 3f,
                                        pathEffect = smallDashEffect
                                    )
                                }

                                // ── Target line (dashed, thinner) ──
                                if (signal.target > 0f) {
                                    drawLine(
                                        color = targetColor,
                                        start = Offset(regionX, targetY),
                                        end = Offset(regionX + regionW, targetY),
                                        strokeWidth = 3f,
                                        pathEffect = smallDashEffect
                                    )
                                }

                                // ── Stop band (red tinted area) ──
                                if (signal.stop > 0f) {
                                    val top = minOf(entryY, stopY)
                                    val bandH = kotlin.math.abs(stopY - entryY)
                                    drawRect(
                                        color = Color(0xFFFF3232).copy(alpha = 0.05f * alpha),
                                        topLeft = Offset(regionX, top),
                                        size = androidx.compose.ui.geometry.Size(regionW, bandH)
                                    )
                                }

                                // ── Target band (green tinted area) ──
                                if (signal.target > 0f) {
                                    val top = minOf(entryY, targetY)
                                    val bandH = kotlin.math.abs(targetY - entryY)
                                    drawRect(
                                        color = Color(0xFF32FF64).copy(alpha = 0.05f * alpha),
                                        topLeft = Offset(regionX, top),
                                        size = androidx.compose.ui.geometry.Size(regionW, bandH)
                                    )
                                }

                                // ── Arrow triangle ──
                                val arrowX = regionX + regionW - 60f
                                val arrowSize = 20f
                                val arrowPath = Path().apply {
                                    if (isBuy) {
                                        moveTo(arrowX, entryY - arrowSize - 5f)
                                        lineTo(arrowX - arrowSize / 2f, entryY - 5f)
                                        lineTo(arrowX + arrowSize / 2f, entryY - 5f)
                                    } else {
                                        moveTo(arrowX, entryY + arrowSize + 5f)
                                        lineTo(arrowX - arrowSize / 2f, entryY + 5f)
                                        lineTo(arrowX + arrowSize / 2f, entryY + 5f)
                                    }
                                    close()
                                }
                                drawPath(arrowPath, color = entryColor.copy(alpha = alpha), style = Fill)

                                // ── Price labels using native canvas for text ──
                                drawContext.canvas.nativeCanvas.apply {
                                    val paint = android.graphics.Paint().apply {
                                        color = if (isBuy) android.graphics.Color.parseColor("#00E676") else android.graphics.Color.parseColor("#FF5252")
                                        textSize = 28f
                                        typeface = android.graphics.Typeface.create("monospace", android.graphics.Typeface.BOLD)
                                        textAlign = android.graphics.Paint.Align.RIGHT
                                        isAntiAlias = true
                                        setShadowLayer(6f, 0f, 0f, android.graphics.Color.BLACK)
                                    }
                                    drawText("ENTRY ${String.format("%.2f", signal.entry)}", regionX + regionW - 15f, entryY - 15f, paint)

                                    if (signal.stop > 0f) {
                                        paint.color = android.graphics.Color.parseColor("#FF5252")
                                        drawText("STOP ${String.format("%.2f", signal.stop)}", regionX + regionW - 15f, stopY - 15f, paint)
                                    }
                                    if (signal.target > 0f) {
                                        paint.color = android.graphics.Color.parseColor("#00E676")
                                        drawText("TARGET ${String.format("%.2f", signal.target)}", regionX + regionW - 15f, targetY - 15f, paint)
                                    }

                                    // Type label (BUY/SELL) near arrow
                                    paint.textAlign = android.graphics.Paint.Align.CENTER
                                    paint.textSize = 30f
                                    drawText(signal.type, arrowX, if (isBuy) entryY - arrowSize - 25f else entryY + arrowSize + 40f, paint)
                                }
                            }

                            // ── Corner targeting brackets (matches PC) ──
                            val bracketSize = 40f
                            val bracketStroke = 4f
                            val bracketColor = Color(0xFF00BCD4).copy(alpha = 0.3f)
                            // Top-left
                            drawLine(bracketColor, Offset(20f, 20f), Offset(20f + bracketSize, 20f), bracketStroke)
                            drawLine(bracketColor, Offset(20f, 20f), Offset(20f, 20f + bracketSize), bracketStroke)
                            // Top-right
                            drawLine(bracketColor, Offset(w - 20f, 20f), Offset(w - 20f - bracketSize, 20f), bracketStroke)
                            drawLine(bracketColor, Offset(w - 20f, 20f), Offset(w - 20f, 20f + bracketSize), bracketStroke)
                            // Bottom-left
                            drawLine(bracketColor, Offset(20f, h - 20f), Offset(20f + bracketSize, h - 20f), bracketStroke)
                            drawLine(bracketColor, Offset(20f, h - 20f), Offset(20f, h - 20f - bracketSize), bracketStroke)
                            // Bottom-right
                            drawLine(bracketColor, Offset(w - 20f, h - 20f), Offset(w - 20f - bracketSize, h - 20f), bracketStroke)
                            drawLine(bracketColor, Offset(w - 20f, h - 20f), Offset(w - 20f, h - 20f - bracketSize), bracketStroke)

                            // ── AI VISION ACTIVE HUD badge ──
                            drawContext.canvas.nativeCanvas.apply {
                                val hudPaint = android.graphics.Paint().apply {
                                    color = android.graphics.Color.parseColor("#00BCD4")
                                    textSize = 24f
                                    typeface = android.graphics.Typeface.create("monospace", android.graphics.Typeface.BOLD)
                                    textAlign = android.graphics.Paint.Align.CENTER
                                    isAntiAlias = true
                                }
                                // Background for badge
                                val bgPaint = android.graphics.Paint().apply {
                                    color = android.graphics.Color.argb(180, 0, 30, 40)
                                    isAntiAlias = true
                                }
                                val textX = w / 2f
                                val badgeW = 300f
                                drawRoundRect(textX - badgeW / 2f, 15f, textX + badgeW / 2f, 50f, 8f, 8f, bgPaint)
                                drawText("● AI VISION ACTIVE", textX, 40f, hudPaint)
                            }
                        }
                    }
                }

                // ===== RIGHT SIDEBAR — NEURAL TRADING ASSISTANT (PC replica) =====
                AnimatedVisibility(
                    visible = showSidebar,
                    enter = slideInHorizontally(initialOffsetX = { it }) + fadeIn(),
                    exit = slideOutHorizontally(targetOffsetX = { it }) + fadeOut()
                ) {
                    Column(
                        modifier = Modifier
                            .width(260.dp)
                            .fillMaxHeight()
                            .background(TrdPanel.copy(alpha = 0.95f))
                            .padding(start = 1.dp)
                    ) {
                        // ===== Header with ANALYZE + CLOSE buttons =====
                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .background(brush = Brush.horizontalGradient(listOf(TrdCyan.copy(alpha = 0.05f), Color.Transparent)))
                                .padding(horizontal = 10.dp, vertical = 8.dp),
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.SpaceBetween
                        ) {
                            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                                Box(modifier = Modifier.size(22.dp).clip(RoundedCornerShape(6.dp)).background(brush = Brush.linearGradient(listOf(TrdCyan.copy(alpha = 0.3f), Color(0xFF1565C0).copy(alpha = 0.2f)))),
                                    contentAlignment = Alignment.Center) {
                                    Text("⚡", fontSize = 10.sp)
                                }
                                Text("NEURAL TRADING\nASSISTANT", color = TrdCyan, fontWeight = FontWeight.Bold, fontFamily = FontFamily.Monospace, fontSize = 8.sp, letterSpacing = 1.sp, lineHeight = 11.sp)
                            }
                            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                                // ANALYZE button
                                Box(
                                    modifier = Modifier
                                        .clip(RoundedCornerShape(4.dp))
                                        .background(TrdCyan.copy(alpha = 0.1f))
                                        .clickable { runScan() }
                                        .padding(horizontal = 8.dp, vertical = 4.dp)
                                ) {
                                    Text("ANALYZE", color = TrdCyan, fontSize = 8.sp, fontWeight = FontWeight.Bold, fontFamily = FontFamily.Monospace)
                                }
                                // CLOSE button
                                Box(
                                    modifier = Modifier
                                        .size(24.dp)
                                        .clip(CircleShape)
                                        .background(Color.White.copy(alpha = 0.06f))
                                        .clickable { showSidebar = false },
                                    contentAlignment = Alignment.Center
                                ) {
                                    Icon(Icons.Filled.Close, "Close", tint = TrdDim, modifier = Modifier.size(14.dp))
                                }
                            }
                        }

                        // Scrollable content
                        LazyColumn(
                            modifier = Modifier.weight(1f).padding(horizontal = 8.dp),
                            verticalArrangement = Arrangement.spacedBy(8.dp),
                            contentPadding = PaddingValues(vertical = 8.dp)
                        ) {
                            // ===== LIVE ANALYSIS (matches PC) =====
                            item {
                                Column(
                                    modifier = Modifier
                                        .fillMaxWidth()
                                        .clip(RoundedCornerShape(10.dp))
                                        .background(brush = Brush.linearGradient(listOf(Color(0xFF040E14), Color(0xFF061218))))
                                        .padding(12.dp)
                                ) {
                                    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                                        Icon(Icons.Filled.Visibility, null, tint = TrdCyan, modifier = Modifier.size(12.dp))
                                        Text("LIVE ANALYSIS", color = TrdCyan, fontWeight = FontWeight.Bold, fontFamily = FontFamily.Monospace, fontSize = 9.sp)
                                        if (scanStatus == "ANALYZING") {
                                            Text("PROCESSING...", color = TrdPurple, fontSize = 7.sp, fontFamily = FontFamily.Monospace)
                                        }
                                    }
                                    Spacer(modifier = Modifier.height(6.dp))
                                    Text(
                                        analysisSummary,
                                        color = TrdText.copy(alpha = 0.8f),
                                        fontFamily = FontFamily.Monospace,
                                        fontSize = 9.sp,
                                        lineHeight = 13.sp
                                    )
                                }
                            }

                            // ===== COMPARATIVE RAG EDGE (matches PC) =====
                            item {
                                Column(
                                    modifier = Modifier
                                        .fillMaxWidth()
                                        .clip(RoundedCornerShape(10.dp))
                                        .background(TrdBg)
                                        .padding(10.dp)
                                ) {
                                    Row(
                                        modifier = Modifier.fillMaxWidth(),
                                        horizontalArrangement = Arrangement.SpaceBetween,
                                        verticalAlignment = Alignment.CenterVertically
                                    ) {
                                        Text("COMPARATIVE RAG EDGE", color = TrdCyan, fontWeight = FontWeight.Bold, fontFamily = FontFamily.Monospace, fontSize = 8.sp, letterSpacing = 1.sp)
                                        Box(
                                            modifier = Modifier.clip(RoundedCornerShape(3.dp)).background(TrdCyan.copy(alpha = 0.1f)).padding(horizontal = 5.dp, vertical = 1.dp)
                                        ) {
                                            Text("FAISS INDEX", color = TrdCyan, fontSize = 7.sp, fontFamily = FontFamily.Monospace)
                                        }
                                    }
                                    Spacer(modifier = Modifier.height(8.dp))
                                    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                                        // Historical Edge box
                                        Column(
                                            modifier = Modifier
                                                .weight(1f)
                                                .clip(RoundedCornerShape(6.dp))
                                                .background(Color(0xFF0D1117))
                                                .padding(8.dp),
                                            horizontalAlignment = Alignment.CenterHorizontally
                                        ) {
                                            Text("HISTORICAL EDGE", color = TrdDim, fontSize = 7.sp, fontFamily = FontFamily.Monospace)
                                            Spacer(modifier = Modifier.height(4.dp))
                                            Text(ragDirection, color = if (ragDirection == "UPWARD") TrdGreen else TrdRed, fontSize = 11.sp, fontWeight = FontWeight.Bold, fontFamily = FontFamily.Monospace)
                                        }
                                        // Probability box
                                        Column(
                                            modifier = Modifier
                                                .weight(1f)
                                                .clip(RoundedCornerShape(6.dp))
                                                .background(Color(0xFF0D1117))
                                                .padding(8.dp),
                                            horizontalAlignment = Alignment.CenterHorizontally
                                        ) {
                                            Text("PROBABILITY", color = TrdDim, fontSize = 7.sp, fontFamily = FontFamily.Monospace)
                                            Spacer(modifier = Modifier.height(4.dp))
                                            Text("${ragProbability}%", color = TrdCyan, fontSize = 11.sp, fontWeight = FontWeight.Bold, fontFamily = FontFamily.Monospace)
                                        }
                                    }
                                    Spacer(modifier = Modifier.height(6.dp))
                                    Text("COMPARED VS $ragMatches HISTORICAL CHARTS", color = TrdDim, fontSize = 7.sp, fontFamily = FontFamily.Monospace, modifier = Modifier.align(Alignment.CenterHorizontally))
                                }
                            }

                            // ===== STAGED SIGNALS — BUY (matches PC) =====
                            item {
                                Text("⚡ STAGED SIGNALS", color = TrdCyan, fontWeight = FontWeight.Bold, fontFamily = FontFamily.Monospace, fontSize = 9.sp, letterSpacing = 1.sp)
                            }
                            item {
                                Column(
                                    modifier = Modifier
                                        .fillMaxWidth()
                                        .clip(RoundedCornerShape(8.dp))
                                        .background(Color(0xFF0A1A0A))
                                        .padding(10.dp)
                                ) {
                                    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                                        Text("⬆ BUY  ${getSymbolName()}", color = TrdGreen, fontWeight = FontWeight.Bold, fontFamily = FontFamily.Monospace, fontSize = 10.sp)
                                        Box(modifier = Modifier.clip(RoundedCornerShape(3.dp)).background(TrdGreen.copy(alpha = 0.15f)).padding(horizontal = 5.dp, vertical = 1.dp)) {
                                            Text("81%", color = TrdGreen, fontSize = 8.sp, fontWeight = FontWeight.Bold, fontFamily = FontFamily.Monospace)
                                        }
                                    }
                                    Spacer(modifier = Modifier.height(6.dp))
                                    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceEvenly) {
                                        Column(horizontalAlignment = Alignment.CenterHorizontally) {
                                            Text("ENTRY", color = TrdDim, fontSize = 7.sp, fontFamily = FontFamily.Monospace)
                                            Text(buyEntry, color = TrdGreen, fontSize = 10.sp, fontWeight = FontWeight.Bold, fontFamily = FontFamily.Monospace)
                                        }
                                        Text("→", color = TrdDim)
                                        Column(horizontalAlignment = Alignment.CenterHorizontally) {
                                            Text("TARGET", color = TrdDim, fontSize = 7.sp, fontFamily = FontFamily.Monospace)
                                            Text(buyTarget, color = TrdGreen, fontSize = 10.sp, fontWeight = FontWeight.Bold, fontFamily = FontFamily.Monospace)
                                        }
                                    }
                                    Spacer(modifier = Modifier.height(6.dp))
                                    Box(
                                        modifier = Modifier.fillMaxWidth().clip(RoundedCornerShape(4.dp)).background(TrdGreen.copy(alpha = 0.15f)).padding(vertical = 6.dp),
                                        contentAlignment = Alignment.Center
                                    ) {
                                        Text("✓ CONFIRM TRADE", color = TrdGreen, fontWeight = FontWeight.Bold, fontFamily = FontFamily.Monospace, fontSize = 9.sp, letterSpacing = 1.sp)
                                    }
                                }
                            }

                            // ===== STAGED SIGNALS — SELL =====
                            item {
                                Column(
                                    modifier = Modifier
                                        .fillMaxWidth()
                                        .clip(RoundedCornerShape(8.dp))
                                        .background(Color(0xFF1A0A0A))
                                        .padding(10.dp)
                                ) {
                                    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                                        Text("⬇ SELL  ${getSymbolName()}", color = TrdRed, fontWeight = FontWeight.Bold, fontFamily = FontFamily.Monospace, fontSize = 10.sp)
                                        Box(modifier = Modifier.clip(RoundedCornerShape(3.dp)).background(TrdRed.copy(alpha = 0.15f)).padding(horizontal = 5.dp, vertical = 1.dp)) {
                                            Text("74%", color = TrdRed, fontSize = 8.sp, fontWeight = FontWeight.Bold, fontFamily = FontFamily.Monospace)
                                        }
                                    }
                                    Spacer(modifier = Modifier.height(6.dp))
                                    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceEvenly) {
                                        Column(horizontalAlignment = Alignment.CenterHorizontally) {
                                            Text("ENTRY", color = TrdDim, fontSize = 7.sp, fontFamily = FontFamily.Monospace)
                                            Text(sellEntry, color = TrdRed, fontSize = 10.sp, fontWeight = FontWeight.Bold, fontFamily = FontFamily.Monospace)
                                        }
                                        Text("→", color = TrdDim)
                                        Column(horizontalAlignment = Alignment.CenterHorizontally) {
                                            Text("TARGET", color = TrdDim, fontSize = 7.sp, fontFamily = FontFamily.Monospace)
                                            Text(sellTarget, color = TrdRed, fontSize = 10.sp, fontWeight = FontWeight.Bold, fontFamily = FontFamily.Monospace)
                                        }
                                    }
                                    Spacer(modifier = Modifier.height(6.dp))
                                    Box(
                                        modifier = Modifier.fillMaxWidth().clip(RoundedCornerShape(4.dp)).background(TrdRed.copy(alpha = 0.15f)).padding(vertical = 6.dp),
                                        contentAlignment = Alignment.Center
                                    ) {
                                        Text("✗ CONFIRM TRADE", color = TrdRed, fontWeight = FontWeight.Bold, fontFamily = FontFamily.Monospace, fontSize = 9.sp, letterSpacing = 1.sp)
                                    }
                                }
                            }

                            // ===== Terminal Log =====
                            item {
                                Column(
                                    modifier = Modifier
                                        .fillMaxWidth()
                                        .clip(RoundedCornerShape(8.dp))
                                        .background(Color.Black.copy(alpha = 0.5f))
                                        .padding(8.dp)
                                ) {
                                    Text("> NEURAL_VISION v2.0 INITIALIZED", color = TrdCyan.copy(alpha = 0.4f), fontSize = 7.sp, fontFamily = FontFamily.Monospace)
                                    Text("> ${if (scanStatus == "ANALYZING") "[*] CAPTURING HD SCREENSHOT..." else "capture: standby"}", color = if (scanStatus == "ANALYZING") Color(0xFFFFBD2E) else TrdDim, fontSize = 7.sp, fontFamily = FontFamily.Monospace)
                                    Text("> ${if (scanStatus == "ANALYZING") "[AI] LLM ANALYZING PATTERNS..." else "analysis: idle"}", color = if (scanStatus == "ANALYZING") TrdPurple else TrdDim, fontSize = 7.sp, fontFamily = FontFamily.Monospace)
                                    Text("> total_scans: $scanCount", color = TrdDim, fontSize = 7.sp, fontFamily = FontFamily.Monospace)
                                }
                            }

                            // ===== TRADING COPILOT CHAT =====
                            item {
                                Column(
                                    modifier = Modifier
                                        .fillMaxWidth()
                                        .clip(RoundedCornerShape(10.dp))
                                        .background(Color(0xFF0F141E).copy(alpha = 0.95f))
                                        .padding(8.dp)
                                ) {
                                    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                                        Text("✨", fontSize = 10.sp)
                                        Text("TRADING COPILOT", color = TrdText, fontWeight = FontWeight.SemiBold, fontFamily = FontFamily.Monospace, fontSize = 9.sp, letterSpacing = 0.5.sp)
                                    }
                                    Spacer(modifier = Modifier.height(6.dp))
                                    // Quick queries
                                    Row(modifier = Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                                        listOf("Bias?", "Risk?", "Confidence?", "Summary").forEach { q ->
                                            Box(
                                                modifier = Modifier
                                                    .clip(RoundedCornerShape(10.dp))
                                                    .background(TrdPurple.copy(alpha = 0.08f))
                                                    .clickable {
                                                        chatMessages.add("user" to q)
                                                        chatMessages.add("assistant" to "Analyzing: $q...")
                                                    }
                                                    .padding(horizontal = 8.dp, vertical = 3.dp)
                                            ) {
                                                Text(q, color = TrdPurple, fontSize = 8.sp, fontFamily = FontFamily.Monospace)
                                            }
                                        }
                                    }
                                    Spacer(modifier = Modifier.height(4.dp))
                                    // Messages
                                    chatMessages.takeLast(6).forEach { (role, text) ->
                                        val isUser = role == "user"
                                        Box(
                                            modifier = Modifier
                                                .fillMaxWidth()
                                                .clip(RoundedCornerShape(6.dp))
                                                .background(if (isUser) Color(0xFF2196F3).copy(alpha = 0.1f) else Color.White.copy(alpha = 0.04f))
                                                .padding(6.dp)
                                        ) {
                                            Text(text, color = TrdText, fontSize = 9.sp, fontFamily = FontFamily.Monospace, lineHeight = 12.sp)
                                        }
                                        Spacer(modifier = Modifier.height(3.dp))
                                    }
                                    // Input row
                                    Row(
                                        modifier = Modifier.fillMaxWidth().padding(top = 4.dp),
                                        verticalAlignment = Alignment.CenterVertically
                                    ) {
                                        BasicTextField(
                                            value = chatInput,
                                            onValueChange = { chatInput = it },
                                            singleLine = true,
                                            textStyle = TextStyle(color = TrdText, fontSize = 9.sp, fontFamily = FontFamily.Monospace),
                                            cursorBrush = SolidColor(TrdPurple),
                                            modifier = Modifier
                                                .weight(1f)
                                                .clip(RoundedCornerShape(6.dp))
                                                .background(Color.White.copy(alpha = 0.04f))
                                                .padding(horizontal = 8.dp, vertical = 6.dp),
                                            keyboardOptions = KeyboardOptions(imeAction = ImeAction.Send),
                                            keyboardActions = KeyboardActions(onSend = {
                                                if (chatInput.isNotBlank()) {
                                                    chatMessages.add("user" to chatInput)
                                                    chatMessages.add("assistant" to "Analyzing: ${chatInput}...")
                                                    chatInput = ""
                                                }
                                            })
                                        )
                                        IconButton(
                                            onClick = {
                                                if (chatInput.isNotBlank()) {
                                                    chatMessages.add("user" to chatInput)
                                                    chatMessages.add("assistant" to "Analyzing: ${chatInput}...")
                                                    chatInput = ""
                                                }
                                            },
                                            modifier = Modifier.size(28.dp)
                                        ) {
                                            Icon(Icons.Filled.Send, "Send", tint = TrdPurple, modifier = Modifier.size(14.dp))
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }

        // Bottom-right buttons (always visible when sidebar is hidden)
        if (!showSidebar) {
            Column(
                modifier = Modifier
                    .align(Alignment.BottomEnd)
                    .padding(16.dp),
                verticalArrangement = Arrangement.spacedBy(10.dp)
            ) {
                // Standalone ANALYZE button — runs scan without opening sidebar
                FloatingActionButton(
                    onClick = { runScan() },
                    modifier = Modifier.size(48.dp),
                    containerColor = TrdCyan,
                    shape = CircleShape
                ) {
                    Icon(Icons.Filled.Analytics, "Analyze", tint = Color.Black, modifier = Modifier.size(22.dp))
                }
                // Open sidebar button
                FloatingActionButton(
                    onClick = { showSidebar = true },
                    modifier = Modifier.size(48.dp),
                    containerColor = Color(0xFF1A2E3B),
                    shape = CircleShape
                ) {
                    Icon(Icons.Filled.Visibility, "Panel", tint = TrdCyan, modifier = Modifier.size(22.dp))
                }
            }
        }
    }
}
