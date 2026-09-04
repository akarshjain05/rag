import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import App from './App';

describe('App', () => {
  it('renders without crashing', () => {
    // This smoke test catches Temporal Dead Zone (TDZ) reference errors
    // and basic syntax/hook violations that occur unconditionally on mount.
    const { container } = render(<App />);
    expect(container).toBeTruthy();
  });
});
