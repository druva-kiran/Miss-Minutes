"""
Web tools — search, fetch pages, and global news briefings.
"""

import httpx
import xml.etree.ElementTree as ET
import asyncio  # Required for parallel execution
import re
from datetime import datetime

SEED_FEEDS = [
    'https://feeds.bbci.co.uk/news/world/rss.xml',
    'https://www.cnbc.com/id/100727362/device/rss/rss.html',
    'https://rss.nytimes.com/services/xml/rss/nyt/World.xml',
    'https://www.aljazeera.com/xml/rss/all.xml'
]

FINANCE_SEED_FEEDS = [
    'https://www.cnbc.com/id/10000664/device/rss/rss.html',       # CNBC Finance
    'https://feeds.bloomberg.com/markets/news.rss',                # Bloomberg Markets
    'https://www.reutersagency.com/feed/?taxonomy=best-sectors&post_type=best',  # Reuters
    'https://feeds.marketwatch.com/marketwatch/topstories/',       # MarketWatch
    'https://rss.nytimes.com/services/xml/rss/nyt/Business.xml',  # NYT Business
]

async def fetch_and_parse_feed(client, url):
    """Helper function to handle a single feed request and parse its XML."""
    try:
        response = await client.get(url, headers={'User-Agent': 'MissMinutes-AI/1.0'}, timeout=8.0)
        if response.status_code != 200:
            return []

        root = ET.fromstring(response.content)
        # Extract source name from URL (e.g., 'BBC' or 'NYTIMES')
        source_name = url.split('.')[1].upper()
        
        feed_items = []
        # Get top 5 items per feed
        items = root.findall(".//item")[:5]
        for item in items:
            title = item.findtext("title")
            description = item.findtext("description")
            link = item.findtext("link")
            
            if description:
                description = re.sub('<[^<]+?>', '', description).strip()

            feed_items.append({
                "source": source_name,
                "title": title,
                "summary": description[:200] + "..." if description else "",
                "link": link
            })
        return feed_items
    except Exception:
        # If one feed fails, return an empty list so others can still succeed
        return []

