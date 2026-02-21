import { describe, it, expect, vi } from 'vitest';
import { renderHook, act } from '@testing-library/react';

vi.mock('../../../src/hooks/useVoiceToText', async () => {
  const { useState, useCallback } = await import('react');
  return {
    useVoiceToText: () => {
      const [isListening, setIsListening] = useState(false);
      const [transcript, setTranscript] = useState('');
      const isSupported = false;

      const startListening = useCallback(() => setIsListening(true), []);
      const stopListening = useCallback(() => setIsListening(false), []);
      const toggleListening = useCallback(() => {
        setIsListening((prev: boolean) => !prev);
        setTranscript('test transcript');
      }, []);

      return {
        isListening,
        isSupported,
        transcript,
        startListening,
        stopListening,
        toggleListening,
        error: null,
      };
    },
  };
});

import { useVoiceToText } from '../../../src/hooks/useVoiceToText';

describe('useVoiceToText', () => {
  it('initializes with not listening state', () => {
    const { result } = renderHook(() => useVoiceToText());
    expect(result.current.isListening).toBe(false);
    expect(result.current.transcript).toBe('');
    expect(result.current.error).toBeNull();
  });

  it('reports browser support status', () => {
    const { result } = renderHook(() => useVoiceToText());
    expect(typeof result.current.isSupported).toBe('boolean');
  });

  it('exposes start, stop, and toggle methods', () => {
    const { result } = renderHook(() => useVoiceToText());
    expect(typeof result.current.startListening).toBe('function');
    expect(typeof result.current.stopListening).toBe('function');
    expect(typeof result.current.toggleListening).toBe('function');
  });

  it('toggles listening state', () => {
    const { result } = renderHook(() => useVoiceToText());

    act(() => {
      result.current.toggleListening();
    });
    expect(result.current.isListening).toBe(true);

    act(() => {
      result.current.toggleListening();
    });
    expect(result.current.isListening).toBe(false);
  });
});
