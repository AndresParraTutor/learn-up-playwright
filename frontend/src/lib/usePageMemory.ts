import {
  type Dispatch,
  type SetStateAction,
  useEffect,
  useRef,
  useState,
} from "react";
import { useLocation } from "react-router-dom";

const SCROLL_KEY_PREFIX = "scrollY:";

// Route components unmount on navigation, so scroll position has to survive outside React state.
// sessionStorage (keyed by pathname) persists it across the round trip to a lesson/lab detail page
// and back, without leaking between browser tabs the way localStorage would.
export function useScrollRestoration(ready: boolean): void {
  const { pathname } = useLocation();
  const restoredRef = useRef(false);

  useEffect(() => {
    restoredRef.current = false;
  }, [pathname]);

  useEffect(() => {
    if (!ready || restoredRef.current) return;
    restoredRef.current = true;
    const saved = sessionStorage.getItem(SCROLL_KEY_PREFIX + pathname);
    if (saved === null) return;
    const y = Number(saved);
    if (Number.isNaN(y)) return;
    requestAnimationFrame(() => window.scrollTo(0, y));
  }, [pathname, ready]);

  useEffect(() => {
    // Debounced, not saved on every event or on unmount: navigating away swaps in the new
    // route's (briefly short, "Loading…") DOM in place, and the browser clamps window.scrollY
    // to fit — a genuine 'scroll' event firing with y=0 on this same, not-yet-unmounted
    // listener. Saving immediately (or in an unmount cleanup) would durably overwrite the real
    // position with that clamp artifact. Debouncing means the component has already unmounted
    // (clearing the pending timeout below) before the artifact would otherwise get persisted.
    let timeout: ReturnType<typeof setTimeout> | undefined;
    function onScroll() {
      clearTimeout(timeout);
      timeout = setTimeout(() => {
        sessionStorage.setItem(
          SCROLL_KEY_PREFIX + pathname,
          String(window.scrollY),
        );
      }, 300);
    }
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => {
      clearTimeout(timeout);
      window.removeEventListener("scroll", onScroll);
    };
  }, [pathname]);
}

// Same idea as useState, but the value survives the component unmounting when the user navigates
// away and back (e.g. an accordion expanded before following a link to a lesson).
export function usePersistedState<T>(
  key: string,
  initial: T,
): [T, Dispatch<SetStateAction<T>>] {
  const [state, setState] = useState<T>(() => {
    const saved = sessionStorage.getItem(key);
    if (saved === null) return initial;
    try {
      return JSON.parse(saved) as T;
    } catch {
      return initial;
    }
  });

  useEffect(() => {
    sessionStorage.setItem(key, JSON.stringify(state));
  }, [key, state]);

  return [state, setState];
}
