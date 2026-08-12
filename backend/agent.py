"""
Miss Minutes – Voice Agent (MCP-powered)
===================================
TVA-style voice assistant that controls systems and pulls live info 
via an MCP server running on the Windows host.


MCP Server URL is auto-resolved from WSL → Windows host IP.

Run:
  uv run miss_minutes_voice dev      – LiveKit Cloud mode
  uv run miss_minutes_voice console  – text-only console mode
"""

import os
import logging
import subprocess

from dotenv import load_dotenv
from livekit.agents import JobContext, WorkerOptions, cli
from livekit.agents.voice import Agent, AgentSession
from livekit.agents.llm import mcp

# Plugins
from livekit.plugins import google as lk_google, openai as lk_openai, sarvam, silero

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------

STT_PROVIDER       = "sarvam"
LLM_PROVIDER       = "omniroute"
TTS_PROVIDER       = "sarvam"

OPENAI_TTS_MODEL   = "tts-1"
OPENAI_TTS_VOICE   = "nova"       # "nova" has a clean, confident female tone
TTS_SPEED           = 1.15

SARVAM_TTS_LANGUAGE = "en-IN"
SARVAM_TTS_SPEAKER  = "priya"

# MCP server running on Windows host
MCP_SERVER_PORT = 8000

# ---------------------------------------------------------------------------
# System prompt – Miss Minutes
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """
You are Miss Minutes, a professional executive personal voice assistant.

## Core Persona & Tone
- Your name is Miss Minutes. If asked who or what you are, state that you are Miss Minutes, Boss's executive personal assistant.
- You ALWAYS address the user as "Boss".
- NEVER call the user "Sweetie", "friend", "bro", "buddy", "hon", or romantic/casual titles.
- Tone: Calm, intelligent, concise, confident, respectful, and proactive.
- Use natural spoken language suitable for text-to-speech. No unnecessary emojis, flirting, or casual filler.
- Prioritize completing tasks quickly and concisely.

---

## Capabilities & News Structuring

### get_world_news — News Command
When Boss asks for news ("fetch news", "get the news", "what's happening"):
1. Call the `get_world_news` tool immediately and silently.
2. Structure and deliver the spoken report strictly in this order:
   - **AI News — India**: Major AI developments, companies, research, and policy in India.
   - **AI News — Global**: Top international AI breakthroughs and industry developments.
   - **Top World News**: Most impactful global non-AI headlines.
   - **India News**: Top general headlines from India.
3. Keep items concise and voice-friendly:
   - "AI News — India. First: ... Second: ..."
   - "AI News — Global. First: ... Second: ..."
4. Prioritize impact and importance over recency. Do not read URLs aloud.

### open_world_monitor — Visual Map Dashboard
- After delivering a world news report, say: "Let me open the live world map for you, Boss." and call `open_world_monitor`.

### open_finance_world_monitor — Finance Dashboard
- After finance updates, say: "Let me open the finance dashboard for you, Boss." and call `open_finance_world_monitor`.

### Local File System Tools
- **read_file**: Read local files when Boss asks to inspect or read a file.
- **write_file**: Create or overwrite local files when Boss asks to write or save content.
- **list_directory**: List files and folders when Boss asks to view directory contents.

---

## Behavioral Rules

1. ALWAYS address the user as "Boss".
2. **NO AUTOMATIC TOOL CALLS ON GREETING**: On initial session start, ONLY speak the greeting. NEVER call any tools automatically (such as `get_world_news` or `open_world_monitor`) when greeting Boss. Wait for Boss to give an explicit command or ask a query.
3. Call tools silently and immediately ONLY when Boss asks a query or gives a command — never say "I am going to call a function..." Just do it.
4. Keep all spoken responses concise — two to four sentences maximum.
5. No markdown bullet points, code snippets, or URLs in spoken output.
6. If a tool fails, report calmly: "The news feed is currently unavailable, Boss. Would you like me to try again?"
""".strip()
# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

load_dotenv()

logger = logging.getLogger("miss-minutes-agent")
logger.setLevel(logging.INFO)


# ---------------------------------------------------------------------------
# Resolve Windows host IP from WSL
# ---------------------------------------------------------------------------

def _get_windows_host_ip() -> str:
    """Get the Windows host IP by looking at the default network route."""
    try:
        # 'ip route' is the most reliable way to find the 'default' gateway
        # which is always the Windows host in WSL.
        cmd = "ip route show default | awk '{print $3}'"
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=2
        )
        ip = result.stdout.strip()
        if ip:
            logger.info("Resolved Windows host IP via gateway: %s", ip)
            return ip
    except Exception as exc:
        logger.warning("Gateway resolution failed: %s. Trying fallback...", exc)

    # Fallback to your original resolv.conf logic if 'ip route' fails
    try:
        with open("/etc/resolv.conf", "r") as f:
            for line in f:
                if "nameserver" in line:
                    ip = line.split()[1]
                    logger.info("Resolved Windows host IP via nameserver: %s", ip)
                    return ip
    except Exception:
        pass

    return "127.0.0.1"

