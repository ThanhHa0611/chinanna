import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import MenteeFilterDropdown from '../components/MenteeFilterDropdown';
import { useAuth } from '../context/AuthContext';
import { api } from '../services/api';
import { formatDateTime } from '../utils/formatDateTime';
import { isLevel1MentorAccount } from '../utils/mentorDisplay';
import { matchesNameSearch } from '../utils/searchByName';
import { countMenteesNeedingAttention } from '../utils/menteeAttention';
import {
  APPLY_DEGREE_FILTER_OPTIONS,
  APPLY_DIRECTION_FILTER_OPTIONS,
  APPLY_LANGUAGE_FILTER_OPTIONS,
  applyDegreeLevelShortDisplay,
  mentorApplyDirectionLabel,
  normalizeMentorApplyDirectionValue,
  normalizeScholarshipSystemValue,
  researchDirectionDisplayText,
  scholarshipLanguageShortLabel,
  TERM3_LANGUAGE_FILTER_OPTIONS,
  term3LanguageSemesterLabel,
} from '../data/applyDegree';

function term3LanguageShortDisplay(mentee) {
  const value = (mentee?.term3_2027_language_semester || '').trim().toLowerCase();
  if (value === 'co') return 'Có';
  if (value === 'khong') return 'Không';
  return term3LanguageSemesterLabel(mentee?.term3_2027_language_semester) || '—';
}

