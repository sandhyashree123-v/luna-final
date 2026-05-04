import React, { useEffect, useMemo, useRef, useState } from "react";
import { API_BASE } from "./apiBase";

function createDiaryStorageKey(seed) {
  const normalized = String(seed || "guest")
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-");

  return `luna_diary_entries:${normalized || "guest"}`;
}

function formatEntryDate(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Just now";

  return new Intl.DateTimeFormat("en-IN", {
    dateStyle: "full",
  }).format(date);
}

function createAutoEntryId(value) {
  return `luna-auto-story:${value || "today"}`;
}

function splitStoryParagraphs(text) {
  return String(text || "")
    .split(/\n{2,}/)
    .map((segment) => segment.trim())
    .filter(Boolean);
}

function storyToAutoEntry(data) {
  const story = String(data?.story || "").trim();
  if (!story) return null;

  const diaryDate = String(data?.date || new Date().toISOString().slice(0, 10));
  return {
    id: createAutoEntryId(diaryDate),
    title: data?.title?.trim() || "Luna's note for today",
    body: story,
    createdAt: `${diaryDate}T12:00:00`,
    updatedAt: data?.generated_at || new Date().toISOString(),
    kind: "luna-auto",
    sourceCount: Number(data?.entry_count || 0),
  };
}

function sortDiaryEntries(entries) {
  return [...entries].sort((a, b) => {
    const bTime = new Date(b.createdAt || 0).getTime();
    const aTime = new Date(a.createdAt || 0).getTime();
    return (Number.isNaN(bTime) ? 0 : bTime) - (Number.isNaN(aTime) ? 0 : aTime);
  });
}

