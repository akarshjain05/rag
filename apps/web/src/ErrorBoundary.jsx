import React from 'react';

export class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error('ErrorBoundary caught an error:', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{ padding: '2rem', fontFamily: 'sans-serif', textAlign: 'center' }}>
          <h2 style={{ color: '#b23a52' }}>Something went wrong.</h2>
          <pre style={{ background: '#f5f5f5', padding: '1rem', borderRadius: '4px', overflowX: 'auto', textAlign: 'left', display: 'inline-block' }}>
            {this.state.error?.toString()}
          </pre>
          <div style={{ marginTop: '1rem' }}>
            <button 
              onClick={() => window.location.reload()}
              style={{ background: '#2d4fe0', color: 'white', border: 'none', padding: '8px 16px', borderRadius: '3px', cursor: 'pointer' }}
            >
              Reload Page
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
