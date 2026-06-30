import { useEffect, useState } from 'react';
import { api } from '../services/api';
import ActivityKeeptrackBar from './ActivityKeeptrackBar';
import {
  MENTEE_PARTICIPATION_CHOICES,
  feedLineLink,
  feedLineText,
  formatImportanceStars,
  getDeadlineBadge,
  participationModeDisplayLabel,
} from '../utils/profileActivities';

function isActivityViewed(item) {
  return Boolean(item?.viewed ?? item?.read);
}

function FeedLine({ item, onLinkClick }) {
  const text = feedLineText(item);
  const link = feedLineLink(item);
  const participationLabel = participationModeDisplayLabel(item);

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
        {link && (
          <>
            {' '}
            <a
              href={link}
              target="_blank"
              rel="noreferrer"
              className="profile-activity-inline-link"
              onClick={onLinkClick}
            >
              (Link)
            </a>
          </>
        )}
      </div>
      {(item.target_audience || participationLabel) && (
        <div className="profile-activity-feed-meta muted">
          {item.target_audience && <span>Đối tượng: {item.target_audience}</span>}
          {item.target_audience && participationLabel && ' · '}
          {participationLabel && (
            <span>Hình thức: {participationLabel}</span>
          )}
        </div>
      )}
    </div>
  );
}

function DayBlock({ day, renderItem }) {
  if (!day?.items?.length) return null;
  return (
    <div className="profile-activities-day">
      <h4>Ngày {day.date_label}</h4>
      <div className="profile-activities-list">{(day.items || []).map(renderItem)}</div>
    </div>
  );
}

