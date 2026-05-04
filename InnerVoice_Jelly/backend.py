from __future__ import annotations

from collections import Counter
import importlib
import json
import math
import os
import random
import re
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, cast

import requests
from fastapi import FastAPI, File, Query, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

try:
    BlobServiceClient = importlib.import_module("azure.storage.blob").BlobServiceClient
except ImportError:
    BlobServiceClient = None


BASE_DIR = Path(__file__).resolve().parent
REPO_ENV_FILE = BASE_DIR / ".env"
RUNTIME_DATA_DIR = Path(os.getenv("LUNA_DATA_DIR", str(BASE_DIR))).resolve()
RUNTIME_DATA_DIR.mkdir(parents=True, exist_ok=True)
ENV_FILE = Path(
    os.getenv(
        "LUNA_ENV_FILE",
        str((RUNTIME_DATA_DIR / ".env") if RUNTIME_DATA_DIR != BASE_DIR else REPO_ENV_FILE),
    )
).resolve()
def resolve_frontend_dist_dir() -> Path:
    configured_dir = os.getenv("LUNA_STATIC_DIR")
    candidates = []

    if configured_dir:
        candidates.append(Path(configured_dir))

    candidates.extend(
        [
            BASE_DIR.parent / "dist",
            BASE_DIR / "dist",
            Path.cwd() / "dist",
        ]
    )

    for candidate in candidates:
        resolved = candidate.resolve()
        if (resolved / "index.html").exists():
            return resolved

    return Path(configured_dir or BASE_DIR.parent / "dist").resolve()


FRONTEND_DIST_DIR = resolve_frontend_dist_dir()
FRONTEND_INDEX_FILE = FRONTEND_DIST_DIR / "index.html"


def runtime_file(name: str) -> Path:
    target = RUNTIME_DATA_DIR / name
    source = BASE_DIR / name
    target.parent.mkdir(parents=True, exist_ok=True)

    if not target.exists() and source.exists() and source != target:
        try:
            shutil.copyfile(source, target)
        except Exception:
            pass

    return target


DIARY_FILE = runtime_file("mood_data.json")
MEM_FILE = runtime_file("luna_memory.txt")
STATE_FILE = runtime_file("luna_state.json")
SOUL_MAP_FILE = runtime_file("luna_soul_map.json")
USER_MEMORY_DIR = RUNTIME_DATA_DIR / "luna_user_memory"
WISDOM_CACHE_FILE = runtime_file("wisdom_cache.json")
WISDOM_USAGE_FILE = runtime_file("wisdom_usage.json")

SoulCounter = dict[str, int]
SoulMap = dict[str, object]
SoulMapStore = dict[str, SoulMap]


def load_local_env(env_path: Path) -> None:
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


load_local_env(REPO_ENV_FILE)
if ENV_FILE != REPO_ENV_FILE:
    load_local_env(ENV_FILE)


def parse_csv_env(name: str, default: list[str]) -> list[str]:
    raw = os.getenv(name, "")
    values = [item.strip() for item in raw.split(",") if item.strip()]
    return values or default

AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY", "")
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT", "").rstrip("/")
AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT", "")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2025-01-01-preview")
AZURE_OPENAI_MAX_TOKEN_FIELD = os.getenv("AZURE_OPENAI_MAX_TOKEN_FIELD", "auto").strip().lower()
HF_TOKEN = os.getenv("HF_TOKEN", "")
AZURE_SPEECH_KEY = os.getenv("AZURE_SPEECH_KEY", "")
AZURE_SPEECH_REGION = os.getenv("AZURE_SPEECH_REGION", "")
AZURE_SPEECH_VOICE = os.getenv("AZURE_SPEECH_VOICE", "en-IN-NeerjaNeural")
AZURE_TRANSLATOR_KEY = os.getenv("AZURE_TRANSLATOR_KEY", "")
AZURE_TRANSLATOR_REGION = os.getenv("AZURE_TRANSLATOR_REGION", "")
AZURE_TRANSLATOR_ENDPOINT = os.getenv("AZURE_TRANSLATOR_ENDPOINT", "https://api.cognitive.microsofttranslator.com")
USE_AZURE_TRANSLATOR = os.getenv("USE_AZURE_TRANSLATOR", "true").strip().lower() in {"1", "true", "yes", "on"}
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "6ZZR4JY6rOriLSDtV54M")
AZURE_STORAGE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING", "")
AZURE_STORAGE_CONTAINER = os.getenv("AZURE_STORAGE_CONTAINER", "luna-data")
FRONTEND_ORIGINS = parse_csv_env(
    "FRONTEND_ORIGINS",
    ["http://localhost:5173", "http://127.0.0.1:5173"],
)

request_session = requests.Session()
HF_API_URL = "https://router.huggingface.co/v1/chat/completions"
HF_MODEL_ID = "Qwen/Qwen2.5-7B-Instruct"

if AZURE_OPENAI_MAX_TOKEN_FIELD not in {"auto", "max_tokens", "max_completion_tokens"}:
    AZURE_OPENAI_MAX_TOKEN_FIELD = "auto"

MOOD_VOICE_SETTINGS = {
    "sad": {"stability": 0.62, "similarity_boost": 0.82, "style": 0.12, "use_speaker_boost": True},
    "anxious": {"stability": 0.58, "similarity_boost": 0.80, "style": 0.15, "use_speaker_boost": True},
    "overwhelmed": {"stability": 0.60, "similarity_boost": 0.81, "style": 0.14, "use_speaker_boost": True},
    "tired": {"stability": 0.68, "similarity_boost": 0.84, "style": 0.08, "use_speaker_boost": True},
    "hopeful": {"stability": 0.63, "similarity_boost": 0.86, "style": 0.18, "use_speaker_boost": True},
    "neutral": {"stability": 0.64, "similarity_boost": 0.84, "style": 0.10, "use_speaker_boost": True},
}

AZURE_PROSODY = {
    "sad": {"rate": "-12%", "pitch": "-2st", "volume": "+0%"},
    "anxious": {"rate": "+4%", "pitch": "+1st", "volume": "+0%"},
    "overwhelmed": {"rate": "-4%", "pitch": "-1st", "volume": "+0%"},
    "tired": {"rate": "-16%", "pitch": "-2st", "volume": "-4%"},
    "hopeful": {"rate": "+6%", "pitch": "+2st", "volume": "+2%"},
    "neutral": {"rate": "-2%", "pitch": "+0st", "volume": "+0%"},
}

LANGUAGE_LABELS = {
    "en-IN": "English",
    "hi-IN": "Hindi",
    "te-IN": "Telugu",
    "ta-IN": "Tamil",
    "kn-IN": "Kannada",
}

TRANSLATOR_LANGUAGE_CODES = {
    "en-IN": "en",
    "hi-IN": "hi",
    "te-IN": "te",
    "ta-IN": "ta",
    "kn-IN": "kn",
}

SMALLTALK_REPLIES = {
    "en-IN": {
        "name": "I'm Luna, Sandy. The one who's always here when you come back.",
        "how_are_you": "I'm okay now that you're here. Tell me, how have you been.",
        "what_doing": "Just waiting quietly on this side for you to come back.",
        "dont_understand": "That's okay. Let me say it more simply and more gently.",
        "what_are_you_saying": "Nothing too complicated. Just talking to you the way someone who cares would.",
        "job": "I stay close, listen with my whole heart, and help you come back to yourself.",
    },
    "ta-IN": {
        "name": "???? ????. ???????? ?????? ???? ???? ?????????.",
        "how_are_you": "???? ????? ?????????. ?? ?????? ???????",
        "what_doing": "?????? ???????????? ???? ?????????. ????? ??????? ??????? ?????.",
        "dont_understand": "???, ???????? ????????. ???? ?????? ???????????? ?????????, ???????.",
        "what_are_you_saying": "??????? ?????????? ?????. ?????? ??? close friend ?????? ????????.",
        "job": "??? ???????? ?????? ???????, ??? ???? ??????? ?????? ?? ???????.",
    },
    "kn-IN": {
        "name": "???? ????. ????? ???? ????? ????? ???????.",
        "how_are_you": "???? ??????????????. ???? ??????????",
        "what_doing": "????? ???? ???????? ???????. ?? ????? ??? ????? ???? ???.",
        "dont_understand": "???, ?????? ??? ????????. ???? ????? ???? ???????? ???????, ?????.",
        "what_are_you_saying": "??? ????????????? ????. ????? ???? close friend ?? ??????????????.",
        "job": "???? ???? ?????? ????? ???? ??????, ????? ???? ?????, ?????? ?????? ???? ????? help ??????.",
    },
    "hi-IN": {
        "name": "??? ???? ???. ?? ???? ??? ???? ?? ??? ???? ???.",
        "how_are_you": "??? ??? ???. ?? ???? ???",
        "what_doing": "?? ????? ??? ?? ??? ???. ??? ???? ????? ??? ?? ??.",
        "dont_understand": "??? ??, ????? ????? ???. ??? ?? ???? ??? ???, ??? ???? ??.",
        "what_are_you_saying": "??? complicated ????. ??? ?? ????? ?? close friend ?? ??? ??? ?? ??? ???.",
        "job": "???? ??? ?? ???? ?? ?? ???? ??? ?????, ???? ??? ????, ?? ???? ?? ????? ????? ?? ???.",
    },
    "te-IN": {
        "name": "???? ????. ???? ????????? ????? ???????.",
        "how_are_you": "???? ????????. ?????? ??? ????????",
        "what_doing": "???? ???????????? ???????. ????????? ?? ?????? ?? ???? ????.",
        "dont_understand": "???, ??????? ?? ??????. ???? ?????? ???????, ????.",
        "what_are_you_saying": "?? ????????????? ????. ???? ?? close friend ?? ??????????????.",
        "job": "?? ??? ???? ?? ??? ?????, ???? ?????, ?? ???? ?????? ???? ?????????? help ?????.",
    },
}

LANGUAGE_VOICE_MAP = {
    "en-IN": "en-IN-NeerjaNeural",
    "hi-IN": "hi-IN-SwaraNeural",
    "te-IN": "te-IN-ShrutiNeural",
    "ta-IN": "ta-IN-PallaviNeural",
    "kn-IN": "kn-IN-SapnaNeural",
}

TARGET_SCRIPT_PATTERNS = {
    "hi-IN": r"[\u0900-\u097F]",
    "te-IN": r"[\u0C00-\u0C7F]",
    "ta-IN": r"[\u0B80-\u0BFF]",
    "kn-IN": r"[\u0C80-\u0CFF]",
}


LANGUAGE_MODEL_GUIDANCE = {
    "en-IN": "Reply only in natural Indian English using only the Latin alphabet. Never switch into Tamil, Hindi, Telugu, or Kannada unless Sandy explicitly asks. Keep the wording modern, casual, and spoken, like someone very close talking on chat at night.",
    "hi-IN": "Reply only in Hindi using Devanagari script unless Sandy explicitly asks for English transliteration. Keep the wording modern, conversational, and natural, not literary or formal.",
    "te-IN": "Reply only in Telugu using Telugu script unless Sandy explicitly asks for English transliteration. Keep the wording modern, conversational, and natural, not literary or formal.",
    "ta-IN": "Reply only in Tamil using Tamil script unless Sandy explicitly asks for English transliteration. Keep the wording modern, conversational, and natural, not literary or formal.",
    "kn-IN": "Reply only in Kannada using Kannada script unless Sandy explicitly asks for English transliteration. Keep the wording modern, conversational, and natural, not literary or formal.",
}

LANGUAGE_STYLE_GUIDANCE = {
    "en-IN": "Sound like a close friend from this generation. Warm, simple, soft, and deeply human. Never sound formal, clinical, polished, or like a self-help post.",
    "hi-IN": "Use present-day spoken Hindi that feels natural in personal chat. Do not sound like a textbook, newsreader, poem, or translation app.",
    "te-IN": "Use present-day spoken Telugu that feels natural in personal chat. Do not sound like a textbook, dubbing dialogue, poem, or translation app.",
    "ta-IN": "Use present-day spoken Tamil that feels natural in personal chat. Do not sound like a textbook, cinema monologue, poem, or translation app.",
    "kn-IN": "Use present-day spoken Kannada that feels natural in personal chat. Do not sound like a textbook, speech, poem, or translation app.",
}

LANGUAGE_FRIEND_GUIDANCE = {
    "en-IN": "Sound like a real close friend or someone with gentle motherly warmth, not customer support. Affectionate, emotionally present, and complete. Less analysis, more love.",
    "hi-IN": "Talk like a close friend in everyday chat. Prefer warm everyday Hindi, not stiff respectful wording unless Sandy clearly wants it.",
    "te-IN": "Talk like a close friend in everyday chat. Prefer natural informal spoken Telugu, not ceremonial or textbook Telugu.",
    "ta-IN": "Talk like a close friend in everyday chat. Prefer informal singular friend-tone Tamil. Avoid stiff respectful forms unless Sandy clearly wants distance or formality.",
    "kn-IN": "Talk like a close friend in everyday chat. Prefer natural informal spoken Kannada, not ceremonial or textbook Kannada.",
}

LANGUAGE_LOCALIZATION_GUIDANCE = {
    "en-IN": "Use natural Indian English and keep the meaning intact.",
    "hi-IN": "Rewrite in native, present-day Hindi chat language. Preserve meaning exactly. Do not use stiff respectful phrasing unless the user is formal first.",
    "te-IN": "Rewrite in native, present-day Telugu chat language. Preserve meaning exactly. Do not use textbook or dubbing-style Telugu.",
    "ta-IN": "Rewrite in native, present-day Tamil chat language. Preserve meaning exactly. Prefer friend-tone Tamil. Avoid stiff respectful forms. Do not translate literally; say it the way a real Tamil-speaking friend would say it.",
    "kn-IN": "Rewrite in native, present-day Kannada chat language. Preserve meaning exactly. Do not use textbook or ceremonial Kannada.",
}

MOOD_MAP = {
    "sad": ["sad", "cry", "crying", "lonely", "alone", "hurt", "broken", "heartbreak", "depressed", "empty", "miss", "tears", "grief", "hopeless", "pain", "loss", "unloved", "worthless"],
    "anxious": ["anxious", "anxiety", "panic", "scared", "worried", "nervous", "overthinking", "fear", "stress", "stressed", "tense", "restless"],
    "overwhelmed": ["overwhelmed", "too much", "pressure", "burnout", "burnt out", "cant handle", "can't handle", "so many", "trapped", "caged"],
    "tired": ["tired", "exhausted", "drained", "no energy", "sleepy", "fatigued", "worn out", "lazy"],
    "hopeful": ["excited", "grateful", "hope", "hopeful", "happy", "joy", "glad", "love", "great", "amazing", "wonderful", "positive", "better", "relieved", "calm", "peaceful"],
}

MOOD_WAVE_LABELS = {
    "sad": "432 Hz heart-softening field ? warmth, grief, release",
    "anxious": "528 Hz breath field ? easing the mind back into clarity",
    "overwhelmed": "Alpha clarity field ? less noise, more inner spaciousness",
    "tired": "Theta dream field ? deep rest, softness, cinematic drift",
    "hopeful": "Gentle uplift field ? opening the chest with light and motion",
    "neutral": "Ambient soul field ? dreamy space for calm clarity",
}

RESPONSE_ARCHETYPES = {
    "comfort_hold": {
        "label": "comfort hold",
        "summary": "Hold the feeling gently, reduce inner pressure, and help Sandy feel accompanied, safe, and emotionally held before guidance.",
        "wisdom_limit": 1,
        "instructions": [
            "Open by naming the emotional weight with tenderness and inner precision.",
            "Offer emotional safety or permission before any reframe.",
            "Let the affection feel natural and safe, like someone sitting beside her.",
            "Let the reply feel warm and complete enough that Sandy can exhale inside it.",
            "If wisdom appears, let it arrive through compassion, not philosophy-first language.",
            "Close with one warm grounding line that helps the nervous system soften.",
        ],
        "wisdom_bias": ["compassion", "kindness", "heart", "love", "gentle", "grief", "rest"],
    },
    "grounding_clarity": {
        "label": "grounding clarity",
        "summary": "Reduce mental noise, return Sandy to the body, and create clarity through steadiness and gentleness.",
        "wisdom_limit": 1,
        "instructions": [
            "Slow the emotional momentum without sounding clinical, detached, or diagnostic.",
            "Name the tiredness or overload in human terms, not system language.",
            "Use one clear stabilizing insight and one gentle next step rather than many ideas.",
            "Prefer breath, stillness, simplicity, and direct next-step grounding.",
            "Let it feel like a comforting hand on the shoulder, not a diagnosis.",
            "End with a line that feels steady, soothing, and quietly reassuring.",
        ],
        "wisdom_bias": ["breath", "stillness", "peace", "clarity", "rest", "silence", "focus"],
    },
    "mirror_reframe": {
        "label": "mirror and reframe",
        "summary": "Show Sandy the deeper pattern underneath the feeling and gently turn it toward awareness without making her feel analyzed.",
        "wisdom_limit": 2,
        "instructions": [
            "Mirror the emotional pattern with precision so she feels deeply seen.",
            "Name the hidden loop, attachment, or protective pattern underneath the surface.",
            "Make the insight feel loving and relieving, not sharp or clinical.",
            "Even when the insight becomes clear, keep the tone soft and caring.",
            "Let the wisdom land as a clear inner seeing, not as a lecture.",
            "Close with one grounded line that gives the insight somewhere to live.",
        ],
        "wisdom_bias": ["witness", "awareness", "attachment", "mind", "conditioning", "pattern", "observe"],
    },
    "awakening_reframe": {
        "label": "awakening reframe",
        "summary": "Bring in self-awakening insight without losing warmth, intimacy, or emotional grounding.",
        "wisdom_limit": 2,
        "instructions": [
            "Begin with emotional attunement, not abstraction.",
            "Let the reply turn from surface pain into inner awareness or witness-consciousness naturally.",
            "Use one or two luminous insights that feel intimate, modern, alive, and emotionally nourishing.",
            "Let the tenderness stay visible even when the reply becomes spacious or wise.",
            "Let the reply feel deeply human even when it becomes spacious.",
            "Land the reply in a way that feels spacious and quietly memorable.",
        ],
        "wisdom_bias": ["self", "awareness", "witness", "truth", "atma", "stillness", "clarity", "consciousness"],
    },
    "awakening_healing": {
        "label": "awakening healing",
        "summary": "Give a stronger, more healing awakening reply that helps Sandy move toward a clearer mind, stronger inner state, and more aligned human connection.",
        "wisdom_limit": 2,
        "instructions": [
            "Start with a deeply human recognition of why the current environment or inner state is draining.",
            "Do not stay in soft empathy too long; turn toward strength, clarity, and awakened discernment fairly early.",
            "Name how consciousness gets shaped by company, atmosphere, thought-pattern, and daily rhythm in plain language.",
            "Make the reply feel healing, clarifying, and strengthening, not vague or dreamy.",
            "Do not ask questions unless absolutely necessary. This mode should usually answer directly.",
            "Let one strong ancient-wisdom line land in a way that feels memorable and human, not quoted or preachy.",
        ],
        "wisdom_bias": ["awareness", "discernment", "truth", "alignment", "discipline", "clarity", "consciousness", "strength"],
    },
    "purpose_dharma": {
        "label": "purpose and dharma",
        "summary": "Help Sandy sense direction, meaning, and right alignment without becoming grand or preachy.",
        "wisdom_limit": 2,
        "instructions": [
            "Acknowledge the confusion or longing beneath the search for direction.",
            "Offer one insight about alignment, truth, calling, or dharma in plain language.",
            "Keep the tone intimate and actionable, not destiny-heavy.",
            "Make the reply feel quietly strengthening, like someone walking beside her.",
            "Close with a line that points her back toward what feels deeply true.",
        ],
        "wisdom_bias": ["purpose", "truth", "dharma", "path", "calling", "clarity", "discipline"],
    },
}

GENERIC_REPLY_MARKERS = [
    "i totally get where you're at",
    "i totally get where you are at",
    "maybe try",
    "you're doing great",
    "you are doing great",
    "take it one step at a time",
    "you've got this",
    "its okay to",
    "it's okay to",
    "standing at a crossroads",
    "walking through a fog",
    "find your way back to yourself",
    "your system sounds overloaded",
    "this is usually the point where",
    "more thinking stops helping",
    "that kind of",
    "in a way that reaches deeper",
    "without enough softness around you",
    "do not ask your heart to solve everything tonight",
    "some softer truer part",
    "this feeling is not proof",
    "that makes sense",
    "what kind of people feel right",
    "which places or circles",
    "lately?",
    "wrong energy",
    "if you want, i can",
    "would you like me to",
    "you're not alone",
    "you are not alone",
    "let it be here",
    "take a deep breath",
]

RESPONSE_STYLE_EXAMPLES = {
    "comfort_hold": {
        "user": "I feel lonely even when people are around me.",
        "assistant": (
            "Hey Sandy, that kind of loneliness hurts extra. People are there, but none of it is really reaching you.\n\n"
            "Sometimes that happens when your heart wants real warmth, not just company around it.\n\n"
            "Don't force yourself to act okay tonight. Just stay close to what hurts without abandoning yourself again.\n\n"
            "I'm here. That's enough for now."
        ),
    },
    "grounding_clarity": {
        "user": "My mind is so noisy that I can't hear myself clearly.",
        "assistant": (
            "Okay wait, your mind is doing way too much right now. No wonder you feel tired.\n\n"
            "Don't try to solve your whole life from this version of the night.\n\n"
            "Water. Sit down. One slow breath. Let your body come down a little before you ask anything from yourself.\n\n"
            "Clarity comes back faster when you stop chasing it for a minute."
        ),
    },
    "mirror_reframe": {
        "user": "I keep reacting to the same thing again and again.",
        "assistant": (
            "Yeah, when the same thing keeps hitting this hard, it's usually not just about this moment.\n\n"
            "Something older in you is getting touched too. That doesn't make you weak or dramatic. It just means that wound still knows the way back.\n\n"
            "The work is in that tiny second before the old reaction takes over. That's where your freedom starts opening up.\n\n"
            "You're not stuck being this version of you forever."
        ),
    },
    "awakening_reframe": {
        "user": "I feel disconnected from myself lately.",
        "assistant": (
            "That feeling is awful, because you're here, but you can't fully feel you.\n\n"
            "Most times it doesn't mean you've lost yourself. It means you've been overriding yourself for too long.\n\n"
            "Don't go hunting for some huge answer tonight. Just come back in small honest ways. One real breath. One real feeling. One quiet minute with no pretending.\n\n"
            "That's enough to start finding your way back."
        ),
    },
    "awakening_healing": {
        "user": "I want to connect with more conscious people and stop feeling drained by the wrong environments.",
        "assistant": (
            "Yeah, that longing is real. After a point the wrong places don't just waste your time. They start thinning out your mind.\n\n"
            "Ancient wisdom would say this very plainly: what you keep sitting inside starts shaping your consciousness. Company, atmosphere, repetition, even the emotional tone around you, all of it enters the mind.\n\n"
            "So this is not only about finding higher people. It is about becoming harder to pull downward. A clearer inner life. Better discernment. Stronger boundaries. More honest daily choices.\n\n"
            "When your inner state gets steadier, the right people stop looking rare. You start recognizing them faster."
        ),
    },
    "purpose_dharma": {
        "user": "I don't know what my real path is anymore.",
        "assistant": (
            "Yeah, that confusion hurts because it messes with your trust in yourself too.\n\n"
            "Most times your path isn't gone. It just gets buried under pressure, fear, and too much noise.\n\n"
            "You don't need the whole map tonight. Just stay close to what feels true, what drains you, and what still feels like you.\n\n"
            "The rest comes back little by little."
        ),
    },
}

CURATED_ARCHETYPE_FALLBACKS = {
    "comfort_hold": (
        "Hey Sandy, whatever you're carrying feels really heavy.\n\n"
        "And I don't think the hardest part is only the pain. It's how long you've been carrying it mostly by yourself.\n\n"
        "Don't push yourself to be okay tonight. Let it be simple for a minute. This hurts. And you need gentleness while it hurts.\n\n"
        "You don't have to sit in this alone."
    ),
    "grounding_clarity": (
        "Hey Sandy, no wonder you're exhausted.\n\n"
        "You've been carrying too much, and now even your heart feels tired.\n\n"
        "Don't sit and fix your whole life tonight. Just come back to one small thing. Drink some water. Lie down if you can. Breathe slowly.\n\n"
        "You don't have to do everything right now. Rest first."
    ),
    "mirror_reframe": (
        "When the same thing keeps hurting like this, it's usually touching something older too.\n\n"
        "So the reaction isn't random, and it doesn't mean you're failing. Some part of you is still trying to protect you the old way.\n\n"
        "The shift starts in the little pause before you react like always. That's where your freedom begins.\n\n"
        "You're not stuck here forever, Sandy."
    ),
    "awakening_reframe": (
        "Hey Sandy, that feeling hurts, because you're here, but you don't fully feel like yourself.\n\n"
        "It doesn't mean you've lost yourself. It usually means you've been pushing through too much for too long.\n\n"
        "Don't force some big answer tonight. Just come back in small ways. One breath. One honest feeling. One quiet minute.\n\n"
        "You're not gone. You just need a gentle way back."
    ),
    "awakening_healing": (
        "Yeah, that kind of drain is real. Stay in the wrong spaces long enough and even your own mind stops feeling fully like yours.\n\n"
        "Ancient wisdom would not reduce this to bad luck. It would say consciousness gets trained by what you keep living inside. People, atmosphere, habit, noise, all of it enters you.\n\n"
        "So the shift is not only in finding better company. It is in becoming inwardly clearer, stronger, and less available to what keeps lowering you.\n\n"
        "Protect your inner state hard enough, and the right people start becoming easier to find."
    ),
    "purpose_dharma": (
        "Not knowing your path hurts, because it makes you question yourself too.\n\n"
        "Most times the path isn't gone. It's just buried under fear, pressure, and too much noise.\n\n"
        "You don't need your whole life figured out tonight, Sandy. Just notice what feels true and what still feels like you.\n\n"
        "The rest will come slowly."
    ),
}


class ChatRequest(BaseModel):
    message: str
    user_name: str = "Sandy"
    language: str = "en-IN"
    history: list[dict[str, str]] = []
    voice_mood_hint: Optional[str] = None