export default function DiaryTab({
  userName = "Choose account",
  storageSeed = "guest",
  accounts = [],
  selectedAccountName = "",
  onAccountChange,
}) {
  const storageKey = useMemo(() => createDiaryStorageKey(storageSeed), [storageSeed]);
  const hasAccount = userName !== "Choose account";
  const [entries, setEntries] = useState([]);
  const [status, setStatus] = useState("");
  const [isGeneratingStory, setIsGeneratingStory] = useState(false);
  const [pageIndex, setPageIndex] = useState(0);
  const [turnDirection, setTurnDirection] = useState("idle");
  const skipNextLocalSaveRef = useRef(true);

  const sortedEntries = useMemo(() => sortDiaryEntries(entries), [entries]);
  const activeEntry = sortedEntries[pageIndex] || null;
  const activeParagraphs = activeEntry ? splitStoryParagraphs(activeEntry.body).slice(0, 5) : [];
  const canGoPrevious = pageIndex > 0;
  const canGoNext = pageIndex < sortedEntries.length - 1;

  useEffect(() => {
    skipNextLocalSaveRef.current = true;
    setPageIndex(0);
    setTurnDirection("idle");
    setStatus("");

    try {
      const saved = window.localStorage.getItem(storageKey);
      if (!saved) {
        setEntries([]);
        return;
      }

      const parsed = JSON.parse(saved);
      setEntries(Array.isArray(parsed) ? parsed : []);
    } catch {
      setEntries([]);
    }
  }, [storageKey]);

  useEffect(() => {
    if (skipNextLocalSaveRef.current) {
      skipNextLocalSaveRef.current = false;
      return;
    }

    try {
      window.localStorage.setItem(storageKey, JSON.stringify(entries));
    } catch {
      setStatus("Luna couldn't save this diary update locally.");
    }
  }, [entries, storageKey]);

  useEffect(() => {
    if (!hasAccount) return undefined;

    let cancelled = false;
    const loadLunaStory = async () => {
      setIsGeneratingStory(true);

      try {
        const response = await fetch(
          `${API_BASE}/diary/stories?user_name=${encodeURIComponent(userName)}&language=en-IN&limit_days=30`,
        );
        if (!response.ok) {
          throw new Error(`Diary story request failed with ${response.status}`);
        }

        const data = await response.json();
        if (cancelled) return;

        const autoEntries = (Array.isArray(data?.stories) ? data.stories : [])
          .map(storyToAutoEntry)
          .filter(Boolean);
        if (!autoEntries.length) return;

        setEntries((current) => {
          const autoIds = new Set(autoEntries.map((entry) => entry.id));
          const withoutSameAuto = current.filter((entry) => !autoIds.has(entry.id));
          return [...autoEntries, ...withoutSameAuto];
        });
      } catch {
        if (!cancelled) {
          try {
            const fallbackResponse = await fetch(
              `${API_BASE}/diary/story?user_name=${encodeURIComponent(userName)}&language=en-IN`,
            );
            if (!fallbackResponse.ok) throw new Error("Diary story fallback failed");
            const fallbackData = await fallbackResponse.json();
            const autoEntry = storyToAutoEntry(fallbackData);
            if (cancelled || !autoEntry) return;

            setEntries((current) => {
              const withoutSameAuto = current.filter((entry) => entry.id !== autoEntry.id);
              return [autoEntry, ...withoutSameAuto];
            });
          } catch {
            if (!cancelled) {
              setStatus((current) => current || "Luna couldn't shape this diary right now.");
            }
          }
        }
      } finally {
        if (!cancelled) {
          setIsGeneratingStory(false);
        }
      }
    };

    loadLunaStory();
    return () => {
      cancelled = true;
    };
  }, [hasAccount, userName, storageKey]);

  const goToPage = (nextIndex, direction) => {
    if (nextIndex < 0 || nextIndex >= sortedEntries.length) return;
    setTurnDirection(direction);
    setPageIndex(nextIndex);
  };

  return (
    <div className="diary-shell diary-book-shell">
      <div className="diary-hero-card diary-reader-toolbar">
        <div className="diary-toolbar-title">
          <div className="section-kicker">Diary</div>
          <strong>{activeEntry ? formatEntryDate(activeEntry.createdAt) : "Daily memory book"}</strong>
        </div>

        <div className="diary-reader-controls">
          <label className="diary-account-field">
            <span>Account</span>
            <select
              className="diary-account-select"
              value={selectedAccountName}
              disabled={!accounts.length}
              onChange={(event) => {
                if (typeof onAccountChange === "function") {
                  onAccountChange(event.target.value);
                }
              }}
            >
              {accounts.length ? (
                accounts.map((account) => (
                  <option key={account.name} value={account.name}>
                    {account.name}
                  </option>
                ))
              ) : (
                <option value="">No accounts yet</option>
              )}
            </select>
          </label>

          <div className="diary-stats diary-reader-stats">
            <div className="diary-stat-card">
              <span className="diary-stat-label">Pages</span>
              <strong>{sortedEntries.length}</strong>
            </div>
          </div>
        </div>
      </div>

      <section className="diary-book-stage" aria-label="Luna diary book">
        <div
          key={activeEntry?.id || "empty-diary-book"}
          className={`diary-book ${turnDirection === "next" ? "diary-book-turn-next" : ""} ${turnDirection === "previous" ? "diary-book-turn-previous" : ""}`}
        >
          <div className={`diary-turn-sheet ${turnDirection === "next" ? "diary-turn-sheet-next" : ""} ${turnDirection === "previous" ? "diary-turn-sheet-previous" : ""}`} aria-hidden="true" />
          <div className="diary-book-spine" aria-hidden="true" />
          <article className="diary-book-page diary-book-page-left">
            <div className="diary-page-kicker">One day memory</div>
            <h3>{activeEntry?.title || "No diary pages yet"}</h3>
            <div className="diary-page-date">
              {activeEntry ? formatEntryDate(activeEntry.createdAt) : "Start a chat and Luna will write the first page."}
            </div>
            <div className="diary-page-meta">
              {activeEntry?.sourceCount ? `${activeEntry.sourceCount} chat moments` : isGeneratingStory ? "Refreshing from today's chats" : "Auto-written from chat"}
            </div>
            {status && <div className="diary-page-status">{status}</div>}
          </article>

          <article className="diary-book-page diary-book-page-right">
            {activeEntry ? (
              <div className="diary-story-body diary-page-story">
                {activeParagraphs.map((paragraph, index) => (
                  <p key={`${activeEntry.id}-p-${index}`}>{paragraph}</p>
                ))}
              </div>
            ) : (
              <div className="diary-empty-state">
                {hasAccount
                  ? "This account has no diary story yet. Chat with Luna and come back here."
                  : "Choose an account from the dropdown to read its diary."}
              </div>
            )}
          </article>
        </div>

        <div className="diary-page-controls" aria-label="Diary page controls">
          <button
            type="button"
            className="site-secondary-button diary-page-button"
            disabled={!canGoPrevious}
            onClick={() => goToPage(pageIndex - 1, "previous")}
          >
            Previous page
          </button>
          <div className="diary-page-count">
            {sortedEntries.length ? `${pageIndex + 1} / ${sortedEntries.length}` : "0 / 0"}
          </div>
          <button
            type="button"
            className="site-primary-button diary-page-button"
            disabled={!canGoNext}
            onClick={() => goToPage(pageIndex + 1, "next")}
          >
            Next page
          </button>
        </div>
      </section>
    </div>
  );
}
