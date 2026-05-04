/** Where LUNA's FastAPI (InnerVoice_Jelly) lives. Used by ChatUI + DiaryTab. */

export const API_BASE = (() => {
  const configured = import.meta.env.VITE_API_BASE_URL?.trim().replace(/\/+$/, "");
  if (configured) return configured;

  if (typeof window !== "undefined") {
    /**
     * In `npm run dev`, call the backend through Vite's proxy so it works whether you open the app at
     * localhost, 127.0.0.1, or your LAN IP (same-origin avoids wrong API host + CORS).
     */
    if (import.meta.env.DEV) {
      return `${window.location.origin.replace(/\/+$/, "")}/luna-backend`;
    }

    const { hostname, origin } = window.location;
    if (hostname === "localhost" || hostname === "127.0.0.1") {
      return "http://127.0.0.1:8000";
    }
    return origin.replace(/\/+$/, "");
  }

  return "http://127.0.0.1:8000";
})();
