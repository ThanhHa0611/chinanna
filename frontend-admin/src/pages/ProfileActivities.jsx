import { useEffect, useMemo, useState } from 'react';
import { api } from '../services/api';

const ACTIVITY_TYPES = ['Cuộc thi', 'NCKH', 'HĐNK', 'Hội thảo', 'Chương trình hè', 'Dự án', 'Khác'];
const MAJORS = [
  'Kinh tế',
  'Kỹ thuật',
  'Logistics',
  'Truyền thông',
  'Giáo dục',
  'Ngôn ngữ',
  'Y sinh',
  'Nghệ thuật',
  'Xã hội học',
  'Khác',
];

function emptyForm() {
  return {
    link: '',
    description: '',
    activity_name: '',
    activity_type: 'Khác',
    deadline: '',
    organizer: '',
    target_audience: '',
    content: '',
    attachment_url: '',
    suitable_majors: [],
  };
}

export default function ProfileActivities() {
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

  const selectedActivity = useMemo(
    () => activities.find((item) => item.id === selectedId) || null,
    [activities, selectedId],
  );

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

  const updateForm = (key, value) => {
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  const toggleMajor = (major) => {
    setForm((prev) => {
      const has = prev.suitable_majors.includes(major);
      return {
        ...prev,
        suitable_majors: has
          ? prev.suitable_majors.filter((item) => item !== major)
          : [...prev.suitable_majors, major],
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
        ...parsed,
        suitable_majors: parsed.suitable_majors || [],
      }));
      setMessage('Đã phân tích mô tả. Bạn kiểm tra lại rồi đăng.');
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
      await api.createProfileActivity(form);
      setForm(emptyForm());
      await loadActivities();
      setMessage('Đã đăng hoạt động mới.');
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
    setSaving(true);
    setError('');
    setMessage('');
    try {
      await api.upsertProfileActivityGroup(selectedActivity.id, {
        group_name: groupName || 'Nhóm mới',
        mentee_ids: selectedMentees,
      });
      setSelectedMentees([]);
      setGroupName('');
      await loadActivities();
      await loadRegistrations(selectedActivity.id);
      setMessage('Đã tạo nhóm.');
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
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

  if (loading) return <p className="loader">Đang tải...</p>;

  return (
    <>
      <div className="page-head">
        <h2>Hoạt động làm đẹp hồ sơ</h2>
        <p>Tạo hoạt động, quản lý báo danh, chia nhóm và chốt sync HDNK + NCKH.</p>
      </div>

      {error && <p className="form-error">{error}</p>}
      {message && <p className="form-success">{message}</p>}

      <div className="panel-card">
        <h3>Tạo hoạt động</h3>
        <div className="auth-form profile-activity-form">
          <label>
            Link
            <input value={form.link} onChange={(e) => updateForm('link', e.target.value)} />
          </label>
          <label>
            Mô tả gốc
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
            Tên hoạt động
            <input
              value={form.activity_name}
              onChange={(e) => updateForm('activity_name', e.target.value)}
            />
          </label>
          <label>
            Loại hoạt động
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
            Nội dung
            <input value={form.content} onChange={(e) => updateForm('content', e.target.value)} />
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
          </div>
          <button type="button" className="btn btn-primary" onClick={handleCreate} disabled={saving}>
            Đăng hoạt động
          </button>
        </div>
      </div>

      <div className="panel-card">
        <h3>Quản lý hoạt động</h3>
        <label>
          Chọn hoạt động
          <select value={selectedId} onChange={(e) => setSelectedId(e.target.value)}>
            <option value="">-- Chọn --</option>
            {activities.map((item) => (
              <option key={item.id} value={item.id}>
                {item.activity_name} ({item.registration_count || 0} báo danh)
              </option>
            ))}
          </select>
        </label>

        {selectedActivity && (
          <div className="profile-activity-management">
            <p>
              <strong>{selectedActivity.activity_name}</strong> · {selectedActivity.registration_count || 0} báo
              danh
            </p>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th />
                    <th>Tên</th>
                    <th>Zalo</th>
                    <th>Ngành apply</th>
                    <th>Nhóm</th>
                    <th>Phản hồi</th>
                  </tr>
                </thead>
                <tbody>
                  {registrations.map((item) => (
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
                      <td>{item.group_name || '—'}</td>
                      <td>{item.group_response_status || 'pending'}</td>
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
              <button type="button" className="btn btn-outline btn-sm" onClick={handleCreateGroup} disabled={saving}>
                Tạo nhóm
              </button>
            </div>

            <div className="profile-activity-groups">
              {(selectedActivity.groups || []).map((group) => (
                <div key={group.group_id} className="panel-card">
                  <p>
                    <strong>{group.group_name}</strong> ({(group.mentee_ids || []).length} thành viên)
                  </p>
                  <div className="action-cell">
                    <button
                      type="button"
                      className="btn btn-outline btn-sm"
                      onClick={() => handleNotifyGroup(group.group_id)}
                      disabled={saving}
                    >
                      Gửi thông báo nhóm
                    </button>
                    <button
                      type="button"
                      className="btn btn-primary btn-sm"
                      onClick={() => handleFinalizeGroup(group.group_id)}
                      disabled={saving}
                    >
                      Chốt nhóm
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </>
  );
}
