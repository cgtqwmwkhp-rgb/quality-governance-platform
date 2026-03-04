import { useState, useCallback } from 'react';

interface GeolocationState {
  latitude: number | null;
  longitude: number | null;
  accuracy: number | null;
  isLoading: boolean;
  error: string | null;
  formattedAddress: string | null;
}

interface UseGeolocationOptions {
  enableHighAccuracy?: boolean;
  timeout?: number;
  maximumAge?: number;
}

interface UseGeolocationReturn extends GeolocationState {
  getLocation: () => Promise<GeolocationPosition | null>;
  getLocationString: () => Promise<string | null>;
  clearError: () => void;
}

export function useGeolocation(options: UseGeolocationOptions = {}): UseGeolocationReturn {
  const {
    enableHighAccuracy = true,
    timeout = 10000,
    maximumAge = 0,
  } = options;

  const [state, setState] = useState<GeolocationState>({
    latitude: null,
    longitude: null,
    accuracy: null,
    isLoading: false,
    error: null,
    formattedAddress: null,
  });

  const getLocation = useCallback(async (): Promise<GeolocationPosition | null> => {
    // Check if geolocation is supported
    if (!navigator.geolocation) {
      setState(prev => ({
        ...prev,
        error: 'Geolocation is not supported by your browser',
        isLoading: false,
      }));
      return null;
    }

    setState(prev => ({ ...prev, isLoading: true, error: null }));

    try {
      const position = await new Promise<GeolocationPosition>((resolve, reject) => {
        navigator.geolocation.getCurrentPosition(
          resolve,
          reject,
          {
            enableHighAccuracy,
            timeout,
            maximumAge,
          }
        );
      });

      setState({
        latitude: position.coords.latitude,
        longitude: position.coords.longitude,
        accuracy: position.coords.accuracy,
        isLoading: false,
        error: null,
        formattedAddress: null,
      });

      return position;
    } catch (error) {
      let errorMessage = 'Unable to retrieve your location';

      if (error instanceof GeolocationPositionError) {
        switch (error.code) {
          case error.PERMISSION_DENIED:
            errorMessage = 'Location permission denied. Please enable location access in your browser settings.';
            break;
          case error.POSITION_UNAVAILABLE:
            errorMessage = 'Location information is unavailable. Please try again.';
            break;
          case error.TIMEOUT:
            errorMessage = 'Location request timed out. Please try again.';
            break;
        }
      }

      setState(prev => ({
        ...prev,
        isLoading: false,
        error: errorMessage,
      }));

      return null;
    }
  }, [enableHighAccuracy, timeout, maximumAge]);

  const getLocationString = useCallback(async (): Promise<string | null> => {
    const position = await getLocation();
    
    if (position) {
      const lat = position.coords.latitude.toFixed(6);
      const lng = position.coords.longitude.toFixed(6);
      const accuracy = Math.round(position.coords.accuracy);
      
      return `GPS: ${lat}, ${lng} (±${accuracy}m)`;
    }
    
    return null;
  }, [getLocation]);

  const clearError = useCallback(() => {
    setState(prev => ({ ...prev, error: null }));
  }, []);

  return {
    ...state,
    getLocation,
    getLocationString,
    clearError,
  };
}
