import { useEffect, useRef } from "react";
/** Reset after StrictMode's setup/cleanup cycle; abort mutations on unmount. */
export function usePrivateOperation() {
  const controller = useRef(new AbortController());
  useEffect(() => {
    controller.current = new AbortController();
    const current = controller.current;
    return () => current.abort();
  }, []);
  return controller;
}