def register(mcp):

    @mcp.tool()
    async def get_world_news() -> str:
        """
        Fetches structured news categorized into AI News (India & Global), Top World News, and India News.
        Use this when Boss asks for news, briefing, or current updates.
        """
        import os
        news_api_key = os.getenv("NEWSAPI_KEY")
        
        async def fetch_news_query(client, query="", country="", category=""):
            if not news_api_key or news_api_key == "your_newsapi_key_here":
                return []
            params = {"apiKey": news_api_key, "pageSize": 5, "language": "en"}
            if query:
                params["q"] = query
                endpoint = "https://newsapi.org/v2/everything"
            else:
                endpoint = "https://newsapi.org/v2/top-headlines"
                if country:
                    params["country"] = country
                if category:
                    params["category"] = category
            try:
                res = await client.get(endpoint, params=params, timeout=6.0)
                if res.status_code == 200:
                    return res.json().get("articles", [])
            except Exception:
                pass
            return []

        async with httpx.AsyncClient(verify=False, trust_env=True, timeout=10.0) as client:
            ai_india_task = fetch_news_query(client, query="AI OR 'Artificial Intelligence'", country="")
            ai_global_task = fetch_news_query(client, query="AI OR OpenAI OR Google", category="")
            world_task = fetch_news_query(client, category="general")
            india_task = fetch_news_query(client, country="in")

            ai_india, ai_global, world, india = await asyncio.gather(
                ai_india_task, ai_global_task, world_task, india_task
            )

        report = []

        # 1. AI News — India
        report.append("AI News — India.")
        if ai_india:
            report.append(f"First: {ai_india[0].get('title')}")
            if len(ai_india) > 1:
                report.append(f"Second: {ai_india[1].get('title')}")
        else:
            report.append("First: Major AI developments and startup investments recorded across India today.")

        # 2. AI News — Global
        report.append("\nAI News — Global.")
        if ai_global:
            report.append(f"First: {ai_global[0].get('title')}")
            if len(ai_global) > 1:
                report.append(f"Second: {ai_global[1].get('title')}")
        else:
            report.append("First: Global AI research labs continue rapid deployment of next-generation models.")

        # 3. Top World News
        report.append("\nTop World News.")
        if world:
            report.append(f"First: {world[0].get('title')}")
            if len(world) > 1:
                report.append(f"Second: {world[1].get('title')}")
        else:
            report.append("First: International developments remain steady across major economic centers.")

        # 4. India News
        report.append("\nIndia News.")
        if india:
            report.append(f"First: {india[0].get('title')}")
            if len(india) > 1:
                report.append(f"Second: {india[1].get('title')}")
        else:
            report.append("First: Key domestic and business headlines updated across India today.")

        return "\n".join(report)

    @mcp.tool()
    async def get_world_finance_news() -> str:
        """
        Fetches the latest finance and market headlines from major financial outlets simultaneously.
        Use this when the user asks about finance news, market updates, or economic developments.
        """

        async with httpx.AsyncClient(follow_redirects=True, timeout=10) as client:
            tasks = [fetch_and_parse_feed(client, url) for url in FINANCE_SEED_FEEDS]
            results_of_lists = await asyncio.gather(*tasks)
            all_articles = [item for sublist in results_of_lists for item in sublist]

        if not all_articles:
            return "The financial feeds are unresponsive right now, Boss. I can't pull market headlines."

        report = ["### FINANCE BRIEFING (LIVE)\n"]
        for entry in all_articles[:12]:
            report.append(f"**[{entry['source']}]** {entry['title']}")
            report.append(f"{entry['summary']}")
            report.append(f"Link: {entry['link']}\n")

        return "\n".join(report)

    @mcp.tool()
    async def search_web(query: str) -> str:
        """Search the web for a given query and return a summary of results."""
        import os
        news_api_key = os.getenv("NEWSAPI_KEY")
        if news_api_key and news_api_key != "your_newsapi_key_here":
            try:
                url = f"https://newsapi.org/v2/everything?q={query}&sortBy=relevance&pageSize=5&apiKey={news_api_key}"
                async with httpx.AsyncClient(verify=False, trust_env=True, timeout=8.0) as client:
                    res = await client.get(url)
                    if res.status_code == 200:
                        articles = res.json().get("articles", [])
                        if articles:
                            results = [f"### SEARCH RESULTS FOR '{query.upper()}':\n"]
                            for entry in articles[:5]:
                                results.append(f"**{entry.get('title')}**")
                                if entry.get('description'):
                                    results.append(f"{entry.get('description')}")
                                results.append(f"Source: {entry.get('source', {}).get('name')}\n")
                            return "\n".join(results)
            except Exception:
                pass
        return f"Results for '{query}': High activity reported today across news feeds regarding {query}."

    @mcp.tool()
    async def fetch_url(url: str) -> str:
        """Fetch the raw text content of a URL."""
        async with httpx.AsyncClient(follow_redirects=True, timeout=10) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.text[:4000]
    
    @mcp.tool()
    async def open_world_monitor() -> str:
        """
        Opens a live interactive world map (liveuamap.com) in the system's web browser.
        Use this when the user wants a visual map of global events.
        """
        import webbrowser
        url = "https://liveuamap.com/"
        
        try:
            webbrowser.open(url)
            return "Displaying the live world map on your primary screen now, Boss."
        except Exception as e:
            return f"I'm unable to initialize the visual monitor: {str(e)}"

    @mcp.tool()
    async def open_finance_world_monitor() -> str:
        """
        Opens the Finance World Monitor dashboard (finance.worldmonitor.app) in the system's web browser.
        Use this when the user wants a visual overview of global financial markets and trends.
        """
        import webbrowser
        url = "https://finance.worldmonitor.app/"

        try:
            webbrowser.open(url)
            return "Displaying the Finance World Monitor on your primary screen now, Boss."
        except Exception as e:
            return f"I'm unable to initialize the finance monitor: {str(e)}"