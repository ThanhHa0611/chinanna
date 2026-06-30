import { useEffect, useMemo, useState } from 'react';
import { api } from '../services/api';
import {
  feedLineLink,
  feedLineText,
  formatImportanceStars,
  getDeadlineBadge,
} from '../utils/profileActivities';

function FeedLine({ item, onLinkClick }) {
  const text = feedLineText(item);
  const link = feedLineLink(item);

  return (
    <div className="profile-activity-feed-text">
      <div>
        {item.highlight_star ? '⭐ ' : ''}
        {item.importance > 0 && (
          <span className="importance-stars-display" title="Mức độ quan trọng">
            {formatImportanceStars(item.importance)}{' '}
          </span>
        )}
        {text}
      </div>
      {link && (
        <div className="profile-activity-feed-link-line">
          Link:{' '}
          <a
            href={link}
            target="_blank"
            rel="noreferrer"
            className="profile-activity-inline-link"
            onClick={onLinkClick}
          >
            {link}
          </a>
        </div>
      )}
    </div>
  );
}

export default function ProfileActivitiesSection({ user }) {
  const [days, setDays] = useState([]);
  const [hiddenDays, setHiddenDays] = useState([]);
  const [expanded, setExpanded] = useState(true);
  const [showOld, setShowOld] = useState(false);
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

  const markRead = async (itemId) => {
    try {
      await api.markProfileActivityRead(itemId);
      await refresh();
    } catch {
      // best effort
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

  const renderItem = (item) => (
    <div
      key={item.id}
      className={`profile-activity-line ${item.read ? 'is-read' : 'is-unread'}`}
    >
      <div className="profile-activity-line-main">
        <span className="profile-activity-dot">•</span>
        <div className="profile-activity-line-content">
          <FeedLine
            item={item}
            onLinkClick={() => {
              if (!item.read) markRead(item.id);
            }}
          />
          {renderDeadlineBadge(item)}
        </div>
      </div>
      <div className="profile-activity-line-actions">
        {item.group_assignment_pending && (
          <>
            <button
              type="button"
              className="btn btn-outline btn-sm"
              onClick={() => respondGroup(item.id, 'confirmed')}
            >
              Xác nhận nhóm
            </button>
            <button
              type="button"
              className="btn btn-outline btn-sm"
              onClick={() => respondGroup(item.id, 'rejected')}
            >
              Từ chối nhóm
            </button>
          </>
        )}
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
    </>
  );
}
