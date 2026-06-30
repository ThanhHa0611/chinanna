import { useEffect, useMemo, useState } from 'react';
import { useLocation } from 'react-router-dom';
import DocHintButton from '../components/DocHintButton';
import DeviceModeSwitcher from '../components/DeviceModeSwitcher';
import ProfileScrollTop from '../components/ProfileScrollTop';
import { useAuth } from '../context/AuthContext';
import { useDeviceMode } from '../context/DeviceModeContext';
import {
  APPLY_DOCUMENTS,
  APPLY_GENERAL_NOTES,
  MENTOR_APPLY_SETUP,
  MENTOR_FORWARD_GUIDE,
  getMentorApplyNote,
} from '../data/applyDocuments';
import {
  APPLY_DEGREE_LEVELS,
  TERM3_2027_LANGUAGE_OPTIONS,
} from '../data/applyDegree';
import { api } from '../services/api';
import ApplyProgressSection from '../components/ApplyProgressSection';
import HdnkNckhSection from '../components/HdnkNckhSection';
import ProfileActivitiesSection from '../components/ProfileActivitiesSection';
import ParentProfile from './ParentProfile';

const MENU_ITEMS = [
  { id: 'account', label: 'Tài khoản và mật khẩu' },
  { id: 'documents', label: 'Giấy tờ apply' },
  { id: 'apply-progress', label: 'Tiến độ apply' },
  { id: 'feedback', label: 'Phản hồi' },
];

const MENTEE_FEEDBACK_SEEN_KEY = 'mentee-feedback-seen-v1';
const MENTEE_MISSING_REMINDER_COLLAPSED_KEY = 'mentee-missing-reminder-collapsed-v1';

function missingReminderSignature(reminder) {
  if (!reminder) return '';
  return reminder.sent_at || 'reminder';
}

function readCollapsedMissingReminder(signature) {
  if (!signature) return false;
  try {
    const raw = localStorage.getItem(MENTEE_MISSING_REMINDER_COLLAPSED_KEY);
    return raw ? JSON.parse(raw) === signature : false;
  } catch {
    return false;
  }
}

function saveCollapsedMissingReminder(signature) {
  try {
    localStorage.setItem(MENTEE_MISSING_REMINDER_COLLAPSED_KEY, JSON.stringify(signature));
  } catch {
    // ignore storage errors
  }
}

function readSeenFeedbackThreads() {
  try {
    const raw = localStorage.getItem(MENTEE_FEEDBACK_SEEN_KEY);
    return raw ? JSON.parse(raw) : {};
  } catch {
    return {};
  }
}

function saveSeenFeedbackThread(threadId, signature) {
  try {
    const all = readSeenFeedbackThreads();
    all[threadId] = signature;
    localStorage.setItem(MENTEE_FEEDBACK_SEEN_KEY, JSON.stringify(all));
  } catch {
    // ignore storage errors
  }
}

function feedbackThreadSignature(item) {
  const messages = item.messages || [];
  const last = messages[messages.length - 1];
  return `${messages.length}|${last?.created_at || item.updated_at}|${item.mentee_unread ? 'u' : 'r'}`;
}

function feedbackDisplayStatus(item) {
  if (item.status === 'đã xử lí') return item.status;
  return item.mentee_status_label || item.status;
}

function feedbackStatusClassName(item) {
  if (item.status === 'đã xử lí') return ' feedback-status-done';
  if (item.mentee_status_label === 'Mentor đã nhận được tin nhắn của bạnn rùii') {
    return ' feedback-status-received';
  }
  return '';
}

function getLastMessagePreview(item) {
  const messages = item.messages || [];
  const last = messages[messages.length - 1];
  const content = last?.content || item.content || '';
  if (content.length <= 96) return content;
  return `${content.slice(0, 96)}…`;
}

const MENTORS = ['', 'Thanh Hà', 'Mai Chi'];

const ACCEPTED_FILE_TYPES = '.jpg,.jpeg,.png,.pdf,.doc,.docx';
const ACCEPTED_FILE_HINT = 'JPG, PNG, PDF, DOC, DOCX';
const MENTOR_UPLOAD_DOC_IDS = new Set(['study-plan', 'cv']);

function documentNotificationCount(data) {
  return (
    (data?.feedback_unread_count || 0) +
    (data?.missing_reminder_unread ? 1 : 0) +
    (data?.mentor_upload_unread_count || 0)
  );
}

const MENTOR_STATUS_LABELS = {
  'chờ phản hồi': 'Chờ phản hồi',
  'đã duyệt': 'Đã duyệt',
  'cần chỉnh sửa': 'Cần chỉnh sửa',
};

const MENTOR_STATUS_CLASS = {
  'chờ phản hồi': 'waiting',
  'đã duyệt': 'approved',
  'cần chỉnh sửa': 'revision',
};

function isDocMentorApproved(doc, record, personalDeclaration) {
  const submitted =
    doc.id === 'personal-declaration'
      ? Boolean(
          personalDeclaration?.exists ||
            personalDeclaration?.has_online_link ||
            personalDeclaration?.has_local_file ||
            personalDeclaration?.url,
        )
      : Boolean(record?.uploaded);
  if (!submitted) return false;
  return (record?.mentor_status || 'chờ phản hồi') === 'đã duyệt';
}

function personalDeclarationHasForm(personalDeclaration) {
  return Boolean(
    personalDeclaration?.exists ||
      personalDeclaration?.has_online_link ||
      personalDeclaration?.has_local_file ||
      personalDeclaration?.url,
  );
}

const SCHOLARSHIP_OPTIONS = [
  { value: '', label: 'Chọn hệ học bổng' },
  { value: 'english', label: 'Học bổng hệ tiếng Anh' },
  { value: 'chinese', label: 'Học bổng hệ tiếng Trung' },
];

const ENGLISH_SKILL_FIELDS = [
  { key: 'overall', label: 'Overall' },
  { key: 'listening', label: 'Nghe' },
  { key: 'speaking', label: 'Nói' },
  { key: 'reading', label: 'Đọc' },
  { key: 'writing', label: 'Viết' },
];

const CHINESE_OVERALL_FIELDS = [
  { key: 'overall', label: 'Overall' },
  { key: 'listening', label: 'Nghe' },
  { key: 'reading', label: 'Đọc' },
  { key: 'writing', label: 'Viết' },
];

const CHINESE_HSKK_FIELDS = [{ key: 'hskk', label: 'HSKK' }];

function getLanguageScoreGroups(langKey) {
  if (langKey === 'chinese') {
    return [
      { id: 'overall', title: 'Overall', fields: CHINESE_OVERALL_FIELDS },
      { id: 'hskk', title: 'HSKK', fields: CHINESE_HSKK_FIELDS },
    ];
  }
  return [{ id: 'overall', title: 'Overall', fields: ENGLISH_SKILL_FIELDS }];
}

function getSkillFieldsForLanguage(langKey) {
  return getLanguageScoreGroups(langKey).flatMap((group) => group.fields);
}

function emptySkillScoresFor(langKey) {
  return Object.fromEntries(getSkillFieldsForLanguage(langKey).map((field) => [field.key, '']));
}

const LANGUAGE_OPTIONS = [
  { key: 'english', label: 'Tiếng Anh' },
  { key: 'chinese', label: 'Tiếng Trung' },
];

function emptyLanguageForm() {
  return {
    languages: { english: false, chinese: false },
    certificate_name: '',
    english: emptySkillScoresFor('english'),
    chinese: emptySkillScoresFor('chinese'),
    score_updated_at: '',
    mentor_handles_update: false,
  };
}

function emptyScoreUpdateForm() {
  return {
    exam_date: '',
    english: emptySkillScoresFor('english'),
    chinese: emptySkillScoresFor('chinese'),
  };
}

function hasAnyScoreValues(scores) {
  return Object.values(scores).some((value) => String(value).trim());
}

function languageFormFromRecord(record) {
  if (!record) return emptyLanguageForm();

  const languages = record.languages?.length
    ? record.languages
    : record.language_type
      ? [record.language_type]
      : [];

  return {
    languages: {
      english: languages.includes('english'),
      chinese: languages.includes('chinese'),
    },
    certificate_name: record.certificate_name || '',
    english: { ...emptySkillScoresFor('english'), ...(record.english || {}) },
    chinese: { ...emptySkillScoresFor('chinese'), ...(record.chinese || {}) },
    score_updated_at: record.score_updated_at || '',
    mentor_handles_update: Boolean(record.mentor_handles || record.mentor_handles_update),
  };
}

