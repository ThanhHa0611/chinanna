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
  };
}

function StarRating({ value, onChange }) {
  return (
    <div className="importance-stars" role="group" aria-label="Mức độ quan trọng">
      {[1, 2, 3, 4, 5].map((n) => (
        <button
          key={n}
          type="button"
          className={`importance-star${n <= value ? ' is-active' : ''}`}
          onClick={() => onChange(n)}
          aria-label={`${n} sao`}
          aria-pressed={n <= value}
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
  const [createFormCollapsed, setCreateFormCollapsed] = useState(false);
  const [moveTargets, setMoveTargets] = useState({});
  const [addToGroupTargets, setAddToGroupTargets] = useState({});
  const [keeptrackReviews, setKeeptrackReviews] = useState([]);
  const [selectedKeeptrackReviews, setSelectedKeeptrackReviews] = useState([]);
  const [abandonRequests, setAbandonRequests] = useState([]);
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

  const composedName = useMemo(() => compose_activity_name(form), [
    form.activity_type,
    form.organizer,
    form.content,
    form.target_audience,
    form.deadline,
  ]);

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

  useEffect(() => {
    Promise.all([loadActivities(), loadKeeptrackReviews(), loadAbandonRequests()])
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
      setMessage(result?.message || 'Đã chuyển mentee sang nhóm mới.');
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const findMenteeGroupId = (menteeId) => {
    for (const group of selectedActivity?.groups || []) {
      if ((group.mentee_ids || []).includes(menteeId)) {
        return group.group_id;
      }
    }
    return '';
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
      await Promise.all([loadAbandonRequests(), loadActivities()]);
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
            <div className="auth-form profile-activity-form">
          <label>
            Link
            <input value={form.link} onChange={(e) => updateForm('link', e.target.value)} />
          </label>
          <label>
            Mô tả gốc (dùng parse — không hiển thị trên feed)
            <textarea
              rows={4}
              value={form.description}
              onChange={(e) => updateForm('description', e.target.value)}
            />
          </label>
          <div className="action-cell">
            <button type="button" className="btn btn-outline btn-sm" onClick={handleParse} disabled={saving}>
              Parse tự động
            </button>
          </div>
          <label>
            Loại hoạt động
            <span className="field-hint">Tự nhận diện khi parse — có thể chỉnh lại trước khi đăng</span>
            <select
              value={form.activity_type}
              onChange={(e) => updateForm('activity_type', e.target.value)}
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
            <input value={form.deadline} onChange={(e) => updateForm('deadline', e.target.value)} />
          </label>
          <label>
            Đơn vị tổ chức
            <input value={form.organizer} onChange={(e) => updateForm('organizer', e.target.value)} />
          </label>
          <label>
            Đối tượng
            <input
              value={form.target_audience}
              onChange={(e) => updateForm('target_audience', e.target.value)}
            />
          </label>
          <label>
            Hình thức tham gia
            <select
              value={form.participation_mode}
              onChange={(e) => updateForm('participation_mode', e.target.value)}
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
            <input value={form.content} onChange={(e) => updateForm('content', e.target.value)} />
          </label>
          <label>
            Mức độ quan trọng
            <StarRating value={form.importance} onChange={(n) => updateForm('importance', n)} />
          </label>
          <label>
            File đính kèm (URL)
            <input
              value={form.attachment_url}
              onChange={(e) => updateForm('attachment_url', e.target.value)}
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
                  onChange={(e) => updateForm('suitable_majors_other', e.target.value)}
                  placeholder="Ví dụ: Kiến trúc, Du lịch..."
                />
              </label>
            )}
          </div>
          <div className="profile-activity-feed-preview">
            <p className="profile-activity-feed-preview-label">Tên hoạt động (tự động)</p>
            <p className="muted profile-activity-feed-preview-hint">
              Dòng compact hiển thị trên feed mentee — cập nhật theo các trường bên trên
            </p>
            <p className="profile-activity-name-preview">{composedName}</p>
            <p className="profile-activity-feed-preview-label">Xem trước feed</p>
            <FeedLinePreview activity={form} />
          </div>
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

      <div className="panel-card">
        <h3>Quản lý hoạt động</h3>
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
            </div>
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
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th />
                    <th>Tên</th>
                    <th>Zalo</th>
                    <th>Ngành apply</th>
                    <th>Hình thức</th>
                    <th>Nhóm</th>
                    <th>Quản lý nhóm</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {registrations.map((item) => {
                    const currentGroupId = findMenteeGroupId(item.mentee_id);
                    const approvedGroups = (selectedActivity.groups || []).filter(
                      (group) => group.approval_status !== 'pending_l1_approval',
                    );
                    return (
                    <>
                    <tr key={item.mentee_id}>
                      <td>
                        <input
                          type="checkbox"
                          checked={selectedMentees.includes(item.mentee_id)}
                          onChange={() => toggleMentee(item.mentee_id)}
                        />
                      </td>
                      <td>{item.mentee_name}</td>
                      <td>{item.zalo_phone || '—'}</td>
                      <td>{item.apply_major || '—'}</td>
                      <td>{renderParticipationCell(item)}</td>
                      <td>{item.group_name || '—'}</td>
                      <td>
                        <div className="action-cell profile-activity-group-ops">
                          {!currentGroupId && approvedGroups.length > 0 && (
                            <>
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
                                {approvedGroups.map((group) => (
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
                            </>
                          )}
                          {currentGroupId && (
                            <button
                              type="button"
                              className="btn btn-outline btn-sm"
                              onClick={() => handleRemoveMenteeFromGroup(item.mentee_id, currentGroupId)}
                              disabled={saving}
                            >
                              Xóa khỏi nhóm
                            </button>
                          )}
                          {currentGroupId && approvedGroups.length > 1 && (
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
                                <option value="">Chuyển sang...</option>
                                {approvedGroups
                                  .filter((group) => group.group_id !== currentGroupId)
                                  .map((group) => (
                                    <option key={group.group_id} value={group.group_id}>
                                      {group.group_name}
                                    </option>
                                  ))}
                              </select>
                              <button
                                type="button"
                                className="btn btn-outline btn-sm"
                                onClick={() => handleMoveMenteeGroup(item.mentee_id)}
                                disabled={saving}
                              >
                                Chuyển
                              </button>
                            </>
                          )}
                        </div>
                      </td>
                      <td>
                        {!item.pending_l1_reject &&
                          item.response_display_status !== 'rejected' &&
                          item.response_display_status !== 'confirmed' && (
                            <button
                              type="button"
                              className="btn btn-outline btn-sm"
                              onClick={() => handleRejectRegistration(item.mentee_id)}
                              disabled={saving}
                            >
                              Từ chối
                            </button>
                          )}
                      </td>
                    </tr>
                    </>
                    );
                  })}
                </tbody>
              </table>
            </div>

            <div className="action-cell">
              <input
                placeholder="Tên nhóm"
                value={groupName}
                onChange={(e) => setGroupName(e.target.value)}
              />
              <button type="button" className="btn btn-outline btn-sm" onClick={handleCreateGroup} disabled={saving}>
                Tạo nhóm
              </button>
            </div>

            <div className="profile-activity-groups">
              {(selectedActivity.groups || []).map((group) => {
              const groupPending = group.approval_status === 'pending_l1_approval';
              const isFinalized = Boolean(group.finalized_at);
              const showFinalizeSuccess = Boolean(finalizeSuccessByGroup[group.group_id]);
              const showLeaderPicker =
                !group.is_auto_solo &&
                isFinalized &&
                !group.leader_mentee_id &&
                !showFinalizeSuccess &&
                Boolean(leaderPickerVisible[group.group_id]);
              return (
                <div key={group.group_id} className="panel-card">
                  <div className="group-head">
                    <div className="group-head-title">
                      <strong>{group.group_name}</strong> ({(group.mentee_ids || []).length} thành viên)
                      {groupPending && (
                        <span className="profile-activity-approval-badge is-pending">
                          {' '}
                          Chờ L1 duyệt
                        </span>
                      )}
                      {group.is_auto_solo && (
                        <span className="muted"> — Cá nhân, không cần chốt nhóm</span>
                      )}
                    </div>
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
                  </div>
                  {showFinalizeSuccess && (
                    <p className="form-success group-finalize-success">Đã tạo nhóm thành công</p>
                  )}
                  {(group.mentee_ids || []).length > 0 && (
                    <ol className="profile-activity-group-member-list">
                      {(group.mentee_ids || []).map((menteeId) => (
                        <li key={menteeId}>
                          {getMenteeDisplayName(menteeId)}
                          {group.leader_mentee_id === menteeId ? ' (nhóm trưởng)' : ''}
                        </li>
                      ))}
                    </ol>
                  )}
                  {canReview && groupPending && (
                    <div className="action-cell">
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
                    </div>
                  )}
                  {showLeaderPicker && (
                    <div className="action-cell profile-activity-group-leader-picker">
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
                    </div>
                  )}
                </div>
              );
            })}
            </div>
          </div>
        )}
      </div>
    </>
  );
}
