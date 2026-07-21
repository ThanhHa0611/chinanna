import { useEffect, useState } from 'react';
import {
  HDNK_NCKH_AWARD_LEVELS,
  HDNK_NCKH_PARTICIPATION_TYPES,
  HDNK_NCKH_PROGRESS_OPTIONS,
  emptyHdnkNckhEntry,
  isInternalGroupParticipation,
  normalizeHdnkNckhEntries,
} from '../data/hdnkNckh';
import { api } from '../services/api';

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

export default function HdnkNckhSection() {
  const [entries, setEntries] = useState([emptyHdnkNckhEntry()]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError('');
    api
      .getHdnkNckh()
      .then((data) => {
        if (cancelled) return;
        const normalized = normalizeHdnkNckhEntries(data.entries || []);
        setEntries(normalized.length ? normalized : [emptyHdnkNckhEntry()]);
      })
      .catch((err) => {
        if (!cancelled) setError(err.message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

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

  const handleSave = async () => {
    setSaving(true);
    setMessage('');
    setError('');
    try {
      const payload = await api.updateHdnkNckh({
        entries: entries.filter(hasHdnkEntryContent),
      });
      const normalized = normalizeHdnkNckhEntries(payload.entries || []);
      setEntries(normalized.length ? normalized : [emptyHdnkNckhEntry()]);
      setMessage('Đã lưu, hãy cố gắng tiếp nhé ❤️');
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return <p className="profile-note">Đang tải keep track HDNK+NCKH...</p>;
  }

  return (
    <>
      <h2>Keep track HDNK + NCKH</h2>
      <p className="profile-panel-desc">
        Hãy ghi lại tiến độ build pro5 của bạn nha.
      </p>

      {error && <p className="form-error">{error}</p>}
      {message && <p className="form-success">{message}</p>}

      <div className="profile-card hdnk-nckh-card">
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

              <label className="hdnk-nckh-field-category">
                Hạng mục tham gia
                <input
                  type="text"
                  value={entry.category}
                  onChange={(e) => updateEntry(index, 'category', e.target.value)}
                  placeholder="VD: NCKH cấp trường..."
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
                <label className="hdnk-nckh-field-zalo">
                  Tên nhóm Zalo
                  <input
                    type="text"
                    value={entry.zalo_group_name}
                    onChange={(e) => updateEntry(index, 'zalo_group_name', e.target.value)}
                    placeholder="Tên nhóm Zalo Du học Trung Quốc"
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
                <select
                  value={entry.award_level}
                  disabled={!entry.has_award}
                  onChange={(e) => updateEntry(index, 'award_level', e.target.value)}
                  aria-label="Chọn giải"
                >
                  <option value="">Chọn giải</option>
                  {HDNK_NCKH_AWARD_LEVELS.map((option) => (
                    <option key={option} value={option}>
                      {option}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          </div>
        ))}

        <div className="hdnk-nckh-actions">
          <button type="button" className="btn btn-sm hdnk-nckh-add-btn" onClick={addEntry}>
            + Thêm mục
          </button>
          <button
            type="button"
            className="btn btn-primary btn-sm"
            disabled={saving}
            onClick={handleSave}
          >
            {saving ? 'Đang lưu...' : 'Lưu cập nhật'}
          </button>
        </div>
      </div>
    </>
  );
}
