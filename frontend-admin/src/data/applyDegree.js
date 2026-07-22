import { formatMenteeNameForMentor } from '../utils/mentorDisplay';

export const APPLY_DEGREE_LEVELS = [
  { value: 'undergrad', label: 'Hệ đại (本科)' },
  { value: 'master', label: 'Hệ thạc (硕士)' },
  { value: 'phd', label: 'Tiến sĩ (博士)' },
];

export const APPLY_DEGREE_FILTER_OPTIONS = [
  { value: 'all', label: 'Tất cả hệ' },
  ...APPLY_DEGREE_LEVELS,
];

export const APPLY_DEGREE_SELECT_OPTIONS = [
  { value: '', label: 'Chọn hệ apply' },
  ...APPLY_DEGREE_LEVELS,
];

export const MENTOR_APPLY_DIRECTION_OPTIONS = [
  { value: '', label: 'Chọn phân loại' },
  { value: 'kinh_te', label: 'Kinh tế' },
  { value: 'giao_duc', label: 'Giáo dục' },
  { value: 'truyen_thong', label: 'Truyền thông' },
  { value: 'quan_he_quoc_te', label: 'Quan hệ quốc tế' },
  { value: 'duoc', label: 'Dược' },
  { value: 'khac', label: 'Khác' },
];

export const TERM3_2027_LANGUAGE_OPTIONS = [
  { value: 'co', label: 'Có — dự định đi 1 kì tiếng' },
  { value: 'khong', label: 'Không' },
];

export const TERM3_LANGUAGE_SELECT_OPTIONS = [
  { value: '', label: 'Chọn 1 kì tiếng' },
  ...TERM3_2027_LANGUAGE_OPTIONS,
];

export const TERM3_LANGUAGE_SHORT_OPTIONS = [
  { value: '', label: 'Chọn' },
  { value: 'co', label: 'Có' },
  { value: 'khong', label: 'Không' },
];

export const APPLY_LANGUAGE_OPTIONS = [
  { value: '', label: 'Chọn hệ tiếng' },
  { value: 'english', label: 'Tiếng Anh' },
  { value: 'chinese', label: 'Tiếng Trung' },
];

export const APPLY_LANGUAGE_FILTER_OPTIONS = [
  { value: 'all', label: 'Tất cả tiếng' },
  { value: 'english', label: 'Tiếng Anh' },
  { value: 'chinese', label: 'Tiếng Trung' },
];

export const APPLY_DIRECTION_FILTER_OPTIONS = [
  { value: 'all', label: 'Tất cả hướng' },
  ...MENTOR_APPLY_DIRECTION_OPTIONS.filter((item) => item.value),
];

export const TERM3_LANGUAGE_FILTER_OPTIONS = [
  { value: 'all', label: 'Tất cả kì tiếng' },
  { value: 'co', label: 'Có 1 kì tiếng' },
  { value: 'khong', label: 'Không' },
];

const LEGACY_DIRECTION_MAP = {
  'kinh tế': 'kinh_te',
  'kinh te': 'kinh_te',
  'giáo dục': 'giao_duc',
  'giao duc': 'giao_duc',
  'truyền thông': 'truyen_thong',
  'truyen thong': 'truyen_thong',
  'quan hệ quốc tế': 'quan_he_quoc_te',
  'quan he quoc te': 'quan_he_quoc_te',
  'dược': 'duoc',
  'duoc': 'duoc',
  'khác': 'khac',
  'khac': 'khac',
};

export function normalizeMentorApplyDirectionValue(value) {
  const raw = (value || '').trim();
  if (!raw) return '';
  const lowered = raw.toLowerCase();
  if (MENTOR_APPLY_DIRECTION_OPTIONS.some((item) => item.value === lowered)) {
    return lowered;
  }
  return LEGACY_DIRECTION_MAP[lowered] || LEGACY_DIRECTION_MAP[raw] || '';
}

export const MENTOR_APPLY_DIRECTION_FIELDS = [
  'mentor_apply_direction',
  'mentor_apply_direction_2',
  'mentor_apply_direction_3',
];

export function mentorApplyDirectionWishes(mentee) {
  const codes = [];
  MENTOR_APPLY_DIRECTION_FIELDS.forEach((field) => {
    const code = normalizeMentorApplyDirectionValue(mentee?.[field]);
    if (code && !codes.includes(code)) codes.push(code);
  });
  return codes;
}

export function mentorApplyDirectionCombinedLabel(mentee) {
  const combined = (mentee?.mentor_apply_direction_combined_label || '').trim();
  if (combined) return combined;
  const labels = mentorApplyDirectionWishes(mentee)
    .map((code) => MENTOR_APPLY_DIRECTION_OPTIONS.find((item) => item.value === code)?.label)
    .filter(Boolean);
  return labels.join(' / ');
}

export function applyDegreeLevelLabel(value) {
  const match = APPLY_DEGREE_LEVELS.find((item) => item.value === (value || '').trim());
  return match?.label || '—';
}

export function applyDegreeLevelShortLabel(value) {
  const match = APPLY_DEGREE_LEVELS.find((item) => item.value === (value || '').trim());
  if (!match) return '';
  return match.label.replace(/\s*\([^)]*\)/, '').trim();
}

