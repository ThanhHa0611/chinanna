import { useEffect, useMemo, useRef, useState } from 'react';
import ApplyProgressPanel from '../components/ApplyProgressPanel';
import HdnkNckhPanel from '../components/HdnkNckhPanel';
import MenteeClassificationFields from '../components/MenteeClassificationFields';
import MenteeFilterDropdown from '../components/MenteeFilterDropdown';
import { buildWatermarkLabel } from '../components/ScreenProtection';
import { isMaiChiTeam, isThanhHaTeam } from '../data/hdnkNckh';
import {
  APPLY_DEGREE_FILTER_OPTIONS,
  APPLY_LANGUAGE_FILTER_OPTIONS,
  applyDegreeLevelLabel,
  menteeClassificationSummaryLine,
  menteeMaiChiClassificationLine,
  mentorApplyDirectionLabel,
  normalizeScholarshipSystemValue,
  patchMenteeSummaryFromDetail,
  researchDirectionDisplayText,
  scholarshipLanguageShortLabel,
  term3LanguageSemesterLabel,
} from '../data/applyDegree';
import { isLevel1MentorAccount } from '../utils/mentorDisplay';
import { getUnreadL2Activity, mergeL2ActivityPayload } from '../utils/l2Activity';
import {
  dismissMenteeAttention,
  menteeAttentionReasons,
  menteeNeedsAttention,
  pinMenteeAttentionUnread,
} from '../utils/menteeAttention';
import { useAuth } from '../context/AuthContext';
import { useDeviceMode } from '../context/DeviceModeContext';
import { api } from '../services/api';
import { matchesNameSearch } from '../utils/searchByName';
import { formatDateTime } from '../utils/formatDateTime';
import { formatLevel1MentorLine } from '../utils/mentorDisplay';

const MENTOR_STATUS_LABELS = {
  'chờ phản hồi': 'Chờ phản hồi',
  'đã duyệt': 'Đã duyệt',
  'cần chỉnh sửa': 'Cần chỉnh sửa',
};

const MENTOR_UPLOADABLE_DOC_IDS = new Set(['study-plan', 'cv']);
const MENTOR_UPLOAD_ACCEPT = '.jpg,.jpeg,.png,.pdf,.doc,.docx';

const isMentorOnlyDoc = (doc) =>
  Boolean(doc?.mentor_only || doc?.doc_id === 'supporting-materials');

const SUPPORTING_BUNDLE_DOC_IDS = ['cv', 'research', 'award'];

function buildSupportingMaterialsDoc(documents, scholarshipSystem) {
  const bundleCount = documents.filter(
    (doc) => SUPPORTING_BUNDLE_DOC_IDS.includes(doc.doc_id) && doc.has_file,
  ).length;
  return {
    doc_id: 'supporting-materials',
    label: 'Gộp CV + Bài báo + Tài liệu khác',
    download_label: scholarshipSystem === 'chinese' ? '其他支撑材料' : 'Supporting Materials',
    uploaded: bundleCount > 0,
    has_file: bundleCount > 0,
    mentor_only: true,
    is_bundle: true,
    bundle_file_count: bundleCount,
  };
}

function ensureDisplayDocuments(documents, mentee) {
  if (!mentee || !documents.length) return documents;
  if (documents.some((doc) => doc.doc_id === 'supporting-materials')) {
    return documents;
  }
  return [...documents, buildSupportingMaterialsDoc(documents, mentee.scholarship_system)];
}

function countMenteeApplyDocStats(documents) {
  const applyDocs = (documents || []).filter((doc) => doc.doc_id !== 'supporting-materials');
  return {
    uploaded_count: applyDocs.filter((doc) => doc.uploaded).length,
    approved_count: applyDocs.filter(
      (doc) => doc.uploaded && doc.mentor_status === 'đã duyệt',
    ).length,
  };
}

function patchMenteeApplyDocCounts(mentee, documents) {
  const stats = countMenteeApplyDocStats(documents);
  return { ...mentee, ...stats };
}

const MENTEE_SECTION_SEEN_KEY = 'mentor-mentee-sections-v1';

const LANGUAGE_LABELS = { english: 'Tiếng Anh', chinese: 'Tiếng Trung' };

const ENGLISH_SKILL_FIELDS = [
  { key: 'overall', label: 'Overall' },
  { key: 'listening', label: 'Nghe' },
  { key: 'speaking', label: 'Nói' },
  { key: 'reading', label: 'Đọc' },
  { key: 'writing', label: 'Viết' },
];

const CHINESE_SKILL_FIELDS = [
  { key: 'overall', label: 'Overall' },
  { key: 'listening', label: 'Nghe' },
  { key: 'reading', label: 'Đọc' },
  { key: 'writing', label: 'Viết' },
  { key: 'hskk', label: 'HSKK' },
];

function buildScoreUpdateMap(scoreUpdates) {
  const map = {};
  for (const entry of scoreUpdates || []) {
    if (entry.value_type !== 'new') continue;
    const key = `${entry.language}:${entry.skill}`;
    map[key] = {
      previous: entry.previous_value || '',
      next: entry.new_value || '',
    };
  }
  return map;
}

function renderScoreValue(skillKey, langKey, block, updateMap) {
  const current = String(block?.[skillKey] || '').trim();
  const update = updateMap[`${langKey}:${skillKey}`];

  if (!current && !update?.next) {
    return '—';
  }

  if (update?.previous && update.previous !== (current || update.next)) {
    return (
      <>
        <span className="language-score-old">{update.previous}</span>
        <span className="language-score-new">{current || update.next}</span>
      </>
    );
  }

  return current || update?.next || '—';
}

function getLanguageDocument(mentee) {
  return (mentee?.documents || []).find((doc) => doc.doc_id === 'language');
}

