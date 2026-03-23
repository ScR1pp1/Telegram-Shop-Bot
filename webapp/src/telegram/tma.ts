export type ThemeParams = Record<string, string>;

export function getTelegramWebApp(): any | null {
  const w = window as any;
  return w?.Telegram?.WebApp ?? null;
}

export function initTelegram() {
  const tma = getTelegramWebApp();
  if (!tma) return { tma: null, initData: "" };
  try {
    tma.ready();
  } catch {}
  return { tma, initData: String(tma.initData || "") };
}

export function applyThemeParams(themeParams: ThemeParams | undefined) {
  if (!themeParams) return;
  const root = document.documentElement;
  const bg = themeParams.bg_color;
  const text = themeParams.text_color;
  if (bg) root.style.setProperty("--tma-bg", bg);
  if (text) root.style.setProperty("--tma-text", text);
}

export function setBackButtonHandler(handler: () => void) {
  const tma = getTelegramWebApp();
  if (!tma) return;
  tma.BackButton.onClick(handler);
  tma.BackButton.show();
}

export function removeBackButtonHandler() {
  const tma = getTelegramWebApp();
  if (!tma) return;
  tma.BackButton.offClick(() => {});
  tma.BackButton.hide();
}