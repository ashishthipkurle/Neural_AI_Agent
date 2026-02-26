package com.neuralai.agent.core.skills.research

import io.ktor.client.HttpClient
import io.ktor.client.call.body
import io.ktor.client.request.get
import io.ktor.client.request.header
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.jsoup.Jsoup
import java.net.URLEncoder
import javax.inject.Inject
import javax.inject.Singleton

data class SearchResult(
    val title: String,
    val url: String,
    val snippet: String
)

@Singleton
class WebSearchSkill @Inject constructor(
    private val httpClient: HttpClient
) {
    /**
     * Executes a web search using DuckDuckGo Html interface.
     */
    suspend fun search(query: String, maxResults: Int = 3): List<SearchResult> = withContext(Dispatchers.IO) {
        try {
            val encodedQuery = URLEncoder.encode(query, "UTF-8")
            val html = httpClient.get("https://html.duckduckgo.com/html/?q=$encodedQuery") {
                header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64)")
            }.body<String>()

            val doc = Jsoup.parse(html)
            val results = doc.select(".result__body")
            
            return@withContext results.take(maxResults).mapNotNull { result ->
                val titleElem = result.selectFirst(".result__title a")
                val snippetElem = result.selectFirst(".result__snippet")
                
                if (titleElem != null && snippetElem != null) {
                    // DuckDuckGo redirects links through duckduckgo.com/l/?uddg=...
                    // Jsoup url decoding or regex might be needed for the pure link, but 
                    // for basic fetching, the redirect URL still works if followed.
                    val rawUrl = titleElem.attr("href")
                    var cleanUrl = rawUrl
                    if (rawUrl.contains("uddg=")) {
                        try {
                            cleanUrl = java.net.URLDecoder.decode(rawUrl.substringAfter("uddg=").substringBefore("&"), "UTF-8")
                        } catch (e: Exception) {
                            // fallback
                        }
                    }

                    SearchResult(
                        title = titleElem.text(),
                        url = cleanUrl,
                        snippet = snippetElem.text()
                    )
                } else null
            }
        } catch (e: Exception) {
            emptyList()
        }
    }

    /**
     * Fetches and extracts the main text content of a webpage, attempting to strip out navbars and sidebars.
     */
    suspend fun fetchPage(url: String): String = withContext(Dispatchers.IO) {
        try {
            val html = httpClient.get(url) {
                header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64)")
            }.body<String>()

            val doc = Jsoup.parse(html)
            
            // Remove noise
            doc.select("script, style, nav, footer, header, aside, .sidebar, .comments").remove()
            
            // Prefer article tags if present
            val article = doc.selectFirst("article")
            if (article != null) {
                return@withContext article.text().take(8000) // limit arbitrary length to avoid blowing up prompt
            }
            
            // Fallback to body paragraphs
            val paragraphs = doc.select("p")
            if (paragraphs.isNotEmpty()) {
                val text = paragraphs.joinToString("\n\n") { it.text() }
                return@withContext text.take(8000)
            }
            
            // Absolute fallback
            return@withContext doc.body().text().take(8000)
        } catch (e: Exception) {
            "Error fetching webpage: ${e.message}"
        }
    }
}
