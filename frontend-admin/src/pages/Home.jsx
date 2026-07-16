import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import MenteeFilterDropdown from '../components/MenteeFilterDropdown';
import { useAuth } from '../context/AuthContext';
import { api } from '../services/api';
import { isLevel1MentorAccount } from '../utils/mentorDisplay';
import { matchesNameSearch } from '../utils/searchByName';
import {
  APPLY_DEGREE_FILTER_OPTIONS,
  APPLY_DIRECTION_FILTER_OPTIONS,
  APPLY_LANGUAGE_FILTER_OPTIONS,
  applyDegreeLevelShortDisplay,
  MENTOR_APPLY_DIRECTION_FIELDS,
  mentorApplyDirectionCombinedLabel,
  mentorApplyDirectionLabel,
  mentorApplyDirectionWishes,
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

function formatDateInputInVn(date) {
  return new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Ho_Chi_Minh' }).format(date);
}

function vnTomorrowDateInputValue() {
  const tomorrow = new Date();
  tomorrow.setDate(tomorrow.getDate() + 1);
  return formatDateInputInVn(tomorrow);
}

function inboxDescriptionPreview(description) {
  if (!description) return '';
  const lines = description.split('\n').filter((line) => line.trim());
  if (lines.length <= 1) return description;
  return `${lines[0]} (+${lines.length - 1} thay đổi khác)`;
}

function reminderAtIsoFromDateInput(dateStr) {
  return `${dateStr}T00:00:00+07:00`;
}

function inboxItemHasFile(item) {
  if (item?.has_file === false) {
    return false;
  }
  const docId = (item?.doc_id || '').trim();
  if (!docId) {
    return false;
  }
  if (docId === 'personal-declaration') {
    return Boolean((item?.mentee_id || '').trim());
  }
  return true;
}

function isInboxItemDone(item) {
  return item?.status === 'done' || item?.display_state === 'done';
}

function isInboxItemPending(item) {
  return item?.status === 'pending' && !isInboxItemDone(item) && !item?.synthetic;
}

function inboxHeadline(item) {
  return item?.summary_line || item?.action_line || item?.title || '—';
}

export default function Home() {
  const { admin } = useAuth();
  const navigate = useNavigate();
  const [stats, setStats] = useState(null);
  const [mentees, setMentees] = useState([]);
  const [feedback, setFeedback] = useState([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [degreeFilter, setDegreeFilter] = useState('all');
  const [languageFilter, setLanguageFilter] = useState('all');
  const [directionFilter, setDirectionFilter] = useState('all');
  const [termFilter, setTermFilter] = useState('all');
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');
  const [actionError, setActionError] = useState('');
  const [inboxItems, setInboxItems] = useState([]);
  const [inboxBoard, setInboxBoard] = useState(null);
  const [dailySummary, setDailySummary] = useState(null);
  const [archiveDays, setArchiveDays] = useState([]);
  const [inboxPendingCount, setInboxPendingCount] = useState(0);
  const [inboxSavingId, setInboxSavingId] = useState('');
  const [selectedInboxIds, setSelectedInboxIds] = useState([]);
  const [bulkInboxProcessing, setBulkInboxProcessing] = useState(false);
  const [reminderDrafts, setReminderDrafts] = useState({});
  const [collapsedSections, setCollapsedSections] = useState({});
  const [archiveView, setArchiveView] = useState(null);
  const [archiveLoading, setArchiveLoading] = useState(false);
  const [inboxViewer, setInboxViewer] = useState(null);

  useEffect(() => {
    Promise.all([api.getStats(), api.getMentees(), api.getFeedback(), api.getInbox()])
      .then(([statsData, menteeData, feedbackData, inboxData]) => {
        setStats(statsData);
        setMentees(menteeData || []);
        setFeedback(feedbackData || []);
        setInboxItems(inboxData?.items || []);
        setInboxBoard(inboxData?.board || null);
        setDailySummary(inboxData?.daily_summary || null);
        setArchiveDays(inboxData?.archive_days || []);
        setInboxPendingCount(inboxData?.pending_count || 0);
      })
      .catch((err) => setLoadError(err.message))
      .finally(() => setLoading(false));
  }, []);

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
            !mentorApplyDirectionWishes(mentee).includes(directionFilter)
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
          ...(showDirectionFilter ? MENTOR_APPLY_DIRECTION_FIELDS : []),
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
      setInboxBoard(data?.board || null);
      setDailySummary(data?.daily_summary || null);
      setArchiveDays(data?.archive_days || []);
      setInboxPendingCount(data?.pending_count || 0);
    });

  const toggleInboxSelection = (taskId) => {
    setSelectedInboxIds((prev) =>
      prev.includes(taskId) ? prev.filter((id) => id !== taskId) : [...prev, taskId],
    );
  };

  const getSectionSelectableIds = (section) =>
    (section?.items || []).filter(isInboxItemPending).map((item) => item.id);

  const isSectionAllSelected = (section) => {
    const ids = getSectionSelectableIds(section);
    return ids.length > 0 && ids.every((id) => selectedInboxIds.includes(id));
  };

  const selectedCountForSection = (section) =>
    getSectionSelectableIds(section).filter((id) => selectedInboxIds.includes(id)).length;

  const toggleSectionSelectAll = (section) => {
    const ids = getSectionSelectableIds(section);
    if (isSectionAllSelected(section)) {
      const idSet = new Set(ids);
      setSelectedInboxIds((prev) => prev.filter((id) => !idSet.has(id)));
      return;
    }
    setSelectedInboxIds((prev) => [...new Set([...prev, ...ids])]);
  };

  const handleBulkConfirmSection = async (section) => {
    const taskIds = getSectionSelectableIds(section).filter((id) =>
      selectedInboxIds.includes(id),
    );
    if (taskIds.length === 0) {
      setActionError('Chọn ít nhất một mục để xử lí.');
      return;
    }

    setBulkInboxProcessing(true);
    setActionError('');
    try {
      await api.bulkConfirmInboxTasks(taskIds);
      setSelectedInboxIds((prev) => prev.filter((id) => !taskIds.includes(id)));
      await refreshInbox();
    } catch (err) {
      setActionError(err.message);
    } finally {
      setBulkInboxProcessing(false);
    }
  };

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
      setActionError(err.message);
    } finally {
      setArchiveLoading(false);
    }
  };

  const closeArchiveView = () => setArchiveView(null);

  const closeInboxViewer = () => {
    if (inboxViewer?.url) URL.revokeObjectURL(inboxViewer.url);
    setInboxViewer(null);
  };

  const handleViewInbox = async (item) => {
    if (item?.synthetic && item?.nav_path) {
      navigate(item.nav_path);
      return;
    }

    setInboxSavingId(item.id);
    setActionError('');
    try {
      if (inboxItemHasFile(item)) {
        const preview = await api.fetchInboxDocumentPreview(item);
        setInboxViewer({
          title: item.title || item.action_line || item.summary_line || 'Xem nội dung',
          description: item.description || '',
          url: preview.url,
          mimeType: preview.mimeType || 'application/pdf',
        });
      } else {
        setInboxViewer({
          title: item.title || item.action_line || item.summary_line || 'Xem nội dung',
          description: item.description || '',
          url: '',
          mimeType: '',
        });
      }
    } catch (err) {
      setInboxViewer(null);
      setActionError(err.message);
      setInboxSavingId('');
      return;
    }

    try {
      await api.viewInboxTask(item.id);
      await refreshInbox();
    } catch (err) {
      setActionError(err.message || 'Không ghi nhận được trạng thái xem');
    } finally {
      setInboxSavingId('');
    }
  };

  const handleConfirmInbox = async (taskId) => {
    const item = inboxItems.find((row) => row.id === taskId);
    if (item?.synthetic && item?.nav_path) {
      navigate(item.nav_path);
      return;
    }

    setInboxSavingId(taskId);
    try {
      await api.confirmInboxTask(taskId);
      await refreshInbox();
    } catch (err) {
      setActionError(err.message);
    } finally {
      setInboxSavingId('');
    }
  };

  const handleUpdateReminder = async (taskId) => {
    setInboxSavingId(taskId);
    try {
      const dateStr = reminderDrafts[taskId] || vnTomorrowDateInputValue();
      await api.updateInboxReminder(taskId, {
        reminder_at: reminderAtIsoFromDateInput(dateStr),
      });
      await refreshInbox();
    } catch (err) {
      setActionError(err.message);
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
    const processedByLabel = item.processed_by_label || item.processed_by_name || '';
    const reminderDate = reminderDrafts[item.id] ?? vnTomorrowDateInputValue();

    return (
      <div key={item.id} className={`daily-summary-row ${stateClass}`}>
        <div className="daily-summary-main">
          <span className="daily-summary-action">{inboxHeadline(item)}</span>
          <span className={`daily-summary-status-line daily-summary-badge ${statusClass}`}>
            {statusLine}
          </span>
          {isDone && processedByLabel && !statusLine.includes(processedByLabel) && (
            <span className="daily-summary-processed-by">{processedByLabel}</span>
          )}
        </div>
        {!readOnly && !isDone && (
          <div className="daily-summary-actions-inline">
            <button
              type="button"
              className="btn btn-outline btn-sm daily-summary-btn"
              disabled={inboxSavingId === item.id}
              onClick={() => handleViewInbox(item)}
            >
              Xem
            </button>
            {!item.synthetic && (
              <>
                <button
                  type="button"
                  className="btn btn-sm daily-summary-btn daily-summary-btn-done"
                  disabled={inboxSavingId === item.id}
                  onClick={() => handleConfirmInbox(item.id)}
                >
                  Đã xử lí
                </button>
                <label className="daily-summary-reminder-field">
                  Hẹn xử lí (ngày)
                  <input
                    type="date"
                    value={reminderDate}
                    min={formatDateInputInVn(new Date())}
                    onChange={(e) =>
                      setReminderDrafts((prev) => ({
                        ...prev,
                        [item.id]: e.target.value,
                      }))
                    }
                  />
                </label>
                <button
                  type="button"
                  className="btn btn-primary btn-sm daily-summary-btn"
                  disabled={inboxSavingId === item.id}
                  onClick={() => handleUpdateReminder(item.id)}
                >
                  Lưu nhắc hẹn
                </button>
              </>
            )}
          </div>
        )}
      </div>
    );
  };

  const renderInboxBoardItem = (item) => {
    const isDone = isInboxItemDone(item);
    const isPending = isInboxItemPending(item);
    const isViewed = !isDone && (item.display_state === 'viewed' || Boolean(item.viewed_at));
    const stateClass = isDone ? 'is-done' : isViewed ? 'is-viewed' : 'is-new';
    const statusClass = isDone ? 'is-done' : isViewed ? 'is-viewed' : 'is-new';
    const statusLine =
      item.status_line ||
      (isDone ? 'Đã xử lí' : isViewed ? 'Đã xem · chưa xử lí' : 'Chưa xem');
    const processedByLabel = item.processed_by_label || item.processed_by_name || '';
    const reminderDate = reminderDrafts[item.id] ?? vnTomorrowDateInputValue();
    const actionLine = inboxHeadline(item);
    const isSynthetic = Boolean(item.synthetic);

    return (
      <div key={item.id} className={`home-inbox-item ${stateClass}`}>
        {isPending ? (
          <div className="home-inbox-check-col">
            <input
              type="checkbox"
              checked={selectedInboxIds.includes(item.id)}
              onChange={() => toggleInboxSelection(item.id)}
              disabled={bulkInboxProcessing || inboxSavingId === item.id}
              aria-label={`Chọn ${actionLine}`}
            />
          </div>
        ) : (
          <div className="home-inbox-check-col home-inbox-check-col-spacer" aria-hidden="true" />
        )}
        <div className="home-inbox-main">
          <strong>{actionLine}</strong>
          {item.description && (
            <p className="home-inbox-desc">{inboxDescriptionPreview(item.description)}</p>
          )}
          <span className={`home-inbox-status status-${item.display_state || 'pending'} ${statusClass}`}>
            {statusLine}
          </span>
          {isDone && processedByLabel && !statusLine.includes(processedByLabel) && (
            <span className="daily-summary-processed-by">{processedByLabel}</span>
          )}
        </div>
        {!isDone && (
          <div className="home-inbox-actions">
            <button
              type="button"
              className="btn btn-outline btn-sm daily-summary-btn"
              disabled={inboxSavingId === item.id || bulkInboxProcessing}
              onClick={() => handleViewInbox(item)}
            >
              Xem
            </button>
            {!isSynthetic && (
              <>
                <button
                  type="button"
                  className="btn btn-sm daily-summary-btn daily-summary-btn-done"
                  disabled={inboxSavingId === item.id || bulkInboxProcessing}
                  onClick={() => handleConfirmInbox(item.id)}
                >
                  Đã xử lí
                </button>
                <label className="home-inbox-reminder-field">
                  Hẹn xử lí (ngày)
                  <input
                    type="date"
                    value={reminderDate}
                    min={formatDateInputInVn(new Date())}
                    onChange={(e) =>
                      setReminderDrafts((prev) => ({
                        ...prev,
                        [item.id]: e.target.value,
                      }))
                    }
                  />
                </label>
                <button
                  type="button"
                  className="btn btn-primary btn-sm daily-summary-btn"
                  disabled={inboxSavingId === item.id || bulkInboxProcessing}
                  onClick={() => handleUpdateReminder(item.id)}
                >
                  Lưu nhắc hẹn
                </button>
              </>
            )}
          </div>
        )}
      </div>
    );
  };

  // Unprocessed items first, processed items last; stable sort keeps the
  // existing relative order (e.g. newest-first) within each status group.
  const byProcessedStatus = (a, b) => Number(isInboxItemDone(a)) - Number(isInboxItemDone(b));

  const inboxBoardSections = (inboxBoard?.sections || [])
    .filter((section) => (section?.item_count || 0) > 0)
    .map((section) => ({
      ...section,
      items: [...(section.items || [])].sort(byProcessedStatus),
    }));

  const sortedDailySummaryItems = [...(dailySummary?.items || [])].sort(byProcessedStatus);

  if (loading) return <p className="loader">Đang tải...</p>;
  if (loadError) return <p className="form-error">{loadError}</p>;

  return (
    <>
      {actionError && <p className="form-error home-action-error">{actionError}</p>}

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
          <span className="stat-label">Việc chưa xử lí</span>
          <strong className="stat-value accent">{inboxPendingCount ?? 0}</strong>
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
      </div>

      {inboxBoardSections.length > 0 && (
        <div className="panel-card home-inbox-panel">
          <button
            type="button"
            className="daily-summary-head"
            onClick={() => toggleSection('inboxBoard')}
            aria-expanded={!collapsedSections.inboxBoard}
          >
            <span className="daily-summary-title">
              {inboxBoard?.title || 'Mail'}
            </span>
            <span className="daily-summary-toggle">
              {collapsedSections.inboxBoard ? 'Mở rộng' : 'Thu gọn'}
            </span>
          </button>
          {!collapsedSections.inboxBoard && (
            <div className="daily-summary-body">
              {inboxBoard?.date_label && (
                <p className="daily-summary-date">Ngày {inboxBoard.date_label}</p>
              )}
              <div className="home-inbox-board">
                {inboxBoardSections.map((section) => {
                  const sectionKey = `inbox-${section.key}`;
                  const selectableCount = getSectionSelectableIds(section).length;
                  const selectedCount = selectedCountForSection(section);

                  return (
                    <div key={section.key} className="home-inbox-section">
                      <button
                        type="button"
                        className="home-inbox-section-head"
                        onClick={() => toggleSection(sectionKey)}
                        aria-expanded={!collapsedSections[sectionKey]}
                      >
                        <span>
                          {section.label}
                          <span className="home-inbox-section-count">
                            {section.pending_count > 0
                              ? `${section.pending_count} chưa xử lí`
                              : `${section.item_count} mục`}
                          </span>
                        </span>
                        <span className="home-inbox-section-toggle">
                          {collapsedSections[sectionKey] ? 'Mở rộng' : 'Thu gọn'}
                        </span>
                      </button>
                      {!collapsedSections[sectionKey] && (
                        <>
                          {selectableCount > 0 && (
                            <div className="home-inbox-bulk-toolbar">
                              <label className="checkbox-label home-inbox-select-all">
                                <input
                                  type="checkbox"
                                  checked={isSectionAllSelected(section)}
                                  onChange={() => toggleSectionSelectAll(section)}
                                  disabled={bulkInboxProcessing}
                                />
                                Chọn tất cả
                              </label>
                              {selectedCount > 0 && (
                                <button
                                  type="button"
                                  className="btn btn-sm daily-summary-btn-done"
                                  disabled={bulkInboxProcessing}
                                  onClick={() => handleBulkConfirmSection(section)}
                                >
                                  {bulkInboxProcessing
                                    ? 'Đang xử lý...'
                                    : `Đã xử lí hàng loạt (${selectedCount})`}
                                </button>
                              )}
                            </div>
                          )}
                          <div className="home-inbox-list">
                            {(section.items || []).map((item) => renderInboxBoardItem(item))}
                          </div>
                        </>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      )}

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
                      {sortedDailySummaryItems.map((item) => renderDailySummaryRow(item))}
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

      {inboxViewer && (
        <div className="modal-backdrop" onClick={closeInboxViewer} role="presentation">
          <div
            className="modal-card doc-viewer-modal"
            role="dialog"
            aria-modal="true"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="doc-viewer-head">
              <div>
                <h3>{inboxViewer.title}</h3>
                {inboxViewer.description && (
                  <p className="muted daily-summary-viewer-desc">{inboxViewer.description}</p>
                )}
              </div>
              <button type="button" className="btn btn-outline btn-sm" onClick={closeInboxViewer}>
                Đóng
              </button>
            </div>
            {inboxViewer.url && (
              <div className="doc-viewer-body">
                {inboxViewer.mimeType.startsWith('image/') ? (
                  <img
                    src={inboxViewer.url}
                    alt={inboxViewer.title}
                    className="doc-viewer-image"
                  />
                ) : (
                  <iframe
                    title={inboxViewer.title}
                    src={inboxViewer.url}
                    className="doc-viewer-frame"
                  />
                )}
              </div>
            )}
          </div>
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
          <button
            type="button"
            className="home-section-collapse-trigger"
            onClick={() => toggleSection('mentees')}
            aria-expanded={!collapsedSections.mentees}
          >
            <div>
              <h3>Tổng quan mentee</h3>
              <p className="muted home-section-note">
                Chỉ xem thông tin mentee. Chỉnh phân loại tại Quản lý mentee.
              </p>
            </div>
            <span className="daily-summary-toggle">
              {collapsedSections.mentees ? 'Mở rộng' : 'Thu gọn'}
            </span>
          </button>
          <Link to="/mentees" className="home-section-link">
            Quản lý mentee →
          </Link>
        </div>
        {!collapsedSections.mentees &&
          (mentees.length === 0 ? (
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
                            {mentorApplyDirectionCombinedLabel(mentee) ||
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
          ))}
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
