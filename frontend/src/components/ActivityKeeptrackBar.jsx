import { useEffect, useState } from 'react';
import { HDNK_NCKH_AWARD_LEVELS } from '../data/hdnkNckh';

const PROGRESS_OPTIONS = [
  { value: 'in_progress', label: 'Đang tiến hành' },
  { value: 'completed', label: 'Đã xong' },
];

function buildDraft(keeptrack) {
  return {
    start_date: keeptrack?.start_date || '',
    progress_status: keeptrack?.progress_status || 'in_progress',
    has_award: Boolean(keeptrack?.has_award),
    award_level: keeptrack?.award_level || '',
  };
}

export default function ActivityKeeptrackBar({
  keeptrack,
  onSave,
  saving = false,
  disabled = false,
}) {
  const [draft, setDraft] = useState(() => buildDraft(keeptrack));

  useEffect(() => {
    setDraft(buildDraft(keeptrack));
  }, [keeptrack?.start_date, keeptrack?.progress_status, keeptrack?.has_award, keeptrack?.award_level]);

  if (!keeptrack?.active) return null;

  const updateDraft = (key, value) => {
    setDraft((prev) => {
      const next = { ...prev, [key]: value };
      if (key === 'progress_status' && value !== 'completed') {
        next.has_award = false;
        next.award_level = '';
      }
      if (key === 'has_award' && !value) {
        next.award_level = '';
      }
      return next;
    });
  };

  const handleSave = () => {
    onSave?.({
      start_date: draft.start_date,
      progress_status: draft.progress_status,
      has_award: draft.progress_status === 'completed' ? draft.has_award : false,
      award_level: draft.progress_status === 'completed' && draft.has_award ? draft.award_level : '',
    });
  };

  const reviewStatus = keeptrack.review_status || '';
  const reviewMessage = keeptrack.review_message || '';

  return (
    <div className="profile-activity-keeptrack">
      <div className="profile-activity-keeptrack-head">
        <span className="profile-activity-keeptrack-icon" aria-hidden="true">
          🍀
        </span>
        <strong>Đang tiến hành</strong>
      </div>
      {reviewMessage && (
        <p
          className={`profile-activity-keeptrack-status${
            reviewStatus === 'rejected' ? ' is-rejected' : ' is-pending'
          }`}
        >
          {reviewMessage}
        </p>
      )}
      <div className="profile-activity-keeptrack-grid">
        <label>
          Tên
          <input type="text" value={keeptrack.display_name || ''} readOnly />
        </label>
        <label>
          Ngày bắt đầu
          <input
            type="date"
            value={draft.start_date}
            disabled={disabled}
            onChange={(e) => updateDraft('start_date', e.target.value)}
          />
        </label>
        <label>
          Trạng thái
          <select
            value={draft.progress_status}
            disabled={disabled}
            onChange={(e) => updateDraft('progress_status', e.target.value)}
          >
            {PROGRESS_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        {draft.progress_status === 'completed' && (
          <>
            <label className="profile-activity-keeptrack-checkbox">
              <input
                type="checkbox"
                checked={draft.has_award}
                disabled={disabled}
                onChange={(e) => updateDraft('has_award', e.target.checked)}
              />
              Có giải thưởng không
            </label>
            <label>
              Hạng giải
              <select
                value={draft.award_level}
                disabled={disabled || !draft.has_award}
                onChange={(e) => updateDraft('award_level', e.target.value)}
              >
                <option value="">—</option>
                {(keeptrack.award_level_options || HDNK_NCKH_AWARD_LEVELS).map((option) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
              </select>
            </label>
          </>
        )}
      </div>
      <div className="profile-activity-keeptrack-actions">
        <button
          type="button"
          className="btn btn-primary btn-sm"
          disabled={saving || disabled}
          onClick={handleSave}
        >
          {saving ? 'Đang lưu...' : 'Lưu tiến độ'}
        </button>
      </div>
    </div>
  );
}
