const VN_TIMEZONE = 'Asia/Ho_Chi_Minh';

function getVnTodayParts(date = new Date()) {
  const formatter = new Intl.DateTimeFormat('en-CA', {
    timeZone: VN_TIMEZONE,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  });
  const parts = formatter.formatToParts(date);
  const get = (type) => parseInt(parts.find((item) => item.type === type)?.value || '0', 10);
  return { year: get('year'), month: get('month'), day: get('day') };
}

function parseDeadlineParts(deadlineStr) {
  const normalized = (deadlineStr || '').trim().replace(/\./g, '/').replace(/-/g, '/');
  const parts = normalized.split('/').filter(Boolean);
  if (parts.length !== 3) return null;
  const day = parseInt(parts[0], 10);
  const month = parseInt(parts[1], 10);
  let year = parseInt(parts[2], 10);
  if (Number.isNaN(day) || Number.isNaN(month) || Number.isNaN(year)) return null;
  if (year < 100) year += 2000;
  if (day < 1 || day > 31 || month < 1 || month > 12) return null;
  return { day, month, year };
}

function daysUntilDeadline(deadlineStr) {
  const deadline = parseDeadlineParts(deadlineStr);
  if (!deadline) return null;
  const today = getVnTodayParts();
  const todayUtc = Date.UTC(today.year, today.month - 1, today.day);
  const deadlineUtc = Date.UTC(deadline.year, deadline.month - 1, deadline.day);
  return Math.floor((deadlineUtc - todayUtc) / (1000 * 60 * 60 * 24));
}

export function getDeadlineBadge(deadlineStr, badgeFromApi = null) {
  if (badgeFromApi?.label) return badgeFromApi;
  const daysLeft = daysUntilDeadline(deadlineStr);
  if (daysLeft === null) return null;
  if (daysLeft < 0) return { label: 'Hết hạn', variant: 'expired' };
  if (daysLeft <= 3) return { label: 'Còn 3 ngày', variant: 'urgent' };
  if (daysLeft <= 7) return { label: 'Còn 7 ngày', variant: 'warning' };
  return null;
}
