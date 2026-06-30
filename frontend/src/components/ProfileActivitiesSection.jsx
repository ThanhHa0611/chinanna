import { useEffect, useMemo, useState } from 'react';
import { api } from '../services/api';
import { format_activity_feed_line, getDeadlineBadge } from '../utils/profileActivities';

export default function ProfileActivitiesSection({ user }) {
  const [days, setDays] = useState([]);
  const [hiddenDays, setHiddenDays] = useState([]);
  const [expanded, setExpanded] = useState(true);
  const [showOld, setShowOld] = useState(false);
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const refresh = async () => {
    const data = await api.getProfileActivities();
    setDays(data.days || []);
    setHiddenDays(data.hidden_days || []);
  };

  useEffect(() => {
    setLoading(true);
    refresh()
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [user?.id]);

  const totalItems = useMemo(
    () =>
      [...days, ...(showOld ? hiddenDays : [])].reduce(
        (sum, day) => sum + (day.items || []).length,
        0,
      ),
    [days, hiddenDays, showOld],
  );

  const openDetail = async (itemId) => {
    try {
      const data = await api.getProfileActivityDetail(itemId);
      setDetail(data);
      await refresh();
    } catch (err) {
      setError(err.message);
    }
  };

  const hideActivity = async (itemId) => {
    try {
      await api.hideProfileActivity(itemId, { hidden: true });
      await refresh();
    } catch (err) {
      setError(err.message);
    }
  };

  const registerActivity = async (itemId) => {
    try {
      await api.registerProfileActivity(itemId);
      await refresh();
    } catch (err) {
      setError(err.message);
    }
  };

  const respondGroup = async (itemId, status) => {
    try {
      await api.respondProfileActivityGroup(itemId, { status });
      if (detail?.id === itemId) {
        const data = await api.getProfileActivityDetail(itemId);
        setDetail(data);
      }
      await refresh();
    } catch (err) {
      setError(err.message);
    }
  };

  const renderDeadlineBadge = (item) => {
    const badge = getDeadlineBadge(item.deadline, item.deadline_badge);
    if (!badge) return null;
    return (
      <span className={`profile-activity-deadline-badge is-${badge.variant}`}>{badge.label}</span>
    );
  };

  const renderItem = (item) => {
    const line = format_activity_feed_line(item, user);
    return (
      <div
        key={item.id}
        className={`profile-activity-line ${item.read ? 'is-read' : 'is-unread'}`}
      >
        <div className="profile-activity-line-main">
          <span className="profile-activity-dot">•</span>
          <button
            type="button"
            className="profile-activity-link-btn"
            onClick={() => openDetail(item.id)}
          >
            {item.highlight_star ? '⭐ ' : ''}
            {line}
            {renderDeadlineBadge(item)}
          </button>
        </div>
        <div className="profile-activity-line-actions">
          {!item.registered && (
            <button type="button" className="btn btn-outline btn-sm" onClick={() => registerActivity(item.id)}>
              Báo danh
            </button>
          )}
          <button type="button" className="btn btn-outline btn-sm" onClick={() => hideActivity(item.id)}>
            Ẩn
          </button>
        </div>
      </div>
    );
  };

  return (
    <>
      <h2>Hoạt động làm đẹp hồ sơ</h2>
      <p className="profile-panel-desc">
        Theo dõi và đăng ký các hoạt động hỗ trợ làm đẹp hồ sơ apply.
      </p>

      <div className="profile-card">
        <div className="profile-activities-head">
          <button type="button" className="btn btn-outline btn-sm" onClick={() => setExpanded((v) => !v)}>
            {expanded ? 'Thu gọn' : 'Mở rộng'}
          </button>
        </div>
        {error && <p className="form-error">{error}</p>}
        {loading ? (
          <p className="profile-note">Đang tải hoạt động...</p>
        ) : !expanded ? (
          <p className="muted">Có {totalItems} hoạt động.</p>
        ) : (
          <div className="profile-activities-days">
          {days.map((day) => (
            <div key={day.date_key} className="profile-activities-day">
              <h4>Ngày {day.date_label}</h4>
              <div className="profile-activities-list">{(day.items || []).map(renderItem)}</div>
            </div>
          ))}
          {hiddenDays.length > 0 && (
            <div className="profile-activities-old">
              <button type="button" className="btn btn-outline btn-sm" onClick={() => setShowOld((v) => !v)}>
                {showOld ? 'Ẩn hoạt động cũ' : `Xem ${hiddenDays.length} ngày cũ hơn`}
              </button>
              {showOld &&
                hiddenDays.map((day) => (
                  <div key={day.date_key} className="profile-activities-day">
                    <h4>Ngày {day.date_label}</h4>
                    <div className="profile-activities-list">{(day.items || []).map(renderItem)}</div>
                  </div>
                ))}
            </div>
          )}
          </div>
        )}
      </div>

      {detail && (
        <div className="modal-backdrop" onClick={() => setDetail(null)} role="presentation">
          <div className="modal-card profile-activity-modal" onClick={(e) => e.stopPropagation()}>
            <h3>{detail.activity_name}</h3>
            <p><strong>Loại:</strong> {detail.activity_type || 'Khác'}</p>
            {detail.organizer && <p><strong>Đơn vị:</strong> {detail.organizer}</p>}
            {detail.content && <p><strong>Nội dung:</strong> {detail.content}</p>}
            {detail.target_audience && <p><strong>Đối tượng:</strong> {detail.target_audience}</p>}
            {detail.deadline && (
              <p>
                <strong>Deadline:</strong> {detail.deadline}
                {renderDeadlineBadge(detail)}
              </p>
            )}
            {detail.link && (
              <p>
                <strong>Link:</strong>{' '}
                <a href={detail.link} target="_blank" rel="noreferrer">
                  Mở liên kết
                </a>
              </p>
            )}
            {detail.attachment_url && (
              <p>
                <strong>Đính kèm:</strong>{' '}
                <a href={detail.attachment_url} target="_blank" rel="noreferrer">
                  Xem file
                </a>
              </p>
            )}
            {detail.description && <p><strong>Mô tả:</strong> {detail.description}</p>}
            {detail.group_response_status === 'pending' && (
              <div className="action-cell">
                <button type="button" className="btn btn-outline btn-sm" onClick={() => respondGroup(detail.id, 'confirmed')}>
                  Xác nhận nhóm
                </button>
                <button type="button" className="btn btn-outline btn-sm" onClick={() => respondGroup(detail.id, 'rejected')}>
                  Từ chối nhóm
                </button>
              </div>
            )}
            <div className="modal-actions">
              <button type="button" className="btn btn-outline btn-sm" onClick={() => setDetail(null)}>
                Đóng
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
