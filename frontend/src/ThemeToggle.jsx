/**
 * ThemeToggle — Light/dark mode toggle button.
 *
 * Persists the user's theme preference in localStorage and applies it
 * via the `data-theme` attribute on the <html> element.  The CSS design
 * system in index.css defines all color variables under both
 * `:root` (light) and `[data-theme="dark"]` selectors.
 *
 * Default theme is 'dark' to match the wood-textured board aesthetic.
 */

import React, { useEffect, useState } from 'react';

export default function ThemeToggle() {
  // Initialize from localStorage so the correct icon shows immediately
  const [theme, setTheme] = useState(() => {
    return localStorage.getItem('theme') || 'dark';
  });

  // Sync the data-theme attribute whenever the theme changes
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
  }, [theme]);

  const toggleTheme = () => {
    const newTheme = theme === 'light' ? 'dark' : 'light';
    setTheme(newTheme);
    localStorage.setItem('theme', newTheme);
  };

  return (
    <button
      onClick={toggleTheme}
      className="btn btn-ghost theme-toggle"
      aria-label="Toggle Dark Mode"
      title={theme === 'light' ? "Switch to Dark Mode" : "Switch to Light Mode"}
    >
      {theme === 'light' ? '🌙' : '☀️'}
    </button>
  );
}
