import React, { useCallback, useEffect, useRef, useState } from "react";
import axios from "axios";
import * as SpeechSDK from "microsoft-cognitiveservices-speech-sdk";
import MoonScene from "./MoonScene";
import { API_BASE } from "./apiBase";
import "./App.css";

const SONOTHERAPY_PROFILES = {
  angry: {
    track: "/tracks/alpha_relief_space.mp3",
    label: "Grounding field • cooling the heat into steadiness",
    volume: 0.34,
    playbackRate: 0.96,
  },
  sad: {
    track: "/tracks/432hz_soft_piano.mp3",
    label: "432 Hz heart-softening field • warmth, grief, release",
    volume: 0.42,
    playbackRate: 0.98,
  },
  anxious: {
    track: "/tracks/528hz_calm_breath.mp3",
    label: "528 Hz breath field • easing the mind back into clarity",
    volume: 0.4,
    playbackRate: 0.97,
  },
  overwhelmed: {
    track: "/tracks/alpha_relief_space.mp3",
    label: "Alpha clarity field • less noise, more inner spaciousness",
    volume: 0.33,
    playbackRate: 0.95,
  },
  tired: {
    track: "/tracks/theta_rest_ambient.mp3",
    label: "Theta dream field • deep rest, softness, cinematic drift",
    volume: 0.3,
    playbackRate: 0.94,
  },
  hopeful: {
    track: "/tracks/soft_strings_uplift.mp3",
    label: "Gentle uplift field • opening the chest with light and motion",
    volume: 0.36,
    playbackRate: 1.0,
  },
  neutral: {
    track: "/tracks/soft_ambient_room.mp3",
    label: "Ambient soul field • dreamy space for calm clarity",
    volume: 0.26,
    playbackRate: 0.95,
  },
};

const MOOD_TRACKS = Object.fromEntries(
  Object.entries(SONOTHERAPY_PROFILES).map(([mood, profile]) => [mood, profile.track]),
);

const MOOD_WAVE_LABELS = Object.fromEntries(
  Object.entries(SONOTHERAPY_PROFILES).map(([mood, profile]) => [mood, profile.label]),
);

const MOOD_MAP = {
  angry: ["angry", "mad", "furious", "annoyed", "irritated", "rage", "frustrated", "pissed", "upset"],
  sad: ["sad", "cry", "crying", "lonely", "alone", "hurt", "broken", "heartbreak", "depressed", "empty", "miss", "tears", "grief", "hopeless", "pain", "loss", "unloved", "worthless"],
  anxious: ["anxious", "anxiety", "panic", "scared", "worried", "nervous", "overthinking", "fear", "stress", "stressed", "tense", "restless"],
  overwhelmed: ["overwhelmed", "too much", "pressure", "burnout", "burnt out", "cant handle", "can't handle", "so many", "trapped", "caged"],
  tired: ["tired", "exhausted", "drained", "no energy", "sleepy", "fatigued", "worn out", "lazy"],
  hopeful: ["excited", "grateful", "hope", "hopeful", "happy", "joy", "glad", "love", "great", "amazing", "wonderful", "positive", "better", "relieved", "calm", "peaceful"],
};

const VOICE_PREVIEW_TEXT = "Hey, I'm here. Take this softly. We can move gently tonight.";
const CLEAN_LUNA_RETRY_MESSAGE = "LUNA's connection glitched for a bit. Try once more in a moment.";

const LANGUAGE_OPTIONS = [
  { code: "en-IN", label: "English" },
  { code: "hi-IN", label: "Hindi" },
  { code: "te-IN", label: "Telugu" },
  { code: "ta-IN", label: "Tamil" },
  { code: "kn-IN", label: "Kannada" },
];

function detectMoodFromText(text) {
  const lowered = text.toLowerCase();
  for (const [mood, keywords] of Object.entries(MOOD_MAP)) {
    if (keywords.some((keyword) => lowered.includes(keyword))) return mood;
  }
  return "neutral";
}

function buildLocalConnectionFallback(text, mood) {
  const compact = String(text || "").toLowerCase();

  if (mood === "sad" || /sad|hurt|cry|lonely|broken|empty/.test(compact)) {
    return "Ayy, I heard you. My server connection slipped, but I am still here with you. Tell me what hurt first, slowly.";
  }

  if (mood === "anxious" || /anxious|stress|panic|worried|overthinking/.test(compact)) {
    return "Ayy breathe, I got you. My server connection slipped for a moment, but stay with one small thought at a time.";
  }

  if (mood === "angry" || /angry|mad|frustrated|irritated/.test(compact)) {
    return "Oho, I heard the fire in that. My server connection slipped, but say it properly here. What happened?";
  }

  if (mood === "tired" || /tired|exhausted|drained|sleepy/.test(compact)) {
    return "Ayy, you sound worn out. My server connection slipped, but do not push yourself harder right now. Sit with me a second.";
  }

  return "Ayy, I heard you. My server connection slipped for a moment, but I am still here. Try once more, or tell me a little more.";
}

