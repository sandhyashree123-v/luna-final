// src/App.jsx
import React, { Component, useEffect, useState } from "react";
import ChatUI from "./ChatUI";
import DiaryTab from "./DiaryTab";
import "./App.css";

const PROFILE_STORAGE_KEY = "luna_profile";
const ACCOUNTS_STORAGE_KEY = "luna_accounts";

function normalizeAccountName(name) {
  return String(name || "").trim();
}

function createAccountStorageSlug(name) {
  return normalizeAccountName(name).toLowerCase().replace(/[^a-z0-9]+/g, "-") || "account";
}

function ensureAccountSpaces(account) {
  const slug = createAccountStorageSlug(account?.name);
  const diaryKey = `luna_diary_entries:${slug}`;
  const chatKey = `luna_chat_history:${slug}`;

  if (!window.localStorage.getItem(diaryKey)) {
    window.localStorage.setItem(diaryKey, JSON.stringify([]));
  }
  if (!window.localStorage.getItem(chatKey)) {
    window.localStorage.setItem(chatKey, JSON.stringify([]));
  }
}

function readSavedProfile() {
  try {
    const raw = window.localStorage.getItem(PROFILE_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (!parsed?.name || !parsed?.password) return null;
    return { name: String(parsed.name), password: String(parsed.password) };
  } catch {
    return null;
  }
}

function readSavedAccounts() {
  try {
    const raw = window.localStorage.getItem(ACCOUNTS_STORAGE_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    const accounts = Array.isArray(parsed)
      ? parsed
        .filter((item) => item?.name && item?.password)
        .map((item) => ({ name: String(item.name), password: String(item.password) }))
      : [];

    const legacyProfile = readSavedProfile();
    if (
      legacyProfile &&
      !accounts.some((account) => account.name.toLowerCase() === legacyProfile.name.toLowerCase())
    ) {
      accounts.unshift(legacyProfile);
      window.localStorage.setItem(ACCOUNTS_STORAGE_KEY, JSON.stringify(accounts));
    }

    accounts.forEach(ensureAccountSpaces);
    return accounts;
  } catch {
    return [];
  }
}

function saveProfile(profile) {
  window.localStorage.setItem(PROFILE_STORAGE_KEY, JSON.stringify(profile));
  ensureAccountSpaces(profile);
}

function saveAccounts(accounts) {
  window.localStorage.setItem(ACCOUNTS_STORAGE_KEY, JSON.stringify(accounts));
  accounts.forEach(ensureAccountSpaces);
}

function clearSavedProfile() {
  window.localStorage.removeItem(PROFILE_STORAGE_KEY);
}

class ChatErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  render() {
    if (this.state.error) {
      return (
        <div className="app-root" style={{ padding: "2rem" }}>
          <div className="luna-error-panel">
            <div className="luna-error-panel-title">Luna hit a render glitch</div>
            <div className="luna-error-panel-body">
              {this.state.error?.message || "Unknown render error"}
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

export default function App() {
  const [profile, setProfile] = useState(() => readSavedProfile());
  const [accounts, setAccounts] = useState(() => readSavedAccounts());
  const [isSignedIn, setIsSignedIn] = useState(false);
  const [activeTab, setActiveTab] = useState("overview");
  const [isAuthModalOpen, setIsAuthModalOpen] = useState(false);
  const [authMode, setAuthMode] = useState(() => (readSavedAccounts().length ? "signin" : "signup"));
  const [authName, setAuthName] = useState(() => readSavedProfile()?.name || "");
  const [authPassword, setAuthPassword] = useState("");
  const [authConfirmPassword, setAuthConfirmPassword] = useState("");
  const [authError, setAuthError] = useState("");
  const accountChoices = accounts.length ? accounts : readSavedAccounts();
  const [diaryAccountName, setDiaryAccountName] = useState(
    () => readSavedProfile()?.name || readSavedAccounts()[0]?.name || "",
  );
  const authButtonLabel = isSignedIn ? "Account" : accountChoices.length ? "Choose account" : "Create account";
  const isChatView = activeTab === "chat" && isSignedIn;
  const diaryAccount = accountChoices.find(
    (account) => account.name.toLowerCase() === diaryAccountName.toLowerCase(),
  ) || accountChoices[0] || null;
  const diaryUserName = diaryAccount?.name || "Choose account";
  const goHome = () => setActiveTab("overview");

  const handleUnlock = (nextProfile) => {
    if (nextProfile) {
      saveProfile(nextProfile);
      setProfile(nextProfile);
      setAccounts(readSavedAccounts());
      setDiaryAccountName(nextProfile.name);
    }
    setIsSignedIn(true);
    setActiveTab("chat");
    setIsAuthModalOpen(false);
    setAuthPassword("");
    setAuthConfirmPassword("");
    setAuthError("");
  };

  const openAuthModal = (preferredMode) => {
    const savedProfile = readSavedProfile();
    const savedAccounts = readSavedAccounts();
    setAccounts(savedAccounts);
    setAuthMode(preferredMode || (savedAccounts.length ? "signin" : "signup"));
    setAuthName(savedProfile?.name || savedAccounts[0]?.name || "");
    setAuthPassword("");
    setAuthConfirmPassword("");
    setAuthError("");
    setIsAuthModalOpen(true);
  };

  const handleSignOut = () => {
    setIsSignedIn(false);
    setActiveTab("overview");
  };

  const handleReplaceProfile = () => {
    setIsSignedIn(false);
    setProfile(null);
    setAuthMode("signup");
    setAuthName("");
    setAuthPassword("");
    setAuthConfirmPassword("");
    setAuthError("");
  };

  const handleDeleteCurrentAccount = () => {
    if (!profile) return;

    const remainingAccounts = readSavedAccounts().filter(
      (account) => account.name.toLowerCase() !== profile.name.toLowerCase(),
    );
    saveAccounts(remainingAccounts);

    const nextProfile = remainingAccounts[0] || null;
    if (nextProfile) {
      saveProfile(nextProfile);
    } else {
      clearSavedProfile();
    }

    setAccounts(remainingAccounts);
    setProfile(nextProfile);
    setDiaryAccountName(nextProfile?.name || "");
    setIsSignedIn(false);
    setAuthMode(remainingAccounts.length ? "signin" : "signup");
    setAuthName(nextProfile?.name || "");
    setAuthPassword("");
    setAuthConfirmPassword("");
    setAuthError("");
  };

  const handleAuthSubmit = (event) => {
    event.preventDefault();

    const savedAccounts = readSavedAccounts();
    const cleanName = normalizeAccountName(authName);
    const cleanPassword = authPassword.trim();
    const cleanConfirm = authConfirmPassword.trim();

    if (authMode === "signup") {
      if (!cleanName) {
        setAuthError("Enter the name Luna should use for you.");
        return;
      }
      if (cleanPassword.length < 4) {
        setAuthError("Use a password with at least 4 characters.");
        return;
      }
      if (cleanPassword !== cleanConfirm) {
        setAuthError("Passwords do not match.");
        return;
      }
      if (savedAccounts.some((account) => account.name.toLowerCase() === cleanName.toLowerCase())) {
        setAuthError("An account with this name already exists. Choose it from Sign in.");
        return;
      }

      const nextProfile = { name: cleanName, password: cleanPassword };
      const nextAccounts = [...savedAccounts, nextProfile];
      saveAccounts(nextAccounts);
      saveProfile(nextProfile);
      setAccounts(nextAccounts);
      setDiaryAccountName(nextProfile.name);
      handleUnlock(nextProfile);
      return;
    }

    if (!savedAccounts.length) {
      setAuthMode("signup");
      setAuthError("No Luna accounts found yet. Create one first.");
      return;
    }

    const selectedAccount = savedAccounts.find(
      (account) => account.name.toLowerCase() === cleanName.toLowerCase(),
    );

    if (!selectedAccount) {
      setAuthError("Choose one of the saved Luna accounts.");
      return;
    }

    if (cleanPassword !== selectedAccount.password) {
      setAuthError("That password doesn't match this Luna account.");
      return;
    }

    handleUnlock(selectedAccount);
  };

  useEffect(() => {
    if (!isAuthModalOpen) return undefined;

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    const handleKeyDown = (event) => {
      if (event.key === "Escape") {
        setIsAuthModalOpen(false);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [isAuthModalOpen]);

  useEffect(() => {
    const { body, documentElement } = document;
    const previousBodyOverflow = body.style.overflow;
    const previousHtmlOverflow = documentElement.style.overflow;

    if (isChatView) {
      body.style.overflow = "hidden";
      documentElement.style.overflow = "hidden";
      body.classList.add("chat-mode-active");
      window.scrollTo(0, 0);
    } else {
      body.classList.remove("chat-mode-active");
    }

    return () => {
      body.style.overflow = previousBodyOverflow;
      documentElement.style.overflow = previousHtmlOverflow;
      body.classList.remove("chat-mode-active");
    };
  }, [isChatView]);

  return (
    <div className={`site-shell ${isChatView ? "site-shell-chat" : ""}`}>
      <div className="site-cosmic-backdrop" />
      <div className="site-atmosphere" aria-hidden="true">
        <div className="site-orb site-orb-a" />
        <div className="site-orb site-orb-b" />
      </div>
      <div className="site-noise" aria-hidden="true" />
      <div className="site-stars" />

      {isChatView && (
        <button
          type="button"
          className="site-brand site-brand-floating"
          onClick={goHome}
          aria-label="Return to Luna home"
          title="Return home"
        >
          <span className="site-brand-mark">
            <span className="site-brand-mark-core" />
            <span className="site-brand-mark-stroke" />
          </span>
          <span>
            <span className="site-brand-name">Luna</span>
            <span className="site-brand-subtitle">Companion</span>
          </span>
        </button>
      )}

      {!isChatView && <header className="site-header">
        <button
          type="button"
          className="site-brand"
          onClick={goHome}
          aria-label="Return to Luna home"
          title="Return home"
        >
          <span className="site-brand-mark">
            <span className="site-brand-mark-core" />
            <span className="site-brand-mark-stroke" />
          </span>
          <span>
            <span className="site-brand-name">Luna</span>
            <span className="site-brand-subtitle">Companion</span>
          </span>
        </button>

      </header>}

      <main className={`site-main ${isChatView ? "site-main-chat" : ""}`}>
        {activeTab === "overview" && (
          <section className="minimal-home">
            <div className="minimal-home-brand">
              <div className="minimal-home-logo">
                <span className="minimal-home-logo-core" />
                <span className="minimal-home-logo-orbit" />
              </div>
              <h1 className="minimal-home-title">Luna</h1>
            </div>

            <p className="minimal-home-subtitle">
              A calm space for thoughtful conversation, private journaling, and everyday reflection.
            </p>

            <div className="minimal-home-divider" aria-hidden="true" />

            <div className="minimal-home-actions">
              <button
                type="button"
                className="minimal-home-cta minimal-home-cta-primary"
                onClick={() => {
                  if (isSignedIn) {
                    setActiveTab("chat");
                  } else {
                    openAuthModal(accountChoices.length ? "signin" : "signup");
                  }
                }}
              >
                <span className="minimal-home-cta-shine" aria-hidden="true" />
                {isSignedIn
                  ? "Enter Luna"
                  : profile
                    ? "Sign in & begin"
                    : "Begin with Luna"}
              </button>
              <button type="button" className="minimal-home-cta minimal-home-cta-secondary" onClick={() => setActiveTab("diary")}>
                Open diary
              </button>
            </div>

            <div className="minimal-presence-strip" aria-label="About Luna">
              <div className="minimal-presence-card">
                <span className="minimal-presence-kicker">Companion</span>
                <strong>Emotion-aware chat</strong>
                <p>Luna listens with care, responds with warmth, and adapts to your emotional tone.</p>
              </div>
              <div className="minimal-presence-card">
                <span className="minimal-presence-kicker">Voice</span>
                <strong>Sonotherapy + speech</strong>
                <p>Ambient soundscapes, natural spoken replies, and a calmer atmosphere in every session.</p>
              </div>
              <div className="minimal-presence-card">
                <span className="minimal-presence-kicker">Memory</span>
                <strong>Private reflection space</strong>
                <p>Pick up your chats, keep personal notes, and stay grounded in one consistent space.</p>
              </div>
            </div>

          </section>
        )}

        {activeTab === "chat" && isSignedIn && (
          <section className="site-content-panel site-content-panel-chat">
            <div className="fade-container">
              <ChatErrorBoundary>
                <ChatUI
                  embedded
                  userName={isSignedIn ? profile?.name || "You" : "You"}
                />
              </ChatErrorBoundary>
            </div>
          </section>
        )}

        {activeTab === "diary" && (
          <section className="site-content-panel diary-content-panel">
            <DiaryTab
              userName={diaryUserName}
              storageSeed={diaryAccount?.name || "guest"}
              accounts={accountChoices}
              selectedAccountName={diaryAccount?.name || ""}
              onAccountChange={setDiaryAccountName}
            />
          </section>
        )}
      </main>

      {isAuthModalOpen && (
        <div className="auth-modal-overlay" onClick={() => setIsAuthModalOpen(false)}>
          <div
            className="auth-modal"
            role="dialog"
            aria-modal="true"
            aria-label="Luna account access"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="auth-modal-header">
              <div>
                <div className="section-kicker">Luna account</div>
                <h2>{isSignedIn ? "Manage your Luna access" : "Sign in or create your Luna profile"}</h2>
              </div>
              <button
                type="button"
                className="auth-close-button"
                onClick={() => setIsAuthModalOpen(false)}
                aria-label="Close dialog"
              >
                ×
              </button>
            </div>

            {isSignedIn ? (
              <div className="auth-signed-in-state">
                <div className="auth-signed-in-card">
                  <div className="auth-signed-in-label">Currently signed in</div>
                  <div className="auth-signed-in-name">{profile?.name || "You"}</div>
                  <p className="auth-signed-in-copy">
                    This Luna account is active on this device. Its chat history and diary stay separate from your other accounts.
                  </p>
                </div>

                <div className="auth-actions-row">
                  <button type="button" className="site-ghost-button" onClick={handleSignOut}>
                    Sign out
                  </button>
                  <button
                    type="button"
                    className="site-secondary-button"
                    onClick={() => {
                      setIsSignedIn(false);
                      setAuthMode("signin");
                      setAuthName(profile?.name || accountChoices[0]?.name || "");
                      setAuthPassword("");
                      setAuthConfirmPassword("");
                      setAuthError("");
                    }}
                  >
                    Switch account
                  </button>
                  <button
                    type="button"
                    className="site-secondary-button"
                    onClick={handleDeleteCurrentAccount}
                  >
                    Delete account
                  </button>
                  <button type="button" className="site-primary-button" onClick={() => setIsAuthModalOpen(false)}>
                    Continue
                  </button>
                </div>
              </div>
            ) : (
              <>
                <div className="auth-mode-switch">
                  <button
                    type="button"
                    className={`auth-mode-button ${authMode === "signin" ? "auth-mode-button-active" : ""}`}
                    onClick={() => {
                      setAuthMode("signin");
                      setAuthName(profile?.name || accountChoices[0]?.name || "");
                      setAuthError("");
                    }}
                  >
                    Sign in
                  </button>
                  <button
                    type="button"
                    className={`auth-mode-button ${authMode === "signup" ? "auth-mode-button-active" : ""}`}
                    onClick={() => {
                      setAuthMode("signup");
                      setAuthName("");
                      setAuthError("");
                    }}
                  >
                    Sign up
                  </button>
                </div>

                <form className="auth-form" onSubmit={handleAuthSubmit}>
                  <div className="auth-form-grid">
                    <label className="auth-field">
                      <span>{authMode === "signin" ? "Account" : "Name"}</span>
                      {authMode === "signin" && accountChoices.length ? (
                        <select
                          className="auth-input"
                          value={authName}
                          onChange={(event) => {
                            setAuthName(event.target.value);
                            if (authError) setAuthError("");
                          }}
                        >
                          {accountChoices.map((account) => (
                            <option key={account.name} value={account.name}>
                              {account.name}
                            </option>
                          ))}
                        </select>
                      ) : (
                        <input
                          type="text"
                          className="auth-input"
                          value={authName}
                          placeholder="How should Luna call you?"
                          onChange={(event) => {
                            setAuthName(event.target.value);
                            if (authError) setAuthError("");
                          }}
                        />
                      )}
                    </label>

                    <label className="auth-field">
                      <span>Password</span>
                      <input
                        type="password"
                        className="auth-input"
                        value={authPassword}
                        placeholder={authMode === "signin" ? "Enter your password" : "Create a password"}
                        onChange={(event) => {
                          setAuthPassword(event.target.value);
                          if (authError) setAuthError("");
                        }}
                      />
                    </label>

                    {authMode === "signup" && (
                      <label className="auth-field auth-field-full">
                        <span>Confirm password</span>
                        <input
                          type="password"
                          className="auth-input"
                          value={authConfirmPassword}
                          placeholder="Confirm your password"
                          onChange={(event) => {
                            setAuthConfirmPassword(event.target.value);
                            if (authError) setAuthError("");
                          }}
                        />
                      </label>
                    )}
                  </div>

                  <div className="auth-status-line">
                    {authError ||
                      (authMode === "signin"
                        ? accountChoices.length
                          ? `Choose an account. Luna will open only that account's chat and diary.`
                          : "No Luna accounts found yet. Switch to Sign up to create one."
                        : "Creating an account also creates its own Luna chat and diary space.")}
                  </div>

                  <div className="auth-actions-row">
                    {accountChoices.length > 0 && authMode === "signin" && (
                      <button
                        type="button"
                        className="site-ghost-button"
                        onClick={handleReplaceProfile}
                      >
                        Create another
                      </button>
                    )}
                    <button type="submit" className="site-primary-button">
                      {authMode === "signin" ? "Continue" : "Create account"}
                    </button>
                  </div>
                </form>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
