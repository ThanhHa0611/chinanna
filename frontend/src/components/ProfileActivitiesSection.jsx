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
  const [expandedGroupViews, setExpandedGroupViews] = useState({});

  const refresh = async () => {
    const data = await api.getProfileActivities();
    setCurrentDay(data.current_day || null);
    setOtherDays(data.other_days || []);
    onUnviewedCountChange?.(data.unviewed_count ?? 0);
    setError('');
  };

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError('');
    api
      .getProfileActivities()
      .then((data) => {
        if (cancelled) return;
        setCurrentDay(data.current_day || null);
        setOtherDays(data.other_days || []);
        onUnviewedCountChange?.(data.unviewed_count ?? 0);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err.message || 'Không tải được hoạt động.');
        setCurrentDay(null);
        setOtherDays([]);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
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

  const patchActivityInFeed = (itemId, activityPatch) => {
    const patchItem = (item) => (item.id === itemId ? { ...item, ...activityPatch } : item);
    setCurrentDay((day) =>
      day ? { ...day, items: (day.items || []).map(patchItem) } : day,
    );
    setOtherDays((days) =>
      days.map((day) => ({ ...day, items: (day.items || []).map(patchItem) })),
    );
  };

  const completeKeeptrack = async (itemId, body) => {
    setKeeptrackSaving((prev) => ({ ...prev, [itemId]: true }));
    try {
      const result = await api.completeProfileActivityKeeptrack(itemId, body);
      if (result?.activity) {
        patchActivityInFeed(itemId, result.activity);
      } else {
        await refresh();
      }
      setError('');
    } catch (err) {
      setError(err.message);
    } finally {
      setKeeptrackSaving((prev) => ({ ...prev, [itemId]: false }));
    }
  };

  const abandonKeeptrack = async (itemId, body) => {
    setKeeptrackSaving((prev) => ({ ...prev, [itemId]: true }));
    try {
      const result = await api.abandonProfileActivityKeeptrack(itemId, body);
      if (result?.activity) {
        patchActivityInFeed(itemId, result.activity);
      } else {
        await refresh();
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

  const toggleGroupMembersView = (itemId, event) => {
    event?.stopPropagation?.();
    setExpandedGroupViews((prev) => ({ ...prev, [itemId]: !prev[itemId] }));
  };

  const renderRegistrationStatus = (item) => {
    if (item.group_assignment_pending && item.group_name) {
      const memberCount = item.group_member_count ?? item.group_members?.length ?? 0;
      return (
        <span className="muted profile-activity-group-invite-text">
          Mentor đã phân bạn vào nhóm {item.group_name} bao gồm {memberCount} thành viên{' '}
          <button
            type="button"
            className="profile-activity-inline-link profile-activity-view-link"
            onClick={(event) => toggleGroupMembersView(item.id, event)}
          >
            (Xem)
          </button>
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
      if (item.keeptrack?.active) {
        return (
          <span className="muted">Đã báo danh (Cá nhân) — tiến độ đang theo dõi</span>
        );
      }
      return <span className="muted">Đã báo danh (Cá nhân)</span>;
    }
    if (item.registered && item.group_response_status === 'confirmed' && item.keeptrack?.active) {
      return (
        <span className="muted">Đã xác nhận nhóm — tiến độ đang theo dõi</span>
      );
    }
    if (item.registered && item.participation_choice_label) {
      return <span className="muted">Đã báo danh ({item.participation_choice_label})</span>;
    }
    if (item.registered) {
      return <span className="muted">Đã báo danh</span>;
    }
    return null;
  };

  const renderGroupMembers = (item, { forceShow = false } = {}) => {
    const isConfirmed = item.group_response_status === 'confirmed';
    const showExpanded = Boolean(expandedGroupViews[item.id]);
    const shouldShow =
      item.group_members?.length &&
      (forceShow || isConfirmed || (item.group_assignment_pending && showExpanded));
    if (!shouldShow) {
      return null;
    }
    return (
      <div className="profile-activity-group-members">
        {!isConfirmed && <p className="profile-activity-group-members-title">Thành viên nhóm:</p>}
        {isConfirmed && <p className="profile-activity-group-members-title">Nhóm bao gồm:</p>}
        <ol className="profile-activity-group-members-list">
          {item.group_members.map((member) => (
            <li key={member.mentee_id}>
              {member.full_name}
              {member.is_leader ? ' (nhóm trưởng)' : ''}
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
                onComplete={(body) => completeKeeptrack(item.id, body)}
                onAbandon={(body) => abandonKeeptrack(item.id, body)}
              />
            )}
          </div>
        </div>
        <div className="profile-activity-line-actions">
          {item.group_assignment_pending && (
            <div className="profile-activity-group-actions">
              <button
                type="button"
                className="btn btn-outline btn-sm"
                onClick={() => respondGroup(item.id, 'confirmed')}
              >
                Đồng ý
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
            {!loading && !error && !currentDay?.items?.length && !otherItemCount && (
              <p className="muted">Chưa có hoạt động nào.</p>
            )}
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
          </div>
        )}
      </div>
    </>
  );
}