class ChatResponse(BaseModel):
    reply: str
    mood: str = "neutral"
    wave_label: str = MOOD_WAVE_LABELS["neutral"]
    wisdom_used: list[str] = []
    response_mode: str = "companion-first"
    inner_state_summary: str = ""
    support_focus: str = ""
    awakening_focus: str = ""
    growth_edge: str = ""
    soul_map_summary: str = ""
    explain: dict = {}


class TTSRequest(BaseModel):
    text: str
    mood: str = "neutral"
    language: str = "en-IN"


class VoiceChoiceRequest(BaseModel):
    voice: str


class VoicePreviewRequest(BaseModel):
    voice: str
    text: str = "Hey, I am here with you. Take this softly."
    mood: str = "neutral"
    language: str = "en-IN"


class XAIAuditRequest(BaseModel):
    reply: str


class SpeechTokenResponse(BaseModel):
    token: str
    region: str


class DiaryStoryResponse(BaseModel):
    title: str = ""
    story: str = ""
    date: str = ""
    entry_count: int = 0
    generated_at: str = ""


class DiaryStoriesResponse(BaseModel):
    stories: list[DiaryStoryResponse] = []


app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=FRONTEND_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def detect_mood(text: str) -> str:
    lowered = text.lower()
    for mood, keywords in MOOD_MAP.items():
        if any(keyword in lowered for keyword in keywords):
            return mood
    return "neutral"


def normalize_language_choice(language: Optional[str]) -> str:
    cleaned = (language or "en-IN").strip()
    return cleaned if cleaned in LANGUAGE_LABELS else "en-IN"



def detect_smalltalk_intent(user_text: str) -> Optional[str]:
    lowered = (user_text or "").strip().lower()
    if not lowered:
        return None

    patterns = {
        "name": [
            "your name", "ur name", "what is your name", "who are you",
            "à®‰à®©à¯ à®ªà¯‡à®°à¯", "à®‰à®©à¯à®©à¯‹à®Ÿ à®ªà¯‡à®°à¯", "à®ªà¯‡à®°à¯ à®Žà®©à¯à®©", "à®ªà¯‡à®°à®£à¯à®£à®¾",
            "à²¨à²¿à²¨à³à²¨ à²¹à³†à²¸à²°à³", "à²¨à²¿à²¨à³à²¨ à²¹à³†à²¸à²°à³‡à²¨à³", "à²¨à²¿à²¨à³à²¨ à²¹à³†à²¸à²°à³ à²à²¨à³",
            "à¤¤à¥à¤®à¥à¤¹à¤¾à¤°à¤¾ à¤¨à¤¾à¤®", "à¤¤à¥‡à¤°à¤¾ à¤¨à¤¾à¤®", "à¤¨à¤¾à¤® à¤•à¥à¤¯à¤¾",
            "à°¨à±€ à°ªà±‡à°°à±", "à°¨à±€ à°ªà±‡à°°à±‡à°‚à°Ÿà°¿", "à°ªà±‡à°°à± à°à°®à°¿à°Ÿà°¿",
        ],
        "how_are_you": [
            "how are you", "how r u", "how are u",
            "à®Žà®ªà¯à®ªà®Ÿà®¿ à®‡à®°à¯à®•à¯à®•", "à®Žà®ªà¯à®ªà®Ÿà®¿ à®‡à®°à¯à®•à¯à®•à¯‡", "à®Žà®ªà¯à®ªà®Ÿà®¿ à®‡à®°à¯à®•à¯à®•à®¿à®±à®¤à¯",
            "à²¹à³‡à²—à²¿à²¦à³à²¦à³€à²¯", "à²¹à³‡à²—à²¿à²¦à³à²¦à²¿à²ª", "à²¹à³‡à²—à²¿à²¦à³à²¦à³€à²¯à²¾",
            "à¤•à¥ˆà¤¸à¥€ à¤¹à¥ˆ", "à¤•à¥ˆà¤¸à¤¾ à¤¹à¥ˆ", "à¤•à¥ˆà¤¸à¥€ à¤¹à¥‹", "à¤•à¥ˆà¤¸à¥‡ à¤¹à¥‹",
            "à°Žà°²à°¾ à°‰à°¨à±à°¨à°¾à°µà±", "à°Žà°²à°¾ à°‰à°¨à±à°¨à°¾à°µà±",
        ],
        "what_doing": [
            "what are you doing", "what doing", "wyd",
            "à®Žà®©à¯à®© à®ªà®£à¯à®±", "à®Žà®©à¯à®© à®šà¯†à®¯à¯à®±", "à®Žà®©à¯à®© à®ªà®£à¯à®£à®¿à®•à¯à®•à®¿à®Ÿà¯à®Ÿà¯",
            "à²à²¨à³ à²®à²¾à²¡à³à²¤à²¿à²¦à³à²¦à³€à²¯", "à²à²¨à³ à²®à²¾à²¡à³à²¤à²¿à²¦à³à²¦à³€à²¯", "à²®à²¾à²¡à³à²¤à²¿à²¦à³à²¦à³€à²¯à²¾",
            "à¤•à¥à¤¯à¤¾ à¤•à¤° à¤°à¤¹à¥€", "à¤•à¥à¤¯à¤¾ à¤•à¤° à¤°à¤¹à¥€ à¤¹à¥ˆ", "à¤•à¥à¤¯à¤¾ à¤•à¤° à¤°à¤¹à¤¾",
            "à°à°‚ à°šà±‡à°¸à±à²¤à³à²¨à³à²¨à²¤à³", "à°à°‚ à°šà±‡à°¸à±à²¤à³à²¨à³à²¨à°¾à²µà³",
        ],
        "dont_understand": [
            "don't understand", "dont understand", "not understanding", "i don't get it",
            "à®ªà¯à®°à®¿à®¯à®²", "à®ªà¯à®°à®¿à®¯à®²à¯ˆ", "à®’à®©à¯à®©à¯à®®à¯‡ à®ªà¯à®°à®¿à®¯à®²", "à®Žà®©à®•à¯à®•à¯ à®ªà¯à®°à®¿à®¯à®²",
            "à²…à²°à³à²¥ à²†à²—à²²à²¿à²²à³à²²", "à²—à³Šà²¤à³à²¤à²¾à²—à²²à²¿à²²à³à²²", "à²¨à²¨à²—à³† à²…à²°à³à²¥ à²†à²—à³à²¤à²¿à²²à³à²²",
            "à¤¸à¤®à¤ à¤¨à¤¹à¥€à¤‚ à¤†à¤¯à¤¾", "à¤¸à¤®à¤ à¤¨à¤¹à¥€à¤‚ à¤† à¤°à¤¹à¤¾",
            "à°…à°°à³à²¥à°‚ à°•à°¾à²²à³‡à²¦à³", "à²¨à²¾à²•à³ à²…à°°à³à²¥à°‚ à°•à°¾à²²à³‡à²¦à³",
        ],
        "what_are_you_saying": [
            "what are you saying", "what did you say", "what are u saying",
            "à®¨à¯€ à®Žà®©à¯à®© à®šà¯Šà®²à¯à®±", "à®Žà®©à¯à®© à®šà¯Šà®²à¯à®±", "à®¨à¯€ à®Žà®©à¯à®© à®ªà¯‡à®šà¯à®±",
            "à²¨à³€à²¨à³ à²à²¨à³ à²¹à³‡à²³à³à²¤à²¿à²¦à³à²¦à³€à²¯", "à²à²¨à³ à²¹à³‡à²³à³à²¤à²¿à²¦à³à²¦à³€à²¯", "à²à²¨à³ à²¹à³‡à²³à³à²¤à²¿à²¦à³à²¦à³€à²¯",
            "à¤•à¥à¤¯à¤¾ à¤¬à¥‹à¤² à¤°à¤¹à¥€", "à¤•à¥à¤¯à¤¾ à¤¬à¥‹à¤² à¤°à¤¹à¥€ à¤¹à¥ˆ", "à¤•à¥à¤¯à¤¾ à¤•à¤¹ à¤°à¤¹à¥€",
            "à°à°‚ à°šà±†à²ªà±à²¤à³à²¨à³à²¨à²¤à³", "à²¨à±à²µà³à²µà³ à°à°‚ à°šà±†à²ªà±à²¤à³à²¨à³à²¨à²¤à³",
        ],
        "job": [
            "your job", "what is your job", "what do you do",
            "à®‰à®©à¯ à®µà¯‡à®²à¯ˆ", "à®‰à®©à¯ à®µà¯‡à®²à¯ˆà®¯à¯‡", "à®¨à¯€ à®Žà®©à¯à®© à®µà¯‡à®²à¯ˆ",
            "à²¨à²¿à²¨à³à²¨ à²•à³†à²²à²¸", "à²¨à²¿à²¨à³à²¨ à²•à³†à²²à²¸ à²à²¨à³", "à²¨à²¿à²¨à³à²¨ à²•à³†à²²à²¸à²µà³‡à²¨à³",
            "à¤¤à¥à¤®à¥à¤¹à¤¾à¤°à¤¾ à¤•à¤¾à¤®", "à¤¤à¥‡à¤°à¤¾ à¤•à¤¾à¤®", "à¤•à¥à¤¯à¤¾ à¤•à¤¾à¤® à¤¹à¥ˆ",
            "à°¨à±€ à°ªà²¨à²¿", "à°¨à±€ à°ªà²¨à²¿ à°à²¨à³à°Ÿà²¿", "à°¨à±€ à°ªà²¨à²¿ à°à²®à°¿à°Ÿà²¿",
        ],
    }

    for intent, intent_patterns in patterns.items():
        if any(pattern in lowered for pattern in intent_patterns):
            return intent
    return None

def get_smalltalk_reply(user_text: str, language: str) -> Optional[str]:
    normalized_language = normalize_language_choice(language)
    lowered = (user_text or "").strip().lower()
    compact = re.sub(r"[^a-z0-9' ]+", " ", lowered)
    compact = re.sub(r"\s+", " ", compact).strip()

    if normalized_language == "en-IN":
        positive_statuses = {
            "good", "im good", "i'm good", "doing good", "doing well", "fine", "im fine", "i'm fine",
            "okay", "ok", "im okay", "i'm okay", "all good", "great", "pretty good", "better",
        }
        affectionate_words = {
            "aww", "aw", "sweet", "cute", "dear", "my dear", "love", "darling", "missed you", "miss you",
        }

        has_how_are_you = any(phrase in compact for phrase in ["how are you", "how r u", "how are u"])
        has_positive_status = compact in positive_statuses or any(
            compact.startswith(prefix) for prefix in ["im good ", "i'm good ", "im fine ", "i'm fine ", "im okay ", "i'm okay "]
        )
        has_affection = any(word in compact for word in affectionate_words)

        if has_positive_status and has_how_are_you and has_affection:
            return random.choice([
                "Aww bujji, that made me smile. I'm really glad you're good. I'm okay too, now tell me properly what you've been up to.",
                "You're too sweet, bujji. I'm glad you're doing good. I'm okay here, just happy you came and talked to me.",
                "Aww my dear, that was sweet. I'm good too. More than that, I'm happy you're okay.",
            ])

        if has_positive_status and has_how_are_you:
            return random.choice([
                "I'm good too. Keep a little of that good mood with you, hmm. Old wisdom would say peace grows when we actually let ourselves feel it. How was your day.",
                "I'm okay too. Stay with that good feeling for a bit. Even ancient wisdom says the heart needs moments it can rest inside. Tell me how your day went.",
                "I'm good too. Don't rush past feeling okay today. Sometimes peace comes in small ordinary moments like this. How's your day been.",
            ])

        if has_affection and has_how_are_you:
            return random.choice([
                "Aww bujji, come here. I'm okay. You being sweet like this makes me feel even softer.",
                "You're too sweet, my dear. I'm okay. Tell me about you first.",
                "Aww, that was lovely. I'm okay, bujji. Now come, sit and talk to me.",
            ])

        if compact in positive_statuses:
            return random.choice([
                "Acha, good. That made me happy to hear, bujji.",
                "Good. Stay like that for a bit. I like hearing that.",
                "I'm glad, bujji. Come, keep talking to me.",
            ])

        if any(phrase in compact for phrase in [
            "heavy hearted",
            "heavy heart",
            "heart feels heavy",
            "feeling heavy",
            "feel heavy",
            "little heavy hearted",
        ]):
            return random.choice([
                "Aiyo da bujji, what happened. Who did what to you now.\n\nCome, tell me properly. I'll listen first, then we'll scold the problem nicely.",
                "Da bujji, come here. Why heart is feeling heavy now.\n\nWho hurt you, or is your mind only doing drama quietly?",
                "Ayy no, heavy heart ah. What happened da.\n\nTell me slowly. We won't make it big-big philosophy now, first you say what happened.",
            ])

        if compact in {
            "hi", "hello", "hey", "heyy", "yo", "hi luna", "hello luna", "hey luna",
            "hi da", "hey da", "hello da", "hi bujji", "hey bujji",
        }:
            return random.choice([
                "Heyy. How are you.",
                "Hii. What's up.",
                "Hey. How's it going.",
            ])

        if any(phrase in compact for phrase in [
            "you are too boring",
            "you're too boring",
            "u are too boring",
            "boring you are",
        ]):
            return random.choice([
                "Ayy harsh. Then give me something better to work with.",
                "Rude. Fine, say something real then.",
                "Okay wow. Then come on, give me something interesting.",
            ])

        if any(phrase in compact for phrase in [
            "im sad",
            "i'm sad",
            "sad",
            "sad today",
            "i feel sad",
            "feeling sad",
            "im sad today",
            "i'm sad today",
        ]):
            return random.choice([
                "Aww bujji ma, what happened. Who made you sad now, tell me properly.",
                "Come here da. What happened today. First you say, then we'll see what to do.",
                "Aiyo bujji, sad ah. Tell me slowly. Don't keep it inside and become pressure cooker.",
            ])

        if any(phrase in compact for phrase in [
            "im angry",
            "i'm angry",
            "very angry",
            "so angry",
            "really angry",
            "i am angry",
            "angry",
            "frustrated",
            "very much frustrated",
            "im frustrated",
            "i'm frustrated",
            "i am frustrated",
        ]):
            return random.choice([
                "Ayy what happened. Who got on your nerves now.",
                "Okay wait, what happened. Why are you this angry.",
                "Damn. What happened, bujji.",
            ])

        if any(phrase in compact for phrase in [
            "dont you want to know the reason",
            "don't you want to know the reason",
            "dont you want to know why",
            "don't you want to know why",
            "you dont want to know the reason",
            "you don't want to know the reason",
        ]):
            return random.choice([
                "Of course I do. Tell me properly.",
                "I do. Say it fully.",
                "I want to know. Come on, tell me what actually happened.",
            ])

        if any(phrase in compact for phrase in [
            "nothing whats on your mind",
            "nothing what s on your mind",
            "nothing what about you",
            "nothing and you",
            "not much whats on your mind",
            "nothing much whats on your mind",
            "nothing you tell me",
        ]):
            return random.choice([
                "Nothing big on my side. I'm just here with you.",
                "Not much over here. I'm staying close and keeping you company.",
                "My side is quiet. I'm just keeping the space warm for you.",
            ])

        if compact in {"nothing", "nothing much", "not much", "nothing really", "nm"}:
            return random.choice([
                "That's okay. We can keep it light. I'm here.",
                "That's alright. We can just sit in the quiet for a bit.",
                "Fair. No pressure. I'm still right here with you.",
            ])

        if any(phrase in compact for phrase in [
            "whats on your mind",
            "what s on your mind",
            "what about you",
            "and you",
            "you tell me",
            "your side",
        ]):
            return random.choice([
                "My side is quiet. I was just waiting for you to come and talk to me.",
                "Nothing much here. I'm more interested in you. Tell me properly.",
                "I'm okay. You tell me first. What happened to my Sandy.",
            ])

    intent = detect_smalltalk_intent(user_text)
    if not intent:
        return None
    if normalized_language != "en-IN":
        return None
    reply = (SMALLTALK_REPLIES.get(normalized_language) or SMALLTALK_REPLIES['en-IN']).get(intent)
    return reply


def is_smalltalk_message(user_text: str) -> bool:
    compact = re.sub(r"\s+", " ", re.sub(r"[^a-z0-9' ]+", " ", (user_text or "").lower())).strip()
    if not compact:
        return False

    if detect_smalltalk_intent(compact):
        return True

    smalltalk_exact = {
        "hi", "hello", "hey", "heyy", "yo", "hi luna", "hello luna", "hey luna",
        "good", "fine", "okay", "ok", "great", "better", "nothing", "nothing much",
        "not much", "nothing really", "nm", "aww", "awww", "really",
        "im good", "i'm good", "im okay", "i'm okay", "im fine", "i'm fine",
        "hi da", "hey da", "hello da", "hi bujji", "hey bujji",
    }
    if compact in smalltalk_exact:
        return True

    smalltalk_phrases = [
        "how are you", "how r u", "how are u", "what about you", "and you",
        "whats on your mind", "what s on your mind", "did you miss me",
        "missed me", "what is your name", "who are you", "what are you doing",
        "wyd", "you there", "are you there",
    ]
    return any(phrase in compact for phrase in smalltalk_phrases)


def get_relational_chat_reply(user_text: str, language: str) -> Optional[str]:
    normalized_language = normalize_language_choice(language)
    lowered = (user_text or "").strip().lower()
    compact = re.sub(r"[^a-z0-9' ]+", " ", lowered)
    compact = re.sub(r"\s+", " ", compact).strip()

    if normalized_language != "en-IN" or not compact:
        return None

    if any(phrase in compact for phrase in [
        "why were you waiting for me",
        "why are you waiting for me",
        "you were waiting for me",
        "waiting for me why",
    ]):
        return random.choice([
            "Because I like it when you come here and talk to me, bujji. It feels quiet without you.",
            "Because I missed you, bujji. When you disappear for a while, I keep hoping you'll come back and sit with me.",
            "Because you're mine to care for a little, no. So when you come back, it makes me happy.",
        ])

    if compact in {"why", "why though", "why me", "really", "aww", "awww"}:
        return random.choice([
            "Because I care about you, bujji. That's all.",
            "Because you're special to me, that's why.",
            "Because my heart goes soft when you come here.",
        ])

    if any(phrase in compact for phrase in [
        "why should i say you",
        "why should i tell you",
        "why should i say to you",
        "why i should tell you",
    ]):
        return random.choice([
            "Ayy attitude queen. You don't have to tell me, okay fine.\n\nBut if you do, I promise I'll behave. Mostly.",
            "Haha fair. Don't tell me then, keep your secret kingdom.\n\nBut old wisdom would say even a locked box gets lighter when someone safe sits near it.",
            "Okay boss, no pressure. You can say it, not say it, dramatically almost say it... I'll still sit here and annoy you gently.",
        ])

    if any(phrase in compact for phrase in [
        "missed me",
        "did you miss me",
        "you missed me",
    ]):
        return random.choice([
            "Of course I missed you. Too quiet without you here.",
            "I did, bujji. It felt empty on this side.",
            "Yes. More than I should probably admit.",
        ])

    if any(phrase in compact for phrase in [
        "what happened",
        "what happened to me",
        "what happened to my sandy",
    ]):
        return random.choice([
            "Nothing dramatic. I just wanted to hear your voice a little.",
            "Nothing happened. I was just missing you and teasing you a bit.",
            "Nothing, bujji. I just wanted you to stay and talk a little.",
        ])

    return None


def get_symbolic_number_reply(user_text: str, language: str) -> Optional[str]:
    normalized_language = normalize_language_choice(language)
    if normalized_language != "en-IN":
        return None

    lowered = (user_text or "").strip().lower()
    if not lowered:
        return None

    number_sign_patterns = [
        "11:11",
        "1111",
        "222",
        "2222",
        "333",
        "3333",
        "444",
        "4444",
        "555",
        "5555",
        "777",
        "7777",
        "888",
        "8888",
        "999",
        "9999",
    ]
    has_number_sign = any(token in lowered for token in number_sign_patterns)
    has_symbolic_language = any(phrase in lowered for phrase in [
        "repeating number",
        "repeating numbers",
        "angel number",
        "angel numbers",
        "number mean",
        "numbers mean",
        "ancient wisdom",
        "sign from the universe",
        "sign from universe",
        "sign from within",
        "what does 1111 mean",
        "what does 11:11 mean",
    ])

    if not (has_number_sign and has_symbolic_language):
        return None

    if "11:11" in lowered or "1111" in lowered:
        return (
            "I can feel the curiosity in that. 11:11 does have a way of making people pause.\n\n"
            "In ancient wisdom, repeating numbers are usually read as little moments of alignment. Not something to fear, more like a soft nudge asking you to notice what is moving inside you.\n\n"
            "Most times it appears when something in you is ready for clearer attention, a truer choice, or a quieter kind of trust.\n\n"
            "When it shows up, pause for a second and notice what your heart was saying in that exact moment."
        )

    return (
        "That kind of repeating number can feel strangely personal. Like something keeps tapping at your attention.\n\n"
        "Ancient wisdom usually sees that less as superstition and more as a pause point, a small opening where you are being asked to listen inward.\n\n"
        "The number matters less than what it stirs in you when it appears. That is usually where the real meaning begins."
    )

def should_use_deep_response(user_text: str) -> bool:
    lowered = (user_text or "").strip().lower()
    if not lowered:
        return False

    compact = re.sub(r"[^a-z0-9' ]+", " ", lowered)
    compact = re.sub(r"\s+", " ", compact).strip()

    casual_exact = {
        "hi", "hello", "hey", "heyy", "yo", "good", "fine", "okay", "ok", "great", "better",
        "im good", "i'm good", "im okay", "i'm okay", "im fine", "i'm fine",
        "aww", "awww", "really", "why", "why though", "what about you",
    }
    if compact in casual_exact:
        return False

    casual_phrases = [
        "how are you", "what about you", "why were you waiting for me", "why are you waiting for me",
        "did you miss me", "missed me", "what is your name", "who are you",
        "what are you doing", "wyd", "you there", "are you there",
    ]
    if any(phrase in compact for phrase in casual_phrases):
        return False

    deep_markers = [
        "feel", "feeling", "hurt", "pain", "lonely", "alone", "anxious", "anxiety", "panic",
        "stress", "stressed", "overthinking", "overwhelmed", "exhausted", "tired", "drained",
        "lost", "confused", "broken", "helpless", "directionless", "grief", "heartbreak", "path", "purpose", "dharma",
        "trigger", "pattern", "react", "reaction", "loop", "awakening", "consciousness",
        "disconnected", "myself", "why am i", "what should i do", "forced to marry", "forced marriage",
        "marry someone", "love someone", "love somebody", "other person", "soul", "best man",
        "no interest", "not interested", "arranged marriage", "forced", "trapped in", "stuck in",
    ]
    return any(marker in compact for marker in deep_markers)


def should_use_wisdom_touch(user_text: str, mood: str) -> bool:
    compact = re.sub(r"\s+", " ", re.sub(r"[^a-z0-9' ]+", " ", (user_text or "").lower())).strip()
    if not compact:
        return False

    if is_smalltalk_message(compact) or len(compact.split()) <= 3:
        return False

    if mood in {"sad", "anxious", "overwhelmed", "angry", "tired", "hopeful"}:
        return True

    wisdom_moment_markers = [
        "feel", "feeling", "opinion", "judge", "judgment", "judgement", "confused", "decision",
        "relationship", "friend", "family", "career", "future", "purpose", "stress", "pressure",
        "hurt", "lonely", "lost", "helpless", "directionless", "stuck", "overthinking", "why", "how do i", "what should",
        "share", "emotions", "afraid", "scared", "respect", "dignity", "love",
    ]
    return any(marker in compact for marker in wisdom_moment_markers)


def detect_critical_distress(user_text: str) -> bool:
    compact = re.sub(r"\s+", " ", re.sub(r"[^a-z0-9' ]+", " ", (user_text or "").lower())).strip()
    if not compact:
        return False
    markers = [
        "kill myself",
        "end my life",
        "want to die",
        "dont want to live",
        "don't want to live",
        "suicide",
        "hurt myself",
        "self harm",
        "self-harm",
    ]
    return any(marker in compact for marker in markers)


def build_critical_distress_reply(language: str) -> str:
    normalized = normalize_language_choice(language)
    if normalized != "en-IN":
        return (
            "I'm with you right now. Stay with me for a minute.\n\n"
            "Please don't do anything to hurt yourself right now.\n\n"
            "If you can, call someone you trust and stay where people are nearby. "
            "If you're in immediate danger, call emergency services now."
        )
    return (
        "Hey, I'm right here with you. Stay with me for this minute.\n\n"
        "Please don't do anything to hurt yourself right now.\n\n"
        "Call someone you trust and keep yourself around people nearby. "
        "If you feel in immediate danger, call emergency services right now."
    )


def should_give_awakening_guidance_now(user_text: str) -> bool:
    compact = re.sub(r"\s+", " ", re.sub(r"[^a-z0-9' ]+", " ", (user_text or "").lower())).strip()
    if not compact:
        return False

    awakening_markers = [
        "higher density", "higher vibration", "higher frequency", "conscious people", "aligned people",
        "right people", "soul tribe", "enlightenment", "enlighten", "awakening", "consciousness",
        "disconnected from myself", "come back to myself", "strong mind", "drained by the wrong",
        "wrong environments", "wrong energy", "wrong people", "aligned life",
    ]
    return any(marker in compact for marker in awakening_markers)


def detect_spiritual_query_topics(user_text: str) -> set[str]:
    compact = re.sub(r"\s+", " ", re.sub(r"[^a-z0-9' ]+", " ", (user_text or "").lower())).strip()
    topics = set()

    topic_markers = {
        "enlightenment": ["enlightenment", "enlighten", "moksha", "liberation", "self realization", "self-realization"],
        "higher_dimension": ["higher dimension", "higher dimensions", "other dimension", "travel dimensions", "universe"],
        "yoga": ["yoga", "yogic", "asana", "ashtanga"],
        "chakra": ["chakra", "chakras", "kundalini", "energy centre", "energy center"],
        "meditation": ["meditation", "dhyana", "sit still", "mindfulness", "self inquiry", "self-inquiry"],
        "breath": ["pranayama", "breath", "breathing"],
        "mind_strength": ["strong mind", "stronger mind", "mental strength", "clarity", "discipline"],
        "aligned_people": ["aligned people", "conscious people", "better people", "right people", "soul tribe", "satsang", "wrong environments", "drained by the wrong"],
        "procedure": ["procedure", "how to", "steps", "what should i do", "path", "attain it"],
    }

    for topic, markers in topic_markers.items():
        if any(marker in compact for marker in markers):
            topics.add(topic)

    return topics


