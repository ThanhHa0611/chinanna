export const LEVEL1_MENTORS = ['Mai Chi', 'Thanh Hà'];

export function formatLevel1MentorLine(mentorName) {
  const name = (mentorName || '').trim();
  if (name === 'Thanh Hà') return 'Mentor Thanh Hà';
  if (name === 'Mai Chi') return 'Mentor Mai Chi';
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
