import { useEffect, useMemo, useRef, useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { api } from '../services/api';
import { isLevel1MentorAccount } from '../utils/mentorDisplay';
import {
  APPROVAL_STATUS_LABELS,
  PARTICIPATION_MODE_OPTIONS,
  compose_activity_name,
  feedLineLink,
  feedLineText,
  formatImportanceStars,
  getDeadlineBadge,
  participationModeDisplayLabel,
} from '../utils/profileActivities';
import { formatMenteeActivityInviteOption } from '../data/applyDegree';

const ACTIVITY_TYPES = ['Cuộc thi', 'NCKH', 'HĐNK', 'Hội thảo', 'Chương trình hè', 'Dự án', 'Khác'];
const MAJORS = [
  'Kinh tế & Logistics',
  'Truyền thông',
  'Ngôn ngữ & Giáo dục',
  'Y sinh',
  'Nghệ thuật',
  'Xã hội học',
  'Quan hệ quốc tế',
  'Luật',
  'Khác',
];

function emptyForm() {
  return {
    link: '',
    description: '',
    activity_type: 'Khác',
    deadline: '',
    organizer: '',
    target_audience: '',
    content: '',
    attachment_url: '',
    suitable_majors: [],
    suitable_majors_other: '',
    importance: 3,
    participation_mode: 'unknown',
    internal_note: '',
    participant_limit: '',
    referrer_zalo_phone: '',
  };
}

function activityToForm(activity) {
  if (!activity) return emptyForm();
  return {
    link: activity.link || '',
    description: activity.description || '',
    activity_type: activity.activity_type || 'Khác',
    deadline: activity.deadline || '',
    organizer: activity.organizer || '',
    target_audience: activity.target_audience || '',
    content: activity.content || '',
    attachment_url: activity.attachment_url || '',
    suitable_majors: activity.suitable_majors || [],
    suitable_majors_other: activity.suitable_majors_other || '',
    importance: Number.isFinite(Number(activity.importance)) ? Number(activity.importance) : 3,
    participation_mode: activity.participation_mode || 'unknown',
    internal_note: activity.internal_note || '',
    participant_limit: activity.participant_limit ? String(activity.participant_limit) : '',
    referrer_zalo_phone: activity.referrer_zalo_phone || '',
  };
}

function ActivityContentFields({ form, updateField, toggleMajor, onParse, parsing }) {
  return (
    <>
      <label>
        Link
        <input value={form.link} onChange={(e) => updateField('link', e.target.value)} />
      </label>
      <label>
        Mô tả gốc (dùng parse — không hiển thị trên feed)
        <textarea
          rows={4}
          value={form.description}
          onChange={(e) => updateField('description', e.target.value)}
        />
      </label>
      {onParse && (
        <div className="action-cell">
          <button type="button" className="btn btn-outline btn-sm" onClick={onParse} disabled={parsing}>
            Parse tự động
          </button>
        </div>
      )}
      <label>
        Loại hoạt động
        <span className="field-hint">Tự nhận diện khi parse — có thể chỉnh lại trước khi lưu</span>
        <select
          value={form.activity_type}
          onChange={(e) => updateField('activity_type', e.target.value)}
        >
          {ACTIVITY_TYPES.map((item) => (
            <option key={item} value={item}>
              {item}
            </option>
          ))}
        </select>
      </label>
      <label>
        Deadline
        <input value={form.deadline} onChange={(e) => updateField('deadline', e.target.value)} />
      </label>
      <label>
        Đơn vị tổ chức
        <input value={form.organizer} onChange={(e) => updateField('organizer', e.target.value)} />
      </label>
      <label>
        Đối tượng
        <input
          value={form.target_audience}
          onChange={(e) => updateField('target_audience', e.target.value)}
        />
      </label>
      <label>
        Hình thức tham gia
        <select
          value={form.participation_mode}
          onChange={(e) => updateField('participation_mode', e.target.value)}
        >
          {PARTICIPATION_MODE_OPTIONS.map((item) => (
            <option key={item.value} value={item.value}>
              {item.label}
            </option>
          ))}
        </select>
      </label>
      <label>
        Nội dung
        <input value={form.content} onChange={(e) => updateField('content', e.target.value)} />
      </label>
      <label>
        Mức độ quan trọng
        <StarRating value={form.importance} onChange={(n) => updateField('importance', n)} />
      </label>
      <label>
        File đính kèm (URL)
        <input
          value={form.attachment_url}
          onChange={(e) => updateField('attachment_url', e.target.value)}
        />
      </label>
      <div>
        <p className="muted">Ngành phù hợp</p>
        <div className="action-cell">
          {MAJORS.map((major) => (
            <label key={major} className="checkbox-label">
              <input
                type="checkbox"
                checked={form.suitable_majors.includes(major)}
                onChange={() => toggleMajor(major)}
              />
              {major}
            </label>
          ))}
        </div>
        {form.suitable_majors.includes('Khác') && (
          <label>
            Ngành khác (ghi rõ)
            <input
              value={form.suitable_majors_other}
              onChange={(e) => updateField('suitable_majors_other', e.target.value)}
              placeholder="Ví dụ: Kiến trúc, Du lịch..."
            />
          </label>
        )}
      </div>
      <label>
        Giới hạn số người tham gia
        <input
          type="number"
          min="0"
          value={form.participant_limit}
          onChange={(e) => updateField('participant_limit', e.target.value)}
          placeholder="Để trống = không giới hạn"
        />
        <span className="field-hint">
          Khi đủ số lượng, các báo danh còn lại sẽ tự động bị từ chối.
        </span>
      </label>
      <label>
        Ghi chú (nội bộ, mentor)
        <textarea
          value={form.internal_note}
          onChange={(e) => updateField('internal_note', e.target.value)}
          placeholder="Ghi chú riêng cho mentor, mentee sẽ không thấy nội dung này"
          rows={2}
        />
      </label>
      <label>
        SĐT Zalo người giới thiệu
        <input
          type="tel"
          value={form.referrer_zalo_phone}
          onChange={(e) => updateField('referrer_zalo_phone', e.target.value)}
          placeholder="0901234567"
          inputMode="numeric"
        />
        <span className="field-hint">
          Chỉ cộng điểm giới thiệu khi lần đầu thêm SĐT cho hoạt động này.
        </span>
      </label>
      <div className="profile-activity-feed-preview">
        <p className="profile-activity-feed-preview-label">Tên hoạt động (tự động)</p>
        <p className="muted profile-activity-feed-preview-hint">
          Dòng compact hiển thị trên feed mentee — cập nhật theo các trường bên trên
        </p>
        <p className="profile-activity-name-preview">{compose_activity_name(form)}</p>
        <p className="profile-activity-feed-preview-label">Xem trước feed</p>
        <FeedLinePreview activity={form} />
      </div>
    </>
  );
}

function StarRating({ value, onChange }) {
  return (
    <div className="importance-stars" role="group" aria-label="Mức độ quan trọng">
      {[1, 2, 3, 4, 5].map((n) => (
        <button
          key={n}
          type="button"
          className={`importance-star${n <= value ? ' is-active' : ''}`}
          onClick={() => onChange(n === value ? 0 : n)}
          aria-label={`${n} sao`}
          aria-pressed={n <= value}
          title={n === value ? 'Bấm lại để bỏ chọn' : undefined}
        >
          ★
        </button>
      ))}
    </div>
  );
}

function FeedLinePreview({ activity }) {
  const text = feedLineText(activity);
  const link = feedLineLink(activity);
  return (
    <div className="profile-activity-feed-preview-line">
      <div>
        {text}
        {link && (
          <>
            {' '}
            <a
              href={link}
              target="_blank"
              rel="noreferrer"
              className="profile-activity-inline-link"
            >
              (Link)
            </a>
          </>
        )}
      </div>
    </div>
  );
}

function approvalBadgeClass(status) {
  if (status === 'pending_l1_approval') return 'is-pending';
  if (status === 'rejected') return 'is-rejected';
  return 'is-approved';
}

function activityPickerLabel(item) {
  const name = compose_activity_name(item);
  const registrations = item.registration_count || 0;
  let label = `${name} (${registrations} báo danh)`;
  if (item.approval_status === 'pending_l1_approval') {
    label += ' · chờ duyệt';
  }
  return label;
}

function progressTrackingStatusClass(status) {
  if (status === 'completed') return 'is-completed';
  return 'is-in-progress';
}

function ProgressTrackingRows({ rows, activityId, saving, onDelete }) {
  return rows.flatMap((row) => {
    const memberCount = row.members.length;
    const typeLabel = row.type === 'group' ? 'Tên nhóm' : 'Cá nhân';
    return row.members.map((member, index) => (
      <tr key={`${row.row_id}:${member.mentee_id}`}>
        {index === 0 && (
          <td rowSpan={memberCount} className="profile-activity-progress-type">
            {typeLabel}
          </td>
        )}
        <td>
          {row.type === 'group' && index === 0 && row.group_name && (
            <div className="profile-activity-progress-group-name">{row.group_name}</div>
          )}
          <div className="profile-activity-progress-member">
            {member.name || '—'}
            {member.is_leader && (
              <span className="profile-activity-progress-leader"> (nhóm trưởng)</span>
            )}
          </div>
        </td>
        {index === 0 && (
          <>
            <td rowSpan={memberCount}>{row.start_date || '—'}</td>
            <td rowSpan={memberCount}>
              <span
                className={`profile-activity-progress-status ${progressTrackingStatusClass(row.status)}`}
              >
                {row.status_label || '—'}
              </span>
            </td>
            <td rowSpan={memberCount} className="profile-activity-progress-delete">
              <button
                type="button"
                className="btn btn-outline btn-outline-pastel btn-sm"
                onClick={() => onDelete(activityId, row)}
                disabled={saving}
                title="Gỡ khỏi bảng theo dõi tiến độ"
              >
                Xóa
              </button>
            </td>
          </>
        )}
      </tr>
    ));
  });
}

function ActivityPickerDropdown({ activities, value, onChange }) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef(null);
  const selected = activities.find((item) => item.id === value) || null;

  useEffect(() => {
    if (!open) return undefined;
    const handleClickOutside = (event) => {
      if (!rootRef.current?.contains(event.target)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [open]);

  const renderPendingBadge = (item) => {
    const count = item.pending_action_count || 0;
    if (count <= 0) return null;
    return (
      <span className="notify-circle-badge" title="Có hành động chờ duyệt">
        {count}
      </span>
    );
  };

  return (
    <div ref={rootRef} className={`activity-picker${open ? ' is-open' : ''}`}>
      <button
        type="button"
        className="activity-picker-trigger"
        aria-expanded={open}
        aria-haspopup="listbox"
        onClick={() => setOpen((prev) => !prev)}
      >
        {selected ? (
          <span className="activity-picker-trigger-content">
            <span className="activity-picker-option-text">{activityPickerLabel(selected)}</span>
            {renderPendingBadge(selected)}
          </span>
        ) : (
          <span className="activity-picker-placeholder">-- Chọn --</span>
        )}
        <span className="activity-picker-caret" aria-hidden>
          ▾
        </span>
      </button>
      {open && (
        <div className="activity-picker-menu" role="listbox" aria-label="Chọn hoạt động">
          <button
            type="button"
            role="option"
            aria-selected={!value}
            className={`activity-picker-option${!value ? ' active' : ''}`}
            onClick={() => {
              onChange('');
              setOpen(false);
            }}
          >
            <span>-- Chọn --</span>
          </button>
          {activities.map((item) => (
            <button
              key={item.id}
              type="button"
              role="option"
              aria-selected={value === item.id}
              className={`activity-picker-option${value === item.id ? ' active' : ''}`}
              onClick={() => {
                onChange(item.id);
                setOpen(false);
              }}
            >
              <span className="activity-picker-option-text">{activityPickerLabel(item)}</span>
              {renderPendingBadge(item)}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export default function ProfileActivities() {
  const { admin } = useAuth();
  const [form, setForm] = useState(emptyForm());
  const [activities, setActivities] = useState([]);
  const [selectedId, setSelectedId] = useState('');
  const [registrations, setRegistrations] = useState([]);
  const [groupName, setGroupName] = useState('');
  const [selectedMentees, setSelectedMentees] = useState([]);
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [createFormCollapsed, setCreateFormCollapsed] = useState(true);
  const [bulkImportRows, setBulkImportRows] = useState([]);
  const [bulkImportSkipped, setBulkImportSkipped] = useState([]);
  const [bulkImportLoading, setBulkImportLoading] = useState(false);
  const [bulkApproving, setBulkApproving] = useState(false);
  const [manageFormCollapsed, setManageFormCollapsed] = useState(true);
  const [pendingEditActivityId, setPendingEditActivityId] = useState('');
  const manageSectionRef = useRef(null);
  const [editOpen, setEditOpen] = useState(false);
  const [editForm, setEditForm] = useState(emptyForm());
  const [editSaving, setEditSaving] = useState(false);
  const [inviteOpen, setInviteOpen] = useState(false);
  const [inviteMentees, setInviteMentees] = useState([]);
  const [inviteMenteesLoading, setInviteMenteesLoading] = useState(false);
  const [inviteSelectedIds, setInviteSelectedIds] = useState([]);
  const [inviteSaving, setInviteSaving] = useState(false);
  const [moveTargets, setMoveTargets] = useState({});
  const [addToGroupTargets, setAddToGroupTargets] = useState({});
  const [keeptrackReviews, setKeeptrackReviews] = useState([]);
  const [selectedKeeptrackReviews, setSelectedKeeptrackReviews] = useState([]);
  const [abandonRequests, setAbandonRequests] = useState([]);
  const [progressTracking, setProgressTracking] = useState([]);
  const [progressTrackingExpanded, setProgressTrackingExpanded] = useState(false);
  const [progressActivityExpanded, setProgressActivityExpanded] = useState({});
  const [finalizeSuccessByGroup, setFinalizeSuccessByGroup] = useState({});
  const [leaderPickerVisible, setLeaderPickerVisible] = useState({});
  const [leaderTargets, setLeaderTargets] = useState({});
  const finalizeTimeoutsRef = useRef({});

  const canReview = Boolean(admin?.is_super_admin || isLevel1MentorAccount(admin));
  const isL2 = Boolean(admin && !canReview);

  const selectedActivity = useMemo(
    () => activities.find((item) => item.id === selectedId) || null,
    [activities, selectedId],
  );

  const selectedParticipationLabel = participationModeDisplayLabel(selectedActivity);

  const registrationByMenteeId = useMemo(() => {
    const map = new Map();
    for (const item of registrations) {
      map.set(item.mentee_id, item);
    }
    return map;
  }, [registrations]);

  const approvedGroups = useMemo(
    () =>
      (selectedActivity?.groups || []).filter(
        (group) => group.approval_status !== 'pending_l1_approval',
      ),
    [selectedActivity?.groups],
  );

  const unassignedRegistrations = useMemo(() => {
    const assigned = new Set();
    for (const group of selectedActivity?.groups || []) {
      for (const menteeId of group.mentee_ids || []) {
        assigned.add(menteeId);
      }
    }
    return registrations.filter((item) => !assigned.has(item.mentee_id));
  }, [registrations, selectedActivity?.groups]);

  const registeredMenteeIds = useMemo(
    () => new Set(registrations.map((item) => item.mentee_id)),
    [registrations],
  );

  const invitedMenteeIds = useMemo(
    () => new Set(selectedActivity?.invited_mentee_ids || []),
    [selectedActivity?.invited_mentee_ids],
  );

  const inviteCandidates = useMemo(
    () =>
      [...inviteMentees]
        .filter((mentee) => !registeredMenteeIds.has(mentee.id))
        .sort((a, b) =>
          formatMenteeActivityInviteOption(a).localeCompare(
            formatMenteeActivityInviteOption(b),
            'vi',
          ),
        ),
    [inviteMentees, registeredMenteeIds],
  );

  const canInviteMentees =
    selectedActivity?.approval_status === 'approved' ||
    !selectedActivity?.approval_status;

  const pendingActivities = useMemo(
    () => activities.filter((item) => item.approval_status === 'pending_l1_approval'),
    [activities],
  );

  const pendingGroupActions = useMemo(() => {
    const items = [];
    for (const activity of activities) {
      for (const action of activity.pending_l1_actions || []) {
        items.push({ ...action, activity_id: activity.id, activity_name: compose_activity_name(activity) });
      }
    }
    return items;
  }, [activities]);

  const progressTrackingRowCount = useMemo(
    () => progressTracking.reduce((total, item) => total + (item.rows?.length || 0), 0),
    [progressTracking],
  );

  const updateEditForm = (key, value) => {
    setEditForm((prev) => ({ ...prev, [key]: value }));
  };

  const toggleEditMajor = (major) => {
    setEditForm((prev) => {
      const has = prev.suitable_majors.includes(major);
      const suitable_majors = has
        ? prev.suitable_majors.filter((item) => item !== major)
        : [...prev.suitable_majors, major];
      return {
        ...prev,
        suitable_majors,
        suitable_majors_other: major === 'Khác' && has ? '' : prev.suitable_majors_other,
      };
    });
  };

  const handleEditParse = async () => {
    setEditSaving(true);
    setError('');
    setMessage('');
    try {
      const parsed = await api.parseProfileActivity({ description: editForm.description });
      setEditForm((prev) => ({
        ...prev,
        activity_type: parsed.activity_type || prev.activity_type,
        deadline: parsed.deadline || prev.deadline,
        organizer: parsed.organizer || prev.organizer,
        target_audience: parsed.target_audience || prev.target_audience,
        content: parsed.content || prev.content,
        suitable_majors: parsed.suitable_majors || [],
        suitable_majors_other: parsed.suitable_majors_other || '',
      }));
      setMessage('Đã phân tích mô tả. Kiểm tra các trường và xem trước dòng feed.');
    } catch (err) {
      setError(err.message);
    } finally {
      setEditSaving(false);
    }
  };

  const handleSaveEdit = async () => {
    if (!selectedActivity) return;
    setEditSaving(true);
    setError('');
    setMessage('');
    try {
      await api.updateProfileActivity(selectedActivity.id, editForm);
      await loadActivities();
      setEditOpen(false);
      setMessage('Đã cập nhật nội dung hoạt động.');
    } catch (err) {
      setError(err.message);
    } finally {
      setEditSaving(false);
    }
  };

  const openInvitePanel = async () => {
    if (inviteOpen) {
      setInviteOpen(false);
      setInviteSelectedIds([]);
      return;
    }
    setInviteOpen(true);
    setInviteSelectedIds([]);
    if (inviteMentees.length) return;
    setInviteMenteesLoading(true);
    setError('');
    try {
      const items = await api.getMentees();
      setInviteMentees(Array.isArray(items) ? items : items?.items || []);
    } catch (err) {
      setError(err.message);
    } finally {
      setInviteMenteesLoading(false);
    }
  };

  const toggleInviteMentee = (menteeId) => {
    setInviteSelectedIds((prev) =>
      prev.includes(menteeId) ? prev.filter((id) => id !== menteeId) : [...prev, menteeId],
    );
  };

  const handleSendInvites = async () => {
    if (!selectedActivity || !inviteSelectedIds.length) return;
    setInviteSaving(true);
    setError('');
    setMessage('');
    try {
      const result = await api.inviteProfileActivityMentees(selectedActivity.id, {
        mentee_ids: inviteSelectedIds,
      });
      await loadActivities();
      setInviteOpen(false);
      setInviteSelectedIds([]);
      const count = result?.invited_count ?? inviteSelectedIds.length;
      setMessage(`Đã mời ${count} mentee tham gia hoạt động.`);
    } catch (err) {
      setError(err.message);
    } finally {
      setInviteSaving(false);
    }
  };

  const loadActivities = async () => {
    const data = await api.getProfileActivities();
    const items = Array.isArray(data) ? data : data?.items || [];
    setActivities(items);
    if (!selectedId && items.length) {
      setSelectedId(items[0].id);
    }
  };

  const loadRegistrations = async (activityId) => {
    if (!activityId) {
      setRegistrations([]);
      return;
    }
    const data = await api.getProfileActivityRegistrations(activityId);
    setRegistrations(data.items || []);
  };

  const loadKeeptrackReviews = async () => {
    const data = await api.getProfileActivityKeeptrackReviews();
    setKeeptrackReviews(data.items || []);
  };

  const loadAbandonRequests = async () => {
    const data = await api.getProfileActivityKeeptrackAbandonRequests();
    setAbandonRequests(data.items || []);
  };

  const loadProgressTracking = async () => {
    const data = await api.getProfileActivityProgressTracking();
    setProgressTracking(data.activities || []);
  };

  useEffect(() => {
    Promise.all([
      loadActivities(),
      loadKeeptrackReviews(),
      loadAbandonRequests(),
      loadProgressTracking(),
    ])
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    loadRegistrations(selectedId).catch(() => {});
  }, [selectedId]);

  useEffect(() => {
    return () => {
      Object.values(finalizeTimeoutsRef.current).forEach(clearTimeout);
    };
  }, []);

  useEffect(() => {
    if (!selectedActivity?.groups?.length) return;
    setLeaderPickerVisible((prev) => {
      const next = { ...prev };
      for (const group of selectedActivity.groups) {
        if (
          group.finalized_at &&
          !group.is_auto_solo &&
          !group.leader_mentee_id &&
          !finalizeSuccessByGroup[group.group_id]
        ) {
          next[group.group_id] = true;
        }
      }
      return next;
    });
  }, [selectedActivity?.groups, finalizeSuccessByGroup]);

  useEffect(() => {
    setEditForm(activityToForm(selectedActivity));
    setInviteOpen(false);
    setInviteSelectedIds([]);
    if (pendingEditActivityId && selectedId === pendingEditActivityId && selectedActivity) {
      setEditOpen(true);
      setPendingEditActivityId('');
    } else if (!pendingEditActivityId) {
      setEditOpen(false);
    }
  }, [selectedId, selectedActivity?.id, selectedActivity?.updated_at, pendingEditActivityId, selectedActivity]);

  const openPendingActivityEdit = (activityId) => {
    setManageFormCollapsed(false);
    setPendingEditActivityId(activityId);
    setSelectedId(activityId);
    window.requestAnimationFrame(() => {
      manageSectionRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    });
  };

  useEffect(() => {
    if (!selectedId) {
      setGroupName('');
      return;
    }
    api
      .suggestProfileActivityGroupName(selectedId)
      .then((data) => setGroupName(data?.suggested_name || ''))
      .catch(() => {});
  }, [selectedId, selectedActivity?.groups?.length]);

  const updateForm = (key, value) => {
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  const toggleMajor = (major) => {
    setForm((prev) => {
      const has = prev.suitable_majors.includes(major);
      const suitable_majors = has
        ? prev.suitable_majors.filter((item) => item !== major)
        : [...prev.suitable_majors, major];
      return {
        ...prev,
        suitable_majors,
        suitable_majors_other: major === 'Khác' && has ? '' : prev.suitable_majors_other,
      };
    });
  };

  const handleParse = async () => {
    setSaving(true);
    setError('');
    setMessage('');
    try {
      const parsed = await api.parseProfileActivity({ description: form.description });
      setForm((prev) => ({
        ...prev,
        activity_type: parsed.activity_type || prev.activity_type,
        deadline: parsed.deadline || prev.deadline,
        organizer: parsed.organizer || prev.organizer,
        target_audience: parsed.target_audience || prev.target_audience,
        content: parsed.content || prev.content,
        suitable_majors: parsed.suitable_majors || [],
        suitable_majors_other: parsed.suitable_majors_other || '',
      }));
      setMessage('Đã phân tích mô tả. Kiểm tra các trường và xem trước dòng feed.');
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const handleCreate = async () => {
    setSaving(true);
    setError('');
    setMessage('');
    try {
      const result = await api.createProfileActivity(form);
      setForm(emptyForm());
      await loadActivities();
      if (result?.message) {
        setMessage(result.message);
      } else if (isL2) {
        setMessage('Hoạt động đã gửi, chờ mentor cấp 1 duyệt trước khi hiển thị cho mentee.');
      } else {
        setMessage('Đã đăng hoạt động mới.');
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const handleBulkImportFile = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setBulkImportLoading(true);
    setError('');
    setMessage('');
    try {
      const data = await api.bulkImportParseProfileActivities(file);
      const items = (data.items || []).map((item) => ({ ...item, _selected: true, _error: '' }));
      setBulkImportRows(items);
      setBulkImportSkipped(data.skipped_rows || []);
      if (items.length) {
        setMessage(`Đã phân tích ${items.length} dòng từ file — kiểm tra xem trước feed bên dưới.`);
      } else {
        setMessage('Không tìm thấy dòng hợp lệ nào trong file.');
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setBulkImportLoading(false);
      e.target.value = '';
    }
  };

  const updateBulkImportRow = (rowIndex, key, value) => {
    setBulkImportRows((prev) =>
      prev.map((row) => {
        if (row.row_index !== rowIndex) return row;
        const next = { ...row, [key]: value };
        next.activity_name = compose_activity_name(next);
        return next;
      }),
    );
  };

  const toggleBulkImportRowMajor = (rowIndex, major) => {
    setBulkImportRows((prev) =>
      prev.map((row) => {
        if (row.row_index !== rowIndex) return row;
        const currentMajors = row.suitable_majors || [];
        const has = currentMajors.includes(major);
        const suitable_majors = has
          ? currentMajors.filter((item) => item !== major)
          : [...currentMajors, major];
        const next = {
          ...row,
          suitable_majors,
          suitable_majors_other: major === 'Khác' && has ? '' : row.suitable_majors_other,
        };
        next.activity_name = compose_activity_name(next);
        return next;
      }),
    );
  };

  const toggleBulkImportRowSelected = (rowIndex) => {
    setBulkImportRows((prev) =>
      prev.map((row) => (row.row_index === rowIndex ? { ...row, _selected: !row._selected } : row)),
    );
  };

  const allBulkImportSelected =
    bulkImportRows.length > 0 && bulkImportRows.every((row) => row._selected);

  const toggleAllBulkImportRows = () => {
    setBulkImportRows((prev) => prev.map((row) => ({ ...row, _selected: !allBulkImportSelected })));
  };

  const handleBulkApprove = async () => {
    const selectedRows = bulkImportRows.filter((row) => row._selected);
    if (!selectedRows.length) return;
    setBulkApproving(true);
    setError('');
    setMessage('');
    try {
      const items = selectedRows.map(({ _selected, _error, ...rest }) => rest);
      const data = await api.bulkCreateProfileActivities(items);
      const results = data.results || [];
      const successRowIndexes = new Set(
        results.filter((item) => item.success).map((item) => item.row_index),
      );
      const errorByRow = new Map(
        results.filter((item) => !item.success).map((item) => [item.row_index, item.error]),
      );
      setBulkImportRows((prev) =>
        prev
          .filter((row) => !successRowIndexes.has(row.row_index))
          .map((row) =>
            errorByRow.has(row.row_index)
              ? { ...row, _error: errorByRow.get(row.row_index) }
              : row,
          ),
      );
      await loadActivities();
      const successCount = successRowIndexes.size;
      const failCount = results.length - successCount;
      if (successCount && !failCount) {
        setMessage(
          isL2
            ? `Đã gửi ${successCount} hoạt động, chờ mentor cấp 1 duyệt trước khi hiển thị cho mentee.`
            : `Đã đăng ${successCount} hoạt động mới.`,
        );
      } else if (successCount && failCount) {
        setMessage(`Đã tạo ${successCount} hoạt động, ${failCount} dòng lỗi — sửa lại bên dưới rồi duyệt lại.`);
      } else {
        setError('Không tạo được hoạt động nào — kiểm tra lại các dòng bên dưới.');
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setBulkApproving(false);
    }
  };

  const handleApprove = async (activityId) => {
    setSaving(true);
    setError('');
    try {
      await api.approveProfileActivity(activityId);
      await loadActivities();
      setMessage('Đã duyệt hoạt động — mentee sẽ thấy trên feed.');
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const handleReject = async (activityId) => {
    setSaving(true);
    setError('');
    try {
      await api.rejectProfileActivity(activityId);
      await loadActivities();
      setMessage('Đã từ chối hoạt động.');
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteActivity = async (activity) => {
    if (!activity?.id) return;
    const activityName = (activity.activity_name || '').trim() || 'này';
    if (
      !window.confirm(
        `Bạn có chắc muốn xóa toàn bộ hoạt động "${activityName}"? Hành động này sẽ xóa hoạt động, các nhóm và toàn bộ báo danh/tiến độ của mentee — không thể hoàn tác.`,
      )
    ) {
      return;
    }
    setSaving(true);
    setError('');
    setMessage('');
    try {
      const result = await api.deleteProfileActivity(activity.id);
      if (activity.id === selectedId) {
        setSelectedId('');
      }
      await loadActivities();
      setMessage(result?.message || 'Đã xóa hoạt động.');
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const toggleMentee = (menteeId) => {
    setSelectedMentees((prev) =>
      prev.includes(menteeId) ? prev.filter((id) => id !== menteeId) : [...prev, menteeId],
    );
  };

  const handleCreateGroup = async () => {
    if (!selectedActivity) return;
    let name = (groupName || '').trim();
    if (!name) {
      setSaving(true);
      setError('');
      try {
        const data = await api.suggestProfileActivityGroupName(selectedActivity.id);
        name = (data?.suggested_name || '').trim();
        if (name) setGroupName(name);
      } catch (err) {
        setError(err.message);
        setSaving(false);
        return;
      }
      setSaving(false);
    }
    if (!name) {
      setError('Vui lòng nhập tên nhóm trước khi tạo.');
      return;
    }
    if (!window.confirm(`Tạo nhóm "${name}" với ${selectedMentees.length} mentee đã chọn?`)) {
      return;
    }
    setSaving(true);
    setError('');
    setMessage('');
    try {
      const result = await api.upsertProfileActivityGroup(selectedActivity.id, {
        group_name: name,
        mentee_ids: selectedMentees,
      });
      setSelectedMentees([]);
      setGroupName('');
      await loadActivities();
      await loadRegistrations(selectedActivity.id);
      setMessage(
        result?.message ||
          (isL2
            ? 'Đã gửi phân nhóm, chờ mentor cấp 1 duyệt trước khi mentee thấy.'
            : 'Đã tạo nhóm — mentee sẽ nhận thông báo.'),
      );
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const handleApproveGroupAction = async (activityId, groupId) => {
    setSaving(true);
    setError('');
    try {
      await api.approveProfileActivityGroup(activityId, groupId);
      await loadActivities();
      if (activityId === selectedId) {
        await loadRegistrations(activityId);
      }
      setMessage('Đã duyệt phân nhóm — mentee sẽ nhận thông báo.');
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const handleRejectGroupAction = async (activityId, groupId) => {
    setSaving(true);
    setError('');
    try {
      await api.rejectProfileActivityGroup(activityId, groupId);
      await loadActivities();
      if (activityId === selectedId) {
        await loadRegistrations(activityId);
      }
      setMessage('Đã từ chối phân nhóm.');
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const handleRejectRegistration = async (menteeId) => {
    if (!selectedActivity) return;
    setSaving(true);
    setError('');
    setMessage('');
    try {
      const result = await api.rejectProfileActivityRegistration(selectedActivity.id, menteeId);
      await loadActivities();
      await loadRegistrations(selectedActivity.id);
      setMessage(
        result?.message ||
          (isL2
            ? 'Đã gửi từ chối, chờ mentor cấp 1 duyệt trước khi mentee thấy.'
            : 'Đã từ chối báo danh mentee.'),
      );
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const handleApproveRegistrationReject = async (activityId, menteeId) => {
    setSaving(true);
    setError('');
    try {
      await api.approveProfileActivityRegistrationReject(activityId, menteeId);
      await loadActivities();
      if (activityId === selectedId) {
        await loadRegistrations(activityId);
      }
      setMessage('Đã duyệt từ chối báo danh — mentee sẽ được thông báo.');
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const handleDenyRegistrationReject = async (activityId, menteeId) => {
    setSaving(true);
    setError('');
    try {
      await api.denyProfileActivityRegistrationReject(activityId, menteeId);
      await loadActivities();
      if (activityId === selectedId) {
        await loadRegistrations(activityId);
      }
      setMessage('Đã hủy yêu cầu từ chối báo danh.');
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const handleAddMenteeToGroup = async (menteeId) => {
    if (!selectedActivity) return;
    const groupId = addToGroupTargets[menteeId];
    if (!groupId) {
      setError('Chọn nhóm để thêm mentee.');
      return;
    }
    setSaving(true);
    setError('');
    setMessage('');
    try {
      const result = await api.addMenteeToProfileActivityGroup(selectedActivity.id, groupId, {
        mentee_id: menteeId,
      });
      await loadActivities();
      await loadRegistrations(selectedActivity.id);
      setMessage(result?.message || 'Đã thêm mentee vào nhóm.');
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const handleRemoveMenteeFromGroup = async (menteeId, groupId) => {
    if (!selectedActivity || !groupId) return;
    if (!window.confirm('Xóa mentee khỏi nhóm này?')) return;
    setSaving(true);
    setError('');
    setMessage('');
    try {
      const result = await api.removeMenteeFromProfileActivityGroup(selectedActivity.id, groupId, {
        mentee_id: menteeId,
      });
      await loadActivities();
      await loadRegistrations(selectedActivity.id);
      setMessage(result?.message || 'Đã xóa mentee khỏi nhóm.');
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const handleMoveMenteeGroup = async (menteeId) => {
    if (!selectedActivity) return;
    const targetGroupId = moveTargets[menteeId];
    if (!targetGroupId) {
      setError('Chọn nhóm đích để chuyển mentee.');
      return;
    }
    setSaving(true);
    setError('');
    setMessage('');
    try {
      const result = await api.moveProfileActivityMenteeGroup(selectedActivity.id, menteeId, {
        target_group_id: targetGroupId,
      });
      await loadActivities();
      await loadRegistrations(selectedActivity.id);
      setMessage(result?.message || 'Đã chuyển mentee sang nhóm — có thể chốt nhóm khi sẵn sàng.');
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const renderParticipationCell = (item) => {
    if (item.participation_choice_label) {
      return item.participation_choice_label;
    }
    if (item.awaiting_group_assignment) {
      return 'Chờ phân nhóm';
    }
    return '—';
  };

  const getMenteeDisplayName = (menteeId) => {
    const registration = registrations.find((item) => item.mentee_id === menteeId);
    return registration?.mentee_name || menteeId;
  };

  const handleDeleteGroup = async (group) => {
    if (!selectedActivity || !group?.group_id) return;
    const groupName = (group.group_name || '').trim() || 'này';
    if (!window.confirm(`Bạn có chắc muốn xóa nhóm ${groupName}?`)) return;
    setSaving(true);
    setError('');
    setMessage('');
    try {
      const result = await api.deleteProfileActivityGroup(selectedActivity.id, group.group_id);
      await loadActivities();
      await loadRegistrations(selectedActivity.id);
      setMessage(result?.message || 'Đã xóa nhóm.');
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const handleFinalizeGroup = async (groupId) => {
    if (!selectedActivity) return;
    setSaving(true);
    setError('');
    try {
      await api.finalizeProfileActivityGroup(selectedActivity.id, groupId);
      await loadActivities();
      await loadRegistrations(selectedActivity.id);
      setFinalizeSuccessByGroup((prev) => ({ ...prev, [groupId]: true }));
      if (finalizeTimeoutsRef.current[groupId]) {
        clearTimeout(finalizeTimeoutsRef.current[groupId]);
      }
      finalizeTimeoutsRef.current[groupId] = setTimeout(() => {
        setFinalizeSuccessByGroup((prev) => {
          const next = { ...prev };
          delete next[groupId];
          return next;
        });
        setLeaderPickerVisible((prev) => ({ ...prev, [groupId]: true }));
        delete finalizeTimeoutsRef.current[groupId];
      }, 3000);
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const handleSetGroupLeader = async (groupId) => {
    if (!selectedActivity) return;
    const menteeId = leaderTargets[groupId];
    if (!menteeId) {
      setError('Chọn mentee làm nhóm trưởng.');
      return;
    }
    setSaving(true);
    setError('');
    try {
      await api.setProfileActivityGroupLeader(selectedActivity.id, groupId, {
        mentee_id: menteeId,
      });
      await loadActivities();
      setLeaderPickerVisible((prev) => {
        const next = { ...prev };
        delete next[groupId];
        return next;
      });
      setMessage('Đã chọn nhóm trưởng.');
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const keeptrackReviewKey = (item) => `${item.activity_id}:${item.mentee_id}`;

  const toggleKeeptrackReview = (item) => {
    const key = keeptrackReviewKey(item);
    setSelectedKeeptrackReviews((prev) =>
      prev.includes(key) ? prev.filter((row) => row !== key) : [...prev, key],
    );
  };

  const toggleAllKeeptrackReviews = () => {
    if (selectedKeeptrackReviews.length === keeptrackReviews.length) {
      setSelectedKeeptrackReviews([]);
      return;
    }
    setSelectedKeeptrackReviews(keeptrackReviews.map((item) => keeptrackReviewKey(item)));
  };

  const handleViewKeeptrackReview = async (item) => {
    setSaving(true);
    setError('');
    try {
      await api.viewProfileActivityKeeptrackReview(item.activity_id, item.mentee_id);
      await Promise.all([loadKeeptrackReviews(), loadAbandonRequests(), loadActivities()]);
      if (item.activity_id === selectedId) {
        await loadRegistrations(item.activity_id);
      }
      setSelectedKeeptrackReviews((prev) =>
        prev.filter((row) => row !== keeptrackReviewKey(item)),
      );
      setMessage('Đã đánh dấu đã xem cập nhật tiến độ.');
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const handleRejectKeeptrackReview = async (item) => {
    const note = window.prompt('Ghi chú từ chối (tuỳ chọn):', '') ?? '';
    if (note === null) return;
    setSaving(true);
    setError('');
    try {
      await api.rejectProfileActivityKeeptrackReview(item.activity_id, item.mentee_id, { note });
      await Promise.all([loadKeeptrackReviews(), loadAbandonRequests(), loadActivities()]);
      if (item.activity_id === selectedId) {
        await loadRegistrations(item.activity_id);
      }
      setSelectedKeeptrackReviews((prev) =>
        prev.filter((row) => row !== keeptrackReviewKey(item)),
      );
      setMessage('Đã từ chối và hoàn tác tiến độ mentee.');
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const handleBulkViewKeeptrackReviews = async () => {
    const items = keeptrackReviews
      .filter((item) => selectedKeeptrackReviews.includes(keeptrackReviewKey(item)))
      .map((item) => ({ activity_id: item.activity_id, mentee_id: item.mentee_id }));
    if (!items.length) {
      setError('Chọn ít nhất một cập nhật tiến độ.');
      return;
    }
    setSaving(true);
    setError('');
    try {
      const result = await api.bulkViewProfileActivityKeeptrackReviews(items);
      await Promise.all([loadKeeptrackReviews(), loadAbandonRequests(), loadActivities()]);
      if (selectedId) {
        await loadRegistrations(selectedId);
      }
      setSelectedKeeptrackReviews([]);
      setMessage(result?.message || 'Đã đánh dấu đã xem hàng loạt.');
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const handleApproveAbandonRequest = async (item) => {
    if (!window.confirm(`Đồng ý cho ${item.mentee_name || 'mentee'} từ bỏ hoạt động này?`)) return;
    setSaving(true);
    setError('');
    try {
      await api.approveProfileActivityKeeptrackAbandon(item.activity_id, item.mentee_id);
      await Promise.all([loadAbandonRequests(), loadActivities(), loadProgressTracking()]);
      if (item.activity_id === selectedId) {
        await loadRegistrations(item.activity_id);
      }
      setMessage('Đã đồng ý từ bỏ — hoạt động đã gỡ khỏi Keep track.');
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const handleRejectAbandonRequest = async (item) => {
    const note = window.prompt('Ghi chú từ chối (tuỳ chọn):', '') ?? '';
    if (note === null) return;
    setSaving(true);
    setError('');
    try {
      await api.rejectProfileActivityKeeptrackAbandon(item.activity_id, item.mentee_id, { note });
      await Promise.all([loadAbandonRequests(), loadActivities()]);
      if (item.activity_id === selectedId) {
        await loadRegistrations(item.activity_id);
      }
      setMessage('Đã từ chối yêu cầu từ bỏ — mentee tiếp tục theo dõi hoạt động.');
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const toggleProgressActivity = (activityId) => {
    setProgressActivityExpanded((prev) => ({
      ...prev,
      [activityId]: !prev[activityId],
    }));
  };

  const isProgressActivityExpanded = (activityId) => Boolean(progressActivityExpanded[activityId]);

  const handleRemoveProgressTracking = async (activityId, row) => {
    const label =
      row.type === 'group'
        ? `nhóm "${row.group_name || 'Nhóm'}"`
        : row.members?.[0]?.name || 'mentee';
    if (!window.confirm(`Gỡ ${label} khỏi bảng theo dõi tiến độ? Tiến độ HDNK của mentee cũng sẽ bị gỡ.`)) {
      return;
    }
    setSaving(true);
    setError('');
    try {
      await api.removeProfileActivityProgressTrackingRow(activityId, {
        type: row.type,
        group_id: row.group_id || '',
        mentee_id: row.type === 'individual' ? row.mentee_ids?.[0] || '' : '',
      });
      await Promise.all([loadProgressTracking(), loadActivities()]);
      if (activityId === selectedId) {
        await loadRegistrations(activityId);
      }
      setMessage('Đã gỡ khỏi bảng theo dõi tiến độ.');
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const renderDeadlineBadge = (activity) => {
    const badge = getDeadlineBadge(activity?.deadline, activity?.deadline_badge);
    if (!badge) return null;
    return (
      <span className={`profile-activity-deadline-badge is-${badge.variant}`}>{badge.label}</span>
    );
  };

  const renderApprovalBadge = (activity) => {
    const status = activity?.approval_status || 'approved';
    const label = APPROVAL_STATUS_LABELS[status] || status;
    return (
      <span className={`profile-activity-approval-badge ${approvalBadgeClass(status)}`}>
        {label}
      </span>
    );
  };

  const renderMenteeNameCell = (item) => (
    <>
      <div>{item.mentee_name}</div>
      {item.mentee_profile_summary && (
        <div className="profile-activity-keeptrack-mentee-summary">{item.mentee_profile_summary}</div>
      )}
    </>
  );

  const canRejectRegistration = (item) => {
    if (item.pending_l1_reject || item.response_display_status === 'rejected') {
      return false;
    }
    if (item.response_display_status === 'confirmed' && !item.awaiting_group_assignment) {
      return false;
    }
    return true;
  };

  const renderRejectRegistrationButton = (item) => {
    if (item.pending_l1_reject) {
      return <span className="muted profile-activity-pending-reject">Chờ L1 duyệt từ chối</span>;
    }
    if (!canRejectRegistration(item)) {
      return null;
    }
    return (
      <button
        type="button"
        className="btn btn-outline btn-sm profile-activity-reject-btn"
        onClick={() => handleRejectRegistration(item.mentee_id)}
        disabled={saving}
      >
        Từ chối
      </button>
    );
  };

  const renderGroupMemberActions = (item, group) => {
    const currentGroupId = group.group_id;
    const isAutoSolo = Boolean(group.is_auto_solo);
    const teamGroups = approvedGroups.filter((entry) => !entry.is_auto_solo);
    const moveOptions = isAutoSolo
      ? teamGroups
      : teamGroups.filter((entry) => entry.group_id !== currentGroupId);

    return (
    <div className="action-cell profile-activity-group-ops">
      {!isAutoSolo && (
        <button
          type="button"
          className="btn btn-outline btn-sm"
          onClick={() => handleRemoveMenteeFromGroup(item.mentee_id, currentGroupId)}
          disabled={saving}
        >
          Xóa khỏi nhóm
        </button>
      )}
      {moveOptions.length > 0 && (
        <>
          <select
            value={moveTargets[item.mentee_id] || ''}
            onChange={(e) =>
              setMoveTargets((prev) => ({
                ...prev,
                [item.mentee_id]: e.target.value,
              }))
            }
          >
            <option value="">{isAutoSolo ? 'Chuyển sang nhóm...' : 'Chuyển sang...'}</option>
            {moveOptions.map((entry) => (
              <option key={entry.group_id} value={entry.group_id}>
                {entry.group_name}
              </option>
            ))}
          </select>
          <button
            type="button"
            className="btn btn-outline btn-sm"
            onClick={() => handleMoveMenteeGroup(item.mentee_id)}
            disabled={saving}
          >
            {isAutoSolo ? 'Chuyển sang nhóm' : 'Chuyển'}
          </button>
        </>
      )}
    </div>
    );
  };

  const renderUnassignedActions = (item) => (
    <div className="profile-activity-group-ops">
      {renderRejectRegistrationButton(item)}
      {approvedGroups.length > 0 && (
        <div className="action-cell profile-activity-add-to-group">
          <select
            value={addToGroupTargets[item.mentee_id] || ''}
            onChange={(e) =>
              setAddToGroupTargets((prev) => ({
                ...prev,
                [item.mentee_id]: e.target.value,
              }))
            }
          >
            <option value="">Thêm vào nhóm...</option>
            {approvedGroups.filter((group) => !group.is_auto_solo).map((group) => (
              <option key={group.group_id} value={group.group_id}>
                {group.group_name}
              </option>
            ))}
          </select>
          <button
            type="button"
            className="btn btn-outline btn-sm"
            onClick={() => handleAddMenteeToGroup(item.mentee_id)}
            disabled={saving}
          >
            Thêm
          </button>
        </div>
      )}
    </div>
  );

  const renderGroupSectionHead = (group) => {
    const groupPending = group.approval_status === 'pending_l1_approval';
    const isFinalized = Boolean(group.finalized_at);
    const showFinalizeSuccess = Boolean(finalizeSuccessByGroup[group.group_id]);
    const showLeaderPicker =
      !group.is_auto_solo &&
      isFinalized &&
      !group.leader_mentee_id &&
      !showFinalizeSuccess &&
      Boolean(leaderPickerVisible[group.group_id]);
    const memberCount = (group.mentee_ids || []).length;

    return (
      <div className="profile-activity-registration-group-head">
        <div className="profile-activity-registration-group-title">
          <strong>{group.group_name}</strong> ({memberCount} thành viên)
          {groupPending && (
            <span className="profile-activity-approval-badge is-pending"> Chờ L1 duyệt</span>
          )}
          {group.is_auto_solo && <span className="muted"> — Cá nhân, không cần chốt nhóm</span>}
          {showFinalizeSuccess && (
            <span className="form-success group-finalize-success"> · Đã tạo nhóm thành công</span>
          )}
        </div>
        <div className="action-cell">
          {!isFinalized && !group.is_auto_solo && (
            <button
              type="button"
              className="btn btn-primary btn-sm"
              onClick={() => handleFinalizeGroup(group.group_id)}
              disabled={saving || groupPending}
            >
              Chốt nhóm
            </button>
          )}
          {!group.is_auto_solo && (
            <button
              type="button"
              className="btn btn-outline btn-sm"
              onClick={() => handleDeleteGroup(group)}
              disabled={saving}
            >
              Xóa nhóm
            </button>
          )}
          {canReview && groupPending && (
            <>
              <button
                type="button"
                className="btn btn-primary btn-sm"
                onClick={() => handleApproveGroupAction(selectedActivity.id, group.group_id)}
                disabled={saving}
              >
                Duyệt nhóm
              </button>
              <button
                type="button"
                className="btn btn-outline btn-sm"
                onClick={() => handleRejectGroupAction(selectedActivity.id, group.group_id)}
                disabled={saving}
              >
                Từ chối
              </button>
            </>
          )}
          {showLeaderPicker && (
            <>
              <select
                value={leaderTargets[group.group_id] || ''}
                onChange={(e) =>
                  setLeaderTargets((prev) => ({
                    ...prev,
                    [group.group_id]: e.target.value,
                  }))
                }
              >
                <option value="">Chọn nhóm trưởng...</option>
                {(group.mentee_ids || []).map((menteeId) => (
                  <option key={menteeId} value={menteeId}>
                    {getMenteeDisplayName(menteeId)}
                  </option>
                ))}
              </select>
              <button
                type="button"
                className="btn btn-primary btn-sm"
                onClick={() => handleSetGroupLeader(group.group_id)}
                disabled={saving || !(leaderTargets[group.group_id] || '')}
              >
                Chọn nhóm trưởng
              </button>
            </>
          )}
        </div>
      </div>
    );
  };

  if (loading) return <p className="loader">Đang tải...</p>;

  return (
    <>
      <div className="page-head">
        <h2>Hoạt động làm đẹp hồ sơ</h2>
        <p>Tạo hoạt động, quản lý báo danh, chia nhóm và chốt sync HDNK + NCKH.</p>
      </div>

      {error && <p className="form-error">{error}</p>}
      {message && <p className="form-success">{message}</p>}

      {keeptrackReviews.length > 0 && (
        <div className="panel-card profile-activity-pending-queue">
          <div className="profile-activity-pending-queue-head">
            <h3>Tiến độ cá nhân chờ xem ({keeptrackReviews.length})</h3>
            <div className="action-cell">
              <button
                type="button"
                className="btn btn-primary btn-sm"
                onClick={handleBulkViewKeeptrackReviews}
                disabled={saving || selectedKeeptrackReviews.length === 0}
              >
                Đã xem hàng loạt ({selectedKeeptrackReviews.length})
              </button>
            </div>
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>
                    <input
                      type="checkbox"
                      checked={
                        keeptrackReviews.length > 0 &&
                        selectedKeeptrackReviews.length === keeptrackReviews.length
                      }
                      onChange={toggleAllKeeptrackReviews}
                      aria-label="Chọn tất cả"
                    />
                  </th>
                  <th>Mentee</th>
                  <th>Hoạt động</th>
                  <th>Tiến độ</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {keeptrackReviews.map((item) => (
                  <tr key={keeptrackReviewKey(item)}>
                    <td>
                      <input
                        type="checkbox"
                        checked={selectedKeeptrackReviews.includes(keeptrackReviewKey(item))}
                        onChange={() => toggleKeeptrackReview(item)}
                      />
                    </td>
                    <td>
                      <div>{item.mentee_name || item.mentee_email || '—'}</div>
                      {item.mentee_profile_summary && (
                        <div className="profile-activity-keeptrack-mentee-summary">
                          {item.mentee_profile_summary}
                        </div>
                      )}
                    </td>
                    <td>{item.activity_name}</td>
                    <td>{item.progress_summary || item.progress_label || '—'}</td>
                    <td>
                      <div className="action-cell">
                        <button
                          type="button"
                          className="btn btn-outline btn-sm"
                          onClick={() => handleRejectKeeptrackReview(item)}
                          disabled={saving}
                        >
                          Từ chối
                        </button>
                        <button
                          type="button"
                          className="btn btn-primary btn-sm"
                          onClick={() => handleViewKeeptrackReview(item)}
                          disabled={saving}
                        >
                          Đã xem
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {abandonRequests.length > 0 && (
        <div className="panel-card profile-activity-pending-queue">
          <h3>Yêu cầu từ bỏ hoạt động ({abandonRequests.length})</h3>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Mentee</th>
                  <th>Hoạt động</th>
                  <th>Ghi chú</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {abandonRequests.map((item) => (
                  <tr key={`${item.activity_id}:${item.mentee_id}`}>
                    <td>
                      <div>{item.mentee_name || item.mentee_email || '—'}</div>
                      {item.mentee_profile_summary && (
                        <div className="profile-activity-keeptrack-mentee-summary">
                          {item.mentee_profile_summary}
                        </div>
                      )}
                    </td>
                    <td>{item.activity_name}</td>
                    <td>{item.note || '—'}</td>
                    <td>
                      <div className="action-cell">
                        <button
                          type="button"
                          className="btn btn-outline btn-sm"
                          onClick={() => handleRejectAbandonRequest(item)}
                          disabled={saving}
                        >
                          Từ chối
                        </button>
                        <button
                          type="button"
                          className="btn btn-primary btn-sm"
                          onClick={() => handleApproveAbandonRequest(item)}
                          disabled={saving}
                        >
                          Đồng ý
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {canReview && pendingGroupActions.length > 0 && (
        <div className="panel-card profile-activity-pending-queue">
          <h3>Chờ duyệt phân nhóm / từ chối ({pendingGroupActions.length})</h3>
          <ul className="profile-activity-pending-list">
            {pendingGroupActions.map((item) => (
              <li
                key={
                  item.action_type === 'assign_group'
                    ? `group-${item.activity_id}-${item.group_id}`
                    : `reject-${item.activity_id}-${item.mentee_id}`
                }
                className="profile-activity-pending-item"
              >
                <div className="profile-activity-pending-line">
                  <strong>{item.activity_name}</strong>
                  {item.action_type === 'assign_group' ? (
                    <span className="muted">
                      Phân nhóm &quot;{item.group_name}&quot; ({(item.mentee_ids || []).length} mentee)
                    </span>
                  ) : (
                    <span className="muted">
                      Từ chối báo danh: {item.mentee_name}
                      {item.note ? ` — ${item.note}` : ''}
                    </span>
                  )}
                </div>
                <div className="action-cell">
                  <button
                    type="button"
                    className="btn btn-primary btn-sm"
                    onClick={() =>
                      item.action_type === 'assign_group'
                        ? handleApproveGroupAction(item.activity_id, item.group_id)
                        : handleApproveRegistrationReject(item.activity_id, item.mentee_id)
                    }
                    disabled={saving}
                  >
                    Duyệt
                  </button>
                  <button
                    type="button"
                    className="btn btn-outline btn-sm"
                    onClick={() =>
                      item.action_type === 'assign_group'
                        ? handleRejectGroupAction(item.activity_id, item.group_id)
                        : handleDenyRegistrationReject(item.activity_id, item.mentee_id)
                    }
                    disabled={saving}
                  >
                    Từ chối
                  </button>
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}

      {canReview && pendingActivities.length > 0 && (
        <div className="panel-card profile-activity-pending-queue">
          <h3>Chờ duyệt ({pendingActivities.length})</h3>
          <ul className="profile-activity-pending-list">
            {pendingActivities.map((item) => (
              <li key={item.id} className="profile-activity-pending-item">
                <div className="profile-activity-pending-line">
                  <span className="importance-stars-display" title="Mức độ quan trọng">
                    {formatImportanceStars(item.importance)}
                  </span>
                  <FeedLinePreview activity={item} />
                  {renderDeadlineBadge(item)}
                </div>
                <div className="action-cell">
                  <button
                    type="button"
                    className="btn btn-outline btn-sm"
                    onClick={() => openPendingActivityEdit(item.id)}
                    disabled={saving || editSaving}
                  >
                    Chỉnh sửa
                  </button>
                  <button
                    type="button"
                    className="btn btn-primary btn-sm"
                    onClick={() => handleApprove(item.id)}
                    disabled={saving}
                  >
                    Duyệt
                  </button>
                  <button
                    type="button"
                    className="btn btn-outline btn-sm"
                    onClick={() => handleReject(item.id)}
                    disabled={saving}
                  >
                    Từ chối
                  </button>
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="panel-card daily-summary-panel profile-activity-progress-panel">
        <button
          type="button"
          className="daily-summary-head"
          onClick={() => setProgressTrackingExpanded((value) => !value)}
          aria-expanded={progressTrackingExpanded}
        >
          <span className="daily-summary-title">
            Theo dõi tiến độ
            {progressTrackingRowCount > 0 ? ` (${progressTrackingRowCount})` : ''}
          </span>
          <span className="daily-summary-toggle">
            {progressTrackingExpanded ? 'Thu gọn' : 'Mở rộng'}
          </span>
        </button>
        {progressTrackingExpanded && (
          <div className="daily-summary-body">
            {progressTracking.length > 0 ? (
              <div className="profile-activity-progress-activities">
                {progressTracking.map((activityBlock) => {
                  const expanded = isProgressActivityExpanded(activityBlock.activity_id);
                  return (
                    <div
                      key={activityBlock.activity_id}
                      className="profile-activity-progress-activity"
                    >
                      <button
                        type="button"
                        className="profile-activity-progress-activity-head"
                        onClick={() => toggleProgressActivity(activityBlock.activity_id)}
                        aria-expanded={expanded}
                      >
                        <span className="profile-activity-progress-activity-title">
                          {activityBlock.activity_name}
                        </span>
                        <span className="daily-summary-toggle">
                          {expanded ? 'Thu gọn' : 'Mở rộng'}
                        </span>
                      </button>
                      {expanded && (
                        <div className="profile-activity-progress-activity-body">
                          <div className="table-wrap">
                            <table className="profile-activity-progress-table">
                              <thead>
                                <tr>
                                  <th>Loại</th>
                                  <th>Tên</th>
                                  <th>Ngày bắt đầu</th>
                                  <th>Trạng thái</th>
                                  <th>Xóa</th>
                                </tr>
                              </thead>
                              <tbody>
                                <ProgressTrackingRows
                                  rows={activityBlock.rows || []}
                                  activityId={activityBlock.activity_id}
                                  saving={saving}
                                  onDelete={handleRemoveProgressTracking}
                                />
                              </tbody>
                            </table>
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            ) : (
              <p className="profile-activity-progress-empty muted">
                Chưa có tiến độ nào được theo dõi. Tiến độ sẽ xuất hiện sau khi mentee báo danh và bắt
                đầu keep track.
              </p>
            )}
          </div>
        )}
      </div>

      <div className="panel-card daily-summary-panel">
        <button
          type="button"
          className="daily-summary-head"
          onClick={() => setCreateFormCollapsed((v) => !v)}
          aria-expanded={!createFormCollapsed}
        >
          <span className="daily-summary-title">Tạo hoạt động</span>
          <span className="daily-summary-toggle">
            {createFormCollapsed ? 'Mở rộng' : 'Thu gọn'}
          </span>
        </button>
        {!createFormCollapsed && (
          <div className="daily-summary-body">
            <div className="profile-activity-bulk-import">
              <div className="action-cell">
                <label
                  className={`btn btn-outline btn-sm${bulkImportLoading ? ' btn-disabled' : ''}`}
                  title="Tạo hàng loạt từ file Excel (cột Link và Mô tả gốc)"
                >
                  {bulkImportLoading ? 'Đang phân tích...' : '+ File'}
                  <input
                    type="file"
                    accept=".xlsx"
                    hidden
                    disabled={bulkImportLoading}
                    onChange={handleBulkImportFile}
                  />
                </label>
                <span className="muted field-hint">
                  Upload file Excel (cột Link, Mô tả gốc) để tạo hàng loạt hoạt động — xem trước và duyệt
                  bên dưới
                </span>
              </div>
              {bulkImportSkipped.length > 0 && (
                <ul className="profile-activity-bulk-import-skipped muted">
                  {bulkImportSkipped.map((row) => (
                    <li key={row.row_index}>Bỏ qua dòng {row.row_index}: thiếu Mô tả gốc</li>
                  ))}
                </ul>
              )}
              {bulkImportRows.length > 0 && (
                <div className="profile-activity-bulk-import-preview">
                  <p className="profile-activity-feed-preview-label">
                    Xem trước feed ({bulkImportRows.length} dòng)
                  </p>
                  <p className="muted profile-activity-feed-preview-hint">
                    Kiểm tra/sửa các trường rồi chọn dòng cần duyệt — Tên hoạt động tự cập nhật theo các
                    trường bên dưới
                  </p>
                  <div className="table-wrap">
                    <table>
                      <thead>
                        <tr>
                          <th>
                            <input
                              type="checkbox"
                              checked={allBulkImportSelected}
                              onChange={toggleAllBulkImportRows}
                            />
                          </th>
                          <th>Tên hoạt động (tự động)</th>
                          <th>Link</th>
                          <th>Loại hoạt động</th>
                          <th>Đơn vị tổ chức</th>
                          <th>Nội dung</th>
                          <th>Đối tượng</th>
                          <th>Khối ngành phù hợp</th>
                          <th>Deadline</th>
                          <th>Hình thức tham gia</th>
                          <th>Mức độ quan trọng</th>
                          <th>Giới hạn số người</th>
                          <th>Ghi chú (nội bộ)</th>
                          <th>SĐT Zalo người giới thiệu</th>
                        </tr>
                      </thead>
                      <tbody>
                        {bulkImportRows.map((row) => (
                          <tr key={row.row_index}>
                            <td>
                              <input
                                type="checkbox"
                                checked={Boolean(row._selected)}
                                onChange={() => toggleBulkImportRowSelected(row.row_index)}
                              />
                            </td>
                            <td>
                              <div>{row.activity_name}</div>
                              {row._error && <p className="form-error">{row._error}</p>}
                            </td>
                            <td>
                              <input
                                value={row.link}
                                onChange={(e) => updateBulkImportRow(row.row_index, 'link', e.target.value)}
                              />
                            </td>
                            <td>
                              <select
                                value={row.activity_type}
                                onChange={(e) =>
                                  updateBulkImportRow(row.row_index, 'activity_type', e.target.value)
                                }
                              >
                                {ACTIVITY_TYPES.map((item) => (
                                  <option key={item} value={item}>
                                    {item}
                                  </option>
                                ))}
                              </select>
                            </td>
                            <td>
                              <input
                                value={row.organizer}
                                onChange={(e) =>
                                  updateBulkImportRow(row.row_index, 'organizer', e.target.value)
                                }
                              />
                            </td>
                            <td>
                              <input
                                value={row.content}
                                onChange={(e) =>
                                  updateBulkImportRow(row.row_index, 'content', e.target.value)
                                }
                              />
                            </td>
                            <td>
                              <input
                                value={row.target_audience}
                                onChange={(e) =>
                                  updateBulkImportRow(row.row_index, 'target_audience', e.target.value)
                                }
                              />
                            </td>
                            <td>
                              <div className="profile-activity-bulk-import-majors">
                                {MAJORS.map((major) => (
                                  <label key={major} className="checkbox-label">
                                    <input
                                      type="checkbox"
                                      checked={(row.suitable_majors || []).includes(major)}
                                      onChange={() => toggleBulkImportRowMajor(row.row_index, major)}
                                    />
                                    {major}
                                  </label>
                                ))}
                              </div>
                              {(row.suitable_majors || []).includes('Khác') && (
                                <input
                                  className="profile-activity-bulk-import-major-other"
                                  value={row.suitable_majors_other || ''}
                                  onChange={(e) =>
                                    updateBulkImportRow(row.row_index, 'suitable_majors_other', e.target.value)
                                  }
                                  placeholder="Ngành khác (ghi rõ)"
                                />
                              )}
                            </td>
                            <td>
                              <input
                                value={row.deadline}
                                onChange={(e) =>
                                  updateBulkImportRow(row.row_index, 'deadline', e.target.value)
                                }
                              />
                            </td>
                            <td>
                              <select
                                value={row.participation_mode}
                                onChange={(e) =>
                                  updateBulkImportRow(row.row_index, 'participation_mode', e.target.value)
                                }
                              >
                                {PARTICIPATION_MODE_OPTIONS.map((item) => (
                                  <option key={item.value} value={item.value}>
                                    {item.label}
                                  </option>
                                ))}
                              </select>
                            </td>
                            <td>
                              <StarRating
                                value={row.importance}
                                onChange={(n) => updateBulkImportRow(row.row_index, 'importance', n)}
                              />
                            </td>
                            <td>
                              <input
                                type="number"
                                min="0"
                                className="profile-activity-bulk-import-limit"
                                value={row.participant_limit || ''}
                                onChange={(e) =>
                                  updateBulkImportRow(row.row_index, 'participant_limit', e.target.value)
                                }
                                placeholder="Không giới hạn"
                              />
                            </td>
                            <td>
                              <textarea
                                className="profile-activity-bulk-import-note"
                                rows={2}
                                value={row.internal_note || ''}
                                onChange={(e) =>
                                  updateBulkImportRow(row.row_index, 'internal_note', e.target.value)
                                }
                                placeholder="Ghi chú nội bộ..."
                              />
                            </td>
                            <td>
                              <input
                                type="tel"
                                className="profile-activity-bulk-import-referrer-phone"
                                value={row.referrer_zalo_phone || ''}
                                onChange={(e) =>
                                  updateBulkImportRow(row.row_index, 'referrer_zalo_phone', e.target.value)
                                }
                                placeholder="0901234567"
                                inputMode="numeric"
                              />
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  {isL2 && (
                    <p className="muted profile-activity-l2-note">
                      Hoạt động của mentor cấp 2 cần được mentor cấp 1 duyệt trước khi mentee thấy.
                    </p>
                  )}
                  <div className="action-cell">
                    <button
                      type="button"
                      className="btn btn-primary btn-sm"
                      onClick={handleBulkApprove}
                      disabled={bulkApproving || !bulkImportRows.some((row) => row._selected)}
                    >
                      {isL2 ? 'Gửi duyệt hàng loạt' : 'Duyệt hàng loạt'} (
                      {bulkImportRows.filter((row) => row._selected).length})
                    </button>
                  </div>
                </div>
              )}
            </div>
            <div className="auth-form profile-activity-form">
              <ActivityContentFields
                form={form}
                updateField={updateForm}
                toggleMajor={toggleMajor}
                onParse={handleParse}
                parsing={saving}
              />
          {isL2 && (
            <p className="muted profile-activity-l2-note">
              Hoạt động của mentor cấp 2 cần được mentor cấp 1 duyệt trước khi mentee thấy.
            </p>
          )}
          <button type="button" className="btn btn-primary" onClick={handleCreate} disabled={saving}>
            {isL2 ? 'Gửi duyệt' : 'Đăng hoạt động'}
          </button>
            </div>
          </div>
        )}
      </div>

      <div className="panel-card daily-summary-panel" ref={manageSectionRef}>
        <button
          type="button"
          className="daily-summary-head"
          onClick={() => setManageFormCollapsed((v) => !v)}
          aria-expanded={!manageFormCollapsed}
        >
          <span className="daily-summary-title">Quản lý hoạt động</span>
          <span className="daily-summary-toggle">
            {manageFormCollapsed ? 'Mở rộng' : 'Thu gọn'}
          </span>
        </button>
        {!manageFormCollapsed && (
          <div className="daily-summary-body">
        <label>
          Chọn hoạt động
          <ActivityPickerDropdown
            activities={activities}
            value={selectedId}
            onChange={setSelectedId}
          />
        </label>

        {selectedActivity && (
          <div className="profile-activity-management">
            <div className="profile-activity-management-summary">
              <span className="importance-stars-display" title="Mức độ quan trọng">
                {formatImportanceStars(selectedActivity.importance)}
              </span>
              {renderApprovalBadge(selectedActivity)}
              <FeedLinePreview activity={selectedActivity} />
              {renderDeadlineBadge(selectedActivity)}
              <span className="muted">
                · {selectedActivity.registration_count || 0} báo danh
              </span>
              {Boolean(selectedActivity.participant_limit) && (
                <span
                  className={`muted profile-activity-capacity-badge${
                    (selectedActivity.approved_participant_count || 0) >= selectedActivity.participant_limit
                      ? ' is-full'
                      : ''
                  }`}
                >
                  · Đã duyệt {selectedActivity.approved_participant_count || 0}/
                  {selectedActivity.participant_limit}
                  {(selectedActivity.approved_participant_count || 0) >= selectedActivity.participant_limit
                    ? ' — đã đủ số lượng'
                    : ''}
                </span>
              )}
            </div>
            <div className="action-cell">
              <button
                type="button"
                className="btn btn-outline btn-sm"
                onClick={openInvitePanel}
                disabled={editSaving || saving || inviteSaving || !canInviteMentees}
                title={
                  canInviteMentees
                    ? undefined
                    : 'Hoạt động cần được duyệt trước khi mời mentee'
                }
              >
                {inviteOpen ? 'Đóng mời tham gia' : 'Mời tham gia'}
              </button>
              <button
                type="button"
                className="btn btn-outline btn-sm"
                onClick={() => {
                  if (editOpen) {
                    setEditOpen(false);
                    setEditForm(activityToForm(selectedActivity));
                  } else {
                    setEditForm(activityToForm(selectedActivity));
                    setEditOpen(true);
                  }
                }}
                disabled={editSaving || saving}
              >
                {editOpen ? 'Hủy chỉnh sửa' : 'Chỉnh sửa nội dung'}
              </button>
              <button
                type="button"
                className="btn btn-outline btn-sm"
                onClick={() => handleDeleteActivity(selectedActivity)}
                disabled={saving || editSaving}
              >
                Xóa HDNK
              </button>
            </div>
            {inviteOpen && (
              <div className="profile-activity-invite-panel">
                <p className="profile-activity-edit-form-title">Mời mentee tham gia hoạt động</p>
                <p className="muted profile-activity-invite-hint">
                  Chọn mentee cần mời — tên hiển thị theo định dạng Tên (khối ngành-hướng NC-hệ).
                </p>
                {inviteMenteesLoading ? (
                  <p className="muted">Đang tải danh sách mentee…</p>
                ) : inviteCandidates.length === 0 ? (
                  <p className="muted">Không còn mentee nào để mời (đã báo danh hết).</p>
                ) : (
                  <ul className="profile-activity-invite-list">
                    {inviteCandidates.map((mentee) => {
                      const alreadyInvited = invitedMenteeIds.has(mentee.id);
                      const checked =
                        inviteSelectedIds.includes(mentee.id) || alreadyInvited;
                      return (
                        <li key={mentee.id}>
                          <label className="profile-activity-invite-option checkbox-label">
                            <input
                              type="checkbox"
                              checked={checked}
                              disabled={alreadyInvited}
                              onChange={() => toggleInviteMentee(mentee.id)}
                            />
                            <span>
                              {formatMenteeActivityInviteOption(mentee)}
                              {alreadyInvited ? (
                                <span className="muted"> · đã mời</span>
                              ) : null}
                            </span>
                          </label>
                        </li>
                      );
                    })}
                  </ul>
                )}
                <div className="action-cell">
                  <button
                    type="button"
                    className="btn btn-primary btn-sm"
                    onClick={handleSendInvites}
                    disabled={
                      inviteSaving ||
                      inviteMenteesLoading ||
                      inviteSelectedIds.length === 0
                    }
                  >
                    Gửi lời mời ({inviteSelectedIds.length})
                  </button>
                </div>
              </div>
            )}
            {editOpen && (
              <div className="profile-activity-edit-form auth-form profile-activity-form">
                <p className="profile-activity-edit-form-title">Chỉnh sửa nội dung hoạt động</p>
                <ActivityContentFields
                  form={editForm}
                  updateField={updateEditForm}
                  toggleMajor={toggleEditMajor}
                  onParse={handleEditParse}
                  parsing={editSaving}
                />
                <div className="action-cell">
                  <button
                    type="button"
                    className="btn btn-primary btn-sm"
                    onClick={handleSaveEdit}
                    disabled={editSaving}
                  >
                    Lưu thay đổi
                  </button>
                </div>
              </div>
            )}
            {!editOpen && (
              <>
            {(selectedActivity.suitable_majors || []).length > 0 && (
              <p className="muted">
                Ngành phù hợp: {(selectedActivity.suitable_majors || []).join(', ')}
                {selectedActivity.suitable_majors_other
                  ? ` (${selectedActivity.suitable_majors_other})`
                  : ''}
              </p>
            )}
            {selectedParticipationLabel && (
              <p className="muted">Hình thức tham gia: {selectedParticipationLabel}</p>
            )}
            {selectedActivity.internal_note && (
              <p className="muted profile-activity-internal-note">
                Ghi chú (nội bộ): {selectedActivity.internal_note}
              </p>
            )}
            {selectedActivity.referrer_zalo_phone && (
              <p className="muted">
                SĐT Zalo người giới thiệu: {selectedActivity.referrer_zalo_phone}
              </p>
            )}
              </>
            )}
            {canReview && selectedActivity.approval_status === 'pending_l1_approval' && (
              <div className="action-cell">
                <button
                  type="button"
                  className="btn btn-primary btn-sm"
                  onClick={() => handleApprove(selectedActivity.id)}
                  disabled={saving}
                >
                  Duyệt
                </button>
                <button
                  type="button"
                  className="btn btn-outline btn-sm"
                  onClick={() => handleReject(selectedActivity.id)}
                  disabled={saving}
                >
                  Từ chối
                </button>
              </div>
            )}
            <div className="profile-activity-registrations">
              {unassignedRegistrations.length > 0 && (
                <div className="profile-activity-registration-group">
                  <h4 className="profile-activity-registration-section-title">
                    Chờ phân nhóm ({unassignedRegistrations.length})
                  </h4>
                  <div className="table-wrap">
                    <table>
                      <thead>
                        <tr>
                          <th />
                          <th>Tên</th>
                          <th>Zalo</th>
                          <th>Ngành apply</th>
                          <th>Hình thức</th>
                          <th>Thao tác</th>
                        </tr>
                      </thead>
                      <tbody>
                        {unassignedRegistrations.map((item) => (
                          <tr key={item.mentee_id}>
                            <td>
                              <input
                                type="checkbox"
                                checked={selectedMentees.includes(item.mentee_id)}
                                onChange={() => toggleMentee(item.mentee_id)}
                              />
                            </td>
                            <td>{renderMenteeNameCell(item)}</td>
                            <td>{item.zalo_phone || '—'}</td>
                            <td>{item.apply_major || '—'}</td>
                            <td>{renderParticipationCell(item)}</td>
                            <td>{renderUnassignedActions(item)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <div className="action-cell">
                    <input
                      placeholder="Tên nhóm"
                      value={groupName}
                      onChange={(e) => setGroupName(e.target.value)}
                    />
                    <button
                      type="button"
                      className="btn btn-outline btn-sm"
                      onClick={handleCreateGroup}
                      disabled={saving}
                    >
                      Tạo nhóm
                    </button>
                  </div>
                </div>
              )}

              {(selectedActivity.groups || []).map((group) => {
                const groupMembers = (group.mentee_ids || [])
                  .map((menteeId) => registrationByMenteeId.get(menteeId))
                  .filter(Boolean);
                if (!groupMembers.length && group.approval_status === 'pending_l1_approval') {
                  return null;
                }
                return (
                  <div key={group.group_id} className="profile-activity-registration-group">
                    {renderGroupSectionHead(group)}
                    {groupMembers.length > 0 && (
                      <div className="table-wrap">
                        <table>
                          <thead>
                            <tr>
                              <th>Tên</th>
                              <th>Zalo</th>
                              <th>Ngành apply</th>
                              <th>Hình thức</th>
                              <th>Thao tác</th>
                            </tr>
                          </thead>
                          <tbody>
                            {groupMembers.map((item) => (
                              <tr key={item.mentee_id}>
                                <td>
                                  {renderMenteeNameCell(item)}
                                  {group.leader_mentee_id === item.mentee_id && (
                                    <div className="muted profile-activity-keeptrack-mentee-summary">
                                      Nhóm trưởng
                                    </div>
                                  )}
                                </td>
                                <td>{item.zalo_phone || '—'}</td>
                                <td>{item.apply_major || '—'}</td>
                                <td>{renderParticipationCell(item)}</td>
                                <td>{renderGroupMemberActions(item, group)}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}
          </div>
        )}
      </div>
    </>
  );
}
