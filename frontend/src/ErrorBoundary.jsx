/**
 * ErrorBoundary — React class component that catches unhandled render errors.
 *
 * Wraps the main game UI.  If any child component throws during rendering,
 * this boundary catches the error, logs it to the console, and displays
 * a fallback UI with a "Try again" button that clears the error state.
 *
 * This is a class component because React's error boundary API
 * (getDerivedStateFromError, componentDidCatch) is only available
 * on class components — there is no hooks equivalent.
 */

import { Component } from 'react'

export class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { error: null }
  }

  /** Capture the error and trigger a re-render with the fallback UI. */
  static getDerivedStateFromError(error) {
    return { error }
  }

  /** Log the error and component stack for debugging. */
  componentDidCatch(error, info) {
    console.error('Unhandled render error:', error, info.componentStack)
  }

  render() {
    if (this.state.error) {
      return (
        <div className="error-boundary">
          <h2>Something went wrong</h2>
          <pre className="error-boundary-msg">{this.state.error.message}</pre>
          <button
            className="btn btn-primary"
            onClick={() => this.setState({ error: null })}
          >
            Try again
          </button>
        </div>
      )
    }
    return this.props.children
  }
}