export default function ProfileActivitiesSection({ user, unviewedCount = 0, onUnviewedCountChange }) {
  const [currentDay, setCurrentDay] = useState(null);
  const [otherDays, setOtherDays] = useState([]);
  const [expanded, setExpanded] = useState(true);
  const [showOther, setShowOther] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [registerChoice, setRegisterChoice] = useState({});
  const [keeptrackSaving, setKeeptrackSaving] = useState({});

  const refresh = async () => {
    const data = await api.getProfileActivities();
    setCurrentDay(data.current_day || null);
    setOtherDays(data.other_days || []);
    onUnviewedCountChange?.(data.unviewed_count ?? 0);
  };

  useEffect(() => {
    setLoading(true);
    refresh()
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [user?.id]);

  const markViewed = async (itemId) => {
    try {
      await api.markProfileActivityRead(itemId);
      onUnviewedCountChange?.((count) => Math.max(0, count - 1));
      setCurrentDay((day) =>
        day
          ? {
              ...day,
              items: (day.items || []).map((item) =>
                item.id === itemId ? { ...item, viewed: true, read: true } : item,
              ),
            }
          : day,
      );
      setOtherDays((days) =>
        days.map((day) => ({
          ...day,
          items: (day.items || []).map((item) =>
            item.id === itemId ? { ...item, viewed: true, read: true } : item,
          ),
        })),
      );
    } catch {
      // best effort
    }
  };

  const hideActivity = async (itemId) => {
    if (!window.confirm('Bạn có chắc muốn ẩn hoạt động này?')) return;

    try {
      await api.hideProfileActivity(itemId, { hidden: true });
      await refresh();
    } catch (err) {
      setError(err.message);
    }
  };

  const registerActivity = async (item) => {
    const needsChoice = item.needs_participation_choice;
    const choice = registerChoice[item.id];

    if (needsChoice && !choice) {
      setError('Vui lòng chọn hình thức tham gia: Cá nhân hoặc Nhóm.');
      return;
    }

    const choiceLabel =
      MENTEE_PARTICIPATION_CHOICES.find((row) => row.value === choice)?.label || '';
    const confirmText = needsChoice
      ? `Bạn chọn tham gia ${choiceLabel}. Xác nhận báo danh hoạt động này?`
      : 'Bạn có chắc muốn báo danh hoạt động này?';
    if (!window.confirm(confirmText)) return;

    try {
      await api.registerProfileActivity(
        item.id,
        needsChoice ? { participation_choice: choice } : {},
      );
      setRegisterChoice((prev) => {
        const next = { ...prev };
        delete next[item.id];
        return next;
      });
      setError('');
      await refresh();
    } catch (err) {
      setError(err.message);
    }
  };

  const respondGroup = async (itemId, status) => {
    try {
      const result = await api.respondProfileActivityGroup(itemId, { status });
      if (result?.activity) {
        const patchItem = (item) => (item.id === itemId ? { ...item, ...result.activity } : item);
        setCurrentDay((day) =>
          day ? { ...day, items: (day.items || []).map(patchItem) } : day,
        );
        setOtherDays((days) =>
          days.map((day) => ({ ...day, items: (day.items || []).map(patchItem) })),
        );
      }
      await refresh();
    } catch (err) {
      setError(err.message);
    }
  };

  const saveKeeptrack = async (itemId, body) => {
    setKeeptrackSaving((prev) => ({ ...prev, [itemId]: true }));
    try {
      const result = await api.updateProfileActivityKeeptrack(itemId, body);
      if (result?.activity) {
        const patchItem = (item) => (item.id === itemId ? { ...item, ...result.activity } : item);
        setCurrentDay((day) =>
          day ? { ...day, items: (day.items || []).map(patchItem) } : day,
        );
        setOtherDays((days) =>
          days.map((day) => ({ ...day, items: (day.items || []).map(patchItem) })),
        );
      }
      setError('');
    } catch (err) {
      setError(err.message);
    } finally {
      setKeeptrackSaving((prev) => ({ ...prev, [itemId]: false }));
    }
  };

  const renderDeadlineBadge = (item) => {
    const badge = getDeadlineBadge(item.deadline, item.deadline_badge);
    if (!badge) return null;
    return (
      <span className={`profile-activity-deadline-badge is-${badge.variant}`}>{badge.label}</span>
    );
  };

  const renderRegistrationStatus = (item) => {
    if (item.group_assignment_pending && item.group_name) {
      return (
        <span className="muted profile-activity-group-invite-text">
          Mentor mời bạn vào {item.group_name}
        </span>
      );
    }
    if (item.registered && item.awaiting_group_assignment) {
      return <span className="muted">Đã báo danh — chờ mentor phân nhóm</span>;
    }
    if (
      item.registered &&
      item.participation_choice === 'individual' &&
      item.group_response_status === 'confirmed'
    ) {
      return <span className="muted">Đã báo danh (Cá nhân)</span>;
    }
    if (item.registered && item.participation_choice_label) {
      return <span className="muted">Đã báo danh ({item.participation_choice_label})</span>;
    }
    if (item.registered) {
      return <span className="muted">Đã báo danh</span>;
    }
    return null;
  };

  const renderGroupMembers = (item) => {
    if (item.group_response_status !== 'confirmed' || !item.group_members?.length) {
      return null;
    }
    return (
      <div className="profile-activity-group-members">
        <p className="profile-activity-group-members-title">Nhóm bao gồm:</p>
        <ol className="profile-activity-group-members-list">
          {item.group_members.map((member) => (
            <li key={member.mentee_id}>
              {member.full_name}
              {member.zalo_phone ? ` — ${member.zalo_phone}` : ' — Chưa có Zalo'}
            </li>
          ))}
        </ol>
      </div>
    );
  };

  const handleViewActivity = (item) => {
    if (!isActivityViewed(item)) {
      markViewed(item.id);
    }
  };

  const renderItem = (item) => {
    const viewed = isActivityViewed(item);
    return (
      <div
        key={item.id}
        className={`profile-activity-line ${viewed ? 'is-read' : 'is-unread'}`}
      >
        <div
          className="profile-activity-line-main"
          role="button"
          tabIndex={0}
          onClick={() => handleViewActivity(item)}
          onKeyDown={(event) => {
            if (event.key === 'Enter' || event.key === ' ') {
              event.preventDefault();
              handleViewActivity(item);
            }
          }}
        >
          <span className="profile-activity-dot">•</span>
          <div className="profile-activity-line-content">
            <FeedLine
              item={item}
              onLinkClick={(event) => {
                event.stopPropagation();
                handleViewActivity(item);
              }}
            />
            {renderDeadlineBadge(item)}
            {renderRegistrationStatus(item)}
            {renderGroupMembers(item)}
            {item.keeptrack?.active && (
              <ActivityKeeptrackBar
                keeptrack={item.keeptrack}
                saving={Boolean(keeptrackSaving[item.id])}
                disabled={item.keeptrack?.review_status === 'pending'}
                onSave={(body) => saveKeeptrack(item.id, body)}
              />
            )}
          </div>
        </div>
        <div className="profile-activity-line-actions">
          {item.group_assignment_pending && (
            <div className="profile-activity-group-actions">
              {!item.group_name && (
                <p className="muted profile-activity-group-invite-text">Mentor mời bạn vào nhóm</p>
              )}
              <button
                type="button"
                className="btn btn-outline btn-sm"
                onClick={() => respondGroup(item.id, 'confirmed')}
              >
                Xác nhận
              </button>
              <button
                type="button"
                className="btn btn-outline btn-sm"
                onClick={() => respondGroup(item.id, 'rejected')}
              >
                Từ chối
              </button>
            </div>
          )}
          {!item.registered && item.needs_participation_choice && (
            <div className="profile-activity-register-choice">
              {MENTEE_PARTICIPATION_CHOICES.map((choice) => (
                <label key={choice.value} className="checkbox-label">
                  <input
                    type="radio"
                    name={`participation-${item.id}`}
                    checked={registerChoice[item.id] === choice.value}
                    onChange={() =>
                      setRegisterChoice((prev) => ({ ...prev, [item.id]: choice.value }))
                    }
                  />
                  {choice.label}
                </label>
              ))}
            </div>
          )}
          {!item.registered && (
            <button
              type="button"
              className="btn btn-outline btn-sm"
              onClick={() => registerActivity(item)}
            >
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

  const otherDayCount = otherDays.length;
  const otherItemCount = otherDays.reduce((sum, day) => sum + (day.items || []).length, 0);
  const totalCount = (currentDay?.items?.length || 0) + otherItemCount;
  const primaryDateLabel = currentDay?.date_label;

  return (
    <>
      <h2>Hoạt động làm đẹp hồ sơ</h2>
      <p className="profile-panel-desc">
        Theo dõi và đăng ký các hoạt động hỗ trợ làm đẹp hồ sơ apply.
      </p>

      <div className="profile-card">
        <div className="profile-activities-head">
          {!loading && (
            <p className="profile-activities-head-summary muted">
              {primaryDateLabel && (
                <>
                  <strong>Ngày {primaryDateLabel}</strong>
                  {!expanded && totalCount > 0 && (
                    <>
                      {' · '}
                      Có {totalCount} hoạt động
                      {unviewedCount > 0 ? ` (${unviewedCount} mới)` : ''}
                    </>
                  )}
                </>
              )}
              {!primaryDateLabel && !expanded && (
                <>
                  Có {totalCount} hoạt động
                  {unviewedCount > 0 ? ` (${unviewedCount} mới)` : ''}.
                </>
              )}
            </p>
          )}
          <button type="button" className="btn btn-outline btn-sm" onClick={() => setExpanded((v) => !v)}>
            {expanded ? 'Thu gọn' : 'Mở rộng'}
          </button>
        </div>
        {error && <p className="form-error">{error}</p>}
        {loading ? (
          <p className="profile-note">Đang tải hoạt động...</p>
        ) : !expanded ? null : (
          <div className="profile-activities-days">
            <DayBlock day={currentDay} renderItem={renderItem} />
            {otherDayCount > 0 && (
              <div className="profile-activities-other">
                <button
                  type="button"
                  className="profile-activities-other-toggle btn btn-outline btn-sm"
                  onClick={() => setShowOther((value) => !value)}
                  aria-expanded={showOther}
                >
                  {showOther ? 'Thu gọn Khác' : `Khác (${otherDayCount} ngày, ${otherItemCount} hoạt động)`}
                </button>
                {showOther && otherDays.map((day) => (
                  <DayBlock key={day.date_key} day={day} renderItem={renderItem} />
                ))}
              </div>
            )}
            {!currentDay?.items?.length && !otherItemCount && (
              <p className="muted">Chưa có hoạt động nào.</p>
            )}
          </div>
        )}
      </div>
    </>
  );
}