export function mentorApplyDirectionLabel(value) {
  const normalized = normalizeMentorApplyDirectionValue(value);
  const match = MENTOR_APPLY_DIRECTION_OPTIONS.find((item) => item.value === normalized);
  if (match?.value) return match.label;
  const raw = (value || '').trim();
  return raw || '—';
}

export function term3LanguageSemesterLabel(value) {
  const match = TERM3_2027_LANGUAGE_OPTIONS.find((item) => item.value === (value || '').trim());
  return match?.label || '—';
}

export function scholarshipLanguageShortLabel(mentee) {
  const system = normalizeScholarshipSystemValue(mentee);
  if (system === 'english') return 'Tiếng Anh';
  if (system === 'chinese') return 'Tiếng Trung';
  const label = (mentee?.scholarship_system_label || '').trim();
  if (/tiếng anh/i.test(label)) return 'Tiếng Anh';
  if (/tiếng trung/i.test(label)) return 'Tiếng Trung';
  return label || '';
}

export function normalizeScholarshipSystemValue(menteeOrValue) {
  if (typeof menteeOrValue === 'string') {
    const raw = menteeOrValue.trim().toLowerCase();
    return raw === 'english' || raw === 'chinese' ? raw : '';
  }
  const system = (menteeOrValue?.scholarship_system || '').trim().toLowerCase();
  if (system === 'english' || system === 'chinese') return system;
  const label = (menteeOrValue?.scholarship_system_label || '').trim();
  if (/tiếng anh/i.test(label)) return 'english';
  if (/tiếng trung/i.test(label)) return 'chinese';
  return '';
}

export function researchDirectionDisplayText(mentee) {
  const raw = (mentee?.research_direction || '').trim();
  if (!raw) return '';
  const lowered = raw.toLowerCase();
  if (lowered === 'co') return 'Hướng NC';
  if (lowered === 'khong') return '';
  return mentee?.research_direction_label || raw;
}

export function menteeHasResearchDirection(mentee) {
  return Boolean(researchDirectionDisplayText(mentee));
}

export function applyDegreeLevelShortDisplay(mentee) {
  return (
    applyDegreeLevelShortLabel(mentee?.apply_degree_level) ||
    (mentee?.apply_degree_level_label || '').replace(/\s*\([^)]*\)/, '').trim() ||
    '—'
  );
}

export function menteeClassificationMiddleLabel(mentee) {
  const research = researchDirectionDisplayText(mentee);
  if (research) return research;
  return (
    applyDegreeLevelShortLabel(mentee?.apply_degree_level) ||
    (mentee?.apply_degree_level_label || '').replace(/\s*\([^)]*\)/, '').trim()
  );
}

export function menteeClassificationSummaryLine(mentee) {
  const direction =
    mentorApplyDirectionCombinedLabel(mentee) ||
    mentorApplyDirectionLabel(mentee?.mentor_apply_direction);
  const middle = menteeClassificationMiddleLabel(mentee);
  const language = scholarshipLanguageShortLabel(mentee);
  const parts = [direction, middle, language].filter((part) => part && part !== '—');
  return parts.length ? parts.join(' - ') : 'Chưa phân loại';
}

/** Tên phụ cho mời tham gia HDNK: khối ngành-hướng NC-hệ */
export function menteeActivityInviteLabel(mentee) {
  const major =
    mentorApplyDirectionCombinedLabel(mentee) ||
    mentorApplyDirectionLabel(mentee?.mentor_apply_direction);
  const research = researchDirectionDisplayText(mentee);
  const degree = applyDegreeLevelShortDisplay(mentee);
  const parts = [major, research, degree].filter((part) => part && part !== '—');
  return parts.length ? parts.join('-') : 'Chưa phân loại';
}

export function formatMenteeActivityInviteOption(mentee) {
  const name = (
    (mentee?.display_name || '').trim() ||
    formatMenteeNameForMentor(mentee, 'Mentee')
  );
  return `${name} (${menteeActivityInviteLabel(mentee)})`;
}

export function patchMenteeSummaryFromDetail(summary, detail) {
  return {
    ...summary,
    mentor_apply_direction: detail.mentor_apply_direction || '',
    mentor_apply_direction_label: detail.mentor_apply_direction_label || mentorApplyDirectionLabel(
      detail.mentor_apply_direction,
    ),
    mentor_apply_direction_2: detail.mentor_apply_direction_2 || '',
    mentor_apply_direction_2_label: detail.mentor_apply_direction_2_label || '',
    mentor_apply_direction_3: detail.mentor_apply_direction_3 || '',
    mentor_apply_direction_3_label: detail.mentor_apply_direction_3_label || '',
    mentor_apply_direction_combined_label:
      detail.mentor_apply_direction_combined_label ||
      mentorApplyDirectionCombinedLabel(detail),
    apply_degree_level: detail.apply_degree_level || '',
    apply_degree_level_label: detail.apply_degree_level_label || applyDegreeLevelLabel(
      detail.apply_degree_level,
    ),
    term3_2027_language_semester: detail.term3_2027_language_semester || '',
    term3_2027_language_semester_label: detail.term3_2027_language_semester_label ||
      term3LanguageSemesterLabel(detail.term3_2027_language_semester),
    research_direction: detail.research_direction || '',
    research_direction_label:
      detail.research_direction_label || researchDirectionDisplayText(detail),
    scholarship_system: detail.scholarship_system || summary.scholarship_system || '',
    scholarship_system_label:
      detail.scholarship_system_label || summary.scholarship_system_label || '',
  };
}
