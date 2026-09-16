"use client";

import { useEffect } from "react";

/**
 * Opens a folded list when the page is reached through its anchor: a station picked in the
 * search lands on `/wyk/<id>#stemlokale`, and that reader came for the stations, so they
 * should not have to tap "show" as well. Renders nothing; without JavaScript the list simply
 * stays folded under its heading.
 */
export function OopVirAnker({ anker }: { anker: string }) {
  useEffect(() => {
    function maakOop() {
      if (window.location.hash !== `#${anker}`) return;
      const lys = document.querySelector<HTMLDetailsElement>(`#${anker} details[data-uitvou]`);
      if (lys) lys.open = true;
    }
    maakOop();
    window.addEventListener("hashchange", maakOop);
    return () => window.removeEventListener("hashchange", maakOop);
  }, [anker]);
  return null;
}