function formatDateTime(value) {
  if (!value) return '';
  return new Date(value).toLocaleString('vi-VN', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export default function Profile() {
  const { user } = useAuth();
  if (user?.role === 'parent') {
    return <ParentProfile />;
  }

  return <MenteeProfile user={user} />;
}

function MenteeProfile() {
  const { user, updateUser } = useAuth();
  const { isPhone } = useDeviceMode() || {};
  const location = useLocation();
  const [activeSection, setActiveSection] = useState('account');
  const menuItems = useMemo(() => {
    const items = [...MENU_ITEMS];
    if ((user?.mentor || '').trim() === 'Thanh Hà') {
      items.push({ id: 'hdnk-nckh', label: 'Keep track HDNK + NCKH' });
    }
    items.push({ id: 'profile-activities', label: 'Hoạt động làm đẹp hồ sơ' });
    return items;
  }, [user?.mentor]);

  useEffect(() => {
    if (!isPhone) return;
    const section = location.state?.section || 'account';
    setActiveSection(section);
    window.requestAnimationFrame(() => {
      window.scrollTo({ top: 0, behavior: 'smooth' });
    });
  }, [location.pathname, location.key, location.state, isPhone]);

  useEffect(() => {
    const handleOpenSection = (event) => {
      const section = event.detail?.section || 'account';
      setActiveSection(section);
      window.requestAnimationFrame(() => {
        window.scrollTo({ top: 0, behavior: 'smooth' });
      });
    };
    window.addEventListener('profile-open-section', handleOpenSection);
    return () => window.removeEventListener('profile-open-section', handleOpenSection);
  }, []);

  const mentorLocked = Boolean((user?.mentor || '').trim());

  const [fullName, setFullName] = useState('');
  const [dateOfBirth, setDateOfBirth] = useState('');
  const [mentor, setMentor] = useState('');
  const [applyCloneEmail, setApplyCloneEmail] = useState('');
  const [applyClonePassword, setApplyClonePassword] = useState('');
  const [scholarshipSystem, setScholarshipSystem] = useState('');
  const [applyDegreeLevel, setApplyDegreeLevel] = useState('');
  const [term3LanguageSemester, setTerm3LanguageSemester] = useState('');
  const [parentEmail, setParentEmail] = useState('');
  const [zaloPhone, setZaloPhone] = useState('');
  const [feedbackUnreadCount, setFeedbackUnreadCount] = useState(0);
  const [missingReminder, setMissingReminder] = useState(null);
  const [missingReminderUnread, setMissingReminderUnread] = useState(false);
  const [missingReminderExpanded, setMissingReminderExpanded] = useState(true);
  const [profileInfoReminder, setProfileInfoReminder] = useState(null);
  const [profileInfoReminderUnread, setProfileInfoReminderUnread] = useState(false);
  const [generalFeedbackUnread, setGeneralFeedbackUnread] = useState(0);
  const [profileSaving, setProfileSaving] = useState(false);
  const [profileMessage, setProfileMessage] = useState('');
  const [profileError, setProfileError] = useState('');

  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [passwordSaving, setPasswordSaving] = useState(false);
  const [passwordMessage, setPasswordMessage] = useState('');
  const [passwordError, setPasswordError] = useState('');

  const [feedback, setFeedback] = useState('');
  const [feedbackList, setFeedbackList] = useState([]);
  const [feedbackLoading, setFeedbackLoading] = useState(false);
  const [feedbackSubmitting, setFeedbackSubmitting] = useState(false);
  const [feedbackMessage, setFeedbackMessage] = useState('');
  const [feedbackError, setFeedbackError] = useState('');
  const [feedbackLoadError, setFeedbackLoadError] = useState('');
  const [feedbackReplyDrafts, setFeedbackReplyDrafts] = useState({});
  const [feedbackReplySubmitting, setFeedbackReplySubmitting] = useState('');
  const [expandedFeedbackThreads, setExpandedFeedbackThreads] = useState({});
  const [feedbackDeletingId, setFeedbackDeletingId] = useState('');
  const [openHintId, setOpenHintId] = useState(null);
  const [personalDeclaration, setPersonalDeclaration] = useState(null);
  const [declarationLoading, setDeclarationLoading] = useState(false);
  const [declarationError, setDeclarationError] = useState('');
  const [declarationLinkDraft, setDeclarationLinkDraft] = useState('');
  const [declarationLinkSaving, setDeclarationLinkSaving] = useState(false);
  const [declarationManualCopyUrl, setDeclarationManualCopyUrl] = useState('');
  const [applyDocItems, setApplyDocItems] = useState([]);
  const [applyDocSummary, setApplyDocSummary] = useState({ uploaded_count: 0, total_count: 0 });
  const [applyDocsLoading, setApplyDocsLoading] = useState(false);
  const [applyDocsError, setApplyDocsError] = useState('');
  const [uploadingDocId, setUploadingDocId] = useState(null);
  const [uploadErrors, setUploadErrors] = useState({});
  const [languageForm, setLanguageForm] = useState(emptyLanguageForm());
  const [scoreUpdateForm, setScoreUpdateForm] = useState(emptyScoreUpdateForm());
  const [languageSaving, setLanguageSaving] = useState(false);
  const [scoreUpdateSaving, setScoreUpdateSaving] = useState(false);
  const [languageMessage, setLanguageMessage] = useState('');
  const [languageError, setLanguageError] = useState('');
  const [scoreUpdateMessage, setScoreUpdateMessage] = useState('');
  const [scoreUpdateError, setScoreUpdateError] = useState('');
  const [menteeRequestSaving, setMenteeRequestSaving] = useState('');
  const [preferredSchoolsNote, setPreferredSchoolsNote] = useState('');
  const [preferredSchoolsSaving, setPreferredSchoolsSaving] = useState(false);
  const [preferredSchoolsMessage, setPreferredSchoolsMessage] = useState('');
  const [preferredSchoolsError, setPreferredSchoolsError] = useState('');
  const [applyProgressUnread, setApplyProgressUnread] = useState(false);

  useEffect(() => {
    setFullName(user?.full_name || '');
    setDateOfBirth(user?.date_of_birth || '');
    setMentor(user?.mentor || '');
    setApplyCloneEmail(user?.apply_clone_email || '');
    setApplyClonePassword(user?.apply_clone_password || '');
    setScholarshipSystem(user?.scholarship_system || '');
    setApplyDegreeLevel(user?.apply_degree_level || '');
    setTerm3LanguageSemester(user?.term3_2027_language_semester || '');
    setParentEmail(user?.parent_email || '');
    setZaloPhone(user?.zalo_phone || '');
    setProfileInfoReminder(user?.profile_info_reminder || null);
    setProfileInfoReminderUnread(Boolean(user?.profile_info_reminder_unread));
  }, [user]);

  useEffect(() => {
    if (!missingReminder?.items?.length) {
      setMissingReminderExpanded(false);
      return;
    }
    const signature = missingReminderSignature(missingReminder);
    if (missingReminderUnread) {
      setMissingReminderExpanded(true);
      return;
    }
    setMissingReminderExpanded(!readCollapsedMissingReminder(signature));
  }, [
    missingReminder?.sent_at,
    missingReminder?.items?.length,
    missingReminderUnread,
  ]);

  const refreshMissingReminderFromApi = async () => {
    const data = await api.getApplyDocuments();
    setMissingReminder(data.missing_reminder || null);
    setMissingReminderUnread(Boolean(data.missing_reminder_unread));
    return data;
  };

  const handleMissingReminderMarkSeen = async () => {
    if (!missingReminder?.items?.length) return;

    const signature = missingReminderSignature(missingReminder);
    if (missingReminderUnread) {
      try {
        await api.ackMissingDocumentsReminder();
        setMissingReminderUnread(false);
        setMissingReminder((prev) => (prev ? { ...prev, unread: false } : prev));
        setFeedbackUnreadCount((prev) => Math.max(0, prev - 1));
      } catch {
        return;
      }
    }
    saveCollapsedMissingReminder(signature);
    setMissingReminderExpanded(false);
  };

  const handleProfileInfoReminderMarkSeen = async () => {
    if (!profileInfoReminder || !profileInfoReminderUnread) return;
    try {
      const data = await api.ackProfileInfoReminder();
      setProfileInfoReminder(data.profile_info_reminder || null);
      setProfileInfoReminderUnread(Boolean(data.profile_info_reminder_unread));
      updateUser({
        ...user,
        profile_info_reminder: data.profile_info_reminder,
        profile_info_reminder_unread: data.profile_info_reminder_unread,
      });
    } catch {
      // ignore
    }
  };

  useEffect(() => {
    api
      .getApplyDocuments()
      .then((data) => {
        setMissingReminder(data.missing_reminder || null);
        setMissingReminderUnread(Boolean(data.missing_reminder_unread));
        setFeedbackUnreadCount(documentNotificationCount(data));
      })
      .catch(() => {});
  }, [user]);

  useEffect(() => {
    api
      .getFeedback()
      .then((data) => {
        const items = data.items || data;
        const unread = data.unread_count ?? items.filter((item) => item.mentee_unread).length;
        setGeneralFeedbackUnread(unread);
      })
      .catch(() => {});
  }, [user]);

  useEffect(() => {
    api
      .getApplyProgress()
      .then((data) => {
        setApplyProgressUnread(Boolean(data.mentee_unread));
      })
      .catch(() => {});
  }, [user]);

  useEffect(() => {
    if (activeSection !== 'apply-progress' || !applyProgressUnread) return;

    api
      .ackApplyProgress()
      .then(() => setApplyProgressUnread(false))
      .catch(() => {});
  }, [activeSection, applyProgressUnread]);

  useEffect(() => {
    if (activeSection !== 'feedback') return;

    let cancelled = false;
    setFeedbackLoading(true);
    setFeedbackLoadError('');

    api
      .getFeedback()
      .then((data) => {
        if (cancelled) return;
        const items = data.items || data;
        setFeedbackList(items);
        setGeneralFeedbackUnread(data.unread_count ?? items.filter((item) => item.mentee_unread).length);
        const drafts = {};
        items.forEach((item) => {
          drafts[item.id] = '';
        });
        setFeedbackReplyDrafts(drafts);
        const seen = readSeenFeedbackThreads();
        const initialExpanded = {};
        items.forEach((item) => {
          const signature = feedbackThreadSignature(item);
          if (item.mentee_unread || seen[item.id] !== signature) {
            initialExpanded[item.id] = true;
          }
        });
        setExpandedFeedbackThreads(initialExpanded);
      })
      .catch((err) => {
        if (!cancelled) setFeedbackLoadError(err.message);
      })
      .finally(() => {
        if (!cancelled) setFeedbackLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [activeSection]);

  useEffect(() => {
    if (activeSection !== 'documents') return;

    let cancelled = false;
    setApplyDocsLoading(true);
    setApplyDocsError('');

    api
      .getApplyDocuments()
      .then((data) => {
        if (cancelled) return;
        setApplyDocItems(data.items || []);
        setApplyDocSummary({
          uploaded_count: data.uploaded_count || 0,
          total_count: data.total_count || APPLY_DOCUMENTS.length,
        });
        setMissingReminder(data.missing_reminder || null);
        setMissingReminderUnread(Boolean(data.missing_reminder_unread));
        setPreferredSchoolsNote(data.preferred_schools_note || '');
        setFeedbackUnreadCount(documentNotificationCount(data));
        const unreadItems = (data.items || []).filter((item) => item.mentee_unread_feedback);
        if (unreadItems.length) {
          Promise.all(
            unreadItems.map((item) => api.ackDocumentFeedback(item.doc_id).catch(() => null)),
          ).then(() => {
            setFeedbackUnreadCount((prev) => Math.max(0, prev - unreadItems.length));
          });
        }
        const unreadUploads = (data.items || []).filter((item) => item.mentee_unread_upload);
        if (unreadUploads.length) {
          Promise.all(
            unreadUploads.map((item) => api.ackDocumentUpload(item.doc_id).catch(() => null)),
          ).then(() => {
            setFeedbackUnreadCount((prev) => Math.max(0, prev - unreadUploads.length));
            setApplyDocItems((prev) =>
              prev.map((item) =>
                unreadUploads.some((row) => row.doc_id === item.doc_id)
                  ? { ...item, mentee_unread_upload: false }
                  : item,
              ),
            );
          });
        }
        const languageItem = (data.items || []).find((item) => item.doc_id === 'language');
        if (languageItem) {
          setLanguageForm(languageFormFromRecord(languageItem));
        }
      })
      .catch((err) => {
        if (!cancelled) setApplyDocsError(err.message);
      })
      .finally(() => {
        if (!cancelled) setApplyDocsLoading(false);
      });

    setDeclarationLoading(true);
    setDeclarationError('');

    api
      .getPersonalDeclaration()
      .then((data) => {
        if (!cancelled && data.exists) setPersonalDeclaration(data);
      })
      .catch((err) => {
        if (!cancelled) setDeclarationError(err.message);
      })
      .finally(() => {
        if (!cancelled) setDeclarationLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [activeSection]);

  const handleOpenPersonalDeclaration = async () => {
    setDeclarationLoading(true);
    setDeclarationError('');

    try {
      let doc = personalDeclaration;
      if (!personalDeclarationHasForm(doc)) {
        doc = await api.openPersonalDeclaration();
        if (doc.needs_manual_copy) {
          setDeclarationManualCopyUrl(doc.copy_url || '');
          if (doc.copy_url) {
            window.open(doc.copy_url, '_blank', 'noopener,noreferrer');
          }
          return;
        }
        setPersonalDeclaration(doc);
        setDeclarationManualCopyUrl('');
        const data = await refreshMissingReminderFromApi();
        setApplyDocItems(data.items || []);
        refreshApplyDocSummary(data.items || []);
      }

      const onlineUrl = doc.google_doc_url || (doc.url?.includes('docs.google.com') ? doc.url : '');
      if (onlineUrl) {
        window.open(onlineUrl, '_blank', 'noopener,noreferrer');
        return;
      }

      if (doc.has_local_file || doc.mode === 'local_docx' || doc.local_file_url) {
        await api.openPersonalDeclarationFile();
        return;
      }

      if (doc.url) {
        window.open(doc.url, '_blank', 'noopener,noreferrer');
      }
    } catch (err) {
      setDeclarationError(err.message);
    } finally {
      setDeclarationLoading(false);
    }
  };

  const handleOpenPersonalDeclarationLocal = async () => {
    setDeclarationLoading(true);
    setDeclarationError('');
    try {
      await api.openPersonalDeclarationFile();
    } catch (err) {
      setDeclarationError(err.message);
    } finally {
      setDeclarationLoading(false);
    }
  };

  const handleSavePersonalDeclarationLink = async () => {
    setDeclarationLinkSaving(true);
    setDeclarationError('');
    try {
      const doc = await api.registerPersonalDeclarationLink({ url: declarationLinkDraft });
      setPersonalDeclaration(doc);
      setDeclarationManualCopyUrl('');
      setDeclarationLinkDraft('');
      const data = await refreshMissingReminderFromApi();
      setApplyDocItems(data.items || []);
      refreshApplyDocSummary(data.items || []);
      const onlineUrl = doc.google_doc_url || (doc.url?.includes('docs.google.com') ? doc.url : '');
      if (onlineUrl) {
        window.open(onlineUrl, '_blank', 'noopener,noreferrer');
      }
    } catch (err) {
      setDeclarationError(err.message);
    } finally {
      setDeclarationLinkSaving(false);
    }
  };

  useEffect(() => {
    setOpenHintId(null);
  }, [activeSection]);

  const getApplyDocRecord = (docId) =>
    applyDocItems.find((item) => item.doc_id === docId) || null;

  const refreshApplyDocSummary = (items) => {
    setApplyDocSummary({
      uploaded_count: items.filter((item) => item.uploaded).length,
      total_count: items.length || APPLY_DOCUMENTS.length,
    });
  };

  const handleApplyDocUpload = async (docId, event) => {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file) return;

    setUploadingDocId(docId);
    setUploadErrors((prev) => ({ ...prev, [docId]: '' }));

    try {
      const record = await api.uploadApplyDocument(docId, file);
      setApplyDocItems((prev) => {
        const next = prev.some((item) => item.doc_id === docId)
          ? prev.map((item) => (item.doc_id === docId ? record : item))
          : [...prev, record];
        refreshApplyDocSummary(next);
        return next;
      });
      await refreshMissingReminderFromApi();
    } catch (err) {
      setUploadErrors((prev) => ({ ...prev, [docId]: err.message }));
    } finally {
      setUploadingDocId(null);
    }
  };

  const selectedLanguages = LANGUAGE_OPTIONS.filter(
    (option) => languageForm.languages[option.key],
  );

  const handleLanguageToggle = (langKey) => {
    setLanguageForm((prev) => ({
      ...prev,
      languages: {
        ...prev.languages,
        [langKey]: !prev.languages[langKey],
      },
    }));
    setLanguageMessage('');
    setLanguageError('');
  };

  const handleLanguageFieldChange = (field, value) => {
    setLanguageForm((prev) => ({ ...prev, [field]: value }));
    setLanguageMessage('');
    setLanguageError('');
  };

  const handleLanguageSkillChange = (langKey, skillKey, value) => {
    setLanguageForm((prev) => ({
      ...prev,
      [langKey]: {
        ...prev[langKey],
        [skillKey]: value,
      },
    }));
    setLanguageMessage('');
    setLanguageError('');
  };

  const handleScoreUpdateFieldChange = (field, value) => {
    setScoreUpdateForm((prev) => ({ ...prev, [field]: value }));
    setScoreUpdateMessage('');
    setScoreUpdateError('');
  };

  const handleScoreUpdateSkillChange = (langKey, skillKey, value) => {
    setScoreUpdateForm((prev) => ({
      ...prev,
      [langKey]: {
        ...prev[langKey],
        [skillKey]: value,
      },
    }));
    setScoreUpdateMessage('');
    setScoreUpdateError('');
  };

  const buildLanguagePayload = () => ({
    languages: selectedLanguages.map((option) => option.key),
    certificate_name: languageForm.certificate_name,
    english: languageForm.english,
    chinese: languageForm.chinese,
    score_updated_at: languageForm.score_updated_at,
  });

  const handleLanguageScoreSubmit = async (event) => {
    event.preventDefault();
    if (selectedLanguages.length === 0) {
      setLanguageError('Chọn ít nhất Tiếng Anh hoặc Tiếng Trung.');
      return;
    }

    setLanguageSaving(true);
    setLanguageMessage('');
    setLanguageError('');

    try {
      const record = await api.updateLanguageScores(buildLanguagePayload());
      setApplyDocItems((prev) =>
        prev.map((item) => (item.doc_id === 'language' ? record : item)),
      );
      setLanguageForm(languageFormFromRecord(record));
      setLanguageMessage('Đã lưu thông tin chứng chỉ ngoại ngữ.');
      await refreshMissingReminderFromApi();
    } catch (err) {
      setLanguageError(err.message);
    } finally {
      setLanguageSaving(false);
    }
  };

  const handleScoreUpdateSubmit = async (event) => {
    event.preventDefault();

    if (selectedLanguages.length === 0) {
      setScoreUpdateError('Lưu thông tin chứng chỉ trước khi cập nhật điểm thi mới.');
      return;
    }

    const payload = {
      exam_date: scoreUpdateForm.exam_date,
    };
    let hasNewScore = false;

    selectedLanguages.forEach((option) => {
      payload[option.key] = scoreUpdateForm[option.key];
      if (hasAnyScoreValues(scoreUpdateForm[option.key])) {
        hasNewScore = true;
      }
    });

    if (!hasNewScore) {
      setScoreUpdateError('Nhập ít nhất một điểm thi mới.');
      return;
    }

    setScoreUpdateSaving(true);
    setScoreUpdateMessage('');
    setScoreUpdateError('');

    try {
      const record = await api.submitLanguageScoreUpdate(payload);
      setApplyDocItems((prev) =>
        prev.map((item) => (item.doc_id === 'language' ? record : item)),
      );
      setLanguageForm(languageFormFromRecord(record));
      setScoreUpdateForm(emptyScoreUpdateForm());
      const appliedCount = record.applied_updates?.length || 0;
      setScoreUpdateMessage(
        appliedCount > 0
          ? 'Đã cập nhật điểm cao hơn và gửi tới mentor.'
          : 'Đã gửi cập nhật điểm tới mentor.',
      );
      await refreshMissingReminderFromApi();
    } catch (err) {
      setScoreUpdateError(err.message);
    } finally {
      setScoreUpdateSaving(false);
    }
  };

  const handleMenteeRequestToggle = async (docId, field, checked) => {
    setMenteeRequestSaving(docId);
    setApplyDocsError('');
    try {
      const updated = await api.setApplyDocumentMenteeRequest(docId, { [field]: checked });
      setApplyDocItems((prev) => prev.map((item) => (item.doc_id === docId ? updated : item)));
      if (docId === 'language') {
        setLanguageForm(languageFormFromRecord(updated));
      }
    } catch (err) {
      setApplyDocsError(err.message);
    } finally {
      setMenteeRequestSaving('');
    }
  };

  const handleSavePreferredSchoolsNote = async () => {
    setPreferredSchoolsSaving(true);
    setPreferredSchoolsMessage('');
    setPreferredSchoolsError('');
    try {
      const data = await api.updatePreferredSchoolsNote({ note: preferredSchoolsNote });
      setPreferredSchoolsNote(data.note || '');
      setPreferredSchoolsMessage('Đã lưu ghi chú.');
    } catch (err) {
      setPreferredSchoolsError(err.message);
    } finally {
      setPreferredSchoolsSaving(false);
    }
  };

  const renderMenteeRequestColumn = (doc) => {
    const record = getApplyDocRecord(doc.id);
    const saving = menteeRequestSaving === doc.id;
    return (
      <div className="profile-doc-request-cell">
        <label className="profile-doc-request-check">
          <input
            type="checkbox"
            checked={Boolean(record?.mentor_handles)}
            disabled={saving}
            onChange={(e) => handleMenteeRequestToggle(doc.id, 'mentor_handles', e.target.checked)}
          />
          Mentor làm
        </label>
        <label className="profile-doc-request-check">
          <input
            type="checkbox"
            checked={Boolean(record?.needs_mentor_edit)}
            disabled={saving}
            onChange={(e) =>
              handleMenteeRequestToggle(doc.id, 'needs_mentor_edit', e.target.checked)
            }
          />
          Gói cơ bản_Cần mentor sửa
        </label>
      </div>
    );
  };

  const renderMentorStatus = (doc, record) => {
    if (doc.id === 'personal-declaration') {
      const hasForm = personalDeclarationHasForm(personalDeclaration);
      if (!hasForm) return <span className="profile-doc-muted">—</span>;
      const status = record?.mentor_status || 'chờ phản hồi';
      return (
        <div className="profile-doc-mentor-cell">
          <span className={`profile-doc-mentor-badge profile-doc-mentor-${MENTOR_STATUS_CLASS[status] || 'waiting'}`}>
            {MENTOR_STATUS_LABELS[status] || status}
          </span>
          {record?.mentor_note && (
            <p className="profile-doc-mentor-note">{record.mentor_note}</p>
          )}
        </div>
      );
    }

    if (!record?.uploaded) {
      return <span className="profile-doc-muted">—</span>;
    }

    const status = record.mentor_status || 'chờ phản hồi';
    return (
      <div className="profile-doc-mentor-cell">
        <span className={`profile-doc-mentor-badge profile-doc-mentor-${MENTOR_STATUS_CLASS[status] || 'waiting'}`}>
          {MENTOR_STATUS_LABELS[status] || status}
        </span>
        {record.mentor_note && (
          <p className="profile-doc-mentor-note">{record.mentor_note}</p>
        )}
      </div>
    );
  };

  const renderLanguageScoreGroup = (langKey, group, values, onChange, showCurrent = false) => (
    <div key={`${langKey}-${group.id}`} className="profile-language-subgroup">
      <p className="profile-language-subgroup-title">{group.title}</p>
      <div className="profile-language-scores">
        {group.fields.map((field) => (
          <label key={`${langKey}-${group.id}-${field.key}`} className="profile-language-score-field">
            {field.label}
            {showCurrent && (
              <span className="profile-language-current">
                Hiện tại: {languageForm[langKey][field.key] || '—'}
              </span>
            )}
            <input
              type="text"
              value={values[field.key]}
              onChange={(e) => onChange(field.key, e.target.value)}
              placeholder={showCurrent ? 'Điểm thi mới' : 'Điểm'}
            />
          </label>
        ))}
      </div>
    </div>
  );

  const renderLanguageScoreForm = () => (
    <div className="profile-language-form">
      <form onSubmit={handleLanguageScoreSubmit}>
        <p className="profile-language-form-title">Điểm chứng chỉ ngoại ngữ</p>

        <div className="profile-language-top-row">
          <div className="profile-language-type">
            {LANGUAGE_OPTIONS.map((option) => (
              <label key={option.key} className="profile-language-check">
                <input
                  type="checkbox"
                  checked={languageForm.languages[option.key]}
                  onChange={() => handleLanguageToggle(option.key)}
                />
                {option.label}
              </label>
            ))}
          </div>
          <label className="profile-language-cert-name">
            Tên chứng chỉ
            <input
              type="text"
              value={languageForm.certificate_name}
              onChange={(e) => handleLanguageFieldChange('certificate_name', e.target.value)}
              placeholder="VD: IELTS, TOEFL, HSK 5..."
            />
          </label>
        </div>

        {selectedLanguages.map((option) => (
          <div key={option.key} className="profile-language-block">
            <p className="profile-language-block-title">{option.label}</p>
            {getLanguageScoreGroups(option.key).map((group) =>
              renderLanguageScoreGroup(
                option.key,
                group,
                languageForm[option.key],
                (skillKey, value) => handleLanguageSkillChange(option.key, skillKey, value),
              ),
            )}
          </div>
        ))}

        {selectedLanguages.length > 0 && (
          <>
            <label className="profile-language-date">
              Ngày cập nhật điểm
              <input
                type="date"
                value={languageForm.score_updated_at}
                onChange={(e) => handleLanguageFieldChange('score_updated_at', e.target.value)}
              />
            </label>
            {languageError && <p className="form-error">{languageError}</p>}
            {languageMessage && <p className="form-success">{languageMessage}</p>}
            <button type="submit" className="btn btn-outline btn-sm" disabled={languageSaving}>
              {languageSaving ? 'Đang lưu...' : 'Lưu thông tin chứng chỉ'}
            </button>
          </>
        )}
      </form>

      {selectedLanguages.length > 0 && (
        <form className="profile-language-update-form" onSubmit={handleScoreUpdateSubmit}>
          <p className="profile-language-form-title">Update điểm thi mới nhất</p>

          {selectedLanguages.map((option) => (
            <div key={`update-${option.key}`} className="profile-language-block">
              <p className="profile-language-block-title">{option.label}</p>
              {getLanguageScoreGroups(option.key).map((group) =>
                renderLanguageScoreGroup(
                  option.key,
                  group,
                  scoreUpdateForm[option.key],
                  (skillKey, value) => handleScoreUpdateSkillChange(option.key, skillKey, value),
                  true,
                ),
              )}
            </div>
          ))}

          <label className="profile-language-date">
            Ngày thi mới
            <input
              type="date"
              value={scoreUpdateForm.exam_date}
              onChange={(e) => handleScoreUpdateFieldChange('exam_date', e.target.value)}
            />
          </label>

          {scoreUpdateError && <p className="form-error">{scoreUpdateError}</p>}
          {scoreUpdateMessage && <p className="form-success">{scoreUpdateMessage}</p>}
          <button type="submit" className="btn btn-primary btn-sm" disabled={scoreUpdateSaving}>
            {scoreUpdateSaving ? 'Đang gửi...' : 'Save'}
          </button>
        </form>
      )}
    </div>
  );

  const renderUploadColumn = (doc) => {
    if (MENTOR_UPLOAD_DOC_IDS.has(doc.id)) {
      const record = getApplyDocRecord(doc.id);
      const uploadError = uploadErrors[doc.id];

      const ackUploadIfUnread = () => {
        if (!record?.mentee_unread_upload) return;
        api
          .ackDocumentUpload(doc.id)
          .catch(() => null)
          .then(() => {
            setApplyDocItems((prev) =>
              prev.map((item) =>
                item.doc_id === doc.id ? { ...item, mentee_unread_upload: false } : item,
              ),
            );
            setFeedbackUnreadCount((prev) => Math.max(0, prev - 1));
          });
      };

      if (!record?.uploaded) {
        return (
          <div className="profile-doc-upload-cell">
            <span className="profile-doc-muted">Mentor sẽ tải lên giúp bạn</span>
          </div>
        );
      }

      return (
        <div className="profile-doc-upload-cell">
          <div className="profile-doc-uploaded">
            {record.mentee_unread_upload && (
              <span className="profile-doc-new-from-mentor">Mới từ mentor</span>
            )}
            <span className="profile-doc-file-name" title={record.original_name}>
              {record.uploaded_by === 'mentor' && record.uploaded_by_name
                ? `${record.uploaded_by_name}: ${record.original_name}`
                : record.original_name}
            </span>
            <div className="profile-doc-upload-actions">
              <button
                type="button"
                className="btn btn-outline btn-sm profile-doc-view-btn"
                onClick={() => {
                  ackUploadIfUnread();
                  api.openApplyDocumentFile(doc.id).catch((err) => {
                    setUploadErrors((prev) => ({ ...prev, [doc.id]: err.message }));
                  });
                }}
              >
                Xem
              </button>
              <button
                type="button"
                className="btn btn-outline btn-sm"
                onClick={() => {
                  ackUploadIfUnread();
                  api.downloadApplyDocument(doc.id, record.original_name || doc.label).catch((err) => {
                    setUploadErrors((prev) => ({ ...prev, [doc.id]: err.message }));
                  });
                }}
              >
                Tải
              </button>
            </div>
          </div>
          {uploadError && <p className="form-error profile-doc-upload-error">{uploadError}</p>}
        </div>
      );
    }

    if (doc.id === 'personal-declaration') {
      const hasForm = personalDeclarationHasForm(personalDeclaration);
      const hasOnlineLink = Boolean(
        personalDeclaration?.has_online_link ||
          personalDeclaration?.google_doc_url ||
          personalDeclaration?.url?.includes('docs.google.com'),
      );
      const hasLocalFile = Boolean(
        personalDeclaration?.has_local_file || personalDeclaration?.mode === 'local_docx',
      );
      const manualCopyUrl =
        declarationManualCopyUrl || personalDeclaration?.manual_copy_url || '';
      const statusLabel = hasOnlineLink && hasLocalFile
        ? 'Đã đồng bộ Google Docs · có file docx'
        : hasOnlineLink
          ? 'Đã có form Google Docs'
          : hasLocalFile
            ? 'Đã có file docx · chưa có link online'
            : manualCopyUrl
              ? 'Đang chờ link form'
              : 'Chưa tạo form';
      return (
        <div className="profile-doc-upload-cell">
          <div className="profile-declaration-actions">
            <button
              type="button"
              className="btn btn-outline btn-sm profile-declaration-light-btn"
              disabled={declarationLoading}
              onClick={handleOpenPersonalDeclaration}
            >
              {declarationLoading
                ? 'Đang mở...'
                : hasForm
                  ? hasOnlineLink
                    ? 'Mở form online'
                    : 'Mở file kê khai'
                  : 'Tạo & mở form kê khai'}
            </button>
            {hasForm && hasOnlineLink && hasLocalFile && (
              <button
                type="button"
                className="btn btn-outline btn-sm profile-declaration-light-btn"
                disabled={declarationLoading}
                onClick={handleOpenPersonalDeclarationLocal}
              >
                Mở file docx
              </button>
            )}
          </div>
          <span className={`profile-doc-upload-status${hasForm ? ' profile-doc-upload-done' : ''}`}>
            {statusLabel}
          </span>
          {hasOnlineLink && personalDeclaration?.google_doc_url && (
            <a
              href={personalDeclaration.google_doc_url}
              target="_blank"
              rel="noopener noreferrer"
              className="profile-declaration-online-link"
            >
              Link online cho mentor
            </a>
          )}
          {(manualCopyUrl || (hasLocalFile && !hasOnlineLink)) && (
            <div className="profile-declaration-link-box">
              <p className="profile-note">
                Bấm vào đây để tạo bản sao google docx, điền xong bạn vui lòng mở quyền và dán
                link tại đây
              </p>
              {manualCopyUrl && (
                <a
                  href={manualCopyUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="btn btn-outline btn-sm profile-declaration-light-btn profile-declaration-copy-btn"
                >
                  Tạo bản sao Google Docs
                </a>
              )}
              <input
                type="url"
                className="profile-declaration-link-input"
                value={declarationLinkDraft}
                onChange={(e) => setDeclarationLinkDraft(e.target.value)}
                placeholder="https://docs.google.com/document/d/..."
              />
              <button
                type="button"
                className="btn btn-primary btn-sm"
                disabled={declarationLinkSaving || !declarationLinkDraft.trim()}
                onClick={handleSavePersonalDeclarationLink}
              >
                {declarationLinkSaving ? 'Đang lưu...' : 'Lưu link online'}
              </button>
            </div>
          )}
          {declarationError && <p className="form-error">{declarationError}</p>}
        </div>
      );
    }

    const record = getApplyDocRecord(doc.id);
    const isUploading = uploadingDocId === doc.id;
    const uploadError = uploadErrors[doc.id];

    return (
      <div className="profile-doc-upload-cell">
        {record?.uploaded ? (
          <div className="profile-doc-uploaded">
            <span className="profile-doc-file-name" title={record.original_name}>
              {record.original_name}
            </span>
            <div className="profile-doc-upload-actions">
              <button
                type="button"
                className="btn btn-outline btn-sm profile-doc-view-btn"
                onClick={() => api.openApplyDocumentFile(doc.id).catch((err) => {
                  setUploadErrors((prev) => ({ ...prev, [doc.id]: err.message }));
                })}
              >
                Xem file
              </button>
              <label className="btn btn-primary btn-sm profile-doc-upload-btn">
                {isUploading ? 'Đang tải...' : 'Thay file'}
                <input
                  type="file"
                  accept={ACCEPTED_FILE_TYPES}
                  disabled={isUploading}
                  hidden
                  onChange={(e) => handleApplyDocUpload(doc.id, e)}
                />
              </label>
            </div>
          </div>
        ) : (
          <label className="btn btn-primary btn-sm profile-doc-upload-btn">
            {isUploading ? 'Đang tải lên...' : 'Chọn file tải lên'}
            <input
              type="file"
              accept={ACCEPTED_FILE_TYPES}
              disabled={isUploading}
              hidden
              onChange={(e) => handleApplyDocUpload(doc.id, e)}
            />
          </label>
        )}
        <span className="profile-doc-file-hint">{ACCEPTED_FILE_HINT}</span>
        {uploadError && <p className="form-error profile-doc-upload-error">{uploadError}</p>}
        {doc.id === 'language' && renderLanguageScoreForm()}
      </div>
    );
  };

  const renderDocColumns = (doc) => {
    const record = getApplyDocRecord(doc.id);
    return (
      <div className="profile-doc-columns">
        <div className="profile-doc-col profile-doc-col-mentor">
          {renderMentorStatus(doc, record)}
        </div>
        <div className="profile-doc-col profile-doc-col-request">
          {renderMenteeRequestColumn(doc)}
        </div>
        <div className="profile-doc-col profile-doc-col-upload">
          {renderUploadColumn(doc)}
        </div>
      </div>
    );
  };

  const handleProfileSubmit = async (event) => {
    event.preventDefault();
    setProfileSaving(true);
    setProfileMessage('');
    setProfileError('');

    try {
      const updated = await api.updateProfile({
        full_name: fullName,
        date_of_birth: dateOfBirth,
        ...(mentorLocked ? {} : { mentor }),
        apply_clone_email: applyCloneEmail,
        apply_clone_password: applyClonePassword,
        scholarship_system: scholarshipSystem,
        apply_degree_level: applyDegreeLevel,
        ...(user?.mentor === 'Thanh Hà'
          ? { term3_2027_language_semester: term3LanguageSemester }
          : {}),
        parent_email: parentEmail,
        zalo_phone: zaloPhone,
      });
      updateUser(updated);
      setProfileMessage('Đã lưu thông tin cá nhân.');
    } catch (err) {
      setProfileError(err.message);
    } finally {
      setProfileSaving(false);
    }
  };

  const handlePasswordSubmit = async (event) => {
    event.preventDefault();
    setPasswordMessage('');
    setPasswordError('');

    if (newPassword !== confirmPassword) {
      setPasswordError('Mật khẩu mới không khớp.');
      return;
    }

    setPasswordSaving(true);

    try {
      await api.changePassword({
        current_password: currentPassword,
        new_password: newPassword,
      });
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
      setPasswordMessage('Đổi mật khẩu thành công.');
    } catch (err) {
      setPasswordError(err.message);
    } finally {
      setPasswordSaving(false);
    }
  };

  const handleFeedbackSubmit = async (event) => {
    event.preventDefault();
    if (!feedback.trim()) return;

    setFeedbackSubmitting(true);
    setFeedbackMessage('');
    setFeedbackError('');

    try {
      const created = await api.submitFeedback({ content: feedback.trim() });
      setFeedback('');
      setFeedbackList((prev) => [created, ...prev]);
      setFeedbackMessage('Cảm ơn bạn! Phản hồi đã được ghi nhận.');
    } catch (err) {
      setFeedbackError(err.message);
    } finally {
      setFeedbackSubmitting(false);
    }
  };

  const handleFeedbackThreadReply = async (item) => {
    const content = (feedbackReplyDrafts[item.id] || '').trim();
    if (!content) return;

    setFeedbackReplySubmitting(item.id);
    setFeedbackError('');
    setFeedbackMessage('');
    try {
      const updated = await api.replyFeedback(item.id, { content });
      setFeedbackList((prev) => prev.map((row) => (row.id === item.id ? updated : row)));
      setFeedbackReplyDrafts((prev) => ({ ...prev, [item.id]: '' }));
      setExpandedFeedbackThreads((prev) => ({ ...prev, [item.id]: true }));
      setFeedbackMessage('Đã gửi phản hồi tới mentor.');
    } catch (err) {
      setFeedbackError(err.message);
    } finally {
      setFeedbackReplySubmitting('');
    }
  };

  const isFeedbackThreadExpanded = (item) => {
    if (expandedFeedbackThreads[item.id] != null) {
      return expandedFeedbackThreads[item.id];
    }
    const seen = readSeenFeedbackThreads();
    return item.mentee_unread || seen[item.id] !== feedbackThreadSignature(item);
  };

  const toggleFeedbackThread = (item) => {
    const expanded = isFeedbackThreadExpanded(item);
    setExpandedFeedbackThreads((prev) => ({ ...prev, [item.id]: !expanded }));
  };

  const handleFeedbackMarkSeen = async (item) => {
    setFeedbackError('');
    try {
      if (item.mentee_unread) {
        await api.ackFeedback(item.id);
      }
      const updatedItem = { ...item, mentee_unread: false };
      saveSeenFeedbackThread(item.id, feedbackThreadSignature(updatedItem));
      setExpandedFeedbackThreads((prev) => ({ ...prev, [item.id]: false }));
      setFeedbackList((prev) =>
        prev.map((row) => (row.id === item.id ? updatedItem : row)),
      );
      if (item.mentee_unread) {
        setGeneralFeedbackUnread((prev) => Math.max(0, prev - 1));
      }
    } catch (err) {
      setFeedbackError(err.message);
    }
  };

  const handleFeedbackDelete = async (item) => {
    if (!window.confirm('Bạn có chắc muốn xóa tin nhắn này? Hành động không thể hoàn tác.')) return;

    setFeedbackDeletingId(item.id);
    setFeedbackError('');
    setFeedbackMessage('');
    try {
      await api.deleteFeedback(item.id);
      setFeedbackList((prev) => prev.filter((row) => row.id !== item.id));
      setExpandedFeedbackThreads((prev) => {
        const next = { ...prev };
        delete next[item.id];
        return next;
      });
      setFeedbackMessage('Đã xóa tin nhắn.');
    } catch (err) {
      setFeedbackError(err.message);
    } finally {
      setFeedbackDeletingId('');
    }
  };

  const renderSectionContent = (sectionId) => {
    if (sectionId === 'account') {
      return (
        <>
          <h2>Tài khoản và mật khẩu</h2>
          <p className="profile-panel-desc">
            Cập nhật thông tin cá nhân và mật khẩu đăng nhập của bạn.
          </p>

          <div className="profile-card">
            <h3>Thông tin cá nhân</h3>
            {profileInfoReminder && (
              <div
                className={`profile-missing-reminder${
                  profileInfoReminderUnread ? ' profile-missing-reminder-unread' : ''
                }`}
                role="status"
              >
                <div className="profile-missing-reminder-head">
                  <strong>
                    {profileInfoReminder.message ||
                      'Vui lòng hoàn thiện thông tin cá nhân bạn nhé'}
                  </strong>
                  {profileInfoReminderUnread && (
                    <button
                      type="button"
                      className="btn btn-outline btn-sm profile-mark-seen-btn"
                      onClick={handleProfileInfoReminderMarkSeen}
                    >
                      Đã xem
                    </button>
                  )}
                </div>
                {profileInfoReminder.items?.length > 0 && (
                  <ul>
                    {profileInfoReminder.items.map((item) => (
                      <li key={item.key}>{item.label}</li>
                    ))}
                  </ul>
                )}
              </div>
            )}
            <form onSubmit={handleProfileSubmit} className="auth-form">
              <label>
                Họ và tên
                <input
                  type="text"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  placeholder="Nhập họ và tên"
                />
              </label>
              <label>
                Số Zalo
                <input
                  type="tel"
                  value={zaloPhone}
                  onChange={(e) => setZaloPhone(e.target.value)}
                  placeholder="0901234567"
                  inputMode="numeric"
                />
              </label>
              <label>
                Ngày tháng năm sinh
                <input
                  type="date"
                  value={dateOfBirth}
                  onChange={(e) => setDateOfBirth(e.target.value)}
                />
              </label>
              <label>
                App học bổng
                <select
                  value={scholarshipSystem}
                  onChange={(e) => setScholarshipSystem(e.target.value)}
                  className="profile-select"
                >
                  {SCHOLARSHIP_OPTIONS.map((option) => (
                    <option key={option.value || 'empty'} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Hệ apply
                <select
                  value={applyDegreeLevel}
                  onChange={(e) => setApplyDegreeLevel(e.target.value)}
                  className="profile-select"
                >
                  {APPLY_DEGREE_LEVELS.map((option) => (
                    <option key={option.value || 'empty'} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>
              {mentor === 'Thanh Hà' && (
                <label>
                  Kì 3/2027 có dự định đi 1 kì tiếng không?
                  <select
                    value={term3LanguageSemester}
                    onChange={(e) => setTerm3LanguageSemester(e.target.value)}
                    className="profile-select"
                  >
                    {TERM3_2027_LANGUAGE_OPTIONS.map((option) => (
                      <option key={option.value || 'empty'} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </label>
              )}
              <label>
                Email phụ huynh
                <input
                  type="email"
                  value={parentEmail}
                  onChange={(e) => setParentEmail(e.target.value)}
                  placeholder="email.phu.huynh@gmail.com"
                  autoComplete="off"
                />
                <span className="profile-field-hint">
                  Tài khoản phụ huynh mặc định mật khẩu: TronTru2027 — xem hồ sơ con (chỉ đọc).
                </span>
              </label>
              <label>
                Mentor
                <select
                  value={mentor}
                  onChange={(e) => setMentor(e.target.value)}
                  disabled={mentorLocked}
                  className="profile-select"
                >
                  <option value="">Chọn mentor</option>
                  {MENTORS.filter(Boolean).map((name) => (
                    <option key={name} value={name}>
                      {name}
                    </option>
                  ))}
                </select>
              </label>
              {MENTOR_APPLY_SETUP[mentor] && (
                <>
                  <div className="profile-mentor-note">
                    <strong>Mentor {mentor}:</strong>
                    <p>{getMentorApplyNote(mentor)}</p>
                    <a
                      href={MENTOR_FORWARD_GUIDE.href}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="profile-mentor-link"
                    >
                      {MENTOR_FORWARD_GUIDE.label}
                    </a>
                  </div>
                  <label>
                    Email (clone) dùng để apply
                    <input
                      type="email"
                      value={applyCloneEmail}
                      onChange={(e) => setApplyCloneEmail(e.target.value)}
                      placeholder="vidu.apply@gmail.com"
                      autoComplete="off"
                    />
                  </label>
                  <label>
                    Pass
                    <input
                      type="text"
                      value={applyClonePassword}
                      onChange={(e) => setApplyClonePassword(e.target.value)}
                      placeholder="Mật khẩu email clone"
                      autoComplete="off"
                    />
                  </label>
                </>
              )}
              <div className="profile-readonly">
                <div className="info-row">
                  <span className="info-label">Tên đăng nhập</span>
                  <span className="info-value">{user?.username}</span>
                </div>
                <div className="info-row">
                  <span className="info-label">Email</span>
                  <span className="info-value">{user?.email}</span>
                </div>
              </div>
              {profileError && <p className="form-error">{profileError}</p>}
              {profileMessage && <p className="form-success">{profileMessage}</p>}
              <button type="submit" className="btn btn-primary" disabled={profileSaving}>
                {profileSaving ? 'Đang lưu...' : 'Lưu thông tin'}
              </button>
            </form>
          </div>

          <div className="profile-card">
            <h3>Đổi mật khẩu</h3>
            <form onSubmit={handlePasswordSubmit} className="auth-form">
              <label>
                Mật khẩu hiện tại
                <input
                  type="password"
                  value={currentPassword}
                  onChange={(e) => setCurrentPassword(e.target.value)}
                  autoComplete="current-password"
                />
              </label>
              <label>
                Mật khẩu mới
                <input
                  type="password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  autoComplete="new-password"
                />
              </label>
              <label>
                Xác nhận mật khẩu mới
                <input
                  type="password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  autoComplete="new-password"
                />
              </label>
              {passwordError && <p className="form-error">{passwordError}</p>}
              {passwordMessage && <p className="form-success">{passwordMessage}</p>}
              <button type="submit" className="btn btn-outline" disabled={passwordSaving}>
                {passwordSaving ? 'Đang đổi...' : 'Đổi mật khẩu'}
              </button>
            </form>
          </div>

          <div className="profile-card">
            <DeviceModeSwitcher />
          </div>
        </>
      );
    }

    if (sectionId === 'documents') {
      return (
        <>
          <h2>Giấy tờ apply</h2>
          <p className="profile-panel-desc">
            Tải lên và quản lý các giấy tờ hồ sơ apply. Bấm dấu{' '}
            <span className="doc-hint-inline">?</span> bên cạnh từng mục để xem hướng dẫn chi
            tiết.
          </p>

          <div className="profile-card profile-general-notes">
            <h3>Lưu ý chung</h3>
            <ul>
              {APPLY_GENERAL_NOTES.map((note) => (
                <li key={note}>{note}</li>
              ))}
            </ul>
          </div>

          <div className="profile-card profile-preferred-schools">
            <h3>Trường ưa thích</h3>
            <p className="profile-preferred-schools-prompt">
              Nếu bạn nào đã có sẵn trường mình thích thì note ở đây cho c nhé, c sẽ cân nhắc và báo
              lại khi vào mùa là có rải được không nha:
            </p>
            <textarea
              className="profile-textarea"
              value={preferredSchoolsNote}
              onChange={(e) => setPreferredSchoolsNote(e.target.value)}
              placeholder="Ví dụ: PKU, Tsinghua, Fudan..."
              rows={3}
            />
            <div className="profile-preferred-schools-actions">
              <button
                type="button"
                className="btn btn-primary btn-sm"
                disabled={preferredSchoolsSaving}
                onClick={handleSavePreferredSchoolsNote}
              >
                {preferredSchoolsSaving ? 'Đang lưu...' : 'Lưu ghi chú'}
              </button>
              {preferredSchoolsMessage && (
                <span className="form-success">{preferredSchoolsMessage}</span>
              )}
              {preferredSchoolsError && (
                <span className="form-error">{preferredSchoolsError}</span>
              )}
            </div>
          </div>

          <div className="profile-card">
            <div className="profile-doc-summary">
              <span>
                {applyDocSummary.uploaded_count} / {applyDocSummary.total_count || APPLY_DOCUMENTS.length}{' '}
                giấy tờ đã tải lên
              </span>
            </div>
            {missingReminder?.items?.length > 0 && (
              missingReminderExpanded ? (
                <div
                  className={`profile-missing-reminder${
                    missingReminderUnread ? ' profile-missing-reminder-unread' : ''
                  }`}
                  role="status"
                >
                  <div className="profile-missing-reminder-head">
                    <strong>{missingReminder.message || 'Bạn cần làm các loại giấy tờ sau'}</strong>
                    <button
                      type="button"
                      className="btn btn-outline btn-sm profile-mark-seen-btn"
                      onClick={handleMissingReminderMarkSeen}
                    >
                      Đã xem
                    </button>
                  </div>
                  <ul>
                    {missingReminder.items.map((item) => (
                      <li key={item.doc_id}>{item.label}</li>
                    ))}
                  </ul>
                </div>
              ) : (
                <button
                  type="button"
                  className="profile-missing-reminder-collapsed"
                  onClick={() => setMissingReminderExpanded(true)}
                >
                  Bạn cần làm {missingReminder.items.length} loại giấy tờ — bấm để xem lại
                </button>
              )
            )}
            {applyDocsError && <p className="form-error">{applyDocsError}</p>}
            {applyDocsLoading ? (
              <p className="profile-note">Đang tải danh sách giấy tờ...</p>
            ) : (
              <>
                <div className="profile-doc-header">
                  <div className="profile-doc-info">
                    <span className="profile-doc-header-label">Giấy tờ</span>
                  </div>
                  <div className="profile-doc-columns">
                    <div className="profile-doc-col profile-doc-col-mentor">
                      <span className="profile-doc-header-label">Đợi mentor phản hồi</span>
                    </div>
                    <div className="profile-doc-col profile-doc-col-request">
                      <span className="profile-doc-header-label">Yêu cầu mentor</span>
                    </div>
                    <div className="profile-doc-col profile-doc-col-upload">
                      <span className="profile-doc-header-label">Upload tài liệu</span>
                    </div>
                  </div>
                </div>
                <div className="profile-doc-list">
                  {APPLY_DOCUMENTS.map((doc, index) => {
                    const record = getApplyDocRecord(doc.id);
                    const mentorApproved = isDocMentorApproved(doc, record, personalDeclaration);
                    return (
                    <div key={doc.id} className="profile-doc-item">
                      <div className="profile-doc-info">
                        {mentorApproved && (
                          <span
                            className="profile-doc-approved-tick"
                            title="Mentor đã duyệt"
                            aria-label="Mentor đã duyệt"
                          >
                            ✓
                          </span>
                        )}
                        <span className="profile-doc-num">{index + 1}.</span>
                        <span className="profile-doc-label">{doc.label}</span>
                        <DocHintButton
                          docId={doc.id}
                          openId={openHintId}
                          setOpenId={setOpenHintId}
                          hint={doc.hint}
                        />
                        {doc.optional && (
                          <span className="profile-doc-optional">nếu có</span>
                        )}
                      </div>
                      {renderDocColumns(doc)}
                    </div>
                    );
                  })}
                </div>
              </>
            )}
            {declarationError && (
              <p className="form-error profile-doc-error">{declarationError}</p>
            )}
          </div>
        </>
      );
    }

    if (sectionId === 'apply-progress') {
      return <ApplyProgressSection />;
    }

    if (sectionId === 'hdnk-nckh') {
      return <HdnkNckhSection />;
    }

    if (sectionId === 'profile-activities') {
      return <ProfileActivitiesSection user={user} />;
    }

    if (sectionId !== 'feedback') {
      return null;
    }

    return (
      <>
        <h2>Phản hồi</h2>
        <p className="profile-panel-desc">
          Gửi góp ý hoặc báo lỗi. Phản hồi được lưu vào hệ thống và sẽ được phản hồi lại khi đã xử lí.
        </p>

        <div className="profile-card">
          <h3>Gửi phản hồi mới</h3>
          <form onSubmit={handleFeedbackSubmit} className="auth-form">
            <label>
              Nội dung phản hồi
              <textarea
                className="profile-textarea"
                rows={5}
                value={feedback}
                onChange={(e) => setFeedback(e.target.value)}
                placeholder="Viết phản hồi của bạn tại đây..."
              />
            </label>
            {feedbackError && <p className="form-error">{feedbackError}</p>}
            {feedbackMessage && <p className="form-success">{feedbackMessage}</p>}
            <button
              type="submit"
              className="btn btn-primary"
              disabled={!feedback.trim() || feedbackSubmitting}
            >
              {feedbackSubmitting ? 'Đang gửi...' : 'Gửi phản hồi'}
            </button>
          </form>
        </div>

        <div className="profile-card">
          <h3>Lịch sử phản hồi</h3>
          {feedbackLoadError && <p className="form-error">{feedbackLoadError}</p>}
          {feedbackLoading ? (
            <p className="profile-note">Đang tải...</p>
          ) : feedbackList.length === 0 ? (
            <p className="profile-note">Bạn chưa gửi phản hồi nào.</p>
          ) : (
            <div className="feedback-list">
              {feedbackList.map((item, index) => {
                const expanded = isFeedbackThreadExpanded(item);
                return (
                  <article
                    key={item.id}
                    className={`feedback-item${expanded ? '' : ' feedback-item-collapsed'}${
                      item.mentee_unread ? ' feedback-item-unread' : ''
                    }`}
                  >
                    <div className="feedback-item-top">
                      <button
                        type="button"
                        className="feedback-item-toggle"
                        onClick={() => toggleFeedbackThread(item)}
                        aria-expanded={expanded}
                      >
                        <div className="feedback-item-header-main">
                          <strong>Tin #{feedbackList.length - index}</strong>
                          <span className={`feedback-status${feedbackStatusClassName(item)}`}>
                            {feedbackDisplayStatus(item)}
                          </span>
                        </div>
                        {!expanded && (
                          <p className="feedback-item-preview">{getLastMessagePreview(item)}</p>
                        )}
                      </button>
                      <div className="feedback-item-meta">
                        <time className="feedback-time" dateTime={item.created_at}>
                          {formatDateTime(item.created_at)}
                        </time>
                        {expanded && (
                          <button
                            type="button"
                            className="btn btn-outline btn-sm feedback-mark-seen-btn"
                            onClick={() => handleFeedbackMarkSeen(item)}
                          >
                            Đã xem
                          </button>
                        )}
                        <button
                          type="button"
                          className="feedback-delete-btn"
                          aria-label="Xóa tin nhắn"
                          title="Xóa tin nhắn"
                          disabled={feedbackDeletingId === item.id}
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
                    {expanded && (
                      <>
                        <div className="feedback-thread">
                          {(item.messages || [
                            { sender: 'mentee', content: item.content, created_at: item.created_at },
                          ]).map((message, messageIndex) => (
                            <div
                              key={message.id || `${item.id}-${messageIndex}`}
                              className={`feedback-thread-message feedback-thread-${message.sender}`}
                            >
                              <span className="feedback-thread-label">
                                {message.sender === 'mentor' ? 'Mentor' : 'Bạn'}
                              </span>
                              <p>{message.content}</p>
                              {message.created_at && (
                                <time className="feedback-reply-time" dateTime={message.created_at}>
                                  {formatDateTime(message.created_at)}
                                </time>
                              )}
                            </div>
                          ))}
                        </div>
                        <label className="feedback-reply-compose">
                          Trả lời tiếp
                          <textarea
                            className="profile-textarea"
                            rows={3}
                            value={feedbackReplyDrafts[item.id] || ''}
                            onChange={(e) =>
                              setFeedbackReplyDrafts((prev) => ({ ...prev, [item.id]: e.target.value }))
                            }
                            placeholder="Viết phản hồi tiếp theo..."
                          />
                        </label>
                        <div className="feedback-item-actions">
                          <button
                            type="button"
                            className="btn btn-outline btn-sm"
                            disabled={
                              !feedbackReplyDrafts[item.id]?.trim() ||
                              feedbackReplySubmitting === item.id
                            }
                            onClick={() => handleFeedbackThreadReply(item)}
                          >
                            {feedbackReplySubmitting === item.id ? 'Đang gửi...' : 'Gửi phản hồi'}
                          </button>
                        </div>
                      </>
                    )}
                  </article>
                );
              })}
            </div>
          )}
        </div>
      </>
    );
  };

  const renderSectionNotify = (item) => {
    if (item.id === 'documents' && feedbackUnreadCount > 0) {
      return (
        <span className="profile-nav-notify">
          <span className="profile-nav-notify-dot" aria-hidden="true" />
          Mới
        </span>
      );
    }
    if (item.id === 'feedback' && generalFeedbackUnread > 0) {
      return (
        <span className="profile-nav-notify">
          <span className="profile-nav-notify-dot" aria-hidden="true" />
          Mới
        </span>
      );
    }
    if (item.id === 'apply-progress' && applyProgressUnread) {
      return (
        <span className="profile-nav-notify">
          <span className="profile-nav-notify-dot" aria-hidden="true" />
          Mới
        </span>
      );
    }
    return null;
  };

  const togglePhoneSection = (sectionId) => {
    setActiveSection(sectionId);
    window.requestAnimationFrame(() => {
      window.scrollTo({ top: 0, behavior: 'smooth' });
    });
  };

  if (isPhone) {
    const activeItem =
      menuItems.find((item) => item.id === activeSection) || menuItems[0] || null;
    const currentSection = activeItem?.id || 'account';

    return (
      <div className="profile-page profile-page-phone">
        <div className="profile-phone-head">
          <h1>Tôi</h1>
          <p className="muted profile-phone-hint">
            Mục {menuItems.findIndex((item) => item.id === currentSection) + 1}:{' '}
            {activeItem?.label}
          </p>
          <div className="profile-phone-tabs">
            {menuItems.map((item, index) => (
              <button
                key={item.id}
                type="button"
                className={`profile-phone-tab${currentSection === item.id ? ' active' : ''}`}
                onClick={() => togglePhoneSection(item.id)}
              >
                <span className="profile-phone-tab-num">{index + 1}</span>
                <span className="profile-phone-tab-label">{item.label}</span>
                {renderSectionNotify(item)}
              </button>
            ))}
          </div>
        </div>
        <div
          className="profile-phone-content profile-panel"
          id={`profile-section-${currentSection}`}
        >
          {renderSectionContent(currentSection)}
        </div>
        <ProfileScrollTop />
      </div>
    );
  }

  return (
    <div className="profile-page">
      <aside className="profile-sidebar">
        <h1>Tôi</h1>
        <nav className="profile-nav">
          {menuItems.map((item, index) => (
            <button
              key={item.id}
              type="button"
              className={`profile-nav-item${activeSection === item.id ? ' active' : ''}`}
              onClick={() => setActiveSection(item.id)}
            >
              <span className="profile-nav-item-main">
                <span className="profile-nav-num">{index + 1}.</span>
                {item.label}
              </span>
              {item.id === 'documents' && feedbackUnreadCount > 0 && (
                <span className="profile-nav-notify">
                  <span className="profile-nav-notify-dot" aria-hidden="true" />
                  Bạn có thông báo mới
                </span>
              )}
              {item.id === 'feedback' && generalFeedbackUnread > 0 && (
                <span className="profile-nav-notify">
                  <span className="profile-nav-notify-dot" aria-hidden="true" />
                  Bạn có thông báo mới
                </span>
              )}
              {item.id === 'apply-progress' && applyProgressUnread && (
                <span className="profile-nav-notify">
                  <span className="profile-nav-notify-dot" aria-hidden="true" />
                  Bạn có thông báo mới
                </span>
              )}
            </button>
          ))}
        </nav>
      </aside>

      <section className="profile-panel">{renderSectionContent(activeSection)}</section>
    </div>
  );
}