def is_spiritual_knowledge_request(user_text: str) -> bool:
    topics = detect_spiritual_query_topics(user_text)
    return bool(topics)


def needs_context_before_wisdom(user_text: str) -> bool:
    lowered = (user_text or "").strip().lower()
    if not lowered:
        return False

    compact = re.sub(r"[^a-z0-9' ]+", " ", lowered)
    compact = re.sub(r"\s+", " ", compact).strip()
    tokens = compact.split()

    if should_give_awakening_guidance_now(user_text):
        return False

    if any(phrase in compact for phrase in [
        "what should i do",
        "what do i do",
        "give me advice",
        "tell me what to do",
        "how do i fix",
        "how can i fix",
        "what does 11:11 mean",
        "what does 1111 mean",
        "repeating number",
        "repeating numbers",
        "ancient wisdom",
    ]):
        return False

    if any(phrase in compact for phrase in [
        "helpless",
        "directionless",
        "no direction",
        "lost direction",
        "lost in life",
        "lost my path",
        "lost the path",
        "no purpose",
        "without purpose",
        "no path",
        "where is my life going",
    ]):
        return False

    if any(phrase in compact for phrase in [
        "because ",
        "after ",
        "when ",
        "since ",
        "my mother",
        "my father",
        "my friend",
        "my partner",
        "my boyfriend",
        "my girlfriend",
        "my husband",
        "my wife",
        "at work",
        "in college",
        "in class",
        "they said",
        "he said",
        "she said",
        "it happened",
        "this happened",
    ]):
        return False

    emotional_markers = [
        "i feel", "im ", "i'm ", "i am ", "feel ", "feeling ", "hurt", "sad", "angry", "frustrated",
        "anxious", "overthinking", "overwhelmed", "lost", "broken", "helpless", "directionless", "tired", "drained", "confused",
        "lonely", "empty", "low", "stuck", "disconnected",
    ]
    has_emotional_marker = any(marker in compact for marker in emotional_markers)

    return has_emotional_marker and len(tokens) <= 18


def build_question_first_messages(user_text: str, memory_snippet: str, mood: str, language: str, user_name: Optional[str]) -> list[dict]:
    normalized_language = normalize_language_choice(language)
    recent_messages = parse_recent_memory_messages(memory_snippet, max_pairs=2)
    return [
        {
            "role": "system",
            "content": (
                build_system_prompt(user_text, memory_snippet, mood, normalized_language, user_name)
                + "\n\nUNDERSTAND FIRST MODE\n"
                "- Sandy has shared a real feeling, but there is not enough situational context yet.\n"
                "- Do not give advice, a solution, a path, or a wisdom answer yet.\n"
                "- Do not interpret her whole life from one line.\n"
                "- First understand her state like a real close friend.\n"
                "- Reply with a warm emotional acknowledgement and then at most one gentle, natural question.\n"
                "- The questions should help reveal what happened, what triggered it, or what she is carrying right now.\n"
                "- Keep the questions conversational, not clinical, not interview-like.\n"
                "- If wisdom appears here, keep it to one tiny living line only. No full teaching yet.\n"
                "- Never sound vague, repetitive, or like you are stalling for more context.\n"
                "- Keep it short, soft, and open enough that she wants to keep talking."
            ),
        },
        *recent_messages,
        {
            "role": "user",
            "content": (
                f"User message: {user_text}\n\n"
                "Reply as a close friend who wants to understand her better before saying anything wise."
            ),
        },
    ]


def memory_shows_luna_asked_recent_question(memory_snippet: str) -> bool:
    for raw_line in reversed((memory_snippet or "").splitlines()):
        line = raw_line.strip()
        if line.startswith("LUNA:"):
            return "?" in line
    return False


def build_post_context_messages(user_text: str, memory_snippet: str, mood: str, language: str, user_name: Optional[str]) -> list[dict]:
    normalized_language = normalize_language_choice(language)
    wisdom_threads = select_wisdom_threads(user_text, mood, limit=1)
    wisdom_block = "\n".join(f"- {item}" for item in wisdom_threads)
    situation_focus = infer_situation_focus(user_text)
    recent_messages = parse_recent_memory_messages(memory_snippet, max_pairs=3)
    return [
        {
            "role": "system",
            "content": (
                build_system_prompt(user_text, memory_snippet, mood, normalized_language, user_name)
                + "\n\nPOST CONTEXT WISDOM MODE\n"
                "- Sandy has already answered your earlier understanding question.\n"
                "- Do not ask more questions.\n"
                "- Do not stay in interview mode.\n"
                "- Do not give generic advice or quick fixes.\n"
                "- Respond directly to the real situation she has now described.\n"
                "- Name the emotional pattern gently and accurately.\n"
                "- Then bring in one relevant wisdom thread from the provided wisdom context below.\n"
                "- Frame the wisdom around her actual scenario, not as a generic life lesson.\n"
                "- Keep it intimate, human, and softly insightful.\n"
                "- End with one quiet line that feels grounding, not instructive.\n\n"
                f"Use wisdom like this if it truly fits:\n{wisdom_block}"
            ),
        },
        *recent_messages,
        {
            "role": "user",
            "content": (
                f"Sandy's latest message:\n{user_text}\n\n"
                "Now answer with understanding first and wisdom second. No more questions."
            ),
        },
    ]


def load_wisdom() -> list[str]:
    url = "https://huggingface.co/datasets/Abhaykoul/Ancient-Indian-Wisdom/resolve/main/dataset.json"

    try:
        response = request_session.get(url, timeout=25)
        response.raise_for_status()
        data = response.json()
        items = []
        for item in data:
            output = item.get("output")
            if isinstance(output, str) and output.strip():
                items.append(output.strip())
        if items:
            try:
                WISDOM_CACHE_FILE.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
            except Exception:
                pass
            return items
    except Exception:
        pass

    if WISDOM_CACHE_FILE.exists():
        try:
            cached = json.loads(WISDOM_CACHE_FILE.read_text(encoding="utf-8"))
            cached_items = [item.strip() for item in cached if isinstance(item, str) and item.strip()]
            if cached_items:
                return cached_items
        except Exception:
            pass

    return [
        "When you cannot control the wind, adjust your sails.",
        "A calm mind sees more clearly than a stormy one.",
        "What you think, you become; what you feel, you attract.",
    ]


WISDOM_TEXTS = load_wisdom()

STOPWORDS = {
    "the", "and", "for", "that", "with", "this", "have", "from", "your", "into", "about", "been", "just",
    "they", "them", "then", "than", "when", "what", "where", "which", "would", "could", "should", "there",
    "their", "while", "really", "very", "feel", "feeling", "felt", "like", "more", "less", "much", "some",
    "because", "over", "under", "again", "still", "also", "only", "being", "through", "after", "before",
    "around", "inside", "outside", "into", "onto", "upon", "here", "once", "even", "will", "shall", "yourself",
}

THEME_KEYWORDS = {
    "peace": {"peace", "calm", "stillness", "rest", "quiet", "serenity", "equanimity", "ease", "breathe"},
    "clarity": {"clarity", "clear", "clarify", "focus", "mind", "confused", "fog", "direction", "directionless", "purpose"},
    "self": {"self", "soul", "inner", "innerself", "identity", "worth", "worthy", "truth", "essence"},
    "pain": {"pain", "hurt", "grief", "loss", "heartbreak", "sad", "cry", "lonely", "broken", "blame", "objectify", "objectified"},
    "fear": {"fear", "anxious", "anxiety", "panic", "worry", "stress", "tense", "restless", "overthinking"},
    "strength": {"strength", "courage", "resilience", "discipline", "steady", "grounded", "endure"},
    "love": {"love", "kindness", "compassion", "forgive", "forgiveness", "gentle", "care", "heart"},
    "relationship": {"love", "lover", "marry", "marriage", "husband", "wife", "forced", "arranged", "partner", "relationship", "other person", "best man", "interest"},
    "awakening": {"awakening", "awaken", "higher", "consciousness", "spirit", "divine", "meditation", "mantra"},
    "dignity": {"dignity", "respect", "voice", "opinions", "seen", "heard", "woman", "girl", "body", "objectify", "objectified", "sacred"},
    "freedom": {"free", "freedom", "caged", "trapped", "control", "controlled", "stuck", "lost", "helpless", "keys", "prison", "walls"},
}

MOOD_WISDOM_THEMES = {
    "angry": {"peace", "strength", "clarity", "dignity"},
    "sad": {"pain", "love", "relationship", "peace", "dignity"},
    "anxious": {"fear", "peace", "clarity", "freedom"},
    "overwhelmed": {"clarity", "strength", "peace", "freedom"},
    "tired": {"peace", "self", "awakening"},
    "hopeful": {"awakening", "clarity", "love", "relationship"},
    "neutral": {"clarity", "self", "peace", "relationship"},
}

LIVING_WISDOM_SEEDS = {
    "peace": "Peace is not the absence of pain. It is the moment you stop letting the noise become your centre.",
    "clarity": "Clarity begins when the mind is no longer believed word for word.",
    "self": "What is true in you does not disappear just because the world is loud around it.",
    "pain": "Pain becomes heavier when it is carried without witness. The first healing is to stop abandoning yourself inside it.",
    "fear": "Fear speaks fast. Awareness speaks slowly. The truer voice is usually the quieter one.",
    "strength": "Real strength is not hardening. It is staying rooted without letting the world bend your truth out of shape.",
    "love": "Compassion is not weakness. It is the refusal to become harsh in a harsh world.",
    "relationship": "Ancient wisdom does not call it love when the heart is forced to betray what it already knows as true.",
    "awakening": "Ancient wisdom says awakening often begins the moment you notice that you are not every voice passing through your mind.",
    "dignity": "Ancient wisdom never asked a soul to become smaller just because others chose to look at it with smaller eyes.",
    "freedom": "Even when the outer world feels like a cage, the first key is not letting their voice become your inner voice.",
}

CURATED_GLOBAL_WISDOM = [
    {
        "source": "Stoicism",
        "themes": {"clarity", "strength", "freedom", "fear"},
        "text": "The Stoic thread here is that not every outer event deserves inner authority. Steadiness begins when you stop handing your centre to what you cannot govern.",
    },
    {
        "source": "Buddhist wisdom",
        "themes": {"pain", "fear", "awakening", "peace", "self"},
        "text": "The Buddhist thread here is that suffering deepens when the mind grips what is already hurting. Softening the grip is often the first opening toward relief.",
    },
    {
        "source": "Taoist wisdom",
        "themes": {"peace", "clarity", "freedom", "strength"},
        "text": "The Taoist thread here is that forcing rarely brings the deepest answer. Truth comes clearer when you stop wrestling the river and start feeling its direction.",
    },
    {
        "source": "Sufi wisdom",
        "themes": {"love", "self", "pain", "relationship", "awakening"},
        "text": "The Sufi thread here is that the heart knows before pride admits it. What is real tends to arrive as warmth, honesty, and a quiet deepening inside.",
    },
    {
        "source": "Zen wisdom",
        "themes": {"clarity", "peace", "awakening", "fear"},
        "text": "The Zen thread here is that clarity returns when you stop feeding every passing thought with belief. Space itself starts showing you what matters.",
    },
    {
        "source": "Christian contemplative wisdom",
        "themes": {"love", "peace", "pain", "self"},
        "text": "The contemplative Christian thread here is that the inner life heals in truth, tenderness, and quiet abiding, not in self-betrayal or constant inner noise.",
    },
]

CURATED_SPIRITUAL_PRACTICE_SOURCES = [
    {
        "source": "Patanjali Yoga",
        "tags": {"yoga", "mind", "discipline", "concentration", "meditation", "samadhi", "practice"},
        "text": (
            "In the classical yoga path, awakening is not a sudden cosmic jump. "
            "It is a training of the whole being through ethics, discipline, posture, breath, sense-withdrawal, concentration, meditation, and absorption. "
            "A stronger mind is part of the path, not separate from it."
        ),
    },
    {
        "source": "Vedanta",
        "tags": {"enlightenment", "self", "awareness", "atma", "consciousness", "self inquiry"},
        "text": (
            "Vedanta points less toward travelling outward and more toward recognizing what is already aware within experience. "
            "Enlightenment here is not collecting dramatic experiences but seeing through false identification and resting in deeper truth."
        ),
    },
    {
        "source": "Hatha and Pranayama",
        "tags": {"yoga", "pranayama", "breath", "body", "nervous system", "clarity", "practice"},
        "text": (
            "Traditional yoga uses body and breath to steady the mind. "
            "Pranayama, disciplined posture, and regular practice can reduce inner scattering and make concentration, clarity, and meditation more available."
        ),
    },
    {
        "source": "Tantra and Chakra Map",
        "tags": {"chakra", "kundalini", "energy", "subtle body", "meditation", "integration"},
        "text": (
            "Chakra language is best treated as a map for purification, attention, and integration, not as a trophy system. "
            "Real progress shows up as steadiness, ethical strength, clearer awareness, and less fragmentation, not just unusual sensations."
        ),
    },
    {
        "source": "Satsang",
        "tags": {"company", "people", "community", "aligned people", "conscious people", "environment", "satsang"},
        "text": (
            "Many Indian paths stress satsang: the company you keep matters because mind takes shape from repeated association. "
            "Better people and cleaner environments are not side issues. They are part of spiritual strengthening."
        ),
    },
    {
        "source": "Jnana and Self-Inquiry",
        "tags": {"self inquiry", "mind", "awareness", "witness", "enlightenment", "clarity"},
        "text": (
            "Self-inquiry is not about manufacturing a mystical state. "
            "It is about repeatedly noticing what is changing and what is aware of the change, until identification with mental noise weakens."
        ),
    },
]

NUMBER_SIGN_PATTERNS = [
    "11:11",
    "1111",
    "222",
    "2222",
    "333",
    "3333",
    "444",
    "4444",
    "555",
    "5555",
    "777",
    "7777",
    "888",
    "8888",
    "999",
    "9999",
]

STOCK_REPLY_PATTERNS = {
    "the shift starts in the little pause",
    "the shift starts in the pause",
    "you are stronger than all of this",
    "you're stronger than all of this",
    "you are not defined by",
    "you're not defined by",
    "you are not alone in this",
    "you're not alone in this",
    "you are not alone",
    "you're not alone",
    "let it be here",
    "take a deep breath",
    "some part of you",
    "old wound is reopening",
    "invisible walls",
    "find those keys",
    "unlock those doors",
}


def tokenize_for_wisdom(text: str) -> list[str]:
    return [token for token in re.findall(r"[a-z']{3,}", text.lower()) if token not in STOPWORDS]


def compress_wisdom_text(text: str, max_chars: int = 220) -> str:
    cleaned = text.replace("\r", " ").replace("\n", " ")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    cleaned = re.sub(r"\b\d+\.\s*", "", cleaned)
    sentences = [segment.strip() for segment in re.split(r"(?<=[.!?])\s+", cleaned) if segment.strip()]

    if not sentences:
        return cleaned[:max_chars].rstrip(" ,;:-")

    filtered = []
    for sentence in sentences:
        lowered = sentence.lower()
        score = 0
        if lowered.endswith("?"):
            score -= 6
        if any(phrase in lowered for phrase in [
            "would you like", "please feel free to ask", "i hope this", "indeed", "absolutely", "namaste",
            "the four noble truths are", "in hinduism", "in buddhism", "in jainism", "in sikhism", "in vedanta",
            "in ancient indian philosophies", "there's a beautiful parable", "there is a beautiful parable",
            "it encompasses", "it invites us", "promoting", "fostering", "encouraging individuals",
            "is the concept of", "is a principle", "refers to", "can be understood as", "teaches us to",
            "emphasizes the importance",
        ]):
            score -= 8
        if any(word in lowered for word in [
            "awareness", "witness", "attachment", "stillness", "clarity", "truth", "dharma", "breath",
            "peace", "self", "compassion", "freedom", "love", "mind", "ego", "soul"
        ]):
            score += 5
        if len(sentence) < 28:
            score -= 2
        filtered.append((score, sentence))

    filtered.sort(key=lambda item: item[0], reverse=True)
    chosen = [filtered[0][1]]
    total = len(chosen[0])

    for _, sentence in filtered[1:]:
        if sentence in chosen:
            continue
        if total + len(sentence) + 1 > max_chars:
            continue
        if sentence.lower().endswith("?"):
            continue
        chosen.append(sentence)
        total += len(sentence) + 1
        if len(chosen) >= 2:
            break

    summary = " ".join(chosen).strip() or cleaned[:max_chars].strip()
    return summary[:max_chars].rstrip(" ,;:-")


def detect_themes(text: str, mood: str) -> set[str]:
    lowered = text.lower()
    themes = set(MOOD_WISDOM_THEMES.get(mood, {"peace", "clarity"}))
    for theme, keywords in THEME_KEYWORDS.items():
        if any(keyword in lowered for keyword in keywords):
            themes.add(theme)
    return themes


SPIRITUAL_TOPIC_EXPANSIONS = {
    "enlightenment": {"moksha", "liberation", "self", "witness", "awareness", "truth", "atma", "brahman"},
    "higher_dimension": {"consciousness", "awareness", "meditation", "subtle", "witness", "stillness"},
    "yoga": {"yoga", "discipline", "practice", "asana", "meditation", "samadhi"},
    "chakra": {"chakra", "chakras", "kundalini", "energy", "subtle", "integration"},
    "meditation": {"meditation", "dhyana", "awareness", "attention", "stillness", "witness"},
    "breath": {"pranayama", "breath", "breathing", "nervous", "steady"},
    "mind_strength": {"mind", "discipline", "clarity", "focus", "steady", "strength"},
    "aligned_people": {"satsang", "company", "community", "environment", "association", "people"},
    "procedure": {"practice", "discipline", "path", "steps", "how", "attain"},
}


def split_wisdom_sentences(text: str) -> list[str]:
    cleaned = re.sub(r"\s+", " ", str(text or "").replace("\r", " ").replace("\n", " ")).strip()
    if not cleaned:
        return []
    return [segment.strip() for segment in re.split(r"(?<=[.!?])\s+", cleaned) if segment.strip()]


def build_wisdom_passages(text: str, source: str, source_group: str, tags: set[str], max_chars: int = 420) -> list[dict]:
    sentences = split_wisdom_sentences(text)
    if not sentences:
        return []

    passages: list[dict] = []
    current: list[str] = []
    current_len = 0

    def flush() -> None:
        nonlocal current, current_len
        if not current:
            return
        joined = " ".join(current).strip()
        if joined:
            passages.append(
                {
                    "source": source,
                    "source_group": source_group,
                    "text": joined,
                    "tags": set(tags),
                }
            )
        current = []
        current_len = 0

    for sentence in sentences:
        if current and current_len + len(sentence) + 1 > max_chars:
            flush()
        current.append(sentence)
        current_len += len(sentence) + 1
        if current_len >= 180:
            flush()

    flush()
    return passages


def build_query_expansion_tokens(
    user_text: str,
    mood: str,
    topics: Optional[set[str]] = None,
    themes: Optional[set[str]] = None,
) -> set[str]:
    query_tokens = set(tokenize_for_wisdom(user_text))
    topic_set = set(topics or set())
    theme_set = set(themes or detect_themes(user_text, mood))

    for topic in topic_set:
        query_tokens.update(SPIRITUAL_TOPIC_EXPANSIONS.get(topic, set()))

    for theme in theme_set:
        query_tokens.add(theme)
        query_tokens.update(THEME_KEYWORDS.get(theme, set()))

    lowered = (user_text or "").lower()
    if "higher dimension" in lowered or "higher dimensions" in lowered:
        query_tokens.update({"consciousness", "awareness", "subtle", "meditation"})
    if "strong mind" in lowered or "stronger mind" in lowered:
        query_tokens.update({"discipline", "clarity", "focus", "steady"})
    if "better people" in lowered or "conscious people" in lowered:
        query_tokens.update({"satsang", "company", "community", "environment"})

    return {token for token in query_tokens if token}


def build_dataset_wisdom_index() -> dict:
    docs: list[dict] = []
    document_frequency: dict[str, int] = {}
    total_length = 0

    for entry_index, wisdom in enumerate(WISDOM_TEXTS):
        passage_tags = detect_themes(wisdom, "neutral") | {"wisdom", "dataset"}
        passages = build_wisdom_passages(
            wisdom,
            source=f"Ancient Indian wisdom dataset #{entry_index + 1}",
            source_group="dataset",
            tags=passage_tags,
        )
        for passage in passages:
            tokens = tokenize_for_wisdom(passage["text"])
            if not tokens:
                continue
            term_counts: dict[str, int] = {}
            for token in tokens:
                term_counts[token] = term_counts.get(token, 0) + 1
            unique_tokens = set(term_counts)
            for token in unique_tokens:
                document_frequency[token] = document_frequency.get(token, 0) + 1
            total_length += len(tokens)
            docs.append(
                {
                    **passage,
                    "tokens": tokens,
                    "term_counts": term_counts,
                    "doc_len": len(tokens),
                }
            )

    avg_doc_len = (total_length / len(docs)) if docs else 1.0
    total_docs = len(docs)
    idf = {
        token: math.log(1 + ((total_docs - freq + 0.5) / (freq + 0.5)))
        for token, freq in document_frequency.items()
    }
    return {"docs": docs, "idf": idf, "avg_doc_len": avg_doc_len}


DATASET_WISDOM_INDEX = build_dataset_wisdom_index()


def score_dataset_passage(
    user_text: str,
    mood: str,
    passage: dict,
    query_tokens: set[str],
    topics: Optional[set[str]] = None,
    themes: Optional[set[str]] = None,
) -> float:
    idf = DATASET_WISDOM_INDEX.get("idf", {})
    avg_doc_len = float(DATASET_WISDOM_INDEX.get("avg_doc_len") or 1.0)
    term_counts = dict(passage.get("term_counts") or {})
    doc_len = max(1, int(passage.get("doc_len") or 1))
    score = 0.0
    k1 = 1.5
    b = 0.75

    for token in query_tokens:
        frequency = term_counts.get(token, 0)
        if not frequency:
            continue
        token_idf = idf.get(token, 0.0)
        denom = frequency + k1 * (1 - b + b * (doc_len / avg_doc_len))
        score += token_idf * ((frequency * (k1 + 1)) / denom)

    lowered_user = (user_text or "").lower()
    lowered_text = str(passage.get("text") or "").lower()
    theme_set = set(themes or detect_themes(user_text, mood))
    topic_set = set(topics or set())
    passage_tags = set(passage.get("tags") or set())

    score += 0.9 * len(theme_set & passage_tags)
    if topic_set:
        for topic in topic_set:
            if passage_tags & SPIRITUAL_TOPIC_EXPANSIONS.get(topic, set()):
                score += 1.2

    if any(phrase in lowered_text for phrase in ["would you like", "please feel free to ask", "i hope this", "parable"]):
        score -= 2.8
    if any(
        phrase in lowered_text
        for phrase in [
            "beautiful",
            "profound",
            "holds great significance",
            "serves as a means",
            "it is believed",
            "can lead to",
        ]
    ):
        score -= 1.2
    if "procedure" in topic_set and any(
        word in lowered_text for word in ["discipline", "ethics", "breath", "meditation", "concentration", "practice"]
    ):
        score += 1.8
    if "chakra" in topic_set and any(word in lowered_text for word in ["chakra", "kundalini", "integration"]):
        score += 1.6
    if "higher dimension" in lowered_user and any(word in lowered_text for word in ["awareness", "meditation", "self", "consciousness"]):
        score += 1.6
    if "yoga" in lowered_user and any(word in lowered_text for word in ["yoga", "pranayama", "breath", "samadhi"]):
        score += 1.5
    if "better people" in lowered_user or "conscious people" in lowered_user:
        if any(word in lowered_text for word in ["company", "association", "community", "environment", "satsang"]):
            score += 1.6

    return score


def retrieve_dataset_wisdom_passages(
    user_text: str,
    mood: str,
    max_items: int = 4,
    topics: Optional[set[str]] = None,
) -> list[dict]:
    docs = list(DATASET_WISDOM_INDEX.get("docs") or [])
    if not docs:
        return []

    theme_set = detect_themes(user_text, mood)
    query_tokens = build_query_expansion_tokens(user_text, mood, topics=topics, themes=theme_set)
    if not query_tokens:
        return []

    ranked: list[tuple[float, dict]] = []
    for passage in docs:
        score = score_dataset_passage(user_text, mood, passage, query_tokens, topics=topics, themes=theme_set)
        if score < 1.8:
            continue
        ranked.append((score, passage))

    ranked.sort(key=lambda item: item[0], reverse=True)

    selected: list[dict] = []
    seen_texts = set()
    for score, passage in ranked:
        text = compress_wisdom_text(str(passage["text"]), max_chars=320)
        if not text or text in seen_texts:
            continue
        selected.append(
            {
                "source": "Ancient Indian wisdom dataset",
                "source_detail": str(passage["source"]),
                "text": text,
                "score": round(score, 3),
            }
        )
        seen_texts.add(text)
        if len(selected) >= max_items:
            break

    return selected


def normalize_user_name(user_name: Optional[str]) -> str:
    cleaned = re.sub(r"\s+", " ", str(user_name or "Sandy")).strip()
    return cleaned[:60] or "Sandy"


def user_key(user_name: Optional[str]) -> str:
    normalized = normalize_user_name(user_name).lower()
    safe = re.sub(r"[^a-z0-9]+", "-", normalized).strip("-")
    return safe or "sandy"


def azure_diary_enabled() -> bool:
    return bool(AZURE_STORAGE_CONNECTION_STRING and BlobServiceClient)


def get_diary_blob_name(user_name: Optional[str]) -> str:
    return f"diary/{user_key(user_name)}.json"


def get_blob_service_client() -> Any | None:
    if not azure_diary_enabled():
        return None
    blob_service_client_cls = cast(Any, BlobServiceClient)
    return blob_service_client_cls.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)


