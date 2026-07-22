export const LEVEL1_MENTORS = ['Thanh Hà'];
export const THANH_HA_MENTOR = 'Thanh Hà';

/** Học sinh đăng ký sau ngày này thì mentor thấy hậu tố (VMH) bên tên. */
export const VMH_REGISTRATION_CUTOFF_DATE = '2023-07-23';

export function menteeCreatedDateKey(mentee) {
  const raw = mentee?.created_at || '';
  if (!raw) return '';
  const date = new Date(raw);
  if (Number.isNaN(date.getTime())) {
    const match = String(raw).match(/^(\d{4}-\d{2}-\d{2})/);
    return match ? match[1] : '';
  }
  return new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Ho_Chi_Minh',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(date);
}

export function menteeShowsVmhTag(mentee) {
  if (typeof mentee?.shows_vmh_tag === 'boolean') return mentee.shows_vmh_tag;
  const day = menteeCreatedDateKey(mentee);
  return Boolean(day && day > VMH_REGISTRATION_CUTOFF_DATE);
}

export function formatMenteeNameForMentor(mentee, fallback = '—') {
  const fromApi = (mentee?.display_name || '').trim();
  if (fromApi) return fromApi;
  const name =
    (mentee?.full_name || '').trim() ||
    (mentee?.username || '').trim() ||
    (mentee?.email || '').trim() ||
    fallback;
  if (!name || name === fallback) return fallback;
  return menteeShowsVmhTag(mentee) ? `${name} (VMH)` : name;
}

export function isThanhHaSuperAdmin(admin) {
  if (!admin?.is_super_admin) return false;
  return (admin.mentor_name || admin.full_name || '').trim() === THANH_HA_MENTOR;
}

export function formatLevel1MentorLine(mentorName) {
  const name = (mentorName || '').trim();
  if (name === 'Thanh Hà') return 'Mentor Thanh Hà';
  return name ? `Mentor ${name}` : '';
}

export function formatMentorWithTeam(displayName, teamName) {
  const name = (displayName || '').trim() || 'Không rõ';
  const team = (teamName || '').trim();
  if (!team || team === 'Chung') return name;
  return `${name} (${team === teamName ? `team ${team}` : team})`;
}
