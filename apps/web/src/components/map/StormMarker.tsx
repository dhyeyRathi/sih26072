export function createStormMarkerElement(
  cellId: string,
  dbz: number,
  color: string,
  onClick: (e: MouseEvent) => void
): HTMLDivElement {
  const el = document.createElement("div");
  el.className = "storm-marker-node group flex cursor-pointer flex-col items-center select-none z-20";

  el.innerHTML = `
    <div class="relative flex items-center justify-center">
      <span class="storm-marker-pulse absolute h-10 w-10 rounded-full opacity-60" style="background-color:${color}"></span>
      <div class="marker-core flex h-8 w-8 items-center justify-center rounded-full border-2 border-white shadow-xl transition-all group-hover:scale-110" style="background-color:${color}">
        <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
          <path d="M13 2 3 14h9l-1 8 10-12h-9l1-8z"/>
        </svg>
      </div>
    </div>
    <div class="marker-label mt-1 flex items-center gap-1 whitespace-nowrap rounded-md border border-slate-700/80 bg-slate-900/90 px-2 py-0.5 text-[11px] font-semibold text-white shadow-lg backdrop-blur">
      <span>${cellId}</span>
      <span class="marker-dbz font-bold" style="color:${color}">${dbz.toFixed(0)} dBZ</span>
    </div>
  `;

  el.addEventListener("click", onClick);
  return el;
}

export function updateStormMarkerSelection(el: HTMLElement, isSelected: boolean) {
  const core = el.querySelector(".marker-core");
  if (!core) return;
  if (isSelected) {
    core.className = "marker-core flex h-10 w-10 items-center justify-center rounded-full border-4 border-amber-400 shadow-2xl scale-110 transition-all";
  } else {
    core.className = "marker-core flex h-8 w-8 items-center justify-center rounded-full border-2 border-white shadow-xl transition-all group-hover:scale-110";
  }
}

export function updateStormMarkerDbz(el: HTMLElement, dbz: number, color: string) {
  const dbzEl = el.querySelector(".marker-dbz");
  if (dbzEl) {
    dbzEl.textContent = `${dbz.toFixed(0)} dBZ`;
    (dbzEl as HTMLElement).style.color = color;
  }
}
