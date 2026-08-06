"use client";

import { useEffect, useState } from "react";

export type Theme = "dark" | "light";

export const THEME_STORAGE_KEY = "seoos-theme";

/**
 * Runs before first paint, inlined into <head> by the root layout.
 *
 * Without this the server always renders dark (it cannot know the visitor's
 * choice), the browser paints a dark page, and React then corrects it on
 * hydration — a white flash on every navigation for anyone using light mode.
 * Reading localStorage synchronously here settles the theme before the first
 * frame instead.
 *
 * Kept as a string because it has to execute before the bundle loads, and
 * deliberately wrapped in try/catch: localStorage throws in Safari's private
 * mode, and a theme preference is not worth a blank page.
 */
export const THEME_INIT_SCRIPT = `
(function () {
  try {
    var stored = localStorage.getItem(${JSON.stringify(THEME_STORAGE_KEY)});
    var theme = stored === "light" || stored === "dark"
      ? stored
      : (window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark");
    document.documentElement.setAttribute("data-theme", theme);
  } catch (e) {
    document.documentElement.setAttribute("data-theme", "dark");
  }
})();
`;

function SunIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <circle cx="12" cy="12" r="4.5" stroke="currentColor" strokeWidth="1.6" />
      <path
        d="M12 2v2.5M12 19.5V22M22 12h-2.5M4.5 12H2m15.07-7.07-1.77 1.77M8.7 15.3l-1.77 1.77m10.14 0-1.77-1.77M8.7 8.7 6.93 6.93"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
      />
    </svg>
  );
}

function MoonIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M20 14.2A8.2 8.2 0 0 1 9.8 4a8.5 8.5 0 1 0 10.2 10.2Z"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function ThemeToggle() {
  // Starts null rather than "dark": until the effect runs we do not know what
  // the pre-paint script chose, and rendering a definite icon would mean
  // showing the wrong one for a frame.
  const [theme, setTheme] = useState<Theme | null>(null);

  useEffect(() => {
    const current = document.documentElement.getAttribute("data-theme");
    setTheme(current === "light" ? "light" : "dark");
  }, []);

  useEffect(() => {
    // Someone who has never pressed the button should follow their OS when it
    // changes. Once they have chosen, their choice wins and this stops.
    const media = window.matchMedia("(prefers-color-scheme: light)");
    const onChange = (e: MediaQueryListEvent) => {
      try {
        if (localStorage.getItem(THEME_STORAGE_KEY)) return;
      } catch {
        return;
      }
      const next: Theme = e.matches ? "light" : "dark";
      document.documentElement.setAttribute("data-theme", next);
      setTheme(next);
    };
    media.addEventListener("change", onChange);
    return () => media.removeEventListener("change", onChange);
  }, []);

  function toggle() {
    const next: Theme = theme === "light" ? "dark" : "light";
    document.documentElement.setAttribute("data-theme", next);
    setTheme(next);
    try {
      localStorage.setItem(THEME_STORAGE_KEY, next);
    } catch {
      // Private mode. The theme still applies for this page view.
    }
  }

  const label =
    theme === null
      ? "Toggle theme"
      : `Switch to ${theme === "light" ? "dark" : "light"} theme`;

  return (
    <button
      type="button"
      onClick={toggle}
      aria-label={label}
      title={label}
      className="flex h-9 w-9 items-center justify-center rounded-md border border-line text-subtle transition-colors hover:border-line-strong hover:text-title"
    >
      {/* suppressHydrationWarning: the server has no way to know the theme, so
          the icon legitimately differs between server and client markup. */}
      <span suppressHydrationWarning>
        {theme === "light" ? <MoonIcon /> : <SunIcon />}
      </span>
    </button>
  );
}
