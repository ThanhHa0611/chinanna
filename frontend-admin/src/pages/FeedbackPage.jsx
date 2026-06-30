import { useEffect, useMemo, useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { api } from '../services/api';
import { formatDateTime, groupItemsByVnDate } from '../utils/formatDateTime';
import { isLevel1MentorAccount } from '../utils/mentorDisplay';

function FeedbackDateGroups({ sectionKey, items, renderItem }) {
  const { todayItems, pastGroups } = useMemo(() => groupItemsByVnDate(items), [items]);
  const [collapsedGroups, setCollapsedGroups] = useState({});

  const groupCollapseKey = (dateKey) => `${sectionKey}-${dateKey}`;
  const isGroupCollapsed = (dateKey) => collapsedGroups[groupCollapseKey(dateKey)] ?? true;

  const toggleGroup = (dateKey) => {
    const key = groupCollapseKey(dateKey);
    setCollapsedGroups((prev) => ({ ...prev, [key]: !isGroupCollapsed(dateKey) }));
  };

  return (
    <>
      {todayItems.map(renderItem)}
      {pastGroups.map((group) => (
        <div key={group.dateKey} className="panel-card feedback-date-group">
          <button
            type="button"
            className="daily-summary-head"
            onClick={() => toggleGroup(group.dateKey)}
            aria-expanded={!isGroupCollapsed(group.dateKey)}
          >
            <span className="daily-summary-title">
              {group.dateLabel} ({group.items.length})
            </span>
            <span className="daily-summary-toggle">
              {isGroupCollapsed(group.dateKey) ? 'Mở rộng' : 'Thu gọn'}
            </span>
          </button>
          {!isGroupCollapsed(group.dateKey) && (
            <div className="feedback-date-group-body">
              {group.items.map(renderItem)}
            </div>
          )}
        </div>
      ))}
    </>
  );
}

export default function FeedbackPage() {
  const { admin } = useAuth();
  const canSeeProcessor = Boolean(admin?.is_super_admin || isLevel1MentorAccount(admin));
  const [feedback, setFeedback] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [replyDrafts, setReplyDrafts] = useState({});
  const [savingId, setSavingId] = useState(null);

  const loadFeedback = () => {
    setLoading(true);
    setError('');
    api
      .getFeedback()
      .then((data) => {
        setFeedback(data);
        const drafts = {};
        data.forEach((item) => {
          drafts[item.id] = item.admin_reply || '';
        });
        setReplyDrafts(drafts);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadFeedback();
  }, []);

  const handleReply = async (item) => {
    setSavingId(item.id);
    setError('');
    try {
      const updated = await api.updateFeedback(item.id, {
        admin_reply: replyDrafts[item.id] || '',
        status: item.status,
      });
      setFeedback((prev) => prev.map((row) => (row.id === item.id ? updated : row)));
    } catch (err) {
      setError(err.message);
    } finally {
      setSavingId(null);
    }
  };

  const handleMarkDone = async (item) => {
    setSavingId(item.id);
    setError('');
    try {
      const updated = await api.updateFeedback(item.id, {
        admin_reply: replyDrafts[item.id] || '',
        status: 'đã xử lí',
      });
      setFeedback((prev) => prev.map((row) => (row.id === item.id ? updated : row)));
    } catch (err) {
      setError(err.message);
    } finally {
      setSavingId(null);
    }
  };

  const unreadFeedback = feedback.filter((item) => item.mentor_unread || item.status === 'chờ xử lí');
  const doneFeedback = feedback.filter((item) => item.status === 'đã xử lí');

  const renderFeedbackItem = (item) => (
    <div key={item.id} className="panel-card feedback-admin-item">
      <div className="feedback-admin-head">
        <div>
          <strong>{item.username}</strong>
          <span className="muted"> · {item.email}</span>
        </div>
        <span className={`status-pill${item.status === 'đã xử lí' ? ' status-done' : ''}`}>
          {item.status}
        </span>
      </div>
      <p className="feedback-admin-time">Gửi lúc: {formatDateTime(item.created_at)}</p>
      <p className="feedback-admin-content">{item.content}</p>
      <label className="reply-label">
        Nhắn lại mentee
        <textarea
          rows={3}
          value={replyDrafts[item.id] ?? ''}
          onChange={(e) => setReplyDrafts((prev) => ({ ...prev, [item.id]: e.target.value }))}
        />
      </label>
      <div className="feedback-admin-actions">
        <button
          type="button"
          className="btn btn-outline btn-sm"
          disabled={savingId === item.id}
          onClick={() => handleReply(item)}
        >
          Lưu nhắn lại
        </button>
        <button
          type="button"
          className="btn btn-primary btn-sm"
          disabled={savingId === item.id}
          onClick={() => handleMarkDone(item)}
        >
          {savingId === item.id ? 'Đang lưu...' : 'Đánh dấu đã xử lí'}
        </button>
      </div>
      {item.status === 'đã xử lí' && item.processed_at && (
        <p className="muted processed-at">
          Đã xử lí lúc: {formatDateTime(item.processed_at)}
          {canSeeProcessor && item.processed_by_name ? ` · bởi ${item.processed_by_name}` : ''}
        </p>
      )}
    </div>
  );

  return (
    <>
      <div className="page-head">
        <h2>Phản hồi mentee</h2>
        <p>Trả lời và đánh dấu đã xử lí — mọi thao tác được ghi vào lịch sử</p>
      </div>

      {error && <p className="form-error panel-error">{error}</p>}
      {loading ? (
        <p className="loader">Đang tải...</p>
      ) : feedback.length === 0 ? (
        <div className="panel-card">
          <p className="muted">Chưa có phản hồi nào.</p>
        </div>
      ) : (
        <>
          <div className="home-section-head home-feedback-page-head">
            <h3>Chưa xử lí ({unreadFeedback.length})</h3>
          </div>
          <div className="feedback-admin-list">
            {unreadFeedback.length === 0 ? (
              <div className="panel-card">
                <p className="muted">Không có tin nhắn chưa đọc.</p>
              </div>
            ) : (
              <FeedbackDateGroups
                sectionKey="unread"
                items={unreadFeedback}
                renderItem={renderFeedbackItem}
              />
            )}
          </div>

          <div className="home-section-head home-feedback-page-head">
            <h3>Đã xử lí ({doneFeedback.length})</h3>
          </div>
          <div className="feedback-admin-list">
            {doneFeedback.length === 0 ? (
              <div className="panel-card">
                <p className="muted">Chưa có phản hồi đã xử lí.</p>
              </div>
            ) : (
              <FeedbackDateGroups
                sectionKey="done"
                items={doneFeedback}
                renderItem={renderFeedbackItem}
              />
            )}
          </div>
        </>
      )}
    </>
  );
}
