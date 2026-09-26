// Shared by the server layout and the client theme hook, so it must not be a client module.

export const THEMES = ["dark", "light"] as const;
export type Theme = (typeof THEMES)[number];

export const THEME_STORAGE_KEY = "gridlock-theme";
export const DEFAULT_THEME: Theme = "dark";

/** Runs inline in <head>: applies the stored theme before the page renders. Kept tiny and dependency-free. */
export const THEME_INIT_SCRIPT = `(function(){var t="${DEFAULT_THEME}";try{var s=localStorage.getItem("${THEME_STORAGE_KEY}");if(s==="light"||s==="dark")t=s}catch(e){}document.documentElement.dataset.theme=t})();`;
