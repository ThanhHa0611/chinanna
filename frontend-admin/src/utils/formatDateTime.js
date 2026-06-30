const VN_TIMEZONE = 'Asia/Ho_Chi_Minh';

export function formatDateTime(value) {
  if (!value) return '—';
  return new Date(value).toLocaleString('vi-VN', {
    timeZone: VN_TIMEZONE,
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export function getVnDateKey(value) {
  if (!value) return '';
  return new Intl.DateTimeFormat('en-CA', { timeZone: VN_TIMEZONE }).format(new Date(value));
}

export function getVnTodayKey() {
  return new Intl.DateTimeFormat('en-CA', { timeZone: VN_TIMEZONE }).format(new Date());
}

export function formatVnDateLabel(value) {
  if (!value) return '—';
  return new Date(value).toLocaleDateString('vi-VN', {
    timeZone: VN_TIMEZONE,
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
  });
}

export function groupItemsByVnDate(items, dateField = 'created_at') {
  const todayKey = getVnTodayKey();
  const groups = new Map();

  items.forEach((item) => {
    const dateKey = getVnDateKey(item[dateField]) || 'unknown';
    if (!groups.has(dateKey)) {
      groups.set(dateKey, []);
    }
    groups.get(dateKey).push(item);
  });

  for (const list of groups.values()) {
    list.sort((a, b) => new Date(b[dateField]) - new Date(a[dateField]));
  }

  const todayItems = groups.get(todayKey) || [];
  const pastGroups = [...groups.keys()]
    .filter((key) => key !== todayKey && key !== 'unknown')
    .sort((a, b) => b.localeCompare(a))
    .map((dateKey) => ({
      dateKey,
      dateLabel: formatVnDateLabel(groups.get(dateKey)[0][dateField]),
      items: groups.get(dateKey),
    }));

  return { todayItems, pastGroups };
}