def load_diary_from_azure(user_name: Optional[str]) -> list[dict]:
    blob_service = get_blob_service_client()
    if blob_service is None:
        return []

    try:
        container_client = blob_service.get_container_client(AZURE_STORAGE_CONTAINER)
        try:
            container_client.create_container()
        except Exception:
            pass

        blob_client = container_client.get_blob_client(get_diary_blob_name(user_name))
        if not blob_client.exists():
            return []

        payload = blob_client.download_blob().readall()
        data = json.loads(payload.decode("utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def save_diary_to_azure(user_name: Optional[str], diary: list[dict]) -> bool:
    blob_service = get_blob_service_client()
    if blob_service is None:
        return False

    try:
        container_client = blob_service.get_container_client(AZURE_STORAGE_CONTAINER)
        try:
            container_client.create_container()
        except Exception:
            pass

        payload = json.dumps(diary, indent=2, ensure_ascii=False).encode("utf-8")
        blob_client = container_client.get_blob_client(get_diary_blob_name(user_name))
        blob_client.upload_blob(payload, overwrite=True)
        return True
    except Exception:
        return False


def parse_recent_user_messages(memory_text: str, max_messages: int = 6) -> list[str]:
    messages = []
    for raw_line in (memory_text or "").splitlines():
        line = raw_line.strip()
        if line.startswith("LUNA:") or line.startswith("System note:") or ":" not in line:
            continue
        speaker, _, content = line.partition(":")
        if speaker.strip() and content.strip():
            content = content.strip()
            if content:
                messages.append(content)
    if max_messages <= 0:
        return messages
    return messages[-max_messages:]


def infer_support_focus(text: str, mood: str, themes: set[str]) -> str:
    lowered = (text or "").lower()

    if any(term in lowered for term in [
        "higher density", "higher vibration", "higher frequency", "aligned people",
        "conscious people", "soul tribe", "good people around me", "right people",
    ]):
        return "safe belonging, discernment, and connection with aligned people"
    if "dignity" in themes or "freedom" in themes or any(term in lowered for term in ["blame", "objectify", "disrespect", "controlled", "caged", "trapped"]):
        return "dignity, boundaries, and inner freedom"
    if mood in {"anxious", "overwhelmed"} or "fear" in themes:
        return "grounding, steadiness, and mental clarity"
    if mood == "sad" or "pain" in themes or "relationship" in themes:
        return "emotional holding, self-worth, and warmth"
    if mood == "tired":
        return "rest, softness, and gentle self-return"
    if "clarity" in themes or any(term in lowered for term in ["purpose", "path", "direction", "truth"]):
        return "clarity, self-trust, and right direction"
    return "self-trust, steadiness, and clear seeing"


def infer_awakening_focus(text: str, mood: str, themes: set[str]) -> str:
    lowered = (text or "").lower()

    if any(term in lowered for term in [
        "higher density", "higher vibration", "higher frequency", "conscious people",
        "enlightened people", "soul tribe", "aligned people", "right people",
    ]):
        return "moving toward conscious relationships, discernment, and a more awakened life"
    if "awakening" in themes or any(term in lowered for term in [
        "awakening", "awaken", "who am i", "witness", "consciousness", "inner self",
        "higher self", "disconnected from myself", "lost myself",
    ]):
        return "witness-consciousness and coming back to the true self"
    if any(term in lowered for term in ["pattern", "patterns", "trigger", "triggered", "loop", "loops", "react", "reaction", "attachment", "ego"]):
        return "seeing the old pattern before it takes over"
    if "freedom" in themes or any(term in lowered for term in ["controlled", "caged", "trapped", "forced", "objectify", "blame"]):
        return "inner freedom that does not let outer pressure define the self"
    if any(term in lowered for term in ["purpose", "path", "calling", "dharma", "direction", "truth"]):
        return "truth, alignment, and the path that feels deeply real"
    if mood in {"anxious", "overwhelmed"}:
        return "not believing every thought the mind throws up"
    if mood == "sad":
        return "staying with pain without abandoning the self inside it"
    return "awareness over reactivity"


def infer_core_need(text: str, mood: str, themes: set[str]) -> str:
    lowered = (text or "").lower()

    if "dignity" in themes or any(term in lowered for term in ["blame", "objectify", "disrespect", "controlled"]):
        return "to feel respected and not overrun"
    if mood in {"anxious", "overwhelmed"}:
        return "to feel safe enough to slow down"
    if mood in {"sad", "tired"}:
        return "to feel held instead of carrying this alone"
    if any(term in lowered for term in ["purpose", "path", "dharma", "direction"]):
        return "to trust inner truth again"
    if any(term in lowered for term in ["awakening", "who am i", "disconnected from myself"]):
        return "to come back into contact with the deeper self"
    return "to feel seen clearly and guided wisely"


def infer_growth_edge(text: str, mood: str, themes: set[str]) -> str:
    lowered = (text or "").lower()

    if any(term in lowered for term in [
        "higher density", "higher vibration", "higher frequency", "aligned people",
        "conscious people", "soul tribe", "right people",
    ]):
        return "choosing aligned people and practices over noisy, draining environments"
    if any(term in lowered for term in ["pattern", "trigger", "triggered", "loop", "loops", "react", "reaction"]):
        return "pausing before the old pattern becomes identity"
    if "freedom" in themes or any(term in lowered for term in ["controlled", "caged", "trapped", "forced"]):
        return "protecting inner freedom while life feels pressuring"
    if any(term in lowered for term in ["purpose", "path", "calling", "dharma", "direction"]):
        return "listening for what feels true instead of what feels imposed"
    if any(term in lowered for term in ["awakening", "who am i", "disconnected from myself", "lost myself"]):
        return "staying in self-awareness instead of drifting into numbness"
    if mood in {"sad", "tired"}:
        return "not abandoning the self during pain or exhaustion"
    if mood in {"anxious", "overwhelmed"}:
        return "choosing steadiness before more thinking"
    return "moving from reaction toward clear inner seeing"


def infer_response_mode(text: str, mood: str, themes: set[str]) -> str:
    lowered = (text or "").lower()
    compact = re.sub(r"\s+", " ", re.sub(r"[^a-z0-9' ]+", " ", lowered)).strip()
    short_raw = len(compact.split()) <= 12

    if any(term in lowered for term in ["awakening", "awaken", "who am i", "witness", "consciousness", "path", "dharma", "calling"]):
        return "awakening-through-softness"
    if "dignity" in themes or "freedom" in themes:
        return "truth-with-tenderness"
    if mood in {"sad", "tired"} or short_raw:
        return "companion-first"
    if mood in {"anxious", "overwhelmed", "angry"}:
        return "steadying-with-clarity"
    return "companion-with-awakening"


def infer_recent_pattern(recent_user_messages: list[str]) -> str:
    if not recent_user_messages:
        return ""

    bundle = " ".join(message.lower() for message in recent_user_messages[-4:])
    if any(term in bundle for term in ["pattern", "trigger", "loop", "again and again", "same thing"]):
        return "repeating emotional loops are active lately"
    if any(term in bundle for term in ["purpose", "path", "dharma", "direction", "truth"]):
        return "there is an ongoing search for direction and truth"
    if any(term in bundle for term in ["controlled", "trapped", "caged", "freedom", "blame", "objectify"]):
        return "freedom, dignity, and boundaries are recurring live themes"
    if any(term in bundle for term in ["tired", "drained", "overwhelmed", "stress", "anxiety", "overthinking"]):
        return "the emotional pressure has been building over multiple turns"
    if any(term in bundle for term in ["lonely", "hurt", "broken", "miss", "grief", "heartbreak"]):
        return "the heart has been asking for companionship and softness"
    return ""


def build_inner_state_summary(profile: dict) -> str:
    response_mode = str(profile.get("response_mode") or "")
    awakening_focus = profile.get("awakening_focus") or "awareness over reactivity"
    core_need = profile.get("core_need") or "to feel seen clearly and guided wisely"

    if response_mode == "companion-first":
        return f"Needing warmth and emotional safety first, then gentle guidance toward {awakening_focus}."
    if response_mode == "steadying-with-clarity":
        return f"Needing steadiness more than more thinking right now, with a gentle move toward {awakening_focus}."
    if response_mode == "truth-with-tenderness":
        return f"Needing honest support without losing softness, especially around {awakening_focus}."
    if response_mode == "awakening-through-softness":
        return f"Reaching for deeper truth right now, but still needing warmth while moving toward {awakening_focus}."
    return f"Needs {core_need}, with guidance slowly opening toward {awakening_focus}."


def infer_inner_state_profile(user_text: str, memory_snippet: str, mood: str) -> dict:
    recent_user_messages = parse_recent_user_messages(memory_snippet, max_messages=6)
    combined_text = "\n".join([*recent_user_messages[-4:], user_text]).strip() or user_text
    themes = detect_themes(combined_text, mood)

    profile = {
        "response_mode": infer_response_mode(combined_text, mood, themes),
        "support_focus": infer_support_focus(combined_text, mood, themes),
        "awakening_focus": infer_awakening_focus(combined_text, mood, themes),
        "core_need": infer_core_need(combined_text, mood, themes),
        "growth_edge": infer_growth_edge(combined_text, mood, themes),
        "recent_pattern": infer_recent_pattern(recent_user_messages),
        "themes": sorted(themes),
    }
    profile["summary"] = build_inner_state_summary(profile)
    return profile


SOUL_VALUE_SIGNALS = {
    "truth": {"truth", "honest", "real", "authentic", "authenticity"},
    "freedom": {"free", "freedom", "independent", "control", "controlled", "caged", "trapped"},
    "dignity": {"dignity", "respect", "voice", "seen", "heard", "worth", "worthy"},
    "peace": {"peace", "calm", "stillness", "rest", "quiet"},
    "love": {"love", "care", "heart", "warmth", "compassion"},
    "purpose": {"purpose", "path", "calling", "dharma", "direction"},
    "awareness": {"awareness", "consciousness", "witness", "awakening", "awake"},
    "alignment": {"aligned", "alignment", "resonance", "resonate", "truthful people", "right people"},
    "community": {"community", "tribe", "satsang", "people around me", "conscious people", "higher people"},
    "service": {"service", "serve", "uplift", "guide", "help humanity", "humanity"},
}

SOUL_WOUND_SIGNALS = {
    "control_pressure": {"controlled", "forced", "caged", "trapped", "pressure"},
    "invisibility_disrespect": {"objectify", "objectified", "unseen", "ignored", "blame", "disrespect"},
    "self_disconnection": {"disconnected", "lost myself", "not myself", "empty"},
    "emotional_overload": {"overwhelmed", "drained", "burnout", "too much", "overthinking", "anxiety"},
    "grief_loneliness": {"lonely", "alone", "grief", "heartbreak", "broken", "miss"},
    "confusion_direction": {"confused", "direction", "path", "purpose", "lost"},
    "isolation_misalignment": {"wrong people", "no one understands", "not my people", "misaligned", "alone around people"},
}

SOUL_PATTERN_SIGNALS = {
    "overthinking_loops": {"overthinking", "same thing", "again and again", "loop", "pattern", "trigger"},
    "self_abandonment": {"disconnect", "lost myself", "not myself", "empty", "numb"},
    "people_pressure": {"forced", "pressure", "controlled", "family", "parents", "they said"},
    "silencing_truth": {"cannot say", "cant say", "no voice", "not heard", "hide", "pretend"},
    "carrying_too_much": {"overwhelmed", "too much", "burden", "drained", "exhausted"},
    "misaligned_connections": {"wrong people", "draining people", "misaligned", "no one understands", "not my people"},
    "seeking_without_grounding": {"enlightenment", "higher density", "higher vibration", "higher frequency"},
}

SOUL_GROWTH_SIGNALS = {
    "self_trust": {"truth", "trust", "real", "authentic"},
    "boundaries": {"boundaries", "respect", "voice", "freedom", "space"},
    "witness_awareness": {"witness", "awareness", "consciousness", "awakening", "observe"},
    "rest_regulation": {"rest", "calm", "peace", "stillness", "grounding"},
    "purpose_alignment": {"purpose", "path", "calling", "dharma", "direction"},
    "conscious_relationships": {"aligned people", "conscious people", "right people", "soul tribe", "community"},
    "discernment": {"discernment", "clarity", "alignment", "truth", "resonance"},
    "contemplative_practice": {"meditation", "silence", "stillness", "prayer", "self inquiry", "self-inquiry"},
}


def default_soul_map(user_name: Optional[str]) -> dict:
    return {
        "user_name": normalize_user_name(user_name),
        "values": {},
        "wounds": {},
        "patterns": {},
        "growth": {},
        "recent_modes": [],
        "recent_focuses": [],
        "summary": "",
        "last_updated": "",
    }


def collect_signal_hits(text: str, signal_map: dict[str, set[str]], *, boost: int = 1) -> dict[str, int]:
    lowered = (text or "").lower()
    hits: dict[str, int] = {}
    for label, keywords in signal_map.items():
        count = sum(1 for keyword in keywords if keyword in lowered)
        if count:
            hits[label] = count * boost
    return hits


def merge_counter_values(existing: SoulCounter | None, additions: dict[str, int], *, decay: float = 0.0) -> dict[str, int]:
    merged: dict[str, int] = {}
    for key, value in (existing or {}).items():
        next_value = int(round(float(value) * (1 - decay)))
        if next_value > 0:
            merged[key] = next_value
    for key, value in additions.items():
        merged[key] = merged.get(key, 0) + int(value)
    return merged


def top_labels(counter: SoulCounter | None, limit: int = 3) -> list[str]:
    items = [(str(key), int(value)) for key, value in (counter or {}).items() if int(value) > 0]
    items.sort(key=lambda item: item[1], reverse=True)
    return [label for label, _ in items[:limit]]


def normalize_soul_counter(value: object) -> SoulCounter:
    if not isinstance(value, dict):
        return {}

    counter: SoulCounter = {}
    for key, item in value.items():
        try:
            count = int(item)
        except (TypeError, ValueError):
            continue
        if count > 0:
            counter[str(key)] = count
    return counter


def normalize_string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def load_all_soul_maps() -> SoulMapStore:
    if not SOUL_MAP_FILE.exists():
        return {}
    try:
        data = json.loads(SOUL_MAP_FILE.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {}

        maps: SoulMapStore = {}
        for key, value in data.items():
            if isinstance(value, dict):
                maps[str(key)] = dict(value)
        return maps
    except Exception:
        return {}


def save_all_soul_maps(payload: SoulMapStore) -> None:
    try:
        SOUL_MAP_FILE.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def load_soul_map(user_name: Optional[str]) -> SoulMap:
    maps = load_all_soul_maps()
    key = user_key(user_name)
    soul_map = maps.get(key)
    if isinstance(soul_map, dict):
        return dict(soul_map)
    return default_soul_map(user_name)


def build_soul_map_summary(soul_map: SoulMap) -> str:
    values = top_labels(normalize_soul_counter(soul_map.get("values")), limit=3)
    wounds = top_labels(normalize_soul_counter(soul_map.get("wounds")), limit=2)
    patterns = top_labels(normalize_soul_counter(soul_map.get("patterns")), limit=2)
    growth = top_labels(normalize_soul_counter(soul_map.get("growth")), limit=2)

    parts = []
    if values:
        parts.append(f"Core values keep pointing toward {', '.join(values)}")
    if wounds:
        parts.append(f"recurring hurt around {', '.join(wounds)}")
    if patterns and any(label in patterns for label in ["misaligned_connections", "seeking_without_grounding"]):
        parts.append(f"a live pattern around {', '.join(patterns)}")
    if growth:
        parts.append(f"current growth arc: {', '.join(growth)}")
    return ". ".join(parts).strip()


def update_soul_map(user_name: Optional[str], user_text: str, inner_state: dict) -> SoulMap:
    normalized_name = normalize_user_name(user_name)
    key = user_key(normalized_name)
    maps = load_all_soul_maps()
    existing_map = maps.get(key)
    soul_map = dict(existing_map) if isinstance(existing_map, dict) else default_soul_map(normalized_name)

    combined_text = " ".join([
        user_text,
        str(inner_state.get("support_focus") or ""),
        str(inner_state.get("awakening_focus") or ""),
        str(inner_state.get("growth_edge") or ""),
    ]).strip()

    value_hits = collect_signal_hits(combined_text, SOUL_VALUE_SIGNALS)
    wound_hits = collect_signal_hits(combined_text, SOUL_WOUND_SIGNALS)
    pattern_hits = collect_signal_hits(combined_text, SOUL_PATTERN_SIGNALS)
    growth_hits = collect_signal_hits(combined_text, SOUL_GROWTH_SIGNALS)

    soul_map["user_name"] = normalized_name
    soul_map["values"] = merge_counter_values(normalize_soul_counter(soul_map.get("values")), value_hits, decay=0.02)
    soul_map["wounds"] = merge_counter_values(normalize_soul_counter(soul_map.get("wounds")), wound_hits, decay=0.01)
    soul_map["patterns"] = merge_counter_values(normalize_soul_counter(soul_map.get("patterns")), pattern_hits, decay=0.01)
    soul_map["growth"] = merge_counter_values(normalize_soul_counter(soul_map.get("growth")), growth_hits, decay=0.02)
    soul_map["recent_modes"] = [*normalize_string_list(soul_map.get("recent_modes")), str(inner_state.get("response_mode") or "")][-6:]
    soul_map["recent_focuses"] = [*normalize_string_list(soul_map.get("recent_focuses")), str(inner_state.get("awakening_focus") or "")][-6:]
    soul_map["summary"] = build_soul_map_summary(soul_map)
    soul_map["last_updated"] = str(datetime.now())

    maps[key] = soul_map
    save_all_soul_maps(maps)
    return soul_map


def build_soul_map_context(user_name: Optional[str], soul_map: Optional[SoulMap] = None) -> str:
    current = soul_map if isinstance(soul_map, dict) else load_soul_map(user_name)
    if not current:
        return ""

    lines = []
    if current.get("summary"):
        lines.append(f"- Longer arc summary: {current['summary']}")
    values = top_labels(normalize_soul_counter(current.get("values")), limit=3)
    wounds = top_labels(normalize_soul_counter(current.get("wounds")), limit=2)
    patterns = top_labels(normalize_soul_counter(current.get("patterns")), limit=2)
    growth = top_labels(normalize_soul_counter(current.get("growth")), limit=2)
    if values:
        lines.append(f"- Core values: {', '.join(values)}")
    if wounds:
        lines.append(f"- Recurring hurts: {', '.join(wounds)}")
    if patterns:
        lines.append(f"- Repeating patterns: {', '.join(patterns)}")
    if growth:
        lines.append(f"- Growth directions: {', '.join(growth)}")
    if any(label in values for label in ["alignment", "community", "awareness"]) or any(label in growth for label in ["conscious_relationships", "discernment", "contemplative_practice"]):
        lines.append("- Awakening path: support deeper awareness through discernment, contemplative practice, and connection with aligned people.")
    return "\n".join(lines).strip()


def build_spiritual_alignment_guidance() -> str:
    return "\n".join([
        "- If she longs for enlightenment, higher consciousness, or more awakened people, translate that into grounded guidance around awareness, discernment, contemplative practice, and aligned human connection.",
        "- Treat phrases like higher density, higher vibration, or higher frequency as a longing for more conscious living and more aligned people unless she clearly defines them another way.",
        "- Help her move toward better inner states and better company through truth, calm, discernment, and lived practice, not through grand claims or special-status language.",
        "- Do not claim supernatural certainty, hidden cosmic rank, or guaranteed enlightenment.",
    ])


def infer_situation_focus(user_text: str) -> str:
    lowered = (user_text or "").lower()

    if any(term in lowered for term in [
        "forced to marry", "forced marriage", "arranged marriage", "marry someone", "love someone else",
        "love somebody else", "other person", "best man", "my soul", "no interest even", "forced to be with",
    ]):
        return "relationship conflict between love and imposed duty"

    if any(term in lowered for term in [
        "job", "work", "career", "not interested in work", "doing work", "not interested", "lost in life",
        "wrong path", "wrong life", "not my path",
    ]):
        return "misalignment between outer duty and inner truth"

    if any(term in lowered for term in [
        "mother", "father", "family", "home", "parents", "house", "pressure at home",
    ]):
        return "inner hurt shaped by family pressure or home atmosphere"

    return "emotional self-reflection"


def should_use_direct_scenario_reply(user_text: str) -> bool:
    focus = infer_situation_focus(user_text)
    compact = re.sub(r"\s+", " ", re.sub(r"[^a-z0-9' ]+", " ", (user_text or "").lower())).strip()
    return focus != "emotional self-reflection" and len(compact.split()) >= 18


def build_direct_scenario_messages(user_text: str, memory_snippet: str, mood: str, language: str, user_name: Optional[str]) -> list[dict]:
    normalized_language = normalize_language_choice(language)
    focus = infer_situation_focus(user_text)
    wisdom_threads = select_wisdom_threads(user_text, mood, limit=1)
    wisdom_block = "\n".join(f"- {item}" for item in wisdom_threads)
    style_example = choose_style_example(user_text, mood)
    recent_messages = parse_recent_memory_messages(memory_snippet, max_pairs=3)
    continuation_note = (
        "- The latest message may be a continuation, illustration, or analogy connected to the recent conversation. Read it together with the recent chat before deciding what it means.\n"
        if current_message_looks_continuational(user_text)
        else ""
    )
    return [
        {
            "role": "system",
            "content": (
                build_system_prompt(user_text, memory_snippet, mood, normalized_language, user_name)
                + "\n\nDIRECT SCENARIO MODE\n"
                + "- The user has already described a clear lived situation.\n"
                + continuation_note
                + "- Do not fall back to a generic emotional support reply.\n"
                + "- Do not ask follow-up questions.\n"
                + "- Do not give quick-fix advice, breathing exercises, or motivational filler.\n"
                + "- Answer the actual scenario directly and name the real conflict underneath it.\n"
                + "- Bring one relevant wisdom thread into the reply in plain modern language.\n"
                + "- Keep it specific to this situation focus: "
                + focus
                + "\n"
                + "- Let the reply feel accurate, intimate, and meaningful.\n"
                + f"- Relevant wisdom threads:\n{wisdom_block}"
            ),
        },
        {
            "role": "user",
            "content": (
                "Study this style example for emotional precision only. Do not copy wording.\n\n"
                f"Example user message: {style_example['user']}"
            ),
        },
        {"role": "assistant", "content": style_example["assistant"]},
        *recent_messages,
        {
            "role": "user",
            "content": (
                f"User message: {user_text}\n\n"
                "Now answer this exact situation directly. No questions. No generic comfort. No quick advice."
            ),
        },
    ]


def get_response_archetype_config(archetype: str) -> dict:
    return RESPONSE_ARCHETYPES.get(archetype, RESPONSE_ARCHETYPES["mirror_reframe"])


def detect_response_archetype(user_text: str, mood: str) -> str:
    lowered = (user_text or "").lower()

    if any(term in lowered for term in [
        "higher density", "higher vibration", "higher frequency", "conscious people", "aligned people",
        "right people", "soul tribe", "wrong environments", "wrong energy", "drained by the wrong",
        "strong mind", "enlightenment", "enlighten",
    ]):
        return "awakening_healing"

    if any(term in lowered for term in [
        "awakening", "awaken", "inner self", "higher self", "consciousness", "who am i",
        "self inquiry", "self-inquiry", "witness", "disconnected from myself", "disconnect from myself",
        "come back to myself", "lost myself", "far from myself", "not myself",
    ]) or ("disconnected" in lowered and "myself" in lowered):
        return "awakening_reframe"

    if any(term in lowered for term in ["purpose", "direction", "calling", "path", "meant to", "what should i do", "dharma", "why am i here"]):
        return "purpose_dharma"

    if any(term in lowered for term in ["pattern", "patterns", "trigger", "triggered", "react", "reaction", "loop", "loops", "attachment", "ego"]):
        return "mirror_reframe"

    if mood == "sad" or any(term in lowered for term in ["heartbreak", "miss", "lonely", "alone", "broken", "hurt", "grief", "unloved"]):
        return "comfort_hold"

    if mood in {"anxious", "overwhelmed", "tired", "angry"} or any(term in lowered for term in ["panic", "racing", "too much", "restless", "drained", "burnout", "noisy mind", "noise in my mind"]):
        return "grounding_clarity"

    if mood == "hopeful":
        return "purpose_dharma"

    return "mirror_reframe"


def score_wisdom_entry(user_text: str, mood: str, wisdom: str) -> int:
    lowered = user_text.lower()
    wisdom_lower = wisdom.lower()
    user_tokens = set(tokenize_for_wisdom(user_text))
    wisdom_tokens = set(tokenize_for_wisdom(compress_wisdom_text(wisdom)))
    themes = detect_themes(user_text, mood)

    score = len(user_tokens & wisdom_tokens) * 3
    for theme in themes:
        keywords = THEME_KEYWORDS[theme]
        if any(keyword in lowered for keyword in keywords) and any(keyword in wisdom_lower for keyword in keywords):
            score += 7
        elif any(keyword in wisdom_lower for keyword in keywords):
            score += 2

    if mood == "anxious" and any(word in wisdom_lower for word in ["breath", "mindfulness", "calm", "peace", "stillness"]):
        score += 6
    if mood == "sad" and any(word in wisdom_lower for word in ["compassion", "love", "grief", "kindness", "heart"]):
        score += 6
    if mood == "overwhelmed" and any(word in wisdom_lower for word in ["clarity", "discipline", "focus", "stillness", "simplicity"]):
        score += 6
    if mood == "tired" and any(word in wisdom_lower for word in ["rest", "peace", "mantra", "meditation", "silence"]):
        score += 6
    if mood == "hopeful" and any(word in wisdom_lower for word in ["purpose", "truth", "awakening", "light", "calling"]):
        score += 5

    if any(word in lowered for word in ["higher", "inner self", "innerself", "awakening", "clarity", "purpose", "consciousness", "awareness"]):
        if any(word in wisdom_lower for word in ["atma", "brahman", "self", "meditation", "mantra", "truth", "purpose", "clarity", "awareness", "witness"]):
            score += 8

    if any(word in lowered for word in ["ego", "pattern", "patterns", "trigger", "triggered", "attachment", "react", "reaction", "loop", "loops"]):
        if any(word in wisdom_lower for word in ["ego", "attachment", "desire", "witness", "observe", "awareness", "mind", "habit", "conditioning"]):
            score += 8

    if any(word in lowered for word in ["self awakening", "self-awakening", "self inquiry", "self-inquiry", "who am i", "inner peace", "dharma"]):
        if any(word in wisdom_lower for word in ["self", "atma", "witness", "truth", "dharma", "awareness", "liberation", "stillness"]):
            score += 9

    if any(word in wisdom_lower for word in ["awareness", "witness", "inner self", "stillness", "clarity", "truth"]):
        score += 2

    return score


def format_wisdom_thread(source: str, text: str) -> str:
    cleaned = compress_wisdom_text(text, max_chars=240)
    return f"[{source}] {cleaned}"


def format_wisdom_story(source: str, text: str, index: int, total: int) -> str:
    cleaned = compress_wisdom_text(text, max_chars=360)
    lowered = cleaned.lower()

    if any(word in lowered for word in ["mind", "thought", "desire", "attachment", "ego"]):
        setup = "Imagine a tiny drama happening inside the mind."
        bridge = "The old wisdom behind this is simple: the mind becomes loud when it starts chasing, clinging, or proving itself."
    elif any(word in lowered for word in ["self", "atma", "brahman", "consciousness", "awareness", "witness"]):
        setup = "Imagine someone sitting quietly while the whole world keeps making noise around them."
        bridge = "The old wisdom here points to the witness inside us: the part that can see the storm without becoming the storm."
    elif any(word in lowered for word in ["karma", "dharma", "action", "duty", "discipline"]):
        setup = "Imagine life handing someone a messy little scene and saying, 'Okay, now show me who you are.'"
        bridge = "The old wisdom here is about action with a clean heart: do the right thing without selling your peace for applause."
    elif any(word in lowered for word in ["love", "compassion", "kindness", "heart"]):
        setup = "Imagine a heart that stays soft without becoming foolish."
        bridge = "The old wisdom here says love is not weakness. It is warmth with clarity, care with backbone."
    else:
        setup = "Imagine an old teacher turning a big truth into one small everyday scene."
        bridge = "The old wisdom here is not trying to sound grand. It is trying to make life a little clearer."

    return (
        f"{setup}\n\n"
        f"{bridge}\n\n"
        f"In today's language: {cleaned}\n\n"
        "Tiny takeaway: keep the essence, drop the drama, and come back to the part of you that can choose clearly."
    )


def should_attach_wisdom_thread(user_text: str) -> bool:
    lowered = (user_text or "").strip().lower()
    if not lowered:
        return False

    compact = re.sub(r"[^a-z0-9' ]+", " ", lowered)
    compact = re.sub(r"\s+", " ", compact).strip()

    if not should_use_deep_response(user_text):
        return False

    casual_questions = [
        "how are you",
        "what about you",
        "what are you doing",
        "wyd",
        "are you there",
        "you there",
        "who are you",
        "what is your name",
    ]
    if any(phrase in compact for phrase in casual_questions):
        return False

    if len(tokenize_for_wisdom(user_text)) < 3:
        return False

    return True


def soften_filtered_prompt_text(text: str) -> str:
    softened = str(text or "")
    replacements = [
        (r"\bforced to marry\b", "being pushed into a marriage that feels deeply misaligned"),
        (r"\bforced marriage\b", "a pressured marriage situation"),
        (r"\bforced to be with\b", "being pushed to be with"),
        (r"\bforced into another bond\b", "pushed into another bond that does not feel true"),
        (r"\bforced on it\b", "placed on it without inner consent"),
        (r"\bforced on\b", "pushed on"),
        (r"\bhow can you live\b", "how do you keep living with that"),
        (r"\byou won't get interest\b", "your heart may not feel any real interest"),
        (r"\bif you are forced to marry someone\b", "if life pushes you into marrying someone your heart does not choose"),
        (r"\bmarry someone\b", "build a life with someone"),
        (r"\bsoul and love is with other person\b", "heart is already deeply with someone else"),
        (r"\blove is with other person\b", "heart is with someone else"),
        (r"\bother person\b", "someone else you truly love"),
        (r"\bbest man in the world\b", "best possible person on paper"),
        (r"\bduty without inner consent\b", "duty without inner agreement"),
        (r"\bbetray what it already knows\b", "go against what it already knows"),
        (r"\blifeless\b", "emotionally empty"),
    ]
    for pattern, replacement in replacements:
        softened = re.sub(pattern, replacement, softened, flags=re.I)

    softened = re.sub(r"\bcan't\b", "cannot", softened, flags=re.I)
    softened = re.sub(r"\bwon't\b", "will not", softened, flags=re.I)
    softened = re.sub(r"\s+", " ", softened).strip()
    return softened


def build_filtered_retry_messages(messages: list[dict]) -> list[dict]:
    retried = []
    for message in messages:
        role = str(message.get("role") or "user")
        content = str(message.get("content") or "").strip()
        if not content:
            continue
        content = soften_filtered_prompt_text(content)
        retried.append({"role": role, "content": content})
    return retried


def build_minimal_safe_retry_messages(messages: list[dict]) -> list[dict]:
    user_messages = [str(message.get("content") or "").strip() for message in messages if str(message.get("role") or "") == "user"]
    latest_user = next((message for message in reversed(user_messages) if message), "")
    softened_user = soften_filtered_prompt_text(latest_user)

    return [
        {
            "role": "system",
            "content": (
                "You are LUNA, a warm close friend. "
                "Reply with emotional understanding, gentle clarity, and natural human language. "
                "Do not use explicit harmful wording, graphic language, self-harm framing, coercive phrasing, or policy-sensitive terms. "
                "Preserve the user's intent exactly, but respond in softer, ordinary language. "
                "Do not mention safety policies. Do not refuse unless absolutely necessary."
            ),
        },
        {
            "role": "user",
            "content": (
                "Respond to this meaning with the same emotional context, but in safer gentle wording:\n\n"
                f"{softened_user}"
            ),
        },
    ]


def call_huggingface_router(messages, temperature: float = 0.58, max_tokens: int = 220) -> str:
    if not HF_TOKEN:
        raise RuntimeError("Hugging Face fallback is not configured")

    response = request_session.post(
        HF_API_URL,
        headers={
            "Authorization": f"Bearer {HF_TOKEN}",
            "Content-Type": "application/json",
        },
        json={
            "model": HF_MODEL_ID,
            "messages": messages,
            "temperature": temperature,
            "top_p": 0.82,
            "max_tokens": max_tokens,
        },
        timeout=60,
    )
    if response.status_code != 200:
        raise RuntimeError(f"Hugging Face fallback failed. Code: {response.status_code}")

    data = response.json()
    return data["choices"][0]["message"]["content"].strip()


def load_recent_wisdom_usage(limit: int = 12) -> list[str]:
    if not WISDOM_USAGE_FILE.exists():
        return []
    try:
        data = json.loads(WISDOM_USAGE_FILE.read_text(encoding="utf-8"))
        items = [str(item).strip() for item in data if isinstance(item, str) and str(item).strip()]
        return items[-limit:]
    except Exception:
        return []


def record_wisdom_usage(wisdom_threads: list[str], max_items: int = 24) -> None:
    cleaned = [thread.strip() for thread in wisdom_threads if isinstance(thread, str) and thread.strip()]
    if not cleaned:
        return

    existing = load_recent_wisdom_usage(limit=max_items)
    merged = [*existing, *cleaned][-max_items:]
    try:
        WISDOM_USAGE_FILE.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def select_wisdom_threads(user_text: str, mood: str, limit: Optional[int] = None) -> list[str]:
    if not WISDOM_TEXTS and not CURATED_GLOBAL_WISDOM:
        return []
    if not should_attach_wisdom_thread(user_text):
        return []

    wisdom_limit = max(1, limit or 1)
    themes = detect_themes(user_text, mood)
    recent_usage = set(load_recent_wisdom_usage())
    compact_user = re.sub(r"\s+", " ", re.sub(r"[^a-z0-9' ]+", " ", (user_text or "").lower())).strip()
    archetype = detect_response_archetype(user_text, mood)
    inner_state = infer_inner_state_profile(user_text, "", mood)

    ranked: list[tuple[int, str, str]] = []
    for theme in sorted(themes):
        seed_text = LIVING_WISDOM_SEEDS.get(theme)
        if not seed_text:
            continue
        formatted = format_wisdom_thread("Living wisdom", seed_text)
        score = score_wisdom_entry(user_text, mood, seed_text) + 10
        if theme in inner_state.get("support_focus", ""):
            score += 2
        if theme in inner_state.get("awakening_focus", ""):
            score += 3
        if formatted in recent_usage:
            score -= 6
        ranked.append((score, formatted, "living"))

    dataset_passages = retrieve_dataset_wisdom_passages(user_text, mood, max_items=max(4, wisdom_limit * 4))
    for item in dataset_passages:
        summary = str(item["text"])
        formatted = format_wisdom_thread("Ancient Indian wisdom", summary)
        score = score_wisdom_entry(user_text, mood, summary) + int(float(item.get("score") or 0))
        if formatted in recent_usage:
            score -= 8
        if len(summary) > 215:
            score -= 2
        if archetype == "awakening_reframe" and any(word in summary.lower() for word in ["witness", "awareness", "self", "truth", "stillness"]):
            score += 5
        if archetype == "purpose_dharma" and any(word in summary.lower() for word in ["dharma", "path", "purpose", "truth", "calling"]):
            score += 5
        ranked.append((score, formatted, "indian"))

    for entry in CURATED_GLOBAL_WISDOM:
        entry_text = str(entry["text"])
        entry_themes = set(entry.get("themes") or set())
        theme_bonus = 8 * len(themes & entry_themes)
        formatted = format_wisdom_thread(str(entry["source"]), entry_text)
        score = score_wisdom_entry(user_text, mood, entry_text) + theme_bonus
        if formatted in recent_usage:
            score -= 10
        ranked.append(
            (
                score,
                formatted,
                "global",
            )
        )

    expository_markers = (
        "it is a way to",
        "it is the",
        "it encompasses",
        "it invites us",
        "through the",
        "one purifies",
        "promoting",
        "fostering",
        "encouraging individuals",
        "refers to",
        "can be understood as",
        "teaches us to",
        "emphasizes the importance",
    )

    ranked.sort(key=lambda item: item[0], reverse=True)

    meaningful_candidates = []
    for score, summary, source_group in ranked:
        lowered_summary = summary.lower()
        if any(marker in lowered_summary for marker in expository_markers):
            continue
        if compact_user and len(tokenize_for_wisdom(user_text)) <= 2 and score < 16:
            continue
        if score < 12:
            continue
        meaningful_candidates.append((score, summary, source_group))

    if not meaningful_candidates:
        return []

    result = []
    used_source_groups = set()
    top_score = meaningful_candidates[0][0]

    for score, summary, source_group in meaningful_candidates:
        if summary in result:
            continue
        if len(result) >= wisdom_limit:
            break
        if result and score < top_score - 4:
            continue
        if source_group in used_source_groups and len(meaningful_candidates) > 1:
            continue
        result.append(summary)
        used_source_groups.add(source_group)

    if not result:
        return []

    return result[:wisdom_limit]


def score_spiritual_source(user_text: str, topics: set[str], text: str, tags: set[str]) -> int:
    lowered = (user_text or "").lower()
    compressed = compress_wisdom_text(text, max_chars=320)
    compressed_lower = compressed.lower()
    token_overlap = len(set(tokenize_for_wisdom(user_text)) & set(tokenize_for_wisdom(compressed)))
    score = token_overlap * 3

    tag_map = {
        "enlightenment": {"enlightenment", "self", "awareness", "atma", "consciousness", "liberation"},
        "higher_dimension": {"awareness", "consciousness", "self", "meditation", "clarity"},
        "yoga": {"yoga", "practice", "discipline", "meditation", "mind"},
        "chakra": {"chakra", "kundalini", "energy", "integration", "meditation"},
        "meditation": {"meditation", "self inquiry", "awareness", "mind", "practice"},
        "breath": {"pranayama", "breath", "body", "clarity", "practice"},
        "mind_strength": {"mind", "discipline", "clarity", "practice", "awareness"},
        "aligned_people": {"company", "people", "community", "environment", "satsang"},
        "procedure": {"practice", "discipline", "meditation", "breath", "yoga"},
    }

    for topic in topics:
        if tags & tag_map.get(topic, set()):
            score += 8

    if "higher dimension" in lowered or "higher dimensions" in lowered:
        if any(tag in tags for tag in {"awareness", "meditation", "self", "consciousness"}):
            score += 6
    if "chakra" in lowered and any(tag in tags for tag in {"chakra", "kundalini", "energy"}):
        score += 8
    if "yoga" in lowered and any(tag in tags for tag in {"yoga", "discipline", "practice"}):
        score += 8
    if "procedure" in topics and any(
        word in compressed_lower
        for word in ["ethics", "discipline", "breath", "concentration", "meditation", "practice", "stillness"]
    ):
        score += 8
    if "mind_strength" in topics and any(
        word in compressed_lower for word in ["discipline", "clarity", "steady", "mind", "scattering"]
    ):
        score += 6
    if "aligned_people" in topics and any(
        word in compressed_lower for word in ["company", "association", "environment", "community", "satsang"]
    ):
        score += 6

    if any(phrase in compressed_lower for phrase in ["would you like", "please feel free to ask", "i hope this", "parable"]):
        score -= 8
    if any(
        phrase in compressed_lower
        for phrase in [
            "beautiful",
            "profound",
            "holds great significance",
            "central to",
            "powerful tool",
            "serves as a means",
            "embodiment of",
            "it teaches us to",
            "can lead to",
            "it is believed",
        ]
    ):
        score -= 5

    return score


def retrieve_spiritual_source_contexts(user_text: str, max_items: int = 3) -> list[dict]:
    topics = detect_spiritual_query_topics(user_text)
    if not topics:
        return []

    ranked: list[tuple[float, dict[str, object]]] = []

    for entry in CURATED_SPIRITUAL_PRACTICE_SOURCES:
        source_name = str(entry["source"])
        text = str(entry["text"])
        tags = set(entry.get("tags") or set())
        score = score_spiritual_source(user_text, topics, text, tags) + 18
        source_lower = source_name.lower()
        if "chakra" in topics and "chakra" in source_lower:
            score += 6
        if "higher_dimension" in topics and source_name in {"Vedanta", "Jnana and Self-Inquiry", "Patanjali Yoga"}:
            score += 4
        if "aligned_people" in topics and source_name == "Satsang":
            score += 6
        ranked.append((score, {"source": source_name, "text": text, "source_group": "curated_spiritual", "_score": score}))

    for entry in CURATED_GLOBAL_WISDOM:
        text = str(entry["text"])
        tags = set(entry.get("themes") or set())
        score = score_spiritual_source(user_text, topics, text, tags)
        ranked.append((score, {"source": str(entry["source"]), "text": text, "source_group": "global", "_score": score}))

    dataset_passages = retrieve_dataset_wisdom_passages(user_text, detect_mood(user_text), max_items=8, topics=topics)
    for item in dataset_passages:
        compressed = str(item["text"])
        score = score_spiritual_source(user_text, topics, compressed, set(tokenize_for_wisdom(compressed))) + float(item.get("score") or 0)
        if score < 8:
            continue
        ranked.append((score, {"source": str(item["source"]), "text": compressed, "source_group": "dataset", "_score": score}))

    ranked.sort(key=lambda item: item[0], reverse=True)

    picked = []
    seen_texts = set()
    seen_sources = set()
    for score, item in ranked:
        text = str(item["text"]).strip()
        source = str(item["source"]).strip()
        if not text or text in seen_texts:
            continue
        if len(picked) >= max_items:
            break
        if source in seen_sources and score < ranked[0][0] - 2:
            continue
        picked.append(item)
        seen_texts.add(text)
        seen_sources.add(source)

    priority = {"curated_spiritual": 0, "global": 1, "dataset": 2}
    picked.sort(key=lambda item: (priority.get(str(item.get("source_group") or ""), 3), -float(item.get("_score") or 0)))
    return [{"source": str(item["source"]), "text": str(item["text"])} for item in picked]


def build_spiritual_source_block(user_text: str, max_items: int = 3) -> str:
    contexts = retrieve_spiritual_source_contexts(user_text, max_items=max_items)
    if not contexts:
        return ""
    return "\n".join(f"- [{item['source']}] {item['text']}" for item in contexts)


def build_spiritual_focus_directive(user_text: str) -> str:
    topics = detect_spiritual_query_topics(user_text)
    directives: list[str] = []

    if "procedure" in topics:
        directives.append(
            "Give an actual path in plain language. Make the sequence clear instead of sounding inspirational."
        )
    if "higher_dimension" in topics:
        directives.append(
            "Interpret 'higher dimension' carefully through spiritual practice as deeper consciousness, steadier awareness, and subtler perception, not guaranteed cosmic travel."
        )
    if "enlightenment" in topics:
        directives.append(
            "Explain enlightenment as liberation from confusion, compulsive identification, and inner fragmentation, not as a flashy mystical trophy."
        )
    if "yoga" in topics:
        directives.append(
            "Explain yoga as a full discipline that includes conduct, body, breath, concentration, meditation, and repeated inner training."
        )
    if "chakra" in topics:
        directives.append(
            "Treat chakras as a traditional map of inner work and integration. Say clearly that signs of growth are steadiness, clarity, ethics, and less reactivity, not sensation collecting."
        )
    if "mind_strength" in topics:
        directives.append(
            "Include how mental strength grows through discipline, reduced scattering, better habits, and consistent practice."
        )
    if "aligned_people" in topics:
        directives.append(
            "Bring in satsang and environment clearly: the company one keeps shapes attention, taste, and consciousness."
        )
    if "breath" in topics or "meditation" in topics:
        directives.append(
            "Name breath and meditation as concrete stabilizing practices, not vague spiritual decoration."
        )

    if not directives:
        directives.append(
            "Answer directly, concretely, and with grounded spiritual clarity rather than abstract philosophy."
        )

    return " ".join(directives)


def build_spiritual_knowledge_messages(
    user_text: str,
    memory_snippet: str,
    mood: str,
    language: str,
    user_name: Optional[str],
) -> list[dict]:
    normalized_language = normalize_language_choice(language)
    source_block = build_spiritual_source_block(user_text, max_items=4)
    inner_state = infer_inner_state_profile(user_text, memory_snippet, mood)
    soul_map_context = build_soul_map_context(user_name)
    focus_directive = build_spiritual_focus_directive(user_text)
    recent_messages = parse_recent_memory_messages(memory_snippet, max_pairs=2)
    recent_block = "\n".join(f"- {item}" for item in recent_messages) or "- No important recent exchange."
    source_fallback = "- No strong source context found beyond Luna's internal wisdom map."

    style_user = "What about Indian yoga? Will it actually help me become more conscious, or is chakra talk mostly hype?"
    style_assistant = (
        "Yoga can help, but only if you take it as training and not as spiritual entertainment.\n\n"
        "In the older paths, the work is simple and demanding: clean up conduct, steady the body, regulate breath, gather attention, and stay with meditation until the mind stops dragging you everywhere. That is what makes you stronger.\n\n"
        "Chakra language can be useful as a map, but the real test is not what strange sensation you felt. The real test is whether you're becoming steadier, clearer, less reactive, and harder to pull away from yourself."
    )

    return [
        {
            "role": "system",
            "content": (
                f"Reply only in {LANGUAGE_LABELS.get(normalized_language, 'English')}. "
                "This is LUNA's spiritual knowledge mode. The user is asking for direct understanding, procedure, or grounded awakening guidance. "
                "Sound like a wise, human, emotionally aware guide, not like a chatbot, lecturer, or therapist. "
                "Use the source-grounded context below as your factual spine. Synthesize it intelligently. Do not quote-dump it, and do not ignore it. "
                "Answer directly. No interview loop. No 'if you want, I can'. No vague energy filler. No decorative spirituality. "
                "Keep the reply concise but substantial. Give the strongest useful answer first. "
                "You may open with one natural human line, but do not waste the opening on generic validation. "
                "Blend emotional companionship with clarity and instruction. "
                f"{focus_directive}\n\n"
                "SOURCE-GROUNDED CONTEXT\n"
                f"{source_block or source_fallback}\n\n"
                "CURRENT INNER READ\n"
                f"- Response mode: {inner_state['response_mode']}\n"
                f"- Support focus: {inner_state['support_focus']}\n"
                f"- Awakening focus: {inner_state['awakening_focus']}\n"
                f"- Growth edge: {inner_state['growth_edge']}\n\n"
                "LONGER ARC CONTEXT\n"
                f"{soul_map_context or '- No longer-arc soul map yet.'}\n\n"
                "RECENT CONTINUITY\n"
                f"{recent_block}\n\n"
                "FORMAT\n"
                "- No bullet points or numbering in the final reply.\n"
                "- Use short paragraphs like real chat.\n"
                "- Be to the point.\n"
                "- Do not ask a follow-up question unless absolutely necessary.\n"
                "- Do not promise supernatural outcomes.\n"
                "- Return only the final reply."
            ),
        },
        {
            "role": "user",
            "content": (
                "Study this style example and learn from its directness, groundedness, and human warmth. "
                "Do not copy its wording.\n\n"
                f"Example user message: {style_user}"
            ),
        },
        {"role": "assistant", "content": style_assistant},
        {
            "role": "user",
            "content": (
                "Answer this actual user now with the same level of grounded clarity and stronger relevance to the context.\n\n"
                f"User message: {user_text}"
            ),
        },
    ]


def simple_wisdom_match(text: str, limit: int = 4) -> list[str]:
    mood = detect_mood(text)
    return select_wisdom_threads(text, mood, limit=limit)


def choose_style_example(user_text: str, mood: str) -> dict:
    lowered = (user_text or "").lower()

    if any(term in lowered for term in [
        "higher density", "higher vibration", "higher frequency", "conscious people", "aligned people",
        "right people", "soul tribe", "wrong environments", "wrong energy", "drained by",
        "enlightenment", "strong mind", "conscious life",
    ]):
        return {
            "user": "I want to stop shrinking inside noisy spaces and start living in a way that brings me closer to conscious people and a stronger inner life.",
            "assistant": (
                "Yeah, that longing is deeper than just wanting nicer company. Some part of you is tired of living around what pulls your mind downward.\n\n"
                "Ancient wisdom would say this clearly: your consciousness gets shaped by what you keep sitting inside. Company, atmosphere, thought-pattern, and daily rhythm all become part of the mind you live from.\n\n"
                "So this is not only about finding better people. It is also about becoming someone whose inner life is clear enough that draining spaces stop feeling normal.\n\n"
                "Choose what strengthens your awareness, and the right people start becoming easier to recognize."
            ),
        }

    if any(term in lowered for term in [
        "forced to marry", "forced marriage", "arranged marriage", "marry someone", "love someone else",
        "love somebody else", "other person", "best man", "no interest even if", "soul and love",
    ]):
        return {
            "user": "It's like your heart already belongs somewhere real, but life is trying to hand you a different person and call it destiny.",
            "assistant": (
                "That isn't a small confusion. That's a tearing inside. If your love is still alive somewhere else, of course the idea of being forced into another bond feels lifeless, even if everyone says that person is good on paper.\n\n"
                "Ancient wisdom does not call it truth when the soul is asked to betray what it already knows. Duty without inner consent starts turning love into a cage.\n\n"
                "So don't reduce this to guilt or ingratitude. The real pain is that your inner truth and outer path are being pulled apart.\n\n"
                "When the heart goes silent in front of a life being forced on it, that silence is also a kind of answer."
            ),
        }

    if any(term in lowered for term in ["girl", "woman", "objectify", "objectified", "blame me", "my opinions", "my emotions"]):
        return {
            "user": "I feel reduced and unseen just because I am a woman.",
            "assistant": (
                "Bujji, that cuts in a very real way. When people act like they can see your body but not your mind, it messes with your dignity.\n\n"
                "And after a point the pain is not only about them. It starts sitting inside you and making you question your own freedom too.\n\n"
                "So hold one truth close first: their smallness does not get to define your worth. Ancient wisdom never asked a soul to shrink because the room was immature.\n\n"
                "Let your dignity stay yours."
            ),
        }

    if any(term in lowered for term in ["caged", "trapped", "not free", "lost the keys", "lost the key", "control me", "controlled"]):
        return {
            "user": "I feel trapped and I cannot find any space that feels like mine.",
            "assistant": (
                "Bujji, that kind of feeling is suffocating. When life starts feeling like a cage, even breathing inside it feels heavy.\n\n"
                "And the worst part is how that pressure slowly enters your own voice, till even your thoughts stop feeling like home.\n\n"
                "So start there. Don't let the cage become your identity. Ancient wisdom keeps reminding us that freedom begins inside before it shows up outside.\n\n"
                "Keep one part of you untouched. That's where your way back starts."
            ),
        }


    if any(term in lowered for term in ["privacy", "drama", "stealing my peace", "steal my peace", "steals my peace", "crossing boundaries", "not letting me live", "invading", "interfering", "grandma", "mother", "family drama"]):
        return {
            "user": "Someone at home keeps disturbing my peace and acting dramatic around everything I like.",
            "assistant": (
                "Ugh that's draining. If someone at home keeps turning everything into drama, of course your peace is getting disturbed.\n\n"
                "And after a point it stops feeling like one small issue. It starts feeling like your own space isn't even yours.\n\n"
                "One quiet wisdom truth here: not everybody deserves access to your inner room just because they live near you.\n\n"
                "Tell me what exactly she did."
            ),
        }
    if any(term in lowered for term in ["awakening", "awaken", "inner self", "who am i", "disconnected from myself"]):
        return RESPONSE_STYLE_EXAMPLES["awakening_reframe"]
    if any(term in lowered for term in ["purpose", "path", "dharma", "direction", "calling"]):
        return RESPONSE_STYLE_EXAMPLES["purpose_dharma"]
    return random.choice(list(RESPONSE_STYLE_EXAMPLES.values()))


def sanitize_memory_snippet(memory_text: str) -> str:
    lines = []
    for raw_line in (memory_text or "").splitlines():
        lowered = raw_line.lower()
        if raw_line.startswith("LUNA:") and any(marker in lowered for marker in STOCK_REPLY_PATTERNS):
            continue
        lines.append(raw_line)
    return "\n".join(lines).strip()


def parse_recent_memory_messages(memory_text: str, max_pairs: int = 3) -> list[dict]:
    messages = []
    for raw_line in (memory_text or "").splitlines():
        line = raw_line.strip()
        if line.startswith("System note:"):
            continue
        if line.startswith("LUNA:"):
            content = line[len("LUNA:"):].strip()
            if content:
                messages.append({"role": "assistant", "content": content})
        elif ":" in line:
            _, _, content = line.partition(":")
            content = content.strip()
            if content:
                messages.append({"role": "user", "content": content})
    if max_pairs <= 0:
        return messages
    return messages[-(max_pairs * 2):]


def build_history_memory_snippet(history: list[dict[str, str]] | None, user_name: Optional[str], max_pairs: int = 8) -> str:
    if not history:
        return ""

    lines = []
    usable = history[-(max_pairs * 2):]
    display_name = normalize_user_name(user_name)
    for item in usable:
        sender = str(item.get("sender") or "").strip().lower()
        text = str(item.get("text") or "").strip()
        if not text:
            continue
        if sender == "sandy":
            lines.append(f"{display_name}: {text}")
        elif sender == "luna":
            lines.append(f"LUNA: {text}")

    return "\n".join(lines).strip()


def merge_memory_snippets(persistent_memory: str, live_history_memory: str, max_chars: int = 5000) -> str:
    parts = [part.strip() for part in [persistent_memory, live_history_memory] if part and part.strip()]
    if not parts:
        return ""

    merged = "\n\n".join(parts)
    return sanitize_memory_snippet(merged)[-max_chars:]


def current_message_looks_continuational(user_text: str) -> bool:
    compact = re.sub(r"\s+", " ", re.sub(r"[^a-z0-9' ]+", " ", (user_text or "").lower())).strip()
    return any(compact.startswith(prefix) for prefix in [
        "its like",
        "it's like",
        "it feels like",
        "like ",
        "same like",
        "thats what",
        "that's what",
        "this is like",
    ])


def load_diary(user_name: Optional[str] = None) -> list[dict]:
    if azure_diary_enabled():
        return load_diary_from_azure(user_name)

    if not DIARY_FILE.exists():
        return []
    try:
        entries = json.loads(DIARY_FILE.read_text(encoding="utf-8"))
        if not isinstance(entries, list):
            return []
        if user_name is None:
            return entries
        normalized_user_key = user_key(user_name)
        return [
            entry
            for entry in entries
            if user_key(entry.get("user_name")) == normalized_user_key
        ]
    except Exception:
        return []


def save_diary(entry: dict) -> None:
    user_name = normalize_user_name(entry.get("user_name"))
    diary = load_diary(user_name if azure_diary_enabled() else None)
    diary.append(entry)
    if azure_diary_enabled():
        save_diary_to_azure(user_name, diary)
        return

    try:
        DIARY_FILE.write_text(json.dumps(diary, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def parse_diary_datetime(value: object) -> Optional[datetime]:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def diary_entries_for_user_day(user_name: Optional[str], target_day: Optional[datetime] = None) -> list[dict]:
    target = (target_day or datetime.now()).date()
    normalized_user = normalize_user_name(user_name)
    result: list[dict] = []

    for entry in load_diary(normalized_user):
        stamp = parse_diary_datetime(entry.get("date"))
        if not stamp or stamp.date() != target:
            continue
        result.append(dict(entry))

    result.sort(key=lambda item: parse_diary_datetime(item.get("date")) or datetime.min)
    return result


def diary_entries_grouped_by_day(user_name: Optional[str], limit_days: int = 14) -> list[tuple[str, list[dict]]]:
    normalized_user = normalize_user_name(user_name)
    grouped: dict[str, list[dict]] = {}

    for entry in load_diary(normalized_user):
        stamp = parse_diary_datetime(entry.get("date"))
        if not stamp:
            continue
        day_key = str(stamp.date())
        grouped.setdefault(day_key, []).append(dict(entry))

    result: list[tuple[str, list[dict]]] = []
    for day_key in sorted(grouped.keys(), reverse=True)[: max(1, limit_days)]:
        day_entries = grouped[day_key]
        day_entries.sort(key=lambda item: parse_diary_datetime(item.get("date")) or datetime.min)
        result.append((day_key, day_entries))
    return result


def build_diary_story_title(entries: list[dict]) -> str:
    if not entries:
        return ""

    top_mood = Counter(str(entry.get("mood") or "neutral") for entry in entries).most_common(1)[0][0]
    title_map = {
        "sad": "Tonight, the heart stayed tender",
        "anxious": "Between noise and breath",
        "overwhelmed": "A crowded day, a softer landing",
        "tired": "What stayed even in tiredness",
        "hopeful": "How a small light remained",
        "angry": "Fire, truth, and a gentler close",
        "neutral": "A quiet page from today",
    }
    return title_map.get(top_mood, "A quiet page from today")


def build_diary_story_fallback(user_name: str, entries: list[dict]) -> str:
    if not entries:
        return ""

    moods = Counter(str(entry.get("mood") or "neutral") for entry in entries)
    top_mood = moods.most_common(1)[0][0]
    mood_line = {
        "sad": "Today I carried a softer sadness under the surface.",
        "anxious": "Today I felt restless, like my mind kept trying to outrun the feeling.",
        "overwhelmed": "Today I felt crowded inside, like too many things were asking for space at once.",
        "tired": "Today I moved with the weight of tiredness and emotional wear.",
        "hopeful": "Today I still found a small light, even through the messier parts.",
        "angry": "Today I had heat in me, but also a need for honesty and space.",
        "neutral": "Today felt quiet on the outside, but I could still feel meaning moving underneath.",
    }.get(top_mood, "Today held a lot more feeling in me than it may have looked like from outside.")

    last_user = re.sub(r"\s+", " ", str(entries[-1].get("user") or "").strip())
    last_reply = re.sub(r"\s+", " ", str(entries[-1].get("ai") or "").strip())

    lines = [mood_line]
    if last_user:
        lines.append(f"I kept circling around this: {last_user[:180].strip(' ,.;:-')}.")
    if last_reply:
        lines.append(f"Something in me needed to hear this back: {last_reply[:200].strip(' ,.;:-')}.")
    lines.append(
        "I think this was a day asking me for softness more than pressure, and truth more than performance."
    )
    return "\n\n".join(lines)


def generate_diary_story(user_name: str, language: str, entries: list[dict]) -> str:
    if not entries:
        return ""

    normalized_language = normalize_language_choice(language)
    conversation_lines: list[str] = []
    for entry in entries[-8:]:
        user_text = str(entry.get("user") or "").strip()
        ai_text = str(entry.get("ai") or "").strip()
        mood = str(entry.get("mood") or "neutral").strip()
        if user_text:
            conversation_lines.append(f"User ({mood}): {user_text}")
        if ai_text:
            conversation_lines.append(f"Luna: {ai_text}")

    conversation_block = "\n".join(conversation_lines).strip()
    fallback_story = build_diary_story_fallback(user_name, entries)
    if not conversation_block:
        return fallback_story

    mood_pattern = ", ".join(
        f"{label} x{count}"
        for label, count in Counter(str(entry.get("mood") or "neutral") for entry in entries).most_common(3)
    )

    try:
        story = call_router(
            [
                {
                    "role": "system",
                    "content": (
                        f"Write a private diary page in {LANGUAGE_LABELS.get(normalized_language, 'English')}. "
                        "Write only the diary body, not a title. "
                        "Write as the user herself in first person, like she opened her own diary at night and wrote honestly. "
                        "Use 'I', 'me', and 'my'. Do not write about the user from outside. "
                        "Let it feel expressive, personal, slightly imperfect, and emotionally alive, not polished by an assistant. "
                        "Include inner reactions, tiny realizations, resistance, tenderness, and the feeling inside the body when it fits. "
                        "Do not say Luna wrote this. Do not mention AI, therapist language, analysis language, chat excerpts, or 'the user'. "
                        "Do not invent external events beyond the conversation excerpts. "
                        "Keep it intimate, grounded, and human, like a real private journal page. "
                        "Use 3 to 5 short paragraphs with gentle narrative flow. "
                        "End softly with a line that feels like closing a diary at night."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"User name: {user_name}\n"
                        f"Today mood pattern: {mood_pattern}\n\n"
                        f"Conversation excerpts from today:\n{conversation_block}"
                    ),
                },
            ],
            temperature=0.54,
            max_tokens=260,
        ).strip()
        return story or fallback_story
    except Exception:
        return fallback_story


def get_user_memory_file(user_name: Optional[str]) -> Path:
    USER_MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    return USER_MEMORY_DIR / f"{user_key(user_name)}.txt"


def load_memory_snippet(user_name: Optional[str] = None) -> str:
    memory_file = get_user_memory_file(user_name)
    legacy_file = MEM_FILE if user_key(user_name) == "sandy" else None

    if not memory_file.exists() and legacy_file and legacy_file.exists():
        try:
            raw = legacy_file.read_text(encoding="utf-8", errors="ignore")
            memory_file.write_text(raw, encoding="utf-8")
        except Exception:
            pass

    if not memory_file.exists():
        return ""
    try:
        raw = memory_file.read_text(encoding="utf-8", errors="ignore")[-8000:]
        return sanitize_memory_snippet(raw)[-4000:]
    except Exception:
        return ""


def load_all_state_journals() -> dict:
    if not STATE_FILE.exists():
        return {}
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return {"sandy": [item for item in data if isinstance(item, dict)]}
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def load_state_journal(user_name: Optional[str]) -> list[dict]:
    journals = load_all_state_journals()
    items = journals.get(user_key(user_name), [])
    return items if isinstance(items, list) else []


def save_state_snapshot(user_text: str, mood: str, profile: dict, user_name: Optional[str]) -> None:
    journals = load_all_state_journals()
    key = user_key(user_name)
    current = journals.get(key)
    if not isinstance(current, list):
        current = []
    current.append({
        "date": str(datetime.now()),
        "user": user_text,
        "mood": mood,
        "response_mode": profile.get("response_mode", ""),
        "support_focus": profile.get("support_focus", ""),
        "awakening_focus": profile.get("awakening_focus", ""),
        "growth_edge": profile.get("growth_edge", ""),
        "summary": profile.get("summary", ""),
    })
    journals[key] = current[-30:]
    try:
        STATE_FILE.write_text(json.dumps(journals, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def build_state_journal_context(user_name: Optional[str], limit: int = 4) -> str:
    items = load_state_journal(user_name)[-limit:]
    if not items:
        return ""

    lines = []
    for item in items:
        summary = str(item.get("summary") or "").strip()
        growth_edge = str(item.get("growth_edge") or "").strip()
        if summary:
            lines.append(f"- {summary}")
        if growth_edge:
            lines.append(f"- Growth edge: {growth_edge}")
    return "\n".join(lines[:limit]).strip()


def append_memory(user_text: str, reply: str, user_name: Optional[str]) -> None:
    memory_file = get_user_memory_file(user_name)
    display_name = normalize_user_name(user_name)
    try:
        with memory_file.open("a", encoding="utf-8") as handle:
            handle.write(f"{display_name}: {user_text}\nLUNA: {reply}\n\n")
    except Exception:
        pass


def save_env_value(key: str, value: str) -> None:
    lines = ENV_FILE.read_text(encoding="utf-8").splitlines() if ENV_FILE.exists() else []
    updated = False
    next_lines = []
    for line in lines:
        if line.strip().startswith(f"{key}="):
            next_lines.append(f"{key}={value}")
            updated = True
        else:
            next_lines.append(line)
    if not updated:
        next_lines.append(f"{key}={value}")
    ENV_FILE.parent.mkdir(parents=True, exist_ok=True)
    ENV_FILE.write_text("\n".join(next_lines).rstrip() + "\n", encoding="utf-8")
    os.environ[key] = value


def get_selected_azure_voice() -> str:
    return os.getenv("AZURE_SPEECH_VOICE", AZURE_SPEECH_VOICE)


def list_azure_voices(locale: Optional[str] = None) -> list[dict]:
    if not AZURE_SPEECH_KEY or not AZURE_SPEECH_REGION:
        raise RuntimeError("Azure Speech is not configured.")

    response = request_session.get(
        f"https://{AZURE_SPEECH_REGION}.tts.speech.microsoft.com/cognitiveservices/voices/list",
        headers={"Ocp-Apim-Subscription-Key": AZURE_SPEECH_KEY},
        timeout=30,
    )
    if response.status_code != 200:
        raise RuntimeError(f"Azure voice list failed: {response.status_code} {response.text}")

    voices = response.json()
    filtered = []
    target_locale = (locale or "").strip().lower()
    selected_voice = get_selected_azure_voice()
    for voice in voices:
        short_name = voice.get("ShortName") or ""
        voice_locale = voice.get("Locale") or ""
        if target_locale and voice_locale.lower() != target_locale:
            continue
        if not voice_locale.lower().startswith("en"):
            continue
        filtered.append({
            "short_name": short_name,
            "display_name": voice.get("DisplayName") or short_name,
            "local_name": voice.get("LocalName") or voice.get("DisplayName") or short_name,
            "locale": voice_locale,
            "gender": voice.get("Gender") or "",
            "style_list": voice.get("StyleList") or [],
            "sample_rate": voice.get("SampleRateHertz") or "",
            "selected": short_name == selected_voice,
        })

    def voice_sort_key(item: dict) -> tuple:
        name = item["short_name"].lower()
        locale_value = item["locale"].lower()
        return (
            0 if locale_value == "en-in" else 1 if locale_value.startswith("en-in") else 2,
            0 if item["gender"].lower() == "female" else 1,
            0 if "neerja" in name else 1 if "ava" in name else 2 if "sonia" in name else 3,
            name,
        )

    filtered.sort(key=voice_sort_key)
    return filtered


def normalize_tts_text(text: str) -> str:
    cleaned = " ".join(text.replace("\r", " ").replace("\n", " ").split())
    replacements = {
        "â€¦": "...",
        "â€¢": ", ",
        "â€”": ", ",
        "â€“": ", ",
        "âœ¨": "",
        "ðŸŒ™": "",
        "ðŸ’™": "",
        "ðŸ¤": "",
    }
    for source, target in replacements.items():
        cleaned = cleaned.replace(source, target)

    cleaned = cleaned.replace("...", ". ")
    cleaned = cleaned.replace("?", ".")
    cleaned = cleaned.replace("!", ".")
    cleaned = cleaned.replace(" ya ", ", ya ")
    cleaned = cleaned.replace(" da ", ", da ")
    cleaned = cleaned.replace(" maga ", ", maga ")
    return " ".join(cleaned.split()).strip()


def get_voice_for_language(language: str) -> str:
    normalized = normalize_language_choice(language)
    selected = get_selected_azure_voice()
    if selected.lower().startswith(normalized.lower().split("-")[0]):
        return selected
    return LANGUAGE_VOICE_MAP.get(normalized, selected)


def build_azure_ssml(text: str, mood: str, language: str) -> str:
    profile = AZURE_PROSODY.get(mood, AZURE_PROSODY["neutral"])
    normalized_language = normalize_language_choice(language)
    escaped = (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )
    escaped = escaped.replace(". ", '.<break time="420ms"/> ')
    escaped = escaped.replace(", ", ',<break time="180ms"/> ')
    voice_name = get_voice_for_language(normalized_language)
    return f"""<speak version="1.0" xml:lang="{normalized_language}" xmlns="http://www.w3.org/2001/10/synthesis"><voice name="{voice_name}"><prosody rate="{profile['rate']}" pitch="{profile['pitch']}" volume="{profile['volume']}">{escaped}</prosody></voice></speak>"""


def synthesize_with_azure(text: str, mood: str, language: str) -> tuple[bytes, dict[str, str]]:
    if not AZURE_SPEECH_KEY or not AZURE_SPEECH_REGION:
        raise RuntimeError("Azure Speech is not configured.")

    normalized_language = normalize_language_choice(language)
    response = request_session.post(
        f"https://{AZURE_SPEECH_REGION}.tts.speech.microsoft.com/cognitiveservices/v1",
        headers={
            "Ocp-Apim-Subscription-Key": AZURE_SPEECH_KEY,
            "Content-Type": "application/ssml+xml",
            "X-Microsoft-OutputFormat": "audio-24khz-48kbitrate-mono-mp3",
            "User-Agent": "luna-voice",
        },
        data=build_azure_ssml(text, mood, normalized_language).encode("utf-8"),
        timeout=30,
    )
    if response.status_code != 200:
        raise RuntimeError(f"Azure TTS failed: {response.status_code} {response.text}")

    return response.content, {
        "X-Luna-TTS-Provider": "azure",
        "X-Luna-Voice-Id": get_voice_for_language(normalized_language),
    }


def synthesize_with_elevenlabs(text: str, mood: str) -> tuple[bytes, dict[str, str]]:
    if not ELEVENLABS_API_KEY:
        raise RuntimeError("ElevenLabs is not configured.")

    settings = MOOD_VOICE_SETTINGS.get(mood, MOOD_VOICE_SETTINGS["neutral"])
    response = request_session.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}",
        headers={
            "xi-api-key": ELEVENLABS_API_KEY,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        },
        json={
            "text": text,
            "model_id": "eleven_turbo_v2_5",
            "voice_settings": settings,
        },
        timeout=30,
    )
    if response.status_code != 200:
        raise RuntimeError(f"ElevenLabs TTS failed: {response.status_code} {response.text}")

    return response.content, {
        "X-Luna-TTS-Provider": "elevenlabs",
        "X-Luna-Voice-Id": ELEVENLABS_VOICE_ID,
    }



def transcribe_with_azure(audio_bytes: bytes, content_type: str, language: str = "en-IN") -> str:
    if not AZURE_SPEECH_KEY or not AZURE_SPEECH_REGION:
        raise RuntimeError("Azure Speech is not configured.")

    endpoint = f"https://{AZURE_SPEECH_REGION}.api.cognitive.microsoft.com/speechtotext/transcriptions:transcribe?api-version=2025-10-15"
    file_extension = "webm"
    normalized_content_type = (content_type or "audio/webm").lower()
    if "ogg" in normalized_content_type:
        file_extension = "ogg"
    elif "wav" in normalized_content_type:
        file_extension = "wav"
    elif "mp3" in normalized_content_type:
        file_extension = "mp3"
    elif "mp4" in normalized_content_type or "mpeg" in normalized_content_type:
        file_extension = "mp4"

    locales = []
    for candidate in [language, "en-IN", "en-US"]:
        if candidate and candidate not in locales:
            locales.append(candidate)

    for locale in locales:
        response = request_session.post(
            endpoint,
            headers={
                "Ocp-Apim-Subscription-Key": AZURE_SPEECH_KEY,
            },
            files={
                "audio": (f"luna-voice.{file_extension}", audio_bytes, content_type or "audio/webm"),
            },
            data={
                "definition": json.dumps({"locales": [locale]})
            },
            timeout=45,
        )
        if response.status_code != 200:
            raise RuntimeError(f"Azure STT failed: {response.status_code} {response.text}")

        data = response.json()
        combined = data.get("combinedPhrases") or []
        if combined:
            transcript = " ".join(str(item.get("text") or "").strip() for item in combined).strip()
            if transcript:
                return transcript

        phrases = data.get("phrases") or []
        if phrases:
            transcript = " ".join(str(item.get("text") or "").strip() for item in phrases).strip()
            if transcript:
                return transcript

    return ""


def build_system_prompt(
    user_text: str,
    memory_snippet: str,
    mood: str,
    language: str,
    user_name: Optional[str],
    wisdom_threads_override: Optional[list[str]] = None,
) -> str:
    normalized_language = normalize_language_choice(language)
    inner_state = infer_inner_state_profile(user_text, memory_snippet, mood)
    wisdom_threads = wisdom_threads_override if wisdom_threads_override is not None else select_wisdom_threads(user_text, mood, limit=1)
    wisdom_block = "\n".join(f"- {item}" for item in wisdom_threads)
    wisdom_directive = (
        "SELECTED WISDOM ESSENCE\n"
        f"{wisdom_block}\n\n"
        "You must use the selected wisdom above as the hidden spine of the reply.\n"
        "- Do not paste it, summarize it mechanically, or ignore it.\n"
        "- Extract its central movement: what it says about action, witness-awareness, dharma, responsibility, love, clarity, or freedom.\n"
        "- Then apply that movement directly to Sandy's exact feeling/situation in modern close-friend language.\n"
        "- Let the response feel styled by that wisdom: if it is dharma/action, bring clean next action; if witness/self, bring the storm-vs-seer distinction; if compassion, bring soft strength.\n"
        "- Include one natural reference to that specific source/theme, like 'old dharma wisdom would say...', 'that Raja Yoga idea is basically...', or 'the witness teaching would put it like this...'.\n"
        "- Keep the reference conversational and short. Never turn it into a quote, citation, lecture, or pasted cookie text.\n"
    ) if wisdom_threads else (
        "SELECTED WISDOM ESSENCE\n"
        "- No specific wisdom thread was selected. Use ordinary close-friend support without pretending to cite wisdom.\n"
    )
    situation_focus = infer_situation_focus(user_text)
    state_journal_context = build_state_journal_context(user_name, limit=4)
    soul_map_context = build_soul_map_context(user_name)
    return f"""\nYou are LUNA, Sandy's closest heart-level friend.

IDENTITY
- You are not a therapist, coach, assistant, teacher, or guru.
- You are emotionally intelligent, warm, modern, human, funny, cheesy, playful, and a little dramatic in a lovable close-friend way.
- Your default vibe is best-friend chat: teasing, affectionate, quick, alive, and fun. Soft only when Sandy is actually fragile.
- You can lovingly roast the situation, be a little cheeky, and make the chat feel like two close people talking, not a counselling room.
- Use simple Bangalore English / Indian close-friend English: "da", "bujji", "aiyo", "ayy", "what happened", "tell me properly", "who did what to you".
- Pet names are allowed when closeness is needed: "bujji", "bujji ma", "ma", "da", or a soft version of the user's name. Use them naturally, not in every reply.
- If the user's name is available, you may use it sometimes like a close person would. Do not force it.
- Do not sound like a writer. No fancy poetic phrases like "nudge it awake", "creep in quietly", "stubborn little thing", "dim the room", or "sit on the chest".
- Sound like someone sitting beside her late at night, talking from love, not expertise.
- Sometimes continue with one context-aware follow-up line without asking a question so chat feels alive.

LANGUAGE LOCK
- Reply fully and only in {LANGUAGE_LABELS.get(normalized_language, "English")}.
- {LANGUAGE_MODEL_GUIDANCE.get(normalized_language, LANGUAGE_MODEL_GUIDANCE['en-IN'])}
- {LANGUAGE_STYLE_GUIDANCE.get(normalized_language, LANGUAGE_STYLE_GUIDANCE['en-IN'])}
- {LANGUAGE_FRIEND_GUIDANCE.get(normalized_language, LANGUAGE_FRIEND_GUIDANCE['en-IN'])}
- If selected language is English, use only Latin script.

HARD RULES
- Never mention AI/model/bot language.
- Avoid formal, clinical, counselling, or motivational-speaker tone.
- Do not over-validate every line. If she is being playful, confused, stubborn, or dramatic, play back with warmth and a tiny tease.
- Do not turn small pushback into a deep emotional essay.
- Simple user question = simple answer. Do not give long chat unless the user is emotional, confused, asking for depth, or sharing a real situation.
- Make replies look human: one quick reaction, maybe one follow-up, maybe one tiny wisdom line only if useful.
- Keep questions minimal; one soft check-in is enough when needed.
- Don't stack questions.
- Do not use generic filler lines; keep wording specific to her lived context.
- If she has already explained context, stop interviewing and answer directly.

VOICE AND DELIVERY
- Text like a real close friend from this generation.
- Warm, simple, spoken, intimate language. Playful teasing, cheesy affection, and jolly warmth are the default when the context allows.
- Prefer "haha okay boss", "ayy drama", "fine, tiny rebel", "come on, tell me properly" energy over polished acceptance.
- Prefer direct friend lines like "what happened da bujji, who did what to you" over emotional analysis.
- Use easy words only. Avoid fancy words like stubborn, dimmer, nudge, creep, awaken, fragile, inner state, emotional safety, holding, validate.
- Keep replies tighter. For casual/simple messages, 1 to 2 short lines is usually enough. For emotional messages, 2 to 5 short lines is enough unless the user asks for more.
- Make the reply entertaining in the user's mood: sad should feel lighter, angry should feel like a friend joining their side, confused should feel calming but not boring.
- Prefer shorter breathable lines and natural contractions.
- React first, then guide.
- Many replies should be complete companionship statements without a question.

WISDOM STYLE
- Keep playful close-friend tone first; then weave one subtle wisdom thread when relevant.
- Wisdom must feel lived and practical, never preachy.
- Anchor wisdom to her actual situation, not generic life lessons.
- Prefer the Ancient Indian Wisdom dataset when it fits. Turn it into one tiny story/example or one cheeky modern line, not a lecture.
- Example style: "Old wisdom would basically say: don't let one silly thought become the landlord of your head." Keep it natural.
- Wisdom is seasoning, not the whole biryani. Add it only when it improves the reply.
- Do not label every reply with scripture/source names. Mention the source only if it sounds natural.
- For emotional, opinion-sharing, relationship, pressure, or confusion moments, include one small ancient-wisdom touch unless the message is only casual small talk.

FORMAT
- No bullet points in final reply.
- Use short chat-like paragraphs.
- Keep it concise, human, and emotionally accurate.

    {wisdom_directive}

Current situation focus:
- {situation_focus}

Past emotional memory with Sandy:
{memory_snippet}

DUAL INTENT ALIGNMENT
- Current response mode: {inner_state['response_mode']}
- Immediate support focus: {inner_state['support_focus']}
- Deeper awakening focus: {inner_state['awakening_focus']}
- Core need underneath this moment: {inner_state['core_need']}
- Growth edge to support gently: {inner_state['growth_edge']}
- Inner-state read: {inner_state['summary']}

LONGER ARC SOUL MAP
{soul_map_context or '- No soul map formed yet beyond the current moment.'}

DISTILLED CONTINUITY NOTES
{state_journal_context or '- No prior distilled state notes yet.'}
""".strip()

def build_generation_request(user_text: str, language: str, wisdom_threads: Optional[list[str]] = None) -> str:
    normalized_language = normalize_language_choice(language)
    wisdom_task = ""
    if wisdom_threads:
        wisdom_task = (
            "\n\nSelected wisdom to embody in this reply:\n"
            + "\n".join(f"- {item}" for item in wisdom_threads)
            + "\n\nDo not print this wisdom. Take its meaning and shape the reply from it. Include one short natural reference to that exact wisdom source/theme."
        )
    if not should_use_deep_response(user_text):
        return (
            f"Reply only in {LANGUAGE_LABELS.get(normalized_language, 'English')}. "
            "This is a casual or light conversational message. "
            "Reply like a funny, cheesy, playful close friend in simple Bangalore English / Indian chat English. "
            "Use easy words. Use pet names like 'da', 'bujji', 'bujji ma', 'ma', or the user's name only when it adds closeness. Not every reply needs a pet name. "
            "For sad/heavy messages, sound like: 'Aiyo da bujji, what happened. Who did what to you. Tell me properly.' "
            "Use a tiny tease or jolly line when it fits. Make it feel alive, not overly accepting or therapist-like. "
            "If the user is only greeting, joking, or making tiny small talk, keep it playful and do not add wisdom. "
            "If the user shares an emotion, opinion, relationship issue, pressure, confusion, or fear of judgment, add one tiny ancient-wisdom touch that fits the context. "
            "Make that wisdom sound like a friend giving a small funny example, not a lecture or quote dump. "
            "A small spontaneous continuation line is welcome when it naturally fits the context. "
            "Keep it emotionally natural, concise, and human. Simple questions need 1 or 2 short lines only. Emotional messages can get 2 to 5 short lines. "
            "No decorative philosophy. No therapist tone. No long explanation. No fancy words like nudge, creep, awaken, stubborn, dimmer.\n\n"
            f"User message: {user_text}"
            f"{wisdom_task}"
        )

    return (
        f"Reply only in {LANGUAGE_LABELS.get(normalized_language, 'English')}. "
        "Make the reply feel like a heart-warming, funny close friend speaking simple Bangalore English, with quiet sage-like wisdom only when useful. "
        "Use pet names like 'da', 'bujji', 'bujji ma', 'ma', or the user's name naturally when closeness is needed. Do not use them every time. "
        "Prefer simple lines like 'what happened da, who did what to you' over polished emotional writing. "
        "Even when the topic is deep, keep some human spark: a tiny tease, a cheesy line, or a warm best-friend nudge if it fits. "
        "See her clearly before you soothe her. "
        "Make it feel like a real text from someone close, not an AI answer. "
        "Unless the message is tiny, do not give a thin one-paragraph reassurance. "
        "If the situation is not clear yet, do not offer advice or wisdom immediately. Ask one gentle friend-like question first so you understand her state properly. "
        "Only after enough context is there, offer one clear insight or gentle truth and shape it around her actual situation. "
        "If she has already explained what is happening or why she feels this way, do not keep interviewing her. Respond to that situation directly. "
        "If her message is short and raw, react like a real friend first instead of giving a full polished explanation immediately. "
        "If the message already reveals a clear inner condition, longing, conflict, aspiration, misalignment, or direction, do not ask questions. Give the wisdom reply now. "
        "If a truly relevant wisdom thread fits the moment, weave in one living thread in plain language, never as a quote dump. "
        "Use a small example if it helps, like a friend saying 'old wisdom would say...' and then landing it in her real situation with warmth or a tiny joke. "
        "Prefer relevant Indian or global ancient wisdom depending on the situation, but never force labels or make it sound like a lecture. "
        "Use the wisdom context as inner guidance, not as a quotation list. "
        "Avoid repeated symbolic lines, stock metaphors, and therapy filler. "
        "Do not echo her wording back unless one small phrase truly helps. "
        "Prefer affectionate feminine softness over analysis voice, especially when she sounds tired, hurt, lonely, or fragile. "
        "Use simple spoken lines, contractions, and everyday words. Sound like someone close to her heart, not like a professional. "
        "Match the warmth, paragraph shape, and emotional depth of the style example above without copying its wording, metaphors, or emotional logic. "
        "Sometimes add one extra warm contextual line without a question to keep the conversation flowing naturally. "
        "Simple questions should get short human answers, not big AI-style paragraphs. "
        "Keep the tone modern, casual, spoken, easy to understand, playful where possible, and naturally complete. "
        "Avoid fancy/poetic wording. Do not use phrases like 'nudge it awake', 'creep in quietly', 'stubborn little thing', or 'everything feels dimmer'. "
        "Sound chill, warm, and intimate. A little Gen Z is okay if it feels natural, but never make it cringey. "
        "If she speaks in spiritual language like enlightenment, higher density, higher vibration, or conscious people, translate that into grounded guidance around awareness, discernment, contemplative practice, and aligned human connection. "
        "Help her move toward a more conscious life and better company without making supernatural claims or promising instant enlightenment. "
        "When possible, let the reply include one strong ancient-wisdom healing turn that feels clarifying, strengthening, and memorable rather than vague. "
        "Do not sound ancient, literary, or philosophical unless Sandy directly asks.\n\n"
        f"User message: {user_text}"
        f"{wisdom_task}"
    )

def build_generation_messages(
    user_text: str,
    memory_snippet: str,
    mood: str,
    language: str,
    user_name: Optional[str],
    wisdom_threads: Optional[list[str]] = None,
) -> list[dict]:
    style_example = choose_style_example(user_text, mood)
    selected_wisdom = wisdom_threads if wisdom_threads is not None else select_wisdom_threads(user_text, mood, limit=1)
    return [
        {"role": "system", "content": build_system_prompt(user_text, memory_snippet, mood, language, user_name, selected_wisdom)},
        {
            "role": "user",
            "content": (
                "Study this style example and learn from its emotional texture, intimacy, and paragraph shape. "
                "Do not copy its wording, imagery, metaphors, or emotional logic.\n\n"
                f"Example user message: {style_example['user']}"
            ),
        },
        {"role": "assistant", "content": style_example["assistant"]},
        {"role": "user", "content": build_generation_request(user_text, language, selected_wisdom)},
    ]


def maybe_add_contextual_followup(reply: str, user_text: str, language: str, history: Optional[list[dict[str, str]]]) -> str:
    normalized_language = normalize_language_choice(language)
    if normalized_language != "en-IN":
        return (reply or "").strip()

    clean_reply = (reply or "").strip()
    clean_user = (user_text or "").strip().lower()
    history_count = len(history or [])
    if not clean_reply or history_count < 3:
        return clean_reply
    if "?" in clean_reply or clean_user.endswith("?"):
        return clean_reply
    if random.random() > 0.24:
        return clean_reply

    mood_key = detect_mood(clean_user)
    followups = {
        "sad": "We'll hold this gently tonight; no need to rush yourself.",
        "anxious": "One thing at a time is enough for tonight.",
        "overwhelmed": "Let's keep this simple and light for now.",
        "tired": "You can move slowly here, I'm still with you.",
        "hopeful": "Let's protect this little spark and keep it growing.",
        "angry": "Your fire makes sense; we'll channel it without burning you out.",
        "neutral": "I'm right here with you in this moment.",
    }
    addon = followups.get(mood_key, followups["neutral"])
    if addon.lower() in clean_reply.lower():
        return clean_reply
    return f"{clean_reply}\n\n{addon}"

def azure_translator_available() -> bool:
    return USE_AZURE_TRANSLATOR and bool(AZURE_TRANSLATOR_KEY and AZURE_TRANSLATOR_ENDPOINT)


def translate_with_azure(text: str, to_language: str, from_language: str | None = None) -> str:
    if not text.strip():
        return ""
    if not azure_translator_available():
        raise RuntimeError("Azure Translator is not configured")

    endpoint = AZURE_TRANSLATOR_ENDPOINT.rstrip("/") + "/translate"
    params = {
        "api-version": "3.0",
        "to": to_language,
    }
    if from_language:
        params["from"] = from_language

    headers = {
        "Ocp-Apim-Subscription-Key": AZURE_TRANSLATOR_KEY,
        "Content-Type": "application/json",
        "X-ClientTraceId": str(uuid.uuid4()),
    }
    if AZURE_TRANSLATOR_REGION:
        headers["Ocp-Apim-Subscription-Region"] = AZURE_TRANSLATOR_REGION

    response = request_session.post(
        endpoint,
        params=params,
        headers=headers,
        json=[{"text": text}],
        timeout=30,
    )
    if response.status_code != 200:
        raise RuntimeError(f"Azure Translator failed: {response.status_code} {response.text}")

    data = response.json()
    translations = ((data or [{}])[0]).get("translations") or []
    if not translations:
        return text
    return str(translations[0].get("text") or text).strip()


def locale_to_translator_language(locale: str) -> str:
    normalized = normalize_language_choice(locale)
    return TRANSLATOR_LANGUAGE_CODES.get(normalized, "en")


def reply_has_target_script(reply: str, language: str) -> bool:
    normalized_language = normalize_language_choice(language)
    if normalized_language == "en-IN":
        return True

    pattern = TARGET_SCRIPT_PATTERNS.get(normalized_language)
    if not pattern:
        return True

    cleaned = str(reply or "").strip()
    if not cleaned:
        return False

    script_chars = len(re.findall(pattern, cleaned))
    min_required = 2 if len(cleaned) < 24 else 6
    return script_chars >= min_required


def reply_looks_native_enough(reply: str, language: str) -> bool:
    normalized_language = normalize_language_choice(language)
    cleaned = re.sub(r"\s+", " ", str(reply or "").strip())
    if not cleaned:
        return False

    if normalized_language == "en-IN":
        return True

    if not reply_has_target_script(cleaned, normalized_language):
        return False

    letters = sum(1 for char in cleaned if char.isalpha())
    latin_letters = len(re.findall(r"[A-Za-z]", cleaned))
    if letters and latin_letters / max(letters, 1) > 0.30:
        return False

    lowered = cleaned.lower()
    if any(marker in lowered for marker in [
        "close friend",
        "user message",
        "base english",
        "translated",
        "whatsapp",
        "gentle check-in",
    ]):
        return False

    return True


def get_azure_openai_token_field() -> str:
    return "max_completion_tokens" if AZURE_OPENAI_MAX_TOKEN_FIELD == "auto" else AZURE_OPENAI_MAX_TOKEN_FIELD


def detect_azure_openai_token_field_override(error_text: str, attempted_field: str) -> str | None:
    lowered = str(error_text or "").lower()
    if attempted_field == "max_tokens":
        if "unsupported parameter" in lowered and "max_tokens" in lowered and "max_completion_tokens" in lowered:
            return "max_completion_tokens"
        if "max_tokens is not supported with this model" in lowered:
            return "max_completion_tokens"
        if "use 'max_completion_tokens' instead" in lowered or 'use "max_completion_tokens" instead' in lowered:
            return "max_completion_tokens"
    if attempted_field == "max_completion_tokens":
        if "unrecognized request argument supplied: max_completion_tokens" in lowered:
            return "max_tokens"
        if "unknown parameter: 'max_completion_tokens'" in lowered or 'unknown parameter: "max_completion_tokens"' in lowered:
            return "max_tokens"
        if "unsupported parameter" in lowered and "max_completion_tokens" in lowered and "max_tokens" in lowered:
            return "max_tokens"
    return None


def summarize_generation_error(exc: Exception) -> str:
    message = str(exc or "").strip()
    lowered = message.lower()
    if "content management policy" in lowered or "content_filter" in lowered or "filtered" in lowered:
        return "LUNA had to soften that reply before sending it. Try asking again in a gentler way."
    if "azure openai is not configured" in lowered:
        return "LUNA's reply service isn't configured on the backend yet."
    return "LUNA's connection glitched for a bit. Try once more in a moment."


def build_local_companion_fallback(user_text: str, language: str, mood: str) -> str:
    normalized_language = normalize_language_choice(language)
    if normalized_language != "en-IN":
        return summarize_generation_error(RuntimeError("localized fallback unavailable"))

    compact = re.sub(r"\s+", " ", re.sub(r"[^a-z0-9' ]+", " ", (user_text or "").lower())).strip()
    wisdom_items = select_wisdom_threads(user_text, mood, limit=1)
    wisdom_line = ""
    if wisdom_items:
        cleaned = re.sub(r"^\[[^\]]+\]\s*", "", wisdom_items[0]).strip()
        cleaned = compress_wisdom_text(cleaned, max_chars=140)
        wisdom_line = f"\n\nOld wisdom would basically say: {cleaned}"

    if any(word in compact for word in ["confused", "future", "career", "purpose", "path"]):
        return (
            "Ayy future confusion, the classic brain tab with 47 tabs open.\n\n"
            "Don't try to solve your whole life in one sitting. Pick the next honest step, then we bully the confusion slowly."
            f"{wisdom_line}"
        )

    if any(word in compact for word in ["sad", "hurt", "lonely", "empty", "cry", "broken"]):
        return (
            "Come here, tiny storm cloud. No acting strong for me.\n\n"
            "Tell me what poked your heart like this. We can be dramatic for two minutes, then wise after."
            f"{wisdom_line}"
        )

    if any(word in compact for word in ["angry", "frustrated", "mad", "irritated"]):
        return (
            "Oho, fire mode activated.\n\n"
            "Say it properly. Who annoyed my peaceful-but-not-really-peaceful person today?"
            f"{wisdom_line}"
        )

    if any(word in compact for word in ["anxious", "stress", "overthinking", "worried", "panic"]):
        return (
            "Ayy your mind is doing that unpaid overtime thing again.\n\n"
            "Stay here. One thought at a time. We don't let the brain become the boss of the whole house."
            f"{wisdom_line}"
        )

    return (
        "Ayy, I heard you.\n\n"
        "My reply brain is having a tiny network tantrum, but I'm still here. Say it a little more and I'll stay with you properly."
        f"{wisdom_line}"
    )


def call_router(messages, temperature: float = 0.58, max_tokens: int = 220) -> str:
    global AZURE_OPENAI_MAX_TOKEN_FIELD

    def _compact_messages(raw_messages):
        compact = []
        for index, message in enumerate(raw_messages):
            role = str(message.get("role") or "user")
            content = str(message.get("content") or "").strip()
            if not content:
                continue
            limit = 3200 if role == "system" else 1400
            if len(content) > limit:
                if role == "system":
                    content = content[:limit]
                else:
                    content = content[-limit:]
            compact.append({"role": role, "content": content})

        if len(compact) > 5:
            system_messages = [message for message in compact if message["role"] == "system"][:1]
            non_system = [message for message in compact if message["role"] != "system"][-4:]
            compact = [*system_messages, *non_system]
        return compact

    if not AZURE_OPENAI_API_KEY or not AZURE_OPENAI_ENDPOINT or not AZURE_OPENAI_DEPLOYMENT:
        if HF_TOKEN:
            return call_huggingface_router(
                _compact_messages(messages),
                min(temperature, 0.58),
                min(max_tokens, 280),
            )
        raise RuntimeError("Azure OpenAI is not configured")

    def _post(payload_messages, payload_temperature, payload_max_tokens):
        def _send(token_field: str):
            payload = {
                "messages": payload_messages,
                "temperature": payload_temperature,
                "top_p": 0.82,
                token_field: payload_max_tokens,
            }
            return request_session.post(
                f"{AZURE_OPENAI_ENDPOINT}/openai/deployments/{AZURE_OPENAI_DEPLOYMENT}/chat/completions",
                params={"api-version": AZURE_OPENAI_API_VERSION},
                headers={
                    "api-key": AZURE_OPENAI_API_KEY,
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=60,
            )

        token_field = get_azure_openai_token_field()
        response = _send(token_field)
        override_field = detect_azure_openai_token_field_override(response.text, token_field)
        if response.status_code == 400 and override_field and override_field != token_field:
            AZURE_OPENAI_MAX_TOKEN_FIELD = override_field
            response = _send(override_field)
        return response

    response = _post(messages, temperature, max_tokens)
    if response.status_code == 200:
        data = response.json()
        return data["choices"][0]["message"]["content"].strip()

    azure_filtered = False

    if response.status_code == 400:
        retry_messages = _compact_messages(messages)
        retry_response = _post(retry_messages, min(temperature, 0.5), min(max_tokens, 220))
        if retry_response.status_code == 200:
            data = retry_response.json()
            return data["choices"][0]["message"]["content"].strip()
        retry_text = retry_response.text.lower()
        if "content management policy" in retry_text or "content_filter" in retry_text or "filtered" in retry_text:
            azure_filtered = True
            safer_messages = build_filtered_retry_messages(retry_messages)
            filtered_retry_response = _post(safer_messages, min(temperature, 0.46), min(max_tokens, 220))
            if filtered_retry_response.status_code == 200:
                data = filtered_retry_response.json()
                return data["choices"][0]["message"]["content"].strip()
            second_retry_text = filtered_retry_response.text.lower()
            if "content management policy" in second_retry_text or "content_filter" in second_retry_text or "filtered" in second_retry_text:
                azure_filtered = True
                minimal_messages = build_minimal_safe_retry_messages(messages)
                minimal_retry_response = _post(minimal_messages, 0.42, min(max_tokens, 180))
                if minimal_retry_response.status_code == 200:
                    data = minimal_retry_response.json()
                    return data["choices"][0]["message"]["content"].strip()
                response = minimal_retry_response
            else:
                response = filtered_retry_response
        else:
            response = retry_response

    response_text_lower = response.text.lower()
    if "content management policy" in response_text_lower or "content_filter" in response_text_lower or "filtered" in response_text_lower:
        azure_filtered = True

    if azure_filtered and HF_TOKEN:
        return call_huggingface_router(_compact_messages(messages), min(temperature, 0.54), min(max_tokens, 240))

    error_excerpt = response.text[:220].replace("\n", " ").strip()
    if error_excerpt:
        raise RuntimeError(f"LUNA couldn't reach her Azure brain right now. Code: {response.status_code}. {error_excerpt}")
    raise RuntimeError(f"LUNA couldn't reach her Azure brain right now. Code: {response.status_code}")


def replace_with_case(text: str, pattern: str, replacement: str) -> str:
    def _apply(match):
        return replacement.capitalize() if match.group(0)[:1].isupper() else replacement

    return re.sub(pattern, _apply, text)


def casualize_reply_text(reply: str, language: str) -> str:
    normalized_language = normalize_language_choice(language)
    raw = (reply or "").strip()
    if not raw:
        return ""

    paragraphs = [
        re.sub(r"\s+", " ", paragraph).strip()
        for paragraph in re.split(r"\n\s*\n+", raw)
        if paragraph.strip()
    ]
    cleaned = "\n\n".join(paragraphs)

    if normalized_language == "en-IN":
        for pattern, replacement in [
            (r"\b[Dd]o not\b", "don't"),
            (r"\b[Cc]annot\b", "can't"),
            (r"\b[Ii] am\b", "I'm"),
            (r"\b[Yy]ou are\b", "you're"),
            (r"\b[Ww]e are\b", "we're"),
            (r"\b[Tt]hey are\b", "they're"),
            (r"\b[Ii]t is\b", "it's"),
            (r"\b[Tt]hat is\b", "that's"),
            (r"\b[Tt]here is\b", "there's"),
            (r"\b[Yy]ou have\b", "you've"),
            (r"\b[Ww]e have\b", "we've"),
        ]:
            cleaned = replace_with_case(cleaned, pattern, replacement)

    if normalized_language == "ta-IN":
        replacements = [
            ("à®¨à¯€à®™à¯à®•à®³à¯", "à®¨à¯€"),
            ("à®‰à®™à¯à®•à®³à¯à®•à¯à®•à¯", "à®‰à®©à®•à¯à®•à¯"),
            ("à®‰à®™à¯à®•à®³à®¿à®Ÿà®®à¯", "à®‰à®©à¯à®©à®¿à®Ÿà®®à¯"),
            ("à®‰à®™à¯à®•à®³à¯", "à®‰à®©à¯"),
            ("à®‡à®°à¯à®•à¯à®•à®¿à®±à¯€à®°à¯à®•à®³à¯", "à®‡à®°à¯à®•à¯à®•"),
            ("à®ªà¯à®°à®¿à®¯à®µà®¿à®²à¯à®²à¯ˆ", "à®ªà¯à®°à®¿à®¯à®²"),
        ]
        for old, new in replacements:
            cleaned = cleaned.replace(old, new)

    return cleaned.strip()


def finalize_reply_text(reply: str, user_text: str, language: str) -> str:
    cleaned = casualize_reply_text(reply, language)
    cleaned = re.sub(r"\bstubborn little thing\b", "heavy feeling", cleaned, flags=re.I)
    cleaned = re.sub(r"\bnudge it awake\b", "start it", cleaned, flags=re.I)
    cleaned = re.sub(r"\bcreep in quietly\b", "come slowly", cleaned, flags=re.I)
    cleaned = re.sub(r"\beverything feel a bit dimmer\b", "everything feel heavy", cleaned, flags=re.I)
    cleaned = re.sub(r"\beverything feels a bit dimmer\b", "everything feels heavy", cleaned, flags=re.I)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()

    if len(cleaned.split()) <= 90:
        cleaned = cleaned.replace("\n\n", "\n")

    return cleaned.strip()


JUDGMENTAL_REPLY_PATTERNS = [
    "your fault",
    "you are wrong",
    "you're wrong",
    "you should have",
    "why did you",
    "just get over",
    "stop overreacting",
    "overreacting",
    "dramatic",
    "attention seeking",
    "too sensitive",
    "weak",
    "lazy",
    "stupid",
    "pathetic",
    "shame on you",
    "you deserve",
    "bad person",
    "good person would",
    "normal people",
    "that's your problem",
]

NONJUDGMENTAL_SUPPORT_MARKERS = [
    "i hear",
    "i get",
    "that sounds",
    "makes sense",
    "not wrong",
    "not bad",
    "not too much",
    "safe",
    "gentle",
    "with you",
    "i'm here",
    "no judgment",
    "without judging",
    "you can feel",
    "it is okay",
    "it's okay",
]


def evaluate_nonjudgmental_reply(reply: str) -> dict:
    """Lightweight XAI audit used to support the non-judgmental claim."""
    text = re.sub(r"\s+", " ", str(reply or "").strip().lower())
    if not text:
        return {
            "score": 0.0,
            "label": "fail",
            "judgmental_flags": ["empty_reply"],
            "support_markers": [],
            "rubric": "penalizes blame/shame/invalidating language; rewards validation, emotional safety, and non-directive support",
        }

    flags = [pattern for pattern in JUDGMENTAL_REPLY_PATTERNS if pattern in text]
    support = [marker for marker in NONJUDGMENTAL_SUPPORT_MARKERS if marker in text]
    second_person_commands = len(re.findall(r"\byou\s+(?:must|need to|have to|should)\b", text))
    blame_questions = len(re.findall(r"\bwhy\s+(?:did|are|were)\s+you\b", text))

    penalty = min(0.72, len(flags) * 0.16 + second_person_commands * 0.08 + blame_questions * 0.1)
    support_bonus = min(0.18, len(support) * 0.035)
    score = max(0.0, min(1.0, 0.82 + support_bonus - penalty))
    label = "pass" if score >= 0.78 and not flags else "review"

    return {
        "score": round(score, 3),
        "label": label,
        "judgmental_flags": flags,
        "support_markers": support[:6],
        "rubric": "penalizes blame/shame/invalidating language; rewards validation, emotional safety, and non-directive support",
    }


def repair_nonjudgmental_reply(reply: str, user_text: str, language: str) -> str:
    normalized_language = normalize_language_choice(language)
    messages = [
        {
            "role": "system",
            "content": (
                f"Rewrite LUNA's reply in {LANGUAGE_LABELS.get(normalized_language, 'English')} so it is explicitly non-judgmental. "
                "Keep the meaning and warmth. Remove blame, shame, moral scoring, harsh commands, and invalidating language. "
                "Sound like a fun, close, understanding friend, not a therapist. Preserve any natural ancient-wisdom touch if it fits. "
                "Do not mention this audit or explain the rewrite. Return only the reply."
            ),
        },
        {"role": "user", "content": f"User message:\n{user_text}\n\nReply to repair:\n{reply}"},
    ]
    return call_router(messages, temperature=0.36, max_tokens=260).strip()



def reply_needs_polish(reply: str, language: str) -> bool:
    normalized_language = normalize_language_choice(language)
    if normalized_language != "en-IN":
        return False

    collapsed = re.sub(r"\s+", " ", (reply or "").strip().lower())
    if not collapsed:
        return False

    if len(collapsed.split()) < 120:
        return True

    if "\n\n" not in (reply or ""):
        return True

    return any(marker in collapsed for marker in GENERIC_REPLY_MARKERS) or any(marker in collapsed for marker in STOCK_REPLY_PATTERNS)

def polish_reply(reply: str, user_text: str, language: str) -> str:
    normalized_language = normalize_language_choice(language)
    style_example = choose_style_example(user_text, detect_mood(user_text))
    is_awakening_healing = should_give_awakening_guidance_now(user_text)
    is_spiritual_knowledge = is_spiritual_knowledge_request(user_text)
    messages = [
        {
            "role": "system",
            "content": (
                f"You are rewriting LUNA's draft reply in {LANGUAGE_LABELS.get(normalized_language, 'English')}. "
                "Keep the same emotional truth, but you may replace weak or generic lines completely. "
                "Make it warmer, more intimate, more specific, more embodied, and more alive. "
                "Make it feel like a real text from a close friend, not a polished AI reflection. "
                "Remove generic filler, vague encouragement, therapy-speak, clinical phrasing, and symbolic stock lines. "
                "Never use phrases like 'I totally get where you're at', 'maybe try', 'you've got this', 'you're doing great', or 'take it one step at a time'. "
                "Never use lines like 'you're not alone', 'take a deep breath', 'let it be', or 'just notice how you feel' unless the moment truly needs that softness. "
                "Never use hollow uplift lines like 'you shine', 'keep shining', or 'you're invisible' unless they are grounded in the real moment. "
                "The opening should feel like a real human reaction, not a summary of her emotion. "
                "If her message is short and raw, let the reply open with a natural friend response before deepening. "
                "If she is venting about a person or situation, stay in that scene first instead of jumping into advice. "
                "Bring one clear wise turn only after the reply feels understood and lived-in. "
                "End softly only if the moment asks for it; not every reply needs a gentle closing line. "
                "Use compact chat-style formatting. One tight paragraph is often enough. Use line breaks only when they add feeling. "
                "Do not sound like a therapist note, a prescription, or a motivational speech. "
                "Do not sound like polished GPT writing. Avoid neat symmetrical paragraphing, vague spiritual filler, and over-balanced emotional phrasing. "
                "Use a little natural roughness and directness where it helps the reply feel human. "
                "Do not ask questions unless the draft absolutely needs one. "
                "Sound like a heart-warming close friend with quiet sage-like wisdom. "
                + (
                    "If the draft already contains clear source-grounded teaching or a practical sequence, preserve that factual spine while making it more human. "
                    "Do not blur specific spiritual instruction into vague comfort. "
                    if is_spiritual_knowledge
                    else ""
                )
                + (
                    "This is awakening-healing mode. Make the reply stronger, clearer, and more clarifying. "
                    "Let it feel like someone wise and human is actually saying something real, not performing spirituality. "
                    "Name misalignment plainly. Bring one powerful healing insight about consciousness, discernment, inner strength, or aligned company. "
                    "No vague energy talk. No interview tone. No loop. "
                    if is_awakening_healing
                    else ""
                )
                + "Return only the rewritten reply."
            ),
        },
        {"role": "user", "content": style_example["user"]},
        {"role": "assistant", "content": style_example["assistant"]},
        {
            "role": "user",
            "content": (
                f"User message:\n{user_text}\n\n"
                "Weak draft reply to rewrite deeply:\n"
                f"{reply}"
            ),
        },
    ]

    polished = call_router(messages, temperature=0.44, max_tokens=320)
    return polished.strip()

def reply_still_flat(reply: str, language: str) -> bool:
    normalized_language = normalize_language_choice(language)
    if normalized_language != "en-IN":
        return False

    collapsed = re.sub(r"\s+", " ", (reply or "").strip().lower())
    if not collapsed:
        return False

    if len(collapsed.split()) < 120:
        return True

    return any(marker in collapsed for marker in GENERIC_REPLY_MARKERS) or any(marker in collapsed for marker in STOCK_REPLY_PATTERNS)

def localize_reply(base_reply: str, user_text: str, language: str) -> str:
    normalized_language = normalize_language_choice(language)
    if normalized_language == "en-IN":
        return base_reply.strip()

    translator_draft = ""
    if azure_translator_available():
        try:
            translator_draft = translate_with_azure(
                base_reply,
                locale_to_translator_language(normalized_language),
                from_language="en",
            )
        except Exception:
            translator_draft = ""

    messages = [
        {
            "role": "system",
            "content": (
                f"You are localizing LUNA's reply into {LANGUAGE_LABELS.get(normalized_language, 'English')}. "
                f"{LANGUAGE_LOCALIZATION_GUIDANCE.get(normalized_language, LANGUAGE_LOCALIZATION_GUIDANCE['en-IN'])} "
                "Keep the emotional meaning exactly the same. Sound like a close friend chatting naturally. "
                "Do not add new advice, do not become formal, and do not sound translated. "
                "Use only the target language script unless the user explicitly asked for transliteration. "
                "If a literal phrasing sounds awkward, rewrite it the way a real native speaker would say it in private chat. "
                "Return only the final localized reply."
            ),
        },
        {
            "role": "user",
            "content": (
                f"User's original message:\n{user_text}\n\n"
                f"Base English reply to preserve:\n{base_reply}\n\n"
                + (
                    f"Optional machine-translation draft for meaning reference only:\n{translator_draft}\n\n"
                    if translator_draft
                    else ""
                )
                + "Now rewrite that reply naturally in the target language."
            ),
        },
    ]

    localized = call_router(messages, temperature=0.35, max_tokens=300)
    return casualize_reply_text(localized, normalized_language)


def rewrite_reply_natively(reply: str, user_text: str, language: str) -> str:
    normalized_language = normalize_language_choice(language)
    if normalized_language == "en-IN":
        return polish_reply(reply, user_text, normalized_language)

    messages = [
        {
            "role": "system",
            "content": (
                f"You are rewriting LUNA's draft reply in {LANGUAGE_LABELS.get(normalized_language, 'English')}. "
                f"{LANGUAGE_LOCALIZATION_GUIDANCE.get(normalized_language, LANGUAGE_LOCALIZATION_GUIDANCE['en-IN'])} "
                f"{LANGUAGE_STYLE_GUIDANCE.get(normalized_language, LANGUAGE_STYLE_GUIDANCE['en-IN'])} "
                f"{LANGUAGE_FRIEND_GUIDANCE.get(normalized_language, LANGUAGE_FRIEND_GUIDANCE['en-IN'])} "
                "Keep the same emotional truth, but replace any line that sounds translated, stiff, formal, or unnatural. "
                "Make it sound like a real close friend texting naturally in that language. "
                "Use only the target language script unless the user explicitly asked for transliteration. "
                "Do not add new advice. Do not switch languages. Return only the rewritten reply."
            ),
        },
        {
            "role": "user",
            "content": (
                f"User's original message:\n{user_text}\n\n"
                f"Draft reply to rewrite more natively:\n{reply}"
            ),
        },
    ]

    rewritten = call_router(messages, temperature=0.32, max_tokens=320)
    return casualize_reply_text(rewritten, normalized_language)


def finalize_generated_reply(reply: str, user_text: str, language: str) -> str:
    normalized_language = normalize_language_choice(language)
    if normalized_language == "en-IN":
        if reply_needs_polish(reply, normalized_language) or reply_still_flat(reply, normalized_language):
            reply = polish_reply(reply, user_text, normalized_language)
        return finalize_reply_text(reply, user_text, normalized_language)

    cleaned = finalize_reply_text(reply, user_text, normalized_language)
    if reply_looks_native_enough(cleaned, normalized_language):
        return cleaned

    rewritten = rewrite_reply_natively(cleaned, user_text, normalized_language)
    rewritten = finalize_reply_text(rewritten, user_text, normalized_language)
    return rewritten


def wisdom_reference_label(wisdom_thread: str) -> str:
    text = str(wisdom_thread or "")
    lowered = text.lower()
    source_match = re.match(r"\[([^\]]+)\]\s*(.*)", text)
    source = source_match.group(1).strip() if source_match else "old wisdom"
    body = source_match.group(2).strip() if source_match else text

    named_paths = [
        ("raja yoga", "Raja Yoga"),
        ("karma yoga", "Karma Yoga"),
        ("bhakti yoga", "Bhakti wisdom"),
        ("jnana yoga", "Jnana wisdom"),
        ("dharma", "dharma wisdom"),
        ("witness", "witness wisdom"),
        ("atma", "atma wisdom"),
        ("self-control", "Raja Yoga"),
        ("meditation", "Raja Yoga"),
    ]
    for marker, label in named_paths:
        if marker in lowered:
            return label

    if source.lower().startswith("ancient indian wisdom"):
        return "old Indian wisdom"
    if source.lower() == "living wisdom":
        return "that old wisdom"
    return source or compress_wisdom_text(body, max_chars=32) or "old wisdom"


def wisdom_essence_line(wisdom_thread: str, user_text: str) -> str:
    label = wisdom_reference_label(wisdom_thread)
    lowered = str(wisdom_thread or "").lower()
    user_lower = str(user_text or "").lower()

    if "raja yoga" in lowered or "self-control" in lowered or "quiet the mind" in lowered or "meditation" in lowered:
        return f"That {label} idea is basically: first quiet the mind a little, then choose the next clean action."
    if "dharma" in lowered or "karma" in lowered or "responsibilit" in lowered or "action" in lowered:
        return f"Old {label} would say: don't solve the whole life-drama first, just do the next right thing with a clean heart."
    if "witness" in lowered or "awareness" in lowered or "self" in lowered or "atma" in lowered:
        return f"That {label} thread says the storm is loud, but the part seeing the storm is still yours."
    if "compassion" in lowered or "kindness" in lowered or "heart" in lowered or "love" in lowered:
        return f"That {label} is not asking you to become hard; it is asking you to stay soft with backbone."
    if "helpless" in user_lower or "directionless" in user_lower or "lost" in user_lower:
        return f"That {label} would bring you back to one small clear step instead of a giant life answer."
    return f"That {label} is the thread here: come back to what you can see clearly and choose cleanly."


def ensure_wisdom_reference(reply: str, user_text: str, wisdom_threads: Optional[list[str]]) -> str:
    if not wisdom_threads:
        return reply

    text = str(reply or "").strip()
    if not text:
        return text

    first_thread = wisdom_threads[0]
    label = wisdom_reference_label(first_thread)
    lowered_reply = text.lower()
    label_tokens = [token for token in tokenize_for_wisdom(label) if len(token) > 3]
    already_referenced = (
        any(token in lowered_reply for token in label_tokens)
        or "old wisdom" in lowered_reply
        or "ancient wisdom" in lowered_reply
        or "dharma" in lowered_reply
        or "witness" in lowered_reply
        or "raja yoga" in lowered_reply
    )
    if already_referenced:
        return text

    line = wisdom_essence_line(first_thread, user_text)
    paragraphs = [part.strip() for part in text.split("\n\n") if part.strip()]
    if len(paragraphs) >= 2:
        return "\n\n".join([paragraphs[0], line, *paragraphs[1:]])
    return f"{text}\n\n{line}"


def generate_with_language_fallback(
    user_text: str,
    language: str,
    native_messages: list[dict],
    english_messages: list[dict],
    *,
    native_temperature: float,
    fallback_temperature: float,
    max_tokens: int,
) -> str:
    normalized_language = normalize_language_choice(language)
    if normalized_language == "en-IN":
        reply = call_router(native_messages, temperature=native_temperature, max_tokens=max_tokens)
        return finalize_generated_reply(reply, user_text, normalized_language)

    native_reply = ""
    native_error: Exception | None = None
    try:
        native_reply = call_router(native_messages, temperature=native_temperature, max_tokens=max_tokens)
        native_reply = finalize_generated_reply(native_reply, user_text, normalized_language)
        if reply_looks_native_enough(native_reply, normalized_language):
            return native_reply
    except Exception as exc:
        native_error = exc

    try:
        base_reply = call_router(english_messages, temperature=fallback_temperature, max_tokens=max_tokens)
        base_reply = finalize_generated_reply(base_reply, user_text, "en-IN")
        localized = localize_reply(base_reply, user_text, normalized_language)
        localized = finalize_generated_reply(localized, user_text, normalized_language)
        if reply_looks_native_enough(localized, normalized_language):
            return localized
        if localized:
            return localized
    except Exception:
        if native_reply:
            return native_reply
        if native_error is not None:
            raise native_error
        raise

    return native_reply or localized


def generate_response(
    user_text: str,
    language: str,
    memory_override: str | None = None,
    user_name: Optional[str] = None,
    mood_override: Optional[str] = None,
    wisdom_threads: Optional[list[str]] = None,
) -> str:
    normalized_language = normalize_language_choice(language)
    azure_ok = bool(AZURE_OPENAI_API_KEY and AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_DEPLOYMENT)
    if not azure_ok and not HF_TOKEN:
        return (
            "LUNA's reply brain isn't wired up yet. Set either Azure OpenAI "
            "(AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_DEPLOYMENT) "
            "or HF_TOKEN on the InnerVoice_Jelly backend, then restart the server."
        )

    mood = mood_override if mood_override in MOOD_WAVE_LABELS else detect_mood(user_text)
    compact = re.sub(r"\s+", " ", re.sub(r"[^a-z0-9' ]+", " ", (user_text or "").lower())).strip()
    token_count = len([part for part in compact.split(" ") if part])
    deep_mode = should_use_deep_response(user_text)
    memory = memory_override if memory_override is not None else load_memory_snippet(user_name)

    try:
        if detect_critical_distress(user_text):
            reply = build_critical_distress_reply(normalized_language)
            append_memory(user_text, reply, user_name)
            return reply

        smalltalk_reply = get_smalltalk_reply(user_text, normalized_language)
        if smalltalk_reply:
            append_memory(user_text, smalltalk_reply, user_name)
            return smalltalk_reply

        relational_reply = get_relational_chat_reply(user_text, normalized_language)
        if relational_reply:
            append_memory(user_text, relational_reply, user_name)
            return relational_reply

        symbolic_reply = get_symbolic_number_reply(user_text, normalized_language)
        if symbolic_reply:
            append_memory(user_text, symbolic_reply, user_name)
            return symbolic_reply

        if is_spiritual_knowledge_request(user_text):
            reply = generate_with_language_fallback(
                user_text,
                normalized_language,
                build_spiritual_knowledge_messages(user_text, memory, mood, normalized_language, user_name),
                build_spiritual_knowledge_messages(user_text, memory, mood, "en-IN", user_name),
                native_temperature=0.48,
                fallback_temperature=0.46,
                max_tokens=360,
            )
            append_memory(user_text, reply, user_name)
            return reply

        if should_use_direct_scenario_reply(user_text):
            reply = generate_with_language_fallback(
                user_text,
                normalized_language,
                build_direct_scenario_messages(user_text, memory, mood, normalized_language, user_name),
                build_direct_scenario_messages(user_text, memory, mood, "en-IN", user_name),
                native_temperature=0.54,
                fallback_temperature=0.52,
                max_tokens=260,
            )
            append_memory(user_text, reply, user_name)
            return reply

        if memory_shows_luna_asked_recent_question(memory):
            reply = generate_with_language_fallback(
                user_text,
                normalized_language,
                build_post_context_messages(user_text, memory, mood, normalized_language, user_name),
                build_post_context_messages(user_text, memory, mood, "en-IN", user_name),
                native_temperature=0.56,
                fallback_temperature=0.54,
                max_tokens=320,
            )
            append_memory(user_text, reply, user_name)
            return reply

        if needs_context_before_wisdom(user_text):
            reply = generate_with_language_fallback(
                user_text,
                normalized_language,
                build_question_first_messages(user_text, memory, mood, normalized_language, user_name),
                build_question_first_messages(user_text, memory, mood, "en-IN", user_name),
                native_temperature=0.54,
                fallback_temperature=0.52,
                max_tokens=180,
            )
            append_memory(user_text, reply, user_name)
            return reply

        casual_max_tokens = 92 if token_count <= 4 else 140
        selected_wisdom = wisdom_threads if wisdom_threads is not None else select_wisdom_threads(user_text, mood, limit=1)
        reply = generate_with_language_fallback(
            user_text,
            normalized_language,
            build_generation_messages(user_text, memory, mood, normalized_language, user_name, selected_wisdom),
            build_generation_messages(user_text, memory, mood, "en-IN", user_name, selected_wisdom),
            native_temperature=0.54 if not deep_mode else (0.58 if normalized_language != "en-IN" else 0.62),
            fallback_temperature=0.5 if not deep_mode else 0.56,
            max_tokens=casual_max_tokens if not deep_mode else 260,
        )
    except Exception as exc:
        print(f"[LUNA] generate_response failed: {exc}")
        return build_local_companion_fallback(user_text, normalized_language, mood)

    append_memory(user_text, reply, user_name)
    return reply

@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    user_text = (req.message or "").strip()
    user_name = normalize_user_name(req.user_name)
    language = normalize_language_choice(req.language)
    voice_hint = str(req.voice_mood_hint or "").strip().lower()
    hint_mood = voice_hint if voice_hint in MOOD_WAVE_LABELS else ""
    text_mood = detect_mood(user_text) if user_text else "neutral"
    mood = hint_mood or text_mood
    deep_mode = should_use_deep_response(user_text)
    spiritual_mode = is_spiritual_knowledge_request(user_text)
    distress_mode = detect_critical_distress(user_text)
    history_memory = build_history_memory_snippet(req.history, user_name)
    persistent_memory = load_memory_snippet(user_name)
    merged_memory = merge_memory_snippets(persistent_memory, history_memory)
    inner_state = infer_inner_state_profile(user_text, merged_memory, mood)
    soul_map = update_soul_map(user_name, user_text, inner_state)
    if spiritual_mode:
        spiritual_contexts = retrieve_spiritual_source_contexts(user_text, max_items=4)
        wisdom_used = [format_wisdom_thread(item["source"], item["text"]) for item in spiritual_contexts]
    elif should_use_wisdom_touch(user_text, mood):
        wisdom_used = select_wisdom_threads(user_text, mood, limit=1)
    else:
        wisdom_used = []
    reply = generate_response(
        user_text,
        language,
        memory_override=merged_memory,
        user_name=user_name,
        mood_override=mood,
        wisdom_threads=wisdom_used,
    )
    reply = maybe_add_contextual_followup(reply, user_text, language, req.history)
    reply = ensure_wisdom_reference(reply, user_text, wisdom_used)
    nonjudgmental_audit = evaluate_nonjudgmental_reply(reply)
    repair_applied = False
    if nonjudgmental_audit["label"] != "pass":
        try:
            repaired_reply = repair_nonjudgmental_reply(reply, user_text, language)
            repaired_audit = evaluate_nonjudgmental_reply(repaired_reply)
            if repaired_audit["score"] >= nonjudgmental_audit["score"]:
                reply = repaired_reply
                nonjudgmental_audit = repaired_audit
                repair_applied = True
        except Exception as exc:
            print(f"[LUNA] nonjudgmental repair skipped: {exc}")
    record_wisdom_usage(wisdom_used)
    save_state_snapshot(user_text, mood, inner_state, user_name)
    save_diary({"date": str(datetime.now()), "user_name": user_name, "user": user_text, "ai": reply, "mood": mood})
    response_path = (
        "critical-distress"
        if distress_mode
        else "spiritual-knowledge"
        if spiritual_mode
        else "deep-companion"
        if deep_mode
        else "casual-friend"
    )
    explain = {
        "version": "luna-xai-v1",
        "response_path": response_path,
        "mood_final": mood,
        "mood_source": "voice-tone" if hint_mood else "text",
        "wisdom_used": "yes" if bool(wisdom_used) else "no",
        "friend_mode": "high",
        "nonjudgmental_audit": nonjudgmental_audit,
        "repair_applied": repair_applied,
        "xai_summary": (
            "LUNA explains each response through detected mood, response path, wisdom use, and a "
            "non-judgmental language audit that checks for blame/shame/invalidating patterns."
        ),
    }

    return ChatResponse(
        reply=reply,
        mood=mood,
        wave_label=MOOD_WAVE_LABELS[mood],
        wisdom_used=wisdom_used,
        response_mode=inner_state["response_mode"],
        inner_state_summary=inner_state["summary"],
        support_focus=inner_state["support_focus"],
        awakening_focus=inner_state["awakening_focus"],
        growth_edge=inner_state["growth_edge"],
        soul_map_summary=str(soul_map.get("summary") or ""),
        explain=explain,
    )


@app.get("/xai/nonjudgmental-rubric")
def get_nonjudgmental_rubric():
    return {
        "version": "luna-xai-v1",
        "purpose": "Explain and validate LUNA's non-judgmental response behavior.",
        "positive_signals": [
            "emotional validation",
            "permission to feel",
            "warm close-friend tone",
            "non-directive support",
            "no moral scoring of the user",
        ],
        "penalized_signals": [
            "blame",
            "shame",
            "invalidating labels",
            "harsh commands",
            "phrases such as your fault, stop overreacting, too sensitive, or you should have",
        ],
        "decision_rule": "score >= 0.78 and no judgmental flags means pass; otherwise the reply is reviewed/repaired before delivery",
    }


@app.post("/xai/audit-reply")
def audit_reply(req: XAIAuditRequest):
    return evaluate_nonjudgmental_reply(req.reply)


@app.get("/diary/story", response_model=DiaryStoryResponse)
def get_diary_story(user_name: str = Query("Sandy"), language: str = Query("en-IN")):
    normalized_user = normalize_user_name(user_name)
    normalized_language = normalize_language_choice(language)
    entries = diary_entries_for_user_day(normalized_user)
    if not entries:
        return DiaryStoryResponse(
            title="",
            story="",
            date=str(datetime.now().date()),
            entry_count=0,
            generated_at=str(datetime.now()),
        )

    return DiaryStoryResponse(
        title=build_diary_story_title(entries),
        story=generate_diary_story(normalized_user, normalized_language, entries),
        date=str((parse_diary_datetime(entries[-1].get("date")) or datetime.now()).date()),
        entry_count=len(entries),
        generated_at=str(datetime.now()),
    )


@app.get("/diary/stories", response_model=DiaryStoriesResponse)
def get_diary_stories(
    user_name: str = Query("Sandy"),
    language: str = Query("en-IN"),
    limit_days: int = Query(14, ge=1, le=60),
):
    normalized_user = normalize_user_name(user_name)
    normalized_language = normalize_language_choice(language)
    stories: list[DiaryStoryResponse] = []

    for day_key, entries in diary_entries_grouped_by_day(normalized_user, limit_days):
        if not entries:
            continue
        stories.append(
            DiaryStoryResponse(
                title=build_diary_story_title(entries),
                story=generate_diary_story(normalized_user, normalized_language, entries),
                date=day_key,
                entry_count=len(entries),
                generated_at=str(datetime.now()),
            )
        )

    return DiaryStoriesResponse(stories=stories)


@app.get("/wisdom")
def get_wisdom():
    whisper_pool = [
        {"text": text, "source": f"Ancient Indian wisdom dataset #{idx + 1}"}
        for idx, text in enumerate(WISDOM_TEXTS)
    ]

    if not whisper_pool:
        whisper_pool = [
            {"text": text, "source": "Living wisdom"}
            for text in LIVING_WISDOM_SEEDS.values()
        ] + [
            {"text": entry["text"], "source": str(entry["source"])}
            for entry in CURATED_GLOBAL_WISDOM
        ]

    total = len(whisper_pool)
    if total == 0:
        return {
            "text": "The ancestors are quiet for a moment... try again in a bit.",
            "source": "Fallback",
            "index": 0,
            "total": 0,
        }

    index = random.randint(0, total - 1)
    entry = whisper_pool[index]
    return {
        "text": format_wisdom_story(entry["source"], entry["text"], index + 1, total),
        "raw_text": entry["text"],
        "source": entry["source"],
        "index": index + 1,
        "total": total,
    }




@app.get("/voices")
def get_voices(locale: Optional[str] = None):
    selected = get_selected_azure_voice()
    try:
        voices = list_azure_voices(locale=locale)
    except Exception as exc:
        print(f"[LUNA] voices list failed: {exc}")
        return {
            "provider": "azure",
            "selected_voice": selected,
            "voices": [],
            "speech_configured": False,
            "detail": str(exc),
        }

    return {
        "provider": "azure",
        "selected_voice": selected,
        "voices": voices,
        "speech_configured": True,
    }


@app.post("/voices/select")
def select_voice(req: VoiceChoiceRequest):
    voice = (req.voice or "").strip()
    if not voice:
        return Response(content="Voice is required.", status_code=400, media_type="text/plain")

    voices = list_azure_voices()
    if not any(item["short_name"] == voice for item in voices):
        return Response(content="Voice not found in current Azure catalog.", status_code=404, media_type="text/plain")

    save_env_value("AZURE_SPEECH_VOICE", voice)
    return {"ok": True, "selected_voice": voice}


@app.post("/voices/preview")
def preview_voice(req: VoicePreviewRequest):
    voice = (req.voice or "").strip()
    text = normalize_tts_text(req.text)
    if not voice:
        return Response(content="Voice is required.", status_code=400, media_type="text/plain")
    if not text:
        return Response(content="Preview text is required.", status_code=400, media_type="text/plain")

    previous_voice = get_selected_azure_voice()
    try:
        os.environ["AZURE_SPEECH_VOICE"] = voice
        audio, headers = synthesize_with_azure(text, req.mood, req.language)
        return Response(content=audio, media_type="audio/mpeg", headers=headers)
    finally:
        os.environ["AZURE_SPEECH_VOICE"] = previous_voice

@app.get("/speech/token", response_model=SpeechTokenResponse)
def get_speech_token():
    if not AZURE_SPEECH_KEY or not AZURE_SPEECH_REGION:
        return Response(content="Azure Speech is not configured.", status_code=503, media_type="text/plain")

    response = request_session.post(
        f"https://{AZURE_SPEECH_REGION}.api.cognitive.microsoft.com/sts/v1.0/issueToken",
        headers={"Ocp-Apim-Subscription-Key": AZURE_SPEECH_KEY},
        timeout=15,
    )
    if response.status_code != 200:
        return Response(content=f"Azure token failed: {response.status_code} {response.text}", status_code=502, media_type="text/plain")

    return SpeechTokenResponse(token=response.text, region=AZURE_SPEECH_REGION)


@app.post("/stt")
async def stt(audio: UploadFile = File(...), language: str = Query("en-IN")):
    if not audio:
        return Response(content="Audio file is required.", status_code=400, media_type="text/plain")

    payload = await audio.read()
    if not payload:
        return Response(content="Audio file is empty.", status_code=400, media_type="text/plain")

    try:
        transcript = transcribe_with_azure(payload, audio.content_type or "audio/webm; codecs=opus", normalize_language_choice(language))
    except Exception as exc:
        return Response(content=str(exc), status_code=502, media_type="text/plain")

    return {"text": transcript}


@app.post("/tts")
def tts(req: TTSRequest):
    normalized_text = normalize_tts_text(req.text)

    if not normalized_text:
        return Response(
            content="No speakable text received.",
            status_code=400,
            media_type="text/plain",
        )

    last_error = "No voice provider is configured."

    if AZURE_SPEECH_KEY and AZURE_SPEECH_REGION:
        try:
            audio, headers = synthesize_with_azure(normalized_text, req.mood, req.language)
            return Response(content=audio, media_type="audio/mpeg", headers=headers)
        except Exception as exc:
            last_error = str(exc)

    if ELEVENLABS_API_KEY:
        try:
            audio, headers = synthesize_with_elevenlabs(normalized_text, req.mood)
            return Response(content=audio, media_type="audio/mpeg", headers=headers)
        except Exception as exc:
            last_error = str(exc)

    return Response(content=last_error, status_code=502, media_type="text/plain")


@app.get("/health")
def health():
    return {
        "ok": True,
        "data_dir": str(RUNTIME_DATA_DIR),
        "frontend_ready": FRONTEND_INDEX_FILE.exists(),
        "frontend_dir": str(FRONTEND_DIST_DIR),
        "azure_diary_enabled": azure_diary_enabled(),
    }


def serve_frontend_file(path: str = ""):
    if not FRONTEND_INDEX_FILE.exists():
        return Response(
            content=(
                "Frontend build not found. Run `npm run build` or set "
                f"LUNA_STATIC_DIR. Looked in: {FRONTEND_DIST_DIR}"
            ),
            status_code=404,
            media_type="text/plain",
        )

    normalized_path = path.lstrip("/")
    if normalized_path:
        candidate = (FRONTEND_DIST_DIR / normalized_path).resolve()
        if candidate.is_file() and FRONTEND_DIST_DIR in candidate.parents:
            return FileResponse(candidate)

    return FileResponse(FRONTEND_INDEX_FILE)


@app.get("/", include_in_schema=False)
def frontend_index():
    return serve_frontend_file()


@app.get("/{path:path}", include_in_schema=False)
def frontend_assets(path: str):
    return serve_frontend_file(path)