function renderLanguageScoresPanel(languageDoc) {
  if (!languageDoc) {
    return <p className="muted">Mentee chưa nhập điểm chứng chỉ ngoại ngữ.</p>;
  }

  const languages = languageDoc.languages || [];
  const certificateName = languageDoc.certificate_name || '';
  const mentorHandles = languageDoc.mentor_handles || languageDoc.mentor_handles_update;
  const updateMap = buildScoreUpdateMap(languageDoc.score_updates);
  const english = languageDoc.english || {};
  const chinese = languageDoc.chinese || {};

  const hasAnyScore =
    ENGLISH_SKILL_FIELDS.some((field) => english[field.key]) ||
    CHINESE_SKILL_FIELDS.some((field) => chinese[field.key]) ||
    Object.keys(updateMap).length > 0;

  if (!certificateName && !hasAnyScore && languages.length === 0) {
    return <p className="muted">Mentee chưa nhập điểm chứng chỉ ngoại ngữ.</p>;
  }

  const langsToShow = [...languages];
  if (langsToShow.length === 0) {
    if (ENGLISH_SKILL_FIELDS.some((field) => english[field.key])) langsToShow.push('english');
    if (CHINESE_SKILL_FIELDS.some((field) => chinese[field.key])) langsToShow.push('chinese');
  }

  return (
    <div className="mentee-language-scores">
      <h4 className="mentee-language-scores-title">Chứng chỉ ngoại ngữ</h4>
      {certificateName && (
        <p className="mentee-language-cert">
          <span className="info-label">Tên chứng chỉ</span>
          <strong>{certificateName}</strong>
        </p>
      )}
      {mentorHandles && (
        <p className="mentee-language-mentor-badge">Mentee yêu cầu mentor cập nhật điểm</p>
      )}
      {langsToShow.map((langKey) => {
        const block = langKey === 'chinese' ? chinese : english;
        const fields = langKey === 'chinese' ? CHINESE_SKILL_FIELDS : ENGLISH_SKILL_FIELDS;
        const visibleFields = fields.filter((field) => {
          const value = String(block?.[field.key] || '').trim();
          const update = updateMap[`${langKey}:${field.key}`];
          return value || update?.next || update?.previous;
        });
        if (visibleFields.length === 0) return null;
        return (
          <div key={langKey} className="language-scores-group">
            <strong className="language-scores-lang">{LANGUAGE_LABELS[langKey] || langKey}</strong>
            <div className="language-scores-grid">
              {visibleFields.map((field) => (
                <div key={field.key} className="language-score-item">
                  <span className="info-label">{field.label}</span>
                  <span className="language-score-value">
                    {renderScoreValue(field.key, langKey, block, updateMap)}
                  </span>
                </div>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function languageScoresSignature(languageDoc) {
  if (!languageDoc) return '';
  return [
    languageDoc.certificate_name,
    languageDoc.mentor_handles_update,
    languageDoc.score_updated_at,
    JSON.stringify(languageDoc.english || {}),
    JSON.stringify(languageDoc.chinese || {}),
    (languageDoc.score_updates || [])
      .map((entry) => `${entry.language}:${entry.skill}:${entry.new_value}`)
      .join(','),
  ].join('|');
}

function readSeenSections(menteeId) {
  try {
    const raw = localStorage.getItem(MENTEE_SECTION_SEEN_KEY);
    const all = raw ? JSON.parse(raw) : {};
    return all[menteeId] || {};
  } catch {
    return {};
  }
}

function saveSeenSection(menteeId, sectionKey, signature) {
  try {
    const raw = localStorage.getItem(MENTEE_SECTION_SEEN_KEY);
    const all = raw ? JSON.parse(raw) : {};
    all[menteeId] = { ...(all[menteeId] || {}), [sectionKey]: signature };
    localStorage.setItem(MENTEE_SECTION_SEEN_KEY, JSON.stringify(all));
  } catch {
    // ignore storage errors
  }
}

function computeSectionSignatures(mentee) {
  const parent = mentee.parent_account;
  return {
    info: [
      mentee.full_name,
      mentee.email,
      mentee.zalo_phone,
      mentee.apply_direction,
      mentee.mentor_apply_direction,
      mentee.apply_degree_level,
      mentee.research_direction,
      mentee.term3_2027_language_semester,
      mentee.scholarship_system,
      mentee.parent_email,
      mentee.apply_clone_email,
      mentee.apply_clone_password,
      mentee.mentor?.email,
      languageScoresSignature(getLanguageDocument(mentee)),
    ].join('|'),
    device: [
      mentee.pending_login_requests_count,
      mentee.login_unique_ip_count,
      mentee.login_unique_device_count,
      mentee.login_anomaly_unread,
      parent?.pending_login_requests_count,
      parent?.login_unique_ip_count,
      parent?.login_unique_device_count,
      (mentee.login_events || []).length,
      (parent?.login_events || []).length,
    ].join('|'),
    documents: [
      mentee.unread_documents_count,
      mentee.processed_documents_count,
      mentee.uploaded_count,
      mentee.approved_count,
      mentee.preferred_schools_note_unread,
      mentee.preferred_schools_note,
      (mentee.documents || [])
        .filter((doc) => doc.mentor_unread)
        .map((doc) => doc.doc_id)
        .join(','),
    ].join('|'),
    applyProgress: [
      mentee.apply_progress_pending_count,
      mentee.apply_progress_l2_unread,
      mentee.apply_progress?.updated_at,
      JSON.stringify(mentee.apply_progress?.rows || []),
    ].join('|'),
    hdnkNckh: [
      mentee.hdnk_nckh_l1_unread,
      mentee.hdnk_nckh_reminder_unread,
      mentee.hdnk_nckh?.mentee_updated_at,
      JSON.stringify(mentee.hdnk_nckh?.entries || []),
    ].join('|'),
    messages: String(mentee.unread_feedback_count || 0),
    applyProgressL2: getUnreadL2Activity(mentee, 'applyProgress')
      .map((item) => item.id)
      .join(','),
    documentsL2: getUnreadL2Activity(mentee, 'documents')
      .map((item) => item.id)
      .join(','),
    messagesL2: getUnreadL2Activity(mentee, 'messages')
      .map((item) => item.id)
      .join(','),
    deviceL2: getUnreadL2Activity(mentee, 'device')
      .map((item) => item.id)
      .join(','),
  };
}

function computeSectionAlerts(mentee, isSuperAdmin, isLevel1 = false) {
  const l2Alert = (sectionKey) => isLevel1 && getUnreadL2Activity(mentee, sectionKey).length > 0;
  return {
    info: false,
    device: l2Alert('device'),
    documents:
      (mentee.unread_documents_count || 0) > 0 ||
      Boolean(mentee.preferred_schools_note_unread) ||
      l2Alert('documents'),
    applyProgress:
      (mentee.apply_progress_pending_count || 0) > 0 ||
      (!isLevel1 && Boolean(mentee.apply_progress_l2_unread)) ||
      l2Alert('applyProgress'),
    hdnkNckh:
      isLevel1 &&
      (Boolean(mentee.hdnk_nckh_l1_unread) || Boolean(mentee.hdnk_nckh_reminder_unread)),
    messages: (mentee.unread_feedback_count || 0) > 0 || l2Alert('messages'),
  };
}

function shouldExpandSection(sectionKey, signature, seen, alerts) {
  if (alerts[sectionKey]) return true;
  if (seen[sectionKey] == null) return true;
  return signature !== seen[sectionKey];
}

function sectionHasNotification(sectionKey, signature, seen, alerts, showAttention = true) {
  if (alerts[sectionKey]) return showAttention;
  if (seen[sectionKey] == null) return false;
  return signature !== seen[sectionKey];
}

function buildInitialExpandedSections(mentee, isSuperAdmin, isLevel1 = false) {
  const seen = readSeenSections(mentee.id);
  const signatures = computeSectionSignatures(mentee);
  const alerts = computeSectionAlerts(mentee, isSuperAdmin, isLevel1);
  return {
    info: shouldExpandSection('info', signatures.info, seen, alerts),
    device: shouldExpandSection('device', signatures.device, seen, alerts),
    documents: shouldExpandSection('documents', signatures.documents, seen, alerts),
    applyProgress: shouldExpandSection('applyProgress', signatures.applyProgress, seen, alerts),
    hdnkNckh: shouldExpandSection('hdnkNckh', signatures.hdnkNckh, seen, alerts),
    messages: shouldExpandSection('messages', signatures.messages, seen, alerts),
  };
}

export default function Mentees() {
  const { admin } = useAuth();
  const { isPhone } = useDeviceMode() || {};
  const watermarkText = buildWatermarkLabel(admin);
  const isSuperAdmin = Boolean(admin?.is_super_admin);
  const isLevel1 = isLevel1MentorAccount(admin);
  const isThanhHa = isThanhHaTeam(admin);
  const isMaiChi = isMaiChiTeam(admin);
  const isThanhHaL1 = isLevel1 && isThanhHa;
  const isMaiChiL1 = isLevel1 && isMaiChi;
  const [mentees, setMentees] = useState([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [degreeFilter, setDegreeFilter] = useState('all');
  const [languageFilter, setLanguageFilter] = useState('all');
  const [selectedId, setSelectedId] = useState('');
  const [selectedMentee, setSelectedMentee] = useState(null);
  const [loadingList, setLoadingList] = useState(true);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [viewingDocId, setViewingDocId] = useState('');
  const [commentTarget, setCommentTarget] = useState(null);
  const [commentNote, setCommentNote] = useState('');
  const [commentStatus, setCommentStatus] = useState('cần chỉnh sửa');
  const [commentSubmitting, setCommentSubmitting] = useState(false);
  const [selectedDownloadIds, setSelectedDownloadIds] = useState([]);
  const [selectedRemindIds, setSelectedRemindIds] = useState([]);
  const [selectedApproveIds, setSelectedApproveIds] = useState([]);
  const [reminderSending, setReminderSending] = useState(false);
  const [profileReminderSending, setProfileReminderSending] = useState(false);
  const [bulkApproving, setBulkApproving] = useState(false);
  const [deletingMentee, setDeletingMentee] = useState(false);
  const [docDownloadSettings, setDocDownloadSettings] = useState({});
  const [globalDownloadSettings, setGlobalDownloadSettings] = useState({
    format: 'pdf',
    variant: 'original',
  });
  const [bulkDownloading, setBulkDownloading] = useState(false);
  const [viewerDoc, setViewerDoc] = useState(null);
  const [viewerUrl, setViewerUrl] = useState('');
  const [viewerMime, setViewerMime] = useState('');
  const [mentorUploadingDocId, setMentorUploadingDocId] = useState('');
  const [docActionSavingId, setDocActionSavingId] = useState('');
  const [docScheduleId, setDocScheduleId] = useState('');
  const [docScheduleDrafts, setDocScheduleDrafts] = useState({});
  const [expandedSections, setExpandedSections] = useState({
    info: true,
    device: true,
    documents: true,
    messages: true,
  });
  const [menteeFeedback, setMenteeFeedback] = useState([]);
  const [menteeFeedbackUnread, setMenteeFeedbackUnread] = useState(0);
  const [feedbackReplyDrafts, setFeedbackReplyDrafts] = useState({});
  const [feedbackSavingId, setFeedbackSavingId] = useState('');
  const messagesSectionWasExpanded = useRef(false);
  const documentsSectionWasExpanded = useRef(false);
  const applyProgressSectionWasExpanded = useRef(false);
  const markReadRequestId = useRef(0);
  const ackPreferredNoteRequestId = useRef(0);
  const ackApplyProgressL2RequestId = useRef(0);
  const ackL2ActivityRequestId = useRef(0);
  const [attentionRevision, setAttentionRevision] = useState(0);
  const [classificationSaving, setClassificationSaving] = useState('');
  const menteeApplyDirectionSubtitle = (mentee) =>
    mentee?.mentor_apply_direction_label ||
    mentorApplyDirectionLabel(mentee?.mentor_apply_direction);

  const menteeDisplayName = (mentee) =>
    (mentee?.full_name || '').trim() || mentee?.username || mentee?.email || '—';

  const showThanhHaFolderMeta = (mentee) => isThanhHa && mentee?.mentor === 'Thanh Hà';
  const showMaiChiFolderMeta = (mentee) => mentee?.mentor === 'Mai Chi';

  const menteeInfoSectionMeta = (mentee) =>
    showThanhHaFolderMeta(mentee)
      ? [menteeDisplayName(mentee), menteeClassificationSummaryLine(mentee)]
          .filter(Boolean)
          .join(' · ')
      : showMaiChiFolderMeta(mentee)
        ? [menteeDisplayName(mentee), menteeMaiChiClassificationLine(mentee)]
            .filter(Boolean)
            .join(' · ')
        : [mentee?.full_name, menteeApplyDirectionSubtitle(mentee)].filter(Boolean).join(' · ') ||
          '—';

  const menteeAttentionOptions = { isSuperAdmin, isLevel1 };

  const loadMentees = () =>
    api.getMentees().then((data) => {
      setMentees(data);
      if (data.length === 0) {
        setSelectedId('');
        setSelectedMentee(null);
      } else if (!data.some((item) => item.id === selectedId)) {
        if (isPhone) {
          setSelectedId('');
          setSelectedMentee(null);
        } else {
          setSelectedId(data[0].id);
        }
      }
    });

  useEffect(() => {
    loadMentees()
      .catch((err) => setError(err.message))
      .finally(() => setLoadingList(false));
  }, []);

  useEffect(() => {
    if (!selectedId) {
      setSelectedMentee(null);
      return;
    }

    setLoadingDetail(true);
    setError('');
    api
      .getMentee(selectedId)
      .then((data) => {
        dismissMenteeAttention(data, { isSuperAdmin, isLevel1 });
        setAttentionRevision((value) => value + 1);
        setSelectedMentee(data);
        setMentees((prev) =>
          prev.map((item) =>
            item.id === data.id
              ? {
                  ...item,
                  full_name: data.full_name,
                  mentor_apply_direction: data.mentor_apply_direction,
                  mentor_apply_direction_label: data.mentor_apply_direction_label,
                  apply_degree_level: data.apply_degree_level,
                  apply_degree_level_label: data.apply_degree_level_label,
                  term3_2027_language_semester: data.term3_2027_language_semester,
                  term3_2027_language_semester_label: data.term3_2027_language_semester_label,
                  research_direction: data.research_direction,
                  research_direction_label: data.research_direction_label,
                  scholarship_system: data.scholarship_system,
                  scholarship_system_label: data.scholarship_system_label,
                  uploaded_count: data.uploaded_count,
                  approved_count: data.approved_count,
                }
              : item,
          ),
        );
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoadingDetail(false));
  }, [selectedId, isSuperAdmin, isLevel1]);

  const handlePinMenteeUnread = () => {
    if (!selectedMentee) return;
    pinMenteeAttentionUnread(selectedMentee.id);
    setAttentionRevision((value) => value + 1);
  };

  const applyL2ActivityAck = (payload) => {
    setSelectedMentee((prev) => (prev ? mergeL2ActivityPayload(prev, payload) : prev));
    setMentees((prev) =>
      prev.map((item) =>
        item.id === selectedId ? mergeL2ActivityPayload(item, payload) : item,
      ),
    );
    setAttentionRevision((value) => value + 1);
  };

  useEffect(() => {
    if (!selectedMentee || !isLevel1) return;

    const sections = ['applyProgress', 'documents', 'messages', 'device'].filter(
      (sectionKey) =>
        expandedSections[sectionKey] && getUnreadL2Activity(selectedMentee, sectionKey).length > 0,
    );
    if (!sections.length) return;

    const requestId = ackL2ActivityRequestId.current + 1;
    ackL2ActivityRequestId.current = requestId;
    (async () => {
      try {
        let payload = null;
        for (const sectionKey of sections) {
          payload = await api.ackMenteeL2Activity(selectedMentee.id, { section: sectionKey });
        }
        if (requestId !== ackL2ActivityRequestId.current || !payload) return;
        applyL2ActivityAck(payload);
      } catch {
        // ignore ack errors
      }
    })();
  }, [
    expandedSections.applyProgress,
    expandedSections.documents,
    expandedSections.messages,
    expandedSections.device,
    selectedMentee?.id,
    selectedMentee?.mentor_l2_activity,
    isLevel1,
  ]);

  useEffect(() => {
    setSelectedDownloadIds([]);
    setSelectedRemindIds([]);
    setSelectedApproveIds([]);
    setDocDownloadSettings({});
    setGlobalDownloadSettings({ format: 'pdf', variant: 'original' });
  }, [selectedId]);

  useEffect(() => {
    if (!selectedId) {
      setMenteeFeedback([]);
      setMenteeFeedbackUnread(0);
      setFeedbackReplyDrafts({});
      return;
    }

    api
      .getMenteeFeedback(selectedId)
      .then((data) => {
        setMenteeFeedback(data.items || []);
        setMenteeFeedbackUnread(data.unread_count || 0);
        const drafts = {};
        (data.items || []).forEach((item) => {
          drafts[item.id] = '';
        });
        setFeedbackReplyDrafts(drafts);
      })
      .catch((err) => setError(err.message));
  }, [selectedId]);

  useEffect(() => {
    if (!selectedMentee) return;
    setExpandedSections(buildInitialExpandedSections(selectedMentee, isSuperAdmin, isLevel1));
  }, [selectedMentee?.id, isSuperAdmin, isLevel1]);

  useEffect(() => {
    if (!selectedMentee) return;
    const seen = readSeenSections(selectedMentee.id);
    const signatures = computeSectionSignatures(selectedMentee);
    const alerts = computeSectionAlerts(selectedMentee, isSuperAdmin, isLevel1);
    setExpandedSections((prev) => {
      const next = { ...prev };
      let changed = false;
      ['info', 'device', 'documents', 'applyProgress', 'messages'].forEach((key) => {
        const shouldOpen =
          alerts[key] || (seen[key] != null && signatures[key] !== seen[key]);
        if (shouldOpen && !prev[key]) {
          next[key] = true;
          changed = true;
        }
      });
      return changed ? next : prev;
    });
  }, [selectedMentee, isSuperAdmin]);

  useEffect(() => {
    messagesSectionWasExpanded.current = false;
    documentsSectionWasExpanded.current = false;
    applyProgressSectionWasExpanded.current = false;
    markReadRequestId.current += 1;
    ackPreferredNoteRequestId.current += 1;
    ackApplyProgressL2RequestId.current += 1;
  }, [selectedId]);

  useEffect(() => {
    if (!selectedMentee) return;

    if (!expandedSections.messages) {
      messagesSectionWasExpanded.current = false;
      return;
    }

    if (messagesSectionWasExpanded.current) return;
    messagesSectionWasExpanded.current = true;

    if (menteeFeedbackUnread <= 0) return;

    const requestId = markReadRequestId.current + 1;
    markReadRequestId.current = requestId;
    api
      .markMenteeFeedbackRead(selectedMentee.id)
      .then((result) => {
        if (requestId !== markReadRequestId.current) return;
        setMenteeFeedbackUnread(result.unread_count || 0);
        setMenteeFeedback((prev) =>
          prev.map((item) => ({
            ...item,
            mentor_unread: false,
            mentee_status_label:
              item.mentor_unread || item.status === 'chờ xử lí'
                ? 'Mentor đã nhận được tin nhắn của bạnn rùii'
                : item.mentee_status_label,
          })),
        );
        setMentees((prev) =>
          prev.map((item) =>
            item.id === selectedMentee.id
              ? { ...item, unread_feedback_count: result.unread_count || 0 }
              : item,
          ),
        );
        setSelectedMentee((prev) =>
          prev ? { ...prev, unread_feedback_count: result.unread_count || 0 } : prev,
        );
      })
      .catch(() => {});
  }, [expandedSections.messages, selectedMentee?.id, selectedMentee, menteeFeedbackUnread]);

  useEffect(() => {
    if (!selectedMentee) return;

    if (!expandedSections.documents) {
      documentsSectionWasExpanded.current = false;
      return;
    }

    if (documentsSectionWasExpanded.current) return;
    documentsSectionWasExpanded.current = true;

    if (!selectedMentee.preferred_schools_note_unread) return;

    const requestId = ackPreferredNoteRequestId.current + 1;
    ackPreferredNoteRequestId.current = requestId;
    api
      .ackPreferredSchoolsNote(selectedMentee.id)
      .then(() => {
        if (requestId !== ackPreferredNoteRequestId.current) return;
        setMentees((prev) =>
          prev.map((item) =>
            item.id === selectedMentee.id
              ? { ...item, preferred_schools_note_unread: false }
              : item,
          ),
        );
        setSelectedMentee((prev) => {
          if (!prev) return prev;
          const nextMentee = { ...prev, preferred_schools_note_unread: false };
          const signatures = computeSectionSignatures(nextMentee);
          const alerts = computeSectionAlerts(nextMentee, isSuperAdmin, isLevel1);
          if (!alerts.documents) {
            saveSeenSection(nextMentee.id, 'documents', signatures.documents);
          }
          return nextMentee;
        });
      })
      .catch(() => {});
  }, [
    expandedSections.documents,
    selectedMentee?.id,
    selectedMentee?.preferred_schools_note_unread,
    isSuperAdmin,
  ]);

  useEffect(() => {
    if (!selectedMentee || isLevel1) return;

    if (!expandedSections.applyProgress) {
      applyProgressSectionWasExpanded.current = false;
      return;
    }

    if (applyProgressSectionWasExpanded.current) return;
    applyProgressSectionWasExpanded.current = true;

    if (!selectedMentee.apply_progress_l2_unread) return;

    const requestId = ackApplyProgressL2RequestId.current + 1;
    ackApplyProgressL2RequestId.current = requestId;
    api
      .ackApplyProgressL2(selectedMentee.id)
      .then((payload) => {
        if (requestId !== ackApplyProgressL2RequestId.current) return;
        setMentees((prev) =>
          prev.map((item) =>
            item.id === selectedMentee.id
              ? { ...item, apply_progress_l2_unread: false, apply_progress: payload }
              : item,
          ),
        );
        setSelectedMentee((prev) => {
          if (!prev) return prev;
          const nextMentee = {
            ...prev,
            apply_progress_l2_unread: false,
            apply_progress: payload,
          };
          const signatures = computeSectionSignatures(nextMentee);
          const alerts = computeSectionAlerts(nextMentee, isSuperAdmin, isLevel1);
          if (!alerts.applyProgress) {
            saveSeenSection(nextMentee.id, 'applyProgress', signatures.applyProgress);
          }
          return nextMentee;
        });
      })
      .catch(() => {});
  }, [
    expandedSections.applyProgress,
    selectedMentee?.id,
    selectedMentee?.apply_progress_l2_unread,
    isLevel1,
    isSuperAdmin,
  ]);

  const toggleSection = (sectionKey) => {
    if (!selectedMentee) return;

    setExpandedSections((prev) => {
      const nextExpanded = !prev[sectionKey];
      if (!nextExpanded) {
        const signatures = computeSectionSignatures({
          ...selectedMentee,
          unread_feedback_count:
            sectionKey === 'messages' ? 0 : selectedMentee.unread_feedback_count,
        });
        saveSeenSection(selectedMentee.id, sectionKey, signatures[sectionKey]);
      }
      return { ...prev, [sectionKey]: nextExpanded };
    });
  };

  const markSectionSeenIfQuiet = (mentee, sectionKey) => {
    const signatures = computeSectionSignatures(mentee);
    const alerts = computeSectionAlerts(mentee, isSuperAdmin, isLevel1);
    if (alerts[sectionKey]) return;
    saveSeenSection(mentee.id, sectionKey, signatures[sectionKey]);
    if (sectionKey === 'documents') return;
    setExpandedSections((prev) => ({ ...prev, [sectionKey]: false }));
  };

  const refreshAfterView = async () => {
    const [listData, detailData] = await Promise.all([
      api.getMentees(),
      api.getMentee(selectedId),
    ]);
    setMentees(listData);
    setSelectedMentee(detailData);
    markSectionSeenIfQuiet(detailData, 'documents');
    markSectionSeenIfQuiet(detailData, 'device');
  };

  const patchMenteeDocument = (docItem) => {
    setSelectedMentee((prev) => {
      if (!prev) return prev;
      const documents = (prev.documents || []).map((doc) =>
        doc.doc_id === docItem.doc_id ? { ...doc, ...docItem } : doc,
      );
      const unreadDocumentsCount = documents.filter((doc) => doc.mentor_unread).length;
      const processedDocumentsCount = documents.filter(
        (doc) => doc.uploaded && doc.mentor_processed,
      ).length;
      const nextMentee = patchMenteeApplyDocCounts(
        {
          ...prev,
          documents,
          unread_documents_count: unreadDocumentsCount,
          processed_documents_count: processedDocumentsCount,
        },
        documents,
      );
      const signatures = computeSectionSignatures(nextMentee);
      const alerts = computeSectionAlerts(nextMentee, isSuperAdmin, isLevel1);
      if (!alerts.documents) {
        saveSeenSection(nextMentee.id, 'documents', signatures.documents);
      }
      setMentees((list) =>
        list.map((item) =>
          item.id === nextMentee.id
            ? {
                ...item,
                unread_documents_count: unreadDocumentsCount,
                processed_documents_count: processedDocumentsCount,
                uploaded_count: nextMentee.uploaded_count,
                approved_count: nextMentee.approved_count,
              }
            : item,
        ),
      );
      return nextMentee;
    });
  };

  const handleProcessDocument = async (doc) => {
    if (!selectedMentee || !doc.uploaded) return;
    setDocActionSavingId(doc.doc_id);
    setError('');
    try {
      const updated = await api.markMenteeDocumentProcessed(selectedMentee.id, doc.doc_id);
      patchMenteeDocument(updated);
      setDocScheduleId('');
    } catch (err) {
      setError(err.message);
    } finally {
      setDocActionSavingId('');
    }
  };

  const handleScheduleDocument = async (docId) => {
    if (!selectedMentee || !docScheduleDrafts[docId]) {
      setError('Chọn ngày giờ hẹn xử lí.');
      return;
    }
    setDocActionSavingId(docId);
    setError('');
    try {
      const result = await api.scheduleMenteeDocumentProcess(selectedMentee.id, docId, {
        scheduled_at: new Date(docScheduleDrafts[docId]).toISOString(),
      });
      patchMenteeDocument(result.item);
      setDocScheduleId('');
    } catch (err) {
      setError(err.message);
    } finally {
      setDocActionSavingId('');
    }
  };

  const handleViewDocument = async (doc) => {
    if (!selectedMentee || !doc.uploaded) return;

    if (doc.doc_id === 'personal-declaration') {
      setViewingDocId(doc.doc_id);
      setError('');
      try {
        if (doc.declaration_url) {
          window.open(doc.declaration_url, '_blank', 'noopener,noreferrer');
        } else if (doc.declaration_has_local || doc.has_file) {
          const preview = await api.fetchMenteeDocumentPreview(
            selectedMentee.id,
            doc.doc_id,
          );
          setViewerDoc(doc);
          setViewerUrl(preview.url);
          setViewerMime(preview.mimeType);
        }
        await api.markMenteeDocumentViewed(selectedMentee.id, doc.doc_id);
        await refreshAfterView();
      } catch (err) {
        setError(err.message);
      } finally {
        setViewingDocId('');
      }
      return;
    }

    if (!doc.has_file) {
      setViewingDocId(doc.doc_id);
      try {
        await api.markMenteeDocumentViewed(selectedMentee.id, doc.doc_id);
        await refreshAfterView();
      } catch (err) {
        setError(err.message);
      } finally {
        setViewingDocId('');
      }
      return;
    }

    setViewingDocId(doc.doc_id);
    setError('');
    let previewUrl = '';
    try {
      const preview = await api.fetchMenteeDocumentPreview(selectedMentee.id, doc.doc_id);
      previewUrl = preview.url;
      setViewerDoc(doc);
      setViewerUrl(preview.url);
      setViewerMime(preview.mimeType);
      await api.markMenteeDocumentViewed(selectedMentee.id, doc.doc_id);
      await refreshAfterView();
    } catch (err) {
      if (previewUrl) URL.revokeObjectURL(previewUrl);
      setError(err.message);
    } finally {
      setViewingDocId('');
    }
  };

  const closeDocumentViewer = () => {
    if (viewerUrl) URL.revokeObjectURL(viewerUrl);
    setViewerDoc(null);
    setViewerUrl('');
    setViewerMime('');
  };

  const allDocuments = selectedMentee?.documents || [];
  const displayDocuments = useMemo(
    () => ensureDisplayDocuments(allDocuments, selectedMentee),
    [allDocuments, selectedMentee],
  );
  const menteeApplyDocuments = allDocuments.filter((doc) => !isMentorOnlyDoc(doc));
  const downloadableDocuments = menteeApplyDocuments.filter((doc) => doc.uploaded && doc.has_file);
  const missingDocuments = menteeApplyDocuments.filter((doc) => !doc.uploaded);
  const approvableDocuments = menteeApplyDocuments.filter(
    (doc) => doc.uploaded && doc.mentor_status !== 'đã duyệt',
  );

  const defaultDocDownloadSettings = { format: 'pdf', variant: 'original' };

  const getDocDownloadSettings = (docId) => {
    if (docId === 'global' || docId === 'global-bulk') {
      return globalDownloadSettings;
    }
    return {
      ...defaultDocDownloadSettings,
      ...docDownloadSettings[docId],
    };
  };

  const updateDocDownloadSettings = (docId, patch) => {
    if (docId === 'global' || docId === 'global-bulk') {
      setGlobalDownloadSettings((prev) => {
        const nextGlobal = { ...prev, ...patch };
        const docIds = menteeApplyDocuments.map((doc) => doc.doc_id);
        setDocDownloadSettings(() => {
          const next = {};
          docIds.forEach((id) => {
            next[id] = { ...nextGlobal };
          });
          return next;
        });
        return nextGlobal;
      });
      return;
    }
    setDocDownloadSettings((prev) => ({
      ...prev,
      [docId]: { ...defaultDocDownloadSettings, ...prev[docId], ...patch },
    }));
  };

  const toggleDownloadSelection = (docId) => {
    setSelectedDownloadIds((prev) =>
      prev.includes(docId) ? prev.filter((id) => id !== docId) : [...prev, docId],
    );
  };

  const toggleRemindSelection = (docId) => {
    setSelectedRemindIds((prev) =>
      prev.includes(docId) ? prev.filter((id) => id !== docId) : [...prev, docId],
    );
  };

  const toggleApproveSelection = (docId) => {
    setSelectedApproveIds((prev) =>
      prev.includes(docId) ? prev.filter((id) => id !== docId) : [...prev, docId],
    );
  };

  const toggleSelectAllDownload = () => {
    const ids = downloadableDocuments.map((doc) => doc.doc_id);
    setSelectedDownloadIds((prev) => (prev.length === ids.length ? [] : ids));
  };

  const toggleSelectAllRemind = () => {
    const ids = missingDocuments.map((doc) => doc.doc_id);
    setSelectedRemindIds((prev) => (prev.length === ids.length ? [] : ids));
  };

  const toggleSelectAllApprove = () => {
    const ids = approvableDocuments.map((doc) => doc.doc_id);
    setSelectedApproveIds((prev) => (prev.length === ids.length ? [] : ids));
  };

  const handleSendMissingReminder = async () => {
    if (!selectedMentee || selectedRemindIds.length === 0) {
      setError('Chọn ít nhất một giấy tờ còn thiếu để nhắc nhở.');
      return;
    }
    if (
      !window.confirm(
        `Gửi nhắc nhở cho mentee về ${selectedRemindIds.length} giấy tờ còn thiếu?`,
      )
    ) {
      return;
    }

    setReminderSending(true);
    setError('');
    setMessage('');
    try {
      const result = await api.remindMissingDocuments(selectedMentee.id, selectedRemindIds);
      setMessage(result.message || 'Đã gửi nhắc nhở tới mentee.');
      setSelectedRemindIds([]);
    } catch (err) {
      setError(err.message);
    } finally {
      setReminderSending(false);
    }
  };

  const handleSendProfileInfoReminder = async () => {
    if (!selectedMentee) return;
    const missingCount = selectedMentee.missing_profile_fields?.length || 0;
    if (missingCount === 0) {
      setError('Mentee đã điền đủ thông tin cá nhân.');
      return;
    }
    if (!window.confirm('Gửi nhắc nhở cho mentee bổ sung thông tin cá nhân?')) {
      return;
    }

    setProfileReminderSending(true);
    setError('');
    setMessage('');
    try {
      const result = await api.remindProfileInfo(selectedMentee.id);
      setMessage(result.message || 'Đã gửi nhắc nhở tới mentee.');
      setSelectedMentee((prev) =>
        prev
          ? {
              ...prev,
              profile_info_reminder: result.profile_info_reminder || prev.profile_info_reminder,
            }
          : prev,
      );
    } catch (err) {
      setError(err.message);
    } finally {
      setProfileReminderSending(false);
    }
  };

  const handleBulkApprove = async () => {
    if (!selectedMentee || selectedApproveIds.length === 0) {
      setError('Chọn ít nhất một giấy tờ để duyệt.');
      return;
    }
    if (
      !window.confirm(
        `Duyệt ${selectedApproveIds.length} giấy tờ đã chọn? Mentee sẽ nhận thông báo.`,
      )
    ) {
      return;
    }

    setBulkApproving(true);
    setError('');
    setMessage('');
    try {
      const result = await api.approveSelectedMenteeDocuments(
        selectedMentee.id,
        selectedApproveIds,
      );
      setMessage(result.message || `Đã duyệt ${result.approved_count || 0} giấy tờ.`);
      setSelectedApproveIds([]);

      const itemsById = Object.fromEntries(
        (result.items || []).map((item) => [item.doc_id, item]),
      );
      setSelectedMentee((prev) => {
        if (!prev) return prev;
        const documents = (prev.documents || []).map((doc) =>
          itemsById[doc.doc_id] ? { ...doc, ...itemsById[doc.doc_id] } : doc,
        );
        const unreadDocumentsCount = documents.filter((doc) => doc.mentor_unread).length;
        const nextMentee = patchMenteeApplyDocCounts(
          {
            ...prev,
            documents,
            unread_documents_count: unreadDocumentsCount,
          },
          documents,
        );
        const signatures = computeSectionSignatures(nextMentee);
        const alerts = computeSectionAlerts(nextMentee, isSuperAdmin, isLevel1);
        if (!alerts.documents) {
          saveSeenSection(nextMentee.id, 'documents', signatures.documents);
        }
        setMentees((list) =>
          list.map((item) =>
            item.id === nextMentee.id
              ? {
                  ...item,
                  unread_documents_count: unreadDocumentsCount,
                  uploaded_count: nextMentee.uploaded_count,
                  approved_count: nextMentee.approved_count,
                }
              : item,
          ),
        );
        return nextMentee;
      });
    } catch (err) {
      setError(err.message);
    } finally {
      setBulkApproving(false);
    }
  };

  const handleClassificationChange = async (menteeId, field, value) => {
    setClassificationSaving(`${menteeId}:${field}`);
    setError('');
    try {
      const updated = await api.updateMenteeMentorInfo(menteeId, { [field]: value });
      setSelectedMentee(updated);
      setMentees((prev) =>
        prev.map((item) =>
          item.id === menteeId ? patchMenteeSummaryFromDetail(item, updated) : item,
        ),
      );
    } catch (err) {
      setError(err.message);
    } finally {
      setClassificationSaving('');
    }
  };

  const selectedIsThanhHaMentee = selectedMentee?.mentor === 'Thanh Hà';
  const selectedIsMaiChiMentee = selectedMentee?.mentor === 'Mai Chi';
  const canEditClassification = Boolean(isLevel1 || isSuperAdmin);
  const showThanhHaClassification = isThanhHaL1 && selectedIsThanhHaMentee;
  const showMaiChiClassification = isMaiChiL1 && selectedIsMaiChiMentee;

  const handleDeleteMentee = async () => {
    if (!selectedMentee) return;

    const label = selectedMentee.full_name || selectedMentee.username || selectedMentee.email;
    if (
      !window.confirm(
        `Xóa mentee "${label}"?\n\nToàn bộ hồ sơ, giấy tờ và phản hồi sẽ bị xóa vĩnh viễn.`,
      )
    ) {
      return;
    }

    setDeletingMentee(true);
    setError('');
    setMessage('');
    try {
      const result = await api.deleteMentee(selectedMentee.id);
      setMessage(result.message || 'Đã xóa mentee.');
      setMentees((prev) => prev.filter((item) => item.id !== selectedMentee.id));
      setSelectedId('');
      setSelectedMentee(null);
    } catch (err) {
      setError(err.message);
    } finally {
      setDeletingMentee(false);
    }
  };

  const runBulkDownload = async (docIds, options) => {
    if (!selectedMentee || docIds.length === 0) return;
    setBulkDownloading(true);
    setError('');
    setMessage('');
    try {
      const filename = await api.downloadSelectedMenteeDocuments(selectedMentee.id, docIds, options);
      setMessage(
        docIds.length > 1
          ? `Đã tải đồng loạt ${docIds.length} mục (${filename}).`
          : `Đã tải ${filename}.`,
      );
    } catch (err) {
      setError(err.message);
    } finally {
      setBulkDownloading(false);
    }
  };

  const handleDownloadDocument = async (doc) => {
    await runBulkDownload([doc.doc_id], getDocDownloadSettings(doc.doc_id));
  };

  const handleBulkDownload = async () => {
    const docIds = downloadableDocuments
      .filter((doc) => selectedDownloadIds.includes(doc.doc_id))
      .map((doc) => doc.doc_id);
    if (docIds.length === 0) {
      setError('Chọn ít nhất một giấy tờ có file để tải đồng loạt.');
      return;
    }
    await runBulkDownload(docIds, globalDownloadSettings);
  };

  const handleDownloadSupportingBundle = async () => {
    const docIds = ['cv', 'research', 'award'].filter((docId) =>
      downloadableDocuments.some((doc) => doc.doc_id === docId),
    );
    if (docIds.length === 0) return;

    const settingsList = docIds.map((docId) => getDocDownloadSettings(docId));
    const shared = settingsList[0];
    const allSame = settingsList.every(
      (item) => item.format === shared.format && item.variant === shared.variant,
    );

    if (allSame) {
      await runBulkDownload(docIds, shared);
      return;
    }

    setBulkDownloading(true);
    setError('');
    setMessage('');
    try {
      for (const docId of docIds) {
        await api.downloadSelectedMenteeDocuments(
          selectedMentee.id,
          [docId],
          getDocDownloadSettings(docId),
        );
      }
      setMessage(`Đã tải gói Supporting Materials (${docIds.length} file).`);
    } catch (err) {
      setError(err.message);
    } finally {
      setBulkDownloading(false);
    }
  };

  const renderDocDownloadControls = (docId, { hideDownloadButton = false, inline = false } = {}) => {
    const settings = getDocDownloadSettings(docId);
    const patchSettings = (nextPatch) => updateDocDownloadSettings(docId, nextPatch);

    return (
      <div className={`apply-doc-download-row${inline ? ' apply-doc-download-row-inline' : ''}`}>
        <div className="apply-download-options">
          <span className="apply-download-options-label">Định dạng</span>
          <label className="apply-download-option">
            <input
              type="radio"
              name={`download-format-${docId}`}
              value="pdf"
              checked={settings.format === 'pdf'}
              onChange={() => patchSettings({ format: 'pdf' })}
            />
            PDF
          </label>
          <label className="apply-download-option">
            <input
              type="radio"
              name={`download-format-${docId}`}
              value="png"
              checked={settings.format === 'png'}
              onChange={() => patchSettings({ format: 'png' })}
            />
            PNG
          </label>
        </div>
        <div className="apply-download-options">
          <span className="apply-download-options-label">Dung lượng</span>
          <label className="apply-download-option">
            <input
              type="radio"
              name={`download-variant-${docId}`}
              value="original"
              checked={settings.variant === 'original'}
              onChange={() => patchSettings({ variant: 'original' })}
            />
            Dung lượng gốc
          </label>
          <label className="apply-download-option">
            <input
              type="radio"
              name={`download-variant-${docId}`}
              value="compress_3mb"
              checked={settings.variant === 'compress_3mb'}
              onChange={() => patchSettings({ variant: 'compress_3mb' })}
            />
            3MB
          </label>
          <label className="apply-download-option">
            <input
              type="radio"
              name={`download-variant-${docId}`}
              value="compress_1mb"
              checked={settings.variant === 'compress_1mb'}
              onChange={() => patchSettings({ variant: 'compress_1mb' })}
            />
            1MB
          </label>
        </div>
        {!hideDownloadButton && (
          <button
            type="button"
            className="btn btn-outline btn-sm"
            disabled={bulkDownloading}
            onClick={() => {
              const doc = downloadableDocuments.find((item) => item.doc_id === docId);
              if (doc) handleDownloadDocument(doc);
            }}
          >
            Tải
          </button>
        )}
      </div>
    );
  };

  const refreshMenteeFeedback = async () => {
    if (!selectedId) return;
    const data = await api.getMenteeFeedback(selectedId);
    setMenteeFeedback(data.items || []);
    setMenteeFeedbackUnread(data.unread_count || 0);
    setMentees((prev) =>
      prev.map((item) =>
        item.id === selectedId
          ? { ...item, unread_feedback_count: data.unread_count || 0 }
          : item,
      ),
    );
    setSelectedMentee((prev) =>
      prev ? { ...prev, unread_feedback_count: data.unread_count || 0 } : prev,
    );
    return data;
  };

  const handleFeedbackSend = async (item) => {
    const message = (feedbackReplyDrafts[item.id] || '').trim();
    if (!message) {
      setError('Nhập nội dung trước khi gửi.');
      return;
    }
    setFeedbackSavingId(item.id);
    setError('');
    try {
      await api.updateFeedback(item.id, { message });
      setFeedbackReplyDrafts((prev) => ({ ...prev, [item.id]: '' }));
      setMessage('Đã gửi tin nhắn tới mentee.');
      await refreshMenteeFeedback();
    } catch (err) {
      setError(err.message);
    } finally {
      setFeedbackSavingId('');
    }
  };

  const handleFeedbackMarkRead = async (item) => {
    markReadRequestId.current += 1;
    setFeedbackSavingId(item.id);
    setError('');
    try {
      const updated = await api.updateFeedback(item.id, { mentor_unread: false });
      setMenteeFeedback((prev) =>
        prev.map((row) =>
          row.id === item.id ? { ...row, ...updated, mentor_unread: false } : row,
        ),
      );
      if (item.mentor_unread) {
        const nextUnread = Math.max(0, menteeFeedbackUnread - 1);
        setMenteeFeedbackUnread(nextUnread);
        setMentees((prev) =>
          prev.map((row) =>
            row.id === selectedMentee.id ? { ...row, unread_feedback_count: nextUnread } : row,
          ),
        );
        setSelectedMentee((prev) =>
          prev ? { ...prev, unread_feedback_count: nextUnread } : prev,
        );
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setFeedbackSavingId('');
    }
  };

  const handleFeedbackMarkUnread = async (item) => {
    markReadRequestId.current += 1;
    setFeedbackSavingId(item.id);
    setError('');
    try {
      const updated = await api.updateFeedback(item.id, { mentor_unread: true });
      setMenteeFeedback((prev) =>
        prev.map((row) =>
          row.id === item.id
            ? {
                ...row,
                ...updated,
                mentor_unread: true,
                mentee_status_label: 'chờ xử lí',
              }
            : row,
        ),
      );
      if (!item.mentor_unread) {
        const nextUnread = menteeFeedbackUnread + 1;
        setMenteeFeedbackUnread(nextUnread);
        setMentees((prev) =>
          prev.map((row) =>
            row.id === selectedMentee.id
              ? { ...row, unread_feedback_count: nextUnread }
              : row,
          ),
        );
        setSelectedMentee((prev) =>
          prev ? { ...prev, unread_feedback_count: nextUnread } : prev,
        );
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setFeedbackSavingId('');
    }
  };

  const handleFeedbackDelete = async (item) => {
    if (!window.confirm('Bạn có chắc muốn xóa tin nhắn này? Hành động không thể hoàn tác.')) return;

    setFeedbackSavingId(item.id);
    setError('');
    setMessage('');
    try {
      await api.deleteFeedback(item.id);
      setMessage('Đã xóa tin nhắn.');
      await refreshMenteeFeedback();
    } catch (err) {
      setError(err.message);
    } finally {
      setFeedbackSavingId('');
    }
  };


  const openCommentModal = (doc) => {
    setCommentTarget(doc);
    setCommentNote(doc.mentor_note || '');
    setCommentStatus(doc.mentor_status === 'đã duyệt' ? 'đã duyệt' : 'cần chỉnh sửa');
  };

  const handleSubmitComment = async () => {
    if (!commentTarget || !selectedMentee) return;
    if (commentStatus === 'cần chỉnh sửa' && !commentNote.trim()) {
      setError('Vui lòng nhập nhận xét cho mentee.');
      return;
    }

    setCommentSubmitting(true);
    setError('');
    setMessage('');
    try {
      const result = await api.reviewMenteeDocument(selectedMentee.id, commentTarget.doc_id, {
        mentor_status: commentStatus,
        mentor_note: commentNote.trim(),
      });
      setMessage(
        commentStatus === 'đã duyệt'
          ? `Đã duyệt giấy tờ "${commentTarget.label}".`
          : `Đã gửi nhận xét tới mentee cho "${commentTarget.label}".`,
      );
      setCommentTarget(null);
      setCommentNote('');
      setSelectedMentee((prev) => {
        if (!prev) return prev;
        const documents = (prev.documents || []).map((doc) =>
          doc.doc_id === result.doc_id ? { ...doc, ...result } : doc,
        );
        const unreadDocumentsCount = documents.filter((doc) => doc.mentor_unread).length;
        const nextMentee = patchMenteeApplyDocCounts(
          {
            ...prev,
            documents,
            unread_documents_count: unreadDocumentsCount,
          },
          documents,
        );
        const signatures = computeSectionSignatures(nextMentee);
        const alerts = computeSectionAlerts(nextMentee, isSuperAdmin, isLevel1);
        if (!alerts.documents) {
          saveSeenSection(nextMentee.id, 'documents', signatures.documents);
        }
        setMentees((list) =>
          list.map((item) =>
            item.id === nextMentee.id
              ? {
                  ...item,
                  unread_documents_count: unreadDocumentsCount,
                  processed_documents_count: nextMentee.processed_documents_count,
                  uploaded_count: nextMentee.uploaded_count,
                  approved_count: nextMentee.approved_count,
                }
              : item,
          ),
        );
        return nextMentee;
      });
    } catch (err) {
      setError(err.message);
    } finally {
      setCommentSubmitting(false);
    }
  };

  const handleMentorDocumentUpload = async (docId, file) => {
    if (!selectedMentee || !file || !MENTOR_UPLOADABLE_DOC_IDS.has(docId)) return;

    setMentorUploadingDocId(docId);
    setError('');
    setMessage('');
    try {
      const result = await api.uploadMenteeDocument(selectedMentee.id, docId, file);
      setMessage(`Đã tải lên "${result.label || result.download_label || docId}" cho mentee.`);
      setSelectedMentee((prev) => {
        if (!prev) return prev;
        const documents = ensureDisplayDocuments(
          (prev.documents || []).map((doc) =>
            doc.doc_id === result.doc_id ? { ...doc, ...result } : doc,
          ),
          prev,
        );
        return patchMenteeApplyDocCounts({ ...prev, documents }, documents);
      });
      setMentees((list) =>
        list.map((item) => {
          if (item.id !== selectedMentee.id) return item;
          const documents = ensureDisplayDocuments(
            (item.documents || []).map((doc) =>
              doc.doc_id === result.doc_id ? { ...doc, ...result } : doc,
            ),
            item,
          );
          const patched = patchMenteeApplyDocCounts({ ...item, documents }, documents);
          return {
            ...item,
            uploaded_count: patched.uploaded_count,
            approved_count: patched.approved_count,
          };
        }),
      );
    } catch (err) {
      setError(err.message);
    } finally {
      setMentorUploadingDocId('');
    }
  };

  const renderMenteeFeedbackPanel = () => (
    <div className="mentee-feedback-panel">
      {menteeFeedback.length === 0 ? (
        <p className="muted">Mentee chưa gửi tin nhắn nào.</p>
      ) : (
        <div className="feedback-admin-list">
          {menteeFeedback.map((item, index) => (
            <div
              key={item.id}
              className={`panel-card feedback-admin-item${item.mentor_unread ? ' feedback-admin-item-unread' : ''}`}
            >
              <div className="feedback-admin-top">
                <div className="feedback-admin-head">
                  <div>
                    <strong>Tin #{menteeFeedback.length - index}</strong>
                    {item.mentor_unread && <span className="notify-dot" title="Chưa đọc" />}
                  </div>
                  <span
                    className={`status-pill${item.status === 'đã xử lí' ? ' status-done' : ''}`}
                  >
                    {item.status}
                  </span>
                </div>
                <div className="feedback-admin-meta">
                  <p className="feedback-admin-time">
                    Gửi lúc: {formatDateTime(item.created_at)}
                  </p>
                  <button
                    type="button"
                    className="feedback-delete-btn"
                    aria-label="Xóa tin nhắn"
                    title="Xóa tin nhắn"
                    disabled={feedbackSavingId === item.id}
                    onClick={() => handleFeedbackDelete(item)}
                  >
                    <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
                      <path
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="1.8"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        d="M4 7h16M9 7V5h6v2M7 7l1 12h8l1-12M10 11v6M14 11v6"
                      />
                    </svg>
                  </button>
                </div>
              </div>
              <div className="feedback-thread">
                {(item.messages || []).map((message) => (
                  <div
                    key={message.id}
                    className={`feedback-thread-message feedback-thread-${message.sender}`}
                  >
                    <span className="feedback-thread-label">
                      {message.sender === 'mentor' ? 'Mentor' : 'Mentee'}
                    </span>
                    <p>{message.content}</p>
                    {message.created_at && (
                      <time className="muted">{formatDateTime(message.created_at)}</time>
                    )}
                  </div>
                ))}
              </div>
              <label className="reply-label">
                Nhắn lại mentee
                <textarea
                  rows={3}
                  value={feedbackReplyDrafts[item.id] ?? ''}
                  onChange={(e) =>
                    setFeedbackReplyDrafts((prev) => ({ ...prev, [item.id]: e.target.value }))
                  }
                  placeholder="Viết phản hồi..."
                />
              </label>
              <div className="feedback-admin-actions">
                <button
                  type="button"
                  className="btn btn-primary btn-sm"
                  disabled={feedbackSavingId === item.id}
                  onClick={() => handleFeedbackSend(item)}
                >
                  {feedbackSavingId === item.id ? 'Đang gửi...' : 'Send'}
                </button>
                <button
                  type="button"
                  className="btn btn-outline btn-sm"
                  disabled={feedbackSavingId === item.id || !item.mentor_unread}
                  onClick={() => handleFeedbackMarkRead(item)}
                >
                  Đã đọc
                </button>
                <button
                  type="button"
                  className="btn btn-outline btn-sm"
                  disabled={feedbackSavingId === item.id || item.mentor_unread}
                  onClick={() => handleFeedbackMarkUnread(item)}
                >
                  Chưa đọc
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );

  const renderLoginTrackingPanel = (tracking, userId, title) => {
    if (!tracking) return null;
    const formatLocation = (label, lat, lng) => {
      if (label) return label;
      if (lat != null && lng != null) return `${lat}, ${lng}`;
      return '—';
    };

    return (
      <div className="login-tracking-panel">
        <h4>{title}</h4>
        <div className="mentee-info-grid login-tracking-summary">
          <div>
            <span className="info-label">Số thiết bị</span>
            <strong>{tracking.login_unique_device_count ?? 0}</strong>
          </div>
          <div>
            <span className="info-label">Số IP</span>
            <strong>{tracking.login_unique_ip_count ?? 0}</strong>
          </div>
        </div>
        {tracking.login_events?.length > 0 && (
          <div className="login-tracking-block">
            <span className="info-label">Lịch sử đăng nhập (vị trí & thời gian)</span>
            <ul className="login-tracking-list">
              {tracking.login_events.map((event, index) => (
                <li key={`${event.at || 'event'}-${index}`}>
                  <strong>{formatLocation(event.location_label, event.latitude, event.longitude)}</strong>
                  <span className="muted">
                    {event.at ? formatDateTime(event.at) : '—'}
                    {event.ip ? ` · IP ${event.ip}` : ''}
                  </span>
                  {event.device_label && (
                    <span className="muted login-event-device">{event.device_label}</span>
                  )}
                </li>
              ))}
            </ul>
          </div>
        )}
        {(tracking.login_devices?.length > 0 || tracking.login_ips?.length > 0) && (
          <div className="login-tracking-lists">
            {tracking.login_devices?.length > 0 && (
              <div className="login-tracking-block">
                <span className="info-label">Thiết bị</span>
                <ul className="login-tracking-list">
                  {tracking.login_devices.map((device) => (
                    <li key={device.device_id}>
                      <strong>
                        {!device.approved && <span className="login-unapproved-tag">chưa duyệt · </span>}
                        {device.label || 'Thiết bị không xác định'}
                      </strong>
                      <span className="muted">
                        IP gần nhất: {device.last_ip || '—'}
                        {device.last_seen ? ` · ${formatDateTime(device.last_seen)}` : ''}
                      </span>
                      <span className="muted">
                        Vị trí gần nhất:{' '}
                        {formatLocation(
                          device.last_location,
                          device.last_latitude,
                          device.last_longitude,
                        )}
                        {device.last_location_at
                          ? ` · ${formatDateTime(device.last_location_at)}`
                          : ''}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {tracking.login_ips?.length > 0 && (
              <div className="login-tracking-block">
                <span className="info-label">IP</span>
                <ul className="login-tracking-list">
                  {tracking.login_ips.map((entry) => (
                    <li key={entry.ip}>
                      <strong>
                        {!entry.approved && <span className="login-unapproved-tag">chưa duyệt · </span>}
                        {entry.ip}
                      </strong>
                      <span className="muted">
                        {entry.last_seen ? formatDateTime(entry.last_seen) : '—'}
                        {entry.count ? ` · ${entry.count} lần` : ''}
                      </span>
                      <span className="muted">
                        Vị trí gần nhất:{' '}
                        {formatLocation(
                          entry.last_location,
                          entry.last_latitude,
                          entry.last_longitude,
                        )}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </div>
    );
  };

  const approvedDocumentsCount = menteeApplyDocuments.filter(
    (doc) => doc.uploaded && doc.mentor_status === 'đã duyệt',
  ).length;
  const processedDocumentsCount =
    selectedMentee?.processed_documents_count ??
    menteeApplyDocuments.filter((doc) => doc.uploaded && doc.mentor_processed).length;
  const totalDocumentsCount =
    selectedMentee?.total_documents_count || menteeApplyDocuments.length || 0;
  const allDownloadSelected =
    downloadableDocuments.length > 0 &&
    selectedDownloadIds.length === downloadableDocuments.length;
  const allRemindSelected =
    missingDocuments.length > 0 && selectedRemindIds.length === missingDocuments.length;
  const allApproveSelected =
    approvableDocuments.length > 0 &&
    selectedApproveIds.length === approvableDocuments.length;

  const sectionSignatures = selectedMentee
    ? computeSectionSignatures(selectedMentee)
    : null;
  const sectionSeen = selectedMentee ? readSeenSections(selectedMentee.id) : {};
  const sectionAlerts = selectedMentee
    ? computeSectionAlerts(selectedMentee, isSuperAdmin, isLevel1)
    : { info: false, device: false, documents: false };
  const showMenteeAttention = selectedMentee
    ? menteeNeedsAttention(selectedMentee, menteeAttentionOptions)
    : false;
  const canPinMenteeUnread =
    Boolean(selectedMentee) &&
    menteeAttentionReasons(selectedMentee, menteeAttentionOptions).length > 0 &&
    !showMenteeAttention;

  const renderL2ActivityBanner = (sectionKey) => {
    if (!isLevel1 || !selectedMentee) return null;
    const items = getUnreadL2Activity(selectedMentee, sectionKey);
    if (!items.length) return null;
    return (
      <div className="l2-activity-banner">
        {items.map((item) => (
          <p key={item.id} className="l2-activity-banner-item">
            {item.summary}
          </p>
        ))}
      </div>
    );
  };

  const renderCollapsibleSection = (sectionKey, title, collapsedMeta, children) => {
    const expanded = expandedSections[sectionKey];
    const hasNotification =
      sectionSignatures &&
      sectionHasNotification(
        sectionKey,
        sectionSignatures[sectionKey],
        sectionSeen,
        sectionAlerts,
        showMenteeAttention,
      );

    return (
      <section
        className={`panel-card mentee-section mentee-section-collapsible${
          expanded ? ' is-expanded' : ' is-collapsed'
        }`}
      >
        <button
          type="button"
          className="mentee-section-toggle"
          aria-expanded={expanded}
          onClick={() => toggleSection(sectionKey)}
        >
          <span className="mentee-section-toggle-left">
            <span className={`mentee-section-chevron${expanded ? ' open' : ''}`} aria-hidden>
              ▸
            </span>
            <h3 className="mentee-section-toggle-title">{title}</h3>
            {hasNotification && (
              <span className="section-notify-pill">Có thông báo mới</span>
            )}
          </span>
          {!expanded && collapsedMeta && (
            <span className="mentee-section-toggle-meta muted">{collapsedMeta}</span>
          )}
        </button>
        {expanded && <div className="mentee-section-body">{children}</div>}
      </section>
    );
  };

  const deviceCollapsedMeta = selectedMentee
    ? [
        `${selectedMentee.login_unique_device_count ?? 0} thiết bị`,
        `${selectedMentee.login_unique_ip_count ?? 0} IP`,
      ]
        .filter(Boolean)
        .join(' · ')
    : '';

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
        return matchesNameSearch(mentee, searchQuery, [
          'full_name',
          'username',
          'email',
          'zalo_phone',
          'apply_direction',
          'mentor_apply_direction',
          'apply_degree_level_label',
        ]);
      }),
    [mentees, searchQuery, degreeFilter, languageFilter],
  );

  const menteesNeedingAttentionCount = useMemo(
    () => mentees.filter((mentee) => menteeNeedsAttention(mentee, menteeAttentionOptions)).length,
    [mentees, isSuperAdmin, isLevel1, attentionRevision],
  );

  const showMobileDetail = isPhone && Boolean(selectedId);

  return (
    <>
      <div className="page-head">
        <h2>Danh sách mentee</h2>
        <p>
          {showMobileDetail
            ? 'Xem hồ sơ mentee · bấm quay lại để chọn mentee khác'
            : 'Chọn mentee bên trái để xem thông tin và giấy tờ apply'}
        </p>
      </div>

      {message && <p className="form-success panel-error">{message}</p>}
      {error && <p className="form-error panel-error">{error}</p>}

      {!loadingList && mentees.length > 0 && (
        <div className="page-search mentee-list-filters">
          <label className="page-search-label" htmlFor="mentee-search">
            Tìm kiếm
            <input
              id="mentee-search"
              type="search"
              className="page-search-input"
              placeholder="Theo tên, email hoặc số Zalo..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </label>
          <div className="mentee-filter-groups">
            <MenteeFilterDropdown
              label="Hệ"
              value={degreeFilter}
              options={APPLY_DEGREE_FILTER_OPTIONS}
              onChange={setDegreeFilter}
            />
            <MenteeFilterDropdown
              label="Tiếng"
              value={languageFilter}
              options={APPLY_LANGUAGE_FILTER_OPTIONS}
              onChange={setLanguageFilter}
            />
          </div>
        </div>
      )}

      {loadingList ? (
        <p className="loader">Đang tải...</p>
      ) : mentees.length === 0 ? (
        <div className="panel-card">
          <p className="muted">Chưa có mentee nào.</p>
        </div>
      ) : (
        <div className={`mentee-workspace${showMobileDetail ? ' mentee-workspace-detail-open' : ''}`}>
          <aside className="mentee-folder-panel panel-card">
            <h3 className="mentee-folder-title">
              Mentee
              {menteesNeedingAttentionCount > 0 && (
                <span className="mentee-folder-title-badge" title="Có mentee cần xử lí">
                  {menteesNeedingAttentionCount}
                </span>
              )}
            </h3>
            <div className="mentee-folder-list">
              {filteredMentees.length === 0 ? (
                <p className="muted page-search-empty">Không tìm thấy mentee phù hợp.</p>
              ) : (
              filteredMentees.map((mentee) => {
                const needsAttention = menteeNeedsAttention(mentee, menteeAttentionOptions);
                const attentionTitle = menteeAttentionReasons(mentee, menteeAttentionOptions).join(
                  ' · ',
                );
                return (
                <button
                  key={mentee.id}
                  type="button"
                  className={`mentee-folder-item${selectedId === mentee.id ? ' active' : ''}${
                    needsAttention ? ' mentee-folder-item-alert' : ''
                  }`}
                  onClick={() => setSelectedId(mentee.id)}
                >
                  <span className="mentee-folder-name">
                    {menteeDisplayName(mentee)}
                    <span
                      className="mentee-folder-doc-badge"
                      title="Đã duyệt / đã nộp"
                    >
                      {mentee.approved_count ?? 0}/{mentee.uploaded_count ?? 0}
                    </span>
                    {needsAttention && (
                      <span className="notify-dot" title={attentionTitle || 'Cần xử lí'} />
                    )}
                  </span>
                  {showThanhHaFolderMeta(mentee) ? (
                    <span className="mentee-folder-meta mentee-folder-classification">
                      {menteeClassificationSummaryLine(mentee)}
                    </span>
                  ) : showMaiChiFolderMeta(mentee) ? (
                    <span className="mentee-folder-meta mentee-folder-classification">
                      {menteeMaiChiClassificationLine(mentee)}
                    </span>
                  ) : (
                    <>
                      <span
                        className={`mentee-folder-meta${
                          menteeApplyDirectionSubtitle(mentee) ? ' mentee-folder-direction' : ''
                        }`}
                      >
                        {menteeApplyDirectionSubtitle(mentee) || 'Chưa điền phương hướng'}
                      </span>
                      {(mentee.apply_degree_level_label || mentee.apply_degree_level) && (
                        <span className="mentee-folder-degree">
                          {mentee.apply_degree_level_label ||
                            applyDegreeLevelLabel(mentee.apply_degree_level)}
                        </span>
                      )}
                    </>
                  )}
                </button>
              );
              })
              )}
            </div>
          </aside>

          <div className="mentee-detail-panel">
            {showMobileDetail && (
              <button
                type="button"
                className="btn btn-outline btn-sm mentee-mobile-back"
                onClick={() => setSelectedId('')}
              >
                ← Danh sách mentee
              </button>
            )}
            {loadingDetail || !selectedMentee ? (
              <p className="loader">Đang tải hồ sơ mentee...</p>
            ) : (
              <>
                <div className="mentee-detail-head">
                  <div>
                    <h3 className="mentee-detail-title">
                      {menteeDisplayName(selectedMentee)}
                    </h3>
                    <p
                        className={`muted mentee-detail-subtitle${
                        showThanhHaFolderMeta(selectedMentee) ||
                        showMaiChiFolderMeta(selectedMentee) ||
                        menteeApplyDirectionSubtitle(selectedMentee)
                          ? ' mentee-detail-direction'
                          : ''
                      }`}
                    >
                      {showThanhHaFolderMeta(selectedMentee)
                        ? menteeClassificationSummaryLine(selectedMentee)
                        : showMaiChiFolderMeta(selectedMentee)
                          ? menteeMaiChiClassificationLine(selectedMentee)
                          : menteeApplyDirectionSubtitle(selectedMentee) || 'Chưa điền phương hướng'}
                    </p>
                    <p className="muted mentee-detail-email">{selectedMentee.email}</p>
                  </div>
                  {canPinMenteeUnread && (
                    <button
                      type="button"
                      className="btn btn-outline btn-sm"
                      onClick={handlePinMenteeUnread}
                    >
                      Đánh dấu chưa xem
                    </button>
                  )}
                </div>

                {renderCollapsibleSection(
                  'info',
                  'Thông tin mentee',
                  menteeInfoSectionMeta(selectedMentee),
                  (
                    <>
                      <div className="mentee-info-actions">
                        {(isLevel1 || isSuperAdmin) && (
                          <button
                            type="button"
                            className="btn btn-outline btn-sm mentee-delete-btn"
                            disabled={deletingMentee}
                            onClick={handleDeleteMentee}
                          >
                            {deletingMentee ? 'Đang xóa...' : 'Xóa mentee'}
                          </button>
                        )}
                      </div>
                      {(selectedMentee.missing_profile_fields?.length > 0 ||
                        selectedMentee.profile_info_reminder) && (
                        <div className="mentee-profile-reminder-block">
                          {selectedMentee.missing_profile_fields?.length > 0 && (
                            <>
                              <p className="muted">
                                Thiếu thông tin:{' '}
                                {selectedMentee.missing_profile_fields
                                  .map((field) => field.label)
                                  .join(', ')}
                              </p>
                              <button
                                type="button"
                                className="btn btn-outline btn-sm"
                                disabled={profileReminderSending}
                                onClick={handleSendProfileInfoReminder}
                              >
                                {profileReminderSending
                                  ? 'Đang gửi...'
                                  : 'Nhắc bổ sung thông tin'}
                              </button>
                            </>
                          )}
                          {selectedMentee.profile_info_reminder?.sent_at && (
                            <p className="muted">
                              Đã gửi nhắc nhở
                              {selectedMentee.profile_info_reminder.unread
                                ? ' (mentee chưa xem)'
                                : ''}
                            </p>
                          )}
                        </div>
                      )}
                      <div className="mentee-info-grid">
                        <div>
                          <span className="info-label">Họ tên</span>
                          <strong>{selectedMentee.full_name || '—'}</strong>
                        </div>
                        <div>
                          <span className="info-label">Email</span>
                          <strong>{selectedMentee.email || '—'}</strong>
                        </div>
                        <div>
                          <span className="info-label">Số Zalo</span>
                          <strong>{selectedMentee.zalo_phone || '—'}</strong>
                        </div>
                        <div>
                          <span className="info-label">Mật khẩu đăng nhập</span>
                          <strong>{selectedMentee.account_password || '—'}</strong>
                        </div>
                        <div>
                          <span className="info-label">App học bổng</span>
                          <strong>{selectedMentee.scholarship_system_label || '—'}</strong>
                        </div>
                        <div>
                          <span className="info-label">Mentor</span>
                          <strong>
                            {selectedMentee.mentor
                              ? formatLevel1MentorLine(selectedMentee.mentor)
                              : '—'}
                          </strong>
                        </div>
                        <div>
                          <span className="info-label">Email phụ huynh</span>
                          <strong>{selectedMentee.parent_email || '—'}</strong>
                        </div>
                        <div>
                          <span className="info-label">Email clone</span>
                          <strong>{selectedMentee.apply_clone_email || '—'}</strong>
                        </div>
                        <div>
                          <span className="info-label">Pass clone</span>
                          <strong>{selectedMentee.apply_clone_password || '—'}</strong>
                        </div>
                      </div>
                      <div className="mentee-classification-block">
                        <div className="mentee-classification-head">
                          <h4>Phân loại mentee</h4>
                          <p className="muted">
                            {showThanhHaClassification
                              ? 'Chọn khối ngành, phương hướng NC, hệ apply, hệ tiếng và kì tiếng — đồng bộ với bảng Tổng quan ở Trang chủ.'
                              : showMaiChiClassification
                                ? 'Chọn ngành, hệ apply và hệ tiếng — hiển thị dạng Ngành - Hệ - Tiếng ở danh sách mentee.'
                                : 'Chọn hệ apply cho mentee.'}
                          </p>
                        </div>
                        {canEditClassification ? (
                          <MenteeClassificationFields
                            mentee={selectedMentee}
                            savingField={classificationSaving}
                            onFieldChange={handleClassificationChange}
                            showDirection={showThanhHaClassification || showMaiChiClassification}
                            showResearchDirection={showThanhHaClassification}
                            showLanguage={showThanhHaClassification || showMaiChiClassification}
                            showTerm={showThanhHaClassification}
                            showDegree
                          />
                        ) : (
                          <div className="mentee-info-grid">
                            {(showThanhHaClassification || showMaiChiClassification) && (
                              <div>
                                <span className="info-label">Ngành / Hướng apply</span>
                                <strong>{menteeApplyDirectionSubtitle(selectedMentee) || '—'}</strong>
                              </div>
                            )}
                            {showThanhHaClassification && (
                              <div>
                                <span className="info-label">Phương hướng NC</span>
                                <strong>
                                  {researchDirectionDisplayText(selectedMentee) || '—'}
                                </strong>
                              </div>
                            )}
                            <div>
                              <span className="info-label">Hệ apply</span>
                              <strong>
                                {applyDegreeLevelLabel(selectedMentee.apply_degree_level) ||
                                  selectedMentee.apply_degree_level_label ||
                                  '—'}
                              </strong>
                            </div>
                            {(showThanhHaClassification || showMaiChiClassification) && (
                              <div>
                                <span className="info-label">Hệ tiếng</span>
                                <strong>{scholarshipLanguageShortLabel(selectedMentee) || '—'}</strong>
                              </div>
                            )}
                            {showThanhHaClassification && (
                              <div>
                                <span className="info-label">Kì tiếng 3/2027</span>
                                <strong>
                                  {selectedMentee.term3_2027_language_semester_label ||
                                    term3LanguageSemesterLabel(
                                      selectedMentee.term3_2027_language_semester,
                                    )}
                                </strong>
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                      {renderLanguageScoresPanel(getLanguageDocument(selectedMentee))}
                    </>
                  ),
                )}

                {renderCollapsibleSection(
                  'device',
                  'Thiết bị',
                  deviceCollapsedMeta || '—',
                  (
                    <>
                      {renderL2ActivityBanner('device')}
                      {renderLoginTrackingPanel(
                        selectedMentee,
                        selectedMentee.id,
                        'Đăng nhập mentee',
                      )}
                      {selectedMentee.parent_account &&
                        renderLoginTrackingPanel(
                          selectedMentee.parent_account,
                          selectedMentee.parent_account.id,
                          'Đăng nhập phụ huynh',
                        )}
                    </>
                  ),
                )}

                {renderCollapsibleSection(
                  'documents',
                  (
                    <>
                      Tài liệu Apply
                      <span className="apply-doc-progress" title="Tài liệu mentee đã nộp">
                        {uploadedDocumentsCount} đã nộp
                      </span>
                      <span
                        className="apply-doc-approved-badge"
                        title="Tài liệu chính xác (mentor đã duyệt)"
                      >
                        {approvedDocumentsCount} chính xác
                      </span>
                    </>
                  ),
                  `${uploadedDocumentsCount} đã nộp · ${approvedDocumentsCount} chính xác · ${processedDocumentsCount}/${totalDocumentsCount} đã xử lí · mục ${displayDocuments.length} Supporting Materials${
                    selectedMentee.unread_documents_count > 0
                      ? ` · ${selectedMentee.unread_documents_count} cần xử lí`
                      : ''
                  }${
                    selectedMentee.preferred_schools_note_unread ? ' · Trường ưa thích mới' : ''
                  }`,
                  (
                    <>
                  {renderL2ActivityBanner('documents')}
                  {allDocuments.length === 0 ? (
                    <p className="muted">Chưa có dữ liệu giấy tờ.</p>
                  ) : (
                    <>
                      <p className="muted apply-doc-list-hint">
                        {uploadedDocumentsCount} tài liệu đã nộp · {approvedDocumentsCount} tài
                        liệu chính xác (mentor duyệt) · cuối danh sách là mục {displayDocuments.length}{' '}
                        (Supporting Materials, chỉ mentor).
                      </p>
                      <div
                        className={`apply-preferred-schools-note${
                          selectedMentee.preferred_schools_note_unread
                            ? ' apply-preferred-schools-note-unread'
                            : ''
                        }`}
                      >
                        <strong>
                          Trường ưa thích (mentee ghi chú)
                          {selectedMentee.preferred_schools_note_unread && (
                            <span className="notify-dot" title="Ghi chú mới" />
                          )}
                        </strong>
                        <p className={selectedMentee.preferred_schools_note?.trim() ? '' : 'muted'}>
                          {selectedMentee.preferred_schools_note?.trim() ||
                            'Mentee chưa ghi chú trường ưa thích.'}
                        </p>
                      </div>

                      <div className="apply-download-toolbar">
                        {downloadableDocuments.length > 0 && (
                          <label className="apply-download-select-all">
                            <input
                              type="checkbox"
                              checked={allDownloadSelected}
                              onChange={toggleSelectAllDownload}
                            />
                            Chọn tất cả (tải)
                          </label>
                        )}
                        {missingDocuments.length > 0 && (
                          <>
                            <label className="apply-download-select-all apply-remind-select-all">
                              <input
                                type="checkbox"
                                checked={allRemindSelected}
                                onChange={toggleSelectAllRemind}
                              />
                              Chọn tất cả (nhắc nhở)
                            </label>
                            <button
                              type="button"
                              className="btn btn-outline btn-sm"
                              disabled={reminderSending || selectedRemindIds.length === 0}
                              onClick={handleSendMissingReminder}
                            >
                              {reminderSending
                                ? 'Đang gửi...'
                                : `Gửi nhắc nhở (${selectedRemindIds.length || 0})`}
                            </button>
                          </>
                        )}
                        {approvableDocuments.length > 0 && (
                          <>
                            <label className="apply-download-select-all apply-approve-select-all">
                              <input
                                type="checkbox"
                                checked={allApproveSelected}
                                onChange={toggleSelectAllApprove}
                              />
                              Chọn tất cả (duyệt)
                            </label>
                            <button
                              type="button"
                              className="btn btn-primary btn-sm"
                              disabled={bulkApproving || selectedApproveIds.length === 0}
                              onClick={handleBulkApprove}
                            >
                              {bulkApproving
                                ? 'Đang duyệt...'
                                : `Duyệt hàng loạt (${selectedApproveIds.length || 0})`}
                            </button>
                          </>
                        )}
                      </div>

                      {downloadableDocuments.length > 0 && (
                        <div className="apply-global-download-panel">
                          <p className="muted apply-global-download-hint">
                            Yêu cầu tổng — áp dụng cho cả {menteeApplyDocuments.length} mục hồ sơ bên
                            dưới. Chọn mục cần tải rồi bấm tải đồng loạt (1 file ZIP nếu nhiều mục).
                          </p>
                          {renderDocDownloadControls('global-bulk', {
                            inline: true,
                            hideDownloadButton: true,
                          })}
                          <button
                            type="button"
                            className="btn btn-primary btn-sm"
                            disabled={bulkDownloading || selectedDownloadIds.length === 0}
                            onClick={handleBulkDownload}
                          >
                            {bulkDownloading
                              ? 'Đang tải...'
                              : `Tải đồng loạt (${selectedDownloadIds.length || 0})`}
                          </button>
                        </div>
                      )}

                      <div className="apply-doc-list">
                      {displayDocuments.map((doc, index) => {
                        if (isMentorOnlyDoc(doc)) {
                          const bundleCount = doc.bundle_file_count ?? 0;
                          const displayIndex = index + 1;
                          return (
                            <div key={doc.doc_id} className="apply-doc-mentor-section">
                              <div className="apply-doc-mentor-divider">
                                Mục {displayIndex} · Supporting Materials — chỉ mentor (mentee không thấy)
                              </div>
                            <div
                              className={`apply-doc-item${
                                bundleCount === 0 ? ' apply-doc-item-missing' : ''
                              }`}
                            >
                              <span className="apply-doc-check-spacer" aria-hidden />
                              <div className="apply-doc-main">
                                <span className="apply-doc-label">
                                  {displayIndex}. {doc.download_label || doc.label}
                                </span>
                                {doc.label && doc.download_label && (
                                  <span className="apply-doc-subtitle">{doc.label}</span>
                                )}
                                <span className="muted apply-doc-meta">
                                  Gộp CV + Bài báo + Tài liệu khác ({bundleCount} file) · chỉ
                                  mentor · dùng định dạng/dung lượng của 3 mục tương ứng ở trên
                                </span>
                              </div>
                              <div className="apply-doc-actions">
                                <button
                                  type="button"
                                  className="btn btn-outline btn-sm"
                                  disabled={bundleCount === 0 || bulkDownloading}
                                  onClick={handleDownloadSupportingBundle}
                                >
                                  Tải gói
                                </button>
                              </div>
                            </div>
                            </div>
                          );
                        }

                        return (
                        <div
                          key={doc.doc_id}
                          className={`apply-doc-item${doc.uploaded ? '' : ' apply-doc-item-missing'}${
                            doc.mentor_request_active ? ' apply-doc-item-requested' : ''
                          }${doc.mentor_unread ? ' apply-doc-item-unread' : ''}`}
                        >
                          {!doc.uploaded ? (
                            <label
                              className="apply-doc-check apply-doc-remind-check"
                              title="Chọn để nhắc nhở mentee"
                            >
                              <input
                                type="checkbox"
                                checked={selectedRemindIds.includes(doc.doc_id)}
                                onChange={() => toggleRemindSelection(doc.doc_id)}
                              />
                            </label>
                          ) : (
                            <div className="apply-doc-checks">
                              {doc.has_file ? (
                                <label className="apply-doc-check" title="Chọn để tải nhiều mục">
                                  <input
                                    type="checkbox"
                                    checked={selectedDownloadIds.includes(doc.doc_id)}
                                    onChange={() => toggleDownloadSelection(doc.doc_id)}
                                  />
                                </label>
                              ) : null}
                              {doc.mentor_status !== 'đã duyệt' ? (
                                <label
                                  className="apply-doc-check apply-doc-approve-check"
                                  title="Chọn để duyệt hàng loạt"
                                >
                                  <input
                                    type="checkbox"
                                    checked={selectedApproveIds.includes(doc.doc_id)}
                                    onChange={() => toggleApproveSelection(doc.doc_id)}
                                  />
                                </label>
                              ) : !doc.has_file ? (
                                <span className="apply-doc-check-spacer" aria-hidden />
                              ) : null}
                            </div>
                          )}
                          <div className="apply-doc-main">
                            <span
                              className={`apply-doc-label${
                                doc.uploaded ? '' : ' apply-doc-label-missing'
                              }`}
                            >
                              {doc.mentor_status === 'đã duyệt' && doc.uploaded && (
                                <span
                                  className="apply-doc-approved-tick"
                                  title="Đã duyệt"
                                  aria-label="Đã duyệt"
                                >
                                  ✓
                                </span>
                              )}
                              {doc.download_label || doc.label}
                              {doc.mentor_unread && (
                                <span className="notify-dot" title="Cần xử lí" />
                              )}
                            </span>
                            {doc.download_label && doc.label && (
                              <span className="apply-doc-subtitle">{doc.label}</span>
                            )}
                            {doc.uploaded ? (
                              <>
                                <span className="muted apply-doc-meta">
                                  {doc.uploaded_by === 'mentor'
                                    ? `Mentor tải lên${doc.uploaded_by_name ? ` · ${doc.uploaded_by_name}` : ''}`
                                    : doc.declaration_has_online
                                      ? 'Google Docs · mentor theo dõi online'
                                      : doc.declaration_has_local
                                        ? 'File docx · chưa có link online'
                                        : doc.original_name || doc.declaration_url
                                          ? 'Đã nộp'
                                          : 'Đã cập nhật'}
                                  {doc.uploaded_at ? ` · ${formatDateTime(doc.uploaded_at)}` : ''}
                                </span>
                                {doc.mentor_status && (
                                  <span className={`apply-doc-status status-${doc.mentor_status === 'đã duyệt' ? 'approved' : doc.mentor_status === 'cần chỉnh sửa' ? 'revision' : 'waiting'}`}>
                                    {MENTOR_STATUS_LABELS[doc.mentor_status] || doc.mentor_status}
                                  </span>
                                )}
                                {doc.mentor_note && (
                                  <span className="apply-doc-note">Nhận xét: {doc.mentor_note}</span>
                                )}
                                {doc.mentor_viewed_at && !doc.mentor_processed && (
                                  <span className="muted apply-doc-meta">
                                    Đã xem · chưa xử lí
                                    {doc.scheduled_process_at
                                      ? ` · hẹn ${formatDateTime(doc.scheduled_process_at)}`
                                      : ''}
                                  </span>
                                )}
                                {doc.mentor_processed_at && (
                                  <span className="muted apply-doc-meta">
                                    Đã xử lí · {formatDateTime(doc.mentor_processed_at)}
                                  </span>
                                )}
                              </>
                            ) : (
                              <span className="apply-doc-missing-note">
                                {MENTOR_UPLOADABLE_DOC_IDS.has(doc.doc_id)
                                  ? 'Mentee chưa làm · Mentor có thể tải lên'
                                  : 'Mentee chưa làm'}
                              </span>
                            )}
                            {doc.mentor_request_active && (
                              <div className="apply-doc-request-tags">
                                {doc.mentor_handles && (
                                  <span className="apply-doc-request-tag">Mentor làm</span>
                                )}
                                {doc.needs_mentor_edit && (
                                  <span className="apply-doc-request-tag apply-doc-request-tag-edit">
                                    Gói cơ bản_Cần mentor sửa
                                  </span>
                                )}
                              </div>
                            )}
                            {renderDocDownloadControls(doc.doc_id, { hideDownloadButton: true })}
                            {doc.uploaded && !doc.mentor_processed && docScheduleId === doc.doc_id && (
                              <div className="apply-doc-schedule-panel">
                                <label className="muted">
                                  Hẹn ngày xử lí
                                  <input
                                    type="datetime-local"
                                    value={docScheduleDrafts[doc.doc_id] || ''}
                                    onChange={(e) =>
                                      setDocScheduleDrafts((prev) => ({
                                        ...prev,
                                        [doc.doc_id]: e.target.value,
                                      }))
                                    }
                                  />
                                </label>
                                <button
                                  type="button"
                                  className="btn btn-outline btn-sm"
                                  disabled={docActionSavingId === doc.doc_id}
                                  onClick={() => handleScheduleDocument(doc.doc_id)}
                                >
                                  Lưu hẹn
                                </button>
                                <button
                                  type="button"
                                  className="btn btn-outline btn-sm"
                                  onClick={() => setDocScheduleId('')}
                                >
                                  Hủy
                                </button>
                              </div>
                            )}
                          </div>
                          <div className="apply-doc-actions">
                            {MENTOR_UPLOADABLE_DOC_IDS.has(doc.doc_id) && (
                              <label
                                className={`btn btn-primary btn-sm${
                                  mentorUploadingDocId === doc.doc_id ? ' btn-disabled' : ''
                                }`}
                                title="Mentor tải lên giúp mentee"
                              >
                                {mentorUploadingDocId === doc.doc_id ? 'Đang tải...' : 'Mentor tải lên'}
                                <input
                                  type="file"
                                  accept={MENTOR_UPLOAD_ACCEPT}
                                  hidden
                                  disabled={mentorUploadingDocId === doc.doc_id}
                                  onChange={(e) => {
                                    const file = e.target.files?.[0];
                                    e.target.value = '';
                                    if (file) handleMentorDocumentUpload(doc.doc_id, file);
                                  }}
                                />
                              </label>
                            )}
                            <button
                              type="button"
                              className="btn btn-outline btn-sm"
                              disabled={!doc.uploaded || viewingDocId === doc.doc_id}
                              onClick={() => handleViewDocument(doc)}
                            >
                              Xem
                            </button>
                            <button
                              type="button"
                              className="btn btn-outline btn-sm"
                              disabled={!doc.has_file || bulkDownloading}
                              onClick={() => handleDownloadDocument(doc)}
                            >
                              Tải
                            </button>
                            <button
                              type="button"
                              className="btn btn-outline btn-sm"
                              onClick={() => openCommentModal(doc)}
                            >
                              Nhận xét
                            </button>
                            {doc.uploaded && !doc.mentor_processed && (
                              <>
                                <button
                                  type="button"
                                  className="btn btn-outline btn-sm"
                                  disabled={docActionSavingId === doc.doc_id}
                                  onClick={() => {
                                    setDocScheduleId(doc.doc_id);
                                    setDocScheduleDrafts((prev) => ({
                                      ...prev,
                                      [doc.doc_id]: prev[doc.doc_id] || '',
                                    }));
                                  }}
                                >
                                  Hẹn ngày xử lí
                                </button>
                                <button
                                  type="button"
                                  className="btn btn-primary btn-sm"
                                  disabled={docActionSavingId === doc.doc_id}
                                  onClick={() => handleProcessDocument(doc)}
                                >
                                  Đã xử lí
                                </button>
                              </>
                            )}
                          </div>
                        </div>
                        );
                      })}
                      </div>
                    </>
                  )}
                    </>
                  ),
                )}

                {renderCollapsibleSection(
                  'applyProgress',
                  'Tiến độ apply',
                  selectedMentee.apply_progress_pending_count > 0
                    ? `${selectedMentee.apply_progress_pending_count} chỉnh sửa chờ duyệt`
                    : selectedMentee.apply_progress_l2_unread && !isLevel1
                      ? 'Mentor cấp 1 cập nhật tiến độ'
                    : `${selectedMentee.apply_progress?.row_count || selectedMentee.apply_progress?.rows?.length || 8} nguyện vọng`,
                  (
                    <>
                      {renderL2ActivityBanner('applyProgress')}
                      <ApplyProgressPanel
                      menteeId={selectedMentee.id}
                      admin={admin}
                      initialProgress={selectedMentee.apply_progress}
                      onUpdated={(payload) => {
                        setSelectedMentee((prev) =>
                          prev
                            ? {
                                ...prev,
                                apply_progress: payload,
                                apply_progress_pending_count: payload.pending_count || 0,
                                apply_progress_l2_unread: payload.l2_unread || false,
                              }
                            : prev,
                        );
                        setMentees((list) =>
                          list.map((item) =>
                            item.id === selectedMentee.id
                              ? {
                                  ...item,
                                  apply_progress: payload,
                                  apply_progress_pending_count: payload.pending_count || 0,
                                  apply_progress_l2_unread: payload.l2_unread || false,
                                }
                              : item,
                          ),
                        );
                      }}
                    />
                    </>
                  ),
                )}

                {isThanhHa &&
                  renderCollapsibleSection(
                    'hdnkNckh',
                    'Keep track HDNK + NCKH',
                    selectedMentee.hdnk_nckh_l1_unread
                      ? 'Mentee vừa cập nhật'
                      : selectedMentee.hdnk_nckh_reminder_unread
                        ? 'Đến hạn nhắc cập nhật'
                        : `${selectedMentee.hdnk_nckh?.entries?.length || 0} mục`,
                    (
                      <HdnkNckhPanel
                        menteeId={selectedMentee.id}
                        admin={admin}
                        initialData={selectedMentee.hdnk_nckh}
                        onUpdated={(payload) => {
                          setSelectedMentee((prev) =>
                            prev
                              ? {
                                  ...prev,
                                  hdnk_nckh: payload,
                                  hdnk_nckh_l1_unread: payload.l1_unread || false,
                                  hdnk_nckh_reminder_unread: payload.reminder_unread || false,
                                }
                              : prev,
                          );
                          setMentees((prev) =>
                            prev.map((item) =>
                              item.id === selectedMentee.id
                                ? {
                                    ...item,
                                    hdnk_nckh_l1_unread: payload.l1_unread || false,
                                    hdnk_nckh_reminder_unread: payload.reminder_unread || false,
                                  }
                                : item,
                            ),
                          );
                        }}
                      />
                    ),
                  )}

                {renderCollapsibleSection(
                  'messages',
                  'Tin từ mentee',
                  menteeFeedback.length > 0
                    ? `${menteeFeedback.length} tin${
                        menteeFeedbackUnread > 0 ? ` · ${menteeFeedbackUnread} chưa đọc` : ''
                      }`
                    : 'Chưa có tin',
                  (
                    <>
                      {renderL2ActivityBanner('messages')}
                      {renderMenteeFeedbackPanel()}
                    </>
                  ),
                )}
              </>
            )}
          </div>
        </div>
      )}

      {viewerDoc && viewerUrl && (
        <div className="modal-backdrop" onClick={closeDocumentViewer}>
          <div
            className="modal-card doc-viewer-modal"
            role="dialog"
            aria-modal="true"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="doc-viewer-head">
              <div>
                <h3>{viewerDoc.download_label || viewerDoc.label}</h3>
                {viewerDoc.label && viewerDoc.download_label && viewerDoc.label !== viewerDoc.download_label && (
                  <p className="apply-doc-subtitle">{viewerDoc.label}</p>
                )}
              </div>
              <button type="button" className="btn btn-outline btn-sm" onClick={closeDocumentViewer}>
                Đóng
              </button>
            </div>
            <div className="doc-viewer-body">
              {watermarkText && (
                <div className="doc-viewer-watermark" aria-hidden="true">
                  {Array.from({ length: 6 }).map((_, index) => (
                    <span key={index}>{watermarkText}</span>
                  ))}
                </div>
              )}
              {viewerMime.startsWith('image/') ? (
                <img src={viewerUrl} alt={viewerDoc.label || viewerDoc.download_label} className="doc-viewer-image" />
              ) : (
                <iframe
                  title={viewerDoc.download_label || viewerDoc.label}
                  src={viewerUrl}
                  className="doc-viewer-frame"
                />
              )}
            </div>
          </div>
        </div>
      )}

      {commentTarget && (
        <div className="modal-backdrop" onClick={() => setCommentTarget(null)}>
          <div
            className="modal-card"
            role="dialog"
            aria-modal="true"
            onClick={(event) => event.stopPropagation()}
          >
            <h3>Nhận xét — {commentTarget.label}</h3>
            <p className="muted modal-note">
              Nhận xét sẽ hiển thị ở cột &quot;Đợi mentor phản hồi&quot; của mentee và gửi email thông báo.
            </p>
            <label className="comment-field">
              Trạng thái
              <select
                value={commentStatus}
                onChange={(e) => setCommentStatus(e.target.value)}
              >
                <option value="cần chỉnh sửa">Cần chỉnh sửa (gửi nhận xét)</option>
                <option value="đã duyệt">Đã duyệt ✓</option>
              </select>
            </label>
            <label className="comment-field">
              Nhận xét
              <textarea
                rows={4}
                value={commentNote}
                onChange={(e) => setCommentNote(e.target.value)}
                placeholder="Ghi nhận xét cho mentee..."
              />
            </label>
            <div className="modal-actions">
              <button type="button" className="btn btn-outline" onClick={() => setCommentTarget(null)}>
                Hủy
              </button>
              <button
                type="button"
                className="btn btn-primary"
                disabled={commentSubmitting}
                onClick={handleSubmitComment}
              >
                {commentSubmitting ? 'Đang gửi...' : 'Gửi'}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
