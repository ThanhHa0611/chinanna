export const LEVEL1_MENTORS = ['Thanh Hà'];

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
  // Dùng lịch Việt Nam để so ngày đăng ký
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

export function formatLevel1MentorLine(mentorName) {
  const name = (mentorName || '').trim();
  if (name === 'Thanh Hà') return 'Mentor Thanh Hà';
  return name ? `Mentor ${name}` : '';
}

export function isLevel1MentorAccount(admin) {
  if (!admin) return false;
  if (admin.is_level1_mentor) return true;
  const mentor = (admin.mentor_name || '').trim();
  const displayName = (admin.full_name || admin.username || '').trim();
  return LEVEL1_MENTORS.includes(mentor) && displayName === mentor;
}

export function getSidebarBrand(admin) {
  const lines = [{ text: 'Du học Trung Quốc', variant: 'title' }];

  if (admin?.is_super_admin && !admin?.mentor_name) {
    lines.push({ text: 'Quản trị hệ thống', variant: 'mentor' });
    return lines;
  }

  const mentorLine = formatLevel1MentorLine(admin?.mentor_name);
  if (mentorLine) {
    lines.push({ text: mentorLine, variant: 'mentor' });
  }

  const userName = (admin?.full_name || '').trim();
  if (userName && !isLevel1MentorAccount(admin)) {
    lines.push({ text: userName, variant: 'user' });
  }

  return lines;
}
