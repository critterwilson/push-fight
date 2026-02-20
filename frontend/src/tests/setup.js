/**
 * Vitest setup file — loaded before every test file via vite.config.js
 * `test.setupFiles`.
 *
 * Imports @testing-library/jest-dom to extend Vitest's `expect` with
 * DOM-specific matchers such as:
 *   - toBeInTheDocument()
 *   - toHaveAttribute()
 *   - toHaveTextContent()
 *   - toBeVisible()
 *
 * This setup, combined with `test.environment: 'jsdom'` in vite.config.js,
 * provides a browser-like DOM environment for rendering React components
 * in tests without a real browser.
 */
import '@testing-library/jest-dom'