function stripForSpeech(raw) {
  return raw
    .replace(/[\u{1F000}-\u{1FFFF}]/gu, "")
    .replace(/[\u{2600}-\u{27BF}]/gu, "")
    .replace(/[\u{1F100}-\u{1F1FF}]/gu, "")
    .replace(/[\u{1F680}-\u{1F6FF}]/gu, "")
    .replace(/[\uFE00-\uFE0F]/g, "")
    .replace(/[\u200B-\u200D\uFEFF]/g, "")
    .replace(/[*_~`#>|\\]/g, "")
    .replace(/\s{2,}/g, " ")
    .trim();
}

function softenForSpeech(raw) {
  return stripForSpeech(raw)
    .replace(/\s*&\s*/g, " and ")
    .replace(/\s*\.\.\.\s*/g, " ... ")
    .replace(/\bI am\b/g, "I'm")
    .replace(/\bdo not\b/g, "don't")
    .replace(/\bcannot\b/g, "can't")
    .replace(/\bit is\b/g, "it's")
    .replace(/\bthat is\b/g, "that's")
    .replace(/\s{2,}/g, " ")
    .trim();
}

function splitSpeechSegments(text) {
  const segments = [];
  const matches = text.match(/[^,.;:!?]+[,.!?;:]*/g) ?? [];

  for (const match of matches) {
    const rawSegment = match.trim();
    if (!rawSegment) continue;

    const punctuationMatch = rawSegment.match(/[,.!?;:]+$/);
    const punctuation = punctuationMatch ? punctuationMatch[0] : "";
    const content = rawSegment.replace(/[,.!?;:]+$/, "").trim();
    if (!content) continue;

    let pauseMs = 35;
    if (punctuation.includes(",")) pauseMs = 90;
    if (punctuation.includes(";") || punctuation.includes(":")) pauseMs = 130;
    if (punctuation.includes(".")) pauseMs = 170;
    if (punctuation.includes("!")) pauseMs = 160;
    if (punctuation.includes("?")) pauseMs = 180;

    segments.push({ content, punctuation, pauseMs });
  }

  if (!segments.length && text.trim()) {
    segments.push({ content: text.trim(), punctuation: "", pauseMs: 35 });
  }

  return segments;
}

function makeTitle(text) {
  if (!text) return "Untitled whisper";
  const trimmed = text.trim();
  const fullStop = trimmed.indexOf(".");
  if (fullStop > 40 && fullStop < 140) return trimmed.slice(0, fullStop + 1);
  return trimmed.length <= 140 ? trimmed : `${trimmed.slice(0, 120).trimEnd()}...`;
}

function ignoreExpectedError(label, error) {
  if (!error) return;
  console.debug(label, error);
}

function scoreVoice(voice) {
  if (!voice) return -1;

  const name = `${voice.name || ""} ${voice.voiceURI || ""}`.toLowerCase();
  const lang = (voice.lang || "").toLowerCase();

  let score = 0;

  if (lang.startsWith("en-in")) score += 16;
  if (lang.startsWith("hi-in")) score += 12;
  if (lang.startsWith("en-gb")) score += 9;
  if (lang.startsWith("en-au")) score += 8;
  if (lang.startsWith("en-us")) score += 6;
  if (lang.startsWith("en")) score += 5;

  if (/female|woman|samantha|victoria|moira|ava|aria|jenny|zira|sonia|heera|veena|priya|kavya/i.test(name)) score += 12;
  if (/natural|neural|premium|enhanced|soft|warm|calm|gentle/i.test(name)) score += 7;
  if (/india|indian/i.test(name)) score += 8;
  if (/google|microsoft|apple/i.test(name)) score += 3;
  if (/male|david|mark|daniel|fred/i.test(name)) score -= 5;
  if (/robot|compact|espeak/i.test(name)) score -= 6;

  if (!voice.localService) score += 2;

  return score;
}

function getFallbackSpeechProfile(mood) {
  switch (mood) {
    case "sad":
      return { rate: 0.95, pitch: 0.96, volume: 0.98 };
    case "anxious":
      return { rate: 1.04, pitch: 1.01, volume: 1.0 };
    case "overwhelmed":
      return { rate: 1.02, pitch: 0.99, volume: 1.0 };
    case "angry":
      return { rate: 1.01, pitch: 0.94, volume: 1.0 };
    case "tired":
      return { rate: 0.92, pitch: 0.95, volume: 0.96 };
    case "hopeful":
      return { rate: 1.03, pitch: 1.06, volume: 1.0 };
    default:
      return { rate: 0.99, pitch: 1.0, volume: 1.0 };
  }
}

function getLanguageLabel(code) {
  return LANGUAGE_OPTIONS.find((option) => option.code === code)?.label || "English";
}

function personalizeLunaText(raw, userName) {
  if (!raw) return raw;
  const safeName = (userName || "You").trim() || "You";
  return String(raw)
    .replace(/\bSandy\b/gi, safeName)
    .replace(/\bSandhya\b/gi, safeName)
    .replace(/\bSandy's\b/gi, `${safeName}'s`);
}

function sanitizeLunaReplyText(raw) {
  const text = String(raw ?? "").trim();
  if (!text) return text;

  const lowered = text.toLowerCase();
  const looksLikeProviderError = (
    lowered.includes("unsupported parameter")
    || lowered.includes("invalid_request_error")
    || lowered.includes("content management policy")
    || lowered.includes("luna couldn't reach her azure brain")
    || lowered.includes("azure openai is missing on the backend")
    || (lowered.includes("max_completion_tokens") && lowered.includes("max_tokens"))
  );

  if ((lowered.startsWith("luna's connection glitched for a bit.") && text.includes("(")) || looksLikeProviderError) {
    return CLEAN_LUNA_RETRY_MESSAGE;
  }

  return text;
}

function createConversationStorageKey(userName) {
  const normalized = String(userName || "you").trim().toLowerCase().replace(/[^a-z0-9]+/g, "-");
  return `luna_chat_history:${normalized || "you"}`;
}

function createMessage(sender, text, extras = {}) {
  return {
    id: extras.id || `${sender}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    sender,
    text: sender === "luna" ? sanitizeLunaReplyText(text) : text,
    wisdomUsed: Array.isArray(extras.wisdomUsed) ? extras.wisdomUsed : [],
    explain: extras.explain && typeof extras.explain === "object" ? extras.explain : null,
  };
}

function toHistoryPayload(messages) {
  return messages
    .filter((message) => message?.sender && message?.text)
    .slice(-16)
    .map((message) => ({
      sender: message.sender,
      text: message.text,
    }));
}

function ChatUI({ userName = "You", embedded = false }) {
  const [messages, setMessages] = useState([
    createMessage("luna", "Hey, I'm here. What's on your mind tonight?"),
  ]);
  const [input, setInput] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [isOnline, setIsOnline] = useState(true);
  const [isListening, setIsListening] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [currentMood, setCurrentMood] = useState("neutral");
  const [waveLabel, setWaveLabel] = useState(MOOD_WAVE_LABELS.neutral);
  const [isAudioPlaying, setIsAudioPlaying] = useState(false);
  const [wisdomModal, setWisdomModal] = useState(null);
  const [whisperHistory, setWhisperHistory] = useState([]);
  const [showHistory, setShowHistory] = useState(false);
  const [showVoiceStudio, setShowVoiceStudio] = useState(false);
  const [voiceOptions, setVoiceOptions] = useState([]);
  const [selectedVoice, setSelectedVoice] = useState("");
  const [isLoadingVoices, setIsLoadingVoices] = useState(false);
  const [voicePreviewing, setVoicePreviewing] = useState("");
  const [voiceSaving, setVoiceSaving] = useState("");
  const [voiceSearch, setVoiceSearch] = useState("");
  const [voiceStudioError, setVoiceStudioError] = useState("");
  const [voiceListHint, setVoiceListHint] = useState("");
  const [voiceStudioStatus, setVoiceStudioStatus] = useState("");
  const [ttsStatus, setTtsStatus] = useState("idle");
  const [openWisdomMessageId, setOpenWisdomMessageId] = useState(null);
  const [bgmVolumeLevel, setBgmVolumeLevel] = useState(() => {
    if (typeof window === "undefined") return 0.9;
    const saved = Number(window.localStorage.getItem("luna_bgm_volume"));
    return Number.isFinite(saved) && saved >= 0 && saved <= 1 ? saved : 0.9;
  });
  const [voiceVolumeLevel, setVoiceVolumeLevel] = useState(() => {
    if (typeof window === "undefined") return 1;
    const saved = Number(window.localStorage.getItem("luna_voice_volume"));
    return Number.isFinite(saved) && saved >= 0 && saved <= 1 ? saved : 1;
  });
  const [selectedLanguage, setSelectedLanguage] = useState(() => {
    if (typeof window === "undefined") return "en-IN";
    const saved = window.localStorage.getItem("luna_language");
    return LANGUAGE_OPTIONS.some((option) => option.code === saved) ? saved : "en-IN";
  });
  const [selectedInputDeviceId, setSelectedInputDeviceId] = useState("");
  const [sessionMenuOpen, setSessionMenuOpen] = useState(false);

  const chatScrollRef = useRef(null);
  const bgmRef = useRef(null);
  const ttsRef = useRef(null);
  /** Normalized 0–1 mouth drive read by MoonScene ModelRig while Luna is speaking. */
  const lipSyncAmpRef = useRef(0);
  const webSpeechPulseRef = useRef(0);
  const ttsAudioCtxRef = useRef(null);
  const ttsAnalyserRef = useRef(null);
  const ttsAudioLinkedRef = useRef(false);
  const lipRafRef = useRef(null);
  const isSpeakingRef = useRef(false);
  /** When set, calling it completes the active `playAudioBlob` promise (needed for Stop / teardown). */
  const ttsPlaybackCompleteRef = useRef(null);
  const fadeRef = useRef(null);
  const synthRef = useRef(window.speechSynthesis);
  const voicesRef = useRef([]);
  const listeningRef = useRef(false);
  const recognitionRef = useRef(null);
  const azureRecognizerRef = useRef(null);
  const mediaRecorderRef = useRef(null);
  const mediaChunksRef = useRef([]);
  const mediaStreamRef = useRef(null);
  const voiceTranscriptRef = useRef("");
  const shouldAutoSendVoiceRef = useRef(false);
  const sendMessageRef = useRef(null);
  const voiceStudioFetchedRef = useRef(false);
  const loadedTrackRef = useRef(MOOD_TRACKS.neutral);
  const isPlayingRef = useRef(false);
  const currentMoodRef = useRef("neutral");
  const bgmVolumeRef = useRef(0.9);
  const voiceVolumeRef = useRef(1);
  const selectedLanguageRef = useRef("en-IN");
  const shouldStickToBottomRef = useRef(true);
  const pendingVoiceMoodHintRef = useRef(null);
  const conversationStorageKey = createConversationStorageKey(userName);

  const inferMoodFromVoiceTone = useCallback(async (blob) => {
    try {
      const AudioContextCtor = window.AudioContext || window.webkitAudioContext;
      if (!AudioContextCtor || !blob) return null;
      const ctx = new AudioContextCtor();
      const arrayBuffer = await blob.arrayBuffer();
      const decoded = await ctx.decodeAudioData(arrayBuffer.slice(0));
      const samples = decoded.getChannelData(0);
      if (!samples?.length) {
        await ctx.close().catch(() => {});
        return null;
      }

      let sumSq = 0;
      let zeroCrossings = 0;
      let previousSign = 0;
      const step = Math.max(1, Math.floor(samples.length / 24000));

      for (let index = 0; index < samples.length; index += step) {
        const sample = samples[index];
        sumSq += sample * sample;
        const sign = sample >= 0 ? 1 : -1;
        if (previousSign && sign !== previousSign) zeroCrossings += 1;
        previousSign = sign;
      }

      const sampleCount = Math.ceil(samples.length / step);
      const rms = Math.sqrt(sumSq / Math.max(1, sampleCount));
      const zcr = zeroCrossings / Math.max(1, sampleCount);
      await ctx.close().catch(() => {});

      if (rms > 0.14 && zcr < 0.085) return "angry";
      if (rms > 0.11 && zcr > 0.13) return "anxious";
      if (rms < 0.038) return "tired";
      if (rms < 0.06 && zcr < 0.075) return "sad";
      if (rms > 0.095 && zcr < 0.1) return "hopeful";
      return "neutral";
    } catch (error) {
      ignoreExpectedError("Voice tone inference skipped", error);
      return null;
    }
  }, []);

  const stopMicStream = useCallback(() => {
    const stream = mediaStreamRef.current;
    if (stream) {
      stream.getTracks().forEach((track) => track.stop());
    }
    mediaStreamRef.current = null;
  }, []);

  useEffect(() => {
    isPlayingRef.current = isAudioPlaying;
  }, [isAudioPlaying]);

  useEffect(() => {
    currentMoodRef.current = currentMood;
  }, [currentMood]);

  useEffect(() => {
    bgmVolumeRef.current = bgmVolumeLevel;
    window.localStorage.setItem("luna_bgm_volume", String(bgmVolumeLevel));
  }, [bgmVolumeLevel]);

  useEffect(() => {
    voiceVolumeRef.current = voiceVolumeLevel;
    window.localStorage.setItem("luna_voice_volume", String(voiceVolumeLevel));
    if (ttsRef.current) {
      ttsRef.current.volume = voiceVolumeLevel;
    }
  }, [voiceVolumeLevel]);

  useEffect(() => {
    isSpeakingRef.current = isSpeaking;
  }, [isSpeaking]);

  /** Drive lip-sync from TTS waveform (streaming MP3) or Web Speech pulses. */
  useEffect(() => {
    const stopLoop = () => {
      if (lipRafRef.current != null) {
        cancelAnimationFrame(lipRafRef.current);
        lipRafRef.current = null;
      }
      lipSyncAmpRef.current = 0;
      webSpeechPulseRef.current = 0;
    };

    if (!isSpeaking) {
      stopLoop();
      return undefined;
    }

    const td = new Uint8Array(2048);

    const tick = () => {
      const audio = ttsRef.current;
      const analyser = ttsAnalyserRef.current;

      let amp = 0;
      const durationKnown = !!(audio && Number.isFinite(audio.duration) && audio.duration > 0);
      const usingElementAudio =
        audio &&
        !!audio.src &&
        !audio.paused &&
        (durationKnown ? audio.currentTime < audio.duration : (audio.readyState ?? 0) >= 2);

      if (usingElementAudio && analyser) {
        analyser.getByteTimeDomainData(td);
        let sum = 0;
        for (let i = 0; i < td.length; i += 1) {
          const n = (td[i] - 128) / 128;
          sum += n * n;
        }
        const rms = Math.sqrt(sum / td.length);
        amp = Math.min(1, Math.max(0, (rms - 0.012) * 5.5));
      } else if (typeof window !== "undefined" && window.speechSynthesis && window.speechSynthesis.speaking) {
        webSpeechPulseRef.current *= 0.935;
        const wobble = 0.17 + Math.sin(performance.now() * 0.019) * 0.52;
        const base = Math.max(webSpeechPulseRef.current, Math.abs(wobble) * 0.48);
        amp = Math.min(1, base);
      }

      lipSyncAmpRef.current = Math.min(1, Math.max(0, amp));

      if (isSpeakingRef.current) {
        lipRafRef.current = requestAnimationFrame(tick);
      }
    };

    lipRafRef.current = requestAnimationFrame(tick);
    return stopLoop;
  }, [isSpeaking]);

  useEffect(() => {
    selectedLanguageRef.current = selectedLanguage;
    window.localStorage.setItem("luna_language", selectedLanguage);
  }, [selectedLanguage]);

  useEffect(() => {
    if (!sessionMenuOpen) return undefined;

    const handleKeyDown = (event) => {
      if (event.key === "Escape") setSessionMenuOpen(false);
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [sessionMenuOpen]);

  useEffect(() => {
    const container = chatScrollRef.current;
    if (!container) return;

    if (!shouldStickToBottomRef.current) return;

    const prefersReducedMotion = typeof window !== "undefined"
      && window.matchMedia
      && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const shouldAnimate = !prefersReducedMotion && messages.length < 80;

    container.scrollTo({
      top: container.scrollHeight,
      behavior: shouldAnimate ? "smooth" : "auto",
    });
  }, [messages, isSending]);

  useEffect(() => {
    const saved = localStorage.getItem("luna_whispers");
    if (!saved) return;

    try {
      setWhisperHistory(JSON.parse(saved));
    } catch (error) {
      ignoreExpectedError("Failed to parse whisper history", error);
    }
  }, []);

  useEffect(() => {
    localStorage.setItem("luna_whispers", JSON.stringify(whisperHistory));
  }, [whisperHistory]);

  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(conversationStorageKey);
      if (!raw) return;
      const parsed = JSON.parse(raw);
      if (!Array.isArray(parsed) || !parsed.length) return;
      const sanitized = parsed
        .filter((item) => item?.sender && item?.text)
        .map((item) => createMessage(item.sender, item.text, { id: item.id, wisdomUsed: item.wisdomUsed }));
      if (sanitized.length) {
        setMessages(sanitized);
      }
    } catch (error) {
      ignoreExpectedError("Failed to restore chat history", error);
    }
  }, [conversationStorageKey]);

  useEffect(() => {
    try {
      window.localStorage.setItem(conversationStorageKey, JSON.stringify(messages));
    } catch (error) {
      ignoreExpectedError("Failed to save chat history", error);
    }
  }, [conversationStorageKey, messages]);

  const refreshInputDevices = useCallback(async () => {
    if (!navigator.mediaDevices?.enumerateDevices) return;
    try {
      const devices = await navigator.mediaDevices.enumerateDevices();
      const microphones = devices.filter((device) => device.kind === "audioinput");
      setSelectedInputDeviceId((previous) => {
        if (previous && microphones.some((device) => device.deviceId === previous)) {
          return previous;
        }
        return microphones[0]?.deviceId || "";
      });
    } catch (error) {
      ignoreExpectedError("Microphone device list failed", error);
    }
  }, []);

  useEffect(() => {
    refreshInputDevices();
  }, [refreshInputDevices]);

  useEffect(() => {
    if (!showVoiceStudio) {
      voiceStudioFetchedRef.current = false;
      setVoiceListHint("");
      setVoiceOptions([]);
      setVoiceStudioError("");
      return;
    }

    if (voiceStudioFetchedRef.current) return;
    voiceStudioFetchedRef.current = true;

    const loadVoices = async () => {
      setIsLoadingVoices(true);
      setVoiceStudioError("");
      setVoiceListHint("");

      try {
        const response = await axios.get(`${API_BASE}/voices`);
        const data = response.data || {};
        const voices = Array.isArray(data.voices) ? data.voices : [];
        setVoiceOptions(voices);
        setSelectedVoice(data.selected_voice || "");
        if (!voices.length) {
          setVoiceListHint(
            data.detail
              ? String(data.detail)
              : "Azure returned no English voices. Check AZURE_SPEECH_KEY and AZURE_SPEECH_REGION on the backend.",
          );
        }
      } catch (error) {
        console.error("Voice list error:", error);
        setVoiceStudioError("Couldn't reach the backend for voices. Is InnerVoice_Jelly running on port 8000?");
      } finally {
        setIsLoadingVoices(false);
      }
    };

    loadVoices();
  }, [showVoiceStudio]);

  useEffect(() => {
    const synth = synthRef.current;
    if (!synth) return undefined;

    const loadVoices = () => {
      voicesRef.current = synth.getVoices();
    };

    loadVoices();
    if (typeof synth.addEventListener === "function") {
      synth.addEventListener("voiceschanged", loadVoices);
      return () => synth.removeEventListener("voiceschanged", loadVoices);
    }

    synth.onvoiceschanged = loadVoices;
    return () => {
      if (synth.onvoiceschanged === loadVoices) {
        synth.onvoiceschanged = null;
      }
    };
  }, []);

  useEffect(() => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) return undefined;

    const recognition = new SpeechRecognition();
    recognition.interimResults = true;
    recognition.continuous = false;

    recognition.onresult = (event) => {
      let transcript = "";
      let hasFinal = false;
      for (let index = 0; index < event.results.length; index += 1) {
        transcript += event.results[index][0].transcript;
        if (event.results[index].isFinal) hasFinal = true;
      }
      const cleanedTranscript = transcript.trim();
      voiceTranscriptRef.current = cleanedTranscript;
      setInput(cleanedTranscript);
      if (hasFinal) {
        shouldAutoSendVoiceRef.current = true;
      }
    };

    recognition.onerror = (event) => {
      if (event.error === "not-allowed") {
        alert("Microphone blocked!\n\n1. Click the lock icon in the address bar\n2. Set Microphone to Allow\n3. Refresh");
        listeningRef.current = false;
        shouldAutoSendVoiceRef.current = false;
        setIsListening(false);
        return;
      }

      if (event.error === "no-speech") {
        listeningRef.current = false;
        shouldAutoSendVoiceRef.current = false;
        setIsListening(false);
        return;
      }

      if (event.error !== "aborted" && event.error !== "no-speech") {
        console.warn("STT:", event.error);
      }
    };

    recognition.onend = () => {
      const transcriptToSend = voiceTranscriptRef.current.trim();
      const shouldAutoSend = shouldAutoSendVoiceRef.current;

      listeningRef.current = false;
      shouldAutoSendVoiceRef.current = false;
      setIsListening(false);

      if (shouldAutoSend && transcriptToSend) {
        sendMessageRef.current?.(transcriptToSend);
      }
    };

    recognitionRef.current = recognition;

    return () => {
      listeningRef.current = false;
      shouldAutoSendVoiceRef.current = false;
      try {
        recognition.abort();
      } catch (error) {
        ignoreExpectedError("Speech recognition cleanup skipped", error);
      }
    };
  }, []);

  useEffect(() => {
    if (!recognitionRef.current) return;
    recognitionRef.current.lang = selectedLanguage;
  }, [selectedLanguage]);

  useEffect(() => () => {
    try {
      azureRecognizerRef.current?.close();
    } catch (error) {
      ignoreExpectedError("Azure recognizer cleanup skipped", error);
    }
    azureRecognizerRef.current = null;
    try {
      mediaRecorderRef.current?.stop();
    } catch (error) {
      ignoreExpectedError("Media recorder cleanup skipped", error);
    }
    stopMicStream();
  }, [stopMicStream]);

  const linkTtsAnalyserIfNeeded = useCallback(() => {
    const audioElement = ttsRef.current;
    if (!audioElement || ttsAudioLinkedRef.current) return;

    try {
      const AudioContextCtor = window.AudioContext || window.webkitAudioContext;
      if (!AudioContextCtor) return;

      if (!ttsAudioCtxRef.current) {
        ttsAudioCtxRef.current = new AudioContextCtor();
      }

      const ctx = ttsAudioCtxRef.current;
      const src = ctx.createMediaElementSource(audioElement);
      const analyserNode = ctx.createAnalyser();
      analyserNode.fftSize = 2048;
      analyserNode.smoothingTimeConstant = 0.45;
      src.connect(analyserNode);
      analyserNode.connect(ctx.destination);

      ttsAnalyserRef.current = analyserNode;
      ttsAudioLinkedRef.current = true;
    } catch (err) {
      console.warn("[Luna] lip-sync: could not attach audio analyser:", err);
    }
  }, []);

  const playAudioBlob = useCallback((blob, nextStatus = "playing") => {
    const url = URL.createObjectURL(blob);

    return new Promise((resolve, reject) => {
      const audio = ttsRef.current;
      if (!audio) {
        URL.revokeObjectURL(url);
        reject(new Error("No audio element available"));
        return;
      }

      if (audio.src?.startsWith("blob:")) {
        URL.revokeObjectURL(audio.src);
      }

      audio.src = url;
      audio.volume = voiceVolumeRef.current;
      setTtsStatus(nextStatus);

      let settled = false;

      const releaseRef = () => {
        if (ttsPlaybackCompleteRef.current === finalizeSuccess) {
          ttsPlaybackCompleteRef.current = null;
        }
      };

      const finalizeSuccess = () => {
        if (settled) return;
        settled = true;
        releaseRef();
        URL.revokeObjectURL(url);
        audio.onended = null;
        audio.onerror = null;
        setTtsStatus("idle");
        resolve();
      };

      const finalizeError = (message) => {
        if (settled) return;
        settled = true;
        releaseRef();
        URL.revokeObjectURL(url);
        audio.onended = null;
        audio.onerror = null;
        reject(new Error(message));
      };

      ttsPlaybackCompleteRef.current = finalizeSuccess;

      audio.onended = finalizeSuccess;
      audio.onerror = (event) => {
        console.error("[TTS] playback:", event);
        setTtsStatus("error");
        finalizeError("Playback failed");
      };

      linkTtsAnalyserIfNeeded();
      void ttsAudioCtxRef.current?.resume?.().catch(() => {});

      audio.play().catch((error) => {
        console.error("[TTS] play() blocked:", error.message);
        finalizeError(error.message || "Play blocked");
      });
    });
  }, [linkTtsAnalyserIfNeeded]);

  const fetchTtsBlob = useCallback(async (cleanText, mood) => {
    const response = await fetch(`${API_BASE}/tts`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: cleanText, mood, language: selectedLanguageRef.current }),
    });

    if (!response.ok) {
      const errorText = await response.text().catch(() => response.statusText);
      console.error(`[TTS] ${response.status}:`, errorText);
      throw new Error(`${response.status}: ${errorText}`);
    }

    const provider = response.headers.get("X-Luna-TTS-Provider");
    const voiceId = response.headers.get("X-Luna-Voice-Id");
    if (provider) {
      console.info(`[TTS] Provider: ${provider}${voiceId ? ` | Voice: ${voiceId}` : ""}`);
    }
    if (voiceId) {
      setSelectedVoice(voiceId);
    }

    return response.blob();
  }, []);

  const speakWebSpeech = useCallback((cleanText) => new Promise((resolve) => {
    const synth = synthRef.current;
    if (!synth) {
      resolve();
      return;
    }

    synth.cancel();

    const segments = splitSpeechSegments(cleanText);

    const voices = voicesRef.current.length ? voicesRef.current : synth.getVoices();
    const sortedVoices = [...voices].sort((left, right) => scoreVoice(right) - scoreVoice(left));
    const bestVoice = sortedVoices[0];
    const profile = getFallbackSpeechProfile(currentMoodRef.current);

    if (bestVoice) {
      console.info(`[TTS fallback] Browser voice: ${bestVoice.name} (${bestVoice.lang})`);
    }

    let segmentIndex = 0;
    const speakNext = () => {
      if (segmentIndex >= segments.length) {
        resolve();
        return;
      }

      const segment = segments[segmentIndex];
      segmentIndex += 1;

      const utterance = new SpeechSynthesisUtterance(segment.content);
      if (bestVoice) utterance.voice = bestVoice;
      utterance.lang = bestVoice?.lang || selectedLanguageRef.current || "en-IN";
      utterance.rate = profile.rate;
      utterance.pitch = profile.pitch;
      utterance.volume = Math.max(0, Math.min(1, profile.volume * voiceVolumeRef.current));

      utterance.onboundary = (event) => {
        if (!event?.name || event.name === "word" || event.charIndex >= 0) {
          webSpeechPulseRef.current = Math.min(1, webSpeechPulseRef.current + 0.32);
        }
      };

      utterance.onend = () => {
        setTimeout(speakNext, segment.pauseMs);
      };
      utterance.onerror = (event) => {
        if (event.error !== "interrupted") {
          console.warn("TTS fallback:", event.error);
        }
        setTimeout(speakNext, segment.pauseMs);
      };

      synth.speak(utterance);
    };

    speakNext();
  }), []);

  const stopSpeaking = useCallback(() => {
    try {
      ttsPlaybackCompleteRef.current?.();
    } finally {
      ttsPlaybackCompleteRef.current = null;
    }

    const audio = ttsRef.current;
    if (audio) {
      audio.pause();
      if (audio.src?.startsWith("blob:")) {
        URL.revokeObjectURL(audio.src);
      }
      audio.src = "";
    }
    synthRef.current?.cancel();
    setIsSpeaking(false);
    setTtsStatus("idle");
  }, []);

  const filteredVoiceOptions = voiceOptions.filter((voice) => {
    const search = voiceSearch.trim().toLowerCase();
    if (!search) return true;

    const haystack = [
      voice.display_name,
      voice.local_name,
      voice.short_name,
      voice.locale,
      voice.gender,
      ...(voice.style_list || []),
    ].join(" ").toLowerCase();

    return haystack.includes(search);
  });

  const openVoiceStudio = () => {
    setShowVoiceStudio(true);
    setVoiceStudioError("");
    setVoiceStudioStatus("");
  };

  const previewVoice = async (voiceId) => {
    stopSpeaking();
    setVoicePreviewing(voiceId);
    setVoiceStudioError("");
    setVoiceStudioStatus("");
    setIsSpeaking(true);
    setTtsStatus("loading");

    try {
        const response = await fetch(`${API_BASE}/voices/preview`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            voice: voiceId,
            text: VOICE_PREVIEW_TEXT,
            mood: currentMoodRef.current,
            language: selectedLanguageRef.current,
          }),
        });

      if (!response.ok) {
        const errorText = await response.text().catch(() => response.statusText);
        throw new Error(errorText || "Preview failed");
      }

      const blob = await response.blob();
      await playAudioBlob(blob);
      setVoiceStudioStatus("Preview ready.");
    } catch (error) {
      console.error("Voice preview error:", error);
      setVoiceStudioError("Preview failed. Luna used the browser voice softly.");
      await speakWebSpeech(VOICE_PREVIEW_TEXT);
    } finally {
      setVoicePreviewing("");
      setIsSpeaking(false);
    }
  };

  const selectVoice = async (voiceId) => {
    setVoiceSaving(voiceId);
    setVoiceStudioError("");
    setVoiceStudioStatus("");

    try {
      const response = await axios.post(`${API_BASE}/voices/select`, { voice: voiceId });
      const savedVoice = response.data?.selected_voice || voiceId;
      setSelectedVoice(savedVoice);
      setVoiceOptions((previous) => previous.map((voice) => ({
        ...voice,
        selected: voice.short_name === savedVoice,
      })));
      setVoiceStudioStatus("Luna's voice was updated.");
    } catch (error) {
      console.error("Voice save error:", error);
      setVoiceStudioError("Couldn't save that voice right now.");
    } finally {
      setVoiceSaving("");
    }
  };

  const toggleMic = () => {
    const azureRecognizer = azureRecognizerRef.current;
    if (azureRecognizer) {
      stopAzureMicRecognition().then(() => {
        const transcript = voiceTranscriptRef.current.trim();
        if (transcript) {
          sendMessageRef.current?.(transcript);
        } else {
          setInput("");
        }
      });
      return;
    }

    const activeRecorder = mediaRecorderRef.current;
    if (activeRecorder && activeRecorder.state !== "inactive") {
      try {
        activeRecorder.stop();
      } catch (error) {
        ignoreExpectedError("Media recorder stop skipped", error);
      }
      return;
    }

    startAzureMicRecognition().catch((azureError) => {
      console.error("Azure mic start error:", azureError);

    const recognition = recognitionRef.current;
    if (recognition) {
      if (listeningRef.current) {
        listeningRef.current = false;
        if (voiceTranscriptRef.current.trim()) {
          shouldAutoSendVoiceRef.current = true;
        }
        setIsListening(false);
        try {
          recognition.stop();
        } catch (error) {
          ignoreExpectedError("Speech recognition stop skipped", error);
        }
        return;
      }

      voiceTranscriptRef.current = "";
      shouldAutoSendVoiceRef.current = false;
      setInput("");
      listeningRef.current = true;
      setIsListening(true);
      try {
        recognition.start();
      } catch (error) {
        if (!String(error?.message ?? "").includes("already started")) {
          listeningRef.current = false;
          setIsListening(false);
        }
      }
      return;
    }

    if (navigator.mediaDevices?.getUserMedia && typeof window.MediaRecorder !== "undefined") {
      startRecordedMic().catch((error) => {
        console.error("Recorder start error:", error);
        alert("Luna couldn't access the microphone. Allow mic permission and try again.");
        listeningRef.current = false;
        setIsListening(false);
        stopMicStream();
      });
      return;
    }

    alert("Speech recognition is not supported here. Use Google Chrome or Edge.");
    });
  };

  const fadeAudio = useCallback((targetVolume, onDone) => {
    const audio = bgmRef.current;
    if (!audio) {
      onDone?.();
      return;
    }

    if (fadeRef.current) clearInterval(fadeRef.current);

    const step = targetVolume > (audio.volume || 0) ? 0.05 : -0.05;
    fadeRef.current = setInterval(() => {
      const nextVolume = Math.max(0, Math.min(1, (audio.volume || 0) + step));
      audio.volume = nextVolume;

      if ((step > 0 && nextVolume >= targetVolume) || (step < 0 && nextVolume <= targetVolume)) {
        clearInterval(fadeRef.current);
        fadeRef.current = null;
        onDone?.();
      }
    }, 60);
  }, []);

  const getSonotherapyProfile = useCallback((mood) => SONOTHERAPY_PROFILES[mood] || SONOTHERAPY_PROFILES.neutral, []);

  const applySonotherapyProfile = useCallback((audio, mood) => {
    const profile = getSonotherapyProfile(mood);
    audio.playbackRate = profile.playbackRate;
    return profile;
  }, [getSonotherapyProfile]);

  const getBgmTargetVolume = useCallback((mood) => {
    const profile = getSonotherapyProfile(mood);
    return Math.max(0, Math.min(1, profile.volume * bgmVolumeRef.current));
  }, [getSonotherapyProfile]);

  const switchBGM = useCallback((mood) => {
    const audio = bgmRef.current;
    if (!audio) return;

    const profile = getSonotherapyProfile(mood);
    const nextTrack = profile.track;

    if (loadedTrackRef.current === nextTrack) {
      applySonotherapyProfile(audio, mood);
      if (isPlayingRef.current) fadeAudio(getBgmTargetVolume(mood));
      return;
    }

    loadedTrackRef.current = nextTrack;

    if (isPlayingRef.current) {
      fadeAudio(0, () => {
        audio.src = nextTrack;
        applySonotherapyProfile(audio, mood);
        audio.load();
        audio.volume = 0;
        audio.play().then(() => fadeAudio(getBgmTargetVolume(mood))).catch((error) => {
          ignoreExpectedError("BGM switch play blocked", error);
        });
      });
      return;
    }

    audio.src = nextTrack;
    applySonotherapyProfile(audio, mood);
    audio.load();
  }, [applySonotherapyProfile, fadeAudio, getBgmTargetVolume, getSonotherapyProfile]);

  const ensureBackgroundField = useCallback((mood) => {
    const audio = bgmRef.current;
    if (!audio || isPlayingRef.current) return;

    const profile = getSonotherapyProfile(mood);
    if (!audio.src || !audio.src.includes(profile.track)) {
      audio.src = profile.track;
      audio.load();
    }
    applySonotherapyProfile(audio, mood);
    audio.volume = 0;
    audio.play().then(() => {
      setIsAudioPlaying(true);
      fadeAudio(getBgmTargetVolume(mood));
    }).catch((error) => {
      ignoreExpectedError("BGM auto-start blocked", error);
    });
  }, [applySonotherapyProfile, fadeAudio, getBgmTargetVolume, getSonotherapyProfile]);

  const handleBGMToggle = () => {
    const audio = bgmRef.current;
    if (!audio) return;

    if (isPlayingRef.current) {
      fadeAudio(0, () => {
        audio.pause();
        setIsAudioPlaying(false);
      });
      return;
    }

    applySonotherapyProfile(audio, currentMoodRef.current);
    audio.volume = 0;
    audio.play().then(() => {
      setIsAudioPlaying(true);
      fadeAudio(getBgmTargetVolume(currentMoodRef.current));
    }).catch((error) => {
      ignoreExpectedError("BGM start blocked", error);
    });
  };

  useEffect(() => {
    const audio = bgmRef.current;
    if (!audio || !isPlayingRef.current) return;
    audio.volume = getBgmTargetVolume(currentMoodRef.current);
  }, [bgmVolumeLevel, getBgmTargetVolume]);

  const sendMessage = useCallback(async (rawInput, options = {}) => {
    const trimmed = String(rawInput || "").trim();
    if (!trimmed || isSending) return;

    if (listeningRef.current) {
      listeningRef.current = false;
      shouldAutoSendVoiceRef.current = false;
      setIsListening(false);
      try {
        recognitionRef.current?.stop();
      } catch (error) {
        ignoreExpectedError("Speech recognition send-stop skipped", error);
      }
    }

    voiceTranscriptRef.current = "";
    stopSpeaking();

    const voiceMoodHint = typeof options.voiceMoodHint === "string" ? options.voiceMoodHint : "";
    const detectedMood = voiceMoodHint || detectMoodFromText(trimmed);
    setCurrentMood(detectedMood);
    currentMoodRef.current = detectedMood;
    setWaveLabel(MOOD_WAVE_LABELS[detectedMood]);
    switchBGM(detectedMood);
    ensureBackgroundField(detectedMood);

    const userMessage = createMessage("sandy", trimmed);
    const nextHistory = [...messages, userMessage];
    setMessages(nextHistory);
    setInput("");
    setIsSending(true);
    setIsOnline(true);

    try {
      const response = await axios.post(`${API_BASE}/chat`, {
        message: trimmed,
        user_name: userName,
        language: selectedLanguageRef.current,
        history: toHistoryPayload(nextHistory),
        voice_mood_hint: voiceMoodHint || undefined,
      });
      const data = response.data || {};
      const lunaReply = personalizeLunaText(
        data.reply || "LUNA got a bit lost in the stars for a second.",
        userName,
      );
      const wisdomUsed = Array.isArray(data.wisdom_used) ? data.wisdom_used : [];
      const explain = data.explain && typeof data.explain === "object" ? data.explain : null;
      const backendMood = data.mood;

      if (backendMood && MOOD_TRACKS[backendMood]) {
        setCurrentMood(backendMood);
        currentMoodRef.current = backendMood;
        setWaveLabel(data.wave_label || MOOD_WAVE_LABELS[backendMood]);
        switchBGM(backendMood);
        ensureBackgroundField(backendMood);
      }

      const lunaClean = softenForSpeech(lunaReply);
      const lunaMessage = createMessage("luna", lunaReply, { wisdomUsed, explain });
      const ttsMoodKey = backendMood && MOOD_TRACKS[backendMood] ? backendMood : currentMoodRef.current;

      let audioBlob = null;
      setTtsStatus("loading");

      try {
        if (lunaClean) {
          audioBlob = await fetchTtsBlob(lunaClean, ttsMoodKey);
        }
      } catch (ttsPrefetchErr) {
        console.warn("[TTS] prefetch failed, will fall back:", ttsPrefetchErr);
      }

      setMessages((previous) => [...previous, lunaMessage]);
      setIsOnline(true);
      setIsSending(false);

      if (!lunaClean) {
        setTtsStatus("idle");
      } else {
        setIsSpeaking(true);
        try {
          if (audioBlob) {
            await playAudioBlob(audioBlob);
          } else {
            setTtsStatus("error");
            await speakWebSpeech(lunaClean);
          }
        } catch (ttsPlayErr) {
          console.warn("[TTS] playback failed, browser voice:", ttsPlayErr);
          try {
            setTtsStatus("error");
            await speakWebSpeech(lunaClean);
          } catch {
            setTtsStatus("idle");
          }
        } finally {
          setIsSpeaking(false);
          setTtsStatus("idle");
        }
      }
    } catch (error) {
      console.error("Chat error:", error);
      setIsOnline(false);
      const localReply = personalizeLunaText(
        buildLocalConnectionFallback(trimmed, currentMoodRef.current),
        userName,
      );
      setMessages((previous) => [
        ...previous,
        createMessage("luna", localReply),
      ]);
    } finally {
      setIsSending(false);
    }
  }, [
    ensureBackgroundField,
    fetchTtsBlob,
    isSending,
    messages,
    playAudioBlob,
    speakWebSpeech,
    stopSpeaking,
    switchBGM,
    userName,
  ]);

  useEffect(() => {
    sendMessageRef.current = sendMessage;
  }, [sendMessage]);

  const transcribeRecordedAudio = useCallback(async (blob) => {
    const formData = new FormData();
    const extension = blob.type.includes("ogg") ? "ogg" : blob.type.includes("wav") ? "wav" : "webm";
    formData.append("audio", blob, `luna-voice.${extension}`);

    const response = await fetch(`${API_BASE}/stt?language=${encodeURIComponent(selectedLanguageRef.current)}`, {
      method: "POST",
      body: formData,
    });

    if (!response.ok) {
      const errorText = await response.text().catch(() => response.statusText);
      throw new Error(errorText || "Speech transcription failed");
    }

    const data = await response.json();
    return String(data.text || "").trim();
  }, []);

  const startRecordedMic = useCallback(async () => {
    if (!navigator.mediaDevices?.getUserMedia || typeof window.MediaRecorder === "undefined") {
      throw new Error("Audio recording is not supported in this browser.");
    }

    const stream = await navigator.mediaDevices.getUserMedia({
      audio: selectedInputDeviceId ? { deviceId: { exact: selectedInputDeviceId } } : true,
    });
    const mimeType = [
      "audio/ogg;codecs=opus",
      "audio/webm;codecs=opus",
      "audio/webm",
      "audio/mp4",
    ].find((candidate) => window.MediaRecorder.isTypeSupported(candidate));

    const recorder = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream);
    mediaStreamRef.current = stream;
    mediaRecorderRef.current = recorder;
    mediaChunksRef.current = [];
    voiceTranscriptRef.current = "";
    shouldAutoSendVoiceRef.current = false;
    setInput("");
    listeningRef.current = true;
    setIsListening(true);

    recorder.ondataavailable = (event) => {
      if (event.data?.size) {
        mediaChunksRef.current.push(event.data);
      }
    };

    recorder.onerror = (event) => {
      console.warn("Recorder:", event.error);
      listeningRef.current = false;
      setIsListening(false);
      stopMicStream();
    };

    recorder.onstop = async () => {
      const chunks = [...mediaChunksRef.current];
      mediaChunksRef.current = [];
      mediaRecorderRef.current = null;
      listeningRef.current = false;
      setIsListening(false);
      stopMicStream();

      if (!chunks.length) return;

      const audioBlob = new Blob(chunks, { type: recorder.mimeType || "audio/webm" });
      setInput("Transcribing your voice...");

      try {
        const transcript = await transcribeRecordedAudio(audioBlob);
        if (!transcript) {
          setInput("");
          return;
        }

        voiceTranscriptRef.current = transcript;
        setInput(transcript);
        const inferredMood = await inferMoodFromVoiceTone(audioBlob);
        pendingVoiceMoodHintRef.current = inferredMood;
        await sendMessageRef.current?.(transcript, { voiceMoodHint: inferredMood || undefined });
        pendingVoiceMoodHintRef.current = null;
      } catch (error) {
        console.error("STT upload error:", error);
        setInput("");
        alert("Luna couldn't hear that clearly just now. Try once more.");
      }
    };

    recorder.start(250);
    await refreshInputDevices();
  }, [inferMoodFromVoiceTone, refreshInputDevices, selectedInputDeviceId, stopMicStream, transcribeRecordedAudio]);

  const stopAzureMicRecognition = useCallback(() => new Promise((resolve) => {
    const recognizer = azureRecognizerRef.current;
    if (!recognizer) {
      resolve();
      return;
    }

    listeningRef.current = false;
    setIsListening(false);

    recognizer.stopContinuousRecognitionAsync(
      () => {
        try {
          recognizer.close();
        } catch (error) {
          ignoreExpectedError("Azure recognizer close skipped", error);
        }
        azureRecognizerRef.current = null;
        resolve();
      },
      (error) => {
        console.error("Azure mic stop error:", error);
        try {
          recognizer.close();
        } catch (closeError) {
          ignoreExpectedError("Azure recognizer close skipped", closeError);
        }
        azureRecognizerRef.current = null;
        resolve();
      },
    );
  }), []);

  const startAzureMicRecognition = useCallback(async () => {
    const tokenResponse = await axios.get(`${API_BASE}/speech/token`);
    const token = tokenResponse.data?.token;
    const region = tokenResponse.data?.region;
    if (!token || !region) {
      throw new Error("Missing Azure speech token");
    }

    const speechConfig = SpeechSDK.SpeechConfig.fromAuthorizationToken(token, region);
    speechConfig.speechRecognitionLanguage = selectedLanguageRef.current;
    speechConfig.setProperty(SpeechSDK.PropertyId.SpeechServiceConnection_InitialSilenceTimeoutMs, "8000");
    speechConfig.setProperty(SpeechSDK.PropertyId.SpeechServiceConnection_EndSilenceTimeoutMs, "1500");
    const audioConfig = selectedInputDeviceId
      ? SpeechSDK.AudioConfig.fromMicrophoneInput(selectedInputDeviceId)
      : SpeechSDK.AudioConfig.fromDefaultMicrophoneInput();
    const recognizer = new SpeechSDK.SpeechRecognizer(speechConfig, audioConfig);

    azureRecognizerRef.current = recognizer;
    voiceTranscriptRef.current = "";
    shouldAutoSendVoiceRef.current = false;
    setInput("");
    listeningRef.current = true;
    setIsListening(true);

    recognizer.recognizing = (_, event) => {
      const partial = String(event.result?.text || "").trim();
      if (partial) {
        setInput(partial);
      }
    };

    recognizer.recognized = (_, event) => {
      if (event.result?.reason !== SpeechSDK.ResultReason.RecognizedSpeech) return;
      const spoken = String(event.result.text || "").trim();
      if (!spoken) return;
      voiceTranscriptRef.current = `${voiceTranscriptRef.current} ${spoken}`.trim();
      setInput(voiceTranscriptRef.current);
    };

    recognizer.canceled = (_, event) => {
      console.warn("Azure mic canceled:", event.errorDetails || event.reason);
      listeningRef.current = false;
      setIsListening(false);
    };

    recognizer.sessionStopped = () => {
      listeningRef.current = false;
      setIsListening(false);
    };

    await new Promise((resolve, reject) => {
      recognizer.startContinuousRecognitionAsync(resolve, reject);
    });
  }, [selectedInputDeviceId]);

  const handleSend = async () => {
    await sendMessage(input, { voiceMoodHint: pendingVoiceMoodHintRef.current || undefined });
    pendingVoiceMoodHintRef.current = null;
  };

  const handleKeyDown = (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      handleSend();
    }
  };

  const fetchWisdom = async () => {
    try {
      const response = await axios.get(`${API_BASE}/wisdom`);
      const data = response.data || {};
      const entry = {
        id: Date.now(),
        text: data.text || "The ancestors are quiet for a moment...",
        source: data.source || "Ancient global wisdom",
        index: data.index || 0,
        total: data.total || 616,
        createdAt: new Date().toISOString(),
      };
      setWisdomModal(entry);
      setWhisperHistory((previous) => [entry, ...previous]);
    } catch (error) {
      console.error("Wisdom fetch failed:", API_BASE, error);
      ignoreExpectedError("Wisdom fetch failed", error);
      setWisdomModal({
        id: Date.now(),
        text: [
          "This wisdom request failed because the Luna API isn’t reachable.",
          "",
          "Target:",
          `${API_BASE}/wisdom`,
          "",
          import.meta.env.DEV
            ? "Dev mode uses Vite: anything under …/luna-backend is proxied to http://127.0.0.1:8000. If nothing listens on 8000, every feature (chat, voices, wisdom) fails."
            : "Set VITE_API_BASE_URL to your deployed API URL, or serve the backend on the same host as this page.",
          "",
          "Start the API (pick one):",
          "• From repo root, run: run-luna-local.cmd",
          "• Or: cd InnerVoice_Jelly → python -m uvicorn backend:app --reload --host 127.0.0.1 --port 8000",
          "",
          ...(import.meta.env.DEV && typeof window !== "undefined"
            ? [`Ping in a new tab: ${window.location.origin}/luna-backend/health → should say "ok".`]
            : []),
        ].join("\n"),
        source: "Connection",
        index: 0,
        total: 0,
        createdAt: new Date().toISOString(),
      });
    }
  };

  /** Inline TTS status near controls: only surfaced on failure (quiet path during load / play). */
  const ttsLabel = () => {
    if (ttsStatus === "loading" || ttsStatus === "playing") return null;
    if (ttsStatus === "error") return "Soft browser voice";
    return null;
  };

  const activeMoonLine = [...messages].reverse().find((message) => message.sender === "luna")?.text || "";

  return (
    <div className={`app-root${embedded ? " app-root-embedded" : ""}`}>
      <div className="luna-layout">
        <div className="left-panel">
          <div className={`moon-card${isSpeaking ? " moon-card-speaking" : ""}`}>
            <MoonScene mood={currentMood} isSpeaking={isSpeaking} lipSyncAmpRef={lipSyncAmpRef} activeText={activeMoonLine} />
          </div>
        </div>

        <div className="right-panel">
          <div className="luna-session-shell">
            <header className="luna-session-bar">
              <div className="luna-session-bar-main">
                <div className="luna-name-row">
                  <span className="luna-name">LUNA</span>
                  <span className="status-dot-wrapper">
                    <span className={`status-dot ${isOnline ? "status-online" : "status-offline"}`} />
                    <span className="status-label">{isOnline ? "online" : "offline"}</span>
                  </span>
                </div>
                <p className="luna-subtitle-compact">
                  Emotional companion · voice · wisdom · sonotherapy
                </p>
              </div>

              <button
                type="button"
                className={`luna-session-menu-trigger${sessionMenuOpen ? " luna-session-menu-trigger--open" : ""}`}
                aria-expanded={sessionMenuOpen}
                aria-controls="luna-session-drawer"
                aria-label={sessionMenuOpen ? "Close session controls" : "Open session controls"}
                onClick={() => setSessionMenuOpen((open) => !open)}
                title={sessionMenuOpen ? "Close session panel" : "Session controls"}
              >
                <span className="luna-session-menu-dots" aria-hidden="true">
                  <span /><span /><span />
                </span>
              </button>
            </header>

            <audio ref={bgmRef} src={MOOD_TRACKS.neutral} loop preload="auto" />
            <audio ref={ttsRef} preload="none" />
          </div>

          <main className="chat-card">
            <div
              ref={chatScrollRef}
              className="chat-scroll"
              onScroll={(event) => {
                const node = event.currentTarget;
                const distanceFromBottom = node.scrollHeight - node.scrollTop - node.clientHeight;
                shouldStickToBottomRef.current = distanceFromBottom < 56;
              }}
            >
              {messages.map((message) => (
                <div key={message.id} className={`chat-row ${message.sender === "luna" ? "chat-row-luna" : "chat-row-sandy"}`}>
                  <div className={`chat-message-shell ${message.sender === "luna" ? "chat-message-shell-luna" : "chat-message-shell-sandy"}`}>
                  {message.sender === "luna" ? (
                  <>
                  <button
                    type="button"
                    className={`chat-bubble bubble-luna${message.wisdomUsed?.length > 0 ? " bubble-luna-interactive" : ""}${openWisdomMessageId === message.id ? " bubble-luna-open" : ""}`}
                    onClick={() => {
                      if (!message.wisdomUsed?.length) return;
                      setOpenWisdomMessageId((current) => (current === message.id ? null : message.id));
                    }}
                  >
                    <div className="bubble-header">{message.sender === "luna" ? "LUNA" : userName}</div>
                    <div className={`bubble-face bubble-face-reply${openWisdomMessageId === message.id ? " bubble-face-hidden" : ""}`}>
                      <div className="bubble-text">{message.text}</div>
                    </div>
                    {message.wisdomUsed?.length > 0 && (
                      <div className={`bubble-face bubble-face-wisdom${openWisdomMessageId === message.id ? " bubble-face-visible" : ""}`}>
                        <div className="wisdom-inline-kicker">Wisdom thread</div>
                        {message.wisdomUsed.map((thread) => (
                          <div key={thread} className="wisdom-inline-line">{thread}</div>
                        ))}
                      </div>
                    )}
                  </button>
                  </>
                  ) : (
                  <div className="chat-bubble bubble-sandy">
                    <div className="bubble-header">{userName}</div>
                    <div className="bubble-text">{message.text}</div>
                  </div>
                  )}
                  </div>
                </div>
              ))}

              {isSending && (
                <div className="chat-row chat-row-luna">
                  <div className="chat-bubble bubble-luna typing-bubble">
                    <div className="bubble-header">LUNA</div>
                    <div className="typing-dots"><span /><span /><span /></div>
                  </div>
                </div>
              )}
            </div>

            <div className="chat-input-row">
              <button
                type="button"
                className={`mic-btn${isListening ? " active" : ""}`}
                onClick={toggleMic}
                aria-label={isListening ? "Stop voice input" : "Start voice input"}
                title={isListening ? "Stop voice input" : "Start voice input"}
              >
                <img className="mic-btn-image" src="/luna-mic.svg" alt="" aria-hidden="true" />
                <span className="mic-btn-status" aria-hidden="true" />
              </button>
              <textarea
                className="chat-input"
                placeholder={isListening ? "Listening... speak now" : "Type what's on your heart..."}
                value={input}
                onChange={(event) => setInput(event.target.value)}
                onKeyDown={handleKeyDown}
                rows={1}
              />
              <button
                type="button"
                className="chat-send-btn"
                onClick={handleSend}
                disabled={isSending || !input.trim()}
              >
                {isSending ? "..." : "Send"}
              </button>
            </div>
          </main>

          {sessionMenuOpen && (
            <div className="luna-session-layer">
              <div
                className="luna-session-scrim"
                aria-hidden="true"
                onClick={() => setSessionMenuOpen(false)}
              />
              <aside
                id="luna-session-drawer"
                className="luna-session-drawer"
                role="dialog"
                aria-modal="true"
                aria-label="Session controls"
              >
                <div className="luna-session-drawer-head">
                  <span className="luna-session-drawer-kicker">Session</span>
                  <button
                    type="button"
                    className="luna-session-drawer-done"
                    onClick={() => setSessionMenuOpen(false)}
                  >
                    Done
                  </button>
                </div>

                <div className="luna-session-section luna-session-glass">
                  <p className="luna-session-intro">
                    An emotional companion shaped by ancient wisdom, voice, and sonotherapy.
                  </p>
                </div>

                <div className="luna-session-section luna-session-glass">
                  <div className="luna-session-section-label">Ambient</div>
                  <div
                    role="button"
                    tabIndex={0}
                    className="brain-card brain-card--session"
                    onClick={handleBGMToggle}
                    onKeyDown={(event) => {
                      if (event.key === "Enter" || event.key === " ") {
                        event.preventDefault();
                        handleBGMToggle();
                      }
                    }}
                  >
                    <div className="brain-session-top">
                      <span className="brain-title">Sonotherapy</span>
                      <span className="brain-toggle">{isAudioPlaying ? "Pause" : "Play"}</span>
                    </div>
                    <div className="brain-session-meta">
                      <p className="brain-meta-line">
                        <span className="brain-meta-k">Mood</span>
                        <span className="brain-mood-value">{currentMood}</span>
                      </p>
                      <p className="brain-meta-line brain-meta-long">{waveLabel}</p>
                      <p className="brain-meta-line">
                        <span className="brain-meta-k">Language</span>
                        <span>{getLanguageLabel(selectedLanguage)}</span>
                      </p>
                    </div>
                  </div>
                </div>

                <div className="luna-session-section luna-session-glass">
                  <div className="luna-session-section-label">Tools</div>
                  <div className="wisdom-buttons-row luna-session-actions">
                    <button
                      type="button"
                      className="history-button"
                      onClick={() => {
                        setSessionMenuOpen(false);
                        openVoiceStudio();
                      }}
                    >
                      Voice studio
                    </button>
                    <button
                      type="button"
                      className="wisdom-button"
                      onClick={() => {
                        setSessionMenuOpen(false);
                        fetchWisdom();
                      }}
                    >
                      Wisdom cookie
                    </button>
                    <button
                      type="button"
                      className="history-button"
                      onClick={() => {
                        setSessionMenuOpen(false);
                        setShowHistory(true);
                      }}
                    >
                      Whisper history
                    </button>
                    <label className="history-button language-chip luna-session-language-chip">
                      <span>Language</span>
                      <select
                        value={selectedLanguage}
                        onChange={(event) => setSelectedLanguage(event.target.value)}
                        className="language-select"
                      >
                        {LANGUAGE_OPTIONS.map((option) => (
                          <option key={option.code} value={option.code}>{option.label}</option>
                        ))}
                      </select>
                    </label>
                  </div>
                </div>

                <div className="luna-session-section luna-session-glass">
                  <div className="luna-session-section-label">Volume</div>
                  <div className="sound-controls sound-controls-session">
                    <label className="sound-control sound-control-block">
                      <span className="sound-control-label">BGM bed</span>
                      <div className="sound-control-row">
                        <input
                          className="sound-slider sound-slider-accent-cool"
                          type="range"
                          min="0"
                          max="100"
                          value={Math.round(bgmVolumeLevel * 100)}
                          onChange={(event) => setBgmVolumeLevel(Number(event.target.value) / 100)}
                        />
                        <span className="sound-value">{Math.round(bgmVolumeLevel * 100)}%</span>
                      </div>
                    </label>
                    <label className="sound-control sound-control-block">
                      <span className="sound-control-label">Luna voice</span>
                      <div className="sound-control-row">
                        <input
                          className="sound-slider sound-slider-accent-warm"
                          type="range"
                          min="0"
                          max="100"
                          value={Math.round(voiceVolumeLevel * 100)}
                          onChange={(event) => setVoiceVolumeLevel(Number(event.target.value) / 100)}
                        />
                        <span className="sound-value">{Math.round(voiceVolumeLevel * 100)}%</span>
                      </div>
                    </label>
                  </div>
                </div>

                {(isSpeaking || ttsLabel()) && (
                  <div className="luna-session-section luna-session-glass">
                    <div className="luna-session-section-label">Playback</div>
                    <div className="luna-session-playback-row">
                      {isSpeaking && (
                        <button type="button" className="luna-session-stop-btn" onClick={stopSpeaking}>
                          Stop voice
                        </button>
                      )}
                      {ttsLabel() && (
                        <span className={`luna-session-tts-hint ${ttsStatus === "error" ? "luna-session-tts-hint-error" : ""}`}>
                          {ttsLabel()}
                        </span>
                      )}
                    </div>
                  </div>
                )}

                {selectedVoice && (
                  <div className="voice-selected-pill voice-selected-pill-session">
                    Luna voice: <span>{selectedVoice}</span>
                  </div>
                )}
              </aside>
            </div>
          )}
        </div>
      </div>

      {wisdomModal && (
        <div className="wisdom-modal-overlay" onClick={() => setWisdomModal(null)}>
          <div className="wisdom-modal" onClick={(event) => event.stopPropagation()}>
            <div className="wisdom-modal-header">
              <div className="wisdom-modal-title">Ancient wisdom whisper</div>
              <button className="wisdom-modal-close" onClick={() => setWisdomModal(null)}>×</button>
            </div>
            <div className="wisdom-modal-body">
              <div className="wisdom-modal-text">{wisdomModal.text}</div>
            </div>
            <div className="wisdom-modal-footer">
              <span className="wisdom-source">{wisdomModal.source}</span>
              <span className="wisdom-count">Whisper {wisdomModal.index} / {wisdomModal.total}</span>
            </div>
          </div>
        </div>
      )}

      {showHistory && (
        <div className="history-modal-overlay" onClick={() => setShowHistory(false)}>
          <div className="history-modal" onClick={(event) => event.stopPropagation()}>
            <div className="history-modal-header">
              <div className="history-modal-title">Global whisper map</div>
              <button className="history-modal-close" onClick={() => setShowHistory(false)}>×</button>
            </div>
            {whisperHistory.length === 0 ? (
              <div className="history-empty-state">
                <p>No whispers unlocked yet.</p>
                <p>Tap "Wisdom cookie" to open your first ancient doorway.</p>
              </div>
            ) : (
              <div className="history-modal-body history-only-text">
                <div className="history-timeline">
                  {whisperHistory.map((whisper) => (
                    <div key={whisper.id} className="history-timeline-item">
                      <div className="timeline-bullet" />
                      <div className="timeline-content">
                        <div className="timeline-title">{makeTitle(whisper.text)}</div>
                        <div className="timeline-meta">
                          {whisper.source || "Unknown origin"} • Whisper {whisper.index} / {whisper.total || 616}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}
      {showVoiceStudio && (
        <div className="history-modal-overlay" onClick={() => setShowVoiceStudio(false)}>
          <div className="voice-modal" onClick={(event) => event.stopPropagation()}>
            <div className="history-modal-header">
              <div className="history-modal-title">Luna voice studio</div>
              <button className="history-modal-close" onClick={() => setShowVoiceStudio(false)}>×</button>
            </div>

            <div className="voice-toolbar">
              <input
                className="voice-search"
                placeholder="Search by name, locale, or style"
                value={voiceSearch}
                onChange={(event) => setVoiceSearch(event.target.value)}
              />
              <div className="voice-preview-note">{VOICE_PREVIEW_TEXT}</div>
            </div>

            {voiceStudioError && <div className="voice-status voice-status-error">{voiceStudioError}</div>}
            {!voiceStudioError && voiceStudioStatus && (
              <div className="voice-status">{voiceStudioStatus}</div>
            )}

            {isLoadingVoices ? (
              <div className="history-empty-state">
                <p>Loading Azure voices...</p>
              </div>
            ) : !voiceOptions.length && !voiceStudioError ? (
              <div className="history-empty-state">
                <p>{voiceListHint || "No voices available from the server."}</p>
                <p className="voice-preview-note">
                  Add <strong>AZURE_SPEECH_KEY</strong> and <strong>AZURE_SPEECH_REGION</strong> to InnerVoice Jelly
                  (.env), restart the API, then open Voice studio again.
                </p>
              </div>
            ) : (
              <div className="voice-grid">
                {filteredVoiceOptions.map((voice) => (
                  <div
                    key={voice.short_name}
                    className={`voice-card${voice.short_name === selectedVoice ? " voice-card-selected" : ""}`}
                  >
                    <div className="voice-card-top">
                      <div>
                        <div className="voice-name">{voice.display_name}</div>
                        <div className="voice-meta">{voice.short_name}</div>
                      </div>
                      {voice.short_name === selectedVoice && <span className="voice-badge">Current</span>}
                    </div>
                    <div className="voice-meta">{voice.locale} • {voice.gender || "Unknown"}</div>
                    {!!voice.style_list?.length && (
                      <div className="voice-style-list">{voice.style_list.slice(0, 4).join(" • ")}</div>
                    )}
                    <div className="voice-card-actions">
                      <button
                        type="button"
                        className="history-button voice-action-button"
                        onClick={() => previewVoice(voice.short_name)}
                        disabled={voicePreviewing === voice.short_name}
                      >
                        {voicePreviewing === voice.short_name ? "Previewing..." : "Preview"}
                      </button>
                      <button
                        type="button"
                        className="wisdom-button voice-action-button"
                        onClick={() => selectVoice(voice.short_name)}
                        disabled={voiceSaving === voice.short_name}
                      >
                        {voiceSaving === voice.short_name ? "Saving..." : "Use this"}
                      </button>
                    </div>
                  </div>
                ))}
                {!filteredVoiceOptions.length && (
                  <div className="history-empty-state">
                    <p>No voices matched that search.</p>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default ChatUI;
