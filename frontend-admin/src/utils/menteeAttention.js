const STORAGE_KEY = 'mentor-mentee-attention-v1';

function readAllAttentionStates() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : {};
  } catch {
    return {};
  }
}

function writeAllAttentionStates(all) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(all));
  } catch {
    // ignore storage errors
  }
}

export function menteeAttentionReasons(mentee, { isSuperAdmin = false, isLevel1 = false } = {}) {
  if (!mentee) return [];

  const reasons = [];
  if ((mentee.unread_documents_count || 0) > 0) {
    reasons.push('Giấy tờ mới cần xem');
  }
  if (mentee.preferred_schools_note_unread) {
    reasons.push('Trường ưa thích mới');
  }
  if ((mentee.unread_feedback_count || 0) > 0) {
    reasons.push('Tin phản hồi chưa xử lí');
  }
  if ((mentee.apply_progress_pending_count || 0) > 0) {
    reasons.push('Tiến độ apply chờ duyệt');
  }
  if (isLevel1 && mentee.hdnk_nckh_l1_unread) {
    reasons.push('Keep track HDNK+NCKH mới');
  }
  if (isLevel1 && mentee.hdnk_nckh_reminder_unread) {
    reasons.push('Nhắc cập nhật HDNK+NCKH');
  }
  if (isLevel1 && mentee.mentor_l2_activity_l1_unread) {
    const unreadItems = (mentee.mentor_l2_activity || []).filter((item) => item.l1_unread);
    if (unreadItems.length === 1) {
      reasons.push(unreadItems[0].summary || 'Mentor cấp 2 vừa cập nhật');
    } else if (unreadItems.length > 1) {
      reasons.push(`Mentor cấp 2: ${unreadItems.length} thao tác mới`);
    } else {
      reasons.push('Mentor cấp 2 vừa cập nhật');
    }
  }
  if (!isLevel1 && mentee.apply_progress_l2_unread) {
    reasons.push('Mentor cấp 1 cập nhật tiến độ');
  }
  return reasons;
}

export function getAttentionSignature(mentee, options) {
  const base = menteeAttentionReasons(mentee, options).join('\u001f');
  const l2Ids = (mentee?.mentor_l2_activity || [])
    .filter((item) => item.l1_unread)
    .map((item) => item.id)
    .join(',');
  return `${base}\u001f${mentee?.mentor_l2_activity_l1_unread ? '1' : '0'}\u001f${l2Ids}`;
}

export function readMenteeAttentionState(menteeId) {
  if (!menteeId) return {};
  return readAllAttentionStates()[menteeId] || {};
}

export function dismissMenteeAttention(mentee, options) {
  if (!mentee?.id) return;

  const reasons = menteeAttentionReasons(mentee, options);
  const all = readAllAttentionStates();

  if (reasons.length === 0) {
    delete all[mentee.id];
    writeAllAttentionStates(all);
    return;
  }

  all[mentee.id] = {
    dismissedSignature: getAttentionSignature(mentee, options),
    pinnedUnread: false,
  };
  writeAllAttentionStates(all);
}

export function pinMenteeAttentionUnread(menteeId) {
  if (!menteeId) return;

  const all = readAllAttentionStates();
  all[menteeId] = {
    ...(all[menteeId] || {}),
    pinnedUnread: true,
    dismissedSignature: '',
  };
  writeAllAttentionStates(all);
}

export function menteeShowsAttention(mentee, options) {
  const reasons = menteeAttentionReasons(mentee, options);
  if (reasons.length === 0) return false;

  const state = readMenteeAttentionState(mentee.id);
  if (state.pinnedUnread) return true;

  const signature = getAttentionSignature(mentee, options);
  if (state.dismissedSignature === signature) return false;
  return true;
}

export function menteeNeedsAttention(mentee, options) {
  return menteeShowsAttention(mentee, options);
}

export function countMenteesNeedingAttention(mentees, options) {
  return (mentees || []).filter((mentee) => menteeNeedsAttention(mentee, options)).length;
}

export function menteeHasPinnedUnread(menteeId) {
  return Boolean(readMenteeAttentionState(menteeId).pinnedUnread);
}
