export const HDNK_NCKH_GROUP_INTERNAL = 'nhóm Du học Trung Quốc';
export const HDNK_NCKH_GROUP_INTERNAL_LEGACY = 'nhóm Trơn Tru';
export const HDNK_NCKH_PARTICIPATION_TYPES = ['cá nhân', 'nhóm ngoài', HDNK_NCKH_GROUP_INTERNAL];
export const HDNK_NCKH_PROGRESS_OPTIONS = ['mới tạo nhóm', 'đang tiến hành', 'đã hoàn thành'];
export const HDNK_NCKH_AWARD_LEVELS = ['giải 1', 'giải 2', 'giải 3', 'khác'];

export function isInternalGroupParticipation(value) {
  const raw = (value || '').trim();
  return raw === HDNK_NCKH_GROUP_INTERNAL || raw === HDNK_NCKH_GROUP_INTERNAL_LEGACY;
}

export function isThanhHaTeam(admin) {
  return (admin?.mentor_name || '').trim() === 'Thanh Hà';
}

export function isMaiChiTeam(admin) {
  return (admin?.mentor_name || '').trim() === 'Mai Chi';
}

export function emptyHdnkNckhEntry() {
  return {
    entry_id: '',
    start_date: '',
    category: '',
    participation_type: '',
    zalo_group_name: '',
    progress: '',
    has_award: false,
    award_level: '',
    mentor_note: '',
    reminder_due_at: '',
  };
}

export function normalizeHdnkNckhEntries(entries) {
  return (entries || []).map((entry) => {
    let participation = entry?.participation_type || '';
    if (participation === HDNK_NCKH_GROUP_INTERNAL_LEGACY) {
      participation = HDNK_NCKH_GROUP_INTERNAL;
    }
    return {
      entry_id: entry?.entry_id || '',
      start_date: entry?.start_date || '',
      category: entry?.category || '',
      participation_type: participation,
      zalo_group_name: entry?.zalo_group_name || '',
      progress: entry?.progress || '',
      has_award: Boolean(entry?.has_award),
      award_level: entry?.award_level || '',
      mentor_note: entry?.mentor_note || '',
      reminder_due_at: entry?.reminder_due_at || '',
    };
  });
}
