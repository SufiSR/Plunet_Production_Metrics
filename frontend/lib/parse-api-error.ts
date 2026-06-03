/** Parse FastAPI ErrorResponse (`message`) and legacy `detail` shapes. */
export function parseApiErrorBody(body: unknown, status: number): string {
  if (body && typeof body === "object") {
    const record = body as Record<string, unknown>;
    if (typeof record.message === "string" && record.message.trim()) {
      return record.message;
    }
    const detail = record.detail;
    if (typeof detail === "string" && detail.trim()) {
      return detail;
    }
    if (Array.isArray(detail) && detail.length > 0) {
      return detail
        .map((item) => {
          if (!item || typeof item !== "object") return String(item);
          const entry = item as { loc?: unknown; msg?: unknown };
          const loc = Array.isArray(entry.loc) ? entry.loc.join(".") : "";
          const msg = typeof entry.msg === "string" ? entry.msg : "";
          return loc ? `${loc}: ${msg}` : msg;
        })
        .filter(Boolean)
        .join("; ");
    }
  }
  if (status === 500) {
    return "The server failed while building this report. Try a shorter date range or retry in a moment.";
  }
  if (status === 503) {
    return "The report is still processing or temporarily unavailable. Please retry shortly.";
  }
  return `Request failed (HTTP ${status})`;
}
