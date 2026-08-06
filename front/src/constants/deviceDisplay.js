export const TERMINAL_DEVICE_DISPLAY_OFFSET = 0;

export const withTerminalDeviceDisplayOffset = (count) => {
  const normalizedCount = Number(count ?? 0);
  if (Number.isNaN(normalizedCount)) return TERMINAL_DEVICE_DISPLAY_OFFSET;
  return normalizedCount + TERMINAL_DEVICE_DISPLAY_OFFSET;
};
