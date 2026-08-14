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

/** True after VN calendar deadline day has fully passed (matches backend is_activity_deadline_expired). */
export function isDeadlineExpired(activityOrDeadline) {
  if (activityOrDeadline && typeof activityOrDeadline === 'object') {
    if (typeof activityOrDeadline.deadline_expired === 'boolean') {
      return activityOrDeadline.deadline_expired;
    }
    const badge = getDeadlineBadge(
      activityOrDeadline.deadline,
      activityOrDeadline.deadline_badge,
    );
    if (badge?.variant === 'expired') return true;
    return daysUntilDeadline(activityOrDeadline.deadline) < 0;
  }
  const daysLeft = daysUntilDeadline(activityOrDeadline);
  return daysLeft !== null && daysLeft < 0;
}

/** Past-deadline approved activity still awaiting L1 archival confirm. */
export function needsDeadlineHideConfirm(activity) {
  if (!activity || typeof activity !== 'object') return false;
  if (typeof activity.needs_deadline_hide_confirm === 'boolean') {
    return activity.needs_deadline_hide_confirm;
  }
  if (!isDeadlineExpired(activity)) return false;
  if (activity.deadline_hide_confirmed_at) return false;
  const status = activity.approval_status;
  if (status && status !== 'approved') return false;
  return true;
}

function stripLeadingVe(content) {
  const text = (content || '').trim();
  if (/^về\s+/iu.test(text)) {
    return text.replace(/^về\s+/iu, '').trim();
  }
  return text;
}

function buildActivityNameLine(data) {
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

export function compose_activity_name(data) {
  let line = buildActivityNameLine(data);
  const link = (data?.link || '').trim();
  if (link) line = `${line} ${link}`;
  return line;
}

export const FEED_INLINE_LINK_LABEL = '(Link)';

function httpUrlPattern() {
  return /https?:\/\/[^\s]+/gi;
}

/** Extract http(s) URLs embedded in free text (e.g. stored activity_name). */
export function extractHttpUrls(text) {
  const matches = String(text || '').match(httpUrlPattern());
  return matches ? [...matches] : [];
}

/** Remove embedded http(s) URLs so feed/list UIs can show a short "(Link)" instead. */
export function stripHttpUrls(text) {
  return String(text || '')
    .replace(httpUrlPattern(), ' ')
    .replace(/\s{2,}/g, ' ')
    .trim();
}

function isWeakActivityLine(line) {
  const text = (line || '').trim();
  if (!text || text === 'Khác' || text === 'Hoạt động hồ sơ') return true;
  // "Khác" or "Khác, dl DATE" — no real contest title
  return /^Khác(?:,\s*dl\s+\S+)?$/iu.test(text);
}

function descriptionTitle(activity) {
  const desc = (activity?.description || '').trim();
  if (!desc) return '';
  const first =
    desc
      .split(/\r?\n/)
      .map((line) => line.replace(/^[-*•\t\s]+/, '').trim())
      .find(Boolean) || '';
  return stripHttpUrls(
    first.replace(/^(thông tin|hoạt động|event|title|tên)[:\-]\s*/iu, ''),
  ).slice(0, 500);
}

function withDeadlineSuffix(title, activity) {
  const text = (title || '').trim();
  if (!text) return text;
  const deadline = (activity?.deadline || '').trim();
  if (deadline && !text.includes(deadline) && !/,\s*dl\s+/iu.test(text)) {
    return `${text}, dl ${deadline}`;
  }
  return text;
}

export function format_activity_feed_line(activity) {
  const line = feedLineText(activity);
  const link = feedLineLink(activity);
  if (link) {
    return `${line} ${FEED_INLINE_LINK_LABEL}`;
  }
  return line;
}

export function feedLineText(activity) {
  let line = buildActivityNameLine(activity);
  const stored = stripHttpUrls((activity?.activity_name || '').trim());
  const fromDesc = descriptionTitle(activity);

  if (isWeakActivityLine(line)) {
    if (stored && !isWeakActivityLine(stored)) {
      line = stored;
    } else if (fromDesc && !isWeakActivityLine(fromDesc)) {
      line = withDeadlineSuffix(fromDesc, activity);
    } else if (stored) {
      line = stored;
    }
  } else if (stored && !isWeakActivityLine(stored) && stored.length > line.length + 8) {
    // Prefer a clearly richer free-form stored title over a thin composed line.
    line = stored;
  } else {
    line = stripHttpUrls(line) || line;
  }
  return line || 'Hoạt động hồ sơ';
}

export function feedLineLink(activity) {
  const direct = (activity?.link || '').trim();
  if (direct) return direct;
  const embedded = extractHttpUrls(activity?.activity_name || '');
  return embedded.length ? embedded[embedded.length - 1] : '';
}

export function formatImportanceStars(importance) {
  const parsed = parseInt(importance, 10);
  const value = Number.isNaN(parsed) ? 3 : Math.max(0, Math.min(5, parsed));
  return '★'.repeat(value) + '☆'.repeat(5 - value);
}

export const APPROVAL_STATUS_LABELS = {
  approved: 'Đã duyệt',
  pending_l1_approval: 'Chờ mentor cấp 1 duyệt',
  rejected: 'Đã từ chối',
  draft: 'Nháp (đã rút lại)',
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

export function participationModeDisplayLabel(activity) {
  const mode = activity?.participation_mode;
  const label = activity?.participation_mode_label;
  if (mode === 'unknown' || label === PARTICIPATION_MODE_LABELS.unknown) {
    return null;
  }
  return label || null;
}

export const REGISTRATION_RESPONSE_LABELS = {
  pending_l1_approval: 'Chờ L1 duyệt',
  draft: 'Nháp (chưa gửi L1)',
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
  if (status === 'draft') return 'is-pending';
  if (status === 'rejected') return 'is-rejected';
  if (status === 'confirmed') return 'is-approved';
  if (status === 'pending') return 'is-pending';
  return '';
}
