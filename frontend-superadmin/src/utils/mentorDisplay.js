export const LEVEL1_MENTORS = ['Thanh Hà'];
export const THANH_HA_MENTOR = 'Thanh Hà';

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
