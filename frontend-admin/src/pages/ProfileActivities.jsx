import { useEffect, useMemo, useState } from 'react';
import ActivityKeeptrackBar from '../components/ActivityKeeptrackBar';
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
  const [keeptrackSaving, setKeeptrackSaving] = useState({});

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
    setActivities(data || []);
    if (!selectedId && data?.length) {
      setSelectedId(data[0].id);
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

  useEffect(() => {
    Promise.all([loadActivities()])
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    loadRegistrations(selectedId).catch(() => {});
  }, [selectedId]);

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
    const name = (groupName || '').trim();
    if (!name) {
      setError('Vui lòng nhập hoặc gợi ý tên nhóm trước khi tạo.');
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
            : 'Đã tạo nhóm.'),
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

  const handleSuggestGroupName = async () => {
    if (!selectedActivity) return;
    setSaving(true);
    setError('');
    try {
      const data = await api.suggestProfileActivityGroupName(selectedActivity.id);
      setGroupName(data?.suggested_name || '');
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

  const handleNotifyGroup = async (groupId) => {
    if (!selectedActivity) return;
    setSaving(true);
    setError('');
    try {
      await api.notifyProfileActivityGroup(selectedActivity.id, groupId);
      await loadActivities();
      await loadRegistrations(selectedActivity.id);
      setMessage('Đã gửi thông báo nhóm.');
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
      setMessage('Đã chốt nhóm và sync HDNK + NCKH.');
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const saveKeeptrack = async (menteeId, body) => {
    if (!selectedActivity) return;
    setKeeptrackSaving((prev) => ({ ...prev, [menteeId]: true }));
    setError('');
    try {
      const result = await api.updateProfileActivityKeeptrack(selectedActivity.id, menteeId, body);
      if (result?.registration) {
        setRegistrations((prev) =>
          prev.map((item) => (item.mentee_id === menteeId ? result.registration : item)),
        );
      } else {
        await loadRegistrations(selectedActivity.id);
      }
      setMessage('Đã cập nhật tiến độ keeptrack.');
    } catch (err) {
      setError(err.message);
    } finally {
      setKeeptrackSaving((prev) => ({ ...prev, [menteeId]: false }));
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
          <select value={selectedId} onChange={(e) => setSelectedId(e.target.value)}>
            <option value="">-- Chọn --</option>
            {activities.map((item) => (
              <option key={item.id} value={item.id}>
                {compose_activity_name(item)} ({item.registration_count || 0} báo danh)
                {item.approval_status === 'pending_l1_approval' ? ' · chờ duyệt' : ''}
              </option>
            ))}
          </select>
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
                    {item.keeptrack?.active && (
                      <tr key={`${item.mentee_id}-keeptrack`} className="profile-activity-keeptrack-row">
                        <td colSpan={8}>
                          <ActivityKeeptrackBar
                            compact
                            keeptrack={item.keeptrack}
                            saving={Boolean(keeptrackSaving[item.mentee_id])}
                            onSave={(body) => saveKeeptrack(item.mentee_id, body)}
                          />
                        </td>
                      </tr>
                    )}
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
              <button
                type="button"
                className="btn btn-outline btn-sm"
                onClick={handleSuggestGroupName}
                disabled={saving}
              >
                Gợi ý tên
              </button>
              <button type="button" className="btn btn-outline btn-sm" onClick={handleCreateGroup} disabled={saving}>
                Tạo nhóm
              </button>
            </div>

            <div className="profile-activity-groups">
              {(selectedActivity.groups || []).map((group) => {
              const groupPending = group.approval_status === 'pending_l1_approval';
              return (
                <div key={group.group_id} className="panel-card">
                  <p>
                    <strong>{group.group_name}</strong> ({(group.mentee_ids || []).length} thành viên)
                    {groupPending && (
                      <span className="profile-activity-approval-badge is-pending">
                        Chờ L1 duyệt
                      </span>
                    )}
                  </p>
                  <div className="action-cell">
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
                    <button
                      type="button"
                      className="btn btn-outline btn-sm"
                      onClick={() => handleNotifyGroup(group.group_id)}
                      disabled={saving || groupPending}
                    >
                      Gửi thông báo nhóm
                    </button>
                    <button
                      type="button"
                      className="btn btn-primary btn-sm"
                      onClick={() => handleFinalizeGroup(group.group_id)}
                      disabled={saving || groupPending}
                    >
                      Chốt nhóm
                    </button>
                  </div>
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
