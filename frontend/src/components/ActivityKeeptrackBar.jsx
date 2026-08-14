import { useState } from 'react';
import { HDNK_NCKH_AWARD_LEVELS } from '../data/hdnkNckh';
import ActivityInlineLink from './ActivityInlineLink';

export default function ActivityKeeptrackBar({
  keeptrack,
  activity = null,
  onComplete,
  onSubmit,
  onAbandon,
  saving = false,
  disabled = false,
  hideHead = false,
}) {
  const [showPrizeStep, setShowPrizeStep] = useState(false);
  const [hasAward, setHasAward] = useState(false);
  const [awardLevel, setAwardLevel] = useState('');

  if (!keeptrack?.active) return null;

  const isAbandonPending = keeptrack.abandon_status === 'pending';
  const isDisabled = disabled || saving || isAbandonPending;
  const reviewMessage = keeptrack.review_message || '';
  const reviewStatus = keeptrack.abandon_status || '';
  const progressStatus = keeptrack.progress_status || 'in_progress';
  const isSubmitted = progressStatus === 'submitted';
  const progressLabel = keeptrack.progress_label || (isSubmitted ? 'Đã submit' : 'Đang tiến hành');

  const resetPrizeStep = () => {
    setShowPrizeStep(false);
    setHasAward(false);
    setAwardLevel('');
  };

  const handleCompleteClick = () => {
    if (isDisabled) return;
    setShowPrizeStep(true);
  };

  const handleConfirmComplete = async () => {
    if (isDisabled || saving) return;
    if (hasAward && !awardLevel) return;
    try {
      await onComplete?.({
        has_award: hasAward,
        award_level: hasAward ? awardLevel : '',
      });
      resetPrizeStep();
    } catch {
      // parent shows error; keep prize step open for retry
    }
  };

  const handleSubmit = () => {
    if (isDisabled || isSubmitted) return;
    if (!window.confirm('Xác nhận đã submit dự án? Mentor sẽ thấy trạng thái Đã submit.')) return;
    onSubmit?.({});
  };

  const handleAbandon = () => {
    if (isDisabled) return;
    if (!window.confirm('Gửi yêu cầu từ bỏ hoạt động này cho mentor xác nhận?')) return;
    onAbandon?.({});
  };

  return (
    <div
      className={`profile-activity-keeptrack profile-activity-keeptrack--active${
        isSubmitted ? ' is-submitted' : ''
      }`}
    >
      {!hideHead && (
        <div className="profile-activity-keeptrack-head">
          <span className="profile-activity-keeptrack-icon" aria-hidden="true">
            🍀
          </span>
          <strong>{progressLabel}</strong>
        </div>
      )}

      {reviewMessage && (
        <p
          className={`profile-activity-keeptrack-status${
            reviewStatus === 'rejected' ? ' is-rejected' : ' is-pending'
          }`}
        >
          {reviewMessage}
        </p>
      )}

      <div className="profile-activity-keeptrack-fields">
        <div className="profile-activity-keeptrack-field">
          <span className="profile-activity-keeptrack-label">Tên cuộc thi</span>
          <span className="profile-activity-keeptrack-value">
            <ActivityInlineLink activity={activity} fallback={keeptrack.display_name || '—'} />
          </span>
        </div>
        <div className="profile-activity-keeptrack-field">
          <span className="profile-activity-keeptrack-label">Ngày bắt đầu</span>
          <span className="profile-activity-keeptrack-value">{keeptrack.start_date || '—'}</span>
        </div>
        <div className="profile-activity-keeptrack-field">
          <span className="profile-activity-keeptrack-label">Tiến độ</span>
          <span
            className={`profile-activity-keeptrack-value${
              isSubmitted ? ' is-submitted' : ''
            }`}
          >
            {progressLabel}
          </span>
        </div>
      </div>

      {showPrizeStep && (
        <div className="profile-activity-keeptrack-prize">
          <p className="profile-activity-keeptrack-prize-title">Có giải thưởng không?</p>
          <div className="profile-activity-keeptrack-prize-options">
            <label className="profile-activity-keeptrack-prize-choice">
              <input
                type="radio"
                name={`prize-${keeptrack.display_name}`}
                checked={!hasAward}
                onChange={() => {
                  setHasAward(false);
                  setAwardLevel('');
                }}
              />
              Không có giải
            </label>
            <label className="profile-activity-keeptrack-prize-choice">
              <input
                type="radio"
                name={`prize-${keeptrack.display_name}`}
                checked={hasAward}
                onChange={() => setHasAward(true)}
              />
              Có giải
            </label>
          </div>
          {hasAward && (
            <label className="profile-activity-keeptrack-field">
              <span className="profile-activity-keeptrack-label">Hạng giải</span>
              <select
                value={awardLevel}
                onChange={(e) => setAwardLevel(e.target.value)}
                className="profile-activity-keeptrack-select"
              >
                <option value="">— Chọn hạng giải —</option>
                {(keeptrack.award_level_options || HDNK_NCKH_AWARD_LEVELS).map((option) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
              </select>
            </label>
          )}
          <div className="profile-activity-keeptrack-actions">
            <button
              type="button"
              className="btn btn-outline btn-sm"
              disabled={saving}
              onClick={resetPrizeStep}
            >
              Hủy
            </button>
            <button
              type="button"
              className="btn btn-primary btn-sm"
              disabled={saving || (hasAward && !awardLevel)}
              onClick={handleConfirmComplete}
            >
              {saving ? 'Đang lưu...' : 'Xác nhận đã xong'}
            </button>
          </div>
        </div>
      )}

      {!showPrizeStep && (
        <div className="profile-activity-keeptrack-actions">
          <button
            type="button"
            className="btn btn-outline btn-sm"
            disabled={isDisabled || isSubmitted}
            onClick={handleSubmit}
          >
            {isSubmitted ? 'Đã submit' : saving ? 'Đang gửi...' : 'Đã submit'}
          </button>
          <button
            type="button"
            className="btn btn-primary btn-sm"
            disabled={isDisabled}
            onClick={handleCompleteClick}
          >
            Đã xong
          </button>
          <button
            type="button"
            className="btn btn-outline btn-sm"
            disabled={isDisabled}
            onClick={handleAbandon}
          >
            {saving ? 'Đang gửi...' : 'Từ bỏ'}
          </button>
        </div>
      )}
    </div>
  );
}
