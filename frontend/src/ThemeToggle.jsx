import React, { useEffect, useState } from 'react';

export default function ThemeToggle() {
  // Initialize state from local storage to ensure correct icon on load
  const [theme, setTheme] = useState(() => {
    return localStorage.getItem('theme') || 'dark';
  });

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