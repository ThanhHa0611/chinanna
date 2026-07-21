import { useEffect, useState } from 'react';
import {
  HDNK_NCKH_AWARD_LEVELS,
  HDNK_NCKH_PARTICIPATION_TYPES,
  HDNK_NCKH_PROGRESS_OPTIONS,
  emptyHdnkNckhEntry,
  isInternalGroupParticipation,
  normalizeHdnkNckhEntries,
} from '../data/hdnkNckh';
import { isLevel1MentorAccount } from '../utils/mentorDisplay';
import { api } from '../services/api';
import { formatDateTime } from '../utils/formatDateTime';

function toDateInputValue(value) {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value.slice(0, 10);
  return date.toISOString().slice(0, 10);
}

function hasHdnkEntryContent(entry) {
  return Boolean(
    entry.start_date ||
      entry.category ||
      entry.participation_type ||
      entry.progress ||
      entry.zalo_group_name ||
      entry.has_award,
  );
}

export default function HdnkNckhPanel({ menteeId, initialData, admin, onUpdated }) {
  const [entries, setEntries] = useState([emptyHdnkNckhEntry()]);
  const [saving, setSaving] = useState(false);
  const [acking, setAcking] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const isLevel1 = isLevel1MentorAccount(admin);

  useEffect(() => {
    const normalized = normalizeHdnkNckhEntries(initialData?.entries || []);
    setEntries(normalized.length ? normalized : [emptyHdnkNckhEntry()]);
  }, [initialData]);

  const updateEntry = (index, key, value) => {
    setEntries((prev) =>
      prev.map((entry, idx) => {
        if (idx !== index) return entry;
        const next = { ...entry, [key]: value };
        if (key === 'participation_type' && !isInternalGroupParticipation(value)) {
          next.zalo_group_name = '';
        }
        if (key === 'has_award' && !value) {
          next.award_level = '';
        }
        return next;
      }),
    );
  };

  const addEntry = () => {
    setEntries((prev) => [...prev, emptyHdnkNckhEntry()]);
  };

  const removeEntry = (index) => {
    setEntries((prev) => {
      const next = prev.filter((_, idx) => idx !== index);
      return next.length ? next : [emptyHdnkNckhEntry()];
    });
  };

  const refreshFromPayload = (payload) => {
    const normalized = normalizeHdnkNckhEntries(payload.entries || []);
    setEntries(normalized.length ? normalized : [emptyHdnkNckhEntry()]);
    onUpdated?.(payload);
  };

  const handleSave = async () => {
    setSaving(true);
    setMessage('');
    setError('');
    try {
      const payload = await api.updateMenteeHdnkNckh(menteeId, {
        entries: entries.filter(hasHdnkEntryContent),
      });
      refreshFromPayload(payload);
      setMessage('Đã lưu keep track HDNK+NCKH.');
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const handleAck = async () => {
    setAcking(true);
    setMessage('');
    setError('');
    try {
      const payload = await api.ackMenteeHdnkNckh(menteeId);
      refreshFromPayload(payload);
      setMessage('Đã xác nhận cập nhật từ mentee.');
    } catch (err) {
      setError(err.message);
    } finally {
      setAcking(false);
    }
  };

  const showUnreadBanner = Boolean(initialData?.l1_unread);
  const showReminderBanner = Boolean(initialData?.reminder_unread);

  return (
    <div className="hdnk-nckh-panel">
      {(showUnreadBanner || showReminderBanner) && (
        <p className="apply-progress-pending-banner">
          {showUnreadBanner && 'Mentee vừa cập nhật keep track HDNK+NCKH.'}
          {showUnreadBanner && showReminderBanner && ' '}
          {showReminderBanner &&
            'Đến hạn nhắc cập nhật tiến độ theo hạng mục (3 ngày hoặc ngày đã đặt).'}
        </p>
      )}

      {error && <p className="form-error">{error}</p>}
      {message && <p className="form-success">{message}</p>}

      {initialData?.mentee_updated_at && (
        <p className="muted hdnk-nckh-meta">
          Mentee cập nhật lần cuối: {formatDateTime(initialData.mentee_updated_at)}
        </p>
      )}

      {entries.map((entry, index) => (
        <div key={entry.entry_id || `entry-${index}`} className="hdnk-nckh-entry">
          <div className="hdnk-nckh-entry-head">
            <strong>Mục {index + 1}</strong>
            {entries.length > 1 && (
              <button
                type="button"
                className="btn btn-outline btn-sm"
                onClick={() => removeEntry(index)}
              >
                Xóa mục
              </button>
            )}
          </div>

          <div className="hdnk-nckh-grid">
            <label>
              Ngày bắt đầu
              <input
                type="date"
                value={entry.start_date}
                onChange={(e) => updateEntry(index, 'start_date', e.target.value)}
              />
            </label>

            <label>
              Hạng mục tham gia
              <input
                type="text"
                value={entry.category}
                onChange={(e) => updateEntry(index, 'category', e.target.value)}
              />
            </label>

            <label>
              Loại tham gia
              <select
                value={entry.participation_type}
                onChange={(e) => updateEntry(index, 'participation_type', e.target.value)}
              >
                <option value="">—</option>
                {HDNK_NCKH_PARTICIPATION_TYPES.map((option) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
              </select>
            </label>

            {isInternalGroupParticipation(entry.participation_type) && (
              <label>
                Tên nhóm Zalo
                <input
                  type="text"
                  value={entry.zalo_group_name}
                  onChange={(e) => updateEntry(index, 'zalo_group_name', e.target.value)}
                />
              </label>
            )}

            <label>
              Tiến độ quá trình
              <select
                value={entry.progress}
                onChange={(e) => updateEntry(index, 'progress', e.target.value)}
              >
                <option value="">—</option>
                {HDNK_NCKH_PROGRESS_OPTIONS.map((option) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
              </select>
            </label>

            <div className="hdnk-nckh-award-field">
              <label className="hdnk-nckh-checkbox">
                <input
                  type="checkbox"
                  checked={entry.has_award}
                  onChange={(e) => updateEntry(index, 'has_award', e.target.checked)}
                />
                Có giải
              </label>
              {entry.has_award && (
                <select
                  value={entry.award_level}
                  onChange={(e) => updateEntry(index, 'award_level', e.target.value)}
                >
                  <option value="">Chọn giải</option>
                  {HDNK_NCKH_AWARD_LEVELS.map((option) => (
                    <option key={option} value={option}>
                      {option}
                    </option>
                  ))}
                </select>
              )}
            </div>
          </div>

          {isLevel1 && (
            <div className="hdnk-nckh-mentor-only">
              <p className="hdnk-nckh-mentor-label">Chỉ mentor Hà thấy</p>
              <label className="hdnk-nckh-note-field">
                Note
                <textarea
                  rows={2}
                  value={entry.mentor_note}
                  placeholder="Ghi chú riêng cho hạng mục này..."
                  onChange={(e) => updateEntry(index, 'mentor_note', e.target.value)}
                />
              </label>
              <label>
                Ngày nhắc cập nhật
                <input
                  type="date"
                  value={toDateInputValue(entry.reminder_due_at)}
                  onChange={(e) => updateEntry(index, 'reminder_due_at', e.target.value)}
                />
              </label>
              <p className="muted hdnk-nckh-reminder-hint">
                Hệ thống tự nhắc mỗi 3 ngày khi mentee cập nhật mà chưa xử lí. Bạn có thể đặt ngày
                nhắc riêng cho từng hạng mục.
              </p>
            </div>
          )}
        </div>
      ))}

      <div className="hdnk-nckh-actions">
        <button type="button" className="btn btn-outline btn-sm" onClick={addEntry}>
          + Thêm mục
        </button>
        <button
          type="button"
          className="btn btn-primary btn-sm"
          disabled={saving}
          onClick={handleSave}
        >
          {saving ? 'Đang lưu...' : 'Lưu keep track'}
        </button>
      </div>

      {isLevel1 && (showUnreadBanner || showReminderBanner) && (
        <div className="hdnk-nckh-reminder-box">
          <button
            type="button"
            className="btn btn-primary btn-sm"
            disabled={acking}
            onClick={handleAck}
          >
            {acking ? 'Đang xác nhận...' : 'Đã xử lí cập nhật'}
          </button>
        </div>
      )}
    </div>
  );
}
