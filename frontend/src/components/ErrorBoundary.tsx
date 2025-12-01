import { Component, ErrorInfo, ReactNode } from 'react';

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('Uncaught error:', error, errorInfo);
  }

  public render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen flex items-center justify-center bg-void text-white p-4">
            <div className="max-w-md w-full bg-surface border border-white/10 rounded-2xl p-8 shadow-2xl">
                <h1 className="text-2xl font-light mb-4 text-red-400">Application Error</h1>
                <p className="text-txt-secondary mb-6">Something went wrong. Please reload the application.</p>
                <div className="p-4 bg-black/30 rounded-lg overflow-auto max-h-48 mb-6 border border-white/5">
                    <code className="text-xs font-mono text-txt-tertiary">
                        {this.state.error?.toString()}
                    </code>
                </div>
                <button 
                    onClick={() => window.location.reload()}
                    className="w-full bg-accent text-void font-bold py-3 rounded-xl hover:bg-white transition-colors"
                >
                    Reload Application
                </button>
            </div>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;