export const APPLY_PROGRESS_ROW_DEFAULT = 8;
export const APPLY_PROGRESS_ROW_MIN = 1;
export const APPLY_PROGRESS_ROW_MAX = 20;

export const SCHOLARSHIP_TYPE_OPTIONS = [
  'CSC',
  'CIS',
  'SGS',
  'Học bổng tỉnh/thành phố',
  'Học bổng trường',
  'Học bổng viện',
  'Tự phí',
];

export const PROGRESS_BASE_OPTIONS = [
  'Chờ submit',
  'Đã submit',
  'Cần sửa',
  'Chờ phỏng vấn',
  'Đã phỏng vấn',
  'Nominate',
  'Được học bổng',
  'Trượt hb',
];

export const PROGRESS_L1_ONLY = 'Chờ UP hồ sơ';
export const PROGRESS_L2_ONLY = 'Đã up xong còn thiếu tài liệu';

export const APPLY_PROGRESS_COLUMNS = [
  { key: 'school_name', label: 'Tên trường' },
  { key: 'apply_major', label: 'Ngành apply' },
  { key: 'link', label: 'Link' },
  { key: 'scholarship_type', label: 'Loại hb', type: 'select', options: SCHOLARSHIP_TYPE_OPTIONS },
  { key: 'allowance', label: 'Trợ cấp' },
  { key: 'registration_fee', label: 'Phí báo danh' },
  { key: 'progress', label: 'Tiến độ', type: 'select', options: PROGRESS_BASE_OPTIONS },
  { key: 'note', label: 'Note' },
];

export function isSelectColumn(column) {
  return column.type === 'select';
}

export function isThanhHaTeam(admin) {
  return (admin?.mentor_name || '').trim() === 'Thanh Hà';
}

export function getProgressToneClass(progress, fullPalette = false) {
  const value = (progress || '').trim();
  if (!value) return '';
  if (value === 'Trượt hb') {
    return 'apply-progress-tone-black';
  }
  if (!fullPalette) return '';
  if (['Chờ submit', 'Cần sửa'].includes(value)) {
    return 'apply-progress-tone-red';
  }
  if (value === 'Được học bổng') {
    return 'apply-progress-tone-dark-red';
  }
  if (value === PROGRESS_L1_ONLY) {
    return 'apply-progress-tone-yellow';
  }
  if (value === PROGRESS_L2_ONLY) {
    return 'apply-progress-tone-orange';
  }
  if (value === 'Đã submit') {
    return 'apply-progress-tone-green';
  }
  if (value === 'Nominate') {
    return 'apply-progress-tone-purple';
  }
  return '';
}

export function getProgressOptionsForAdmin(admin) {
  const isSuperAdmin = Boolean(admin?.is_super_admin);
  const mentor = (admin?.mentor_name || '').trim();
  const displayName = (admin?.full_name || admin?.username || '').trim();
  const isLevel1 =
    Boolean(admin?.is_level1_mentor) ||
    (mentor === 'Thanh Hà' && displayName === mentor);

  if (isSuperAdmin) {
    return [...PROGRESS_BASE_OPTIONS, PROGRESS_L1_ONLY, PROGRESS_L2_ONLY];
  }
  if (isLevel1) {
    return [...PROGRESS_BASE_OPTIONS, PROGRESS_L1_ONLY];
  }
  return [...PROGRESS_BASE_OPTIONS, PROGRESS_L2_ONLY];
}

export function emptyApplyProgressRow(rowNum) {
  return {
    row_num: rowNum,
    school_name: '',
    apply_major: '',
    link: '',
    scholarship_type: '',
    allowance: '',
    registration_fee: '',
    progress: '',
    note: '',
  };
}

export function emptyApplyProgressRows(rowCount = APPLY_PROGRESS_ROW_DEFAULT) {
  const count = Math.max(APPLY_PROGRESS_ROW_MIN, Math.min(APPLY_PROGRESS_ROW_MAX, rowCount));
  return Array.from({ length: count }, (_, index) => emptyApplyProgressRow(index + 1));
}

export function pickApplyProgressFields(row) {
  const result = { row_num: row?.row_num || 0 };
  for (const column of APPLY_PROGRESS_COLUMNS) {
    result[column.key] = row?.[column.key] || '';
  }
  return result;
}

export function normalizeApplyProgressRows(rows, rowCount = APPLY_PROGRESS_ROW_DEFAULT) {
  const source = rows || [];
  const effectiveCount =
    rowCount ||
    source.reduce((max, row) => Math.max(max, row?.row_num || 0), 0) ||
    APPLY_PROGRESS_ROW_DEFAULT;

  return emptyApplyProgressRows(effectiveCount).map((row) => {
    const match = source.find((item) => item.row_num === row.row_num) || {};
    return {
      ...pickApplyProgressFields(match),
      row_num: row.row_num,
      pending: match.pending || null,
      pending_status: match.pending_status || '',
      rejection_note: match.rejection_note || '',
      has_pending: Boolean(match.has_pending),
    };
  });
}

export function getColumnSelectOptions(column, progressOptions) {
  if (column.key === 'progress') {
    return progressOptions?.length ? progressOptions : column.options || PROGRESS_BASE_OPTIONS;
  }
  return column.options || [];
}
