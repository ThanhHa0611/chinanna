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

function stripLeadingVe(content) {
  const text = (content || '').trim();
  if (/^về\s+/iu.test(text)) {
    return text.replace(/^về\s+/iu, '').trim();
  }
  return text;
}

export function compose_activity_name(data) {
  const activityType = (data?.activity_type || '').trim() || 'Khác';
  const organizer = (data?.organizer || '').trim();
  const content = stripLeadingVe(data?.content);
  const target = (data?.target_audience || '').trim();
  const deadline = (data?.deadline || '').trim();

  let line = activityType;
  if (organizer) line = `${line} của ${organizer}`;
  if (content) line = `${line}, về ${content}`;
  if (target) line = `${line} cho ${target}`;
  if (deadline) line = `${line}, dl ${deadline}`;
  return line.trim() || 'Hoạt động hồ sơ';
}

export function format_activity_feed_line(activity) {
  let line = compose_activity_name(activity);
  const stored = (activity?.activity_name || '').trim();
  if (stored && (line === 'Khác' || line === 'Hoạt động hồ sơ') && stored.length > line.length) {
    line = stored;
  }
  if (!line) line = 'Hoạt động hồ sơ';
  const link = (activity?.link || '').trim();
  if (link) {
    return `${line}\nLink: ${link}`;
  }
  return line;
}

export function feedLineText(activity) {
  return compose_activity_name(activity);
}

export function feedLineLink(activity) {
  return (activity?.link || '').trim();
}

export function formatImportanceStars(importance) {
  const value = Math.max(1, Math.min(5, parseInt(importance, 10) || 3));
  return '★'.repeat(value) + '☆'.repeat(5 - value);
}

export const APPROVAL_STATUS_LABELS = {
  approved: 'Đã duyệt',
  pending_l1_approval: 'Chờ mentor cấp 1 duyệt',
  rejected: 'Đã từ chối',
};

export const PARTICIPATION_MODE_OPTIONS = [
  { value: 'individual', label: 'Cá nhân' },
  { value: 'group', label: 'Nhóm' },
  { value: 'both', label: 'Cá nhân hay nhóm đều được' },
  { value: 'unknown', label: 'Không rõ' },
];

export const PARTICIPATION_MODE_LABELS = Object.fromEntries(
  PARTICIPATION_MODE_OPTIONS.map((item) => [item.value, item.label]),
);

export const MENTEE_PARTICIPATION_CHOICES = [
  { value: 'individual', label: 'Cá nhân' },
  { value: 'group', label: 'Nhóm' },
];

export const REGISTRATION_RESPONSE_LABELS = {
  pending_l1_approval: 'Chờ L1 duyệt',
  confirmed: 'Đã duyệt',
  rejected: 'Từ chối',
  pending: 'Chờ mentee xác nhận',
  '': '—',
};

export function registrationResponseLabel(item) {
  if (item?.response_display_label) return item.response_display_label;
  const status = item?.response_display_status || item?.group_response_status || '';
  return REGISTRATION_RESPONSE_LABELS[status] || status || '—';
}

export function registrationResponseBadgeClass(status) {
  if (status === 'pending_l1_approval') return 'is-pending';
  if (status === 'rejected') return 'is-rejected';
  if (status === 'confirmed') return 'is-approved';
  if (status === 'pending') return 'is-pending';
  return '';
}
