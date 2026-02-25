export const INVENTORY_SERIAL_SEARCH_MIN_CHARS = 2;

export function normalizeInventorySerialSearchQuery(value: string): string {
  const trimmed = String(value ?? "").trim();
  const withoutHash = trimmed.replace(/^#/, "");
  return withoutHash.replace(/\s+/g, "");
}

export function buildInventorySerialSearchQuery(
  value: string,
): string | undefined {
  const normalized = normalizeInventorySerialSearchQuery(value);
  if (normalized.length < INVENTORY_SERIAL_SEARCH_MIN_CHARS) {
    return undefined;
  }
  return normalized;
}