export default function Home() {
  const { admin } = useAuth();
  const [stats, setStats] = useState(null);
  const [mentees, setMentees] = useState([]);
  const [feedback, setFeedback] = useState([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [degreeFilter, setDegreeFilter] = useState('all');
  const [languageFilter, setLanguageFilter] = useState('all');
  const [directionFilter, setDirectionFilter] = useState('all');
  const [termFilter, setTermFilter] = useState('all');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [inboxItems, setInboxItems] = useState([]);
  const [dailySummary, setDailySummary] = useState(null);
  const [archiveDays, setArchiveDays] = useState([]);
  const [inboxPendingCount, setInboxPendingCount] = useState(0);
  const [inboxSavingId, setInboxSavingId] = useState('');
  const [reminderDrafts, setReminderDrafts] = useState({});
  const [collapsedSections, setCollapsedSections] = useState({});
  const [archiveView, setArchiveView] = useState(null);
  const [archiveLoading, setArchiveLoading] = useState(false);

  const canSeeProcessor = Boolean(admin?.is_super_admin || isLevel1MentorAccount(admin));

  useEffect(() => {
    Promise.all([api.getStats(), api.getMentees(), api.getFeedback(), api.getInbox()])
      .then(([statsData, menteeData, feedbackData, inboxData]) => {
        setStats(statsData);
        setMentees(menteeData || []);
        setFeedback(feedbackData || []);
        setInboxItems(inboxData?.items || []);
        setDailySummary(inboxData?.daily_summary || null);
        setArchiveDays(inboxData?.archive_days || []);
        setInboxPendingCount(inboxData?.pending_count || 0);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  const unreadFeedback = useMemo(
    () => feedback.filter((item) => item.mentor_unread || item.status === 'chờ xử lí'),
    [feedback],
  );

  const preferredSchoolsUnread = useMemo(
    () => mentees.filter((item) => item.preferred_schools_note_unread),
    [mentees],
  );

  const doneFeedback = useMemo(
    () => feedback.filter((item) => item.status === 'đã xử lí'),
    [feedback],
  );

  const isThanhHaL1 = isLevel1MentorAccount(admin) && (admin?.mentor_name || '').trim() === 'Thanh Hà';
  const isMaiChiL1 = isLevel1MentorAccount(admin) && (admin?.mentor_name || '').trim() === 'Mai Chi';
  const showDegreeLanguageFilters = isThanhHaL1 || isMaiChiL1;
  const showDirectionFilter = isThanhHaL1 || isMaiChiL1;
  const showDirectionColumn = showDirectionFilter;
  const showLanguageColumn = showDegreeLanguageFilters;

  const filteredMentees = useMemo(
    () =>
      mentees.filter((mentee) => {
        if (degreeFilter !== 'all' && mentee.apply_degree_level !== degreeFilter) {
          return false;
        }
        if (
          languageFilter !== 'all' &&
          normalizeScholarshipSystemValue(mentee) !== languageFilter
        ) {
          return false;
        }
        if (showDirectionFilter) {
          if (
            directionFilter !== 'all' &&
            normalizeMentorApplyDirectionValue(mentee.mentor_apply_direction) !== directionFilter
          ) {
            return false;
          }
        }
        if (isThanhHaL1) {
          if (termFilter !== 'all') {
            const term = (mentee.term3_2027_language_semester || '').trim().toLowerCase();
            if (term !== termFilter) return false;
          }
        }
        return matchesNameSearch(mentee, searchQuery, [
          'full_name',
          'username',
          'zalo_phone',
          ...(showDirectionFilter ? ['mentor_apply_direction'] : []),
        ]);
      }),
    [
      mentees,
      searchQuery,
      degreeFilter,
      languageFilter,
      directionFilter,
      termFilter,
      isThanhHaL1,
      showDirectionFilter,
    ],
  );

  const menteeAttentionOptions = {
    isSuperAdmin: Boolean(admin?.is_super_admin),
    isLevel1: isLevel1MentorAccount(admin),
  };
  const menteeAttentionCount = useMemo(
    () => countMenteesNeedingAttention(mentees, menteeAttentionOptions),
    [mentees, admin],
  );

  const hdnkAttentionMentees = useMemo(
    () =>
      isThanhHaL1
        ? mentees.filter(
            (item) => item.hdnk_nckh_l1_unread || item.hdnk_nckh_reminder_unread,
          )
        : [],
    [mentees, isThanhHaL1],
  );

  const refreshInbox = () =>
    api.getInbox().then((data) => {
      setInboxItems(data?.items || []);
      setDailySummary(data?.daily_summary || null);
      setArchiveDays(data?.archive_days || []);
      setInboxPendingCount(data?.pending_count || 0);
    });

  const toggleSection = (sectionKey) => {
    setCollapsedSections((prev) => ({
      ...prev,
      [sectionKey]: !prev[sectionKey],
    }));
  };

  const openArchiveDay = async (dateKey) => {
    setArchiveLoading(true);
    try {
      const data = await api.getInboxArchiveDay(dateKey);
      setArchiveView(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setArchiveLoading(false);
    }
  };

  const closeArchiveView = () => setArchiveView(null);

  const handleViewInbox = async (item) => {
    setInboxSavingId(item.id);
    try {
      if (item.view_url) {
        window.open(item.view_url, '_blank', 'noopener,noreferrer');
      }
      await api.viewInboxTask(item.id);
      await refreshInbox();
    } catch (err) {
      setError(err.message);
    } finally {
      setInboxSavingId('');
    }
  };

  const handleConfirmInbox = async (taskId) => {
    setInboxSavingId(taskId);
    try {
      await api.confirmInboxTask(taskId);
      await refreshInbox();
    } catch (err) {
      setError(err.message);
    } finally {
      setInboxSavingId('');
    }
  };

  const handleUpdateReminder = async (taskId, mode = 'datetime') => {
    setInboxSavingId(taskId);
    try {
      const payload =
        mode === 'datetime' && reminderDrafts[taskId]
          ? { reminder_at: new Date(reminderDrafts[taskId]).toISOString() }
          : { hours: Number(reminderDrafts[`${taskId}-hours`] || 24) };
      await api.updateInboxReminder(taskId, payload);
      await refreshInbox();
    } catch (err) {
      setError(err.message);
    } finally {
      setInboxSavingId('');
    }
  };

  const renderDailySummaryRow = (item, { readOnly = false } = {}) => {
    const isDone = item.is_processed || item.display_state === 'done' || item.status === 'done';
    const isViewed = !isDone && (item.display_state === 'viewed' || Boolean(item.viewed_at));
    const stateClass = isDone ? 'is-done' : isViewed ? 'is-viewed' : 'is-new';
    const statusClass = isDone ? 'is-done' : isViewed ? 'is-viewed' : 'is-new';
    const statusLine =
      item.status_line ||
      (isDone ? 'Đã xử lí' : isViewed ? 'Đã xem · chưa xử lí' : 'Chưa xem');
    const reminderHours = reminderDrafts[`${item.id}-hours`] ?? 24;

    return (
      <div key={item.id} className={`daily-summary-row ${stateClass}`}>
        <div className="daily-summary-main">
          <span className="daily-summary-action">{item.action_line || item.summary_line || item.title}</span>
          <span className={`daily-summary-status-line daily-summary-badge ${statusClass}`}>
            {statusLine}
          </span>
        </div>
        {!readOnly && !isDone && (
          <div className="daily-summary-actions-inline">
            <button
              type="button"
              className="daily-summary-link"
              disabled={inboxSavingId === item.id}
              onClick={() => handleViewInbox(item)}
            >
              Xem
            </button>
            <button
              type="button"
              className="daily-summary-link confirm-link"
              disabled={inboxSavingId === item.id}
              onClick={() => handleConfirmInbox(item.id)}
            >
              Đã xử lí
            </button>
            <label className="daily-summary-reminder-field">
              Nhắc sau (giờ)
              <input
                type="number"
                min="1"
                max="720"
                value={reminderHours}
                onChange={(e) =>
                  setReminderDrafts((prev) => ({
                    ...prev,
                    [`${item.id}-hours`]: e.target.value,
                  }))
                }
              />
            </label>
            <button
              type="button"
              className="daily-summary-link muted-link"
              disabled={inboxSavingId === item.id}
              onClick={() => handleUpdateReminder(item.id, 'hours')}
            >
              Lưu nhắc
            </button>
          </div>
        )}
      </div>
    );
  };

  if (loading) return <p className="loader">Đang tải...</p>;
  if (error) return <p className="form-error">{error}</p>;

  return (
    <>
      <div className="page-head">
        <h2>Trang chủ · {admin?.mentor_name ? `Mentor ${admin.mentor_name}` : 'Dashboard'}</h2>
        <p>Tổng quan mentee, tiến độ apply và phản hồi</p>
      </div>

      <div className="stat-grid">
        <div className="stat-card">
          <span className="stat-label">Mentee</span>
          <strong className="stat-value">{stats?.mentee_count ?? 0}</strong>
        </div>
        <div className="stat-card">
          <span className="stat-label">Chưa xử lí</span>
          <strong className="stat-value accent">{unreadFeedback.length}</strong>
        </div>
        <div className="stat-card">
          <span className="stat-label">Đã xử lí</span>
          <strong className="stat-value">{doneFeedback.length}</strong>
        </div>
        {admin?.is_super_admin && (
          <div className="stat-card">
            <span className="stat-label">Lịch sử hoạt động</span>
            <strong className="stat-value">{stats?.activity_count ?? 0}</strong>
          </div>
        )}
        {(stats?.pending_access_requests_count ?? 0) > 0 && (
          <div className="stat-card">
            <span className="stat-label">Chờ cấp quyền</span>
            <strong className="stat-value accent">{stats.pending_access_requests_count}</strong>
          </div>
        )}
        {(menteeAttentionCount ?? 0) > 0 && (
          <div className="stat-card">
            <span className="stat-label">Mentee cần xử lí</span>
            <strong className="stat-value accent">{menteeAttentionCount}</strong>
          </div>
        )}
        {(inboxPendingCount ?? 0) > 0 && (
          <div className="stat-card">
            <span className="stat-label">Việc chưa xử lí</span>
            <strong className="stat-value accent">{inboxPendingCount}</strong>
          </div>
        )}
      </div>

      {(dailySummary?.items?.length > 0 || archiveDays.length > 0 || inboxItems.length > 0) && (
        <div className="daily-summary-wrap">
          {(dailySummary?.items?.length > 0 || inboxItems.length > 0) && (
            <div className="panel-card daily-summary-panel">
              <button
                type="button"
                className="daily-summary-head"
                onClick={() => toggleSection('today')}
                aria-expanded={!collapsedSections.today}
              >
                <span className="daily-summary-title">{dailySummary?.title || 'Tóm tắt ngày'}</span>
                <span className="daily-summary-toggle">
                  {collapsedSections.today ? 'Mở rộng' : 'Thu gọn'}
                </span>
              </button>
              {!collapsedSections.today && (
                <div className="daily-summary-body">
                  <p className="daily-summary-date">
                    Ngày {dailySummary?.date_label || '—'}
                  </p>
                  {(dailySummary?.items || []).length === 0 ? (
                    <p className="muted">Không có hoạt động hôm nay.</p>
                  ) : (
                    <div className="daily-summary-list">
                      {(dailySummary?.items || []).map((item) => renderDailySummaryRow(item))}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {archiveDays.length > 0 && (
            <div className="panel-card daily-summary-panel">
              <button
                type="button"
                className="daily-summary-head"
                onClick={() => toggleSection('archive')}
                aria-expanded={!collapsedSections.archive}
              >
                <span className="daily-summary-title">Bảng tin trước</span>
                <span className="daily-summary-toggle">
                  {collapsedSections.archive ? 'Mở rộng' : 'Thu gọn'}
                </span>
              </button>
              {!collapsedSections.archive && (
                <div className="daily-summary-body">
                  <div className="daily-summary-archive-list">
                    {archiveDays.map((day) => (
                      <div key={day.date} className="daily-summary-archive-row">
                        <span>Ngày {day.date_label}</span>
                        <button
                          type="button"
                          className="daily-summary-link"
                          disabled={archiveLoading}
                          onClick={() => openArchiveDay(day.date)}
                        >
                          Xem
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {archiveView && (
        <div className="daily-summary-modal-backdrop" onClick={closeArchiveView} role="presentation">
          <div
            className="panel-card daily-summary-modal"
            onClick={(e) => e.stopPropagation()}
            role="dialog"
            aria-labelledby="archive-summary-title"
          >
            <div className="daily-summary-head static-head">
              <div>
                <h3 id="archive-summary-title">{archiveView.title || 'Tóm tắt ngày'}</h3>
                <p className="daily-summary-date">Ngày {archiveView.date_label}</p>
              </div>
              <button type="button" className="btn btn-outline btn-sm" onClick={closeArchiveView}>
                Đóng
              </button>
            </div>
            <div className="daily-summary-body">
              {(archiveView.items || []).length === 0 ? (
                <p className="muted">Không có mục nào trong ngày này.</p>
              ) : (
                <div className="daily-summary-list">
                  {(archiveView.items || []).map((item) =>
                    renderDailySummaryRow(item, { readOnly: true }),
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {menteeAttentionCount > 0 && (
        <div className="panel-card alert-card">
          <p>
            Có <strong>{menteeAttentionCount}</strong> mentee có thông báo mới cần xử lí.
          </p>
          <Link to="/mentees" className="btn btn-primary btn-sm">
            Xem mentee
          </Link>
        </div>
      )}

      {stats?.pending_access_requests_count > 0 && (
        <div className="panel-card alert-card">
          <p>
            Có <strong>{stats.pending_access_requests_count}</strong> yêu cầu cấp quyền đang chờ
            duyệt
            {admin?.is_super_admin && stats.pending_requests > 0
              ? ` (${stats.pending_requests} mentor, ${stats.pending_mentee_registrations} mentee)`
              : ''}
            .
          </p>
          <Link to="/access-requests" className="btn btn-primary btn-sm">
            Xem yêu cầu
          </Link>
        </div>
      )}

      {preferredSchoolsUnread.length > 0 && (
        <div className="panel-card alert-card">
          <p>
            Có <strong>{preferredSchoolsUnread.length}</strong> mentee cập nhật ghi chú trường ưa
            thích.
          </p>
          <Link to="/mentees" className="btn btn-primary btn-sm">
            Xem mentee
          </Link>
        </div>
      )}

      {hdnkAttentionMentees.length > 0 && (
        <div className="panel-card alert-card">
          <p>
            Có <strong>{hdnkAttentionMentees.length}</strong> mentee cần xử lí keep track HDNK+NCKH
            (cập nhật mới hoặc đến hạn nhắc 3 ngày).
          </p>
          <Link to="/mentees" className="btn btn-primary btn-sm">
            Xem mentee
          </Link>
        </div>
      )}

      <div className="panel-card home-section">
        <div className="home-section-head">
          <div>
            <h3>Tổng quan mentee</h3>
            <p className="muted home-section-note">
              Chỉ xem thông tin mentee. Chỉnh phân loại tại Quản lý mentee.
            </p>
          </div>
          <Link to="/mentees" className="home-section-link">
            Quản lý mentee →
          </Link>
        </div>
        {mentees.length === 0 ? (
          <p className="muted">Chưa có mentee nào.</p>
        ) : (
          <>
            <div className="home-mentee-toolbar">
              <div className="page-search home-mentee-search">
                <label className="page-search-label" htmlFor="home-mentee-search">
                  Tìm kiếm
                  <input
                    id="home-mentee-search"
                    type="search"
                    className="page-search-input"
                    placeholder="Theo tên hoặc số Zalo..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                  />
                </label>
                <span className="muted home-mentee-count">
                  Hiển thị {filteredMentees.length}/{mentees.length} mentee
                </span>
              </div>
              {showDegreeLanguageFilters && (
                <div className="mentee-filter-groups home-mentee-filters">
                  <MenteeFilterDropdown
                    label="Hệ"
                    value={degreeFilter}
                    options={APPLY_DEGREE_FILTER_OPTIONS}
                    onChange={setDegreeFilter}
                  />
                  {showDirectionFilter && (
                    <MenteeFilterDropdown
                      label="Hướng ngành apply"
                      value={directionFilter}
                      options={APPLY_DIRECTION_FILTER_OPTIONS}
                      onChange={setDirectionFilter}
                    />
                  )}
                  <MenteeFilterDropdown
                    label="Tiếng"
                    value={languageFilter}
                    options={APPLY_LANGUAGE_FILTER_OPTIONS}
                    onChange={setLanguageFilter}
                  />
                  {isThanhHaL1 && (
                    <MenteeFilterDropdown
                      label="1 kì tiếng"
                      value={termFilter}
                      options={TERM3_LANGUAGE_FILTER_OPTIONS}
                      onChange={setTermFilter}
                    />
                  )}
                </div>
              )}
            </div>
            {filteredMentees.length === 0 ? (
              <p className="muted page-search-empty">Không tìm thấy mentee phù hợp.</p>
            ) : (
              <div className="table-wrap">
                <table className="home-mentee-password-table">
                  <thead>
                    <tr>
                      <th>Họ tên</th>
                      {showDirectionColumn && <th>Hướng apply</th>}
                      {isThanhHaL1 && <th>Phương hướng NC</th>}
                      <th>Hệ apply</th>
                      {showLanguageColumn && <th>Hệ tiếng</th>}
                      {isThanhHaL1 && <th>Kì tiếng 3/2027</th>}
                      <th>SĐT Zalo</th>
                      <th>Tài liệu hoàn thành</th>
                      <th>Trường đã submit</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredMentees.map((mentee) => (
                      <tr key={mentee.id}>
                        <td>{mentee.full_name || mentee.username}</td>
                        {showDirectionColumn && (
                          <td>
                            {mentee.mentor_apply_direction_label ||
                              mentorApplyDirectionLabel(mentee.mentor_apply_direction)}
                          </td>
                        )}
                        {isThanhHaL1 && (
                          <td>{researchDirectionDisplayText(mentee) || '—'}</td>
                        )}
                        <td>{applyDegreeLevelShortDisplay(mentee)}</td>
                        {showLanguageColumn && (
                          <td>{scholarshipLanguageShortLabel(mentee) || '—'}</td>
                        )}
                        {isThanhHaL1 && <td>{term3LanguageShortDisplay(mentee)}</td>}
                        <td>{mentee.zalo_phone || '—'}</td>
                        <td>
                          {mentee.uploaded_count ?? 0}
                          {mentee.total_documents_count
                            ? ` / ${mentee.total_documents_count}`
                            : ''}
                        </td>
                        <td>
                          {mentee.submitted_schools_count ?? 0}
                          {mentee.total_schools_count
                            ? ` / ${mentee.total_schools_count}`
                            : ''}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}
      </div>

      <div className="home-feedback-grid">
        <div className="panel-card home-section">
          <div className="home-section-head">
            <h3>Chưa xử lí</h3>
            <span className="home-section-count">{unreadFeedback.length} tin chưa đọc</span>
          </div>
          {unreadFeedback.length === 0 ? (
            <p className="muted">Không có tin nhắn chưa đọc.</p>
          ) : (
            <div className="home-feedback-list">
              {unreadFeedback.map((item) => (
                <div key={item.id} className="home-feedback-item home-feedback-item-unread">
                  <div className="home-feedback-item-head">
                    <strong>{item.username}</strong>
                    <span className="muted"> · {item.email}</span>
                  </div>
                  <p className="home-feedback-content">{item.content}</p>
                  <p className="muted home-feedback-time">{formatDateTime(item.created_at)}</p>
                </div>
              ))}
            </div>
          )}
          {unreadFeedback.length > 0 && (
            <Link to="/feedback" className="btn btn-outline btn-sm home-feedback-action">
              Xử lí phản hồi →
            </Link>
          )}
        </div>

        <div className="panel-card home-section">
          <div className="home-section-head">
            <h3>Đã xử lí</h3>
            <span className="home-section-count">{doneFeedback.length} tin</span>
          </div>
          {doneFeedback.length === 0 ? (
            <p className="muted">Chưa có phản hồi đã xử lí.</p>
          ) : (
            <div className="home-feedback-list">
              {doneFeedback.slice(0, 12).map((item) => (
                <div key={item.id} className="home-feedback-item">
                  <div className="home-feedback-item-head">
                    <strong>{item.username}</strong>
                    <span className="status-pill status-done">đã xử lí</span>
                  </div>
                  <p className="home-feedback-content">{item.content}</p>
                  {item.admin_reply && (
                    <p className="home-feedback-reply">
                      <strong>Trả lời:</strong> {item.admin_reply}
                    </p>
                  )}
                  <p className="muted home-feedback-time">
                    {formatDateTime(item.processed_at || item.updated_at || item.created_at)}
                    {canSeeProcessor && item.processed_by_name
                      ? ` · Xử lí bởi ${item.processed_by_name}`
                      : ''}
                  </p>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="quick-links">
        <Link to="/access-requests" className="quick-link">
          Cấp quyền →
        </Link>
        <Link to="/mentees" className="quick-link">
          Quản lý mentee →
        </Link>
        <Link to="/feedback" className="quick-link">
          Phản hồi mentee →
        </Link>
        {admin?.is_super_admin && (
          <Link to="/history" className="quick-link">
            Lịch sử hoạt động →
          </Link>
        )}
      </div>
    </>
  );
}