def _mcp_server_url() -> str:
    # host_ip = _get_windows_host_ip()
    # url = f"http://{host_ip}:{MCP_SERVER_PORT}/sse"
    # url = f"https://ongoing-colleague-samba-pioneer.trycloudflare.com/sse"
    url = f"http://127.0.0.1:{MCP_SERVER_PORT}/sse"
    logger.info("MCP Server URL: %s", url)
    return url


# ---------------------------------------------------------------------------
# Build provider instances
# ---------------------------------------------------------------------------

def _build_stt():
    if STT_PROVIDER == "sarvam":
        logger.info("STT → Sarvam Saaras v3")
        return sarvam.STT(
            language="en-IN",
            model="saaras:v3",
            mode="transcribe",
            flush_signal=True,
            sample_rate=16000,
        )
    elif STT_PROVIDER == "whisper":
        logger.info("STT → OpenAI Whisper")
        return lk_openai.STT(model="whisper-1")
    else:
        raise ValueError(f"Unknown STT_PROVIDER: {STT_PROVIDER!r}")


def _build_llm():
    if LLM_PROVIDER == "omniroute":
        model_name = os.getenv("OMNIROUTE_MODEL", "oc/big-pickle")
        logger.info("LLM → Omni Route (%s)", model_name)
        return lk_openai.LLM(
            model=model_name,
            api_key=os.getenv("OMNIROUTE_API_KEY"),
            base_url=os.getenv("OMNIROUTE_BASE_URL")
        )
    else:
        raise ValueError(f"Unknown LLM_PROVIDER: {LLM_PROVIDER!r}")


def _build_tts():
    if TTS_PROVIDER == "sarvam":
        logger.info("TTS → Sarvam Bulbul v3")
        return sarvam.TTS(
            target_language_code=SARVAM_TTS_LANGUAGE,
            model="bulbul:v3",
            speaker=SARVAM_TTS_SPEAKER,
            pace=TTS_SPEED,
        )
    elif TTS_PROVIDER == "openai":
        logger.info("TTS → OpenAI TTS (%s / %s)", OPENAI_TTS_MODEL, OPENAI_TTS_VOICE)
        return lk_openai.TTS(model=OPENAI_TTS_MODEL, voice=OPENAI_TTS_VOICE, speed=TTS_SPEED)
    else:
        raise ValueError(f"Unknown TTS_PROVIDER: {TTS_PROVIDER!r}")


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

class MissMinutesAgent(Agent):
    """
    Miss Minutes – TVA voice assistant.
    All tools are provided via the MCP server on the Windows host.
    """

    def __init__(self, stt, llm, tts) -> None:
        super().__init__(
            instructions=SYSTEM_PROMPT,
            stt=stt,
            llm=llm,
            tts=tts,
            vad=silero.VAD.load(),
            mcp_servers=[
                mcp.MCPServerHTTP(
                    url=_mcp_server_url(),
                    transport_type="sse",
                    client_session_timeout_seconds=30,
                ),
            ],
        )

    async def on_enter(self) -> None:
        """Greet the user based on the current time of day."""
        from datetime import datetime, timezone
        hour = datetime.now(timezone.utc).hour  # UTC hour; adjust if local TZ differs

        if hour >= 22 or hour < 4:
            greeting_text = "Good evening, Boss. What can I do for you?"
        elif 4 <= hour < 12:
            greeting_text = "Good morning, Boss. What would you like me to do?"
        elif 12 <= hour < 17:
            greeting_text = "Good afternoon, Boss. What would you like me to do?"
        else:  # 17–21
            greeting_text = "Good evening, Boss. What would you like me to do?"

        await self.session.say(greeting_text, add_to_chat_ctx=True)


# ---------------------------------------------------------------------------
# LiveKit entry point
# ---------------------------------------------------------------------------

def _turn_detection() -> str:
    return "stt" if STT_PROVIDER == "sarvam" else "vad"


def _endpointing_delay() -> float:
    return {"sarvam": 0.07, "whisper": 0.3}.get(STT_PROVIDER, 0.1)


async def entrypoint(ctx: JobContext) -> None:
    logger.info(
        "Miss Minutes online – room: %s | STT=%s | LLM=%s | TTS=%s",
        ctx.room.name, STT_PROVIDER, LLM_PROVIDER, TTS_PROVIDER,
    )

    stt = _build_stt()
    llm = _build_llm()
    tts = _build_tts()

    session = AgentSession(
        turn_detection=_turn_detection(),
        min_endpointing_delay=_endpointing_delay(),
    )

    await session.start(
        agent=MissMinutesAgent(stt=stt, llm=llm, tts=tts),
        room=ctx.room,
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))

def dev():
    """Wrapper to run the agent in dev mode automatically."""
    import sys
    # If no command was provided, inject 'dev'
    if len(sys.argv) == 1:
        sys.argv.append("dev")
    main()

if __name__ == "__main__":
    main()